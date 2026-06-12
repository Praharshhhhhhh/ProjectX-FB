import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread
# pyrefly: ignore [missing-import]
import websocket

class WebSocketWorker(QThread):
    message_received = pyqtSignal(dict)
    
    def __init__(self, url: str, token: str):
        super().__init__()
        self.url = f"{url}?token={token}"
        self.ws = None
        self._running = True

    def run(self):
        while self._running:
            self.ws = websocket.WebSocketApp(
                self.url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self.ws.run_forever(ping_interval=20, ping_timeout=10)
            
            if self._running:
                # Reconnect backoff
                time.sleep(3)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except Exception as e:
            print("WS Message Parse Error:", e)

    def _on_error(self, ws, error):
        print("WS Error:", error)

    def _on_close(self, ws, close_status_code, close_msg):
        pass

    def stop(self):
        self._running = False
        if self.ws:
            self.ws.close()
        self.quit()
        self.wait()

class WsClient(QObject):
    # Signals for the UI to listen to
    device_updated = pyqtSignal(dict)
    device_removed = pyqtSignal(int)
    sync_toggle_received = pyqtSignal(int, str, bool)
    user_updated = pyqtSignal()
    lan_device_renamed = pyqtSignal(int, int, str)

    def __init__(self):
        super().__init__()
        self.worker = None

    def connect_ws(self, base_url: str, token: str):
        # Base url is typically http://... so replace with ws://
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws"
        
        self.disconnect_ws()
        self.worker = WebSocketWorker(ws_url, token)
        self.worker.message_received.connect(self._handle_message)
        self.worker.start()

    def disconnect_ws(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def _handle_message(self, payload: dict):
        event = payload.get("event")
        if event == "device_updated":
            self.device_updated.emit(payload.get("device", {}))
        elif event == "device_removed":
            self.device_removed.emit(payload.get("device_id"))
        elif event == "sync_toggle":
            self.sync_toggle_received.emit(
                payload.get("device_id"),
                payload.get("network_id"),
                payload.get("connect")
            )
        elif event == "user_updated":
            self.user_updated.emit()
        elif event == "lan_device_renamed":
            self.lan_device_renamed.emit(
                payload.get("device_id"),
                payload.get("lan_device_id"),
                payload.get("new_name")
            )

# Global singleton
ws_client = WsClient()
