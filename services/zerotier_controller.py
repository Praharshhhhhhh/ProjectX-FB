import httpx
from typing import Optional, List
# pyrefly: ignore [missing-import]
from config import get_settings

settings = get_settings()


def _headers() -> dict:
    return {"X-ZT1-Auth": settings.ZEROTIER_CONTROLLER_TOKEN}


def _base() -> str:
    return settings.ZEROTIER_CONTROLLER_URL


async def get_network_members(network_id: str) -> List[dict]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{_base()}/controller/network/{network_id}/member", headers=_headers())
            if r.status_code == 200:
                return list(r.json().values()) if isinstance(r.json(), dict) else r.json()
    except Exception:
        pass
    return []


async def authorize_member(network_id: str, node_id: str, authorized: bool = True) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{_base()}/controller/network/{network_id}/member/{node_id}",
                json={"authorized": authorized},
                headers=_headers(),
            )
            return r.status_code == 200
    except Exception:
        return False


async def get_network(network_id: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{_base()}/controller/network/{network_id}", headers=_headers())
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


async def create_network(name: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{_base()}/controller/network",
                json={"name": name, "private": True},
                headers=_headers(),
            )
            if r.status_code == 200:
                return r.json().get("id")
    except Exception:
        pass
    return None

async def set_network_mode(network_id: str, is_layer2: bool) -> bool:
    # Note: Setting enableBroadcast toggles broadcast traffic and acts as a partial
    # L2 implementation. For true full Ethernet bridging (e.g. spanning tree,
    # non-IP traffic), the `allowEthernetBridging` flag would also need to be set
    # on the individual member level.
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{_base()}/controller/network/{network_id}",
                json={"enableBroadcast": is_layer2},
                headers=_headers(),
            )
            return r.status_code == 200
    except Exception:
        pass
    return False

async def check_member_status(network_id: str, node_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{_base()}/controller/network/{network_id}/member/{node_id}",
                headers=_headers(),
            )
            if r.status_code == 200:
                data = r.json()
                if not data.get("authorized", False):
                    return "pending"
                if data.get("lastSeen", 0) > 0:
                    import time
                    last_seen = data["lastSeen"] / 1000
                    if time.time() - last_seen < 120:
                        return "active"
                return "offline"
    except Exception:
        pass
    return "offline"
