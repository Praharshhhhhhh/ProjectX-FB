from sqlalchemy.orm import Session
from models import AuditLog, AuditLevel
from typing import Optional


def log(
    db: Session,
    action: str,
    description: str,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    level: AuditLevel = AuditLevel.info,
):
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        user_name=user_name or "System",
        action=action,
        description=description,
        level=level,
    )
    db.add(entry)
    db.commit()
