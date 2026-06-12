from typing import Annotated
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, Device, UserRole
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

router = APIRouter(prefix="/api/devices", tags=["devices"])


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
        return {"message": "Already registered", "device_id": existing.id}
    device = Device(
        tenant_id=tenant.id,
        owner_id=owner_user.id,
        zerotier_node_id=req.zerotier_node_id,
        network_id=req.network_id,
        zerotier_ip=req.zerotier_ip,
        lan_ip=req.lan_ip,
        lan_subnet=req.lan_subnet,
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
    existing = db.query(Device).filter(Device.wg_public_key == req.wg_public_key).first()
    if existing:
        server_pubkey = await wireguard_controller.get_server_public_key()
        server_endpoint = getattr(wireguard_controller, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")
        config_str = wireguard_controller.generate_client_config("", existing.wg_ip, server_pubkey, server_endpoint)
        return {
            "assigned_ip": existing.wg_ip,
            "server_pubkey": server_pubkey,
            "server_endpoint": server_endpoint,
            "config": config_str
        }

    assigned_ip = wireguard_controller.assign_ip_from_pool(db, current_user.tenant_id)
    server_pubkey = await wireguard_controller.get_server_public_key()
    server_endpoint = getattr(wireguard_controller, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")
    config_str = wireguard_controller.generate_client_config("", assigned_ip, server_pubkey, server_endpoint)
    
    device = Device(
        tenant_id=current_user.tenant_id,
        owner_id=current_user.id,
        wg_public_key=req.wg_public_key,
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
    log(db, "device_registered", f"New WireGuard device {req.wg_public_key[:8]}... registered",
        tenant_id=current_user.tenant_id, level=AuditLevel.info)
    
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    
    return {
        "assigned_ip": assigned_ip,
        "server_pubkey": server_pubkey,
        "server_endpoint": server_endpoint,
        "config": config_str
    }


@router.post("/heartbeat")
async def device_heartbeat(req: DeviceRegister, db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.zerotier_node_id == req.zerotier_node_id).first()
    if not device:
        return await register_device(req, db)

    device.network_id = req.network_id
    if req.zerotier_ip:
        device.zerotier_ip = req.zerotier_ip
    if req.lan_ip:
        device.lan_ip = req.lan_ip
    if req.lan_subnet:
        device.lan_subnet = req.lan_subnet
    if req.hostname:
        device.name = req.hostname
    if device.is_approved:
        device.status = DeviceStatus.active
        
    # Force update timestamp even if no columns changed
    from datetime import datetime
    # pyrefly: ignore [deprecated]
    device.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(device)
    await manager.broadcast_to_tenant(device.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
    return {"message": "Heartbeat received", "device_id": device.id}


@router.get("/wg-tunnel-peers")
async def get_wg_tunnel_peers(
    current_user: Annotated[User, Depends(require_master_or_above)],
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
    
    statuses = await wireguard_controller.get_all_peer_statuses(interface=tenant.wg_server_interface)
    
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
        })
    
    return {
        "server_endpoint": tenant.wg_server_endpoint,
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

    if device.tunnel_type == "wireguard":
        await wireguard_controller.add_peer(device.wg_public_key, device.wg_ip)
    elif device.network_id and device.zerotier_node_id:
        await authorize_member(device.network_id, device.zerotier_node_id, True)

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
    await manager.broadcast_to_tenant(current_user.tenant_id, {"event": "device_updated", "device": _device_dict(device)})
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
    if device.tunnel_type == "wireguard":
        await wireguard_controller.remove_peer(device.wg_public_key)
    elif device.network_id and device.zerotier_node_id:
        await authorize_member(device.network_id, device.zerotier_node_id, False)
    log(db, "device_removed", f"Device '{device.name}' removed",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.warning)
    
    dev_id = device.id
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
    network_id: str

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
    return {
        "id": d.id, "name": d.name,
        "zerotier_node_id": d.zerotier_node_id,
        "zerotier_ip": d.zerotier_ip,
        "wg_ip": d.wg_ip,
        "lan_ip": d.lan_ip, "lan_subnet": d.lan_subnet,
        "network_id": None if hide_network else d.network_id, "status": d.status,
        "is_approved": d.is_approved, "tenant_id": d.tenant_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "lan_devices": [{"id": l.id, "name": l.name, "ip_address": l.ip_address, "mac_address": l.mac_address} for l in d.lan_devices],
        "is_shared": hide_network
    }
