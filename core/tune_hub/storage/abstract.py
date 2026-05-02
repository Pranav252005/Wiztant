"""Abstract storage interface for Tune Hub."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..base import LearnedModel


class TuneStorage(ABC):
    """Abstract interface for tune persistence."""

    @abstractmethod
    def store_tune(self, user_id: str, model: LearnedModel) -> bool:
        """Persist a learned model. Returns True on success."""
        raise NotImplementedError

    @abstractmethod
    def get_tune(
        self, user_id: str, feature_name: str, task_signature: str
    ) -> Optional[LearnedModel]:
        """Retrieve the latest deployed tune matching criteria."""
        raise NotImplementedError

    @abstractmethod
    def get_tune_by_id(self, user_id: str, tune_id: str) -> Optional[LearnedModel]:
        """Retrieve a tune by its unique ID."""
        raise NotImplementedError

    @abstractmethod
    def get_tune_version(
        self, user_id: str, tune_id: str, version: int
    ) -> Optional[LearnedModel]:
        """Retrieve a specific historical version of a tune."""
        raise NotImplementedError

    @abstractmethod
    def list_tunes(
        self, user_id: str, feature_name: Optional[str] = None
    ) -> List[LearnedModel]:
        """List all tunes for a user, optionally filtered by feature."""
        raise NotImplementedError

    @abstractmethod
    def delete_tune(self, user_id: str, tune_id: str) -> bool:
        """Delete a tune. Returns True on success."""
        raise NotImplementedError

    @abstractmethod
    def count_tunes(self, user_id: str, feature_name: Optional[str] = None) -> int:
        """Count tunes for a user."""
        raise NotImplementedError
