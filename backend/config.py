import os
from pydantic_settings import BaseSettings
from functools import lru_cache

_ROOT_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
_LOCAL_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_ENV_FILE = _ROOT_ENV if os.path.exists(_ROOT_ENV) else _LOCAL_ENV


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    OWNER_EMAIL: str = "owner@setulink.io"
    OWNER_PASSWORD: str = "Admin@123"

    DATABASE_URL: str = "sqlite:///./setulink.db"

    # SMTP / Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@setulink.io"

    # OTP
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    # Field encryption (Fernet key for PendingValidation.key_code_submitted)
    FIELD_ENCRYPTION_KEY: str = ""

    APP_NAME: str = "SetuLink"
    APP_VERSION: str = "2.0.0"

    class Config:
        env_file = _ENV_FILE
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
