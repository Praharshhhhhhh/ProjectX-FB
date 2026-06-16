import asyncio
import sys
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# In-memory store of applied rules keyed by device_id
# Format: _applied_rules[device_id] = {"virtual_pool": str, "real_subnet": str}
_applied_rules: Dict[int, Dict[str, str]] = {}

async def write_iptables_nat_rule(device_id: int, virtual_pool: str, real_subnet: str) -> bool:
    if sys.platform != "linux":
        logger.warning(f"write_iptables_nat_rule: non-Linux platform detected. Not applying rule for {virtual_pool} -> {real_subnet}")
        _applied_rules[device_id] = {"virtual_pool": virtual_pool, "real_subnet": real_subnet}
        return True
    
    try:
        p1 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-A", "PREROUTING", "-d", f"{virtual_pool}.0/24", "-j", "DNAT", "--to-destination", f"{real_subnet}.0",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err1 = await p1.communicate()
        if p1.returncode != 0:
            logger.error(f"Failed to add PREROUTING rule: {err1.decode()}")
            return False

        p2 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-A", "POSTROUTING", "-s", f"{real_subnet}.0/24", "-j", "SNAT", "--to-source", f"{virtual_pool}.1",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err2 = await p2.communicate()
        if p2.returncode != 0:
            logger.error(f"Failed to add POSTROUTING rule: {err2.decode()}")
            return False
            
        _applied_rules[device_id] = {"virtual_pool": virtual_pool, "real_subnet": real_subnet}
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
            "iptables", "-t", "nat", "-D", "PREROUTING", "-d", f"{virtual_pool}.0/24", "-j", "DNAT", "--to-destination", f"{real_subnet}.0",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await p1.communicate()

        p2 = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-D", "POSTROUTING", "-s", f"{real_subnet}.0/24", "-j", "SNAT", "--to-source", f"{virtual_pool}.1",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await p2.communicate()

        _applied_rules.pop(device_id, None)
        return True
    except Exception as e:
        logger.error(f"remove_iptables_nat_rule exception: {e}")
        return False
