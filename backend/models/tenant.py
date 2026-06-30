from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum


class TenantStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    inactive = "inactive"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, unique=True, nullable=False)
    status = Column(Enum(TenantStatus), default=TenantStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    master_activation_key = Column(String, nullable=True)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan", foreign_keys="[User.tenant_id]")
    routers = relationship("Router", back_populates="tenant", cascade="all, delete-orphan")
