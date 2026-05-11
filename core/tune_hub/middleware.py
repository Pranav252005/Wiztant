"""Tune Application Middleware — event router for real-time tune injection.

Intercepts feature trigger events, resolves applicable tunes from TuneHub,
and injects learned parameters into feature input before execution.

Latency budget:
- Tune resolution: < 50ms (P99)
- Tune application: < 10ms
- Total overhead: < 60ms
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .base import TuneStatus
from .guardrails import TuneBoundaryGuard, TuneBoundaryViolation
from .orchestrator import TuneHub

logger = logging.getLogger(__name__)


class TuneEvent:
    """Feature trigger event for tune resolution."""

    def __init__(
        self,
        user_id: str,
        feature_name: str,
        task: str,
        feature_input: Dict[str, Any],
        timestamp: Optional[float] = None,
    ):
        self.user_id = user_id
        self.feature_name = feature_name
        self.task = task
        self.feature_input = feature_input
        self.timestamp = timestamp or time.time()
        self.tune_applied = False
        self.tune_id: Optional[str] = None
        self.latency_ms = 0.0


class TuneApplicationMiddleware:
    """
    Middleware that resolves and applies tunes on every feature trigger.

    DESIGN DECISION: This is intentionally thin. It delegates to TuneHub.resolve_tune()
    and does not cache — TuneHub's storage layer handles caching (SQLite + in-memory).
    """

    _enabled: bool = True

    def __init__(self, tune_hub: TuneHub) -> None:
        self.tune_hub = tune_hub
        self._handlers: Dict[str, List[Callable[[TuneEvent], None]]] = {}
        self._fallback_enabled = True

    def register_handler(
        self, feature_name: str, handler: Callable[[TuneEvent], None]
    ) -> None:
        """Register a post-processing handler for a feature."""
        if feature_name not in self._handlers:
            self._handlers[feature_name] = []
        self._handlers[feature_name].append(handler)

    def unregister_handler(
        self, feature_name: str, handler: Callable[[TuneEvent], None]
    ) -> None:
        """Unregister a handler."""
        if feature_name in self._handlers:
            self._handlers[feature_name] = [
                h for h in self._handlers[feature_name] if h != handler
            ]

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def apply(
        self,
        user_id: str,
        feature_name: str,
        task: str,
        feature_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve and apply tune for a feature trigger.

        Returns the (possibly modified) feature_input with tune parameters injected.
        """
        if not self._enabled:
            return feature_input

        # Deep copy so the caller's original dict is never mutated
        immutable_input = TuneBoundaryGuard.ensure_immutable_input(feature_input)

        event = TuneEvent(
            user_id=user_id,
            feature_name=feature_name,
            task=task,
            feature_input=immutable_input,
        )

        start = time.perf_counter()
        tuned_input = immutable_input
        try:
            tuned_input = self.tune_hub.resolve_tune(
                user_id=user_id,
                feature_name=feature_name,
                task=task,
                feature_input=immutable_input,
            )
        except TuneBoundaryViolation as exc:
            logger.warning(
                "Tune boundary violation for user=%s feature=%s: %s",
                user_id,
                feature_name,
                exc,
            )
            if not self._fallback_enabled:
                raise
            tuned_input = immutable_input
        except Exception:
            logger.exception(
                "Tune resolution failed for user=%s feature=%s",
                user_id,
                feature_name,
            )
            if not self._fallback_enabled:
                raise
            tuned_input = immutable_input

        elapsed_ms = (time.perf_counter() - start) * 1000
        event.latency_ms = elapsed_ms
        event.feature_input = tuned_input

        # Track if a tune was applied
        if tuned_input.get("tune_id") is not None:
            event.tune_applied = True
            event.tune_id = tuned_input["tune_id"]

        # Call post-processing handlers
        for handler in self._handlers.get(feature_name, []):
            try:
                handler(event)
            except Exception:
                pass

        return tuned_input

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Return tune application statistics for a user."""
        tunes = self.tune_hub.list_tunes(user_id)
        active = [t for t in tunes if t.status == TuneStatus.DEPLOYED]
        return {
            "total_tunes": len(tunes),
            "active_tunes": len(active),
            "features_with_tunes": list(set(t.feature_name for t in active)),
        }

    def enable_fallback(self) -> None:
        self._fallback_enabled = True

    def disable_fallback(self) -> None:
        self._fallback_enabled = False
