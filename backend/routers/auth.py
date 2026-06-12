from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, UserRole, ActivationKey, Tenant
# pyrefly: ignore [missing-import]
from schemas.auth import (
    LoginRequest, Token, ActivateKeyRequest, ClaimNetworkRequest,
    ClaimWgServerRequest, Verify2FARequest, ChangePasswordRequest
)
# pyrefly: ignore [missing-import]
from services import auth_service
# pyrefly: ignore [missing-import]
from services import audit_service
# pyrefly: ignore [missing-import]
from services.audit_service import log
# pyrefly: ignore [missing-import]
from models.audit_log import AuditLevel
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user
import secrets

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = auth_service.create_access_token({
        "user_id": user.id,
        "role": user.role,
        "tenant_id": user.tenant_id,
    })

    log(db, "login", f"{user.full_name} logged in", tenant_id=user.tenant_id,
        user_id=user.id, user_name=user.full_name, level=AuditLevel.info)

    return Token(
        access_token=token,
        role=user.role,
        requires_2fa=auth_service.requires_2fa_setup(user),
        requires_password_change=user.must_change_password,
    )


@router.post("/activate-key")
def activate_master_key(req: ActivateKeyRequest, db: Session = Depends(get_db)):
    key = db.query(ActivationKey).filter(
        ActivationKey.key_code == req.key_code, ActivationKey.is_used == False
    ).first()
    if not key:
        raise HTTPException(status_code=400, detail="Invalid or already used activation key")

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    existing_master = db.query(User).filter(
        User.tenant_id == key.tenant_id, User.role == UserRole.master
    ).first()
    if existing_master:
        raise HTTPException(status_code=400, detail="Tenant already has a master user")

    user = User(
        tenant_id=key.tenant_id,
        email=req.email,
        full_name=req.full_name,
        hashed_password=auth_service.hash_password(req.password),
        role=UserRole.master,
        is_active=True,
    )
    db.add(user)
    db.flush()

    key.is_used = True
    key.used_by_user_id = user.id

    tenant = db.query(Tenant).filter(Tenant.id == key.tenant_id).first()
    if tenant:
        # pyrefly: ignore [missing-import]
        from models.tenant import TenantStatus
        tenant.status = TenantStatus.active

    db.commit()
    db.refresh(user)

    log(db, "master_activated", f"Master user {user.email} activated for tenant {key.tenant_id}",
        tenant_id=key.tenant_id, user_id=user.id, user_name=user.full_name, level=AuditLevel.success)

    token = auth_service.create_access_token({
        "user_id": user.id, "role": user.role, "tenant_id": user.tenant_id
    })
    return Token(access_token=token, role=user.role, requires_2fa=True)


@router.post("/setup-2fa")
def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Removed check: allow re-configuration of 2FA even if already enabled
    secret = auth_service.generate_totp_secret()
    current_user.totp_secret = secret
    db.commit()
    qr = auth_service.get_totp_qr_base64(secret, current_user.email)
    return {"qr_code": qr, "secret": secret}


@router.post("/verify-2fa")
def verify_2fa(req: Verify2FARequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not configured")
    if not auth_service.verify_totp(current_user.totp_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    current_user.totp_enabled = True
    db.commit()
    log(db, "totp_toggled", f"2FA enabled for {current_user.email}",
        tenant_id=current_user.tenant_id, user_id=current_user.id, user_name=current_user.full_name)
    return {"message": "2FA enabled successfully"}


@router.post("/claim-network")
def claim_network(req: ClaimNetworkRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Only master users can claim a network")
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.zerotier_network_id:
        raise HTTPException(status_code=400, detail="Network already claimed")
    existing = db.query(Tenant).filter(Tenant.zerotier_network_id == req.network_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Network ID already in use")
    tenant.zerotier_network_id = req.network_id
    tenant.network_owner_id = current_user.id
    db.commit()
    log(db, "network_claimed", f"ZeroTier network {req.network_id} claimed",
        tenant_id=tenant.id, user_id=current_user.id, user_name=current_user.full_name, level=AuditLevel.success)
    return {"message": "Network claimed successfully", "network_id": req.network_id}


@router.post("/claim-wg-server")
def claim_wg_server(
    req: ClaimWgServerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(403, "Only master users can claim a WireGuard server")
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    
    import base64
    try:
        decoded = base64.b64decode(req.server_public_key + "==")
        if len(decoded) != 32:
            raise ValueError
    except Exception:
        raise HTTPException(400, "Invalid WireGuard public key format")
    
    parts = req.server_endpoint.rsplit(":", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        raise HTTPException(400, "Endpoint must be in host:port format")
    
    tenant.wg_server_public_key = req.server_public_key
    tenant.wg_server_endpoint = req.server_endpoint
    tenant.wg_server_interface = req.server_interface
    tenant.network_owner_id = current_user.id
    db.commit()
    
    log(db, "wg_server_claimed",
        f"WireGuard server {req.server_endpoint} claimed by {current_user.full_name}",
        tenant_id=tenant.id, user_id=current_user.id,
        user_name=current_user.full_name, level=AuditLevel.success)
    
    return {
        "message": "WireGuard server claimed successfully",
        "server_endpoint": req.server_endpoint,
        "server_public_key": req.server_public_key
    }


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.hashed_password = auth_service.hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password changed"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first() if current_user.tenant_id else None
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "network_id": tenant.zerotier_network_id if tenant else None,
        "totp_enabled": current_user.totp_enabled,
        "must_change_password": current_user.must_change_password,
    }
