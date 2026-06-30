import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import get_settings
from models import User, UserRole

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


# ── Email OTP helpers ──────────────────────────────────────────────────────────

def generate_otp_code() -> str:
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_otp_hash(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def requires_email_otp(user: User) -> bool:
    """Return True if this user must complete email OTP before receiving a JWT.

    Rules:
    - High-privilege roles (master, second_master, system_owner) must do OTP
      on their FIRST login ever (first_login_otp_done=False).
    - Any user with force_otp=True (set by System Owner) must always do OTP.
    - After first_login_otp_done=True and force_otp=False, no OTP is required.
    """
    is_privileged = user.role in (
        UserRole.master, UserRole.second_master, UserRole.system_owner
    )
    first_login_needed = is_privileged and not user.first_login_otp_done
    return first_login_needed or bool(user.force_otp)
