<!-- AGENTS.md — Project context for AI coding agents. Read this first. -->

# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# Wiztant — Project-Specific Rules

## Product Identity

- **Product name:** Wiztant (intended branding). Note: the codebase still contains many "Whiztant" references in strings, file names, and legacy docs — update to "Wiztant" when you touch those lines, but do not do a global rename unless asked.
- **What it is:** Windows AI operating assistant (Linux supported for development), distributed as a portable executable, sold as SaaS.
- **Builder:** Solo project by Pranav (venkatesh is the same person).
- **Root directory:** `C:\whis\` (Windows), `/home/user/whis/` or similar (Linux dev).
- **Distribution:** Single portable executable; no installer, no registry writes.

---

## Project Overview

Wiztant is a voice-first AI desktop assistant composed of **three separate applications** that must not be confused:

1. **Python Backend** — headless backend + system tray. Handles voice STT, AI agent loop, hotkeys, tasks, memory, TuneHub tuning, and serves two IPC channels (FastAPI REST on port 8765, WebSocket on port 9120).
2. **Electron Overlay** — the active desktop UI. React + TypeScript + Tailwind + Framer Motion, built with `electron-vite`. Three windows (pill, overlay, settings) communicate with Python via WebSocket.
3. **Marketing Website** — static React + Vite + Tailwind CSS v3 SPA, deployed to Netlify.

---

## Architecture

### 1. Python Backend
- **Entry point:** `main.py` → `app/main.py` → `run_app()`
- **What it does:** Loads `.env`, runs health checks, initializes data directories (`data/`, `memory/`), imports core subsystems (voice → agent → WS bridge), registers global hotkeys via the Platform Abstraction Layer (PAL), starts uvicorn on `localhost:8765`, starts WebSocket bridge on `localhost:9120`, spins up background threads (system context scanner, background agent, system tray, task reminders, overlay launcher).
- **Core logic:** `core/` — 50+ modules (~17,600 lines of Python).
- **Agent rules:** `agent_rules/` — markdown specs for navigation, shortcuts, and apps consumed by the UI-TARS agent.
- **Platform abstraction:** `platforms/` — isolates all OS-specific code (window management, input, screenshots, TTS, hotkeys) behind abstract base classes. Factory at `platforms/factory.py` performs lazy imports so Linux never loads `win32api` and vice versa.
- **No PyQt6 main window** — the Python side is headless backend + tray icon only (`core/tray.py`). PyQt6 is used solely for the tray icon and minimal tkinter overlays (`ui/`).

### 2. Electron Overlay (Active UI)
- **Location:** `ui/whiztant-overlay/`
- **Stack:** Electron 33 + React 18 + TypeScript 5.7 + Tailwind CSS 3.4 + Framer Motion + electron-vite
- **Build:** `npm run build` → outputs to `out/`
- **Three BrowserWindows:**
  - **Pill** — bottom-center always-on-top wave indicator
  - **Overlay** — chat/tasks/agent panel (Ctrl+Space toggle)
  - **Settings** — theme + feature toggle config
- **On-demand:** TaskPanel windows (one per task id, frameless, positioned right of overlay)
- **IPC:** Electron ↔ Python via WebSocket on `ws://localhost:9120` (`core/ws_bridge.py`). Electron main also reads/writes `memory/tasks.json` directly via Node fs.
- **Performance rule:** Overlay uses `setOpacity(0/1)` — NEVER `hide()/show()` (causes DWM repaint lag on Windows).

### 3. Marketing Website
- **Location:** `whiztant-website/`
- **Stack:** React 19 + Vite 6 + Tailwind CSS v3 + PostCSS + Autoprefixer
- **Build:** `npm run build` → static `dist/` (SPA)
- **Deploy:** Manual to Netlify (`netlify.toml` present; no CI/CD pipeline)
- **PostCSS config:** `postcss.config.cjs` (CJS, not `.js`, because `package.json` has `"type": "module"`)

### Legacy / Do Not Use
- `ui/wiztant-clui/` — archived, superseded by `whiztant-overlay`
- `ui/wiztant-app/` — older React app, also superseded
- `overlay/whiztant-overlay/` — legacy Electron overlay, superseded
- `core/wiztype/` — entire subsystem removed

---

## Technology Stack & Key Configuration Files

