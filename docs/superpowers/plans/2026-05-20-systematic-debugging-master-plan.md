# Wiztant Comprehensive Systematic Debugging Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:systematic-debugging (Phase 1 root cause investigation ONLY) and superpowers:dispatching-parallel-agents.

**Goal:** Identify every bug, design flaw, regression risk, and architectural debt across the entire Wiztant codebase (Python backend + Electron overlay) and produce a ranked fix plan with root causes and remediation steps.

**Architecture:** Wiztant is a voice-first AI desktop assistant with a Python backend (~17,600 lines in `core/`, ~5,300 lines in `platforms/`), an Electron overlay (`ui/whiztant-overlay/`), and a marketing website (`whiztant-website/`). The backend handles STT, AI agent loops, hotkeys, tasks, memory, TuneHub tuning, and serves IPC via FastAPI (port 8765) and WebSocket (port 9120).

**Tech Stack:** Python 3.11, asyncio, uvicorn, FastAPI, pynput, websockets, Electron 33 + React 18 + TypeScript, pytest.

---

## Context: Known Issues (Pre-Investigation)

1. **23 test collection errors** when running `pytest tests/` together — many tests pass individually but fail when collected together due to import/path issues.
2. **Missing module imports in tests:** `core.stt_refiner`, `core.smart_paste`, `core.vocab`, `core.hotkeys`, `core.task_classifier` — files EXIST but tests fail to import them under pytest collection (likely missing `sys.path` setup or conflicting imports).
3. **Agent debug log shows repeated runtime errors:** coordinate validation failures (`x=-1 y=500`, `x=1500 y=500`), missing rule files (`apps_creative.md`, `apps_browsers.md`), OCR failures (Tesseract not installed).
4. **Legacy code debt:** Many "Whiztant" references instead of "Wiztant", removed subsystems still referenced, conversation mode removed but F9×2 documentation may be stale.
5. **No `pytest.ini`, `conftest.py`, or `pyproject.toml`** — test discovery relies on manual `sys.path` hacks in each test file.

---

## The 20 Debugging Domains

Each domain is assigned to an independent subagent. Agents must follow **systematic-debugging Phase 1 and Phase 2 ONLY** — identify root causes, do NOT implement fixes.

### Domain 1: Missing Module Imports & Test Infrastructure
**Scope:** All test collection errors (`tests/stt_tests/test_integration.py`, `test_refiner.py`, `test_smart_paste.py`, `test_vocab.py`, `test_dictation_edge_cases.py`, `test_task_classifier.py` and any others). Also the lack of `conftest.py` / `pytest.ini`.
**Files to inspect:** All `tests/**/*.py`, `core/__init__.py`, root directory structure.
**Expected output:** List of every import failure, root cause (missing sys.path, circular import, missing __init__, name collision), and recommended fix.

### Domain 2: STT Engine & Voice Pipeline
**Scope:** `core/voice.py`, `core/stt_engine.py`, Groq Whisper integration, local fallback, VAD, streaming pipeline.
**Files to inspect:** `core/voice.py`, `core/stt_engine.py`, `scripts/stress_test_stt.py`, `scripts/test_with_real_voice.py`, `tests/stt_tests/test_spoken_symbols.py`.
**Expected output:** Bugs in STT flow, error handling gaps, race conditions, API key handling issues, fallback logic flaws.

### Domain 3: Dictation System
**Scope:** `core/dictation_smart.py`, `core/dictation_correction.py`, `core/dictation_memory.py`, formatting, learning patterns.
**Files to inspect:** Above files + `tests/test_dictation_correction.py`, `tests/stt_tests/test_dictation_edge_cases.py`.
**Expected output:** Dictation formatting bugs, memory learning failures, edge case handling gaps.

### Domain 4: Smart Paste & Cross-Platform Input
**Scope:** `core/smart_paste.py` (if it exists), platform-specific paste implementations, cursor positioning.
**Files to inspect:** `core/smart_paste.py`, `platforms/*/system_access.py`, `platforms/*/hotkeys.py`, `tests/stt_tests/test_smart_paste.py`.
**Expected output:** Paste failures, platform abstraction gaps, fallback logic issues.

