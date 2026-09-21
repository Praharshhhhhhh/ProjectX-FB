from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from datetime import datetime
from database import Base
import enum


class PendingValidationStatus(str, enum.Enum):
    pending = "pending"
    syncing = "syncing"
    failed = "failed"
    completed = "completed"


class PendingValidation(Base):
    __tablename__ = "pending_validations"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    claimed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    serial_number_submitted = Column(String, nullable=False)
    key_code_submitted = Column(String, nullable=False)  # Fernet-encrypted at rest
    status = Column(Enum(PendingValidationStatus), default=PendingValidationStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync_attempt_at = Column(DateTime, nullable=True)
    fail_reason = Column(String, nullable=True)
