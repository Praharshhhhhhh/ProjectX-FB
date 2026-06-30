import threading
import time
import logging
from PyQt6.QtCore import QObject, pyqtSignal

from services.api_client import api
from services.wireguard_local import wireguard_local

logger = logging.getLogger(__name__)

class TunnelManager(QObject):
    """
    Manages the desktop WireGuard connection lifecycle:
    - Periodic Heartbeats (every 30s)
    - Handshake Monitoring (checking if connection is stale)
    - Reconnect logic with exponential backoff (5s, 10s, 20s, 40s, max 60s)
    """
    status_changed = pyqtSignal(str) # Emits state: "Disconnected", "Provisioning", "Connected", "Stale", "Reconnecting", "Failed"

    def __init__(self):
        super().__init__()
        self._running = False
        self._thread = None
        self.state = "Disconnected"
        self._wg_ip = None
        self._endpoint = None
        self._gateway_pubkey = None
        self._allowed_ips = []
        self._public_key = None
        self._device_name = None

    def _set_state(self, state: str):
        if self.state != state:
            self.state = state
            self.status_changed.emit(state)
            logger.info(f"TunnelManager state changed -> {state}")

    def start(self, device_name: str):
        if self._running:
            return
        
        self._device_name = device_name
        self._running = True
        self._set_state("Provisioning")
        
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._set_state("Disconnected")
        if self._public_key:
            try:
                api.disconnect_desktop(self._public_key)
            except Exception as e:
                logger.error(f"Failed to notify disconnect: {e}")
        wireguard_local.stop_tunnel()
        # Wait a moment for thread to exit, but don't block main UI thread too long
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def rotate_keys(self):
        """
        Rotates keys and triggers an immediate reconnect.
        """
        was_running = self._running
        if was_running:
            self.stop()
            # Wait for true stop
            time.sleep(1)
            
        wireguard_local.rotate_keys()
        
        if was_running:
            self.start(self._device_name)

    def _provision(self):
        try:
            public_key, private_key = wireguard_local.generate_or_load_keys()
            self._public_key = public_key
            
            # Register with backend
            api.register_desktop(self._public_key, self._device_name)
            
            # Fetch config
            config = api.get_desktop_config()
            self._wg_ip = config["wg_ip"]
            self._endpoint = config["endpoint"]
            self._gateway_pubkey = config["gateway_pubkey"]
            self._allowed_ips = config["allowed_ips"]
            
            # Start interface
            wireguard_local.start_tunnel(self._wg_ip, self._endpoint, self._gateway_pubkey, self._allowed_ips)
            self._set_state("Connected")
            return True
        except Exception as e:
            logger.error(f"Provisioning failed: {e}")
            self._set_state("Failed")
            return False

    def _loop(self):
        # 1. Initial Provisioning
        backoff = 5
        while self._running and self.state in ("Provisioning", "Failed"):
            if self._provision():
                backoff = 5 # Reset backoff
                break
            # Wait with backoff before retry
            logger.info(f"Retrying provisioning in {backoff}s...")
            for _ in range(backoff):
                if not self._running:
                    return
                time.sleep(1)
            backoff = min(backoff * 2, 60)
            
        # 2. Steady State loop (Heartbeats & Monitor)
        heartbeat_timer = 0
        while self._running:
            # Sleep in 1s increments to remain responsive to stop()
            time.sleep(1)
            heartbeat_timer += 1
            
            if not self._running:
                break
                
            # Send heartbeat every 30s
            if heartbeat_timer >= 30:
                heartbeat_timer = 0
                if self._public_key:
                    try:
                        api.heartbeat_desktop(self._public_key)
                    except Exception as e:
                        logger.warning(f"Heartbeat failed: {e}")
            
            # Check handshake age
            age = wireguard_local.get_handshake_age()
            if age > 120:
                self._set_state("Stale")
                logger.warning(f"Handshake stale ({age}s). Reconnecting...")
                self._set_state("Reconnecting")
                
                reconnect_backoff = 5
                while self._running and self.state == "Reconnecting":
                    try:
                        wireguard_local.start_tunnel(self._wg_ip, self._endpoint, self._gateway_pubkey, self._allowed_ips)
                        # Wait a few seconds and re-check age
                        time.sleep(5)
                        if wireguard_local.get_handshake_age() <= 30:
                            self._set_state("Connected")
                            break
                        else:
                            raise Exception("Handshake still stale after reconnect")
                    except Exception as e:
                        logger.error(f"Reconnect failed: {e}")
                        for _ in range(reconnect_backoff):
                            if not self._running: return
                            time.sleep(1)
                        reconnect_backoff = min(reconnect_backoff * 2, 60)

tunnel_manager = TunnelManager()
