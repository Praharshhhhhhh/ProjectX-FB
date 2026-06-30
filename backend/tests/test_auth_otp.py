import pytest
import time
from datetime import datetime, timedelta
from models import User, UserRole, Tenant
from services.auth_service import hash_password, verify_otp_hash
from config import get_settings

settings = get_settings()

def _setup_user(db, email="master@test.com", role=UserRole.master, force_otp=False):
    tenant = Tenant(company_name="OTP Tenant")
    db.add(tenant)
    db.flush()

    user = User(
        email=email,
        full_name="OTP User",
        hashed_password=hash_password("Pass123!"),
        role=role,
        force_otp=force_otp,
        tenant_id=tenant.id,
        uuid=f"uuid-{email}"
    )
    db.add(user)
    db.commit()
    return user

def test_login_master_requires_otp_no_token_yet(client, db_session, mock_email):
    user = _setup_user(db_session)

    res = client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})
    assert res.status_code == 200
    data = res.json()
    assert data["requires_otp"] is True
    assert "access_token" not in data or data["access_token"] == ""

    # Verify email was called
    mock_email.assert_called_once()
    body = mock_email.call_args[0][2]
    assert "Your one-time code is" in body

def test_verify_otp_correct_code_issues_token(client, db_session, mock_email):
    user = _setup_user(db_session)
    client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})

    # Capture the code from the email call args
    body = mock_email.call_args[0][2]
    code = body.split("is ")[1].split(".")[0].strip()

    res = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["access_token"] != ""
    
    # OTP fields cleared
    db_session.expire_all()
    assert user.email_otp_code_hash is None
    assert user.email_otp_expires_at is None

def test_verify_otp_wrong_code_increments_attempts(client, db_session, mock_email):
    user = _setup_user(db_session)
    client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})

    res = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "999999"})
    assert res.status_code == 400
    assert "invalid code" in res.json()["detail"].lower()

    db_session.expire_all()
    assert user.email_otp_attempts == 1

def test_verify_otp_expired_code_rejected(client, db_session, mock_email):
    user = _setup_user(db_session)
    client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})

    # Force expiration
    user.email_otp_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    res = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "123456"})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

def test_verify_otp_max_attempts_locks_out(client, db_session, mock_email):
    user = _setup_user(db_session)
    client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})

    user.email_otp_attempts = settings.OTP_MAX_ATTEMPTS
    db_session.commit()

    res = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "123456"})
    assert res.status_code == 400
    assert "too many incorrect attempts" in res.json()["detail"].lower()

def test_resend_otp_respects_cooldown(client, db_session, mock_email):
    user = _setup_user(db_session)
    client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})

    # Instant resend attempt should fail rate limit
    res = client.post("/api/auth/resend-otp", json={"email": user.email})
    assert res.status_code == 429

    # Wait out the cooldown (configured to 2s in conftest)
    time.sleep(2.1)

    res2 = client.post("/api/auth/resend-otp", json={"email": user.email})
    assert res2.status_code == 200

def test_admin_role_login_does_not_require_otp_unless_force_otp_set(client, db_session, mock_email):
    admin_user = _setup_user(db_session, email="admin@test.com", role=UserRole.admin)
    
    # 1. Login normally without OTP
    res = client.post("/api/auth/login", json={"email": admin_user.email, "password": "Pass123!"})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert mock_email.call_count == 0

    # 2. Set force_otp = True and test login
    admin_user.force_otp = True
    db_session.commit()

    res2 = client.post("/api/auth/login", json={"email": admin_user.email, "password": "Pass123!"})
    assert res2.status_code == 200
    assert res2.json()["requires_otp"] is True
    assert mock_email.call_count == 1
