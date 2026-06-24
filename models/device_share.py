from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime

# pyrefly: ignore [missing-import]
from database import Base

class DeviceShare(Base):
    __tablename__ = "device_shares"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    source_tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    target_tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    # pyrefly: ignore [deprecated]
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    device = relationship("Device", backref="shares")
    source_tenant = relationship("Tenant", foreign_keys=[source_tenant_id])
    target_tenant = relationship("Tenant", foreign_keys=[target_tenant_id])
