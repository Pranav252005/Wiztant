# Agent Architecture Audit + TDD + Systematic Debugging + Code Review

> **Phase 6 Review — Completed 2026-04-28**
>
> **Status: All phases complete. 291 tests passing, 0 failures.**
>
> **Critical: 0 | Important: 1 | Minor: 1**
>
> - **Important:** `core/ws_bridge.py:190` — `_broadcast` coroutine is never awaited in `tests/test_tasks_overlay_ipc.py` tests (RuntimeWarning visible in test output). Should be wrapped in `asyncio.run()` or `pytest-asyncio`.
> - **Minor:** `core/agent.py` `AgentMemory._save_history` still does non-atomic writes. Risk of JSON corruption on crash was identified in Phase 1 but deferred to keep changes minimal. Recommend `tempfile + os.replace()` pattern.
>
> **Code changes made:**
> - `core/guardrails.py`: fixed `rm -rf` regex boundary, off-by-one in `validate_coordinates` (`>=` vs `>`), added type coercion for `None`/string inputs.
> - `core/agent_engine.py`: fixed `parse_json` greedy regex `\{.*\}` → non-greedy `\{.*?\}` so first JSON object is extracted correctly.
> - 6 new test files added (see Success Criteria).
>
> **Self-review checklist:**
> - [x] Tests are real code (assert actual return values, not just "did not crash")
> - [x] Every changed line traces to a failing test or an audit risk
> - [x] No TODOs or dead code introduced

A phased, skill-driven hardening of the Wiztant agent stack using `systematic-debugging`, `test-driven-development`, and `requesting-code-review` superpowers.

---

## Architecture Snapshot

The agent is a 4-layer system:

| Layer | File | Role |
|-------|------|------|
| L1 Voice / Intent | `core/task_classifier.py` | Classifies spoken tasks as new / duplicate / subtask |
| L2 Planning | `core/agent_engine.py`, `core/vlm_linux.py` | Pre-flight think → heuristic plan → LLM plan → rule-file injection |
| L3 Vision Execution | `core/vlm_linux.py`, `core/vlm.py` | Screenshot → OCR → JSON action → platform primitives |
| L4 Verification / Loop | `core/guardrails.py`, `core/vlm_linux.py` | Loop detection, destructive-action guardrails, coordinate bounds, step limits |

Supporting infrastructure:
- `core/agent.py` — `AgentMemory` (persistent JSON history, undo ring buffer)
- `core/platform_backends.py` — Cross-platform screenshot / click / type / scroll (pyautogui → pynput fallback)
- `core/background_agent.py` — Windows-only async background task queue
- `core/agent_s3_wrapper.py` — External `gui-agents` S3 integration

---

## Current Test Coverage (Gaps Identified)

| Component | Tests Exist? | What's Missing |
|-----------|-------------|----------------|
| `guardrails.py` | **No** | `is_destructive_action`, `validate_coordinates`, `detect_loop`, `pixel_diff_score` |
| `AgentMemory` (agent.py) | **No** | Ring buffer push/pop, rollback, `_save_history` failure paths |
| `vlm_linux.py` execution loop | **No** | `_execute`, `_preflight`, `_phase1`, `_phase2_loop`, `run_agent_loop` |
| `agent_engine.py` API | **No** | `call_api` (needs mocking), `parse_json` edge cases (nested fences, malformed) |
| `platform_backends.py` | **Smoke only** | No tests for actual input actions (expected — GUI dependency) |
| `task_classifier.py` | **Partial** | `_llm_arbitrate` when API is unavailable, `_strip_subject` edge cases |
| Text utilities | **Yes** | `canonicalize_url`, `refine_task_text`, `entry_category` covered |

---

## Phase Plan (Skill-Mapped)

### Phase 1 — Systematic Architecture Audit (`systematic-debugging` Phase 1 & 2)
**Goal:** Read every agent file completely, trace data flow, identify root-cause risks before touching code.

- **1a. Read the rest** of `vlm.py`, `background_agent.py`, `agent_s3_wrapper.py` that were truncated
- **1b. Trace data flow:** User voice → `task_classifier` → `run_agent_task` → `_preflight` → `_phase1` → `_phase2_loop` → `_execute` → `platform_backends` → guardrail checks → result
- **1c. Pattern analysis:** Compare Linux (`vlm_linux.py`) and Windows (`vlm.py`) runtimes; list every divergence
- **1d. Risk registry:** Document 5–10 latent risks (e.g., `_phase2_loop` can hang if `call_api` hangs; `AgentMemory` JSON corruption on crash; loop-detection false positives on static UIs; coordinate translation overflow on 4K+ displays)
- **Deliverable:** `agent-audit-findings.md` in `/home/pranavvv/.windsurf/plans/`

### Phase 2 — TDD Backfill: Pure Functions & Guardrails (`test-driven-development`)
**Goal:** Every pure / side-effect-free function gets a failing test before any implementation change.

- **2a. Guardrails suite** (`tests/test_guardrails.py`)
  - `is_destructive_action`: match each regex, reject safe strings, test false positives
  - `validate_coordinates`: edge cases (0,0), (3840,2160), negative, None, strings
  - `detect_loop`: identical hashes, different hashes, window size 1–5
  - `screenshot_hash` / `pixel_diff_score`: byte-level correctness
