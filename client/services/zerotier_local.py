import os
import logging
import subprocess
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class ZeroTierLocal:
    def _get_cli_cmd(self):
        if os.name == 'nt':
            return [r"C:\ProgramData\ZeroTier\One\zerotier-one_x64.exe", "-q"]
        return ["zerotier-cli"]

    def get_node_id(self) -> str | None:
        try:
            cmd = self._get_cli_cmd() + ["info"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Expected output: "200 info <node_id> <version> ONLINE"
            parts = res.stdout.split()
            if len(parts) >= 3 and parts[1] == "info":
                return parts[2]
            return None
        except Exception as e:
            logger.error(f"Failed to get ZeroTier node ID: {e}")
            return None

    def join_network(self, network_id: str) -> bool:
        try:
            logger.info(f"Joining ZeroTier network {network_id}...")
            if os.name == 'nt':
                # On Windows, bypass CLI issue by hitting local API
                token_path = r"C:\ProgramData\ZeroTier\One\authtoken.secret"
                if not os.path.exists(token_path):
                    logger.error("ZeroTier authtoken.secret not found")
                    return False
                    
                with open(token_path, "r") as f:
                    token = f.read().strip()
                
                req = urllib.request.Request(
                    f"http://localhost:9993/network/{network_id}",
                    data=json.dumps({}).encode('utf-8'),
                    headers={"X-ZT1-Auth": token, "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            else:
                cmd = self._get_cli_cmd() + ["join", network_id]
                subprocess.run(cmd, check=True, capture_output=True)
                return True
        except Exception as e:
            logger.error(f"Failed to join ZeroTier network: {e}")
            return False

    def is_connected(self, network_id: str) -> bool:
        try:
            cmd = self._get_cli_cmd() + ["listnetworks"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 8 and parts[2] == network_id:
                    return parts[5] == "OK"
            return False
        except Exception as e:
            logger.error(f"Failed to check ZeroTier connection: {e}")
            return False

zerotier_local = ZeroTierLocal()
