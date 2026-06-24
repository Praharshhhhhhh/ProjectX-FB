from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class LanDeviceOut(BaseModel):
    id: int
    name: str
    ip_address: str
    mac_address: Optional[str]

    class Config:
        from_attributes = True


class LanDeviceRename(BaseModel):
    name: str


class ConnectionInfo(BaseModel):
    tunnel_type: str
    virtual_ip: Optional[str]
    status: str
    conf_download_url: Optional[str] = None
    network_id: Optional[str] = None
    node_id: Optional[str] = None

class DeviceOut(BaseModel):
    id: int
    name: str
    zerotier_node_id: Optional[str]
    zerotier_ip: Optional[str]
    wg_public_key: Optional[str] = None
    wg_ip: Optional[str] = None
    tunnel_type: str = "zerotier"
    lan_ip: Optional[str]
    lan_subnet: Optional[str]
    nat_virtual_pool: Optional[str] = None
    network_id: Optional[str]
    status: str
    is_approved: bool
    tenant_id: int
    lan_devices: List[LanDeviceOut] = []
    created_at: datetime
    connection_info: Optional[ConnectionInfo] = None
    has_conflict: bool = False

    class Config:
        from_attributes = True


class DeviceApprove(BaseModel):
    device_id: int


class DeviceRegister(BaseModel):
    zerotier_node_id: str
    network_id: Optional[str] = None
    hostname: str = "Unknown Device"
    wg_public_key: Optional[str] = None
    zerotier_ip: Optional[str] = None
    lan_ip: Optional[str] = None
    lan_subnet: Optional[str] = None
    device_capability: Optional[Dict[str, Any]] = None


class WgDeviceRegister(BaseModel):
    wg_public_key: Optional[str] = None
    hostname: str = "Unknown Device"
    lan_ip: Optional[str] = None


class LanDeviceBulkUpdate(BaseModel):
    devices: List[dict]


class WgTunnelPeerOut(BaseModel):
    device_id: int
    name: str
    wg_public_key: str
    wg_ip: Optional[str]
    lan_ip: Optional[str]
    status: str
    db_status: str
    created_at: Optional[str]
