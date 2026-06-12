from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, Device, DeviceShare, Tenant, UserRole
# pyrefly: ignore [missing-import]
from schemas.device_share import DeviceShareCreate, DeviceShareResponse
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user
# pyrefly: ignore [missing-import]
from services.websocket_manager import manager
# pyrefly: ignore [missing-import]
from services.audit_service import log
from models.audit_log import AuditLevel

router = APIRouter(prefix="/api/device-shares", tags=["device-shares"])

@router.post("", response_model=DeviceShareResponse)
async def create_share(req: DeviceShareCreate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == req.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Only the network_owner_id can share the device, or tenant master
    if device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Device not in your tenant")
    
    is_owner = device.owner_id is not None and device.owner_id == current_user.id
    if not is_owner and current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Not authorized to share this device")

    target_tenant = db.query(Tenant).filter(Tenant.id == req.target_tenant_id).first()
    if not target_tenant:
        raise HTTPException(status_code=404, detail="Target tenant not found")
        
    if target_tenant.id == device.tenant_id:
        raise HTTPException(status_code=400, detail="Cannot share device with its own tenant")

    existing = db.query(DeviceShare).filter_by(device_id=device.id, target_tenant_id=target_tenant.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device already shared with this tenant")

    share = DeviceShare(
        device_id=device.id,
        source_tenant_id=current_user.tenant_id,
        target_tenant_id=target_tenant.id
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    
    # Audit log
    log(db, "device_shared", f"Shared device {device.name} with tenant {target_tenant.id}", tenant_id=current_user.tenant_id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.info)
    log(db, "device_shared", f"Device {device.name} shared to this tenant by {current_user.full_name}", tenant_id=target_tenant.id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.info)
    
    return share

@router.get("/device/{device_id}", response_model=List[DeviceShareResponse])
def get_device_shares(device_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Device not found")
        
    is_owner = device.owner_id is not None and device.owner_id == current_user.id
    if not is_owner and current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    shares = db.query(DeviceShare).filter_by(device_id=device.id).all()
    return shares

@router.delete("/{share_id}")
async def revoke_share(share_id: int, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    share = db.query(DeviceShare).filter(DeviceShare.id == share_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
        
    if share.source_tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    device = db.query(Device).filter(Device.id == share.device_id).first()
    is_owner = device.owner_id is not None and device.owner_id == current_user.id
    if not is_owner and current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    target_tenant_id = share.target_tenant_id
    db.delete(share)
    db.commit()
    
    log(db, "device_share_revoked", f"Revoked share of device {device.name} from tenant {target_tenant_id}", tenant_id=current_user.tenant_id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.warning)
    log(db, "device_share_revoked", f"Share of device {device.name} revoked by {current_user.full_name}", tenant_id=target_tenant_id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.warning)
    
    return {"message": "Share revoked"}
