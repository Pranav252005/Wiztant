"""Quality judgment system for Tune Hub."""

from __future__ import annotations

from .judge import BaseJudge, RandomJudge

__all__ = ["BaseJudge", "RandomJudge"]
