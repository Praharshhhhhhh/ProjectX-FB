from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, Device
# pyrefly: ignore [missing-import]
from models.lan_device import LanDevice
# pyrefly: ignore [missing-import]
from schemas.device import LanDeviceRename, LanDeviceBulkUpdate
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user
# pyrefly: ignore [missing-import]
from routers.devices import _user_can_see
# pyrefly: ignore [missing-import]
from services.audit_service import log
from models.audit_log import AuditLevel

router = APIRouter(prefix="/api/lan-devices", tags=["lan-devices"])


@router.get("/{device_id}")
def get_lan_devices(device_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    return [{"id": l.id, "name": l.name, "ip_address": l.ip_address, "mac_address": l.mac_address}
            for l in device.lan_devices]


@router.patch("/{lan_device_id}/rename")
async def rename_lan_device(lan_device_id: int, req: LanDeviceRename, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    lan = db.query(LanDevice).filter(LanDevice.id == lan_device_id).first()
    if not lan:
        raise HTTPException(status_code=404, detail="LAN device not found")
    device = db.query(Device).filter(Device.id == lan.device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=403, detail="Not authorized")
    lan.name = req.name
    db.commit()
    
    # pyrefly: ignore [missing-import]
    from services.websocket_manager import manager
    if device.tenant_id:
        await manager.broadcast_to_tenant(device.tenant_id, {
            "event": "lan_device_renamed",
            "lan_device_id": lan.id,
            "device_id": device.id,
            "new_name": lan.name
        })
        
    return {"message": "Renamed", "name": req.name}


@router.post("/{device_id}/sync")
def sync_lan_devices(device_id: int, req: LanDeviceBulkUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not _user_can_see(current_user, device, db):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    
    existing = {l.ip_address: l for l in device.lan_devices}
    new_ips = {d.get("ip_address") for d in req.devices if d.get("ip_address")}
    
    # Delete old devices not in the new scan
    for ip, lan_dev in list(existing.items()):
        if ip not in new_ips:
            db.delete(lan_dev)
            
    # Add or update matching entries
    for d in req.devices:
        ip = d.get("ip_address")
        if not ip:
            continue
        if ip in existing:
            existing[ip].name = d.get("name", existing[ip].name)
            existing[ip].mac_address = d.get("mac_address", existing[ip].mac_address)
        else:
            db.add(LanDevice(device_id=device_id, name=d.get("name", "Unknown Device"),
                             ip_address=ip, mac_address=d.get("mac_address")))
    db.commit()
    log(db, "lan_scan_completed", f"LAN scan completed for device {device.name}. Found {len(req.devices)} devices.", tenant_id=current_user.tenant_id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.info)
    return {"message": "Synced"}
