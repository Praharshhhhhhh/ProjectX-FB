import asyncio
import sys
import logging
from typing import Dict

logger = logging.getLogger(__name__)

import json
import os

NAT_STATE_FILE = os.environ.get(
    "NAT_STATE_FILE",
    os.path.join(os.path.expanduser("~"), ".projectx", "nat_state.json")
)

def _load_state() -> Dict[int, Dict[str, str]]:
    if os.path.exists(NAT_STATE_FILE):
        try:
            with open(NAT_STATE_FILE, "r") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load nat state: {e}")
    return {}

def _save_state(state: Dict[int, Dict[str, str]]):
    try:
        os.makedirs(os.path.dirname(NAT_STATE_FILE), exist_ok=True)
        with open(NAT_STATE_FILE, "w") as f:
            json.dump({str(k): v for k, v in state.items()}, f)
    except Exception as e:
        logger.error(f"Failed to save nat state: {e}")

# In-memory store of applied rules keyed by device_id
# Format: _applied_rules[device_id] = {"virtual_pool": str, "real_subnet": str}
_applied_rules: Dict[int, Dict[str, str]] = _load_state()

async def write_iptables_nat_rule(device_id: int, virtual_pool: str, real_subnet: str, gateway_ip: str) -> bool:
    if sys.platform != "linux":
        logger.warning(f"write_iptables_nat_rule: non-Linux platform detected. Not applying rule for {virtual_pool} -> {real_subnet}")
        _applied_rules[device_id] = {
            "virtual_pool": virtual_pool,
            "real_subnet": real_subnet,
            "gateway_ip": gateway_ip or f"{real_subnet}.1",
        }
        return True
    
    try:
        p1 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-d", f"{virtual_pool}.0/24",
            "-j", "NETMAP",
            "--to", f"{real_subnet}.0/24",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err1 = await p1.communicate()
        if p1.returncode != 0:
            logger.error(f"Failed to add PREROUTING rule: {err1.decode()}")
            return False

        p2 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-A", "POSTROUTING", "-s", f"{real_subnet}.0/24", "-j", "NETMAP", "--to", f"{virtual_pool}.0/24",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err2 = await p2.communicate()
        if p2.returncode != 0:
            logger.error(f"Failed to add POSTROUTING rule: {err2.decode()}")
            return False
            
        _applied_rules[device_id] = {
            "virtual_pool": virtual_pool,
            "real_subnet": real_subnet,
            "gateway_ip": gateway_ip or f"{real_subnet}.1",
        }
        _save_state(_applied_rules)
        return True
    except Exception as e:
        logger.error(f"write_iptables_nat_rule exception: {e}")
        return False

async def remove_iptables_nat_rule(device_id: int) -> bool:
    rule = _applied_rules.get(device_id)
    if not rule:
        return True
        
    virtual_pool = rule["virtual_pool"]
    real_subnet = rule["real_subnet"]

    if sys.platform != "linux":
        logger.warning(f"remove_iptables_nat_rule: non-Linux platform detected. Not removing rule for {virtual_pool} -> {real_subnet}")
        _applied_rules.pop(device_id, None)
        return True

    try:
        p1 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-D", "PREROUTING", "-d", f"{virtual_pool}.0/24", "-j", "NETMAP", "--to", f"{real_subnet}.0/24",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await p1.communicate()

        p2 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-D", "POSTROUTING", "-s", f"{real_subnet}.0/24", "-j", "NETMAP", "--to", f"{virtual_pool}.0/24",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await p2.communicate()

        _applied_rules.pop(device_id, None)
        _save_state(_applied_rules)
        return True
    except Exception as e:
        logger.error(f"remove_iptables_nat_rule exception: {e}")
        return False
