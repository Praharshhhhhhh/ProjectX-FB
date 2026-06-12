import httpx
import os
import time
from typing import Optional
# pyrefly: ignore [missing-import]
from config import ZEROTIER_LOCAL_URL, ZEROTIER_AUTH_FILE


def _get_token() -> Optional[str]:
    # First try the global path (requires Admin)
    try:
        with open(ZEROTIER_AUTH_FILE, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, Exception):
        pass

    # Fallback to the user-level AppData path (created by ZeroTier UI on Windows)
    user_token_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ZeroTier", "authtoken.secret")
    try:
        with open(user_token_path, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, Exception):
        return None


def _headers() -> dict:
    token = _get_token()
    return {"X-ZT1-Auth": token} if token else {}


def connect(network_id: str) -> bool:
    try:
        r = httpx.post(f"{ZEROTIER_LOCAL_URL}/network/{network_id}", headers=_headers(), timeout=5)
        return r.status_code in (200, 201)
    except Exception:
        return False


_last_disconnect_time = 0


def disconnect(network_id: str) -> bool:
    global _last_disconnect_time
    _last_disconnect_time = time.time()
    try:
        r = httpx.delete(f"{ZEROTIER_LOCAL_URL}/network/{network_id}", headers=_headers(), timeout=5)
        return r.status_code in (200, 204)
    except Exception:
        return False


def get_status(network_id: str) -> str:
    global _last_disconnect_time
    if time.time() - _last_disconnect_time < 5:
        return "disconnected"
    try:
        r = httpx.get(f"{ZEROTIER_LOCAL_URL}/network/{network_id}", headers=_headers(), timeout=5)
        if r.status_code == 404:
            return "disconnected"
        data = r.json()
        zt_status = data.get("status", "")
        if zt_status == "OK":
            return "connected"
        if zt_status == "REQUESTING_CONFIGURATION":
            return "connecting"
        if zt_status == "ACCESS_DENIED":
            return "pending"
        if zt_status == "PORT_ERROR":
            return "error"
        return "connecting"
    except Exception:
        return "disconnected"


def get_all_networks() -> list:
    try:
        r = httpx.get(f"{ZEROTIER_LOCAL_URL}/network", headers=_headers(), timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

def get_node_info() -> dict:
    try:
        r = httpx.get(f"{ZEROTIER_LOCAL_URL}/status", headers=_headers(), timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def is_zerotier_running() -> bool:
    return _get_token() is not None


def get_network_ip(network_id: str) -> Optional[str]:
    try:
        r = httpx.get(f"{ZEROTIER_LOCAL_URL}/network/{network_id}", headers=_headers(), timeout=5)
        if r.status_code == 200:
            data = r.json()
            addrs = data.get("assignedAddresses", [])
            if addrs:
                return addrs[0].split("/")[0]
    except Exception:
        pass
    return None
