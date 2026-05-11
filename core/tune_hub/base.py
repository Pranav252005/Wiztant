"""
Core dataclasses, enums, and exceptions for Tune Hub.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# =============================================================
#  ENUMS
# =============================================================


class ComplexityLevel(Enum):
    """Tune complexity tiers."""

    LOW = auto()      # Free tier eligible
    MEDIUM = auto()   # Pro tier eligible
    HIGH = auto()     # Power tier eligible


class TuneStatus(Enum):
    """Lifecycle status of a tune."""

    DRAFT = auto()                 # Learning in progress
    PENDING_VALIDATION = auto()
    VALIDATED = auto()             # Ready for deployment
    DEPLOYED = auto()              # Active on Desktop 1
    ARCHIVED = auto()              # Superseded by newer version
    FAILED = auto()                # Validation failed


# =============================================================
#  EXCEPTIONS
# =============================================================


class ValidationError(Exception):
    """Raised when a learned model fails validation."""

    pass


class InsufficientCreditsError(Exception):
    """Raised when a learning session exceeds its credit budget."""

    pass


# =============================================================
#  DATA CLASSES
# =============================================================


@dataclass
class LearnedModel:
    """Generic container for any tuner's learned output."""

    tune_id: str
    feature_name: str
    task_signature: str  # Normalized task identifier (e.g., "coding_tasks")
    payload: Dict[str, Any]  # Feature-specific data
    quality_score: float  # 0.0 - 1.0
    complexity: ComplexityLevel
    status: TuneStatus = field(default_factory=lambda: TuneStatus.DRAFT)
    version: int = 1
    parent_version: Optional[int] = None  # For versioning/rollback
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_storage_format(self) -> Dict[str, Any]:
        """Serialize to persistence-friendly format."""
        return {
            "tune_id": self.tune_id,
            "feature_name": self.feature_name,
            "task_signature": self.task_signature,
            "payload": self.payload,
            "quality_score": self.quality_score,
            "complexity": self.complexity.name,
            "status": self.status.name,
            "version": self.version,
            "parent_version": self.parent_version,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_storage_format(cls, data: Dict[str, Any]) -> LearnedModel:
        """Deserialize from persistence-friendly format."""
        return cls(
            tune_id=data["tune_id"],
            feature_name=data["feature_name"],
            task_signature=data["task_signature"],
            payload=data["payload"],
            quality_score=data["quality_score"],
            complexity=ComplexityLevel[data["complexity"]],
            status=TuneStatus[data["status"]],
            version=data.get("version", 1),
            parent_version=data.get("parent_version"),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class CreditBudget:
    """Immutable credit allocation for a learning session."""

    approved: int
    consumed: int = 0
    reserved: int = 0

    def can_spend(self, amount: int) -> bool:
        return (self.consumed + self.reserved + amount) <= self.approved

    def spend(self, amount: int) -> "CreditBudget":
        if not self.can_spend(amount):
            raise InsufficientCreditsError(
                f"Requested {amount}, only {self.approved - self.consumed - self.reserved} available"
            )
        return CreditBudget(
            approved=self.approved,
            consumed=self.consumed + amount,
            reserved=self.reserved,
        )


@dataclass
class ExperimentResult:
    """Result of a single experiment iteration."""

    config: Dict[str, Any]       # The configuration tested
    output: Any                   # Raw output from the feature
    score: float                  # Quality score (0.0 - 1.0)
    credits_used: int
    iteration: int
    metadata: Dict[str, Any] = field(default_factory=dict)
