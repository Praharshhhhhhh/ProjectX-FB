import os
from pydantic_settings import BaseSettings
from functools import lru_cache

# Single project-root .env (one level up from backend/). Falls back to the
# local backend/.env if the root file is absent, so nothing breaks.
_ROOT_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
_LOCAL_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_ENV_FILE = _ROOT_ENV if os.path.exists(_ROOT_ENV) else _LOCAL_ENV


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    OWNER_EMAIL: str = "owner@projectx.io"
    OWNER_PASSWORD: str = "Admin@123"

    DATABASE_URL: str = "sqlite:///./projectx.db"

    ZEROTIER_CONTROLLER_URL: str = "http://localhost:9993"
    ZEROTIER_CONTROLLER_TOKEN: str = ""

    WG_SERVER_ENDPOINT: str = "127.0.0.1:51820"
    WG_SERVER_ENDPOINT_SECONDARY: str = ""

    APP_NAME: str = "ProjectX"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = _ENV_FILE
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
