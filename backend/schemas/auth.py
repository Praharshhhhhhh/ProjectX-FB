from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    requires_2fa: bool = False
    requires_password_change: bool = False


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None


class ActivateKeyRequest(BaseModel):
    key_code: str
    email: EmailStr
    full_name: str
    password: str


class ClaimNetworkRequest(BaseModel):
    network_id: str


class ClaimWgServerRequest(BaseModel):
    server_public_key: str
    server_endpoint: str
    server_endpoint_secondary: Optional[str] = None
    server_interface: str = "wg0"


class Verify2FARequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    new_password: str
