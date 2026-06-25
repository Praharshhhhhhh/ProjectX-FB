from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
from models.device import Device
from services import wireguard_controller
from services import zerotier_controller
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class ProvisionResult:
    success: bool
    tunnel_type: str
    wg_ip: Optional[str] = None
    wg_public_key: Optional[str] = None
    wg_private_key: Optional[str] = None
    conf_content: Optional[str] = None
    network_id: Optional[str] = None
    zerotier_node_id: Optional[str] = None
    error: Optional[str] = None

async def decide_tunnel_type(capability: Optional[dict], forced: Optional[str]) -> str:
    if forced in ("wireguard", "zerotier"):
        return forced
    if not capability:
        return "zerotier"
    if capability.get("has_wireguard_kernel") or (
        capability.get("has_wireguard_userspace")
        and capability.get("ram_mb", 0) >= 256
    ):
        return "wireguard"
    return "zerotier"

async def provision_device(device: Device, db: Session) -> ProvisionResult:
    if device.tunnel_type == "wireguard":
        return await _provision_wireguard(device, db)
    elif device.tunnel_type == "zerotier":
        return await _provision_zerotier(device, db)
    return ProvisionResult(success=False, tunnel_type="unknown", error="tunnel_type not set on device")

async def deprovision_device(device: Device) -> bool:
    try:
        if device.tunnel_type == "wireguard" and device.wg_public_key:
            pass # Peer removal is synced via websocket to the hub
        elif device.tunnel_type == "zerotier" and device.network_id and device.zerotier_node_id:
            await zerotier_controller.deauthorize_member(device.network_id, device.zerotier_node_id)
        return True
    except Exception as e:
        logger.error(f"Failed to deprovision device {device.id}: {e}")
        return False

async def get_tunnel_status(device: Device) -> str:
    if device.tunnel_type == "wireguard" and device.wg_public_key:
        from routers.devices import LIVE_WG_STATUSES
        import time
        last_heartbeat = LIVE_WG_STATUSES.get(device.wg_public_key, 0)
        if last_heartbeat > 0 and (time.time() - last_heartbeat) < 180:
            return "active"
        return "offline"
    elif device.tunnel_type == "zerotier" and device.network_id and device.zerotier_node_id:
        return await zerotier_controller.check_member_status(device.network_id, device.zerotier_node_id)
    return "offline"

async def _provision_wireguard(device: Device, db: Session) -> ProvisionResult:
    try:
        from models import User, UserRole
        
        wg_ip = device.wg_ip
        if not wg_ip:
            wg_ip = wireguard_controller.assign_ip_from_pool(db, device.tenant_id)
            if not wg_ip:
                return ProvisionResult(success=False, tunnel_type="wireguard", error="No IP available in WireGuard pool")
                
        priv_key = device.wg_private_key
        pub_key = device.wg_public_key
        
        if not pub_key:
            priv_key, pub_key = await wireguard_controller.generate_keypair()
            device.wg_private_key = priv_key
            device.wg_public_key = pub_key
        
        owner = db.query(User).filter(User.id == device.owner_id).first()
        is_master = owner and owner.role in (UserRole.master, UserRole.second_master)
        
        if is_master:
            # Generate Hub Config
            peers = []
            other_devices = db.query(Device).filter(
                Device.tenant_id == device.tenant_id,
                Device.tunnel_type == "wireguard",
                Device.is_approved == True,
                Device.id != device.id
            ).all()
            for od in other_devices:
                if od.wg_public_key and od.wg_ip:
                    peers.append({
                        "pubkey": od.wg_public_key,
                        "allowed_ips": f"{od.wg_ip}/32"
                    })
            conf = wireguard_controller.generate_hub_config(
                private_key=priv_key,
                assigned_ip=wg_ip,
                listen_port=51820,
                peers=peers
            )
        else:
            # Generate Client Config
            master_device = db.query(Device).join(User, Device.owner_id == User.id).filter(
                Device.tenant_id == device.tenant_id,
                User.role.in_([UserRole.master, UserRole.second_master]),
                Device.tunnel_type == "wireguard",
                Device.is_approved == True
            ).first()
            
            if master_device:
                server_pubkey = master_device.wg_public_key or ""
                server_endpoint = f"{master_device.lan_ip}:51820" if master_device.lan_ip else "127.0.0.1:51820"
            else:
                # Fallback if no master device is set up yet
                server_pubkey = ""
                server_endpoint = "127.0.0.1:51820"
                
            conf = wireguard_controller.generate_client_config(
                private_key=priv_key,
                assigned_ip=wg_ip,
                server_pubkey=server_pubkey,
                server_endpoint=server_endpoint,
                client_pubkey=pub_key
            )
            
        return ProvisionResult(
            success=True, 
            tunnel_type="wireguard", 
            wg_ip=wg_ip,
            wg_public_key=pub_key,
            wg_private_key=priv_key,
            conf_content=conf
        )
    except Exception as e:
        logger.error(f"WG Provisioning failed: {e}")
        return ProvisionResult(success=False, tunnel_type="wireguard", error=str(e))

async def _provision_zerotier(device: Device, db: Session) -> ProvisionResult:
    try:
        if not device.network_id or not device.zerotier_node_id:
            return ProvisionResult(success=False, tunnel_type="zerotier", error="Missing network_id or zerotier_node_id")
            
        await zerotier_controller.authorize_member(device.network_id, device.zerotier_node_id, authorized=True)
        
        return ProvisionResult(
            success=True,
            tunnel_type="zerotier",
            network_id=device.network_id,
            zerotier_node_id=device.zerotier_node_id
        )
    except Exception as e:
        logger.error(f"ZT Provisioning failed: {e}")
        return ProvisionResult(success=False, tunnel_type="zerotier", error=str(e))
