# TuneHub Single-File Architecture Design

> **Status:** Design Review  
> **Date:** 2026-05-30  
> **Author:** Agent (via superpowers:brainstorming)  
> **Scope:** `core/tune_hub/` + feature consumers

---

## 1. Problem Statement

**Current TuneHub violates the single-file principle.**

When tuning a feature (e.g., dictation), changes leak across multiple files:

| What changes | Files touched | Required? |
|---|---|---|
| Add dictation tuning logic | `core/tune_hub/tuners/dictation_tuner.py` | Yes |
| Register dictation storage path | `core/tune_hub/single_file_store.py` | **No — should be automatic** |
| Consume dictation tunes at runtime | `core/hotkeys.py` | **No — should be generic** |
| Middleware routing | `core/tune_hub/middleware.py` | Already generic — OK |
| Orchestrator pipeline | `core/tune_hub/orchestrator.py` | Already generic — OK |

**The user expectation:**
> "TuneHub should only play around in 1 file. Even if it's 5,000 lines of elegant code, it should be only inside that 1 file which makes a big difference in what the feature is trying to do."

This means:
- **Adding a new tuner** → Create exactly **1 file**. Nothing else changes.
- **Tuning an existing feature** → Modify exactly **1 file**. Nothing else changes.
- **Each tuner file is self-contained** — storage path, persistence, learning, validation, deployment, runtime application, and even its feature-consumer hook.

---

## 2. Current Architecture Audit

### 2.1 Shared Registry Violation

`core/tune_hub/single_file_store.py` hardcodes the mapping:

```python
CANONICAL_FILES: Dict[str, Path] = {
    "reprompt":  TUNE_MODELS_DIR / "reprompt_tune.json",
    "dictation": TUNE_MODELS_DIR / "dictation_tune.json",
    "agent":     TUNE_MODELS_DIR / "agent_tune.json",
}
```

Adding a 4th tuner (e.g., `browser_agent`) requires editing this shared file. **This is the central violation.**

### 2.2 Feature Consumer Hardcoding

Each feature consumer has its own TuneHub integration:

| Consumer | Hardcoded Tune Load | Location |
|---|---|---|
| `core/wizprompt.py` | `_load_reprompt_tune()` → `read_tune_file("reprompt")` | Lines 699–703 |
| `core/hotkeys.py` | `read_tune_file("dictation")` | Lines 657–658 |
| `core/agent.py` | `read_tune_file("agent")` | Lines 1399–1400 |

Adding a new tuner requires adding a new hardcoded loader in the consumer. **Violation.**

### 2.3 Shared Utility Sprawl

All three tuners import from shared utils:

```python
from ..utils.convergence import ConvergenceChecker
from ..utils.feature_extraction import embed_text, cosine_similarity
from ..utils.model_persistence import TuneModelPersistence
```

While shared utilities are not inherently bad, `TuneModelPersistence` writes to paths derived from `feature_name`, `user_id`, and `task_signature` — creating a parallel storage system that competes with `single_file_store.py`. A tuner that wants full control must fight two storage layers.

### 2.4 The Orchestrator/Middleware Are Actually Fine

`orchestrator.py` and `middleware.py` are already generic — they use `TuneBase.create(feature_name)` and delegate all work to the plugin. **These do NOT need changes.** They are the only part of the architecture that already respects the single-file principle.

---

## 3. Proposed Architecture: The One-File Tuner

### 3.1 Core Principle

> **Each tuner file is a sovereign plugin.** It owns its storage, its learning, its runtime behavior, and its integration with the feature consumer. The orchestrator never knows more than the `TuneBase` interface.

### 3.2 What Changes in `TuneBase`

Add two new abstract methods that enforce self-containment:

```python
class TuneBase(ABC):
    # ... existing methods ...

    @property
    @abstractmethod
    def canonical_storage_path(self) -> Path:
        """Return the file path this tuner reads/writes at runtime.
        
        Example: Path("data/tune_models/dictation_tune.json")
        """
        raise NotImplementedError

    @abstractmethod
    def load_runtime_state(self) -> Dict[str, Any]:
        """Load the currently deployed tune from canonical_storage_path.
        
        Called by the feature consumer on the hot path.
        Returns empty dict if no tune exists.
        """
        raise NotImplementedError
```

### 3.3 What Each Tuner File Contains

A single tuner file (e.g., `dictation_tuner.py`) contains **everything**:

1. **Feature-specific data structures** (`CorrectionEntry`, `CorrectionTrie`, `ContextDomainClassifier`)
2. **Learning algorithm** (`learn()`, `validate()`)
3. **Deployment** (`deploy()` → writes to `self.canonical_storage_path`)
4. **Runtime application** (`apply()` → reads from `self.canonical_storage_path`)
5. **Default config** (`get_default_config()`)
6. **Feature-consumer helper** — a module-level function the consumer calls directly

```python
# At the bottom of dictation_tuner.py — the ONLY public API hotkeys.py needs

def get_dictation_runtime_config() -> Dict[str, Any]:
    """Hot-path entry for core/hotkeys.py.
    
    Reads the latest deployed dictation tune directly.
    No orchestrator, no middleware, no shared registry.
    """
    path = DictationTuner.canonical_storage_path  # class property
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"correction_map": {}, "tune_id": None, "domain": "general"}
```

### 3.4 What Gets Deleted

- **`core/tune_hub/single_file_store.py`** — Entire file. Each tuner manages its own path.
- **Hardcoded `_load_reprompt_tune()` in `core/wizprompt.py`** — Replaced by a generic call or direct tuner import.
- **Hardcoded `read_tune_file("dictation")` in `core/hotkeys.py`** — Replaced by `from core.tune_hub.tuners.dictation_tuner import get_dictation_runtime_config`.
- **Hardcoded `read_tune_file("agent")` in `core/agent.py`** — Replaced by direct tuner import.

