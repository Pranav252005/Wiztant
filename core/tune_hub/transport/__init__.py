"""Transport layer for Tune Hub — Desktop bridge implementations."""

from __future__ import annotations

from .abstract import DesktopBridge
from .websocket_bridge import WebSocketBridge

__all__ = ["DesktopBridge", "WebSocketBridge"]
