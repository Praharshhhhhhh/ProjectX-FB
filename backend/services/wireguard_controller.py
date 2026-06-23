import base64
from typing import Optional
from sqlalchemy.orm import Session
from models.device import Device
from config import get_settings

settings = get_settings()
# fallback for endpoint if not in settings
WG_SERVER_ENDPOINT = getattr(settings, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")

async def generate_keypair() -> tuple[str, str]:
    try:
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives import serialization
        
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # WireGuard expects the raw 32-byte scalar
        priv_bytes = private_key.private_bytes_raw()
        pub_bytes = public_key.public_bytes_raw()
        
        priv_b64 = base64.b64encode(priv_bytes).decode('utf-8')
        pub_b64 = base64.b64encode(pub_bytes).decode('utf-8')
        
        return priv_b64, pub_b64
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to generate keypair: {e}")
        return "", ""

def assign_ip_from_pool(db: Session, tenant_id: int) -> str:
    # Get all used IPs for this tenant
    devices = db.query(Device).filter(Device.tenant_id == tenant_id, Device.wg_ip.isnot(None)).all()
    used_ips = {d.wg_ip for d in devices if d.wg_ip}
    
    # Use the tenant_id to determine the subnet (e.g. 10.T.0.X) to avoid collisions
    # between tenants on the same server, or to isolate them cleanly.
    t_subnet = (tenant_id % 254) + 1
    
    for i in range(2, 255):
        ip = f"10.{t_subnet}.0.{i}"
        if ip not in used_ips:
            return ip
    return f"10.{t_subnet}.0.254"

def generate_client_config(private_key: str, assigned_ip: str, server_pubkey: str, server_endpoint: str, virtual_pool: str = None, real_subnet: str = None, client_pubkey: str = None) -> str:
    if assigned_ip.startswith("10."):
        # Route the entire ProjectX subnet (10.0.0.0/8) through the VPN 
        # so clients can reach the Hub (10.0.0.1) AND other peers (10.x.x.x)
        allowed_ips = "10.0.0.0/8"
    else:
        allowed_ips = "10.0.0.0/8"

    post_up = ""
    post_down = ""
    
    if client_pubkey:
        backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
        # Extract the local LAN subnet (ignoring wg interfaces) and send it with the heartbeat
        post_up += f"PostUp = (while true; do SUBNET=$(ip route | awk '/kernel/ && !/wg/ {{print $1}}' | head -n 1); curl -s -X POST {backend_url}/api/devices/heartbeat -H 'Content-Type: application/json' -d \"{{\\\"zerotier_node_id\\\": \\\"{client_pubkey}\\\", \\\"lan_subnet\\\": \\\"$SUBNET\\\"}}\"; sleep 30; done) >/dev/null 2>&1 &\n"
        post_down += f"PostDown = pkill -f 'curl.*{client_pubkey[:8]}'\n"
        
    if virtual_pool and real_subnet:
        # Inject Linux iptables NETMAP translation directly into the Edge Gateway config
        post_up += f"PostUp = iptables -t nat -A PREROUTING -d {virtual_pool}.0/24 -j NETMAP --to {real_subnet}\n"
        post_down += f"PostDown = iptables -t nat -D PREROUTING -d {virtual_pool}.0/24 -j NETMAP --to {real_subnet}\n"

    conf = f"""[Interface]
PrivateKey = {private_key if private_key else 'REPLACE_ME'}
Address = {assigned_ip}/32
{post_up}{post_down}
[Peer]
PublicKey = {server_pubkey}
Endpoint = {server_endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
"""

    return conf