### Domain 5: Task System Core
**Scope:** `core/tasks.py` (~1,178 lines), task CRUD, voice parsing, due-time extraction, reminders, snooze.
**Files to inspect:** `core/tasks.py`, `memory/tasks.json`, `tests/test_tasks.py`, `tests/test_task_*.py`.
**Expected output:** Task parsing bugs, timezone issues, reminder logic flaws, snooze edge cases, file locking/concurrency issues.

### Domain 6: Task Classification & Categorization
**Scope:** Task classifier, categorizer, intent verification, mode setting.
**Files to inspect:** `core/task_classifier.py` (if exists), `tests/test_task_classifier.py`, `tests/test_task_classifier_extended.py`, `tests/test_task_categorizer.py`, `tests/test_task_categories.py`, `tests/test_task_intent_verification.py`, `tests/test_task_mode_setting.py`.
**Expected output:** Missing modules, classification logic bugs, false positives/negatives, test coverage gaps.

### Domain 7: Memory System
**Scope:** `core/memory.py`, persistent memory, JSON storage, memory retrieval.
**Files to inspect:** `core/memory.py`, `memory/memory.json`, `tests/test_agent_memory.py`.
**Expected output:** Data corruption risks, retrieval bugs, schema drift, concurrency issues.

### Domain 8: Agent Core — Tool Registry & Routing Loop
**Scope:** `core/agent.py` (~1,305 lines), tool registry, prompts, `ask_ai()` routing.
**Files to inspect:** `core/agent.py`, `tests/test_agent_integration.py`.
**Expected output:** Tool registration bugs, prompt injection risks, routing logic errors, infinite loop risks.

### Domain 9: Agent Engine & Orchestration
**Scope:** `core/agent_engine.py`, `core/agent_unified.py`, OpenRouter client, image encoding.
**Files to inspect:** `core/agent_engine.py`, `core/agent_unified.py`, `tests/test_agent_engine_extended.py`, `tests/test_agent_shared.py`.
**Expected output:** API client bugs, image encoding issues, orchestration race conditions, error handling gaps.

### Domain 10: Agent V2 — Master Planner
**Scope:** `core/agent_v2/master_planner.py`, plan generation, layer decomposition.
**Files to inspect:** `core/agent_v2/master_planner.py`, `tests/test_agent_v2_master_planner.py`.
**Expected output:** Planning logic bugs, validation failures, edge cases in layer generation.

### Domain 11: Agent V2 — Phase Engine
**Scope:** `core/agent_v2/phase_engine.py`, lifecycle management, phase transitions.
**Files to inspect:** `core/agent_v2/phase_engine.py`, `tests/test_agent_v2_phase_engine.py`.
**Expected output:** Phase transition bugs, state machine flaws, cleanup issues.

### Domain 12: Agent V2 — Models, Guardrails, Memory, Checkpoint
**Scope:** `core/agent_v2/models.py`, `core/agent_v2/guardrails.py`, `core/agent_v2/memory.py`, `core/agent_v2/checkpoint.py`, cost control.
**Files to inspect:** All `core/agent_v2/` files listed + `tests/test_agent_v2_guardrails.py`, `tests/test_agent_v2_models.py`, `tests/test_agent_v2_memory.py`.
**Expected output:** Model validation bugs, cost ceiling bypasses, checkpoint corruption, memory leaks.

### Domain 13: Background Agent
**Scope:** `core/background_agent.py` (~1,071 lines), ambient task manager, AgentInputContext isolation.
**Files to inspect:** `core/background_agent.py`, `core/agent_isolation.py`, `tests/test_agent_integration.py`.
**Expected output:** Focus-stealing bugs, background task scheduling issues, isolation failures, resource leaks.

### Domain 14: Hotkeys & Input System
**Scope:** `core/hotkeys.py` (~1,440 lines), F9 tap handler, dictation trigger, recording control, platform hotkey abstraction.
**Files to inspect:** `core/hotkeys.py`, `platforms/*/hotkeys.py`, `tests/stt_tests/test_dictation_edge_cases.py`, `tests/test_overlay_deep.py`.
**Expected output:** Hotkey conflicts, race conditions in tap counting, platform-specific input bugs, recording state machine issues.

