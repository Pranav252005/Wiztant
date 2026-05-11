# TuneHub Boundary Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden TuneHub so it can only improve existing registered features and is physically incapable of modifying system files, mutating non-feature state, or injecting arbitrary keys into feature inputs.

**Architecture:** Add a `TuneBoundaryGuard` singleton that enforces an explicit allow-list of features, injectable keys per feature, and safe persistence paths. Wire this guard into `TuneBase.safe_apply()`, `TuneHub.resolve_tune()`, `TuneApplicationMiddleware.apply()`, and `TuneModelPersistence` so every data mutation and file write is validated before it happens.

**Tech Stack:** Python 3.11, pytest, existing TuneHub core (`core/tune_hub/`).

---

## Task 1: TuneBoundaryGuard Core

**Files:**
- Create: `core/tune_hub/guardrails.py`
- Test: `core/tune_hub/tests/test_guardrails.py`

**Step 1: Write the failing test**
Create `core/tune_hub/tests/test_guardrails.py` with tests for:
- `validate_feature_name` rejects unknown features
- `validate_injection` rejects modifications to non-allowed keys
- `validate_injection` rejects deletion of existing keys
- `sanitize_persistence_path` rejects `..` and null bytes
- `ensure_immutable_input` returns a deep copy

**Step 2: Run test to verify it fails**
```bash
cd /home/pranavvv/Documents/Projects/Wiztant && python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 3: Write minimal implementation**
Create `core/tune_hub/guardrails.py` containing:
- `ALLOWED_FEATURES: frozenset[str] = {"reprompt", "dictation", "agent"}`
- `INJECTABLE_KEYS: dict[str, frozenset[str]]`
  - reprompt: `{"persona_weights", "tune_id", "task_type"}`
  - dictation: `{"correction_map", "tune_id", "domain", "auto_apply_threshold", "text", "applied_corrections"}`
  - agent: `{"recipe", "tune_id", "dsl_code", "recipe_hint"}`
- `TuneBoundaryGuard` class with:
  - `validate_feature_name(feature_name: str) -> tuple[bool, str]`
  - `validate_injection(feature_name: str, original: dict, modified: dict) -> tuple[bool, str]` — ensures only allowed keys are added/modified, no keys are removed, and existing values of non-injectable keys are unchanged
  - `sanitize_persistence_path(base_dir: Path, user_id: str, feature_name: str, task_signature: str, suffix: str) -> Path` — rejects `..`, null bytes, and ensures final path is under `base_dir`
  - `ensure_immutable_input(feature_input: dict) -> dict` — `copy.deepcopy`

**Step 4: Run test to verify it passes**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 5: Commit**
```bash
git add core/tune_hub/guardrails.py core/tune_hub/tests/test_guardrails.py
git commit -m "feat(tunehub): add TuneBoundaryGuard with feature/key allow-lists and path sanitization"
```

---

## Task 2: Harden TuneModelPersistence

**Files:**
- Modify: `core/tune_hub/utils/model_persistence.py`
- Test: `core/tune_hub/tests/test_guardrails.py` (append)

**Step 1: Write the failing test**
Add tests to `test_guardrails.py`:
- `save_json` with `..` in `user_id` raises `ValueError`
- `save_json` with null byte raises `ValueError`
- `save_json` with `.pkl` suffix raises `ValueError` (restrict to `.json`, `.jsonl`)
- Loaded path is always inside `base_dir`

**Step 2: Run test to verify it fails**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 3: Write minimal implementation**
Modify `core/tune_hub/utils/model_persistence.py`:
- Import `TuneBoundaryGuard` at the top (lazy import inside methods to avoid circular deps if needed)
- In `_path()`, call `TuneBoundaryGuard.sanitize_persistence_path()`
- In `save_json()`, `save_checkpoint()`, `save_observations()`, validate that `suffix` is in `ALLOWED_SUFFIXES = {".json", ".jsonl", ".pkl"}`
- Harden `_path()` to also replace `..` with `_` and strip null bytes

**Step 4: Run test to verify it passes**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 5: Commit**
```bash
git add core/tune_hub/utils/model_persistence.py core/tune_hub/tests/test_guardrails.py
git commit -m "feat(tunehub): harden TuneModelPersistence against path traversal and unsafe suffixes"
```

---

## Task 3: Add Safe Apply to TuneBase and Fix Tuners

**Files:**
- Modify: `core/tune_hub/tune_base.py`
- Modify: `core/tune_hub/tuners/agent_tuner.py`
- Modify: `core/tune_hub/tuners/dictation_tuner.py`
- Modify: `core/tune_hub/tuners/reprompt_tuner.py`
- Test: `core/tune_hub/tests/test_guardrails.py` (append)

**Step 1: Write the failing test**
Add tests:
- `TuneBase.safe_apply` raises `TuneBoundaryViolation` when a tuner tries to inject a disallowed key
- `AgentTuner.apply` no longer mutates `feature_input["task"]`, instead uses `recipe_hint`
- `DictationTuner.apply` only touches allowed keys
- `RePromptTuner.apply` only touches allowed keys

**Step 2: Run test to verify it fails**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 3: Write minimal implementation**
Modify `core/tune_hub/tune_base.py`:
- Add `TuneBoundaryViolation(Exception)` class
- Add `allowed_injectable_keys() -> frozenset[str]` abstract method (or return a class attribute)
- Add `safe_apply(model, feature_input)` that:
  1. Deep-copies `feature_input`
  2. Calls `self.apply(model, copied_input)`
  3. Calls `TuneBoundaryGuard.validate_injection()`
  4. Raises `TuneBoundaryViolation` on failure
  5. Returns validated result

Modify `core/tune_hub/tuners/agent_tuner.py`:
- Add `allowed_injectable_keys()` returning `{"recipe", "tune_id", "dsl_code", "recipe_hint"}`
- In `apply()`, remove the line that mutates `feature_input["task"]`. Instead, put the hint in `feature_input["recipe_hint"]` only.

Modify `core/tune_hub/tuners/dictation_tuner.py`:
- Add `allowed_injectable_keys()` returning `{"correction_map", "tune_id", "domain", "auto_apply_threshold", "text", "applied_corrections"}`

Modify `core/tune_hub/tuners/reprompt_tuner.py`:
- Add `allowed_injectable_keys()` returning `{"persona_weights", "tune_id", "task_type"}`

**Step 4: Run test to verify it passes**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 5: Commit**
```bash
git add core/tune_hub/tune_base.py core/tune_hub/tuners/agent_tuner.py core/tune_hub/tuners/dictation_tuner.py core/tune_hub/tuners/reprompt_tuner.py core/tune_hub/tests/test_guardrails.py
git commit -m "feat(tunehub): add safe_apply to TuneBase and restrict tuner injection keys"
```

---

## Task 4: Wire Guardrails into Orchestrator and Middleware

**Files:**
- Modify: `core/tune_hub/orchestrator.py`
- Modify: `core/tune_hub/middleware.py`
- Test: `core/tune_hub/tests/test_guardrails.py` (append)

**Step 1: Write the failing test**
Add tests:
- `TuneHub.resolve_tune` raises `TuneBoundaryViolation` for unknown `feature_name`
- `TuneHub.tune_feature` raises `TuneBoundaryViolation` for unknown `feature_name`
- `TuneApplicationMiddleware.apply` deep-copies input so caller's dict is untouched
- `TuneApplicationMiddleware.apply` logs/raises on boundary violation when fallback is disabled

**Step 2: Run test to verify it fails**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 3: Write minimal implementation**
Modify `core/tune_hub/orchestrator.py`:
- Import `TuneBoundaryGuard`, `TuneBoundaryViolation`
- In `resolve_tune()`, validate `feature_name` against `TuneBoundaryGuard.validate_feature_name()` before creating tuner
- In `tune_feature()`, validate `feature_name` before creating tuner
- In `resolve_tune()`, call `tuner.safe_apply()` instead of `tuner.apply()`

Modify `core/tune_hub/middleware.py`:
- Import `TuneBoundaryGuard`, `TuneBoundaryViolation`
- In `apply()`, deep-copy `feature_input` before passing to `resolve_tune`
- Add `_log_violation` helper that writes to a logger
- On `TuneBoundaryViolation`, if `_fallback_enabled` is True, return original input but log the violation; if False, re-raise

**Step 4: Run test to verify it passes**
```bash
python -m pytest core/tune_hub/tests/test_guardrails.py -v
```

**Step 5: Run full TuneHub test suite**
```bash
python -m pytest core/tune_hub/tests/ -v
```

**Step 6: Commit**
```bash
git add core/tune_hub/orchestrator.py core/tune_hub/middleware.py core/tune_hub/tests/test_guardrails.py
git commit -m "feat(tunehub): wire boundary guardrails into orchestrator and middleware"
```

---

## Task 5: Update Existing TuneHub Tests for New Behavior

**Files:**
- Modify: `core/tune_hub/tests/test_tuners.py`
- Modify: `core/tune_hub/tests/test_middleware.py`

**Step 1: Write the failing test**
Already covered by running existing tests; expect failures due to `agent_tuner` no longer mutating `task`.

**Step 2: Run existing tests**
```bash
python -m pytest core/tune_hub/tests/test_tuners.py core/tune_hub/tests/test_middleware.py -v
```

**Step 3: Fix AgentTuner apply test**
In `test_tuners.py`, update `TestAgentTuner.test_apply` to assert `recipe_hint` contains the recipe reference instead of `task` being modified.

**Step 4: Verify all TuneHub tests pass**
```bash
python -m pytest core/tune_hub/tests/ -v
```

**Step 5: Commit**
```bash
git add core/tune_hub/tests/test_tuners.py core/tune_hub/tests/test_middleware.py
git commit -m "test(tunehub): update existing tests for boundary-safe apply behavior"
```

---

## Task 6: Final Integration Verification

**Step 1: Python import check**
```bash
python -c "from core.tune_hub.guardrails import TuneBoundaryGuard; from core.tune_hub.tune_base import TuneBase; print('imports OK')"
```

**Step 2: Full pytest**
```bash
python -m pytest core/tune_hub/tests/ -v --tb=short
```

**Step 3: Commit**
```bash
git add docs/superpowers/plans/2026-05-04-tunehub-boundary-guardrails.md
git commit -m "docs(tunehub): add boundary guardrails implementation plan"
```

---

## Self-Review

| Requirement | Task |
|---|---|
| Only edit existing features | Task 1 (allow-list), Task 4 (orchestrator validation) |
| Don't edit system files | Task 1 (path sanitization), Task 2 (persistence hardening) |
| Don't mutate non-allowed keys | Task 1 (`validate_injection`), Task 3 (`safe_apply`) |
| Deep-copy input to protect caller | Task 3 (`safe_apply`), Task 4 (middleware copy) |
| Log violations instead of hiding | Task 4 (middleware logging) |
| Fix AgentTuner task mutation | Task 3 (agent_tuner.py) |

**Placeholder scan:** None. Every step contains concrete code locations and commands.

**Type consistency:** `validate_feature_name` and `validate_injection` both return `(bool, reason: str)` tuples. `safe_apply` returns `dict` and raises `TuneBoundaryViolation` on failure.

---

## Execution Handoff

This plan is ready for **Inline Execution** using executing-plans. All six tasks can be executed sequentially by a single agent because they are tightly coupled (each task builds on the previous).
