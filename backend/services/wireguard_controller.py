import asyncio
import time
import os
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

import subprocess

async def _run_wg(*args) -> str:
    try:
        # Use subprocess.run to avoid NotImplementedError on Windows Selector loops
        result = await asyncio.to_thread(
            subprocess.run,
            [WG_CMD, *args],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except Exception:
        return ""

async def get_server_public_key(interface: str = "wg0") -> str:
    key = await _run_wg("show", interface, "public-key")
    if key:
        return key
    
    # Fallback to the first active interface
    interfaces_str = await _run_wg("show", "interfaces")
    if interfaces_str:
        first_iface = interfaces_str.split()[0]
        return await _run_wg("show", first_iface, "public-key")
        
    return ""

async def generate_keypair() -> tuple[str, str]:
    try:
        # Generate private key
        priv_result = await asyncio.to_thread(
            subprocess.run,
            [WG_CMD, "genkey"],
            capture_output=True,
            text=True
        )
        priv_key = priv_result.stdout.strip()
        
        if not priv_key:
            return "", ""
            
        # Generate public key from private key
        pub_result = await asyncio.to_thread(
            subprocess.run,
            [WG_CMD, "pubkey"],
            input=priv_key,
            capture_output=True,
            text=True
        )
        pub_key = pub_result.stdout.strip()
        
        return priv_key, pub_key
    except Exception:
        return "", ""

async def _save_conf(interface: str):
    if sys.platform != "win32":
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["wg-quick", "save", interface],
                capture_output=True
            )
        except Exception:
            pass

async def sync_windows_peers(interface: str, peers: list[tuple[str, str]]) -> bool:
    """
    On Windows, wg set fails with Permission Denied because the WireGuard Manager
    strictly locks the interface to SYSTEM. We must rewrite the conf file and
    bounce the WireGuard service.
    peers is a list of (public_key, allowed_ip) tuples.
    """
    if sys.platform != "win32":
        return False
        
    conf_path = f"C:\\Program Files\\WireGuard\\{interface}.conf"
    if not os.path.exists(conf_path):
        return False
        
    try:
        # Read existing conf and keep only the [Interface] block
        with open(conf_path, "r") as f:
            lines = f.readlines()
            
        interface_lines = []
        for line in lines:
            if line.strip() == "[Peer]":
                break
            # Only keep non-empty lines to prevent WireGuard parser from breaking
            if line.strip():
                interface_lines.append(line.strip() + "\n")
            
        # Append all new peers
        new_conf = "".join(interface_lines)
        for pub_key, allowed_ip in peers:
            # Check if allowed_ip already has CIDR notations (because of multiple IPs)
            if "/" in allowed_ip:
                ips = allowed_ip
            else:
                ips = f"{allowed_ip}/32"
            new_conf += f"\n[Peer]\nPublicKey = {pub_key}\nAllowedIPs = {ips}\n"
            
        with open(conf_path, "w") as f:
            f.write(new_conf)
            
        # Bounce the tunnel service using wireguard.exe, not wg.exe!
        WIREGUARD_EXE = r"C:\Program Files\WireGuard\wireguard.exe"
        
        await asyncio.to_thread(
            subprocess.run,
            [WIREGUARD_EXE, "/uninstalltunnelservice", interface],
            capture_output=True
        )
        
        # Windows Service Manager needs time to actually stop and delete the service
        # before we can install a new one with the exact same name.
        await asyncio.sleep(3)
        
        await asyncio.to_thread(
            subprocess.run,
            [WIREGUARD_EXE, "/installtunnelservice", conf_path],
            capture_output=True
        )
        
        # Another small sleep before executing interface commands
        await asyncio.sleep(1)
        # When the service is reinstalled, Windows resets IP Forwarding to Disabled.
        # We must re-enable it for the Hub-and-Spoke routing to work.
        # We MUST also enable WeakHostSend and WeakHostReceive to allow Hairpin routing
        # (routing packets back out the same interface they came in on).
        await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-Command", f"Set-NetIPInterface -InterfaceAlias {interface} -Forwarding Enabled -WeakHostSend Enabled -WeakHostReceive Enabled"],
            capture_output=True
        )
        
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to sync Windows peers: {e}")
        return False

