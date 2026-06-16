from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, UserRole, Device
# pyrefly: ignore [missing-import]
from models.user_device_access import UserDeviceAccess
# pyrefly: ignore [missing-import]
from schemas.user import UserCreate, UserOut, TrustToggle, Force2FAToggle, AssignDeviceRequest, RoleUpdate
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user, require_master_or_above
# pyrefly: ignore [missing-import]
from services.auth_service import hash_password, verify_totp
# pyrefly: ignore [missing-import]
from services.audit_service import log
# pyrefly: ignore [missing-import]
from models.audit_log import AuditLevel
import secrets
import string
import uuid

router = APIRouter(prefix="/api/users", tags=["users"])

SECOND_MASTER_LIMIT = 2


def _temp_password() -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(12))


@router.get("/", response_model=list[UserOut])
def list_users(current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        return db.query(User).all()
    return db.query(User).filter(User.tenant_id == current_user.tenant_id).all()


@router.post("/")
def create_user(req: UserCreate, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role != UserRole.master and req.role != "admin":
        raise HTTPException(status_code=403, detail="Only master can create non-admin users")

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    if req.role == "second_master":
        count = db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            User.role == UserRole.second_master
        ).count()
        limit = current_user.tenant.max_second_masters if hasattr(current_user.tenant, "max_second_masters") else 2
        if count >= limit:
            raise HTTPException(status_code=400, detail=f"Maximum {limit} second masters allowed")

    password = req.password or _temp_password()
    user = User(
        tenant_id=current_user.tenant_id,
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(password),
        role=UserRole(req.role),
        must_change_password=True,
        uuid=uuid.uuid4().hex
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log(db, "user_created", f"User {user.email} ({req.role}) created",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.success)

    return {"id": user.id, "email": user.email, "role": user.role, "temp_password": password}


@router.delete("/{user_id}")
# pyrefly: ignore [bad-function-definition]
def remove_user(user_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)], totp_code: str = None):
    if current_user.totp_enabled:
        if not totp_code:
            raise HTTPException(status_code=400, detail="2FA code required")
        if not verify_totp(current_user.totp_secret, totp_code):
            raise HTTPException(status_code=400, detail="Invalid 2FA code")
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.master:
        raise HTTPException(status_code=403, detail="Cannot remove master user")
    db.delete(user)
    db.commit()
    log(db, "user_removed", f"User {user.email} removed",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.warning)
    return {"message": "User removed"}


@router.patch("/{user_id}/trust")
def toggle_trust(user_id: int, req: TrustToggle, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_trusted = req.is_trusted
    db.commit()

    action = "trust_granted" if req.is_trusted else "trust_revoked"
    log(db, action, f"Trust {'granted to' if req.is_trusted else 'removed from'} {user.email}",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.info)

    if req.is_trusted:
        devices = db.query(Device).filter(Device.tenant_id == current_user.tenant_id, Device.is_approved == True).all()
        for device in devices:
            exists = db.query(UserDeviceAccess).filter_by(user_id=user.id, device_id=device.id).first()
            if not exists:
                db.add(UserDeviceAccess(user_id=user.id, device_id=device.id))
        db.commit()

    return {"message": "Updated"}


@router.patch("/{user_id}/force-2fa")
def toggle_force_2fa(user_id: int, req: Force2FAToggle, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.force_2fa = req.force_2fa
    db.commit()
    return {"message": "Updated"}


@router.patch("/{user_id}/role")
# pyrefly: ignore [bad-function-definition]
def change_role(user_id: int, req: RoleUpdate, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)], totp_code: str = None):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role == UserRole.second_master and req.new_role == UserRole.admin.value:
        if current_user.totp_enabled:
            if not totp_code:
                raise HTTPException(status_code=400, detail="2FA code required")
            if not verify_totp(current_user.totp_secret, totp_code):
                raise HTTPException(status_code=400, detail="Invalid 2FA code")
                
    if current_user.role != UserRole.system_owner:
        if user.role in (UserRole.system_owner, UserRole.master):
            raise HTTPException(status_code=403, detail="Cannot modify this user's role")
        if req.new_role in (UserRole.system_owner.value, UserRole.master.value):
            raise HTTPException(status_code=403, detail="Cannot promote to this role")

    try:
        user.role = UserRole(req.new_role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    db.commit()
    log(db, "role_changed", f"User '{user.full_name}' role changed to '{req.new_role}'",
        tenant_id=user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.warning)
    return {"message": "Role updated"}


@router.get("/{user_id}/assigned-devices")
def get_assigned_devices(user_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access = db.query(UserDeviceAccess).filter_by(user_id=user_id).all()
    return [a.device_id for a in access]

@router.post("/{user_id}/assign-device", responses={404: {"description": "Not found"}})
def assign_device(user_id: int, req: AssignDeviceRequest, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    device = db.query(Device).filter(Device.id == req.device_id, Device.tenant_id == current_user.tenant_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    exists = db.query(UserDeviceAccess).filter_by(user_id=user_id, device_id=req.device_id).first()
    if not exists:
        db.add(UserDeviceAccess(user_id=user_id, device_id=req.device_id))
        db.commit()
    log(db, "device_assigned", f"Device '{device.name}' assigned to {user.email}",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.info)
    return {"message": "Device assigned"}


@router.delete("/{user_id}/assign-device/{device_id}", responses={404: {"description": "Not found"}})
def revoke_device(user_id: int, device_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    access = db.query(UserDeviceAccess).filter_by(user_id=user_id, device_id=device_id).first()
    if access:
        db.delete(access)
        db.commit()
    log(db, "access_revoked", f"Device access revoked for user {user_id}",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.warning)
    return {"message": "Access revoked"}
