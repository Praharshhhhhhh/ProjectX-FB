import threading
import time
import socket
from typing import Callable, Optional


def _get_active_interface() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


class NetworkMonitor(threading.Thread):
    def __init__(self, on_change: Callable[[], None], interval: int = 5):
        super().__init__(daemon=True)
        self.on_change = on_change
        self.interval = interval
        self._last_ip: Optional[str] = None
        self._running = True

    def run(self):
        self._last_ip = _get_active_interface()
        while self._running:
            time.sleep(self.interval)
            current = _get_active_interface()
            if current != self._last_ip:
                self._last_ip = current
                try:
                    self.on_change()
                except Exception:
                    pass

    def stop(self):
        self._running = False
