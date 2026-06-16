from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TenantCreate(BaseModel):
    company_name: str
    city: Optional[str] = None


class TenantUpdate(BaseModel):
    max_second_masters: Optional[int] = None


class TenantOut(BaseModel):
    id: int
    company_name: str
    city: Optional[str]
    zerotier_network_id: Optional[str]
    status: str
    created_at: datetime
    wg_server_public_key: Optional[str] = None
    wg_server_endpoint: Optional[str] = None
    wg_server_endpoint_secondary: Optional[str] = None
    device_count: int = 0
    user_count: int = 0

    class Config:
        from_attributes = True
