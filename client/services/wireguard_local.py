import os
import subprocess
import logging
import socket
import keyring

logger = logging.getLogger(__name__)

import sys

if getattr(sys, 'frozen', False):
    BIN_DIR = os.path.join(sys._MEIPASS, ".bin")
else:
    BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".bin"))
    
WG_EXE = os.path.join(BIN_DIR, "wg.exe")
WIREGUARD_EXE = os.path.join(BIN_DIR, "wireguard.exe")
WINTUN_DLL = os.path.join(BIN_DIR, "wintun.dll")

def _ensure_wintun():
    if not os.path.exists(WINTUN_DLL):
        logger.info("wintun.dll missing! Downloading from official repository for standalone mode...")
        import urllib.request
        import zipfile
        import io
        try:
            url = "https://www.wintun.net/builds/wintun-0.14.1.zip"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                with zipfile.ZipFile(io.BytesIO(resp.read())) as z:
                    # Extract amd64 wintun.dll
                    with z.open('wintun/bin/amd64/wintun.dll') as zf, open(WINTUN_DLL, 'wb') as f:
                        f.write(zf.read())
            logger.info("Successfully downloaded wintun.dll")
        except Exception as e:
            logger.error(f"Failed to download wintun.dll: {e}")

class WireGuardLocal:
    """
    Manages the local WireGuard tunnel lifecycle and key storage.
    """
    def __init__(self):
        self.interface = "wg-setulink"
        # Use a secure directory to satisfy wireguard.exe DACL checks
        self.config_dir = "C:\\Windows\\Temp"
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, f"{self.interface}.conf")
        self._last_start_params = None

    def generate_or_load_keys(self) -> tuple[str, str]:
        """
        Retrieves existing public/private keys or generates them if not present.
        Private key is stored securely in the OS keyring.
        """
        public_key = keyring.get_password("setulink", "wg_public_key")
        private_key = keyring.get_password("setulink", "wg_private_key")

        if public_key and private_key:
            return public_key, private_key

        logger.info("Generating new WireGuard keypair...")
        try:
            # Generate private key
            res_priv = subprocess.run([WG_EXE, "genkey"], capture_output=True, text=True, check=True)
            private_key = res_priv.stdout.strip()

            # Generate public key from private key
            res_pub = subprocess.run([WG_EXE, "pubkey"], input=private_key, capture_output=True, text=True, check=True)
            public_key = res_pub.stdout.strip()

            # Store in OS keyring
            keyring.set_password("setulink", "wg_private_key", private_key)
            keyring.set_password("setulink", "wg_public_key", public_key)
            
            return public_key, private_key
        except Exception as e:
            logger.error(f"Failed to generate keys: {e}")
            raise

    def rotate_keys(self) -> tuple[str, str]:
        """
        Deletes the existing keypair from the keyring and generates a new one.
        """
        logger.info("Rotating WireGuard keys...")
        try:
            keyring.delete_password("setulink", "wg_public_key")
        except keyring.errors.PasswordDeleteError:
            pass
        try:
            keyring.delete_password("setulink", "wg_private_key")
        except keyring.errors.PasswordDeleteError:
            pass
            
        return self.generate_or_load_keys()

    def get_handshake_age(self) -> int:
        """
        Returns the seconds since the last handshake.
        Returns 999999 if no handshake or command fails.
        """
        try:
            res = subprocess.run([WG_EXE, "show", self.interface, "latest-handshakes"], capture_output=True, text=True)
            if res.returncode == 0:
                output = res.stdout.strip()
                if output:
                    # wg show output format: "peer_pubkey timestamp"
                    parts = output.split()
                    if len(parts) >= 2:
                        ts = int(parts[1])
                        if ts > 0:
                            import time
                            return int(time.time() - ts)
        except Exception as e:
            logger.error(f"Failed to get handshake age: {e}")
        return 999999

    def start_tunnel(self, wg_ip: str, endpoint: str, gateway_pubkey: str, allowed_ips: list[str]):
        """
        Writes configuration temporarily, installs/starts service if not present,
        and uses wg.exe to configure/sync peers.
        """
        _ensure_wintun()
        self._last_start_params = (wg_ip, endpoint, gateway_pubkey, allowed_ips)
        _, private_key = self.generate_or_load_keys()
        
        # Build WireGuard configuration
        allowed_ips_str = ", ".join(allowed_ips) if allowed_ips else "127.0.0.1/32"
        conf_content = f"""[Interface]
PrivateKey = {private_key}
Address = {wg_ip}/24

[Peer]
PublicKey = {gateway_pubkey}
Endpoint = {endpoint}
AllowedIPs = {allowed_ips_str}
PersistentKeepalive = 25
"""

        try:
            # 1. Write config to secure directory
            with open(self.config_path, "w") as f:
                f.write(conf_content)
                
            # Restrict permissions on Windows (if needed, but local write is usually okay)
            
            # 2. Check if the tunnel service is already installed
            # wireguard.exe /installtunnelservice config_path
            # We check if interface exists
            res_show = subprocess.run([WG_EXE, "show", self.interface], capture_output=True)
            if res_show.returncode != 0:
                logger.info("Installing WireGuard tunnel service...")
                # Note: wireguard.exe requires admin/elevated privileges to install service.
                subprocess.run([WIREGUARD_EXE, "/uninstalltunnelservice", self.interface], capture_output=True)
                subprocess.run([WIREGUARD_EXE, "/installtunnelservice", self.config_path], check=True)
            else:
                logger.info("Syncing peer configuration...")
                # Interface exists; update config dynamically via wg.exe syncconf
                # We need to translate config to setconf format or call syncconf if supported.
                # wg.exe setconf expects a file.
                subprocess.run([WG_EXE, "setconf", self.interface, self.config_path], check=True)

        except Exception as e:
            logger.error(f"Failed to start/sync tunnel: {e}")
            raise
        finally:
            # Delete config immediately after load to protect private key
            # if os.path.exists(self.config_path):
            #     try:
            #         os.remove(self.config_path)
            #     except Exception:
            #         pass

    def stop_tunnel(self):
        """
        Stops and uninstalls the WireGuard service.
        """
        self._last_start_params = None
        logger.info("Uninstalling WireGuard tunnel service...")
        try:
            subprocess.run([WIREGUARD_EXE, "/uninstalltunnelservice", self.interface], check=True)
        except Exception as e:
            logger.error(f"Failed to uninstall tunnel: {e}")

    def reconnect_if_stale(self):
        """
        Checks handshake and triggers reconnect if stale.
        """
        if not self._last_start_params:
            return
        age = self.get_handshake_age()
        logger.info(f"Checking handshake age: {age}s")
        if age > 30:
            logger.info("Handshake is stale. Reconnecting WireGuard tunnel...")
            self.start_tunnel(*self._last_start_params)

wireguard_local = WireGuardLocal()
