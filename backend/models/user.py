from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
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
    must_change_password = Column(Boolean, default=False)
    force_otp = Column(Boolean, default=False)
    first_login_otp_done = Column(Boolean, default=False)  # True after first successful OTP verify

    # Email OTP fields
    email_otp_code_hash = Column(String, nullable=True)
    email_otp_expires_at = Column(DateTime, nullable=True)
    email_otp_attempts = Column(Integer, default=0)
    email_otp_last_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users", foreign_keys="[User.tenant_id]")
