# Tune Hub — Technical Architecture Specification

## Document Control
| | |
|---|---|
| **Version** | v1.0 |
| **Status** | Draft for Engineering Review |
| **Date** | 2026-05-02 |
| **Audience** | Backend Engineers, ML Engineers, Platform Architects |

---

## Table of Contents

1. [Executive Summary & Architecture Philosophy](#1-executive-summary)
2. [Class Hierarchy & Core Abstractions](#2-class-hierarchy)
3. [Data Layer Design](#3-data-layer)
4. [API Contracts](#4-api-contracts)
5. [System Flow Architecture](#5-system-flows)
6. [Technology Stack Recommendations](#6-technology-stack)
7. [Key Technical Decisions & Trade-offs](#7-technical-decisions)

---

## 1. Executive Summary & Architecture Philosophy

### 1.1 Design Principles

Tune Hub is built on five core architectural principles:

| Principle | Implication |
|-----------|-------------|
| **Plugin Tuner Architecture** | Every feature tuner is a self-contained plugin implementing `TuneBase`. Adding BrowserAgentTuner requires zero changes to TuneHub core. |
| **Tier-Aware Storage** | The same logical schema persists differently per pricing tier. Free tier = local SQLite, single tune, no versioning. Pro = Postgres + Redis, unlimited, versioning. Power = encrypted Postgres + encrypted S3, marketplace, rollback. |
| **Desktop 1 ↔ Desktop 2 Separation** | Learning (expensive, experimental) runs on Desktop 2. Deployment (fast, deterministic) runs on Desktop 1. Communication via async message queue. |
| **Credit-Gated Experimentation** | Every learning phase consumes credits. Credit tracking is first-class, not bolted-on. |
| **Event-Driven Tune Application** | Feature triggers emit events; Tune Hub asynchronously resolves the best tune and injects it before the feature executes. |

### 1.2 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DESKTOP 1 (Production)                          │
│                                                                              │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐  │
│   │  RePrompt   │   │  Dictation  │   │    Agent    │   │  FutureFeature  │  │
│   │   Feature   │   │   Feature   │   │   Feature   │   │     Feature     │  │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └────────┬────────┘  │
│          │                 │                 │                    │         │
│          └─────────────────┴─────────────────┴────────────────────┘         │
│                                    │                                        │
│                         ┌──────────▼──────────┐                             │
│                         │   Tune Application   │                             │
│                         │    Middleware        │                             │
│                         │   (Event Router)    │                             │
│                         └──────────┬──────────┘                             │
│                                    │                                        │
│                         ┌──────────▼──────────┐                             │
│                         │   TuneHub Core       │                             │
│                         │   (Desktop 1 Node)   │                             │
│                         └──────────┬──────────┘                             │
│                                    │                                        │
│                         ┌──────────▼──────────┐                             │
│                         │   Local Cache        │                             │
│                         │   (SQLite + JSON)    │                             │
│                         └─────────────────────┘                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Async Message Queue (NATS / RabbitMQ)
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DESKTOP 2 (Experimentation)                       │
│                                                                              │
│                         ┌─────────────────────┐                             │
│                         │   TuneHub Core       │                             │
│                         │   (Desktop 2 Node)   │                             │
│                         └──────────┬──────────┘                             │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          │                         │                         │              │
│   ┌──────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐       │
│   │RePromptTuner│          │DictationTuner│          │  AgentTuner  │       │
│   │  (Plugin)   │          │   (Plugin)   │          │   (Plugin)    │       │
│   └─────────────┘          └─────────────┘          └─────────────┘       │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │              Experimentation Engine & ML Pipeline                 │     │
│   │   - Credit consumption tracking                                 │     │
│   │   - A/B testing framework                                       │     │
│   │   - Quality scoring via Claude/LLM judge                        │     │
│   │   - Causal model building (AgentTuner)                          │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │              Remote Storage Layer                                 │     │
│   │   - Pro: PostgreSQL + Redis                                       │     │
│   │   - Power: Encrypted PostgreSQL + Encrypted S3                    │     │
│   │   - MLflow / Weights & Biases for experiment tracking             │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Class Hierarchy & Core Abstractions

### 2.1 Base Abstractions

```python
# tune_hub/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Type, Callable
import json


class ComplexityLevel(Enum):
    """Tune complexity tiers mapped to pricing."""
    LOW = auto()      # Free tier eligible
    MEDIUM = auto()   # Pro tier eligible
    HIGH = auto()     # Power tier eligible


class TuneStatus(Enum):
    """Lifecycle status of a tune."""
    DRAFT = auto()        # Learning in progress
    PENDING_VALIDATION = auto()
    VALIDATED = auto()    # Ready for deployment
    DEPLOYED = auto()     # Active on Desktop 1
    ARCHIVED = auto()     # Superseded by newer version
    FAILED = auto()       # Validation failed


@dataclass(frozen=True)
class CreditBudget:
    """Immutable credit allocation for a learning session."""
    approved: int
    consumed: int = 0
    reserved: int = 0  # Credits held for running experiments
    
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
            reserved=self.reserved
        )


@dataclass
class LearnedModel:
    """Generic container for any tuner's learned output."""
    tune_id: str
    feature_name: str
    task_signature: str  # Normalized task identifier (e.g., "coding_tasks")
    payload: Dict[str, Any]  # Feature-specific data
    quality_score: float  # 0.0 - 1.0
    complexity: ComplexityLevel
    status: TuneStatus = TuneStatus.DRAFT
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


class InsufficientCreditsError(Exception):
    """Raised when a learning session exceeds its credit budget."""
    pass


class ValidationError(Exception):
    """Raised when a learned model fails validation."""
    pass
```

### 2.2 TuneBase Abstract Class

```python
# tune_hub/tune_base.py
from abc import abstractmethod
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass

from .base import (
    ComplexityLevel, CreditBudget, LearnedModel, TuneStatus, ValidationError
)


class QualityJudge(Protocol):
    """Protocol for quality scoring backends (Claude, GPT-4, human-in-the-loop)."""
    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        ...


@dataclass
class ExperimentResult:
    """Result of a single experiment iteration."""
    config: Dict[str, Any]       # The configuration tested
    output: Any                   # Raw output from the feature
    score: float                  # Quality score (0.0 - 1.0)
    credits_used: int
    iteration: int
    metadata: Dict[str, Any]


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
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel:
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
        budget: CreditBudget,
        context: Optional[Dict[str, Any]] = None,
        judge: Optional[QualityJudge] = None
    ) -> LearnedModel:
        """
        Core learning loop. Runs expensive experiments on Desktop 2.
        
        Contract:
        - Must respect CreditBudget; raise InsufficientCreditsError if exceeded
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
        iteration: int
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
        judge: Optional[QualityJudge] = None
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
        - Human-in-the-loop verification (Power tier)
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
        
        Power tier: Returns encrypted payload.
        Others: Returns JSON bytes.
        """
        data = model.to_storage_format()
        return json.dumps(data, default=str).encode("utf-8")
    
    # ───────────────────────────────────────────────────────────────
    # RUNTIME: Tune Application (runs on Desktop 1)
    # ───────────────────────────────────────────────────────────────
    
    @abstractmethod
    def apply(
        self,
        model: LearnedModel,
        feature_input: Dict[str, Any]
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
```

### 2.3 TuneHub Orchestrator

```python
# tune_hub/orchestrator.py
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .base import (
    ComplexityLevel, CreditBudget, LearnedModel, TuneStatus,
    InsufficientCreditsError, ValidationError
)
from .tune_base import TuneBase
from .storage import TuneStorage
from .credit_system import CreditTracker
from .sync import SyncManager


@dataclass
class TuneRequest:
    """User-initiated tuning request."""
    user_id: str
    feature_name: str
    task: str
    approved_credits: int
    tier: str
    urgency: str = "normal"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TuneResult:
    """Outcome of a tuning operation."""
    success: bool
    model: Optional[LearnedModel]
    credits_used: int
    credits_remaining: int
    message: str
    reusable: bool
    sync_status: Optional[str] = None


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
        credit_tracker: CreditTracker,
        sync_manager: Optional[SyncManager] = None,
        quality_judge_factory: Optional[Callable[[], Any]] = None,
        desktop_mode: str = "desktop2"
    ):
        self.storage = storage
        self.credit_tracker = credit_tracker
        self.sync_manager = sync_manager
        self.quality_judge_factory = quality_judge_factory
        self.desktop_mode = desktop_mode
        
        self._tier_matrix = {
            "free": {ComplexityLevel.LOW},
            "pro": {ComplexityLevel.LOW, ComplexityLevel.MEDIUM},
            "power": {ComplexityLevel.LOW, ComplexityLevel.MEDIUM, ComplexityLevel.HIGH},
        }
    
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
            
            # Step 3: Tier gate
            if complexity not in self._tier_matrix.get(request.tier, set()):
                return TuneResult(
                    success=False,
                    model=None,
                    credits_used=0,
                    credits_remaining=request.approved_credits,
                    message=f"Complexity {complexity.name} requires tier upgrade",
                    reusable=False
                )
            
            # Step 4: Credit budget initialization
            budget = CreditBudget(approved=request.approved_credits)
            
            # Step 5: Check existing tune
            existing = self.storage.get_tune(
                user_id=request.user_id,
                feature_name=request.feature_name,
                task_signature=self._normalize_task(request.task)
            )
            if existing and request.tier == "free":
                return TuneResult(
                    success=False,
                    model=existing,
                    credits_used=0,
                    credits_remaining=request.approved_credits,
                    message="Free tier: Only 1 tune allowed. Delete existing first.",
                    reusable=True
                )
            
            # Step 6: LEARN (expensive, Desktop 2 only)
            if self.desktop_mode != "desktop2":
                return TuneResult(
                    success=False,
                    model=None,
                    credits_used=0,
                    credits_remaining=request.approved_credits,
                    message="Learning only available on Desktop 2",
                    reusable=False
                )
            
            judge = self.quality_judge_factory() if self.quality_judge_factory else None
            learned_model = tuner.learn(
                task=request.task,
                budget=budget,
                context=request.context,
                judge=judge
            )
            
            if learned_model.status == TuneStatus.FAILED:
                return TuneResult(
                    success=False,
                    model=learned_model,
                    credits_used=budget.consumed,
                    credits_remaining=budget.approved - budget.consumed,
                    message="Learning failed — could not find viable configuration",
                    reusable=False
                )
            
            # Step 7: VALIDATE
            validated = tuner.validate(learned_model, judge=judge)
            if not validated:
                learned_model.status = TuneStatus.FAILED
                self.storage.store_tune(request.user_id, learned_model)
                return TuneResult(
                    success=False,
                    model=learned_model,
                    credits_used=budget.consumed,
                    credits_remaining=budget.approved - budget.consumed,
                    message="Validation failed — learned model did not generalize",
                    reusable=False
                )
            
            learned_model.status = TuneStatus.VALIDATED
            
            # Step 8: DEPLOY
            deployment_manifest = tuner.deploy(learned_model)
            learned_model.status = TuneStatus.DEPLOYED
            
            # Step 9: PERSIST & SYNC
            self.storage.store_tune(request.user_id, learned_model)
            
            sync_status = None
            if self.sync_manager and request.tier in ("pro", "power"):
                sync_status = self._sync_to_desktop1(request.user_id, learned_model)
            
            # Step 10: Record credit consumption
            self.credit_tracker.consume(request.user_id, budget.consumed)
            
            return TuneResult(
                success=True,
                model=learned_model,
                credits_used=budget.consumed,
                credits_remaining=budget.approved - budget.consumed,
                message=f"Tune deployed successfully (v{learned_model.version})",
                reusable=True,
                sync_status=sync_status
            )
            
        except InsufficientCreditsError as e:
            return TuneResult(
                success=False,
                model=None,
                credits_used=0,
                credits_remaining=0,
                message=f"Credit budget exceeded: {e}",
                reusable=False
            )
        except KeyError as e:
            return TuneResult(
                success=False,
                model=None,
                credits_used=0,
                credits_remaining=request.approved_credits,
                message=f"Unknown feature: {e}",
                reusable=False
            )
        except Exception as e:
            return TuneResult(
                success=False,
                model=None,
                credits_used=0,
                credits_remaining=request.approved_credits,
                message=f"Internal error: {type(e).__name__}: {str(e)}",
                reusable=False
            )
    
    def resolve_tune(
        self,
        user_id: str,
        feature_name: str,
        task: str,
        feature_input: Dict[str, Any]
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
    
    def list_tunes(self, user_id: str, feature_name: Optional[str] = None) -> List[LearnedModel]:
        return self.storage.list_tunes(user_id, feature_name)
    
    def delete_tune(self, user_id: str, tune_id: str) -> bool:
        return self.storage.delete_tune(user_id, tune_id)
    
    def rollback_tune(self, user_id: str, tune_id: str, to_version: int) -> Optional[LearnedModel]:
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
            }
        )
        
        self.storage.store_tune(user_id, rollback)
        return rollback
    
    def _normalize_task(self, task: str) -> str:
        return task.lower().strip().replace(" ", "_")[:64]
    
    def _sync_to_desktop1(self, user_id: str, model: LearnedModel) -> str:
        if not self.sync_manager:
            return "no_sync_manager"
        payload = TuneBase.create(model.feature_name).prepare_sync_payload(model)
        return self.sync_manager.publish_tune(user_id, model, payload)
```

### 2.4 Feature-Specific Tuner Implementations

```python
# tune_hub/tuners/reprompt_tuner.py
from typing import Dict, List, Optional, Any

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult, QualityJudge


class RePromptTuner(TuneBase, feature_name="reprompt"):
    """Learns optimal persona blend weights for different task categories."""
    
    PERSONAS = ["debug", "build", "research", "write", "plan"]
    
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel:
        task_lower = task.lower()
        domains = sum(1 for p in ["code", "write", "research", "debug", "plan"] if p in task_lower)
        if domains >= 4:
            return ComplexityLevel.HIGH
        elif domains >= 2:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW
    
    def learn(self, task: str, budget: CreditBudget,
              context: Optional[Dict[str, Any]] = None,
              judge: Optional[QualityJudge] = None) -> LearnedModel:
        results: List[ExperimentResult] = []
        task_signature = task.lower().strip().replace(" ", "_")
        candidates = self._generate_candidates()
        candidates = candidates[:min(len(candidates), budget.approved)]
        
        for i, blend in enumerate(candidates):
            if not budget.can_spend(1):
                break
            output = self._run_prompt_with_blend(task, blend)
            score = judge.score(output, {"task": task}) if judge else 0.5
            results.append(ExperimentResult(
                config={"blend": blend}, output=output, score=score,
                credits_used=1, iteration=i, metadata={}
            ))
            budget = budget.spend(1)
        
        aggregated = self._aggregate(results)
        best_blend = aggregated.get("best_config", {}).get("blend", self._default_blend())
        best_score = aggregated.get("best_score", 0.0)
        
        return LearnedModel(
            tune_id=f"reprompt_{task_signature}_{uuid.uuid4().hex[:8]}",
            feature_name=self.feature_name,
            task_signature=task_signature,
            payload={"personas": best_blend, "experiment_count": len(results), "aggregate": aggregated},
            quality_score=best_score,
            complexity=self.estimate_complexity(task),
            status=TuneStatus.DRAFT,
        )
    
    def validate(self, model: LearnedModel, hold_out_tasks=None, judge=None) -> bool:
        return model.quality_score >= 0.75
    
    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {"tune_id": model.tune_id, "personas": model.payload["personas"], "quality_score": model.quality_score}
    
    def apply(self, model: LearnedModel, feature_input: Dict[str, Any]) -> Dict[str, Any]:
        feature_input["persona_weights"] = model.payload.get("personas", self._default_blend())
        feature_input["tune_id"] = model.tune_id
        return feature_input
    
    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"persona_weights": self._default_blend(), "tune_id": None}
    
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
```

```python
# tune_hub/tuners/dictation_tuner.py
from typing import Dict, List, Optional, Any
from collections import defaultdict

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult, QualityJudge


class DictationTuner(TuneBase, feature_name="dictation"):
    """Learns domain-specific vocabulary corrections."""
    
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel:
        domain = task.lower()
        if any(d in domain for d in ["medical", "legal", "scientific", "engineering"]):
            return ComplexityLevel.HIGH
        if any(d in domain for d in ["crypto", "finance", "tech", "gaming"]):
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW
    
    def learn(self, task: str, budget: CreditBudget,
              context: Optional[Dict[str, Any]] = None,
              judge: Optional[QualityJudge] = None) -> LearnedModel:
        results: List[ExperimentResult] = []
        domain = task.lower().strip().replace(" ", "_")
        vocab = context.get("vocabulary", []) if context else []
        if not vocab:
            vocab = self._get_default_vocab(domain)
        
        corrections = defaultdict(lambda: {"correct": "", "count": 0, "confidence": 0.0})
        
        for i, word in enumerate(vocab):
            if not budget.can_spend(1):
                break
            variants = self._generate_variants(word)
            for variant in variants:
                dictated = self._simulate_dictation(variant)
                if dictated != word:
                    corrections[dictated]["correct"] = word
                    corrections[dictated]["count"] += 1
            budget = budget.spend(1)
        
        correction_map = {}
        for misspelled, data in corrections.items():
            correction_map[misspelled] = {
                "correct": data["correct"],
                "confidence": min(data["count"] / 3.0, 1.0),
            }
        
        high_conf = sum(1 for c in correction_map.values() if c["confidence"] >= 0.7)
        success_rate = high_conf / max(len(vocab), 1)
        
        return LearnedModel(
            tune_id=f"dictation_{domain}_{uuid.uuid4().hex[:8]}",
            feature_name=self.feature_name,
            task_signature=domain,
            payload={"corrections": correction_map, "domain": domain, "vocab_size": len(vocab)},
            quality_score=success_rate,
            complexity=self.estimate_complexity(task),
            status=TuneStatus.DRAFT,
        )
    
    def validate(self, model: LearnedModel, hold_out_tasks=None, judge=None) -> bool:
        corrections = model.payload.get("corrections", {})
        if not corrections:
            return False
        avg_conf = sum(c["confidence"] for c in corrections.values()) / len(corrections)
        return avg_conf >= 0.5
    
    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {"tune_id": model.tune_id, "corrections": model.payload["corrections"], "domain": model.payload["domain"]}
    
    def apply(self, model: LearnedModel, feature_input: Dict[str, Any]) -> Dict[str, Any]:
        feature_input["correction_map"] = model.payload.get("corrections", {})
        feature_input["tune_id"] = model.tune_id
        return feature_input
    
    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"correction_map": {}, "tune_id": None}
    
    def _get_default_vocab(self, domain: str) -> List[str]:
        defaults = {
            "crypto": ["ethereum", "bitcoin", "blockchain", "defi", "nft", "kimi"],
            "tech": ["kubernetes", "docker", "typescript", "microservices"],
        }
        return defaults.get(domain, ["example", "word"])
    
    def _generate_variants(self, word: str) -> List[str]:
        variants = [word, word.lower(), word.replace("ph", "f"), word.replace("k", "c")]
        return list(set(variants))
    
    def _simulate_dictation(self, variant: str) -> str:
        return variant
```

```python
# tune_hub/tuners/agent_tuner.py
from typing import Dict, List, Optional, Any
import uuid

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult, QualityJudge


class AgentTuner(TuneBase, feature_name="agent"):
    """Learns app behavior and automation sequences."""
    
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel:
        steps = context.get("estimated_steps", 1) if context else 1
        if steps >= 10 or "multi_app" in task.lower():
            return ComplexityLevel.HIGH
        if steps >= 5:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW
    
    def learn(self, task: str, budget: CreditBudget,
              context: Optional[Dict[str, Any]] = None,
              judge: Optional[QualityJudge] = None) -> LearnedModel:
        results: List[ExperimentResult] = []
        task_sig = task.lower().strip().replace(" ", "_")
        candidate_recipes = self._generate_candidate_recipes(task, budget.approved)
        
        for i, recipe in enumerate(candidate_recipes):
            if not budget.can_spend(1):
                break
            outcome = self._execute_recipe_on_desktop2(recipe)
            score = self._score_outcome(outcome)
            results.append(ExperimentResult(
                config={"recipe": recipe}, output=outcome, score=score,
                credits_used=1, iteration=i,
                metadata={"desktop2_session_id": outcome.get("session_id")}
            ))
            budget = budget.spend(1)
        
        aggregated = self._aggregate(results)
        best_recipe = aggregated.get("best_config", {}).get("recipe", [])
        best_score = aggregated.get("best_score", 0.0)
        
        return LearnedModel(
            tune_id=f"agent_{task_sig}_{uuid.uuid4().hex[:8]}",
            feature_name=self.feature_name,
            task_signature=task_sig,
            payload={"recipe": best_recipe, "recipe_type": "automation_sequence",
                     "experiment_count": len(results), "aggregate": aggregated},
            quality_score=best_score,
            complexity=self.estimate_complexity(task, context),
            status=TuneStatus.DRAFT,
        )
    
    def validate(self, model: LearnedModel, hold_out_tasks=None, judge=None) -> bool:
        recipe = model.payload.get("recipe", [])
        if not recipe:
            return False
        successes = sum(1 for _ in range(3)
                       if self._execute_recipe_on_desktop2(recipe, dry_run=True).get("success", False))
        return successes >= 2
    
    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {"tune_id": model.tune_id, "recipe": model.payload["recipe"], "recipe_type": model.payload["recipe_type"]}
    
    def apply(self, model: LearnedModel, feature_input: Dict[str, Any]) -> Dict[str, Any]:
        feature_input["recipe"] = model.payload.get("recipe", [])
        feature_input["tune_id"] = model.tune_id
        return feature_input
    
    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"recipe": [], "tune_id": None}
    
    def _generate_candidate_recipes(self, task: str, budget: int) -> List[List[Dict]]:
        return [[{"action": "open_app", "target": "photoshop"}]]
    
    def _execute_recipe_on_desktop2(self, recipe: List[Dict], dry_run: bool = False) -> Dict[str, Any]:
        return {"success": True, "session_id": "sandbox_123"}
    
    def _score_outcome(self, outcome: Dict[str, Any]) -> float:
        if not outcome.get("success", False):
            return 0.0
        steps = outcome.get("steps_taken", 1)
        return max(0.0, 1.0 - (steps - 1) * 0.05)
```

### 2.5 Plugin Registration & Future Extensibility

```python
# tune_hub/tuners/__init__.py
"""
Plugin registration module.

To add a new tuner (e.g., BrowserAgentTuner):
1. Create tune_hub/tuners/browser_agent_tuner.py
2. Implement class BrowserAgentTuner(TuneBase, feature_name="browser_agent")
3. Import it here

TuneHub auto-discovers via TuneBase._registry.
"""

from .reprompt_tuner import RePromptTuner
from .dictation_tuner import DictationTuner
from .agent_tuner import AgentTuner

# Future tuners:
# from .browser_agent_tuner import BrowserAgentTuner
# from .plugin_api_tuner import PluginAPITuner

__all__ = ["RePromptTuner", "DictationTuner", "AgentTuner"]
```

**Adding a new tuner requires ZERO changes to TuneHub core.**

---

## 3. Data Layer Design

### 3.1 Entity-Relationship Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│     users       │     │  user_tunes      │     │  tune_versions  │
├─────────────────┤     ├──────────────────┤     ├─────────────────┤
│ user_id (PK)    │◄────┤ user_id (FK)     │────►│ tune_id (FK)    │
│ tier            │     │ tune_id (PK)     │     │ version (PK)    │
│ created_at      │     │ feature_name     │     │ payload (JSONB) │
│ updated_at      │     │ task_signature   │     │ quality_score   │
│ sync_enabled    │     │ current_version  │     │ created_at      │
└─────────────────┘     │ complexity       │     │ metadata        │
                        │ status           │     └─────────────────┘
                        │ quality_score    │
                        │ reusable         │     ┌─────────────────┐
                        │ created_at       │     │  sync_queue     │
                        │ updated_at       │     ├─────────────────┤
                        │ encrypted (bool) │     │ sync_id (PK)    │
                        └──────────────────┘     │ user_id         │
                                                 │ tune_id         │
┌─────────────────┐     ┌──────────────────┐   │ target_desktop  │
│  credit_ledger    │     │  tune_shares     │   │ payload         │
├─────────────────┤     ├──────────────────┤   │ status          │
│ ledger_id (PK)  │     │ share_id (PK)    │   │ retry_count     │
│ user_id (FK)    │     │ tune_id (FK)     │   │ created_at      │
│ tune_id (FK)    │◄────┤ shared_by (FK)   │   └─────────────────┘
│ credits_consumed│     │ shared_with (FK) │
│ credits_refunded│     │ permission       │   ┌─────────────────┐
│ transaction_type│     │ shared_at        │   │  marketplace    │
│ created_at      │     └──────────────────┘   ├─────────────────┤
└─────────────────┘                            │ listing_id (PK) │
                                               │ tune_id (FK)    │
                                               │ seller_id       │
                                               │ price_credits   │
                                               │ rating          │
                                               │ downloads       │
                                               └─────────────────┘
```

### 3.2 PostgreSQL Schema (Pro/Power Tiers)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    user_id VARCHAR(64) PRIMARY KEY,
    tier VARCHAR(16) NOT NULL CHECK (tier IN ('free', 'pro', 'power')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    sync_enabled BOOLEAN DEFAULT FALSE,
    encryption_key_id VARCHAR(128)
);

CREATE TABLE user_tunes (
    tune_id VARCHAR(128) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    feature_name VARCHAR(32) NOT NULL,
    task_signature VARCHAR(64) NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    complexity VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
    quality_score DECIMAL(4,3) CHECK (quality_score BETWEEN 0.0 AND 1.0),
    reusable BOOLEAN DEFAULT TRUE,
    encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, feature_name, task_signature, current_version)
);

CREATE INDEX idx_user_tunes_lookup 
    ON user_tunes(user_id, feature_name, task_signature, status);

CREATE TABLE tune_versions (
    tune_id VARCHAR(128) NOT NULL REFERENCES user_tunes(tune_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    payload JSONB NOT NULL,
    quality_score DECIMAL(4,3),
    parent_version INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY(tune_id, version)
);

CREATE INDEX idx_tune_versions_latest 
    ON tune_versions(tune_id, version DESC);

CREATE TABLE credit_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    tune_id VARCHAR(128) REFERENCES user_tunes(tune_id),
    credits_delta INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    transaction_type VARCHAR(32) NOT NULL CHECK (transaction_type IN (
        'consumption', 'refund', 'purchase', 'subscription_grant', 'transfer'
    )),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_credit_ledger_user ON credit_ledger(user_id, created_at DESC);

CREATE TABLE sync_queue (
    sync_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    tune_id VARCHAR(128) NOT NULL,
    target_desktop VARCHAR(16) NOT NULL DEFAULT 'desktop1',
    payload BYTEA NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'in_progress', 'delivered', 'failed')),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_at TIMESTAMPTZ
);

CREATE INDEX idx_sync_queue_pending 
    ON sync_queue(status, retry_count) WHERE status = 'pending';

CREATE TABLE tune_shares (
    share_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tune_id VARCHAR(128) NOT NULL REFERENCES user_tunes(tune_id),
    shared_by VARCHAR(64) NOT NULL REFERENCES users(user_id),
    shared_with VARCHAR(64) NOT NULL REFERENCES users(user_id),
    permission VARCHAR(16) NOT NULL DEFAULT 'read' 
        CHECK (permission IN ('read', 'use', 'fork')),
    shared_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(tune_id, shared_with)
);

CREATE TABLE marketplace_listings (
    listing_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tune_id VARCHAR(128) NOT NULL REFERENCES user_tunes(tune_id),
    seller_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    title VARCHAR(256) NOT NULL,
    description TEXT,
    price_credits INTEGER NOT NULL DEFAULT 0,
    category VARCHAR(64),
    rating DECIMAL(3,2) DEFAULT 0.0,
    downloads INTEGER DEFAULT 0,
    is_featured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 Free Tier Local Storage (SQLite)

```sql
CREATE TABLE local_tunes (
    tune_id TEXT PRIMARY KEY,
    feature_name TEXT NOT NULL,
    task_signature TEXT NOT NULL,
    payload TEXT NOT NULL,
    quality_score REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(feature_name, task_signature)
);
```

### 3.4 Storage Tier Comparison

| Capability | Free | Pro | Power |
|------------|------|-----|-------|
| Storage backend | Local SQLite | PostgreSQL + Redis | Encrypted PostgreSQL + Encrypted S3 |
| Tune limit | 1 total | Unlimited | Unlimited |
| Versioning | No | Last 5 versions | Full history |
| Rollback | No | Last version only | Any version |
| Cross-machine sync | No | Yes (async) | Yes (encrypted async) |
| Sharing | No | Read/use with Pro users | Marketplace + private encrypted shares |
| Encryption | None | TLS in transit | AES-256-GCM at rest + TLS |
| Cache strategy | In-memory LRU | Redis + local SQLite | Redis + local SQLite + S3 cold storage |
| Backup | None | Daily pg_dump | Continuous WAL archiving |

### 3.5 Power Tier Encryption Model

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import json

class PowerTierEncryption:
    """Per-user encryption for Power tier private tunes."""
    
    KEY_SIZE = 32
    NONCE_SIZE = 12
    
    def __init__(self, key_provider):
        self.key_provider = key_provider
    
    def encrypt(self, user_id: str, tune_id: str, plaintext_payload: dict) -> bytes:
        key = self.key_provider.get_key(user_id)
        aesgcm = AESGCM(key)
        nonce = os.urandom(self.NONCE_SIZE)
        associated_data = f"{user_id}:{tune_id}".encode("utf-8")
        plaintext = json.dumps(plaintext_payload).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext
    
    def decrypt(self, user_id: str, tune_id: str, encrypted_blob: bytes) -> dict:
        key = self.key_provider.get_key(user_id)
        aesgcm = AESGCM(key)
        nonce = encrypted_blob[:self.NONCE_SIZE]
        ciphertext = encrypted_blob[self.NONCE_SIZE:]
        associated_data = f"{user_id}:{tune_id}".encode("utf-8")
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))
```

---

## 4. API Contracts

### 4.1 Public REST API (FastAPI)

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/tune` | POST | Initiate learning for a feature | Yes |
| `/resolve` | POST | Hot-path tune resolution at feature trigger | Yes (internal) |
| `/tunes/{user_id}` | GET | List user's tunes | Yes |
| `/tunes/{user_id}/{tune_id}` | DELETE | Delete a tune | Yes |
| `/tunes/{user_id}/{tune_id}/rollback` | POST | Rollback to version | Power only |
| `/tunes/{user_id}/{tune_id}/share` | POST | Share tune with another user | Pro/Power |
| `/sync/pending` | GET | Pull pending syncs (Desktop 1 startup) | Yes |
| `/credits/{user_id}/balance` | GET | Check credit balance | Yes |

### 4.2 Internal API: TuneHub ↔ Tuner Contract

```python
class ITunerPlugin(Protocol):
    @property
    def feature_name(self) -> str: ...
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel: ...
    def learn(self, task: str, budget: CreditBudget, context=None, judge=None) -> LearnedModel: ...
    def validate(self, model: LearnedModel, hold_out_tasks=None, judge=None) -> bool: ...
    def deploy(self, model: LearnedModel) -> Dict[str, Any]: ...
    def apply(self, model: LearnedModel, feature_input: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_default_config(self, task: str) -> Dict[str, Any]: ...
```

### 4.3 Credit System API

```python
class CreditTracker(ABC):
    def get_balance(self, user_id: str) -> CreditBalance: ...
    def reserve(self, user_id: str, amount: int) -> bool: ...
    def consume(self, user_id: str, amount: int) -> int: ...
    def refund(self, user_id: str, amount: int) -> int: ...
    def grant(self, user_id: str, amount: int, reason: str) -> int: ...
```

### 4.4 Desktop Bridge API

```python
class DesktopBridge(ABC):
    async def connect(self) -> bool: ...
    async def publish(self, message: BridgeMessage, target: str) -> bool: ...
    async def subscribe(self, message_type: MessageType, handler) -> str: ...
    async def unsubscribe(self, subscription_id: str) -> bool: ...
    async def disconnect(self) -> bool: ...
```

---

## 5. System Flow Architecture

### 5.1 Learning Phase Flow (Desktop 2)

```
User Request: "tune my RePrompt for coding tasks"
        │
        ▼
┌─────────────────────────────────────┐
│ 1. TUNEHUB RECEIVES REQUEST        │
│    - Parse feature_name="reprompt" │
│    - Look up RePromptTuner plugin  │
│    - Check tier eligibility        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. COMPLEXITY ESTIMATION            │
│    → "coding tasks" = MEDIUM        │
│    Free tier? → BLOCK               │
│    Pro/Power? → APPROVE             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. CREDIT BUDGET SETUP              │
│    CreditBudget(approved=50)        │
│    Reserve 50 credits in Redis      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. EXPERIMENTATION LOOP             │
│    for each candidate blend:        │
│      1. Configure RePrompt          │
│      2. Run prompt with task        │
│      3. Claude scores output        │
│      4. Record result               │
│      5. CreditBudget.spend(1)       │
│      6. Check can_spend()           │
│      7. Yield progress event        │
│    Credit exhausted → break         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. AGGREGATION                      │
│    Select best-scoring blend        │
│    Create LearnedModel (DRAFT)      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 6. VALIDATION                       │
│    Run on 3 hold-out coding tasks   │
│    All scores > 0.75? → PASS        │
│    Any score < 0.75? → FAIL         │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
   PASS               FAIL
    │                   │
    ▼                   ▼
┌────────┐       ┌────────┐
│ DEPLOY │       │ REFUND │
│ + SYNC │       │CREDITS │
└────────┘       └────────┘
```

### 5.2 Validation Phase Flow

```
Input: LearnedModel (status=DRAFT)
        │
        ▼
┌────────────────────────────────────────────┐
│ VALIDATION GATE                             │
│                                             │
│ RePromptTuner:                              │
│   - Test on 3 hold-out tasks              │
│   - Mean >= 0.75 AND min >= 0.60 → PASS   │
│                                             │
│ DictationTuner:                             │
│   - Coverage >= 80% AND avg conf >= 0.5     │
│                                             │
│ AgentTuner:                                 │
│   - Re-run 3 times, success >= 80%          │
│                                             │
│ Power tier bonus:                           │
│   - Human-in-the-loop gate available        │
└─────────────┬───────────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
 PASS                 FAIL
   │                     │
   ▼                     ▼
┌──────────┐     ┌──────────┐
│ VALIDATED│     │ FAILED   │
│ → DEPLOY │     │ → Refund │
└──────────┘     │ 50%      │
                 └──────────┘
```

### 5.3 Deployment Phase Flow

```
Desktop 2                Message Broker          Desktop 1
─────────               ──────────────         ─────────
    │                        │                     │
    ▼                        │                     │
┌────────┐   1. PUBLISH      │                     │
│ Tuner. │ ─────────────────►│                     │
│ deploy()│  subject:         │                     │
│        │  tunehub.desktop1. │                     │
│        │  sync_tune         │                     │
└────────┘                   │                     │
    │                        │   2. ROUTE          │
    │                        │   to D1 subscriber  │
    │                        │                     │
    │                        │   ────────────────►│
    │                        │                     │
    │                        │           ┌─────────▼────────┐
    │                        │           │ Decrypt (Power)   │
    │                        │           │ Deserialize       │
    │                        │           │ Write to SQLite   │
    │                        │           │ Update LRU cache  │
    │                        │           └─────────┬────────┘
    │                        │                     │
    │          3. ACK       │                     ▼
    │◄──────────────────────┘            ┌─────────────┐
    │   status = DELIVERED               │ DEPLOYED    │
    │                                    │ on D1       │
    ▼                                    └─────────────┘
┌────────┐
│DEPLOYED│
│ on D2  │
└────────┘
```

### 5.4 Feature Trigger → Tune Lookup → Application Pipeline

```
User invokes RePrompt: "Help me debug this Python script"
        │
        ▼
┌────────────────────────────────────────────┐
│ 1. FEATURE TRIGGER EVENT                    │
│    { user_id, feature, task, raw_input }   │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ 2. TUNE RESOLUTION (< 50ms)                 │
│                                             │
│  Step 2a: In-memory LRU cache lookup       │
│     Key: "user:feature:task_signature"      │
│     Cache hit? → Skip to Step 4             │
│                                             │
│  Step 2b: Local SQLite lookup              │
│     SELECT payload FROM local_tunes        │
│     WHERE user_id=? AND feature=?          │
│     AND task_signature=? AND status='DEPLOYED'│
│                                             │
│  Step 2c: No tune found → default config   │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ 3. TUNE APPLICATION (< 10ms)                 │
│    RePromptTuner.apply():                   │
│      persona_weights = {                    │
│        debug: 0.75, build: 0.45,            │
│        research: 0.25, write: 0.0,          │
│        plan: 0.1                             │
│      }                                       │
│      tune_id = "reprompt_debug_python_abc123"│
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ 4. FEATURE EXECUTION                         │
│    RePrompt generates response with          │
│    learned persona blend                     │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ 5. OPTIONAL: QUALITY FEEDBACK LOOP          │
│    If thumbs-down:                           │
│    → Queue re-tuning for next D2 session    │
└────────────────────────────────────────────┘

LATENCY BUDGET:
- Tune resolution:   < 50ms (P99)
- Tune application:  < 10ms
- Total overhead:    < 60ms added to base feature latency
- Cache hit path:    < 5ms (P99)
```

---

## 6. Technology Stack Recommendations

### 6.1 Recommended Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Backend Language** | Python 3.11+ | Rich ML ecosystem, async/await support, dataclasses for clean domain models |
| **Web Framework** | FastAPI | Native Pydantic integration, OpenAPI auto-generation, high-performance async |
| **Database (Pro/Power)** | PostgreSQL 15+ | JSONB for flexible tune payloads, excellent concurrency, mature ecosystem |
| **Cache** | Redis 7+ | Credit tracking (atomic Lua scripts), tune metadata caching, pub/sub for sync events |
| **Message Broker** | NATS JetStream | Lightweight, persistent streams, at-least-once delivery, excellent for Desktop 1↔2 sync |
| **Desktop 1 Cache** | SQLite + Python LRU | Zero-config, embedded, sufficient for Free tier; fast path for all tiers |
| **Experiment Tracking** | MLflow | Track experiments, log artifacts, compare runs; integrates with Tune versioning |
| **Encryption** | cryptography (Python) + AWS KMS / HashiCorp Vault | Industry-standard AES-256-GCM, key wrapping via HSM |
| **Container Orchestration** | Docker + Kubernetes | TuneHub services run as containers; Desktop 2 can be K8s-managed |
| **Monitoring** | Prometheus + Grafana | Track tune success rates, credit consumption, sync latency |
| **Task Queue** | Celery + Redis | Background learning jobs for long-running experiments |
| **Desktop Bridge (alt)** | WebSocket (simple) or RabbitMQ (enterprise) | If NATS not available |

### 6.2 Technology Justifications

**Why Python?**
- All feature tuners need to interface with ML/LLM APIs (Claude, OpenAI)
- Rich ecosystem: `pydantic`, `cryptography`, `sqlalchemy`, `asyncio`
- FastAPI provides production-grade async HTTP with minimal boilerplate

**Why PostgreSQL over MongoDB?**
- Tune data is relational (users → tunes → versions → shares)
- JSONB provides sufficient flexibility for feature-specific payloads
- ACID transactions essential for credit ledger (immutable append-only)
- Better query performance for complex analytical queries (marketplace, admin)

**Why NATS JetStream over Kafka?**
- Simpler operational footprint (single binary vs ZooKeeper + Kafka)
- Native support for at-least-once delivery with ACKs
- Excellent client libraries for Python (async)
- JetStream provides persistence exactly matching our sync_queue needs

**Why Redis for credits?**
- Credit operations need atomicity (reserve → consume → refund)
- Redis Lua scripts execute atomically on the server
- Sub-millisecond latency for credit checks on hot path
- Built-in TTL for monthly reset automation

---

## 7. Key Technical Decisions & Trade-offs

### 7.1 Decision Matrix

| Decision | Choice | Alternative | Rationale |
|----------|--------|-------------|-----------|
| **Plugin architecture vs monolith** | Plugin (TuneBase registry) | Switch-case in TuneHub | Zero core changes for new features; feature teams own their tuner |
| **Stateless tuners vs stateful** | Stateless (LearnedModel carries state) | Tuner instances hold state | Enables cloud sync, reproducibility, easy rollback |
| **Desktop 1↔2 sync: push vs pull** | Push (D2 publishes, D1 subscribes) | D1 polls D2 periodically | Lower latency for tune availability; JetStream handles offline gracefully |
| **Credit budget: immutable vs mutable** | Immutable (CreditBudget dataclass) | In-place mutation | Thread-safe, auditable, prevents over-consumption bugs |
| **Encryption: per-user vs per-tune** | Per-user AES key | Per-tune key | Fewer keys to manage; tune-level granularity adds complexity without clear benefit |
| **Validation: auto vs human** | Auto (LLM judge) with human override | Always human | Auto scales; Power tier gets human gate for edge cases |
| **Task signature: keyword vs embedding** | Keyword normalization | Semantic embedding | Keywords are deterministic, fast, debuggable; embeddings add ML dependency to hot path |
| **Version storage: separate table vs in-tune** | Separate tune_versions table | JSON array in user_tunes | Enables efficient querying of version history; avoids row bloat |
| **Free tier storage: SQLite vs JSON file** | SQLite | JSON on disk | SQL interface consistent with Pro/Power; ACID for tune operations |

### 7.2 Scalability Considerations

**Horizontal Scaling TuneHub:**
- TuneHub itself is stateless; all state in PostgreSQL + Redis
- Multiple TuneHub instances can run behind load balancer
- Credit operations use Redis atomic operations (no race conditions)
- Sync queue workers can scale independently

**Database Scaling Path:**
- Phase 1: Single PostgreSQL instance (handles ~10K users)
- Phase 2: Read replicas for tune lookups (Desktop 1 hot path)
- Phase 3: Shard by user_id for >100K users
- Phase 4: Tune payload offload to S3 (cold storage for old versions)

**Credit System Scaling:**
- Redis Cluster for credit tracking at scale
- Monthly reset implemented as scheduled job + lazy evaluation
- Credit ledger remains in PostgreSQL (append-only, partition by month)

### 7.3 Security Model for Cross-Machine Sync

```
┌─────────────────────────────────────────────────────────────────┐
│              CROSS-MACHINE SYNC SECURITY MODEL                     │
│                                                                  │
│  THREAT: Man-in-the-middle intercepts tune during sync          │
│  MITIGATION: TLS 1.3 for all transport (NATS, REST)           │
│                                                                  │
│  THREAT: Cloud operator reads private tune data                  │
│  MITIGATION: Power tier AES-256-GCM encryption                    │
│  - Plaintext NEVER enters cloud DB                               │
│  - Keys managed by user-controlled HSM / secure enclave          │
│                                                                  │
│  THREAT: Attacker replays old sync message                       │
│  MITIGATION: Nonce + timestamp validation; sync_id deduplication │
│                                                                  │
│  THREAT: Unauthorized user accesses another's tunes              │
│  MITIGATION: Row-level security in PostgreSQL                   │
│  - user_id filtering on all queries                            │
│  - Tune shares explicit allowlist (tune_shares table)            │
│                                                                  │
│  THREAT: Sync message lost, Desktop 1 never receives tune       │
│  MITIGATION: JetStream persistent streams + retry logic          │
│  - sync_queue tracks delivery status                             │
│  - Desktop 1 pulls pending on startup                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 Performance Budgets

| Operation | Target Latency | Measurement |
|-----------|---------------|-------------|
| Complexity estimation | < 100ms | Synchronous, user-facing |
| Tune resolution (Desktop 1) | < 50ms (P99) | Per feature trigger |
| Tune application (Desktop 1) | < 10ms | Per feature trigger |
| Credit check | < 5ms | Redis Lua script |
| Learning (Desktop 2) | < 5 min per credit | Background job |
| Sync D2 → D1 | < 2s (when online) | Async message delivery |
| Sync D2 → D1 (offline) | < 1 min after reconnect | Replay missed messages |

### 7.5 Migration Path

```
Phase 1 (MVP): Free tier only
  - SQLite local storage
  - In-memory credit tracking
  - Single Desktop (no D1/D2 split)
  - RePromptTuner only

Phase 2 (Pro tier):
  + PostgreSQL + Redis
  + Desktop 1 / Desktop 2 split
  + NATS JetStream sync
  + DictationTuner + AgentTuner
  + Tune sharing

Phase 3 (Power tier):
  + Encryption layer
  + Full versioning + rollback
  + Marketplace
  + MLflow experiment tracking
  + S3 cold storage for old versions
```

---

## Appendix A: File Structure

```
tune_hub/
├── __init__.py
├── base.py                    # Core dataclasses, enums, exceptions
├── tune_base.py              # TuneBase abstract class
├── orchestrator.py           # TuneHub orchestrator
├── storage/
│   ├── __init__.py
│   ├── abstract.py           # TuneStorage interface
│   ├── sqlite_store.py       # Free tier implementation
│   ├── postgres_store.py     # Pro/Power implementation
│   └── encryption.py         # Power tier crypto wrapper
├── credit_system/
│   ├── __init__.py
│   ├── abstract.py           # CreditTracker interface
│   ├── free_tracker.py
│   ├── pro_tracker.py
│   └── power_tracker.py
├── tuners/
│   ├── __init__.py           # Plugin registration
│   ├── reprompt_tuner.py
│   ├── dictation_tuner.py
│   ├── agent_tuner.py
│   └── browser_agent_tuner.py  # Future
├── transport/
│   ├── __init__.py
│   ├── abstract.py           # DesktopBridge interface
│   ├── nats_bridge.py
│   └── websocket_bridge.py
├── api/
│   ├── __init__.py
│   ├── public.py             # FastAPI endpoints
│   └── internal.py           # In-process protocols
├── sync/
│   ├── __init__.py
│   └── sync_manager.py
├── quality/
│   ├── __init__.py
│   ├── judge.py              # QualityJudge implementations
│   └── claude_judge.py
└── tests/
    ├── test_orchestrator.py
    ├── test_reprompt_tuner.py
    ├── test_credit_system.py
    └── test_encryption.py
```

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **Tune** | A learned configuration optimized for a specific user, feature, and task |
| **Task Signature** | Normalized task identifier (e.g., "coding_tasks") used for tune lookup |
| **Credit** | Unit of experimentation cost. 1 credit ≈ 1 experiment iteration |
| **Desktop 1** | Production environment where features run and tunes are applied |
| **Desktop 2** | Experimentation environment where learning and validation occur |
| **Persona Blend** | Weighted combination of personas (debug, build, research, etc.) |
| **Recipe** | Automation sequence for Agent tuner (list of actions) |
| **TuneHub** | The orchestrator that routes tuning requests to the correct tuner plugin |
| **Tuner Plugin** | Feature-specific implementation of TuneBase (e.g., RePromptTuner) |

---

*End of Technical Architecture Specification*
