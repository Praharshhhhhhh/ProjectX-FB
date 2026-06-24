import os
import sys
import json
import time
import subprocess
from typing import Optional, Tuple
# pyrefly: ignore [missing-import]
from config import WG_INTERFACE, WG_KEY_STORAGE, WG_CONFIG_DIR

def _run_cmd(cmd: list) -> str:
    try:
        # Use CREATE_NO_WINDOW on Windows so no console pops up
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, creationflags=creationflags
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Fallback or error handling
        return ""
    except FileNotFoundError:
        # Binary not found
        return ""

def get_or_create_keypair(storage_path: str = WG_KEY_STORAGE) -> Tuple[str, str]:
    if os.path.exists(storage_path):
        try:
            with open(storage_path, "r") as f:
                data = json.load(f)
                if "private_key" in data and "public_key" in data:
                    return data["private_key"], data["public_key"]
        except Exception:
            pass

    # Generate new keypair
    priv, pub = generate_keypair()
    if priv and pub:
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "w") as f:
            json.dump({"private_key": priv, "public_key": pub}, f)
    return priv, pub

def get_bin_path(name: str) -> str:
    if sys.platform != "win32":
        return name
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, ".bin", name)

WG_CMD = get_bin_path("wg.exe")

def generate_keypair() -> Tuple[str, str]:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        priv = subprocess.run([WG_CMD, "genkey"], capture_output=True, text=True, check=True, creationflags=creationflags).stdout.strip()
        pub = subprocess.run([WG_CMD, "pubkey"], input=priv, capture_output=True, text=True, check=True, creationflags=creationflags).stdout.strip()
        return priv, pub
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "", ""

def write_config(private_key: str, assigned_ip: str, server_pubkey: str, server_endpoint: str, config_path: str) -> bool:
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {assigned_ip}/32

[Peer]
PublicKey = {server_pubkey}
Endpoint = {server_endpoint}
AllowedIPs = 10.0.0.0/8
PersistentKeepalive = 25
"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                if f.read() == config:
                    return False
        with open(config_path, "w") as f:
            f.write(config)
        return True
    except Exception:
        return False

def _run_with_elevation_fallback(cmd: list) -> bool:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(cmd, capture_output=True, check=True, creationflags=creationflags)
        return True
    except (subprocess.CalledProcessError, OSError):
        if sys.platform == "win32":
            try:
                exe = cmd[0]
                # Join arguments into a single double-quoted string to avoid PowerShell array parsing bugs
                args_joined = " ".join(f'"{str(a)}"' for a in cmd[1:])
                ps_cmd = f"Start-Process -FilePath '{exe}' -ArgumentList '{args_joined}' -Verb RunAs -WindowStyle Hidden -Wait"
                subprocess.run(["powershell", "-Command", ps_cmd], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                return True
            except Exception as e:
                print("Elevation fallback failed:", e)
                return False
        return False
    except Exception as e:
        print("Command failed:", e)
        return False

def connect(config_name_or_path: str) -> bool:
    if sys.platform == "win32":
        path = config_name_or_path
        if not path.endswith(".conf"):
            path = os.path.join(WG_CONFIG_DIR, f"{config_name_or_path}.conf")
        wg_manager = get_bin_path("wireguard.exe")
        cmd = [wg_manager, "/installtunnelservice", path]
    else:
        name = os.path.basename(config_name_or_path).replace(".conf", "")
        cmd = ["wg-quick", "up", name]
        
    return _run_with_elevation_fallback(cmd)

def disconnect(config_name: str) -> bool:
    if sys.platform == "win32":
        name = os.path.basename(config_name).replace(".conf", "")
        wg_manager = get_bin_path("wireguard.exe")
        cmd = [wg_manager, "/uninstalltunnelservice", name]
    else:
        name = os.path.basename(config_name).replace(".conf", "")
        cmd = ["wg-quick", "down", name]
        
    return _run_with_elevation_fallback(cmd)

def get_status(config_name: str) -> str:
    name = os.path.basename(config_name).replace(".conf", "")
    out = _run_cmd([WG_CMD, "show", name, "latest-handshakes"])
    if not out:
        return "disconnected"
    
    # wg show <iface> latest-handshakes output: <peer-pubkey> \t <timestamp>
    try:
        parts = out.split()
        if len(parts) >= 2:
            ts = int(parts[1])
            if ts == 0:
                return "connecting"
            if time.time() - ts < 180:
                return "connected"
            return "disconnected"
    except Exception:
        pass
    return "disconnected"

def get_node_info() -> dict:
    priv, pub = get_or_create_keypair()
    return {"address": pub}

def get_network_ip(config_name: str) -> Optional[str]:
    # We can parse `wg show <iface> endpoints` or we can just read from the conf if needed.
    # But let's read the IPs from `ip addr` or `netsh`?
    # Actually, wireguard doesn't show local IP in `wg show` directly except for allowed IPs.
    # We can read the wg configuration file or parse `ipconfig`/`ip` command.
    # Wait, reading from config file is much easier and cross platform.
    name = os.path.basename(config_name).replace(".conf", "")
    path = os.path.join(WG_CONFIG_DIR, f"{name}.conf")
    try:
        with open(path, "r") as f:
            for line in f:
                if line.strip().lower().startswith("address"):
                    # Address = 10.0.0.2/32
                    ip_part = line.split("=")[1].strip()
                    return ip_part.split("/")[0]
    except Exception:
        pass
    return None

def is_wireguard_running() -> bool:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        res = subprocess.run([WG_CMD, "show"], capture_output=True, text=True, check=True, creationflags=creationflags)
        # If output has interface, it's running
        if "interface:" in res.stdout:
            return True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_device_capability() -> dict:
    import sys
    import subprocess
    import shutil
    import os
    
    cap = {
        "kernel": "",
        "arch": "",
        "has_wireguard_kernel": False,
        "has_wireguard_userspace": False,
        "has_zerotier": False,
        "ram_mb": 0,
        "cpu_cores": os.cpu_count() or 0
    }
    
    try:
        if sys.platform != "win32":
            cap["kernel"] = subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip()
            cap["arch"] = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
            
            # Check for wireguard kernel module
            if os.path.exists("/sys/module/wireguard"):
                cap["has_wireguard_kernel"] = True
            else:
                cap["has_wireguard_kernel"] = (subprocess.run(["modprobe", "-n", "wireguard"], capture_output=True).returncode == 0)
                
            cap["has_wireguard_userspace"] = shutil.which("wireguard-go") is not None
            
            # RAM
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                cap["ram_mb"] = int(parts[1]) // 1024
                            break
            except Exception:
                pass
        else:
            # Windows
            cap["kernel"] = "Windows"
            cap["arch"] = os.environ.get("PROCESSOR_ARCHITECTURE", "")
            cap["has_wireguard_kernel"] = False
            cap["has_wireguard_userspace"] = True # WireGuard on Windows uses userspace
            
            # RAM via powershell
            try:
                mem = subprocess.run(["powershell", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty TotalVisibleMemorySize"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
                if mem:
                    cap["ram_mb"] = int(mem) // 1024
            except Exception:
                pass
                
        # ZT check
        if sys.platform == "win32":
            cap["has_zerotier"] = os.path.exists(r"C:\ProgramData\ZeroTier\One\zerotier-one.exe")
        else:
            cap["has_zerotier"] = shutil.which("zerotier-one") is not None
            
    except Exception:
        pass
        
    return cap

