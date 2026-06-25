from typing import Annotated, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, Device, UserRole, AuditLevel, Tenant
# pyrefly: ignore [missing-import]
from models.device import DeviceStatus
# pyrefly: ignore [missing-import]
from models.user_device_access import UserDeviceAccess
# pyrefly: ignore [missing-import]
from schemas.device import DeviceOut, DeviceRegister, WgDeviceRegister
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user, require_master_or_above
# pyrefly: ignore [missing-import]
from services.audit_service import log
# pyrefly: ignore [missing-import]
from services.zerotier_controller import authorize_member, set_network_mode
# pyrefly: ignore [missing-import]
from services import wireguard_controller
# pyrefly: ignore [missing-import]
from services.auth_service import verify_totp
# pyrefly: ignore [missing-import]
from models.audit_log import AuditLevel
import asyncio
# pyrefly: ignore [missing-import]
from services.websocket_manager import manager
from services.tunnel_dispatcher import decide_tunnel_type, provision_device, deprovision_device
from services.nat_engine import write_iptables_nat_rule, remove_iptables_nat_rule, _applied_rules
import json
from fastapi.responses import PlainTextResponse, Response
import logging
from ipaddress import ip_network, IPv4Network

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])

def _nets_overlap(a: IPv4Network, b: IPv4Network) -> bool:
    return a.overlaps(b)

def check_subnet_overlap(new_subnet: str, device_id: int, db: Session) -> list[Device]:
    if not new_subnet:
        return []
    try:
        new_net = ip_network(new_subnet, strict=False)
    except ValueError:
        return []
    candidates = db.query(Device).filter(
        Device.id != device_id,
        Device.lan_subnet.isnot(None),
    ).all()
    result = []
    for d in candidates:
        try:
            other_net = ip_network(d.lan_subnet, strict=False)
            if _nets_overlap(new_net, other_net):
                result.append(d)
        except ValueError:
            continue
    return result

def assign_next_nat_pool(db: Session) -> str:
    used_pools = db.query(Device.nat_virtual_pool).filter(Device.nat_virtual_pool.isnot(None)).all()
    used_prefixes = {p[0] for p in used_pools if p[0]}
    
    for i in range(1, 255):
        pool = f"10.50.{i}"
        if pool not in used_prefixes:
            return pool
    return "10.50.254"

async def _handle_subnet_overlap(device: Device, db: Session):
    if not device.lan_subnet:
        return
    overlaps = check_subnet_overlap(device.lan_subnet, device.id, db)
    if overlaps:
        if device.tunnel_type == "wireguard":
            # Edge NAT handling: The Hub routes the virtual pool down the tunnel.
            # The edge client executes iptables NETMAP translation locally.
            if not device.nat_virtual_pool:
                virtual_pool = assign_next_nat_pool(db)
                device.nat_virtual_pool = virtual_pool
                db.commit()
                logger.info(f"Assigned Edge NAT virtual pool {virtual_pool} to device {device.id} to resolve collision.")
        else:
            overlap_ids = [o.id for o in overlaps]
            logger.warning(
                f"ZeroTier_Conflict_Alert: device {device.id} subnet {device.lan_subnet} "
                f"overlaps with {overlap_ids}. Manual review required."
            )
            # Write to audit log so it appears in the owner dashboard
            log(
                db,
                "subnet_conflict",
                (
                    f"LAN subnet conflict detected on '{device.name}' "
                    f"({device.lan_subnet}). Overlaps with device IDs: {overlap_ids}. "
                    f"Manual review required — ZeroTier conflicts cannot be auto-resolved."
                ),
                tenant_id=device.tenant_id,
                level=AuditLevel.warning,
            )
            # Push a real-time alert to all connected clients in this tenant
            await manager.broadcast_to_tenant(
                device.tenant_id,
                {
                    "event": "alert",
                    "message": (
                        f"⚠ LAN subnet conflict on '{device.name}' "
                        f"({device.lan_subnet}) — manual review required"
                    ),
                },
            )


