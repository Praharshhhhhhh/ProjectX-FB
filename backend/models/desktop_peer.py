from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class DesktopPeer(Base):
    __tablename__ = "desktop_peers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    public_key = Column(String, unique=True, index=True, nullable=False)
    wg_ip = Column(String, nullable=False)
    device_name = Column(String, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    endpoint_ip = Column(String, nullable=True)
    last_handshake = Column(DateTime, nullable=True)
    tunnel_state = Column(String, default="disconnected", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'device_name', name='uix_user_device'),
    )

    user = relationship("User")
    tenant = relationship("Tenant")
