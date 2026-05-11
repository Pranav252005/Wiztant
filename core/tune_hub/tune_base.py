"""
TuneBase abstract class — the plugin interface for all feature tuners.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Type

from .base import (
    ComplexityLevel,
    ExperimentResult,
    LearnedModel,
    TuneStatus,
    ValidationError,
)
from .guardrails import TuneBoundaryGuard, TuneBoundaryViolation


# =============================================================
#  PROTOCOLS
# =============================================================


class QualityJudge(Protocol):
    """Protocol for quality scoring backends (Claude, GPT-4, human-in-the-loop)."""

    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        """Return quality score in range [0.0, 1.0]."""
        ...


# =============================================================
#  TUNE BASE
# =============================================================


class TuneBase(ABC):
    """
    Abstract base for all feature tuners.

    Every tuner plugin MUST implement:
    - estimate_complexity(): Static analysis of task difficulty
    - learn(): The core experimentation loop
    - validate(): Verify learned model works on hold-out examples
    - deploy(): Convert model to feature-usable config
    - apply(): Desktop 1 runtime config injection
    - get_default_config(): Fallback when no tune exists

    DESIGN DECISION: TuneBase is stateless regarding the learned model.
    State flows through LearnedModel dataclass instances. This enables:
    - Easy serialization for cloud sync
    - Reproducible experiments
    - Rollback by re-instantiating old LearnedModel
    """

    # Registry for plugin discovery
    _registry: Dict[str, Type["TuneBase"]] = {}

    def __init_subclass__(cls, feature_name: str, **kwargs):
        """Auto-register subclasses by feature_name."""
        super().__init_subclass__(**kwargs)
        if not feature_name:
            raise ValueError("feature_name is required for TuneBase subclasses")
        cls._registry[feature_name] = cls
        cls._feature_name = feature_name

    @property
    def feature_name(self) -> str:
        return self._feature_name

    # ───────────────────────────────────────────────────────────────
    # PHASE 0: Static Analysis
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def estimate_complexity(
        self, task: str, context: Optional[Dict] = None
    ) -> ComplexityLevel:
        """
        Analyze the task string to determine complexity.

        Used BEFORE learning to:
        1. Check tier eligibility (Free vs Pro vs Power)
        2. Estimate credit requirements
        3. Set user expectations

        Must be FAST (< 100ms) — called synchronously on Desktop 1.
        """
        raise NotImplementedError

    # ───────────────────────────────────────────────────────────────
    # PHASE 1: Learning (runs on Desktop 2)
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def learn(
        self,
        task: str,
        budget: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        judge: Optional[QualityJudge] = None,
    ) -> LearnedModel:
        """
        Core learning loop. Runs expensive experiments on Desktop 2.

        Contract:
        - Must respect budget limit
        - Must return a LearnedModel with status DRAFT or FAILED
        - Should yield intermediate results if possible (for progress UI)
        - Is allowed to run for minutes or hours

        Template pattern: Subclasses override _experiment() and _aggregate().
        """
        raise NotImplementedError

    def _experiment(
        self,
        config: Dict[str, Any],
        task: str,
        iteration: int,
    ) -> ExperimentResult:
        """
        Run ONE experiment. Template method — subclasses override.

        Returns scored result. Called repeatedly by learn().
        """
        raise NotImplementedError

    def _aggregate(self, results: List[ExperimentResult]) -> Dict[str, Any]:
        """
        Aggregate experiment results into learned payload.

        Default: Select best-scoring config. Subclasses may override
        for weighted blending, ensemble methods, etc.
        """
        if not results:
            return {}
        best = max(results, key=lambda r: r.score)
        return {
            "best_config": best.config,
            "best_score": best.score,
            "all_results": [r.__dict__ for r in results],
            "mean_score": sum(r.score for r in results) / len(results),
        }

    # ───────────────────────────────────────────────────────────────
    # PHASE 2: Validation (runs on Desktop 2)
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def validate(
        self,
        model: LearnedModel,
        hold_out_tasks: Optional[List[str]] = None,
        judge: Optional[QualityJudge] = None,
    ) -> bool:
        """
        Validate learned model on hold-out data.

        Contract:
        - Returns True if validation passes
        - On pass, model status becomes VALIDATED
        - On fail, model status becomes FAILED
        - Must be deterministic (same input → same boolean)

        Default implementations may use:
        - k-fold cross-validation
        - LLM-as-judge on synthetic test cases
        - Human-in-the-loop verification
        """
        raise NotImplementedError

    # ───────────────────────────────────────────────────────────────
    # PHASE 3: Deployment (Desktop 2 → Desktop 1)
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        """
        Convert LearnedModel to feature-specific deployment artifact.

        Called on Desktop 2 after validation. Output is serialized
        and sent to Desktop 1 via message queue.

        Returns a deployment manifest that Desktop 1 uses to apply the tune.
        """
        raise NotImplementedError

    def prepare_sync_payload(self, model: LearnedModel) -> bytes:
        """
        Serialize model for cross-machine sync.

        Returns encrypted payload if encryption is enabled.
        """
        import json

        data = model.to_storage_format()
        return json.dumps(data, default=str).encode("utf-8")

    # ───────────────────────────────────────────────────────────────
    # RUNTIME: Tune Application (runs on Desktop 1)
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def apply(
        self,
        model: LearnedModel,
        feature_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply learned tune to a feature invocation.

        Called synchronously on Desktop 1 when a feature triggers.
        Must be FAST (< 50ms) — this is on the hot path.

        Returns modified feature_input with tune parameters injected.
        """
        raise NotImplementedError

    @abstractmethod
    def get_default_config(self, task: str) -> Dict[str, Any]:
        """
        Return default configuration when no tune exists.

        Must be FAST and deterministic. Used as fallback.
        """
        raise NotImplementedError

    # ───────────────────────────────────────────────────────────────
    # BOUNDARY SAFETY
    # ───────────────────────────────────────────────────────────────

    @abstractmethod
    def allowed_injectable_keys(self) -> frozenset[str]:
        """
        Return the set of feature_input keys this tuner is permitted to
        add or modify.  All other keys must remain untouched.
        """
        raise NotImplementedError

    def safe_apply(
        self,
        model: LearnedModel,
        feature_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Boundary-safe wrapper around apply().

        1. Deep-copies the input so the caller's dict is never mutated.
        2. Calls apply() on the copy.
        3. Validates that only allowed keys were touched.
        4. Raises TuneBoundaryViolation on violation.
        """
        original = TuneBoundaryGuard.ensure_immutable_input(feature_input)
        modified = self.apply(model, original)
        ok, reason = TuneBoundaryGuard.validate_injection(
            self.feature_name, original, modified
        )
        if not ok:
            raise TuneBoundaryViolation(reason)
        return modified

    # ───────────────────────────────────────────────────────────────
    # Utility
    # ───────────────────────────────────────────────────────────────

    @classmethod
    def get_registered_tuners(cls) -> Dict[str, Type["TuneBase"]]:
        """Return all registered tuner plugins."""
        return dict(cls._registry)

    @classmethod
    def create(cls, feature_name: str) -> "TuneBase":
        """Factory: instantiate a tuner by feature name."""
        if feature_name not in cls._registry:
            raise KeyError(f"No tuner registered for feature '{feature_name}'")
        return cls._registry[feature_name]()