| Layer | Language | Runtime / Framework |
|---|---|---|
| Python backend | Python 3.11 | asyncio, uvicorn, FastAPI, pynput, websockets |
| Electron overlay | TypeScript | React 18, Electron 33, Vite, Framer Motion |
| Website | TypeScript / JSX | React 19, Vite 6, Tailwind CSS v3 |
| STT | — | Groq Whisper Large v3 Turbo (cloud) + faster-whisper (local fallback) |
| Agent planner | — | Qwen 3.6 Plus free via OpenRouter (text-only) |
| Agent executor | — | UI-TARS 1.5 7B via OpenRouter (vision) |
| Auth | — | Supabase |
| Cost tracking | — | Helicone |
| License validation | — | LemonSqueezy |

### Key Config Files (verified to exist)
- **`requirements.txt`** — Python dependencies (no `pyproject.toml`, `setup.py`, or `setup.cfg`).
- **`ui/whiztant-overlay/package.json`** — Electron overlay dependencies and build scripts.
- **`ui/whiztant-overlay/electron.vite.config.ts`** — electron-vite build configuration.
- **`ui/whiztant-overlay/tailwind.config.js`** — Tailwind config for overlay (CJS).
- **`whiztant-website/package.json`** — Website dependencies.
- **`whiztant-website/tailwind.config.js`** — Website Tailwind config (ESM).
- **`whiztant-website/netlify.toml`** — Netlify deploy config (SPA redirects + build command).
- **`data/settings.json`** — Runtime settings including feature toggles, model selections, snooze presets.
- **`.env`** — API keys and secrets (gitignored, never commit).
- **`build.bat`** — Root-level Windows build script (pip install + PyInstaller).

### Notable Absences
- No `pyproject.toml`, `pytest.ini`, `conftest.py`, or `tox.ini` in the project root.
- No `build/windows/` or `build/linux/` directories currently in the repo.
- No PyInstaller `.spec` files currently tracked in git (`.gitignore` ignores `*.spec` and `build/`).

---

## Code Organization

### Python (`core/` — ~17,600 lines)
| Module | Purpose |
|---|---|
| `app/main.py` | Application bootstrap, health checks, feature flags, background timers |
| `core/agent.py` | Tool registry, prompts, `ask_ai()` routing loop (~1,305 lines) |
| `core/agent_engine.py` | Shared agent orchestration constants, OpenRouter client, image encoding |
| `core/agent_unified.py` | Unified agent runtime (~710 lines) |
| `core/background_agent.py` | Ambient background task manager (~1,071 lines) |
| `core/hotkeys.py` | F9 tap handler, dictation trigger, recording control (~1,440 lines) |
| `core/voice.py` | Groq Whisper transcription + local fallback (~850 lines) |
| `core/stt_engine.py` | Streaming STT pipeline, VAD, smart paste (~581 lines) |
| `core/stt_refiner.py` | Post-transcription LLM polish |
| `core/dictation_smart.py` | Smart formatting for dictation output |
| `core/dictation_correction.py` | Dictation correction engine |
| `core/dictation_memory.py` | Learns user dictation patterns |
| `core/smart_paste.py` | Cross-platform paste at cursor with fallback |
| `core/tasks.py` | Task CRUD, voice parsing, due-time extraction, reminders (~1,178 lines) |
| `core/memory.py` | Persistent memory system |
| `core/wizprompt.py` | RePrompt / WizPrompt optimization engine |
| `core/wizprompt_memory.py` | Prompt optimization memory / feedback loop |
| `core/presets.py` | 5 default presets for WizPrompt |
| `core/tune_hub/` | Adaptive tuning subsystem (Phase 1: manual/seed tuning) |
| `core/ws_bridge.py` | WebSocket server for Electron IPC (~1,149 lines) |
| `core/server.py` | FastAPI REST server (port 8765) |
| `core/guardrails.py` | Safety regex, coordinate validation, loop detection |
| `core/system_context.py` | System context scanner and scheduler (~813 lines) |
| `core/navigation_brain.py` | Agent navigation logic |
| `core/vocab.py` | Vocab correction / phonetic matching |
| `core/tray.py` | System tray icon |
| `core/usage.py` | Usage tracking / Helicone integration |
| `core/license.py` | LemonSqueezy license validation |
| `core/supabase_client.py` | Supabase auth client |

### Platform Abstraction (`platforms/` — ~5,300 lines)
- `platforms/factory.py` — Lazy factory for OS-specific drivers (hotkeys, TTS, VLM, window mgmt, system access).
- `platforms/abstract/` — Abstract base classes.
- `platforms/linux/` — Linux implementations (`hotkeys.py`, `system_access.py`, `window_mgmt.py`, `tts.py`, `vlm.py`, `_vlm_impl.py`, `agent_runtime.py`).
- `platforms/windows/` — Windows implementations (same interface).

