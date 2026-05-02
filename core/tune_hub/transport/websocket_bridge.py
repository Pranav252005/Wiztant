"""WebSocket-based Desktop bridge implementation."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from .abstract import DesktopBridge


class WebSocketBridge(DesktopBridge):
    """
    WebSocket bridge for Desktop 1 ↔ Desktop 2 communication.

    Uses Python websockets library for async bidirectional communication.
    """

    def __init__(self, uri: str = "ws://localhost:9120/tunehub") -> None:
        self.uri = uri
        self._ws: Any = None
        self._subscriptions: Dict[str, Callable] = {}
        self._connected = False

    async def connect(self) -> bool:
        if not WEBSOCKETS_AVAILABLE:
            return False
        try:
            self._ws = await websockets.connect(self.uri)
            self._connected = True
            asyncio.create_task(self._receive_loop())
            return True
        except Exception:
            return False

    async def publish(self, message: Any, target: str) -> bool:
        if not self._connected or not self._ws:
            return False
        try:
            envelope = {"target": target, "payload": message}
            await self._ws.send(json.dumps(envelope))
            return True
        except Exception:
            return False

    async def subscribe(self, message_type: str, handler: Callable) -> str:
        sub_id = f"sub_{message_type}_{id(handler)}"
        self._subscriptions[sub_id] = handler
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    async def disconnect(self) -> bool:
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        return True

    async def _receive_loop(self) -> None:
        if not self._ws:
            return
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    for handler in self._subscriptions.values():
                        asyncio.create_task(handler(data))
                except json.JSONDecodeError:
                    continue
        except Exception:
            self._connected = False
