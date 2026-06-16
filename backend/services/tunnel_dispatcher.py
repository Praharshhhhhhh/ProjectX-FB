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
            tenant_interface = device.tenant.wg_server_interface if device.tenant else "wg0"
            await wireguard_controller.remove_peer(device.wg_public_key, interface=tenant_interface)
        elif device.tunnel_type == "zerotier" and device.network_id and device.zerotier_node_id:
            await zerotier_controller.deauthorize_member(device.network_id, device.zerotier_node_id)
        return True
    except Exception as e:
        logger.error(f"Failed to deprovision device {device.id}: {e}")
        return False

async def get_tunnel_status(device: Device) -> str:
    if device.tunnel_type == "wireguard" and device.wg_public_key:
        tenant_interface = device.tenant.wg_server_interface if device.tenant else "wg0"
        return await wireguard_controller.check_peer_status(device.wg_public_key, interface=tenant_interface)
    elif device.tunnel_type == "zerotier" and device.network_id and device.zerotier_node_id:
        return await zerotier_controller.check_member_status(device.network_id, device.zerotier_node_id)
    return "offline"

async def _provision_wireguard(device: Device, db: Session) -> ProvisionResult:
    try:
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
        
        tenant = device.tenant
        tenant_interface = tenant.wg_server_interface if tenant else "wg0"
        await wireguard_controller.add_peer(pub_key, wg_ip, interface=tenant_interface)
        
        from config import get_settings
        settings = get_settings()
        
        server_pubkey = tenant.wg_server_public_key if tenant and tenant.wg_server_public_key else await wireguard_controller.get_server_public_key(interface=tenant_interface)
        server_endpoint = tenant.wg_server_endpoint if tenant and tenant.wg_server_endpoint else getattr(settings, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")
        
        conf = wireguard_controller.generate_client_config(
            private_key=priv_key,
            assigned_ip=wg_ip,
            server_pubkey=server_pubkey,
            server_endpoint=server_endpoint
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
            
        await zerotier_controller.authorize_member(device.network_id, device.zerotier_node_id, device.name)
        
        return ProvisionResult(
            success=True,
            tunnel_type="zerotier",
            network_id=device.network_id,
            zerotier_node_id=device.zerotier_node_id
        )
    except Exception as e:
        logger.error(f"ZT Provisioning failed: {e}")
        return ProvisionResult(success=False, tunnel_type="zerotier", error=str(e))
