from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditLogOut(BaseModel):
    id: int
    user_name: Optional[str]
    action: str
    description: str
    level: str
    created_at: datetime

    class Config:
        from_attributes = True
