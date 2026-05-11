"""
Minimal credit tracker for Tune Hub.
Stub implementation — returns zero balances until credit billing is wired.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class CreditBalance:
    user_id: str
    available: int = 0
    consumed: int = 0
    reserved: int = 0


class CreditTracker:
    """In-memory stub credit tracker."""

    def __init__(self) -> None:
        self._balances: Dict[str, CreditBalance] = {}

    def get_balance(self, user_id: str) -> CreditBalance:
        if user_id not in self._balances:
            self._balances[user_id] = CreditBalance(user_id=user_id)
        return self._balances[user_id]

    def reserve(self, user_id: str, amount: int) -> bool:
        bal = self.get_balance(user_id)
        if bal.available - bal.reserved < amount:
            return False
        bal.reserved += amount
        return True

    def consume(self, user_id: str, amount: int) -> None:
        bal = self.get_balance(user_id)
        bal.consumed += amount
        bal.reserved = max(0, bal.reserved - amount)

    def refund(self, user_id: str, amount: int) -> None:
        bal = self.get_balance(user_id)
        bal.consumed = max(0, bal.consumed - amount)
        bal.available += amount

    def grant(self, user_id: str, amount: int) -> None:
        bal = self.get_balance(user_id)
        bal.available += amount
