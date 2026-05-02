"""Abstract Desktop bridge interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class DesktopBridge(ABC):
    """Abstract interface for Desktop 1 ↔ Desktop 2 communication."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection. Returns True on success."""
        raise NotImplementedError

    @abstractmethod
    async def publish(self, message: Any, target: str) -> bool:
        """Publish a message to a target desktop."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe(
        self, message_type: str, handler: Callable
    ) -> str:
        """Subscribe to a message type. Returns subscription ID."""
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by ID."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> bool:
        """Clean disconnect."""
        raise NotImplementedError
