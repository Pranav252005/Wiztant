"""Pro/Power tier credit tracker — extends Free tracker with monthly grants."""

from __future__ import annotations

from .free_tracker import FreeCreditTracker


class ProCreditTracker(FreeCreditTracker):
    """
    Pro tier: 10,000/month + $5 per 1,000 additional.
    Power tier: 25,000/month + $3 per 1,000 additional.
    Extends FreeCreditTracker with monthly reset logic.
    """

    PRO_MONTHLY = 10_000
    POWER_MONTHLY = 25_000

    def __init__(
        self,
        persist_path: str = "data/credit_ledger.json",
        tier: str = "pro",
    ) -> None:
        super().__init__(persist_path)
        self._tier = tier

    def _ensure_user(self, user_id: str) -> None:
        if user_id not in self._ledger:
            grant = (
                self.POWER_MONTHLY
                if self._tier == "power"
                else self.PRO_MONTHLY
            )
            self._ledger[user_id] = {
                "available": grant,
                "consumed": 0,
                "reserved": 0,
            }