### UI Layer (`ui/` — ~1,500 lines Python)
- `ui/react_overlay.py` — Legacy React overlay launcher (still used).
- `ui/react_overlay_runner.py` — Overlay runner helper.
- `ui/agent_confirmation_overlay.py` — tkinter confirmation dialog.
- `ui/agent_results_panel.py` — tkinter results panel.
- `ui/constants.py` / `ui/theme.py` — Python-side design tokens.

### Tests (`tests/` — ~24 files)
- `tests/test_*.py` — Core system tests (tasks, agent, guardrails, vocab, wizprompt, etc.).
- `tests/stt_tests/test_*.py` — STT-specific tests (integration, refiner, smart paste, vocab, edge cases).
- `core/tune_hub/tests/test_*.py` — TuneHub unit tests.

---

## Build & Test Commands

### Python Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Verify imports
python -c "import main"

# Run the app
python main.py
```

### Electron Overlay
```bash
cd ui/whiztant-overlay

# Dev mode
npm run dev

# Production build (required before PyInstaller packaging)
npm run build

# Type-check only
npm run typecheck
```

### Marketing Website
```bash
cd whiztant-website

# Dev mode
npm run dev

# Production build
npm run build
```

### Full Desktop Build
- **Windows:** `build.bat` at project root — installs deps, runs PyInstaller.
- **Linux:** No dedicated build script currently in repo.
- **Packaging formats:** `.exe` (Windows), binary / AppImage / Snap (Linux — planned).

---

## Code Style Guidelines

### Python
- Use `from __future__ import annotations` at the top of every module.
- Use type hints where practical.
- Use `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for module-level constants.
- Write module-level docstrings describing the file's purpose.
- Use section headers for logical groups:
  ```python
  # =============================================================
  #  SECTION NAME
  # =============================================================
  ```
- **Lazy imports for platform-specific modules:** always import inside functions (see `platforms/factory.py` pattern) so cross-platform imports never crash at startup.
- **Defensive coding:** wrap optional subsystems in `try/except` so missing API keys or unavailable platforms degrade gracefully rather than crash the app.
- Prefer `pathlib.Path` over `os.path` for new code.
- Keep the project root on `sys.path` in entry-point files (`sys.path.insert(0, str(_ROOT))`).

### TypeScript / React
- Use explicit types; avoid `any`.
- Use functional components with hooks.
- Tailwind classes for styling; do not use inline styles for theming (use theme context + CSS variables).
- The overlay uses `setOpacity(0/1)` for show/hide — never use `hide()/show()` on BrowserWindow.

---

## Testing Instructions

**Framework:** `pytest` (with `pytest-asyncio` and `pytest-cov`).

**Run all tests:**
```bash
pytest tests/
```

**Run a specific test file:**
```bash
pytest tests/test_tasks.py
pytest tests/stt_tests/test_integration.py
```

**Testing patterns observed:**
- Use `unittest.mock.patch` and `pytest.monkeypatch` to isolate external APIs (OpenRouter, Groq, screenshots).
- Use `tmp_path` fixtures for hermetic file I/O (tasks.json, agent memory).
- Integration tests may launch actual subprocesses (React overlay lifecycle, WebSocket bridge roundtrip).
- No `pytest.ini`, `pyproject.toml`, or `conftest.py` in the project root — tests rely on default pytest discovery and manual `sys.path.insert(0, ...)` at the top of test files.

**Manual / stress test scripts:**
- `scripts/stress_test_stt.py` — runs 100 iterations of the full STT pipeline and reports latency p95.
- `scripts/test_with_real_voice.py` — interactive REPL for manually typing phrases through the STT pipeline.

**No E2E tests** exist for the overlay IPC protocol. Add pytest-based tests when modifying bridge code.

---

## Security Considerations

- **`.env` contains secrets** — API keys for OpenAI, OpenRouter, Groq, Supabase, Helicone, and LemonSqueezy. Never commit `.env` to git.
- **Agent guardrails** — `core/guardrails.py` blocks destructive actions via regex (delete files, format drives, drop tables, shutdown, etc.), validates screen coordinates, and detects no-progress loops via screenshot hashing. Always respect and update these rules when adding new agent capabilities.
- **Isolated input** — background agent tasks use `AgentInputContext` (`core/agent_isolation.py`) to send input to background windows without stealing focus.
- **No sandbox escape** — the agent runs with the user's permissions. Do not add elevation prompts or UAC bypasses.
- **Tasks file** — both Python (`core/tasks.py`) and Electron main (`ipc.ts`) read/write `memory/tasks.json`. Ensure file locking or atomic writes if concurrency issues arise.