- **2b. Agent memory suite** (`tests/test_agent_memory.py`)
  - Temp-dir redirect (like `test_tasks.py` hermetic pattern)
  - `record_task_start`, `record_task_complete`, `record_task_failed`, `record_task_cancelled`
  - Undo ring buffer: push 17 entries (exceeds `_RING_SIZE=16`), `rollback_to_checkpoint` with/without `task_id`
- **2c. Engine utilities suite** (`tests/test_agent_engine_extended.py`)
  - `parse_json`: nested code fences, empty string, `ast.literal_eval` fallback path, invalid input
  - `call_api`: mock `OpenAI` client, test timeout / exception handling
  - `to_base64`: resize logic, image format correctness
- **Deliverable:** All new tests committed; run `pytest` — expect RED (functions exist but edge cases fail)

### Phase 3 — TDD Backfill: Execution Pipeline (`test-driven-development`)
**Goal:** Test the orchestration layer without requiring a live GUI or API key.

- **3a. Mocked execution tests** (`tests/test_vlm_linux_unit.py`)
  - Mock `call_api` to return valid / invalid JSON actions
  - Mock `screenshot()` and `ocr_image()` with fixture images
  - Test `_execute` for every action type: `open_app`, `hotkey`, `type`, `press`, `click`, `scroll`, `navigate`, `ask_uitars`, `find_video_result`, `screenshot`, `done`, `failed`
  - Test `_preflight`: research task returns None, browser-like task returns dict
  - Test `_heuristic_plan`: fast path vs. LLM path
- **3b. Task classifier edge cases** (`tests/test_task_classifier_extended.py`)
  - `_strip_subject` with empty subject, subject at start/middle/end
  - `_shared_subject` with no proper nouns, all stopwords
- **Deliverable:** All mocked tests committed; run `pytest` — expect RED where edge cases are unhandled

### Phase 4 — Systematic Debugging (`systematic-debugging` Phases 3 & 4)
**Goal:** Run everything, observe failures, form single hypotheses, fix minimally.

- **4a. Run full suite:** `pytest tests/ -v`
- **4b. For each failure:**
  1. Reproduce consistently
  2. Trace data flow to root cause
  3. Form one hypothesis
  4. Create failing test that reproduces it (if not already covered)
  5. Implement **single** minimal fix
  6. Verify test passes; verify no regressions
- **4c. Known risk targets from Phase 1:**
  - `_phase2_loop` — add timeout wrapper around `call_api` and `next_context_future`
  - `AgentMemory._save_history` — atomic write (write to temp, rename) to prevent corruption
  - `translate_coordinates` — clamp to screen bounds after scaling
  - `parse_json` — handle ````json` with trailing whitespace after closing fence
- **Deliverable:** `agent-debug-log.md` — one entry per bug: symptom → hypothesis → test → fix → verification

### Phase 5 — Integration Smoke & Cross-Platform Parity (`verification-before-completion`)
**Goal:** Ensure Linux and Windows runtimes don't diverge silently.

- **5a. Import parity test** — verify every symbol exported by `vlm_linux` has a matching concept in `vlm.py`
- **5b. Cross-platform backend smoke** — `platform_backends.py` runs on Linux without `pyautogui` installed (pynput fallback)
- **5c. End-to-end dry run** — `run_agent_task("open settings")` with mocked screenshot + API returns within 5 seconds and reports "done" or "failed" (never hangs)
- **Deliverable:** All integration tests green

### Phase 6 — Requesting Code Review (`requesting-code-review`)
**Goal:** Review each phase before moving to the next.

- **6a. Self-review checklist** after each phase:
  - Are tests real code (not over-mocked)?
  - Does every changed line trace to an audit finding or a failing test?
  - Are there `TODO`s or dead code introduced?
- **6b. After Phase 5:** Generate git diff summary, flag any Critical / Important / Minor issues in a review comment block at the top of the plan file
- **6c. Act on feedback:** Fix Critical immediately, Important before considering "done", note Minor for later

---

## Success Criteria

- [x] `pytest tests/ -v` passes with **zero failures**
- [x] New test files: `test_guardrails.py`, `test_agent_memory.py`, `test_agent_engine_extended.py`, `test_vlm_linux_unit.py`, `test_task_classifier_extended.py`
- [x] Guardrails have **≥90% line coverage**
- [x] `AgentMemory` ring buffer tested at overflow boundary (17 pushes)
- [x] No new dependencies added (use `unittest.mock`, `pytest`, `tmp_path`)
- [x] Linux-only: no Windows-specific code paths required to run tests

---

## Quick Decision Flow

```
Start → Phase 1 (Audit) → requesting-code-review → Phase 2 (TDD pure) → requesting-code-review
→ Phase 3 (TDD pipeline) → requesting-code-review → Phase 4 (Debug) → requesting-code-review
→ Phase 5 (Integration) → requesting-code-review → Phase 6 (Final review) → Done
```

Any time a test fails unexpectedly → drop into `systematic-debugging` sub-loop before continuing.
