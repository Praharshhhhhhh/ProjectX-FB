from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

class SubnetProvisioningState(str, enum.Enum):
    pending = "pending"
    allocating_table = "allocating_table"
    provisioning_zt = "provisioning_zt"
    provisioning_wg = "provisioning_wg"
    pending_retry = "pending_retry"
    active = "active"
    failed = "failed"

class SubnetHealth(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    unreachable = "unreachable"
    unknown = "unknown"

class ComponentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

class SubnetRegistry(Base):
    __tablename__ = "subnet_registry"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    
    router_zt_ip = Column(String, nullable=True)
    lan_subnet = Column(String, nullable=False)
    table_id = Column(Integer, unique=True, index=True, nullable=True)
    zt_interface = Column(String, nullable=True)
    
    claimed_state = Column(Enum(SubnetProvisioningState), default=SubnetProvisioningState.pending)
    provisioning_started_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    health = Column(Enum(SubnetHealth), default=SubnetHealth.unknown)
    last_sync = Column(DateTime, nullable=True)
    
    policy_status = Column(Enum(ComponentStatus), default=ComponentStatus.UNKNOWN)
    route_status = Column(Enum(ComponentStatus), default=ComponentStatus.UNKNOWN)
    forward_status = Column(Enum(ComponentStatus), default=ComponentStatus.UNKNOWN)
    nat_status = Column(Enum(ComponentStatus), default=ComponentStatus.UNKNOWN)

    router = relationship("Router", back_populates="subnet_registry")
    tenant = relationship("Tenant")
