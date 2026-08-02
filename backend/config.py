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
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@setulink.io"

    # OTP
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    # Field encryption (Fernet key for PendingValidation.key_code_submitted)
    FIELD_ENCRYPTION_KEY: str = ""

    # Provisioning
    MAX_PROVISIONING_RETRIES: int = 3

    APP_NAME: str = "SetuLink"
    APP_VERSION: str = "2.0.0"

    # Gateway Phase 6 fallback
    GATEWAY_PUBKEY: str = "q1z1P+nKkx2gW7dD2d2e1A0O1H/I6+tT6eM1yA9o/zM="

    # ZeroTier Architecture Configuration
    ZT_API_TOKEN: str = ""
    GATEWAY_ZT_NODE_ID: str = ""
    GLOBAL_ZT_NETWORK_ID: str = ""
    MOCK_ZT_API: bool = False

    model_config = {
        "env_file": _ENV_FILE,
        "extra": "ignore"
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
