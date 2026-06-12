from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import Tenant, User, ActivationKey, AuditLog, UserRole
# pyrefly: ignore [missing-import]
from models.tenant import TenantStatus
# pyrefly: ignore [missing-import]
from schemas.tenant import TenantCreate, TenantOut, TenantUpdate
# pyrefly: ignore [missing-import]
from routers.deps import require_system_owner
# pyrefly: ignore [missing-import]
from services.audit_service import log
# pyrefly: ignore [missing-import]
from models.audit_log import AuditLevel
import secrets
import string

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
            "city": t.city,
            "zerotier_network_id": t.zerotier_network_id,
            "status": t.status,
            "created_at": t.created_at,
            "device_count": len(t.devices),
            "user_count": len(t.users),
            "master_email": master_email,
            "network_owner_id": t.network_owner_id,
            "max_second_masters": getattr(t, "max_second_masters", 2),
        })
    return result


@router.post("/tenants")
def create_tenant(req: TenantCreate, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    existing = db.query(Tenant).filter(Tenant.company_name == req.company_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant already exists")
    tenant = Tenant(company_name=req.company_name, city=req.city, status=TenantStatus.pending)
    db.add(tenant)
    db.commit()
    return {"id": tenant.id, "company_name": tenant.company_name, "status": tenant.status}

@router.post("/force-2fa-all")
async def force_2fa_all(db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    users = db.query(User).filter(User.role.in_([UserRole.master, UserRole.second_master])).all()
    count = 0
    for u in users:
        if not u.force_2fa:
            u.force_2fa = True
            count += 1
    db.commit()
    log(db, "global_force_2fa", f"Forced 2FA globally for {count} users",
        user_id=owner.id, user_name=owner.full_name, level=AuditLevel.warning)
    
    # Broadcast to all tenants
    tenants = db.query(Tenant).all()
    # pyrefly: ignore [missing-import]
    from services.websocket_manager import manager
    for t in tenants:
        await manager.broadcast_to_tenant(t.id, {"event": "user_updated"})
    return {"message": f"Enabled 2FA for {count} users"}


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: int, req: TenantUpdate, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if req.max_second_masters is not None:
        tenant.max_second_masters = req.max_second_masters
    db.commit()
    db.refresh(tenant)
    log(db, "tenant_updated", f"Tenant '{tenant.company_name}' updated",
        user_id=owner.id, user_name=owner.full_name, level=AuditLevel.info)
    return {"message": "Tenant updated"}


@router.delete("/tenants/{tenant_id}")
# pyrefly: ignore [bad-function-definition]
def delete_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)], totp_code: str = None):
    if owner.totp_enabled:
        if not totp_code:
            raise HTTPException(status_code=400, detail="2FA code required")
        # pyrefly: ignore [missing-import]
        from services.auth_service import verify_totp
        if not verify_totp(owner.totp_secret, totp_code):
            raise HTTPException(status_code=400, detail="Invalid 2FA code")
            
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.network_owner_id = None
    db.commit()
    
    db.delete(tenant)
    db.commit()
    log(db, "tenant_deleted", f"Tenant '{tenant.company_name}' deleted",
        user_id=owner.id, user_name=owner.full_name, level=AuditLevel.warning)
    return {"message": "Deleted"}


@router.get("/keys")
def list_keys(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    keys = db.query(ActivationKey).order_by(ActivationKey.created_at.desc()).all()
    result = []
    for k in keys:
        tenant = db.query(Tenant).filter(Tenant.id == k.tenant_id).first()
        result.append({
            "id": k.id,
            "key_code": k.key_code,
            "tenant_id": k.tenant_id,
            "company_name": tenant.company_name if tenant else "—",
            "is_used": k.is_used,
            "created_at": k.created_at,
        })
    return result


@router.post("/keys")
def generate_key(tenant_id: int, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    key = ActivationKey(tenant_id=tenant_id, key_code=_gen_key())
    db.add(key)
    db.commit()
    db.refresh(key)
    log(db, "key_generated", f"Activation key generated for {tenant.company_name}",
        user_id=owner.id, user_name=owner.full_name, level=AuditLevel.info)
    return {"key_code": key.key_code, "tenant_id": tenant_id}


@router.delete("/keys/{key_id}")
def delete_key(key_id: int, db: Annotated[Session, Depends(get_db)], owner: Annotated[User, Depends(require_system_owner)]):
    key = db.query(ActivationKey).filter(ActivationKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    if key.is_used:
        raise HTTPException(status_code=400, detail="Cannot delete a used key")
    db.delete(key)
    db.commit()
    return {"message": "Deleted"}


from datetime import datetime

@router.get("/audit-logs")
def all_audit_logs(
    db: Annotated[Session, Depends(get_db)], 
    _=Depends(require_system_owner),
    from_date: datetime | None = None,
    to_date: datetime | None = None
):
    query = db.query(AuditLog)
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)
        
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return [{"id": l.id, "user_name": l.user_name, "action": l.action,
             "description": l.description, "level": l.level, "created_at": l.created_at} for l in logs]


@router.get("/stats")
def stats(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    return {
        "total_tenants": db.query(Tenant).count(),
        "active_tenants": db.query(Tenant).filter(Tenant.status == TenantStatus.active).count(),
        "total_devices": sum(len(t.devices) for t in db.query(Tenant).all()),
        "pending_keys": db.query(ActivationKey).filter(ActivationKey.is_used == False).count(),
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
            "force_2fa": u.force_2fa,
            "totp_enabled": u.totp_enabled,
            "company_name": tenant.company_name if tenant else "—"
        })
    return result

@router.get("/audit/export")
def export_audit_logs(db: Annotated[Session, Depends(get_db)], _=Depends(require_system_owner)):
    from fastapi.responses import StreamingResponse
    import io
    import csv

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tenant ID", "User ID", "User Name", "Action", "Description", "Level", "Created At"])
    
    for log_ in logs:
        writer.writerow([
            log_.id,
            log_.tenant_id or "",
            log_.user_id or "",
            log_.user_name or "",
            log_.action,
            log_.description,
            log_.level,
            log_.created_at.isoformat() if log_.created_at else ""
        ])
        
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )
