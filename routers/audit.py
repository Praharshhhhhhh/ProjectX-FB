from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from models import User, AuditLog, UserRole
# pyrefly: ignore [missing-import]
from routers.deps import get_current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])


from datetime import datetime

@router.get("/")
def get_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Annotated[Session, Depends(get_db)],
    from_date: datetime | None = None,
    to_date: datetime | None = None
):
    query = db.query(AuditLog)
    if current_user.role != UserRole.system_owner:
        query = query.filter(AuditLog.tenant_id == current_user.tenant_id)
        
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)
        
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    
    return [{"id": l.id, "user_name": l.user_name, "action": l.action,
             "description": l.description, "level": l.level, "created_at": l.created_at} for l in logs]
