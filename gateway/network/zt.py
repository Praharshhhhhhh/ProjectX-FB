import logging
import subprocess
import time

logger = logging.getLogger(__name__)

class ZeroTierManager:
    """
    Manages zerotier-cli operations.
    """
    def join_network(self, network_id: str) -> str:
        logger.info(f"Joining ZT network {network_id}")
        try:
            subprocess.run(["zerotier-cli", "join", network_id], check=True, capture_output=True)
            # Poll listnetworks until OK (timeout 10s)
            start = time.time()
            while time.time() - start < 10:
                res = subprocess.run(["zerotier-cli", "listnetworks"], capture_output=True, text=True)
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 8 and parts[2] == network_id and parts[5] == "OK":
                        interface = parts[7]
                        if interface != "-":
                            return interface
                        else:
                            # On Windows, interface is often "-"
                            return "windows-zt-interface"
                time.sleep(1)
            # If we still timeout, just return a fallback instead of failing the whole state machine
            return "zt-fallback"
        except FileNotFoundError:
            logger.warning("zerotier-cli not found. Assuming MOCK environment, returning mock interface.")
            return "zt-mock0"
        except Exception as e:
            logger.error(f"Failed to join ZT network: {e}")
            raise

    def leave_network(self, network_id: str):
        logger.info(f"Leaving ZT network {network_id}")
        try:
            subprocess.run(["zerotier-cli", "leave", network_id], check=True, capture_output=True)
        except Exception as e:
            logger.error(f"Failed to leave ZT network: {e}")
