# TuneHub Single-File Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor TuneHub so each tuner is a sovereign, single-file plugin. Adding or modifying a tuner touches exactly 1 file.

**Architecture:** Enforce self-containment via `TuneBase` abstract methods (`canonical_storage_path`, `load_runtime_state`). Delete the shared `single_file_store.py` registry. Remove hardcoded tune loading from feature consumers (`wizprompt.py`, `hotkeys.py`, `agent.py`).

**Tech Stack:** Python 3.11, existing pytest suite, zero new dependencies.

---

## Task 1: Enforce Self-Containment in `TuneBase`

**Files:**
- Modify: `core/tune_hub/tune_base.py`
- Modify: `core/tune_hub/base.py` (if needed for imports)

**Steps:**
- [ ] **Step 1:** Add `canonical_storage_path` abstract property to `TuneBase`
- [ ] **Step 2:** Add `load_runtime_state()` abstract method to `TuneBase`
- [ ] **Step 3:** Add optional helper `TuneBase.default_storage_path(feature_name: str) -> Path` for convention-based paths
- [ ] **Step 4:** Run `python -c "import core.tune_hub.tune_base"` to verify no import errors
- [ ] **Step 5:** Run `pytest core/tune_hub/tests/test_base.py -v` to verify base tests still pass

**Verification:**
```bash
python -c "from core.tune_hub.tune_base import TuneBase; print('TuneBase OK')"
pytest core/tune_hub/tests/test_base.py -v
```

---

## Task 2: Refactor `DictationTuner` to Be Self-Contained

**Files:**
- Modify: `core/tune_hub/tuners/dictation_tuner.py`

**Steps:**
- [ ] **Step 1:** Add `canonical_storage_path` property returning `Path("data/tune_models/dictation_tune.json")`
- [ ] **Step 2:** Add `load_runtime_state()` method that reads from `canonical_storage_path` and returns the tune dict
- [ ] **Step 3:** Rewrite `deploy()` to write directly to `self.canonical_storage_path` instead of calling `write_tune_file()`
- [ ] **Step 4:** Rewrite `apply()` to call `self.load_runtime_state()` instead of `read_tune_file()`
- [ ] **Step 5:** Rewrite `get_default_config()` to call `self.load_runtime_state()` instead of `read_tune_file()`
- [ ] **Step 6:** Remove `from ..single_file_store import read_tune_file, write_tune_file` import
- [ ] **Step 7:** Add module-level helper `get_dictation_runtime_config()` at bottom of file for `core/hotkeys.py`
- [ ] **Step 8:** Run dictation tuner tests

**Verification:**
```bash
pytest core/tune_hub/tests/test_tuners.py::TestDictationTuner -v
```

---

## Task 3: Refactor `RePromptTuner` to Be Self-Contained

**Files:**
- Modify: `core/tune_hub/tuners/reprompt_tuner.py`

**Steps:**
- [ ] **Step 1:** Add `canonical_storage_path` property returning `Path("data/tune_models/reprompt_tune.json")`
- [ ] **Step 2:** Add `load_runtime_state()` method
- [ ] **Step 3:** Rewrite `deploy()` to write directly to `self.canonical_storage_path`
- [ ] **Step 4:** Rewrite `apply()` to use `self.load_runtime_state()`
- [ ] **Step 5:** Rewrite `get_default_config()` to use `self.load_runtime_state()`
- [ ] **Step 6:** Remove `from ..single_file_store import read_tune_file, write_tune_file` import
- [ ] **Step 7:** Add module-level helper `get_reprompt_runtime_config()` at bottom of file for `core/wizprompt.py`
- [ ] **Step 8:** Run reprompt tuner tests

**Verification:**
```bash
pytest core/tune_hub/tests/test_tuners.py::TestRePromptTuner -v
```

---

## Task 4: Refactor `AgentTuner` to Be Self-Contained

**Files:**
- Modify: `core/tune_hub/tuners/agent_tuner.py`

**Steps:**
- [ ] **Step 1:** Add `canonical_storage_path` property returning `Path("data/tune_models/agent_tune.json")`
- [ ] **Step 2:** Add `load_runtime_state()` method
- [ ] **Step 3:** Rewrite `deploy()` to write directly to `self.canonical_storage_path`
- [ ] **Step 4:** Rewrite `apply()` to use `self.load_runtime_state()`
- [ ] **Step 5:** Rewrite `get_default_config()` to use `self.load_runtime_state()`
- [ ] **Step 6:** Remove `from ..single_file_store import read_tune_file, write_tune_file` import
- [ ] **Step 7:** Add module-level helper `get_agent_runtime_config()` at bottom of file for `core/agent.py`
- [ ] **Step 8:** Run agent tuner tests

**Verification:**
```bash
pytest core/tune_hub/tests/test_tuners.py::TestAgentTuner -v
```

---

## Task 5: Delete `single_file_store.py` and Update Imports

**Files:**
- Delete: `core/tune_hub/single_file_store.py`
- Modify: `core/tune_hub/__init__.py` (remove re-exports if any)

