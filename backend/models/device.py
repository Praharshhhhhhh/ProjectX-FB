from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
# pyrefly: ignore [missing-import]
from database import Base
import enum


class DeviceStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    offline = "offline"
    connecting = "connecting"


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, default="New Gateway")
    # -- MIGRATION SNIPPET (SQLite) --
    # ALTER TABLE devices ADD COLUMN wg_public_key VARCHAR UNIQUE;
    # ALTER TABLE devices ADD COLUMN wg_ip VARCHAR;
    # ALTER TABLE devices ADD COLUMN tunnel_type VARCHAR DEFAULT 'zerotier';
    
    zerotier_node_id = Column(String, unique=True, nullable=True) # Changed to nullable=True for wireguard only devices
    zerotier_ip = Column(String, nullable=True)
    wg_public_key = Column(String, unique=True, nullable=True)
    wg_ip = Column(String, nullable=True)
    tunnel_type = Column(String, default="zerotier")
    lan_ip = Column(String, nullable=True)
    lan_subnet = Column(String, nullable=True)
    network_id = Column(String, nullable=True)
    status = Column(Enum(DeviceStatus), default=DeviceStatus.pending)
    is_approved = Column(Boolean, default=False)
    # pyrefly: ignore [deprecated]
    created_at = Column(DateTime, default=datetime.utcnow)
    # pyrefly: ignore [deprecated]
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="devices")
    lan_devices = relationship("LanDevice", back_populates="gateway", cascade="all, delete-orphan")
    user_access = relationship("UserDeviceAccess", back_populates="device", cascade="all, delete-orphan")
