import asyncio
import time
from typing import Optional
from sqlalchemy.orm import Session
from models.device import Device
# pyrefly: ignore [missing-import]
from config import get_settings

settings = get_settings()
# fallback for endpoint if not in settings
WG_SERVER_ENDPOINT = getattr(settings, "WG_SERVER_ENDPOINT", "127.0.0.1:51820")
import sys

WG_CMD = r"C:\Program Files\WireGuard\wg.exe" if sys.platform == "win32" else "wg"

async def _run_wg(*args) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            WG_CMD, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
        return ""
    except Exception:
        return ""

async def get_server_public_key() -> str:
    return await _run_wg("show", "wg-server", "public-key")

async def add_peer(public_key: str, allowed_ip: str) -> bool:
    if not allowed_ip or not public_key:
        return False
    # wg set wg-server peer <pubkey> allowed-ips <ip>/32
    res = await _run_wg("set", "wg-server", "peer", public_key, "allowed-ips", f"{allowed_ip}/32")
    return True

async def remove_peer(public_key: str) -> bool:
    if not public_key:
        return False
    # wg set wg-server peer <pubkey> remove
    res = await _run_wg("set", "wg-server", "peer", public_key, "remove")
    return True

async def check_peer_status(public_key: str, interface: str = "wg-server") -> str:
    if not public_key:
        return "offline"
    dump = await _run_wg("show", interface, "dump")
    for line in dump.split("\n"):
        parts = line.split("\t")
        if len(parts) >= 6 and parts[0] == public_key:
            try:
                latest_handshake = int(parts[4])
                if latest_handshake > 0 and (time.time() - latest_handshake) < 180:
                    return "active"
            except ValueError:
                pass
            return "offline"
    return "offline"

async def get_all_peer_statuses(interface: str = "wg-server") -> dict:
    statuses = {}
    dump = await _run_wg("show", interface, "dump")
    for line in dump.split("\n"):
        parts = line.split("\t")
        if len(parts) >= 6:
            public_key = parts[0]
            try:
                latest_handshake = int(parts[4])
                if latest_handshake > 0 and (time.time() - latest_handshake) < 180:
                    statuses[public_key] = "active"
                else:
                    statuses[public_key] = "offline"
            except ValueError:
                statuses[public_key] = "offline"
    return statuses

def assign_ip_from_pool(db: Session, tenant_id: int) -> str:
    # Get all used IPs
    devices = db.query(Device).filter(Device.wg_ip.isnot(None)).all()
    used_ips = {d.wg_ip for d in devices if d.wg_ip}
    
    # Simple allocation from 10.0.0.2 to 10.0.0.254
    for i in range(2, 255):
        ip = f"10.0.0.{i}"
        if ip not in used_ips:
            return ip
    return "10.0.0.254"

def generate_client_config(private_key: str, assigned_ip: str, server_pubkey: str, server_endpoint: str) -> str:
    # If the client provides a private key, we could include it, but the instruction 
    # said private keys must never be sent to backend. 
    # Thus, the client replaces it or we just generate the rest and client writes it.
    # The prompt actually says: Returns {assigned_ip, server_pubkey, server_endpoint, config} 
    # where config is the full .conf file content ready to be written by the client.
    # But wait: "Private keys must never be sent to the backend or logged". 
    # If so, we can't put PrivateKey in the config here if we don't have it.
    # Let's put a placeholder the client can replace, or let client use write_config().
    return f"""[Interface]
PrivateKey = {private_key if private_key else 'REPLACE_ME'}
Address = {assigned_ip}/32

[Peer]
PublicKey = {server_pubkey}
Endpoint = {server_endpoint}
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
"""
