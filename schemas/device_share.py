from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DeviceShareCreate(BaseModel):
    device_id: int
    target_tenant_id: int

class DeviceShareResponse(BaseModel):
    id: int
    device_id: int
    source_tenant_id: int
    target_tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True
