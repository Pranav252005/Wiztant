"""Convergence checking utilities for Tune Hub learning loops.

Implements the convergence criteria defined in the tuner implementation specs:
- Quality plateau
- Acquisition function flatness
- Weight stability
- Budget exhaustion
- Auto-apply rate
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ConvergenceResult:
    """Result of a convergence check."""

    status: str
    reason: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def _std(values: List[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return float("inf")
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _mean(values: List[float]) -> float:
    """Arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


class ConvergenceChecker:
    """Stateful convergence checker for iterative learning loops."""

    def __init__(
        self,
        max_iterations: int = 12,
        quality_plateau_threshold: float = 0.05,
        quality_plateau_min: float = 0.85,
        acquisition_flat_threshold: float = 0.01,
        weight_stability_threshold: float = 0.08,
        auto_apply_rate_min: float = 0.80,
        override_rate_max: float = 0.10,
    ):
        self.max_iterations = max_iterations
        self.quality_plateau_threshold = quality_plateau_threshold
        self.quality_plateau_min = quality_plateau_min
        self.acquisition_flat_threshold = acquisition_flat_threshold
        self.weight_stability_threshold = weight_stability_threshold
        self.auto_apply_rate_min = auto_apply_rate_min
        self.override_rate_max = override_rate_max
        self._history: List[Dict[str, Any]] = []

    def record(self, observation: Dict[str, Any]) -> None:
        """Record an observation for convergence tracking."""
        self._history.append(observation)

    def check(self) -> ConvergenceResult:
        """Check convergence against all criteria."""
        recent = self._history[-5:] if len(self._history) >= 5 else self._history

        # Criterion 1: Quality plateau
        quality_scores = [obs.get("quality_score", 0.0) for obs in recent]
        if len(quality_scores) >= 3:
            std_q = _std(quality_scores)
            mean_q = _mean(quality_scores)
            if std_q < self.quality_plateau_threshold and mean_q > self.quality_plateau_min:
                return ConvergenceResult(
                    status="CONVERGED_HIGH_QUALITY",
                    reason=f"Quality plateau: mean={mean_q:.3f}, std={std_q:.3f}",
                    confidence=mean_q,
                    metadata={"mean_quality": mean_q, "std_quality": std_q},
                )

        # Criterion 2: Acquisition function flat
        acq_values = [obs.get("acquisition_value", 1.0) for obs in recent]
        if acq_values and max(acq_values) < self.acquisition_flat_threshold:
            return ConvergenceResult(
                status="CONVERGED_EXPLORATION_DONE",
                reason=f"Acquisition flat: max={max(acq_values):.4f}",
                confidence=1.0 - max(acq_values),
            )

        # Criterion 3: Weight stability
        weight_vectors = [obs.get("weights") for obs in recent if obs.get("weights")]
        if len(weight_vectors) >= 3:
            # Compute std per dimension
            dims = len(weight_vectors[0])
            stable_dims = 0
            for d in range(dims):
                dim_values = [wv[d] for wv in weight_vectors]
                if _std(dim_values) < self.weight_stability_threshold:
                    stable_dims += 1
            stability_ratio = stable_dims / dims if dims else 0
            if stability_ratio >= 0.8:
                return ConvergenceResult(
                    status="CONVERGED_WEIGHTS_STABLE",
                    reason=f"Weight stability: {stable_dims}/{dims} dimensions stable",
                    confidence=stability_ratio,
                )

        # Criterion 4: Budget exhausted
        if len(self._history) >= self.max_iterations:
            return ConvergenceResult(
                status="CONVERGED_BUDGET",
                reason=f"Max iterations ({self.max_iterations}) reached",
                confidence=_mean(quality_scores) if quality_scores else 0.0,
            )

        # Criterion 5: Auto-apply rate (dictation-specific)
        auto_applied = sum(1 for obs in recent if obs.get("auto_applied"))
        overrides = sum(1 for obs in recent if obs.get("user_override"))
        total = len(recent)
        if total >= 5:
            auto_rate = auto_applied / total
            override_rate = overrides / total if total else 0
            if auto_rate >= self.auto_apply_rate_min and override_rate <= self.override_rate_max:
                return ConvergenceResult(
                    status="CONVERGED_AUTO_APPLY",
                    reason=f"Auto-apply rate {auto_rate:.2f}, override rate {override_rate:.2f}",
                    confidence=auto_rate,
                )

        # Criterion 6: Divergence detection
        if total >= 5 and override_rate > 0.40:
            return ConvergenceResult(
                status="DIVERGING_REVIEW_NEEDED",
                reason=f"Override rate too high: {override_rate:.2f}",
                confidence=1.0 - override_rate,
            )

        return ConvergenceResult(
            status="CONTINUE",
            reason="No convergence criterion met",
            confidence=0.0,
        )

    def reset(self) -> None:
        """Clear observation history."""
        self._history.clear()

    @property
    def observation_count(self) -> int:
        return len(self._history)


def check_convergence_status(
    observations: List[Dict[str, Any]],
    max_iterations: int = 12,
) -> str:
    """One-shot convergence check for a list of observations."""
    checker = ConvergenceChecker(max_iterations=max_iterations)
    for obs in observations:
        checker.record(obs)
    return checker.check().status
