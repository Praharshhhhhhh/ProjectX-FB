from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, ActivationKey, Tenant
from schemas.auth import (
    LoginRequest, Token, ActivateKeyRequest, ChangePasswordRequest,
    VerifyOtpRequest, ResendOtpRequest, UpdateProfileRequest
)
from services import auth_service
from services import email_service
from routers.deps import get_current_user
from config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if auth_service.requires_email_otp(user):
        # Generate OTP, hash it, store, email it — no JWT yet
        code = auth_service.generate_otp_code()
        user.email_otp_code_hash = auth_service.hash_otp(code)
        user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        user.email_otp_attempts = 0
        user.email_otp_last_sent_at = datetime.utcnow()
        db.commit()

        print(f"[DEBUG] Generated OTP code for {user.email}: {code}")
        try:
            email_service.send_otp_email(user.email, code)
        except Exception:
            pass  # Email send failure shouldn't block login flow

        return Token(requires_otp=True, role=user.role)

    # No OTP required — issue JWT immediately
    token = auth_service.create_access_token({
        "user_id": user.id,
        "uuid": user.uuid,
        "role": user.role,
        "tenant_id": user.tenant_id,
    })

    return Token(
        access_token=token,
        role=user.role,
        requires_password_change=user.must_change_password,
    )


@router.post("/verify-otp")
def verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    user = auth_service.get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=400, detail="OTP expired or not requested.")

    # Check expiry
    if not user.email_otp_code_hash or not user.email_otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired or not requested.")
    if user.email_otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired or not requested.")

    # Check attempt limit
    if user.email_otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="Too many incorrect attempts. Please request a new code.")

    # Verify code
    if not auth_service.verify_otp_hash(req.code, user.email_otp_code_hash):
        user.email_otp_attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid code.")

    # Success — clear OTP fields, mark first login done, and issue JWT
    user.email_otp_code_hash = None
    user.email_otp_expires_at = None
    user.email_otp_attempts = 0
    user.first_login_otp_done = True  # Never ask OTP again unless force_otp is set
    db.commit()

    token = auth_service.create_access_token({
        "user_id": user.id,
        "uuid": user.uuid,
        "role": user.role,
        "tenant_id": user.tenant_id,
    })

    return Token(
        access_token=token,
        role=user.role,
        requires_password_change=user.must_change_password,
    )


@router.post("/resend-otp")
def resend_otp(req: ResendOtpRequest, db: Session = Depends(get_db)):
    user = auth_service.get_user_by_email(db, req.email)
    if not user:
        # Don't reveal whether the email exists
        return {"message": "If that email is registered, a new code has been sent."}

    # Rate limit check
    if user.email_otp_last_sent_at:
        elapsed = (datetime.utcnow() - user.email_otp_last_sent_at).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)} seconds before requesting a new code.",
            )

    code = auth_service.generate_otp_code()
    user.email_otp_code_hash = auth_service.hash_otp(code)
    user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    user.email_otp_attempts = 0
    user.email_otp_last_sent_at = datetime.utcnow()
    db.commit()

    print(f"[DEBUG] Generated OTP code for {user.email}: {code}")
    try:
        email_service.send_otp_email(user.email, code)
    except Exception:
        pass

    return {"message": "If that email is registered, a new code has been sent."}


@router.post("/activate-key")
def activate_master_key(req: ActivateKeyRequest, db: Session = Depends(get_db)):
    # 1. Validate key exists and is unused
    key = db.query(ActivationKey).filter(
        ActivationKey.key_code == req.key_code, ActivationKey.is_used == False
    ).first()
    if not key:
        raise HTTPException(status_code=400, detail="Invalid or already used activation key")

    # 2. Guard duplicate email
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 3. Create a new Tenant for this master user
    tenant_name = f"Tenant of {req.email.split('@')[0]}"
    base_name = tenant_name
    counter = 1
    while db.query(Tenant).filter(Tenant.company_name == tenant_name).first():
        tenant_name = f"{base_name} ({counter})"
        counter += 1

    tenant = Tenant(company_name=tenant_name)
    db.add(tenant)
    db.flush()

    import uuid as _uuid
    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=auth_service.hash_password(req.password),
        role=UserRole.master,
        is_active=True,
        tenant_id=tenant.id,
        uuid=_uuid.uuid4().hex,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 4. Do NOT issue JWT here. Force the user to log in so OTP is triggered.
    return {"message": "Activation successful. Please log in to complete verification."}


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.hashed_password = auth_service.hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password updated successfully"}


@router.post("/activate-master")
def activate_master(req: ActivateKeyRequest, db: Session = Depends(get_db)):
    if not req.key_code.startswith("MSTKEY-"):
        raise HTTPException(status_code=400, detail="Invalid master activation key format")
        
    tenant = db.query(Tenant).filter(Tenant.master_activation_key == req.key_code).first()
    if not tenant:
        raise HTTPException(status_code=400, detail="Invalid or expired activation key")
        
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already in use")
        
    # Create the master user
    master_user = User(
        tenant_id=tenant.id,
        email=req.email,
        full_name=req.full_name,
        hashed_password=auth_service.hash_password(req.password),
        role=UserRole.master,
        must_change_password=False,
        uuid=uuid.uuid4().hex,
        first_login_otp_done=False
    )
    db.add(master_user)
    
    # Invalidate the activation key
    tenant.master_activation_key = None
    db.commit()
    
    # Do NOT issue JWT here. Force the user to log in so OTP is triggered.
    return {"message": "Activation successful. Please log in to complete verification."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first() if current_user.tenant_id else None
    return {
        "id": current_user.id,
        "uuid": current_user.uuid,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "company_name": tenant.company_name if tenant else None,
        "must_change_password": current_user.must_change_password,
    }

@router.patch("/me")
def update_me(req: UpdateProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.full_name = req.full_name
    db.commit()
    return {"message": "Profile updated successfully"}
