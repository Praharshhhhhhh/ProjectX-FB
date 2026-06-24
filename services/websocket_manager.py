import asyncio
import json
from typing import Dict, List, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps tenant_id -> list of (user_id, WebSocket)
        self.active_connections: Dict[int, List[tuple[int, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: int, user_id: int):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = []
        self.active_connections[tenant_id].append((user_id, websocket))

    def disconnect(self, websocket: WebSocket, tenant_id: int):
        if tenant_id in self.active_connections:
            # Remove the specific websocket
            self.active_connections[tenant_id] = [
                (uid, ws) for uid, ws in self.active_connections[tenant_id] if ws != websocket
            ]
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def broadcast_to_tenant(self, tenant_id: int, message: dict):
        if tenant_id in self.active_connections:
            payload = json.dumps(message)
            # Use gather to send to all concurrently
            # Handle potential disconnection during send
            tasks = []
            for _, connection in self.active_connections[tenant_id]:
                tasks.append(self._safe_send(connection, payload))
            if tasks:
                await asyncio.gather(*tasks)

    async def broadcast_to_user(self, tenant_id: int, user_id: int, message: dict):
        if tenant_id in self.active_connections:
            payload = json.dumps(message)
            tasks = []
            for uid, connection in self.active_connections[tenant_id]:
                if uid == user_id:
                    tasks.append(self._safe_send(connection, payload))
            if tasks:
                await asyncio.gather(*tasks)

    async def _safe_send(self, websocket: WebSocket, payload: str):
        try:
            await websocket.send_text(payload)
        except Exception:
            # If the connection drops while trying to send, ignore it
            # The client's receive loop or disconnect handler will clean it up
            pass

manager = ConnectionManager()
