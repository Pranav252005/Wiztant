"""
TuneHub orchestrator — universal meta-learner for all wiztant features.

Intentionally thin. Delegates ALL feature-specific logic to TuneBase plugins.
This ensures TuneHub never needs modification when adding features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import (
    ComplexityLevel,
    LearnedModel,
    TuneStatus,
    ValidationError,
)
from .storage.abstract import TuneStorage
from .tune_base import TuneBase


# =============================================================
#  DATA CLASSES
# =============================================================


@dataclass
class TuneRequest:
    """User-initiated tuning request."""

    user_id: str
    feature_name: str
    task: str
    budget_limit: int
    urgency: str = "normal"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TuneResult:
    """Outcome of a tuning operation."""

    success: bool
    model: Optional[LearnedModel]
    iterations_used: int
    iterations_remaining: int
    message: str
    reusable: bool
    sync_status: Optional[str] = None


# =============================================================
#  ORCHESTRATOR
# =============================================================


class TuneHub:
    """
    Universal meta-learner orchestrator for all wiztant features.

    DESIGN DECISION: TuneHub is intentionally thin. It orchestrates
    but delegates ALL feature-specific logic to TuneBase plugins.
    This ensures TuneHub never needs modification when adding features.
    """

    def __init__(
        self,
        storage: TuneStorage,
        sync_manager: Optional[Any] = None,
        quality_judge_factory: Optional[Callable[[], Any]] = None,
        desktop_mode: str = "desktop2",
    ):
        self.storage = storage
        self.sync_manager = sync_manager
        self.quality_judge_factory = quality_judge_factory
        self.desktop_mode = desktop_mode


    def tune_feature(self, request: TuneRequest) -> TuneResult:
        """
        Meta-interface: Initiate tuning for any feature.

        Orchestrates the full pipeline:
        1. Check tier eligibility
        2. Estimate complexity
        3. Get credit approval
        4. Phase 1: Learn (Desktop 2)
        5. Phase 2: Validate (Desktop 2)
        6. Phase 3: Deploy + Sync (Desktop 2 → Desktop 1)
        """
        try:
            # Step 1: Resolve tuner
            tuner = TuneBase.create(request.feature_name)

            # Step 2: Estimate complexity
            complexity = tuner.estimate_complexity(request.task, request.context)

            # Step 3: Budget initialization
            budget = CreditBudget(approved=request.budget_limit)

            # Step 4: LEARN (expensive, Desktop 2 only)
            if self.desktop_mode != "desktop2":
                return TuneResult(
                    success=False,
                    model=None,
                    iterations_used=0,
                    iterations_remaining=request.budget_limit,
                    message="Learning only available on Desktop 2",
                    reusable=False,
                )

            judge = (
                self.quality_judge_factory()
                if self.quality_judge_factory
                else None
            )
            learned_model = tuner.learn(
                task=request.task,
                budget=budget,
                context=request.context,
                judge=judge,
            )

            if learned_model.status == TuneStatus.FAILED:
                return TuneResult(
                    success=False,
                    model=learned_model,
                    credits_used=budget["consumed"],
                    iterations_remaining=budget["approved"] - budget["consumed"],
                    message="Learning failed — could not find viable configuration",
                    reusable=False,
                )

            # Step 7: VALIDATE
            validated = tuner.validate(learned_model, judge=judge)
            if not validated:
                learned_model.status = TuneStatus.FAILED
                self.storage.store_tune(request.user_id, learned_model)
                return TuneResult(
                    success=False,
                    model=learned_model,
                    credits_used=budget["consumed"],
                    iterations_remaining=budget["approved"] - budget["consumed"],
                    message="Validation failed — learned model did not generalize",
                    reusable=False,
                )

            learned_model.status = TuneStatus.VALIDATED

            # Step 8: DEPLOY
            deployment_manifest = tuner.deploy(learned_model)
            learned_model.status = TuneStatus.DEPLOYED

            # Step 9: PERSIST & SYNC
            self.storage.store_tune(request.user_id, learned_model)

            sync_status = None
            if self.sync_manager:
                sync_status = self._sync_to_desktop1(request.user_id, learned_model)

            # Step 5: Record iterations used
            iterations_consumed = learned_model.payload.get("experiment_count", 0)

            return TuneResult(
                success=True,
                model=learned_model,
                iterations_used=iterations_consumed,
                iterations_remaining=request.budget_limit - iterations_consumed,
                message=f"Tune deployed successfully (v{learned_model.version})",
                reusable=True,
                sync_status=sync_status,
            )

        except KeyError as e:
            return TuneResult(
                success=False,
                model=None,
                iterations_used=0,
                iterations_remaining=request.budget_limit,
                message=f"Unknown feature: {e}",
                reusable=False,
            )
        except Exception as e:
            return TuneResult(
                success=False,
                model=None,
                iterations_used=0,
                iterations_remaining=request.budget_limit,
                message=f"Internal error: {type(e).__name__}: {str(e)}",
                reusable=False,
            )

    def resolve_tune(
        self,
        user_id: str,
        feature_name: str,
        task: str,
        feature_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        SYNCHRONOUS hot-path method. Called every time a feature triggers.
        Must complete in < 50ms for UX smoothness.
        """
        tuner = TuneBase.create(feature_name)
        task_signature = self._normalize_task(task)

        # Fast path: local lookup
        model = self.storage.get_tune(user_id, feature_name, task_signature)

        if model and model.status == TuneStatus.DEPLOYED:
            return tuner.apply(model, feature_input)

        # Fallback: default config
        return tuner.get_default_config(task)

    def list_tunes(
        self, user_id: str, feature_name: Optional[str] = None
    ) -> List[LearnedModel]:
        return self.storage.list_tunes(user_id, feature_name)

    def delete_tune(self, user_id: str, tune_id: str) -> bool:
        return self.storage.delete_tune(user_id, tune_id)

    def rollback_tune(
        self, user_id: str, tune_id: str, to_version: int
    ) -> Optional[LearnedModel]:
        """Rollback to a previous version. Power tier only."""
        current = self.storage.get_tune_by_id(user_id, tune_id)
        if not current:
            return None

        historical = self.storage.get_tune_version(user_id, tune_id, to_version)
        if not historical:
            return None

        rollback = LearnedModel(
            tune_id=current.tune_id,
            feature_name=current.feature_name,
            task_signature=current.task_signature,
            payload=historical.payload,
            quality_score=historical.quality_score,
            complexity=current.complexity,
            status=TuneStatus.DEPLOYED,
            version=current.version + 1,
            parent_version=current.version,
            metadata={
                **current.metadata,
                "rollback_from": current.version,
                "rollback_to": to_version,
                "rollback_at": datetime.utcnow().isoformat(),
            },
        )

        self.storage.store_tune(user_id, rollback)
        return rollback

    @staticmethod
    def _normalize_task(task: str) -> str:
        return task.lower().strip().replace(" ", "_")[:64]

    def _sync_to_desktop1(self, user_id: str, model: LearnedModel) -> str:
        if not self.sync_manager:
            return "no_sync_manager"
        payload = TuneBase.create(model.feature_name).prepare_sync_payload(model)
        return self.sync_manager.publish_tune(user_id, model, payload)