**Steps:**
- [ ] **Step 1:** Confirm no other file imports from `single_file_store` (grep the entire `core/` tree)
- [ ] **Step 2:** Delete `core/tune_hub/single_file_store.py`
- [ ] **Step 3:** Check `core/tune_hub/__init__.py` and remove any re-exports of `read_tune_file` / `write_tune_file`
- [ ] **Step 4:** Check `core/tune_hub/tests/test_storage.py` — if it tests `single_file_store`, update or delete those tests
- [ ] **Step 5:** Run full TuneHub test suite

**Verification:**
```bash
grep -r "single_file_store" core/ --include="*.py"
pytest core/tune_hub/tests/ -v
```

---

## Task 6: Refactor `core/wizprompt.py` to Use Generic RePrompt API

**Files:**
- Modify: `core/wizprompt.py`

**Steps:**
- [ ] **Step 1:** Delete `_load_reprompt_tune()` function (lines 688–694)
- [ ] **Step 2:** Replace `_load_reprompt_tune()` usage in `optimize_prompt_with_dynamic_agents()` with direct import:
  ```python
  from core.tune_hub.tuners.reprompt_tuner import get_reprompt_runtime_config
  tune_data = get_reprompt_runtime_config()
  persona_weights = tune_data.get("persona_weights")
  ```
- [ ] **Step 3:** Verify no other `read_tune_file` or `_load_reprompt_tune` references exist in `wizprompt.py`
- [ ] **Step 4:** Run `python -c "import core.wizprompt"` to verify imports

**Verification:**
```bash
python -c "import core.wizprompt; print('wizprompt OK')"
```

---

## Task 7: Refactor `core/hotkeys.py` to Use Generic Dictation API

**Files:**
- Modify: `core/hotkeys.py`

**Steps:**
- [ ] **Step 1:** Find the fallback `read_tune_file("dictation")` block (around lines 657–658)
- [ ] **Step 2:** Replace with:
  ```python
  from core.tune_hub.tuners.dictation_tuner import get_dictation_runtime_config
  tune_data = get_dictation_runtime_config()
  ```
- [ ] **Step 3:** Verify no other `read_tune_file` references exist in `hotkeys.py`
- [ ] **Step 4:** Run `python -c "import core.hotkeys"` to verify imports

**Verification:**
```bash
python -c "import core.hotkeys; print('hotkeys OK')"
```

---

## Task 8: Refactor `core/agent.py` to Use Generic Agent API

**Files:**
- Modify: `core/agent.py`

**Steps:**
- [ ] **Step 1:** Find the fallback `read_tune_file("agent")` block (around lines 1399–1400)
- [ ] **Step 2:** Replace with:
  ```python
  from core.tune_hub.tuners.agent_tuner import get_agent_runtime_config
  tune_data = get_agent_runtime_config()
  ```
- [ ] **Step 3:** Verify no other `read_tune_file` references exist in `agent.py`
- [ ] **Step 4:** Run `python -c "import core.agent"` to verify imports

**Verification:**
```bash
python -c "import core.agent; print('agent OK')"
```

---

## Task 9: Guardrails Update (If Needed)

**Files:**
- Modify: `core/tune_hub/guardrails.py` (if `INJECTABLE_KEYS` references single_file_store)

**Steps:**
- [ ] **Step 1:** Check if `guardrails.py` imports from `single_file_store`
- [ ] **Step 2:** If yes, refactor to use tuner class directly or remove dependency
- [ ] **Step 3:** Run guardrails tests

**Verification:**
```bash
pytest core/tune_hub/tests/test_guardrails.py -v
```

---

## Task 10: Full Integration Verification

**Steps:**
- [ ] **Step 1:** Run ALL TuneHub tests
- [ ] **Step 2:** Run `python -c "import main"` for app-level import verification
- [ ] **Step 3:** Create a temporary 4th tuner file to prove the "1-file add" principle works:
  ```python
  # core/tune_hub/tuners/test_single_file_proof.py
  from pathlib import Path
  from ..tune_base import TuneBase
  class ProofTuner(TuneBase, feature_name="proof"):
      @property
      def canonical_storage_path(self): return Path("data/tune_models/proof_tune.json")
      def load_runtime_state(self): return {}
      def estimate_complexity(self, task, context=None): from ..base import ComplexityLevel; return ComplexityLevel.LOW
      def learn(self, task, budget, context=None, judge=None): raise NotImplementedError
      def validate(self, model, hold_out_tasks=None, judge=None): return True
      def deploy(self, model): return {}
      def apply(self, model, feature_input): return feature_input
      def get_default_config(self, task): return {}
  ```
- [ ] **Step 4:** Verify `TuneBase.create("proof")` works without touching any shared file
- [ ] **Step 5:** Delete the proof tuner file

**Verification:**
```bash
pytest tests/ core/tune_hub/tests/ -v
python -c "import main; print('Full app OK')"
```

---

## Rollback Strategy

If any verification fails catastrophically:
1. All changes are surgical — each task is isolated to 1–2 files.
2. `single_file_store.py` can be restored from git if needed.
3. The orchestrator and middleware are untouched — they continue to work regardless.