def _user_can_see(user: User, device: Device, db: Session) -> bool:
    if user.role in (UserRole.master, UserRole.second_master):
        if device.tenant_id == user.tenant_id:
            return True
    if user.is_trusted or user.role == UserRole.trusted:
        if device.tenant_id == user.tenant_id and device.is_approved:
            return True
            
    access = db.query(UserDeviceAccess).filter_by(user_id=user.id, device_id=device.id).first()
    if access is not None:
        return True
        
    # Check if device is shared to user's tenant
    # pyrefly: ignore [missing-import]
    from models.device_share import DeviceShare
    share = db.query(DeviceShare).filter_by(device_id=device.id, target_tenant_id=user.tenant_id).first()
    if share is not None:
        return True
        
    return False


@router.get("/")
def list_devices(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    # pyrefly: ignore [missing-import]
    from models.device_share import DeviceShare
    shared_to_tenant = db.query(DeviceShare).filter_by(target_tenant_id=current_user.tenant_id).all()
    shared_device_ids = [s.device_id for s in shared_to_tenant]

    if current_user.role in (UserRole.master, UserRole.second_master):
        devices = db.query(Device).filter(Device.tenant_id == current_user.tenant_id).all()
        shared_devices = db.query(Device).filter(Device.id.in_(shared_device_ids)).all()
        devices.extend(shared_devices)
    elif current_user.is_trusted or current_user.role == UserRole.trusted:
        devices = db.query(Device).filter(Device.tenant_id == current_user.tenant_id, Device.is_approved == True).all()
        shared_devices = db.query(Device).filter(Device.id.in_(shared_device_ids), Device.is_approved == True).all()
        devices.extend(shared_devices)
    else:
        access_rows = db.query(UserDeviceAccess).filter_by(user_id=current_user.id).all()
        device_ids = [a.device_id for a in access_rows]
        device_ids.extend(shared_device_ids)
        devices = db.query(Device).filter(Device.id.in_(device_ids), Device.is_approved == True).all()
        
    return [_device_dict(d, hide_network=d.tenant_id != current_user.tenant_id) for d in devices]


@router.get("/pending")
def pending_devices(current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    devices = db.query(Device).filter(
        Device.tenant_id == current_user.tenant_id,
        Device.is_approved == False
    ).all()
    return [_device_dict(d) for d in devices]


@router.post("/register")
async def register_device(req: DeviceRegister, db: Annotated[Session, Depends(get_db)]):
    # pyrefly: ignore [missing-import]
    from models import Tenant
    tenant = db.query(Tenant).filter(Tenant.zerotier_network_id == req.network_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenant owns this network ID")
        
    owner_user = db.query(User).filter(User.id == tenant.network_owner_id).first() if tenant.network_owner_id else None
    if not owner_user or owner_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Network ID is not owned by an active master or second master user")
    existing = db.query(Device).filter(Device.zerotier_node_id == req.zerotier_node_id).first()
    if existing:
        if existing.tenant_id != tenant.id:
            db.delete(existing)
            db.flush()
        else:
            return {"message": "Already registered", "device_id": existing.id}
    device = Device(
        tenant_id=tenant.id,
        owner_id=owner_user.id,
        zerotier_node_id=req.zerotier_node_id,
        network_id=req.network_id,
        zerotier_ip=req.zerotier_ip,
        lan_ip=req.lan_ip,
        lan_subnet=req.lan_subnet,
        device_capability=json.dumps(req.device_capability) if hasattr(req, "device_capability") and req.device_capability else None,
        status=DeviceStatus.pending,
        is_approved=False,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    log(db, "device_registered", f"New device {req.zerotier_node_id} registered (pending approval)",
        tenant_id=tenant.id, level=AuditLevel.info)
    
    await manager.broadcast_to_tenant(tenant.id, {"event": "device_updated", "device": _device_dict(device)})
    return {"message": "Registered, awaiting approval", "device_id": device.id}


@router.post("/wg-register")
async def register_wg_device(req: WgDeviceRegister, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    from models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    from config import get_settings
    settings = get_settings()
    server_endpoint = getattr(settings, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")
    server_endpoint_secondary = getattr(settings, "WG_SERVER_ENDPOINT_SECONDARY", "")
    server_pubkey = getattr(settings, "WG_SERVER_PUBLIC_KEY", "")

    if req.wg_public_key:
        existing = db.query(Device).filter(Device.wg_public_key == req.wg_public_key).first()
        if existing:
            if existing.tenant_id != current_user.tenant_id:
                db.delete(existing)
                db.flush()
                existing = None
            else:
                config_str = wireguard_controller.generate_client_config("", existing.wg_ip, server_pubkey, server_endpoint, client_pubkey=existing.wg_public_key)
                wireguard_controller.sync_peer_to_vps(existing.wg_public_key, existing.wg_ip)
                return {
                    "assigned_ip": existing.wg_ip,
                    "server_pubkey": server_pubkey,
                    "server_endpoint": server_endpoint,
                    "server_endpoint_secondary": server_endpoint_secondary,
                    "config": config_str,
                    "private_key": ""
                }

    priv_key = ""
    pub_key = req.wg_public_key
    if not pub_key:
        priv_key, pub_key = await wireguard_controller.generate_keypair()

    if not pub_key:
        raise HTTPException(status_code=500, detail="WireGuard server could not generate keypair. Is WireGuard installed on the server?")

    assigned_ip = wireguard_controller.assign_ip_from_pool(db, current_user.tenant_id)
    
    config_str = wireguard_controller.generate_client_config(priv_key, assigned_ip, server_pubkey, server_endpoint, client_pubkey=pub_key)
    wireguard_controller.sync_peer_to_vps(pub_key, assigned_ip)
    
    device = Device(
        tenant_id=current_user.tenant_id,
        owner_id=current_user.id,
        wg_public_key=pub_key,
        wg_ip=assigned_ip,
        lan_ip=req.lan_ip,
        name=req.hostname,
        tunnel_type="wireguard",
        status=DeviceStatus.pending,
        is_approved=False,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    log(db, "device_registered", f"New WireGuard device {pub_key[:8]}... registered",
        tenant_id=current_user.tenant_id, level=AuditLevel.info)
    
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    
    return {
        "assigned_ip": assigned_ip,
        "server_pubkey": server_pubkey,
        "server_endpoint": server_endpoint,
        "server_endpoint_secondary": server_endpoint_secondary,
        "config": config_str,
        "private_key": priv_key,
        "device_id": device.id if 'device' in locals() else existing.id
    }


@router.post("/heartbeat")
async def device_heartbeat(req: DeviceRegister, db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(
        (Device.zerotier_node_id == req.zerotier_node_id) | 
        (Device.wg_public_key == req.zerotier_node_id)
    ).first()
    if not device:
        return await register_device(req, db)

    alert_msg = None
    if req.lan_ip and device.lan_ip and req.lan_ip != device.lan_ip:
        alert_msg = f"Alert: Device '{device.name}' LAN IP changed from {device.lan_ip} to {req.lan_ip}"
    if req.lan_subnet and device.lan_subnet and req.lan_subnet != device.lan_subnet:
        alert_msg = f"Alert: Device '{device.name}' LAN Subnet changed from {device.lan_subnet} to {req.lan_subnet}"

    if alert_msg:
        from services.audit_service import log
        from models.audit_log import AuditLevel
        log(db, "lan_changed", alert_msg, tenant_id=device.tenant_id, level=AuditLevel.warning)
        await manager.broadcast_to_tenant(device.tenant_id, {"event": "alert", "message": alert_msg})

    device.network_id = req.network_id
    if req.zerotier_ip:
        device.zerotier_ip = req.zerotier_ip
    if req.lan_ip:
        device.lan_ip = req.lan_ip
    if req.lan_subnet:
        device.lan_subnet = req.lan_subnet
    if req.hostname:
        device.name = req.hostname
    if hasattr(req, "device_capability") and req.device_capability:
        device.device_capability = json.dumps(req.device_capability)
        
    if device.is_approved:
        device.status = DeviceStatus.active
        
    # Force update timestamp even if no columns changed
    from datetime import datetime
    # pyrefly: ignore [deprecated]
    device.updated_at = datetime.utcnow()
    
    db.commit()
    await _handle_subnet_overlap(device, db)
    
    db.refresh(device)
    await manager.broadcast_to_tenant(device.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    return {"message": "Heartbeat received", "device_id": device.id}


LIVE_WG_STATUSES = {}

class WgStatusesReq(BaseModel):
    statuses: dict[str, int]

@router.post("/wg-tunnel-statuses")
async def update_wg_tunnel_statuses(
    req: WgStatusesReq,
    current_user: Annotated[User, Depends(get_current_user)]
):
    for pubkey, handshake in req.statuses.items():
        LIVE_WG_STATUSES[pubkey] = handshake
    return {"message": "Statuses updated"}

@router.get("/wg-tunnel-peers")
async def get_wg_tunnel_peers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    # pyrefly: ignore [missing-import]
    from models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant or not tenant.wg_server_public_key:
        raise HTTPException(400, "No WireGuard server claimed for this tenant")
    
    wg_devices = db.query(Device).filter(
        Device.tenant_id == current_user.tenant_id,
        Device.tunnel_type == "wireguard",
        Device.is_approved == True
    ).all()
    
    # Filter devices based on what the user can see
    wg_devices = [d for d in wg_devices if _user_can_see(current_user, d, db)]
    
    import time
    statuses = {}
    for pubkey, handshake in LIVE_WG_STATUSES.items():
        if handshake > 0 and (time.time() - handshake) < 180:
            statuses[pubkey] = "active"
        else:
            statuses[pubkey] = "offline"
    
    peers = []
    for device in wg_devices:
        live_status = statuses.get(device.wg_public_key, "offline")
        peers.append({
            "device_id": device.id,
            "name": device.name,
            "wg_public_key": device.wg_public_key,
            "wg_ip": device.wg_ip,
            "lan_ip": device.lan_ip,
            "status": live_status,
            "db_status": device.status,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "nat_virtual_pool": device.nat_virtual_pool,
            "lan_subnet": device.lan_subnet,
        })
    
    return {
        "server_endpoint": tenant.wg_server_endpoint,
        "server_endpoint_secondary": tenant.wg_server_endpoint_secondary,
        "server_public_key": tenant.wg_server_public_key,
        "server_interface": tenant.wg_server_interface,
        "peers": peers,
        "total": len(peers),
        "active": sum(1 for p in peers if p["status"] == "active")
    }


@router.post("/{device_id}/approve")
async def approve_device(device_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == current_user.tenant_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.is_approved:
        raise HTTPException(status_code=400, detail="Already approved")

    capability = json.loads(device.device_capability or "{}")
    new_tunnel_type = await decide_tunnel_type(capability, device.forced_tunnel_type)
    if device.tunnel_type == "wireguard" and not device.forced_tunnel_type:
        new_tunnel_type = "wireguard"
    device.tunnel_type = new_tunnel_type
    db.commit()

    result = await provision_device(device, db)
    if not result.success:
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {result.error}")

    if device.tunnel_type == "wireguard":
        device.wg_ip = result.wg_ip
        device.wg_public_key = result.wg_public_key
        device.wg_private_key = result.wg_private_key
    elif device.tunnel_type == "zerotier":
        device.network_id = result.network_id
        device.zerotier_node_id = result.zerotier_node_id

    device.is_approved = True
    device.status = DeviceStatus.active

    trusted_users = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        (User.is_trusted == True) | (User.role == UserRole.trusted)
    ).all()
    second_masters = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        User.role == UserRole.second_master,
    ).all()
    for u in (trusted_users + second_masters):
        exists = db.query(UserDeviceAccess).filter_by(user_id=u.id, device_id=device.id).first()
        if not exists:
            db.add(UserDeviceAccess(user_id=u.id, device_id=device.id))

    db.commit()
    log(db, "device_approved", f"Device '{device.name}' approved by {current_user.full_name}",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.success)

    db.refresh(device)
    await _handle_subnet_overlap(device, db)
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    
    # Broadcast mesh update so all clients re-fetch their config to include the new peer
    if device.tunnel_type == "wireguard":
        await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "mesh_updated"})
        
    return {"message": "Device approved and activated"}


@router.delete("/{device_id}")
# pyrefly: ignore [bad-function-definition]
async def remove_device(device_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)], totp_code: str = None):
    if current_user.totp_enabled:
        if not totp_code:
            raise HTTPException(status_code=400, detail="2FA code required")
        if not verify_totp(current_user.totp_secret, totp_code):
            raise HTTPException(status_code=400, detail="Invalid 2FA code")
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == current_user.tenant_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    await deprovision_device(device)
    await remove_iptables_nat_rule(device.id)
    
    log(db, "device_removed", f"Device '{device.name}' removed",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.warning)
    
    dev_id = device.id
    if device.tunnel_type == "wireguard" and device.wg_public_key:
        wireguard_controller.sync_peer_to_vps(device.wg_public_key, device.wg_ip, remove=True)
    db.delete(device)
    db.commit()
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_removed", "device_id": dev_id})
    return {"message": "Device removed"}


@router.patch("/{device_id}/rename")
async def rename_device(device_id: int, name: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == current_user.tenant_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    device.name = name
    db.commit()
    db.refresh(device)
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    return {"message": "Renamed"}

class ReprovisionReq(BaseModel):
    forced_tunnel_type: str
    re_provision_requested: bool

@router.patch("/{device_id}")
async def reprovision_device(
    device_id: int,
    req: ReprovisionReq,
    current_user: Annotated[User, Depends(require_master_or_above)],
    db: Annotated[Session, Depends(get_db)]
):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == current_user.tenant_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if req.re_provision_requested:
        device.forced_tunnel_type = req.forced_tunnel_type
        device.re_provision_requested = True
        
        # Deprovision old tunnel
        await deprovision_device(device)
        await remove_iptables_nat_rule(device.id)
        
        # Provision new tunnel
        capability = json.loads(device.device_capability or "{}")
        tunnel_type = await decide_tunnel_type(capability, device.forced_tunnel_type)
        device.tunnel_type = tunnel_type
        db.commit()
        
        result = await provision_device(device, db)
        if not result.success:
            raise HTTPException(status_code=500, detail=f"Provisioning failed: {result.error}")
            
        if device.tunnel_type == "wireguard":
            device.wg_ip = result.wg_ip
            device.wg_public_key = result.wg_public_key
            device.wg_private_key = result.wg_private_key
            device.network_id = None
            device.zerotier_node_id = None
        elif device.tunnel_type == "zerotier":
            device.network_id = result.network_id
            device.zerotier_node_id = result.zerotier_node_id
            device.wg_public_key = None
            device.wg_private_key = None
            device.wg_ip = None
            
        device.re_provision_requested = False
        db.commit()
        
        await _handle_subnet_overlap(device, db)
        await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
        
    return {"message": "Reprovisioned"}

@router.get("/{device_id}/conf", response_class=PlainTextResponse)
async def get_device_conf(device_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found")
    if device.tunnel_type != "wireguard":
        raise HTTPException(403, "Not a WireGuard device")
    
    owner = db.query(User).filter(User.id == device.owner_id).first()
    is_master = owner and owner.role in (UserRole.master, UserRole.second_master)
    
    if is_master:
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
            private_key=device.wg_private_key,
            assigned_ip=device.wg_ip,
            listen_port=51820,
            peers=peers,
            virtual_pool=device.nat_virtual_pool,
            real_subnet=device.lan_subnet
        )
    else:
        master_device = db.query(Device).join(User, Device.owner_id == User.id).filter(
            Device.tenant_id == device.tenant_id,
            User.role.in_([UserRole.master, UserRole.second_master]),
            Device.tunnel_type == "wireguard",
            Device.is_approved == True
        ).first()
        
        server_pubkey = master_device.wg_public_key if master_device else ""
        server_endpoint = f"{master_device.lan_ip}:51820" if master_device and master_device.lan_ip else "127.0.0.1:51820"
        
        conf = wireguard_controller.generate_client_config(
            private_key=device.wg_private_key,
            assigned_ip=device.wg_ip,
            server_pubkey=server_pubkey,
            server_endpoint=server_endpoint,
            virtual_pool=device.nat_virtual_pool,
            real_subnet=device.lan_subnet,
            client_pubkey=device.wg_public_key
        )
        
    return Response(content=conf, media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{device.name}.conf"'})


@router.get("/{device_id}/connect")
# pyrefly: ignore [bad-function-definition]
def connect_device(device_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], ip: str = None):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    target_ip = ip if ip else device.lan_ip
    return {"url": f"http://{target_ip}"}


class SyncToggleReq(BaseModel):
    connect: bool
    network_id: Optional[str] = None

@router.post("/{device_id}/sync-toggle")
async def sync_device_toggle(
    device_id: int, 
    req: SyncToggleReq, 
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Annotated[Session, Depends(get_db)]
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
        
    device.status = DeviceStatus.connecting if req.connect else DeviceStatus.offline
    db.commit()
    db.refresh(device)
    
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
        
    await manager.broadcast_to_tenant(current_user.tenant_id, {
        "event": "sync_toggle",
        "device_id": device_id,
        "connect": req.connect,
        "network_id": req.network_id
    })
    return {"message": "Sync toggle broadcasted"}

class SyncStatusReq(BaseModel):
    status: str

@router.post("/{device_id}/status")
async def sync_device_status(
    device_id: int,
    req: SyncStatusReq,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found")
        
    try:
        device.status = DeviceStatus(req.status)
    except ValueError:
        pass
        
    db.commit()
    db.refresh(device)
    
    await manager.broadcast_to_tenant(current_user.tenant_id, {
        "event": "device_updated",
        "device": _device_dict(device)
    })
    return {"message": "Status updated"}
class NetworkModeReq(BaseModel):
    is_layer2: bool

@router.post("/{device_id}/network-mode")
async def change_network_mode(
    device_id: int,
    req: NetworkModeReq,
    current_user: Annotated[User, Depends(require_master_or_above)],
    db: Annotated[Session, Depends(get_db)]
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not device.network_id:
        raise HTTPException(status_code=400, detail="Device does not have a network ID")
        
    ok = await set_network_mode(device.network_id, req.is_layer2)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to change network mode in ZeroTier")
        
    from models.audit_log import AuditLevel
    mode_str = "Layer 2 (Bridged)" if req.is_layer2 else "Layer 3 (Routed)"
    log(db, "network_mode_changed", f"Network mode changed to {mode_str} for network {device.network_id}", tenant_id=current_user.tenant_id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.warning)
    
    return {"message": "Network mode updated", "is_layer2": req.is_layer2}


def _device_dict(d: Device, hide_network: bool = False) -> dict:
    virtual_ip = d.wg_ip if d.tunnel_type == "wireguard" else d.zerotier_ip
    conf_url = f"/api/devices/{d.id}/conf" if d.tunnel_type == "wireguard" else None
    
    connection_info = {
        "tunnel_type": d.tunnel_type or "unknown",
        "virtual_ip": virtual_ip,
        "status": d.status.value if hasattr(d.status, "value") else str(d.status),
        "conf_download_url": conf_url,
        "network_id": d.network_id if d.tunnel_type == "zerotier" else None,
        "node_id": d.zerotier_node_id if d.tunnel_type == "zerotier" else None,
    }
    
    from sqlalchemy.orm import object_session
    db = object_session(d)
    has_conflict = False
    if db and d.lan_subnet:
        has_conflict = len(check_subnet_overlap(d.lan_subnet, d.id, db)) > 0
    
    return {
        "id": d.id, "name": d.name,
        "zerotier_node_id": d.zerotier_node_id,
        "wg_public_key": d.wg_public_key,
        "zerotier_ip": d.zerotier_ip,
        "wg_ip": d.wg_ip,
        "lan_ip": d.lan_ip, "lan_subnet": d.lan_subnet,
        "network_id": None if hide_network else d.network_id, "status": d.status,
        "is_approved": d.is_approved, "tenant_id": d.tenant_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "lan_devices": [{"id": l.id, "name": l.name, "ip_address": l.ip_address, "mac_address": l.mac_address} for l in d.lan_devices],
        "is_shared": hide_network,
        "connection_info": connection_info,
        "has_conflict": has_conflict,
        "nat_virtual_pool": d.nat_virtual_pool
    }
