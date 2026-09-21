from sqlalchemy import Column, Integer
from database import Base

class TableAllocator(Base):
    __tablename__ = "table_allocators"

    id = Column(Integer, primary_key=True, index=True)
    next_table_id = Column(Integer, nullable=False, default=100)
    next_wg_ip_octet = Column(Integer, nullable=False, default=2)