async def add_peer(public_key: str, allowed_ip: str, interface: str = "wg0") -> bool:
    if not allowed_ip or not public_key:
        return False
        
    if sys.platform == "win32":
        from database import SessionLocal
        from models.device import Device
        db = SessionLocal()
        try:
            # Fetch all approved peers to rebuild the config completely
            devices = db.query(Device).filter(
                Device.tunnel_type == "wireguard", 
                Device.wg_public_key.isnot(None), 
                Device.wg_ip.isnot(None),
                Device.is_approved == True
            ).all()
            
            # Make sure to include the new peer if it's not yet in the DB or not yet approved
            peers = []
            found_new = False
            for d in devices:
                t_iface = d.tenant.wg_server_interface if d.tenant and d.tenant.wg_server_interface else "wg0"
                if t_iface == interface:
                    ip_str = f"{d.wg_ip}/32"
                    if d.nat_virtual_pool:
                        ip_str += f", {d.nat_virtual_pool}.0/24"
                    peers.append((d.wg_public_key, ip_str))
                    if d.wg_public_key == public_key:
                        found_new = True
                        
            if not found_new:
                # Provide the raw string, it might have commas
                peers.append((public_key, allowed_ip))
                
            return await sync_windows_peers(interface, peers)
        except Exception as e:
            print(f"Failed to add peer on Windows: {e}")
            return False
        finally:
            db.close()
            
    # wg set <interface> peer <pubkey> allowed-ips <ips>
    ips = allowed_ip if "/" in allowed_ip else f"{allowed_ip}/32"
    res = await _run_wg("set", interface, "peer", public_key, "allowed-ips", ips)
    await _save_conf(interface)
    return True

async def remove_peer(public_key: str, interface: str = "wg0") -> bool:
    if not public_key:
        return False
        
    if sys.platform == "win32":
        from database import SessionLocal
        from models.device import Device
        db = SessionLocal()
        try:
            # Fetch all approved peers to rebuild the config completely
            devices = db.query(Device).filter(
                Device.tunnel_type == "wireguard", 
                Device.wg_public_key.isnot(None), 
                Device.wg_ip.isnot(None),
                Device.is_approved == True
            ).all()
            
            peers = []
            for d in devices:
                t_iface = d.tenant.wg_server_interface if d.tenant and d.tenant.wg_server_interface else "wg0"
                # Exclude the peer we are removing
                if t_iface == interface and d.wg_public_key != public_key:
                    peers.append((d.wg_public_key, d.wg_ip))
                        
            return await sync_windows_peers(interface, peers)
        except Exception as e:
            print(f"Failed to remove peer on Windows: {e}")
            return False
        finally:
            db.close()
            
    # wg set <interface> peer <pubkey> remove
    res = await _run_wg("set", interface, "peer", public_key, "remove")
    await _save_conf(interface)
    return True

async def check_peer_status(public_key: str, interface: str = "wg0") -> str:
    if not public_key:
        return "offline"
    dump = await _run_wg("show", interface, "dump")
    if not dump:
        # Fallback to the first active interface
        interfaces_str = await _run_wg("show", "interfaces")
        if interfaces_str:
            first_iface = interfaces_str.split()[0]
            dump = await _run_wg("show", first_iface, "dump")
            
    if not dump:
        return "offline"

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

async def get_all_peer_statuses(interface: str = "wg0") -> dict:
    statuses = {}
    dump = await _run_wg("show", interface, "dump")
    if not dump:
        # Fallback to the first active interface
        interfaces_str = await _run_wg("show", "interfaces")
        if interfaces_str:
            first_iface = interfaces_str.split()[0]
            dump = await _run_wg("show", first_iface, "dump")
            
    if not dump:
        return statuses

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