### Domain 15: WebSocket Bridge IPC
**Scope:** `core/ws_bridge.py` (~1,149 lines), WebSocket server, Electron IPC, message broadcasting.
**Files to inspect:** `core/ws_bridge.py`, `ui/whiztant-overlay/src/main/bridge.ts`, `tests/test_tasks_overlay_ipc.py`, `tests/test_react_overlay_integration.py`.
**Expected output:** Message serialization bugs, connection leaks, broadcast failures, race conditions in IPC.

### Domain 16: FastAPI Server & API Endpoints
**Scope:** `core/server.py`, REST API, endpoint validation, CORS, error responses.
**Files to inspect:** `core/server.py`, `data/settings.json`.
**Expected output:** Missing endpoints, validation gaps, CORS issues, error response inconsistencies.

### Domain 17: Guardrails & Safety System
**Scope:** `core/guardrails.py`, safety regex, coordinate validation, loop detection, screenshot hashing.
**Files to inspect:** `core/guardrails.py`, `tests/test_guardrails.py`, agent debug log.
**Expected output:** Regex bypasses, coordinate validation gaps (evident from debug log), loop detection false positives/negatives, missing guardrails for new capabilities.

### Domain 18: System Context Scanner & Platform Abstraction
**Scope:** `core/system_context.py` (~813 lines), platform factory, OS-specific drivers, window management, screenshots.
**Files to inspect:** `core/system_context.py`, `platforms/factory.py`, `platforms/abstract/`, `platforms/linux/`, `platforms/windows/`, `tests/test_vlm_linux_unit.py`.
**Expected output:** Platform detection bugs, lazy import failures, window management errors, screenshot/VLM driver issues, missing Linux/Windows feature parity.

### Domain 19: WizPrompt / RePrompt & TuneHub
**Scope:** `core/wizprompt.py`, `core/wizprompt_memory.py`, `core/presets.py`, `core/tune_hub/`.
**Files to inspect:** Above files + `tests/test_wizprompt_memory.py`, `core/tune_hub/tests/`.
**Expected output:** Prompt optimization bugs, preset loading failures, TuneHub orchestrator issues, credit system bugs, marketplace integration gaps.

### Domain 20: Electron Overlay & UI Layer
**Scope:** `ui/whiztant-overlay/` (Electron + React), `ui/react_overlay.py`, `ui/agent_confirmation_overlay.py`, `ui/agent_results_panel.py`.
**Files to inspect:** All `ui/whiztant-overlay/src/` TS/TSX files, `ui/*.py`, `tests/test_overlay_deep.py`, `tests/test_react_overlay_integration.py`.
**Expected output:** TypeScript type errors, React state bugs, IPC message handling issues, theme variable gaps, show/hide logic violations (hide()/show() vs setOpacity), build failures, missing backend handlers for file upload.

---

## Agent Output Format

Each subagent MUST produce a structured report:

```markdown
## Domain N: [Name]

### Bugs Found
| # | Severity | File | Line | Description | Root Cause | Fix Recommendation |
|---|----------|------|------|-------------|------------|-------------------|
| 1 | Critical/High/Med/Low | `path` | N | ... | ... | ... |

### Tests Status
- Tests that fail: ...
- Tests that error on collection: ...
- Missing test coverage: ...

### Architectural Debt
- ...

### Quick Wins (≤5 min fixes)
- ...
```

---

## Integration & Execution

After all 20 agents return:
1. **Synthesize** all reports into a single ranked bug backlog.
2. **Deduplicate** — same bug reported by multiple domains gets merged.
3. **Rank** by severity (Critical → High → Med → Low) and effort.
4. **Write execution plan** using superpowers:writing-plans with bite-sized tasks.
5. **Execute** using superpowers:subagent-driven-development or superpowers:executing-plans.

---

## Constraints
- Agents must NOT modify code — investigation only.
- Agents must follow systematic-debugging: Phase 1 (root cause) and Phase 2 (pattern analysis) only.
- If an agent finds a bug that requires understanding another domain, note the cross-domain dependency but stay focused.
- Report "No bugs found" only after exhaustive inspection — if a domain seems clean, say why.
