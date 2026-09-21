from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = None
    role: str = "admin"


class UserOut(BaseModel):
    id: int
    uuid: Optional[str] = None
    email: str
    full_name: str
    role: str
    is_active: bool
    is_trusted: bool
    force_otp: bool
    tenant_id: Optional[int]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class TrustToggle(BaseModel):
    is_trusted: bool


class Force2FAToggle(BaseModel):
    force_2fa: bool


class RoleUpdate(BaseModel):
    new_role: str
