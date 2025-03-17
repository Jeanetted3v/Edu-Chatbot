from fastapi import WebSocket
import logging
from typing import Dict, List
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(
        self, websocket: WebSocket, session_id: str, client_type: str
    ):
        await websocket.accept()
        websocket.scope["client_type"] = client_type  
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                if connection.client_state != WebSocketState.DISCONNECTED:
                    await connection.send_json(message)


manager = ConnectionManager()