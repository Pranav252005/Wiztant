"""A/B testing framework for Tune Hub.

Provides statistical tests and experiment management for validating
that learned tunes outperform default configurations.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ABTestResult:
    """Result of an A/B test comparison."""

    status: str  # SIGNIFICANT_IMPROVEMENT, SIGNIFICANT_REGRESSION, NO_SIGNIFICANT_DIFFERENCE, INSUFFICIENT_DATA
    p_value: float = 1.0
    treatment_median: float = 0.0
    control_median: float = 0.0
    effect_size: float = 0.0
    sample_size_control: int = 0
    sample_size_treatment: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestGroup:
    """Data for one arm of an A/B test."""

    name: str
    scores: List[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def median(self) -> float:
        if not self.scores:
            return 0.0
        s = sorted(self.scores)
        mid = len(s) // 2
        if len(s) % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / 2

    @property
    def mean(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores) / len(self.scores)


def mann_whitney_u_test(
    treatment_scores: List[float],
    control_scores: List[float],
) -> ABTestResult:
    """
    Mann-Whitney U test (non-parametric) for comparing two groups.

    Returns an ABTestResult with p-value approximated via normal approximation.
    """
    if len(treatment_scores) < 3 or len(control_scores) < 3:
        return ABTestResult(status="INSUFFICIENT_DATA")

    # Combine and rank
    combined = [(score, "treatment") for score in treatment_scores] + [
        (score, "control") for score in control_scores
    ]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (average for ties)
    ranks: Dict[float, float] = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2  # 1-based ranking
        for k in range(i, j):
            ranks[combined[k][0]] = avg_rank
        i = j

    # Sum ranks per group
    R_treatment = sum(ranks[s] for s in treatment_scores)
    R_control = sum(ranks[s] for s in control_scores)

    n1 = len(treatment_scores)
    n2 = len(control_scores)

    # U statistics
    U_treatment = R_treatment - n1 * (n1 + 1) / 2
    U_control = R_control - n2 * (n2 + 1) / 2

    # Normal approximation
    mu = n1 * n2 / 2
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)

    if sigma == 0:
        return ABTestResult(status="INSUFFICIENT_DATA")

    z = (min(U_treatment, U_control) - mu) / sigma
    # Two-tailed p-value
    p_value = 2 * (1 - _normal_cdf(abs(z)))

    treatment_median = sorted(treatment_scores)[len(treatment_scores) // 2]
    control_median = sorted(control_scores)[len(control_scores) // 2]

    # Effect size (rank-biserial correlation)
    effect_size = (2 * (R_treatment / n1 - R_control / n2)) / (n1 + n2)

    if p_value < 0.05 and treatment_median > control_median * 1.15:
        status = "SIGNIFICANT_IMPROVEMENT"
    elif p_value < 0.05 and treatment_median < control_median:
        status = "SIGNIFICANT_REGRESSION"
    else:
        status = "NO_SIGNIFICANT_DIFFERENCE"

    return ABTestResult(
        status=status,
        p_value=p_value,
        treatment_median=treatment_median,
        control_median=control_median,
        effect_size=effect_size,
        sample_size_control=n2,
        sample_size_treatment=n1,
    )


import math


def _normal_cdf(x: float) -> float:
    """Approximate CDF of standard normal distribution."""
    # Abramowitz and Stegun approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2.0)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)


class ABTestFramework:
    """Manages A/B tests for tune validation."""

    def __init__(
        self,
        control_ratio: float = 0.10,
        min_sample_size: int = 30,
        improvement_threshold: float = 1.15,
    ):
        self.control_ratio = control_ratio
        self.min_sample_size = min_sample_size
        self.improvement_threshold = improvement_threshold
        self._tests: Dict[str, Dict[str, Any]] = {}

    def assign_group(self, user_id: str, task_type: str) -> str:
        """Deterministically assign a user to control or treatment."""
        key = f"{user_id}:{task_type}"
        bucket = int(hashlib.sha256(key.encode()).hexdigest(), 16) % 100
        if bucket < int(self.control_ratio * 100):
            return "control"
        return "treatment"

    def record_score(
        self, test_id: str, group: str, score: float, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a score for a test group."""
        if test_id not in self._tests:
            self._tests[test_id] = {
                "control": ABTestGroup(name="control"),
                "treatment": ABTestGroup(name="treatment"),
            }
        self._tests[test_id][group].scores.append(score)

    def evaluate(self, test_id: str) -> ABTestResult:
        """Evaluate an A/B test."""
        test = self._tests.get(test_id)
        if not test:
            return ABTestResult(status="INSUFFICIENT_DATA")

        control = test["control"]
        treatment = test["treatment"]

        if control.n < self.min_sample_size or treatment.n < self.min_sample_size:
            return ABTestResult(status="INSUFFICIENT_DATA")

        return mann_whitney_u_test(treatment.scores, control.scores)

    def summary(self, test_id: str) -> Dict[str, Any]:
        """Human-readable summary of a test."""
        test = self._tests.get(test_id)
        if not test:
            return {"error": "Test not found"}

        result = self.evaluate(test_id)
        return {
            "test_id": test_id,
            "control": {"n": test["control"].n, "median": test["control"].median},
            "treatment": {"n": test["treatment"].n, "median": test["treatment"].median},
            "result": result.status,
            "p_value": result.p_value,
            "effect_size": result.effect_size,
        }
