"""Abstract credit tracker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CreditBalance:
    user_id: str
    available: int
    consumed: int = 0
    reserved: int = 0


class CreditTracker(ABC):
    """Abstract interface for credit tracking."""

    @abstractmethod
    def get_balance(self, user_id: str) -> CreditBalance:
        """Return current credit balance for user."""
        raise NotImplementedError

    @abstractmethod
    def reserve(self, user_id: str, amount: int) -> bool:
        """Reserve credits for an upcoming operation. Returns True if successful."""
        raise NotImplementedError

    @abstractmethod
    def consume(self, user_id: str, amount: int) -> int:
        """Consume reserved or available credits. Returns remaining balance."""
        raise NotImplementedError

    @abstractmethod
    def refund(self, user_id: str, amount: int) -> int:
        """Refund consumed credits. Returns new balance."""
        raise NotImplementedError

    @abstractmethod
    def grant(self, user_id: str, amount: int, reason: str) -> int:
        """Grant credits to user. Returns new balance."""
        raise NotImplementedError
