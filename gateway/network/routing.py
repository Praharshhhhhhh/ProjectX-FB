import logging
import subprocess
try:
    from pyroute2 import IPRoute
    HAS_PYROUTE = True
except ImportError:
    HAS_PYROUTE = False

logger = logging.getLogger(__name__)

class RoutingManager:
    """
    Manages Linux policy routing using pyroute2 and iptables.
    """
    def __init__(self):
        if not HAS_PYROUTE:
            logger.warning("pyroute2 not installed. Routing operations will be stubbed or fail.")

    def add_policy_route(self, wg_peer_ip: str, lan_subnet: str, table_id: int, zt_interface: str, router_zt_ip: str):
        logger.info(f"Adding ip rule from {wg_peer_ip} to {lan_subnet} lookup {table_id}")
        logger.info(f"Adding ip route {lan_subnet} via {router_zt_ip} dev {zt_interface} table {table_id}")
        
        if HAS_PYROUTE:
            with IPRoute() as ipr:
                try:
                    # lookup zt interface index
                    idx = ipr.link_lookup(ifname=zt_interface)[0]
                    # add route via router's ZT IP
                    ipr.route('add', dst=lan_subnet, gateway=router_zt_ip, oif=idx, table=table_id)
                except Exception as e:
                    if 'File exists' not in str(e):
                        logger.error(f"Error adding route: {e}")
                try:
                    # add rule
                    ipr.rule('add', src=wg_peer_ip, dst=lan_subnet, table=table_id)
                except Exception as e:
                    if 'File exists' not in str(e):
                        logger.error(f"Error adding rule: {e}")

        # NAT (iptables check-before-append)
        check_cmd = ["iptables", "-t", "nat", "-C", "POSTROUTING", "-o", zt_interface, "-j", "MASQUERADE"]
        append_cmd = ["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", zt_interface, "-j", "MASQUERADE"]
        try:
            res = subprocess.run(check_cmd, capture_output=True)
            if res.returncode != 0:
                subprocess.run(append_cmd, check=True)
        except Exception as e:
            logger.error(f"Failed to add NAT rule: {e}")

    def remove_policy_route(self, wg_peer_ip: str, lan_subnet: str, table_id: int, zt_interface: str):
        logger.info(f"Removing policy route for table {table_id}")
        if HAS_PYROUTE:
            with IPRoute() as ipr:
                try:
                    ipr.rule('del', src=wg_peer_ip, dst=lan_subnet, table=table_id)
                except Exception:
                    pass
                try:
                    idx = ipr.link_lookup(ifname=zt_interface)[0]
                    ipr.route('del', dst=lan_subnet, oif=idx, table=table_id)
                except Exception:
                    pass
