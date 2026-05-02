"""RePromptTuner — learns optimal persona blend weights for different task categories.

Algorithm: Multi-Task Bayesian Optimization with Thompson Sampling.
- Surrogate: Gaussian Process (Matern-5/2 kernel) via scikit-learn
- Acquisition: Expected Improvement (EI) with L-BFGS-B optimization
- Task classifier: keyword + embedding ensemble
- Convergence: util.ConvergenceChecker
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult
from ..utils.convergence import ConvergenceChecker
from ..utils.feature_extraction import (
    cosine_similarity,
    embed_text,
    extract_text_features,
    extract_weight_features,
)
from ..utils.model_persistence import TuneModelPersistence


# =============================================================
#  TASK CLASSIFIER
# =============================================================


class TaskClassifier:
    """Keyword + embedding ensemble task classifier."""

    TASK_CLUSTERS = {
        "coding_task": {
            "keywords": ["code", "bug", "error", "function", "class", "import", "debug"],
            "default_blend": {"debug": 0.7, "build": 0.5, "research": 0.2, "write": 0.0, "plan": 0.1},
        },
        "writing_task": {
            "keywords": ["write", "essay", "email", "blog", "draft", "tone", "style"],
            "default_blend": {"debug": 0.0, "build": 0.1, "research": 0.3, "write": 0.9, "plan": 0.2},
        },
        "research_task": {
            "keywords": ["research", "find", "analyze", "compare", "sources", "study"],
            "default_blend": {"debug": 0.1, "build": 0.0, "research": 0.9, "write": 0.3, "plan": 0.2},
        },
        "planning_task": {
            "keywords": ["plan", "schedule", "roadmap", "steps", "organize", "timeline"],
            "default_blend": {"debug": 0.1, "build": 0.3, "research": 0.2, "write": 0.1, "plan": 0.9},
        },
        "building_task": {
            "keywords": ["build", "create", "implement", "setup", "configure", "deploy"],
            "default_blend": {"debug": 0.3, "build": 0.8, "research": 0.2, "write": 0.1, "plan": 0.4},
        },
    }

    def classify(self, prompt: str) -> Tuple[str, float]:
        """Return (task_type, confidence)."""
        prompt_lower = prompt.lower()

        # Method 1: Keyword match (fast)
        keyword_scores: Dict[str, float] = {}
        for task, data in self.TASK_CLUSTERS.items():
            matches = sum(1 for kw in data["keywords"] if kw in prompt_lower)
            keyword_scores[task] = matches / max(len(data["keywords"]), 1)

        # Method 2: Embedding similarity (accurate)
        prompt_emb = embed_text(prompt, dim=128)
        embedding_scores: Dict[str, float] = {}
        for task, data in self.TASK_CLUSTERS.items():
            # Use centroid of keyword embeddings as task embedding
            task_text = " ".join(data["keywords"])
            task_emb = embed_text(task_text, dim=128)
            embedding_scores[task] = max(0.0, cosine_similarity(prompt_emb, task_emb))

        # Ensemble: weighted combination
        final_scores: Dict[str, float] = {}
        for task in self.TASK_CLUSTERS:
            final_scores[task] = 0.3 * keyword_scores.get(task, 0.0) + 0.7 * embedding_scores.get(task, 0.0)

        best_task = max(final_scores, key=lambda k: final_scores[k])
        confidence = final_scores[best_task]
        total_score = sum(final_scores.values()) or 1.0
        confidence = confidence / total_score

        if confidence < 0.4:
            return ("general", confidence)
        return (best_task, confidence)

    def get_default_blend(self, task_type: str) -> Dict[str, float]:
        """Return default blend for a task type."""
        if task_type in self.TASK_CLUSTERS:
            return dict(self.TASK_CLUSTERS[task_type]["default_blend"])
        return {p: 0.5 for p in ["debug", "build", "research", "write", "plan"]}


# =============================================================
#  GAUSSIAN PROCESS SURROGATE
# =============================================================


class _GPSurrogate:
    """Lightweight GP surrogate for Bayesian optimization."""

    def __init__(self, kernel: str = "matern"):
        self._kernel_name = kernel
        self._model: Any = None
        self._X: List[List[float]] = []
        self._y: List[float] = []

    def fit(self, X: List[List[float]], y: List[float]) -> None:
        if not X or not y or len(X) < 2:
            self._model = None
            return
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern, WhiteKernel

            kernel = Matern(length_scale=0.5, nu=2.5) + WhiteKernel(noise_level=0.1)
            self._model = GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=5,
                alpha=1e-5,
                normalize_y=True,
            )
            import numpy as np

            self._model.fit(np.array(X), np.array(y))
        except Exception:
            self._model = None
        self._X = X
        self._y = y

    def predict(self, x: List[float]) -> Tuple[float, float]:
        """Return (mean, std)."""
        if self._model is None:
            return 0.5, 1.0
        try:
            import numpy as np

            x_arr = np.array(x).reshape(1, -1)
            mu, sigma = self._model.predict(x_arr, return_std=True)
            return float(mu[0]), float(sigma[0])
        except Exception:
            return 0.5, 1.0

    @property
    def best_observed(self) -> float:
        return max(self._y) if self._y else 0.0

    @property
    def n_observations(self) -> int:
        return len(self._y)


# =============================================================
#  ACQUISITION FUNCTION
# =============================================================


def _expected_improvement(
    x: List[float],
    gp: _GPSurrogate,
    xi: float = 0.01,
) -> float:
    """Negative Expected Improvement (for minimization)."""
    mu, sigma = gp.predict(x)
    if sigma == 0:
        return 0.0
    best = gp.best_observed
    z = (mu - best - xi) / sigma
    # Phi(z) and phi(z) for standard normal
    from scipy.stats import norm

    ei = (mu - best - xi) * norm.cdf(z) + sigma * norm.pdf(z)
    return -ei  # negative for minimization


# =============================================================
#  TUNER
# =============================================================


class RePromptTuner(TuneBase, feature_name="reprompt"):
    """Learns optimal persona blend weights for different task categories."""

    PERSONAS = ["debug", "build", "research", "write", "plan"]

    # Conflict matrix: positive = conflict threshold, negative = synergy
    CONFLICT_MATRIX: Dict[tuple, float] = {
        ("debug", "write"): 0.3,
        ("build", "plan"): 0.25,
        ("research", "build"): -0.1,
    }

    def __init__(self) -> None:
        super().__init__()
        self.classifier = TaskClassifier()
        self.persistence = TuneModelPersistence()
        self.convergence = ConvergenceChecker(max_iterations=12)

    # ── PHASE 0: Static Analysis ──

    def estimate_complexity(
        self, task: str, context: Optional[Dict] = None
    ) -> ComplexityLevel:
        task_lower = task.lower()
        domains = sum(
            1 for p in ["code", "write", "research", "debug", "plan"]
            if p in task_lower
        )
        if domains >= 4:
            return ComplexityLevel.HIGH
        elif domains >= 2:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW

    # ── PHASE 1: Learning ──

    def learn(
        self,
        task: str,
        budget: CreditBudget,
        context: Optional[Dict[str, Any]] = None,
        judge=None,
    ) -> LearnedModel:
        task_signature = self._normalize_task(task)
        task_type, confidence = self.classifier.classify(task)

        # Load previous observations for warm-start
        user_id = context.get("user_id", "anonymous") if context else "anonymous"
        prev_obs = self.persistence.load_observations(user_id, self.feature_name, task_signature)

        # Initialize GP and convergence checker
        gp = _GPSurrogate()
        self.convergence.reset()
        observations: List[Dict[str, Any]] = []

        # Warm-start from previous observations
        warm_X: List[List[float]] = []
        warm_y: List[float] = []
        for obs in prev_obs:
            if "weights" in obs and "score" in obs:
                warm_X.append(self._weights_to_vector(obs["weights"]))
                warm_y.append(obs["score"])
        if warm_X:
            gp.fit(warm_X, warm_y)
            for obs in prev_obs:
                self.convergence.record(obs)
                observations.append(obs)

        results: List[ExperimentResult] = []
        iteration = len(observations)

        while iteration < budget.approved and iteration < 12:
            if not budget.can_spend(1):
                break

            # Phase-aware candidate generation
            if iteration < 3 or gp.n_observations < 3:
                # Warm-start: heuristic blends
                weights = self._heuristic_blend(task_type, iteration)
            elif iteration < 8:
                # Exploration: GP-guided
                weights = self._gp_acquisition(gp, exploration_heavy=True)
            else:
                # Exploitation: converge on best
                weights = self._gp_acquisition(gp, exploration_heavy=False)

            # Apply conflict constraints
            weights = self._apply_constraints(weights)

            # Run experiment
            output = self._run_prompt_with_blend(task, weights)
            score = judge.score(output, {"task": task}) if judge else 0.5

            result = ExperimentResult(
                config={"blend": dict(weights)},
                output=output,
                score=score,
                credits_used=1,
                iteration=iteration,
                metadata={"task_type": task_type, "confidence": confidence},
            )
            results.append(result)

            # Record observation
            obs = {
                "weights": self._weights_to_vector(weights),
                "quality_score": score,
                "task_type": task_type,
                "acquisition_value": abs(_expected_improvement(
                    self._weights_to_vector(weights), gp
                )),
            }
            observations.append(obs)
            self.convergence.record(obs)

            # Update GP
            X = [self._weights_to_vector(r.config["blend"]) for r in results]
            y = [r.score for r in results]
            gp.fit(X, y)

            budget = budget.spend(1)
            iteration += 1

            # Check convergence
            conv = self.convergence.check()
            if conv.status.startswith("CONVERGED"):
                break

        # Save observations
        self.persistence.save_observations(user_id, self.feature_name, task_signature, observations)

        # Aggregate results
        aggregated = self._aggregate(results)
        best_blend = aggregated.get("best_config", {}).get("blend", self._default_blend())
        best_score = aggregated.get("best_score", 0.0)

        # Determine convergence status
        conv = self.convergence.check()

        return LearnedModel(
            tune_id=f"reprompt_{task_signature}_{uuid.uuid4().hex[:8]}",
            feature_name=self.feature_name,
            task_signature=task_signature,
            payload={
                "personas": best_blend,
                "task_type": task_type,
                "task_confidence": confidence,
                "experiment_count": len(results),
                "aggregate": aggregated,
                "observation_count": len(observations),
                "convergence_status": conv.status,
                "blend_history": [
                    {"iteration": i, "weights": r.config["blend"], "score": r.score}
                    for i, r in enumerate(results)
                ],
            },
            quality_score=best_score,
            complexity=self.estimate_complexity(task),
            status=TuneStatus.DRAFT,
        )

    # ── PHASE 2: Validation ──

    def validate(
        self,
        model: LearnedModel,
        hold_out_tasks: Optional[List[str]] = None,
        judge=None,
    ) -> bool:
        # Minimum quality threshold
        if model.quality_score < 0.70:
            return False

        # Minimum observations
        obs_count = model.payload.get("observation_count", 0)
        if obs_count < 3:
            return False

        # Test on hold-out tasks if provided
        if hold_out_tasks and judge:
            blend = model.payload.get("personas", self._default_blend())
            scores = []
            for ht in hold_out_tasks:
                output = self._run_prompt_with_blend(ht, blend)
                scores.append(judge.score(output, {"task": ht}))
            if not scores or min(scores) < 0.60:
                return False
            if sum(scores) / len(scores) < 0.75:
                return False

        return True

    # ── PHASE 3: Deployment ──

    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {
            "tune_id": model.tune_id,
            "personas": model.payload["personas"],
            "quality_score": model.quality_score,
            "task_type": model.payload.get("task_type", "general"),
        }

    # ── RUNTIME: Apply ──

    def apply(
        self, model: LearnedModel, feature_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature_input["persona_weights"] = model.payload.get(
            "personas", self._default_blend()
        )
        feature_input["tune_id"] = model.tune_id
        feature_input["task_type"] = model.payload.get("task_type", "general")
        return feature_input

    def get_default_config(self, task: str) -> Dict[str, Any]:
        task_type, _ = self.classifier.classify(task)
        return {
            "persona_weights": self.classifier.get_default_blend(task_type),
            "tune_id": None,
            "task_type": task_type,
        }

    # ── INTERNALS ──

    def _generate_candidates(self) -> List[Dict[str, float]]:
        weights = [0.0, 0.25, 0.5, 0.75, 1.0]
        candidates = []
        base = {p: 0.5 for p in self.PERSONAS}
        for persona in self.PERSONAS:
            for w in weights:
                blend = dict(base)
                blend[persona] = w
                candidates.append(blend)
        candidates.append(base)
        return candidates

    def _default_blend(self) -> Dict[str, float]:
        return {p: 0.5 for p in self.PERSONAS}

    def _run_prompt_with_blend(self, task: str, blend: Dict[str, float]) -> str:
        return f"[simulated_output_for_{task}]"

    @staticmethod
    def _normalize_task(task: str) -> str:
        return task.lower().strip().replace(" ", "_")[:64]

    def _weights_to_vector(self, weights: Any) -> List[float]:
        """Convert weights dict or list to ordered vector."""
        if isinstance(weights, dict):
            return [weights.get(p, 0.5) for p in self.PERSONAS]
        return list(weights)

    def _vector_to_weights(self, vector: List[float]) -> Dict[str, float]:
        return {p: float(v) for p, v in zip(self.PERSONAS, vector)}

    def _heuristic_blend(self, task_type: str, iteration: int) -> Dict[str, float]:
        """Generate a heuristic blend for warm-start."""
        base = self.classifier.get_default_blend(task_type)
        # Perturb slightly per iteration for diversity
        import random

        perturbation = 0.1 * (iteration + 1)
        return {
            p: max(0.0, min(1.0, v + random.uniform(-perturbation, perturbation)))
            for p, v in base.items()
        }

    def _gp_acquisition(
        self, gp: _GPSurrogate, exploration_heavy: bool = True
    ) -> Dict[str, float]:
        """Optimize acquisition function to find next candidate."""
        xi = 0.05 if exploration_heavy else 0.005
        best_x = None
        best_ei = float("inf")  # _expected_improvement returns negative EI

        # Random restarts
        import random

        for _ in range(50):
            x0 = [random.random() for _ in self.PERSONAS]
            try:
                from scipy.optimize import minimize

                bounds = [(0.0, 1.0)] * len(self.PERSONAS)
                result = minimize(
                    lambda x: _expected_improvement(list(x), gp, xi=xi),
                    x0,
                    bounds=bounds,
                    method="L-BFGS-B",
                )
                if result.fun < best_ei:
                    best_ei = result.fun
                    best_x = result.x
            except Exception:
                continue

        if best_x is None:
            return self._default_blend()

        return self._vector_to_weights(best_x.tolist() if hasattr(best_x, "tolist") else list(best_x))

    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply conflict/synergy constraints to weights."""
        result = dict(weights)
        for (p1, p2), threshold in self.CONFLICT_MATRIX.items():
            if threshold > 0:
                # Conflict: cannot both be high
                if result.get(p1, 0.0) > threshold and result.get(p2, 0.0) > threshold:
                    # Reduce the lower one
                    if result[p1] < result[p2]:
                        result[p1] = threshold
                    else:
                        result[p2] = threshold
            else:
                # Synergy: boost if both above threshold
                synergy_threshold = 0.4
                if result.get(p1, 0.0) > synergy_threshold and result.get(p2, 0.0) > synergy_threshold:
                    boost = abs(threshold) * min(result[p1], result[p2])
                    result[p1] = min(1.0, result[p1] + boost)
                    result[p2] = min(1.0, result[p2] + boost)
        return result
