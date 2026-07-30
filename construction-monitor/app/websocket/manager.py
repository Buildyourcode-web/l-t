"""
WebSocket connection manager.

Handles multiple concurrent browser connections and broadcasts
alerts to all connected clients instantly (no polling).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging_config import get_logger

logger = get_logger(__name__, "api")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """
        Broadcast a JSON message to all connected clients.
        Silently drops disconnected clients.
        """
        if not self._connections:
            return

        message = json.dumps(data)
        dead: List[WebSocket] = []

        async with self._lock:
            connections_snapshot = list(self._connections)

        for ws in connections_snapshot:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    async def broadcast_violation(
        self,
        *,
        camera_id: int,
        camera_name: str,
        track_id: str,
        violation_type: str,
        confidence: float,
        image_path: str | None,
        detected_at: str,
    ) -> None:
        """Broadcast a structured violation alert."""
        await self.broadcast(
            {
                "type": "violation",
                "camera_id": camera_id,
                "camera_name": camera_name,
                "track_id": track_id,
                "violation_type": violation_type,
                "confidence": round(confidence, 4),
                "image_path": image_path,
                "detected_at": detected_at,
                "priority": "HIGH" if violation_type == "fire" else "NORMAL",
            }
        )

    async def broadcast_camera_status(
        self,
        *,
        camera_id: int,
        camera_name: str,
        online: bool,
    ) -> None:
        """Broadcast a camera online/offline status change."""
        await self.broadcast(
            {
                "type": "camera_status",
                "camera_id": camera_id,
                "camera_name": camera_name,
                "online": online,
            }
        )

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Module-level singleton
ws_manager = ConnectionManager()
