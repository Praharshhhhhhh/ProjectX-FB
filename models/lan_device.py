from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class LanDevice(Base):
    __tablename__ = "lan_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    name = Column(String, default="Unknown Device")
    ip_address = Column(String, nullable=False)
    mac_address = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    gateway = relationship("Device", back_populates="lan_devices")
