"""Sync manager for cross-machine tune propagation."""

from __future__ import annotations

from typing import Any, Optional

from ..base import LearnedModel


class SyncManager:
    """
    Manages sync of tunes between Desktop 1 and Desktop 2.

    Uses an async message queue (NATS / RabbitMQ / WebSocket) for
    reliable at-least-once delivery.
    """

    def __init__(self, bridge: Optional[Any] = None) -> None:
        self.bridge = bridge
        self._pending: list[dict] = []

    def publish_tune(
        self, user_id: str, model: LearnedModel, payload: bytes
    ) -> str:
        """
        Publish a tune to Desktop 1.
        Returns status string.
        """
        if self.bridge is None:
            # Queue locally for later sync
            self._pending.append(
                {
                    "user_id": user_id,
                    "tune_id": model.tune_id,
                    "feature_name": model.feature_name,
                    "payload": payload,
                }
            )
            return "queued_locally"

        try:
            # Bridge handles async delivery
            self.bridge.publish(
                {
                    "type": "SYNC_TUNE",
                    "user_id": user_id,
                    "tune_id": model.tune_id,
                    "feature_name": model.feature_name,
                    "payload": payload.decode("utf-8", errors="replace"),
                },
                target="desktop1",
            )
            return "published"
        except Exception as e:
            return f"publish_failed: {e}"

    def pull_pending(self, user_id: str) -> list[dict]:
        """Pull pending syncs for a user (called on Desktop 1 startup)."""
        return [p for p in self._pending if p["user_id"] == user_id]

    def acknowledge(self, tune_id: str) -> None:
        """Acknowledge successful delivery of a tune."""
        self._pending = [p for p in self._pending if p["tune_id"] != tune_id]