### 3.5 What Stays the Same

- `core/tune_hub/orchestrator.py` — Already generic. No changes.
- `core/tune_hub/middleware.py` — Already generic. No changes.
- `core/tune_hub/base.py` — Add two abstract methods only.
- `core/tune_hub/tune_base.py` — Add two abstract methods only.
- Tests in `core/tune_hub/tests/` — Updated, but structure stays.

---

## 4. File Touch Map: Before vs After

### Before (Current State)

| Action | Files Touched |
|---|---|
| Add new tuner (e.g., `browser_agent`) | `tuners/browser_agent_tuner.py` **+** `single_file_store.py` **+** consumer file **+** `guardrails.py` (INJECTABLE_KEYS) |
| Modify dictation learning logic | `dictation_tuner.py` **+** maybe `single_file_store.py` |
| Modify reprompt runtime behavior | `reprompt_tuner.py` **+** `wizprompt.py` |

### After (Proposed State)

| Action | Files Touched |
|---|---|
| Add new tuner (e.g., `browser_agent`) | `tuners/browser_agent_tuner.py` **only** |
| Modify dictation learning logic | `dictation_tuner.py` **only** |
| Modify reprompt runtime behavior | `reprompt_tuner.py` **only** |

The only one-time refactor work touches:
- `core/tune_hub/base.py`
- `core/tune_hub/tune_base.py`
- `core/tune_hub/single_file_store.py` (deleted)
- `core/wizprompt.py`
- `core/hotkeys.py`
- `core/agent.py`
- `core/tune_hub/tuners/dictation_tuner.py`
- `core/tune_hub/tuners/reprompt_tuner.py`
- `core/tune_hub/tuners/agent_tuner.py`

---

## 5. Design Decisions & Trade-offs

### Decision 1: Tuner owns its storage path

**Option A:** Tuner defines `canonical_storage_path` property.  
**Option B:** Orchestrator assigns path via convention (`data/tune_models/{feature_name}_tune.json`).

**Chosen: A.** The tuner knows best where its data lives. The orchestrator should not guess. However, we provide a convention helper so tuners don't have to think about it:

```python
# In tune_base.py — optional helper
@staticmethod
def default_storage_path(feature_name: str) -> Path:
    return Path(f"data/tune_models/{feature_name}_tune.json")
```

### Decision 2: Feature consumer imports tuner directly

**Option A:** Consumer imports the tuner module and calls its helper function.  
**Option B:** Consumer goes through `TuneHub.resolve_tune()` via middleware.

**Chosen: Keep both.** The middleware path stays for the orchestrated flow. The direct import is a **fast-path fallback** that guarantees the consumer always gets the latest tune even if middleware is unavailable. This is what the code already does — we just make it cleaner.

### Decision 3: TuneModelPersistence stays or goes?

`TuneModelPersistence` writes experiment history (observations, recipes) to `data/tune_models/{user_id}/{feature_name}/{task}/*.json`. This is **not** the deployed tune — it's the learning history. It should stay as a shared utility because:
- All tuners need to persist experiment history
- The path structure is generic (user → feature → task)
- It does not compete with the canonical tune file

**Decision:** Keep `TuneModelPersistence` as a shared utility. It is not the violation.

---

## 6. Success Criteria

1. **Adding a new tuner requires creating exactly 1 file.** No edits to shared registries, no edits to consumers.
2. **Modifying an existing tuner requires touching exactly 1 file.** The tuner file itself.
3. **`single_file_store.py` is deleted.**
4. **No hardcoded feature names in `wizprompt.py`, `hotkeys.py`, or `agent.py`.**
5. **All existing tests pass after refactor.**
6. **`python -c "import main"` succeeds.**

---

## 7. Appendix: Future Tuner Template

```python
"""BrowserAgentTuner — learns browser automation patterns.

THIS FILE IS THE ENTIRE FEATURE. Nothing else needs to change.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult


class BrowserAgentTuner(TuneBase, feature_name="browser_agent"):
    """Self-contained tuner for browser automation."""

    # ── Self-contained storage ──
    @property
    def canonical_storage_path(self) -> Path:
        return Path("data/tune_models/browser_agent_tune.json")

    def load_runtime_state(self) -> Dict[str, Any]:
        if self.canonical_storage_path.exists():
            try:
                with open(self.canonical_storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self.get_default_config("")

    # ── PHASE 0: Static Analysis ──
    def estimate_complexity(self, task: str, context: Optional[Dict] = None) -> ComplexityLevel:
        return ComplexityLevel.MEDIUM

    # ── PHASE 1: Learning ──
    def learn(self, task, budget, context=None, judge=None) -> LearnedModel:
        ...

    # ── PHASE 2: Validation ──
    def validate(self, model, hold_out_tasks=None, judge=None) -> bool:
        ...

    # ── PHASE 3: Deployment ──
    def deploy(self, model) -> Dict[str, Any]:
        manifest = {...}
        self.canonical_storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.canonical_storage_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)
        return manifest

    # ── RUNTIME: Apply ──
    def apply(self, model, feature_input) -> Dict[str, Any]:
        tune_data = self.load_runtime_state()
        feature_input.update(tune_data)
        return feature_input

    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"patterns": [], "tune_id": None}

    def allowed_injectable_keys(self) -> frozenset[str]:
        return frozenset({"patterns", "tune_id"})


# ── FEATURE CONSUMER FAST-PATH ──
# This is the ONLY API core/agent.py (or whoever) needs.

def get_browser_agent_runtime_config() -> Dict[str, Any]:
    """Return the latest deployed browser-agent tune."""
    return BrowserAgentTuner().load_runtime_state()
```
