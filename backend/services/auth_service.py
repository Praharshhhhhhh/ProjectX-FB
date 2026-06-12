from datetime import datetime, timedelta
from typing import Optional
# pyrefly: ignore [untyped-import]
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import pyotp
# pyrefly: ignore [untyped-import]
import qrcode
import io
import base64

# pyrefly: ignore [missing-import]
from config import get_settings
# pyrefly: ignore [missing-import]
from models import User, UserRole

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # pyrefly: ignore [deprecated]
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        # pyrefly: ignore [bad-return]
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


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_qr_base64(secret: str, email: str, app_name: str = "ProjectX") -> str:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=app_name)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def requires_2fa_setup(user: User) -> bool:
    if user.totp_enabled:
        return False
    return user.role in (UserRole.master, UserRole.second_master) or user.force_2fa


def requires_2fa_verification(user: User) -> bool:
    return user.totp_enabled or user.force_2fa
