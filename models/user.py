from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
# pyrefly: ignore [missing-import]
from database import Base
import enum


class UserRole(str, enum.Enum):
    system_owner = "system_owner"
    master = "master"
    second_master = "second_master"
    admin = "admin"
    trusted = "trusted"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.admin)
    is_active = Column(Boolean, default=True)
    is_trusted = Column(Boolean, default=False)
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)
    force_2fa = Column(Boolean, default=False)
    # pyrefly: ignore [deprecated]
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users", foreign_keys="[User.tenant_id]")
    device_access = relationship("UserDeviceAccess", back_populates="user", cascade="all, delete-orphan")
