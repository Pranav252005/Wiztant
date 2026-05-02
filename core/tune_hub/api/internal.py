"""
Internal API protocols for Tune Hub — in-process tuner interfaces.

These are Python protocols / abstract classes used when Tune Hub
runs inside the same process as the feature code (Desktop 1 mode).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class ITunerPlugin(Protocol):
    """Protocol that all tuner plugins must satisfy."""

    @property
    def feature_name(self) -> str: ...

    def estimate_complexity(
        self, task: str, context: Optional[Dict] = None
    ) -> Any: ...

    def learn(
        self,
        task: str,
        budget: Any,
        context: Optional[Dict[str, Any]] = None,
        judge: Optional[Any] = None,
    ) -> Any: ...

    def validate(
        self,
        model: Any,
        hold_out_tasks: Optional[List[str]] = None,
        judge: Optional[Any] = None,
    ) -> bool: ...

    def deploy(self, model: Any) -> Dict[str, Any]: ...

    def apply(
        self, model: Any, feature_input: Dict[str, Any]
    ) -> Dict[str, Any]: ...

    def get_default_config(self, task: str) -> Dict[str, Any]: ...
