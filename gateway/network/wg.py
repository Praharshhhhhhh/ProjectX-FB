import logging
import subprocess

logger = logging.getLogger(__name__)

class WireGuardManager:
    """
    Manages wg-setulink interface.
    """
    def ensure_interface(self):
        logger.info("Ensuring wg-setulink interface exists and is up.")
        try:
            # Check if it exists
            res = subprocess.run(["ip", "link", "show", "wg-setulink"], capture_output=True)
            if res.returncode != 0:
                subprocess.run(["ip", "link", "add", "dev", "wg-setulink", "type", "wireguard"], check=True)
                subprocess.run(["ip", "address", "add", "10.200.0.1/24", "dev", "wg-setulink"], check=True)
            # Ensure it is up
            subprocess.run(["ip", "link", "set", "up", "dev", "wg-setulink"], check=True)
        except FileNotFoundError:
            logger.warning("ip/wg commands not found. Assuming Windows mock environment.")
        except Exception as e:
            logger.error(f"Failed to ensure wg-setulink interface: {e}")

    def list_peers(self) -> dict:
        """Returns a dict mapping public_key to a list of allowed IPs."""
        try:
            res = subprocess.run(["wg", "show", "wg-setulink", "dump"], capture_output=True, text=True, check=True)
            lines = res.stdout.strip().split("\n")
            if len(lines) <= 1:
                return {} # First line is interface info
            
            peers = {}
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) >= 4:
                    pubkey = parts[0]
                    allowed_ips = parts[3].split(",")
                    peers[pubkey] = allowed_ips
            return peers
        except FileNotFoundError:
            logger.warning("wg not found. Mocking list_peers")
            return {}
        except Exception as e:
            logger.error(f"Failed to list wg peers: {e}")
            return {}

    def ensure_peer(self, public_key: str, allowed_ips: str):
        """Idempotently adds or updates a peer."""
        logger.info(f"Ensuring WG peer {public_key} with IPs {allowed_ips}")
        try:
            subprocess.run(
                ["wg", "set", "wg-setulink", "peer", public_key, "allowed-ips", allowed_ips],
                check=True
            )
        except FileNotFoundError:
            logger.warning(f"wg not found. Mocking ensure_peer for {public_key}")
        except Exception as e:
            logger.error(f"Failed to ensure peer {public_key}: {e}")
            raise

    def remove_peer(self, public_key: str):
        """Removes a peer."""
        logger.info(f"Removing WG peer {public_key}")
        try:
            subprocess.run(["wg", "set", "wg-setulink", "peer", public_key, "remove"], check=True)
        except FileNotFoundError:
            logger.warning(f"wg not found. Mocking remove_peer for {public_key}")
        except Exception as e:
            logger.error(f"Failed to remove peer {public_key}: {e}")
            raise

    def reconcile_peers(self, expected_peers: dict):
        """
        Takes a dict of {public_key: allowed_ips} and syncs the WG interface.
        """
        current_peers = self.list_peers()
        
        # Remove peers that shouldn't be there
        for pubkey in current_peers.keys():
            if pubkey not in expected_peers:
                self.remove_peer(pubkey)
                
        # Add/update expected peers
        for pubkey, allowed_ips in expected_peers.items():
            current_ips = current_peers.get(pubkey, [])
            # Simple check: if allowed IPs don't perfectly match
            # wg show dump outputs "10.200.0.2/32" usually
            if not current_ips or allowed_ips not in current_ips:
                self.ensure_peer(pubkey, allowed_ips)

    def spawn_router_interface(self, registry_id: int, router_pubkey: str, listen_port: int):
        ifname = f"wg-r{registry_id}"
        logger.info(f"Spawning dedicated WG interface {ifname} on port {listen_port}")
        try:
            # Check if it exists
            res = subprocess.run(["ip", "link", "show", ifname], capture_output=True)
            if res.returncode != 0:
                subprocess.run(["ip", "link", "add", "dev", ifname, "type", "wireguard"], check=True)
                
            # Attempt to configure wg
            try:
                subprocess.run(["wg", "set", ifname, "listen-port", str(listen_port)], check=True)
                privkey_path = "/etc/wireguard/privatekey"
                if __import__('os').path.exists(privkey_path):
                    subprocess.run(["wg", "set", ifname, "private-key", privkey_path], check=True)
            except Exception as e:
                logger.warning(f"Could not configure wg keys/ports (expected on Windows): {e}")

            subprocess.run(["ip", "link", "set", "up", "dev", ifname], check=True)
            
            try:
                subprocess.run(["wg", "set", ifname, "peer", router_pubkey, "allowed-ips", "0.0.0.0/0"], check=True)
            except Exception as e:
                logger.warning(f"Could not set wg peer (expected on Windows): {e}")
                
            return ifname
        except Exception as e:
            logger.error(f"Failed to spawn {ifname}: {e}")
            raise

    def remove_router_interface(self, registry_id: int):
        ifname = f"wg-r{registry_id}"
        logger.info(f"Removing WG interface {ifname}")
        try:
            subprocess.run(["ip", "link", "del", "dev", ifname], check=True)
        except Exception as e:
            logger.error(f"Failed to remove {ifname}: {e}")