---

## Design System (shared across apps)

```
Background:  #07070f
Surface:     #0f0f1a
Primary:     #c0c1ff  (indigo)
Secondary:   #d0bcff  (purple)
Tertiary:    #4cd7f6  (teal)
Text:        #e2e2e2
Muted:       #6b7280
```

- **Wave states:** idle `#7B2241` (burgundy), recording (mic-reactive), thinking `#C4956A` (cappuccino), speaking `#1a3a6b` (dark blue), agent `#2d6e3e` (green)
- **Overlay themes** (5): `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — stored in `memory/theme.json`
- **Python tokens:** defined in `ui/constants.py` and `ui/theme.py`
- **Website tokens:** Tailwind config + CSS classes: `.glass`, `.gradient-text`, `.btn-primary`, `.btn-ghost`, `.card`, `.eyebrow`, `.kbd`, `.prose-dark`, `.page-wrap`, `.section`, `.section-alt`
- **Logo:** `wiztantW.svg` (do NOT regenerate programmatically — always load from file)

---

## Feature Modes (Hotkeys)

| Trigger | Mode | What it does |
|---|---|---|
| **F9 ×1** | Dictation | STT engine transcribes → smart paste at cursor |
| **F9 ×2+** | Agent toggle | Toggles Agent mode on/off (UI-TARS screen-to-action loop) |
| **Ctrl+Space** | Overlay toggle | Show/hide chat+tasks+agent overlay |
| **Ctrl+Shift+Space** | WizPrompt / RePrompt | Reads clipboard → optimizes via TuneHub persona weights + preset → writes back |
| **Esc** | Dismiss overlay | Closes overlay |
| **F10** | Task voice | PLANNED — voice-only task creation with "Add Task" pill state |

**Note:** The old "Conversation" mode (F9×2 voice loop with GPT + TTS) was removed when `core/tts.py` was deleted. Platform-specific TTS lives in `platforms/*/tts.py`.

---

## Feature Toggles System

### 4 Features
| Key | Description | Default |
|---|---|---|
| `agent` | Agent mode (F9 ×2+) | `true` |
| `tunehub` | TuneHub adaptive tuning | `true` |
| `tasks` | Task system | `true` |
| `reprompt` | RePrompt / WizPrompt | `true` |

### Storage
- **Frontend:** `localStorage` keys `whiztant.feature.*` + JSON blob `whiztant.features`
- **Backend:** `data/settings.json` under `"features"` key

### Gating
- **Frontend:** `Settings.tsx` toggles, `Overlay.tsx` conditional panel rendering, `TopTabBar.tsx` dynamic tab visibility
- **Backend:** `app/main.py` wraps agent init, TuneHub init, task timer, background agent in conditional blocks

### Tab Visibility (TopTabBar)
- **Always visible:** `chat` (label: "Tune"), `memories` (label: "Memories")
- **Feature-gated:**
  - `tunehub` → label: "Chat"
  - `reprompt` → label: "Prompt"
  - `agent` → label: "Agent"
  - `tasks` → label: "Today"

---

## Preset System (RePrompt)

- **File:** `core/presets.py`
- **Default presets:** `product_review`, `idea_review`, `code_review`, `code_creation`, `general`
- **UI:** Dropdown selector in `WizPromptPanel.tsx`
- **API:** `GET /presets` exposed in `core/server.py`
- **Integration:** `core/wizprompt.py` consumes the selected preset's `system_prompt_addendum` + `agent_focus`

---

## Task System & Reminders (with Snooze)

### Storage
- **Canonical file:** `memory/tasks.json`
- **Access:** Both Python (`core/tasks.py`) and Electron main process read/write this file

### Schema
```
id, text, status, source, created_at, due_at, completed_at,
parent_id, content, task_type (large/small), carried_over, failed,
progress, reminder_sent, snoozed_until
```

### Reminders
- **Check cycle:** Every 15 minutes
- **30-minute pre-due warning:** Alerts before task is due
- **Due alert:** Fires when `due_at` reached
- **Overdue repeats:** Every 15 minutes after overdue

### Snooze
- **Presets:** Configurable in `data/settings.json` (default includes 15min, 60min, 1440min)
- **Functions in `core/tasks.py`:**
  - `snooze_task(task_id, minutes)`
  - `is_snoozed(task)`
  - `clear_snooze(task_id)`

### WebSocket Broadcasts (from `ws_bridge.py`)
- `due_alert` — first miss alert
- `due_reminder` — periodic for carried-over tasks
- `tasks_failed` — tasks marked `failed=true`
- `task_saved` — task saved via voice or "save this for tomorrow"
- `pill/notice` — generic pill flash

---

## File Location Quick Reference

| Thing | Path |
|---|---|
| App entry | `main.py` |
| Core logic | `core/` |
| Agent navigation spec | `WHISrules.md` |
| Agent rules folder | `agent_rules/` |
| WebSocket bridge | `core/ws_bridge.py` |
| FastAPI server | `core/server.py` |
| Tasks CRUD | `core/tasks.py` |
| Task storage | `memory/tasks.json` |
| Theme storage | `memory/theme.json` |
| Memory storage | `memory/memory.json` |
| Overlay position | `memory/overlay_position.json` |
| Settings + feature flags | `data/settings.json` |
| TuneHub DB | `data/tune_hub.db` |
| Tune models | `data/tune_models/` |
| Electron overlay root | `ui/whiztant-overlay/` |
| Electron main process | `ui/whiztant-overlay/src/main/index.ts` |
| Electron preload | `ui/whiztant-overlay/src/preload/index.ts` |
| Overlay renderer | `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx` |
| Pill renderer | `ui/whiztant-overlay/src/renderer/pill/Pill.tsx` |
| Settings renderer | `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` |
| Shared types/IPC | `ui/whiztant-overlay/src/renderer/shared/` |
| Notification components | `ui/whiztant-overlay/src/renderer/shared/notifications/` |
| Theme tokens | `ui/whiztant-overlay/src/renderer/shared/themes.ts` |
| React overlay launcher | `ui/react_overlay.py` |
| Design tokens (Python) | `ui/constants.py`, `ui/theme.py` |
| Logo SVG | `wiztantW.svg` |
| Website | `whiztant-website/` |
| Implementation plans | `Plans_Implementation/` |
| Python deps | `requirements.txt` |
| Windows build script | `build.bat` |
| Tests | `tests/` |
| STT tests | `tests/stt_tests/` |
| Tune Hub specs | `TuneHubSpecifications/` |

---

## Definition of Done

A task is **complete** when:

1. **Code compiles / imports without errors** — Python: `python -c "import main"` passes; TypeScript: `npm run build` succeeds in `ui/whiztant-overlay/`
2. **The specific behavior requested works** — verified manually or via test, not just "it looks right"
3. **No regressions introduced** — the F9 modes (dictation + agent toggle), Ctrl+Space overlay, pill notifications, and task system still function
4. **No new files created unless necessary** — prefer editing existing files
5. **Build artifact is up to date** — if `whiztant-overlay` was changed, `npm run build` was re-run

For UI changes in `whiztant-overlay`: task is NOT done until `npm run build` completes successfully.

For Python changes: task is NOT done until `python main.py` starts without errors in the terminal.

---

## Appendix: Known Issues / What Can Be Improved

- Overlay dropdown menus styling not fully polished (theme variable gaps).
- File upload refs in attach menu are wired but not connected to a backend handler.
- No E2E tests for the overlay IPC protocol.
- Website deploy is manual — no CI/CD pipeline.
- F10 task hotkey is planned but not fully implemented.
- Build verification (TypeScript `tsc --noEmit`) not yet automated.
- Python import test (`python -c "import main"`) not yet automated.
- TuneHub Phase 2 (actual model training) not yet implemented — currently Phase 1 manual/seed only.

---

## Appendix: Legacy Features — DO NOT USE in New Code

The following were removed and must not be referenced in new code or documentation:

- `core/wiztype/` (entire subsystem)
- `core/action_optimizer.py`, `core/agent_s3_wrapper.py`, `core/app_detector.py`, `core/intent_compiler.py`, `core/learning_agent.py`, `core/system_task_executor.py`, `core/workflow_recorder.py`
- `tests/test_wiztype_*.py`
- `ui/chat_overlay.py`
- `main_old.py`, root `package-lock.json`, `docs/WIZTYPE.md`, `data/wiztype_config.json`
- Conversation mode (F9×2 voice loop with TTS) — removed with `core/tts.py`
