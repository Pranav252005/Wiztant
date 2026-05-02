"""
Convenience factory for creating TuneHub instances based on user tier.
"""

from __future__ import annotations

from typing import Optional

from .credit_system.free_tracker import FreeCreditTracker
from .credit_system.pro_tracker import ProCreditTracker
from .orchestrator import TuneHub
from .quality.judge import BaseJudge, SimpleJudge
from .storage.sqlite_store import SQLiteTuneStore


def create_tune_hub(
    tier: str = "free",
    db_path: str = "data/tune_hub.db",
    ledger_path: str = "data/credit_ledger.json",
    judge_factory: Optional[type[BaseJudge]] = None,
    desktop_mode: str = "desktop2",
) -> TuneHub:
    """
    Factory: create a fully configured TuneHub for a given tier.

    Args:
        tier: 'free', 'pro', or 'power'
        db_path: Path to SQLite database (Free tier)
        ledger_path: Path to credit ledger JSON
        judge_factory: Quality judge class (default SimpleJudge)
        desktop_mode: 'desktop1' or 'desktop2'
    """
    storage = SQLiteTuneStore(db_path)

    if tier == "free":
        credit_tracker = FreeCreditTracker(ledger_path)
    else:
        credit_tracker = ProCreditTracker(ledger_path, tier=tier)

    return TuneHub(
        storage=storage,
        credit_tracker=credit_tracker,
        quality_judge_factory=(judge_factory or SimpleJudge),
        desktop_mode=desktop_mode,
    )
