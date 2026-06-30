from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TenantCreate(BaseModel):
    company_name: str
    master_email: str


class TenantUpdate(BaseModel):
    pass  # Trimmed — extend as needed


class TenantOut(BaseModel):
    id: int
    company_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
