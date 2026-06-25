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

def generate_hub_config(private_key: str, assigned_ip: str, listen_port: int, peers: list[dict], virtual_pool: str = None, real_subnet: str = None) -> str:
    post_up = ""
    post_down = ""
    
    if virtual_pool and real_subnet:
        post_up += f"PostUp = iptables -t nat -A PREROUTING -d {virtual_pool}.0/24 -j NETMAP --to {real_subnet}\n"
        post_down += f"PostDown = iptables -t nat -D PREROUTING -d {virtual_pool}.0/24 -j NETMAP --to {real_subnet}\n"

    conf = f"""[Interface]
PrivateKey = {private_key if private_key else 'REPLACE_ME'}
Address = {assigned_ip}/8
ListenPort = {listen_port}
{post_up}{post_down}"""

    for peer in peers:
        conf += f"""
[Peer]
PublicKey = {peer['pubkey']}
AllowedIPs = {peer['allowed_ips']}
"""
    return conf

def get_bin_path(name: str) -> str:
    import sys, os
    if sys.platform != "win32":
        return name
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, ".bin", name)

def start_hub():
    import sys, os, subprocess, logging, time
    from config import get_settings
    settings = get_settings()
    
    interface = getattr(settings, "WG_SERVER_INTERFACE", "wg0")
    privkey = getattr(settings, "WG_SERVER_PRIVATE_KEY", None)
    
    if sys.platform == "win32":
        try:
            # 1. Enable IP Forwarding in Registry
            subprocess.run(["powershell", "-Command", "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters' -Name 'IPEnableRouter' -Value 1"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 2. Setup NAT
            nat_check = subprocess.run(["powershell", "-Command", "Get-NetNat -Name 'ProjectX_NAT'"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if nat_check.returncode != 0:
                subprocess.run(["powershell", "-Command", "New-NetNat -Name 'ProjectX_NAT' -InternalIPInterfaceAddressPrefix '10.0.0.0/8'"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            if privkey:
                # 3. Create config
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                bin_dir = os.path.join(base_dir, ".bin")
                os.makedirs(bin_dir, exist_ok=True)
                conf_path = os.path.join(bin_dir, f"{interface}.conf")
                
                port = getattr(settings, "WG_SERVER_PORT", "51820")
                
                conf = f"[Interface]\nPrivateKey = {privkey}\nListenPort = {port}\nAddress = 10.0.0.1/8\n"
                with open(conf_path, "w") as f:
                    f.write(conf)
                
                # 4. Start tunnel
                wg_manager = get_bin_path("wireguard.exe")
                # Attempt to uninstall old one if it exists
                subprocess.run([wg_manager, "/uninstalltunnelservice", interface], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(1)
                
                cmd = [wg_manager, "/installtunnelservice", conf_path]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    logging.info(f"Successfully started Windows WireGuard Hub on {interface}")
                except (subprocess.CalledProcessError, OSError):
                    # Fallback to UAC prompt
                    try:
                        args_joined = " ".join(f'"{str(a)}"' for a in cmd[1:])
                        ps_cmd = f"Start-Process -FilePath '{cmd[0]}' -ArgumentList '{args_joined}' -Verb RunAs -WindowStyle Hidden -Wait"
                        subprocess.run(["powershell", "-Command", ps_cmd], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        logging.info(f"Successfully started Windows WireGuard Hub on {interface} (via UAC elevation)")
                    except Exception as e:
                        logging.error(f"Failed to start Windows Hub (UAC fallback failed): {e}")
                    
        except Exception as e:
            logging.error(f"Exception starting Windows Hub: {e}")
    else:
        # On Linux, assume the user handles wg0 via wg-quick or we can attempt to bring it up
        logging.info("Backend running on Linux. Assuming wg0 is configured by host admin.")

def sync_peer_to_vps(client_pubkey: str, assigned_ip: str, remove: bool = False):
    import subprocess
    import logging
    import sys
    
    interface = getattr(settings, "WG_SERVER_INTERFACE", "wg0")
    wg_cmd = get_bin_path("wg.exe") if sys.platform == "win32" else "wg"
    
    if remove:
        cmd = [wg_cmd, "set", interface, "peer", client_pubkey, "remove"]
    else:
        # Route the specific IP to the peer
        cmd = [wg_cmd, "set", interface, "peer", client_pubkey, "allowed-ips", f"{assigned_ip}/32"]
        
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=creationflags)
        logging.info(f"Successfully synced peer to {interface}")
    except (subprocess.CalledProcessError, OSError) as e:
        # Fallback to UAC prompt for Windows
        if sys.platform == "win32":
            try:
                args_joined = " ".join(f'"{str(a)}"' for a in cmd[1:])
                ps_cmd = f"Start-Process -FilePath '{cmd[0]}' -ArgumentList '{args_joined}' -Verb RunAs -WindowStyle Hidden -Wait"
                subprocess.run(["powershell", "-Command", ps_cmd], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                logging.info(f"Successfully synced peer to {interface} (via UAC elevation)")
            except Exception as inner_e:
                logging.error(f"Failed to sync peer to VPS {interface} (UAC fallback failed): {inner_e}")
        else:
            logging.error(f"Failed to sync peer to VPS {interface}: {e}")
    except Exception as e:
        logging.error(f"Exception syncing peer to VPS {interface}: {e}")
