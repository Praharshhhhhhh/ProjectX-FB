from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
from models import Tenant, User, ActivationKey, UserRole, Router, RouterStatus
from models.tenant import TenantStatus
from schemas.tenant import TenantCreate, TenantOut, TenantUpdate
from routers.deps import require_system_owner
import secrets
import string
import uuid
from services.auth_service import hash_password
from services.email_service import send_master_activation_email

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _gen_key() -> str:
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return "PXKEY-" + "-".join(parts)


@router.get("/tenants")
def list_tenants(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    tenants = db.query(Tenant).all()
    result = []
    for t in tenants:
        master_user = next((u for u in t.users if u.role == UserRole.master), None)
        master_email = master_user.email if master_user else "—"
        result.append({
            "id": t.id,
            "company_name": t.company_name,
            "status": t.status,
            "created_at": t.created_at,
            "user_count": len(t.users),
            "master_email": master_email,
        })
    return result


@router.post("/tenants")
def create_tenant(req: TenantCreate, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    existing = db.query(Tenant).filter(Tenant.company_name == req.company_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant already exists")
    
    existing_user = db.query(User).filter(User.email == req.master_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Master email already in use")

    master_key = _gen_key().replace("PXKEY", "MSTKEY")
    
    tenant = Tenant(company_name=req.company_name, status=TenantStatus.pending, master_activation_key=master_key)
    db.add(tenant)
    db.commit()

    # Send activation email
    send_master_activation_email(req.master_email, master_key, req.company_name)

    return {"id": tenant.id, "company_name": tenant.company_name, "status": tenant.status}


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: int, req: TenantUpdate, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # TenantUpdate currently empty after trim; extend as needed
    db.commit()
    db.refresh(tenant)
    return {"message": "Tenant updated"}


@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()
    return {"message": "Deleted"}


@router.get("/stats")
def stats(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    return {
        "total_tenants": db.query(Tenant).count(),
        "active_tenants": db.query(Tenant).filter(Tenant.status == TenantStatus.active).count(),
        "pending_keys": db.query(ActivationKey).filter(ActivationKey.is_used == False).count(),
        "total_routers": db.query(Router).count(),
    }


@router.get("/users")
def list_users(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    users = db.query(User).filter(User.role != UserRole.system_owner).all()
    result = []
    for u in users:
        tenant = db.query(Tenant).filter(Tenant.id == u.tenant_id).first()
        result.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "force_otp": u.force_otp,
            "company_name": tenant.company_name if tenant else "—",
        })
    return result


@router.get("/pending-keys")
def list_pending_keys(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    """Return all unused activation keys with linked router info."""
    keys = db.query(ActivationKey).filter(ActivationKey.is_used == False).all()
    result = []
    for k in keys:
        router_obj = db.query(Router).filter(Router.id == k.router_id).first()
        result.append({
            "id": k.id,
            "key_code": k.key_code,
            "router_id": router_obj.router_id if router_obj else "—",
            "serial_number": router_obj.serial_number if router_obj else "—",
            "prepared_at": router_obj.prepared_at.isoformat() if router_obj and router_obj.prepared_at else None,
            "is_used": k.is_used,
        })
    return result


class ResendKeyRequest(BaseModel):
    recipient_email: EmailStr


@router.post("/pending-keys/{key_id}/resend")
def resend_activation_key(
    key_id: int,
    req: ResendKeyRequest,
    db: Annotated[Session, Depends(get_db)],
    _=Depends(require_system_owner),
):
    """Resend an unused activation key email to a new or corrected address."""
    key = db.query(ActivationKey).filter(ActivationKey.id == key_id, ActivationKey.is_used == False).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found or already used")
    router_obj = db.query(Router).filter(Router.id == key.router_id).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router linked to this key not found")
    try:
        from services.email_service import send_activation_key_email
        send_activation_key_email(
            to=req.recipient_email,
            router_id=router_obj.router_id,
            serial_number=router_obj.serial_number,
            key_code=key.key_code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")
    return {"message": "Activation key email resent"}


@router.get("/activation-keys")
def list_activation_keys(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    """Return all activation keys with linked router info."""
    keys = db.query(ActivationKey).all()
    result = []
    for k in keys:
        router_obj = db.query(Router).filter(Router.id == k.router_id).first()
        result.append({
            "id": k.id,
            "key_code": k.key_code,
            "router_id": router_obj.router_id if router_obj else "—",
            "serial_number": router_obj.serial_number if router_obj else "—",
            "prepared_at": router_obj.prepared_at.isoformat() if router_obj and router_obj.prepared_at else None,
            "is_used": k.is_used,
            "used_at": k.used_at.isoformat() if k.used_at else None,
        })
    return result


@router.delete("/activation-keys/{key_id}")
def delete_activation_key(key_id: int, db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    """Delete an activation key from the database."""
    key = db.query(ActivationKey).filter(ActivationKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    db.delete(key)
    db.commit()
    return {"message": "Key deleted"}

@router.patch("/force-otp-all")
def force_otp_all(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    """Force email OTP for ALL master and second_master users across every tenant."""
    affected = db.query(User).filter(
        User.role.in_([UserRole.master, UserRole.second_master])
    ).all()
    for u in affected:
        u.force_otp = True
    db.commit()
    return {"message": f"force_otp enabled for {len(affected)} users"}


# ── Router Preparation ─────────────────────────────────────────────────────────

class PrepareRouterRequest(BaseModel):
    router_id: str
    serial_number: str
    mac_address: str
    zerotier_node_id: str = ""
    recipient_email: EmailStr


@router.post("/routers/prepare")
def prepare_router(
    req: PrepareRouterRequest,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[User, Depends(require_system_owner)],
):
    # Check uniqueness
    existing = db.query(Router).filter(
        (Router.router_id == req.router_id)
        | (Router.serial_number == req.serial_number)
        | (Router.mac_address == req.mac_address)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Router with this ID, serial, or MAC already exists")

    new_router = Router(
        router_id=req.router_id,
        serial_number=req.serial_number,
        mac_address=req.mac_address,
        zerotier_node_id=req.zerotier_node_id or None,
        status=RouterStatus.prepared,
    )
    db.add(new_router)
    db.flush()

    key_code = secrets.token_urlsafe(16)
    key = ActivationKey(router_id=new_router.id, key_code=key_code)
    db.add(key)
    db.commit()
    db.refresh(new_router)

    # Send activation key email
    try:
        from services.email_service import send_activation_key_email
        send_activation_key_email(
            to=req.recipient_email,
            router_id=req.router_id,
            serial_number=req.serial_number,
            key_code=key_code,
        )
    except Exception as e:
        # Log but don't fail — key is created, can be resent
        import logging
        logging.getLogger(__name__).warning(f"Failed to send activation email: {e}")

    return {
        "id": new_router.id,
        "router_id": new_router.router_id,
        "serial_number": new_router.serial_number,
        "status": new_router.status,
        "prepared_at": new_router.prepared_at.isoformat() if new_router.prepared_at else None,
    }
