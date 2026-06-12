from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
# pyrefly: ignore [missing-import]
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
    city = Column(String, nullable=True)
    zerotier_network_id = Column(String, unique=True, nullable=True)
    network_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    max_second_masters = Column(Integer, default=2)
    status = Column(Enum(TenantStatus), default=TenantStatus.pending)
    wg_server_public_key = Column(String, nullable=True)
    wg_server_endpoint = Column(String, nullable=True)
    wg_server_interface = Column(String, nullable=True, default="wg0")
    # pyrefly: ignore [deprecated]
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # -- MIGRATION (SQLite) --
    # ALTER TABLE tenants ADD COLUMN wg_server_public_key VARCHAR;
    # ALTER TABLE tenants ADD COLUMN wg_server_endpoint VARCHAR;
    # ALTER TABLE tenants ADD COLUMN wg_server_interface VARCHAR DEFAULT 'wg0';

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan", foreign_keys="[User.tenant_id]")
    devices = relationship("Device", back_populates="tenant", cascade="all, delete-orphan")
    activation_keys = relationship("ActivationKey", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")
