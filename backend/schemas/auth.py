from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str = ""
    token_type: str = "bearer"
    role: str = ""
    requires_otp: bool = False
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


class ChangePasswordRequest(BaseModel):
    new_password: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str


class ResendOtpRequest(BaseModel):
    email: EmailStr
