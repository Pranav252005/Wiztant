"""Free tier credit tracker — in-memory with optional JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Dict

from .abstract import CreditBalance, CreditTracker


class FreeCreditTracker(CreditTracker):
    """
    Free tier: 2,000 one-time signup bonus, non-renewing.
    Stored in-memory with optional JSON file backup.
    """

    DEFAULT_FREE_CREDITS = 2_000

    def __init__(self, persist_path: str = "data/credit_ledger.json") -> None:
        self._ledger: Dict[str, Dict[str, int]] = {}
        self._lock = Lock()
        self._persist_path = Path(persist_path)
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if self._persist_path.exists():
            with open(self._persist_path, "r", encoding="utf-8") as f:
                self._ledger = json.load(f)

    def _save(self) -> None:
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(self._ledger, f, indent=2)

    def _ensure_user(self, user_id: str) -> None:
        if user_id not in self._ledger:
            self._ledger[user_id] = {
                "available": self.DEFAULT_FREE_CREDITS,
                "consumed": 0,
                "reserved": 0,
            }

    def get_balance(self, user_id: str) -> CreditBalance:
        with self._lock:
            self._ensure_user(user_id)
            entry = self._ledger[user_id]
            return CreditBalance(
                user_id=user_id,
                available=entry["available"],
                consumed=entry["consumed"],
                reserved=entry["reserved"],
            )

    def reserve(self, user_id: str, amount: int) -> bool:
        with self._lock:
            self._ensure_user(user_id)
            entry = self._ledger[user_id]
            if entry["available"] - entry["reserved"] < amount:
                return False
            entry["reserved"] += amount
            self._save()
            return True

    def consume(self, user_id: str, amount: int) -> int:
        with self._lock:
            self._ensure_user(user_id)
            entry = self._ledger[user_id]
            # Use reserved credits first, then available
            use_reserved = min(entry["reserved"], amount)
            entry["reserved"] -= use_reserved
            entry["available"] -= amount
            entry["consumed"] += amount
            self._save()
            return entry["available"]

    def refund(self, user_id: str, amount: int) -> int:
        with self._lock:
            self._ensure_user(user_id)
            entry = self._ledger[user_id]
            refund_amount = min(amount, entry["consumed"])
            entry["available"] += refund_amount
            entry["consumed"] -= refund_amount
            self._save()
            return entry["available"]

    def grant(self, user_id: str, amount: int, reason: str) -> int:
        with self._lock:
            self._ensure_user(user_id)
            entry = self._ledger[user_id]
            entry["available"] += amount
            self._save()
            return entry["available"]
