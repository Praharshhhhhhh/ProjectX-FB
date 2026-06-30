from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas.user import UserCreate, UserOut, TrustToggle, Force2FAToggle, RoleUpdate, UserUpdate
from routers.deps import get_current_user, require_master_or_above
from services.auth_service import hash_password
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
        uuid=uuid.uuid4().hex,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "role": user.role, "temp_password": password}


@router.delete("/{user_id}")
def remove_user(user_id: int, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
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
    return {"message": "User removed"}


@router.patch("/{user_id}")
def update_user(user_id: int, req: UserUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    is_master_or_above = current_user.role in (UserRole.system_owner, UserRole.master, UserRole.second_master)

    if not is_master_or_above:
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        if req.email is not None and req.email != current_user.email:
            raise HTTPException(status_code=403, detail="Cannot change email address")
        if req.is_active is not None and req.is_active != current_user.is_active:
            raise HTTPException(status_code=403, detail="Cannot change active status")

    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.full_name is not None:
        user.full_name = req.full_name
    if req.email is not None and req.email != user.email:
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = req.email
    if req.is_active is not None:
        user.is_active = req.is_active

    db.commit()
    return {"message": "Profile updated"}


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
    return {"message": "Updated"}


@router.patch("/{user_id}/force-2fa")
def toggle_force_otp(user_id: int, req: Force2FAToggle, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.force_otp = req.force_2fa
    db.commit()
    return {"message": "Updated"}


@router.patch("/{user_id}/role")
def change_role(user_id: int, req: RoleUpdate, current_user: Annotated[User, Depends(require_master_or_above)], db: Annotated[Session, Depends(get_db)]):
    if current_user.role == UserRole.system_owner:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
    return {"message": "Role updated"}
