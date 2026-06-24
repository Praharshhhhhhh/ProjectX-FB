from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class UserDeviceAccess(Base):
    __tablename__ = "user_device_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"), primary_key=True)

    user = relationship("User", back_populates="device_access")
    device = relationship("Device", back_populates="user_access")
