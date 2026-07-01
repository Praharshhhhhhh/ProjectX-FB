from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum


class RouterStatus(str, enum.Enum):
    prepared = "prepared"
    pending_validation = "pending_validation"
    claimed = "claimed"


class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(String, unique=True, nullable=False)
    serial_number = Column(String, unique=True, nullable=False)
    mac_address = Column(String, unique=True, nullable=False)
    zerotier_node_id = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    status = Column(Enum(RouterStatus), default=RouterStatus.prepared)
    name = Column(String, default="New Router")
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    claimed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    prepared_at = Column(DateTime, default=datetime.utcnow)
    claimed_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="routers")
    activation_key = relationship("ActivationKey", back_populates="router", uselist=False, cascade="all, delete-orphan")
    subnet_registry = relationship("SubnetRegistry", back_populates="router", uselist=False, cascade="all, delete-orphan")
