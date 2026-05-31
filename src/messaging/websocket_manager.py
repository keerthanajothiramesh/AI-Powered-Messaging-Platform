import json
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
from src.common.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.group_connections: Dict[str, Set[str]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info("ws_connected", user_id=user_id, total=len(self.active_connections))

    def disconnect(self, user_id: str) -> None:
        self.active_connections.pop(user_id, None)
        for group_id in list(self.group_connections.keys()):
            self.group_connections[group_id].discard(user_id)
        logger.info("ws_disconnected", user_id=user_id, total=len(self.active_connections))

    def join_group(self, user_id: str, group_id: str) -> None:
        if group_id not in self.group_connections:
            self.group_connections[group_id] = set()
        self.group_connections[group_id].add(user_id)

    def leave_group(self, user_id: str, group_id: str) -> None:
        if group_id in self.group_connections:
            self.group_connections[group_id].discard(user_id)

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception as e:
                logger.warning("ws_send_failed", user_id=user_id, error=str(e))
                self.disconnect(user_id)
        return False

    async def broadcast_to_group(
        self, group_id: str, message: dict, exclude_user: Optional[str] = None
    ) -> List[str]:
        members = self.group_connections.get(group_id, set())
        delivered_to = []
        for user_id in members:
            if user_id == exclude_user:
                continue
            sent = await self.send_to_user(user_id, message)
            if sent:
                delivered_to.append(user_id)
        return delivered_to

    async def broadcast_to_all(self, message: dict, exclude_user: Optional[str] = None) -> None:
        for uid in list(self.active_connections.keys()):
            if uid == exclude_user:
                continue
            await self.send_to_user(uid, message)

    def get_online_users(self) -> List[str]:
        return list(self.active_connections.keys())

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections


_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
