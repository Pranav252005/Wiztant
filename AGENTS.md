""
# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
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
- If you notice unrelated dead code, mention it - don't delete it.

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

- **Product name:** Wiztant (never "Whiztant" — name was changed)
- **What it is:** Cross-platform AI operating assistant (Windows primary, Linux supported), distributed as a portable executable, sold as SaaS
- **Builder:** Solo project by Pranav (venkatesh is the same person)
- **Root directory:** `C:\whis\` (Windows), `/home/user/whis/` or similar (Linux dev)

---

## Project Overview

Wiztant is a voice-first AI desktop assistant with three distinct applications that must not be confused:

1. **Python Backend** — headless backend + system tray. Handles voice STT/TTS, AI agent loop, hotkeys, tasks, memory, and serves two IPC channels (FastAPI REST on port 8765, WebSocket on port 9120).
2. **Electron Overlay** — the active UI. React 18 + TypeScript + Tailwind + Framer Motion, built with `electron-vite`. Three windows (pill, overlay, settings) communicate with Python via WebSocket.
3. **Marketing Website** — static React + Vite + Tailwind CSS v3 SPA, deployed to Netlify.

---

## Application Architecture

### 1. Python Backend
- **Entry point:** `main.py` → `app/main.py` → `run_app()`
- **What it does:** Loads `.env`, runs health checks, initializes data directories, imports core subsystems (voice → agent → WS bridge), registers global hotkeys via the Platform Abstraction Layer (PAL), starts uvicorn on `localhost:8765`, starts WebSocket bridge on `localhost:9120`, spins up background threads (system context scanner, background agent, system tray, WizType, task reminders, overlay launcher).
- **Core logic:** `core/` — 50+ modules (~17,700 lines)
- **Agent rules:** `agent_rules/` — markdown specs for navigation, shortcuts, and apps consumed by the UI-TARS agent
- **Platform abstraction:** `platforms/` — isolates all OS-specific code (window management, input, screenshots, TTS, hotkeys) behind abstract base classes. Factory at `platforms/factory.py` performs lazy imports so Linux never loads `win32api` and vice versa.
- **No PyQt6 main window** — the Python side is headless backend + tray icon only. The legacy tkinter overlay (`ui/chat_overlay.py`) still exists as a fallback but is not the primary UI.

### 2. Electron Overlay (Active UI)
- **Location:** `ui/whiztant-overlay/`
- **Stack:** Electron 33 + React 18 + TypeScript 5.7 + Tailwind CSS 3.4 + Framer Motion + electron-vite
- **Build:** `npm run build` → outputs to `out/`
- **Three BrowserWindows:**
  - **Pill** — bottom-center always-on-top wave indicator
  - **Overlay** — 340×420 chat/tasks/agent panel (Ctrl+Space toggle)
  - **Settings** — theme + WizType config
- **On-demand:** TaskPanel windows (one per task id, 340×420 frameless, positioned right of overlay)
- **IPC:** Electron ↔ Python via WebSocket on `ws://localhost:9120` (`core/ws_bridge.py`). Electron main also reads/writes `memory/tasks.json` directly via Node fs.
- **Performance rule:** Overlay uses `setOpacity(0/1)` — NEVER hide/show (causes DWM repaint lag on Windows).

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

---

## Languages & Runtimes

| Layer | Language | Runtime / Framework |
|---|---|---|
| Python backend | Python 3.11 | asyncio, uvicorn, FastAPI, pynput, websockets |
| Electron overlay | TypeScript | React 18, Electron 33, Vite, Framer Motion |
| Website | TypeScript / JSX | React 19, Vite 6, Tailwind CSS v3 |
| STT | — | Groq Whisper Large v3 Turbo (cloud) + faster-whisper (local fallback) |
| TTS | — | Kokoro (local, requires espeak-ng), 6 voices, `af_nova` default |
| Agent planner | — | Qwen 3.6 Plus free via OpenRouter (text-only) |
| Agent executor | — | UI-TARS 1.5 7B via OpenRouter (vision) |
| Auth | — | Supabase |
| Cost tracking | — | Helicone |
| License validation | — | LemonSqueezy |

---

## Feature Modes (F9 Hotkey)

| Trigger | Mode | What it does |
|---|---|---|
| F9 ×1 | Dictation | Whisper transcription → smart paste at cursor |
| F9 ×2 | Conversation | Voice loop with GPT-5.4 + Kokoro TTS |
| F9 ×3 | Agent | UI-TARS screen-to-action loop |
| Ctrl+Space | Overlay toggle | Show/hide 340×420 chat+tasks+agent overlay |
| F10 (planned) | Task voice | Voice-only task creation with "Add Task" pill state |

---

## Design System (shared across all three apps)

```
Background:  #07070f
Primary:     #c0c1ff  (indigo)
Secondary:   #d0bcff  (purple)
Tertiary:    #4cd7f6  (teal)
```

- **Wave states:** idle `#7B2241` (burgundy), recording (mic-reactive), thinking `#C4956A` (cappuccino), speaking `#1a3a6b` (dark blue), agent `#2d6e3e` (green)
- **Overlay themes** (5): `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — stored in `memory/theme.json`
- **Python tokens:** defined in `ui/constants.py` and `ui/theme.py`
- **Website tokens:** Tailwind config + CSS classes: `.glass`, `.gradient-text`, `.btn-primary`, `.btn-ghost`, `.card`, `.eyebrow`, `.kbd`, `.prose-dark`, `.page-wrap`, `.section`, `.section-alt`
- **Logo:** `wiztantW.svg` (do NOT regenerate programmatically — always load from file)

---

## Pricing

| Plan | Monthly | Annual | Limits |
|---|---|---|---|
| Free | $0 | — | 15 chats/mo |
| Pro | $15 | $165/yr | 300 chats, 50 agent, 30 UI-TARS |
| Power | $25 | $275/yr | 500 chats, 200 agent, 200 UI-TARS |

- Trial: 3 days, 30 msgs, 3 agent tasks, no credit card required
- Annual saves 1 month vs monthly

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
- **Windows:** `build/windows/build.bat` — installs deps, builds overlay, runs PyInstaller
- **Linux:** `build/linux/build.sh` — same flow, optionally creates AppImage via `linuxdeploy`
- **PyInstaller specs:** `build/windows/whiztant.spec` and `build/linux/whiztant_linux.spec`
- **Packaging formats:** `.exe` (Windows), binary / AppImage / Snap (Linux)

---

## Code Style Guidelines

### Python
- Use `from __future__ import annotations` at the top of every module.
- Use type hints where practical.
- Use snake_case for functions/variables, PascalCase for classes, UPPER_CASE for module-level constants.
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

**Test inventory:** ~313 test cases across 24 Python files in `tests/`.

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
- Use `pytest.mark.asyncio` for async WizType tests.
- Integration tests launch actual subprocesses (React overlay lifecycle, WebSocket bridge roundtrip).
- No `pytest.ini`, `pyproject.toml`, or `conftest.py` in the project root — tests rely on default pytest discovery and manual `sys.path.insert(0, ...)` at the top of test files.

**Manual / stress test scripts:**
- `scripts/stress_test_stt.py` — runs 100 iterations of the full STT pipeline and reports latency p95.
- `scripts/test_with_real_voice.py` — interactive REPL for manually typing phrases through the STT pipeline.

**No E2E tests** exist for the overlay IPC protocol. Add pytest-based tests when modifying bridge code.

---

## Security Considerations

- **`.env` contains secrets** — API keys for OpenAI, OpenRouter, Groq, Supabase, Helicone, and LemonSqueezy. It is blocked from being read by tools to protect credentials. Never commit `.env` to git.
- **Agent guardrails** — `core/guardrails.py` blocks destructive actions via regex (delete files, format drives, drop tables, shutdown, etc.), validates screen coordinates, and detects no-progress loops via screenshot hashing. Always respect and update these rules when adding new agent capabilities.
- **Isolated input** — background agent tasks use `AgentInputContext` (`core/agent_isolation.py`) to send input to background windows without stealing focus.
- **No sandbox escape** — the agent runs with the user's permissions. Do not add elevation prompts or UAC bypasses.
- **Tasks file** — both Python (`core/tasks.py`) and Electron main (`ipc.ts`) read/write `memory/tasks.json`. Ensure file locking or atomic writes if concurrency issues arise.

---

## What's Been Built

### Python Backend
- [x] F9 hotkey with 3-mode detection (debounced counter)
- [x] Dictation: Groq Whisper STT → clipboard paste with aggressive cross-platform fallback
- [x] Conversation: voice loop with GPT-5.4 + Kokoro TTS, 6 voices
- [x] Agent: UI-TARS 1.5 7B screen-to-action loop with `agent_rules/` navigation spec
- [x] System tray icon (winotify toasts on startup)
- [x] Supabase auth (email/password)
- [x] Usage guard via Helicone
- [x] WebSocket bridge on port 9120 (`core/ws_bridge.py`) — Python ↔ Electron IPC
- [x] FastAPI backend on port 8765 (`core/server.py`)
- [x] Task system (`core/tasks.py`): full CRUD, voice parsing, due-time extraction, LLM task refiner, daily suggestion
- [x] Task schema: id, text, status, source, created_at, due_at, completed_at, parent_id, content, task_type (large/small), carried_over, failed
- [x] Session continuity: "save this for tomorrow" → `save_session_as_task()`
- [x] Due-alert timers: `_due_check()` at 18:00 daily, `_due_reminder()` every 4h for carried-over tasks
- [x] Startup nudge: 8s after boot, pill flashes yesterday's pending task summary
- [x] WizType subsystem (`core/wiztype/`): keyboard hook, debounced inference, Ollama/custom model, Tab-to-accept suggestion overlay
- [x] Background agent manager (`core/background_agent.py`)
- [x] Memory system (`core/memory.py`)
- [x] System context scanner (`core/system_context.py`)
- [x] Vocab correction system (`core/vocab.py`)
- [x] Agent confirmation overlay (`ui/agent_confirmation_overlay.py`)

### Electron Overlay (whiztant-overlay)
- [x] Pill window — always-on-top, bottom-center, wave animation with state colors
- [x] Overlay window — 3-tab layout (Chat / Tasks / Agent), Ctrl+Space toggle
- [x] Settings window — theme picker, WizType config
- [x] Theme system — 5 themes, persisted to `memory/theme.json`, synced to all windows
- [x] WebSocket bridge client — connects to Python on port 9120
- [x] Task system — full CRUD via IPC + fs direct
- [x] TasksPanel — task list with add-form, due-time picker, Today section, Undone section, recent history
- [x] TaskTile — LARGE/SMALL badge, due label, overdue highlighting, failed state, voice badge
- [x] TaskPanel side window — 340×420 frameless, opens to the right of overlay
- [x] Notification system — pill notifications with auto-save, due alerts, due reminders, duplicate warnings
- [x] Agent panel — live step progress, blocked state with undo, done/result state
- [x] VocabCorrectModal — prompt user to correct misheard words
- [x] Warp entrance animation on every Ctrl+Space show
- [x] Multiple chat conversations with tab strip, add/close tabs

### Website
- [x] All marketing pages (/, /features, /how-it-works, /pricing, /download, /login)
- [x] Legal pages (/privacy-policy, /terms-of-service, /cookie-policy)
- [x] /support, /docs (7 sections), /press
- [x] Dark celestial design system throughout
- [x] Supabase auth on /login (email + Google OAuth)

---

## Known Issues / What Can Be Improved

- Overlay dropdown menus styling not fully polished (theme variable gaps)
- Chat overlay tab switching between tkinter and Electron overlay not fully unified
- File upload refs in attach menu are wired but not connected to a backend handler
- No E2E tests for the overlay IPC protocol
- Website deploy is manual — no CI/CD pipeline
- F10 task hotkey is planned but not fully implemented

---

## Definition of Done

A task is **complete** when:

1. **Code compiles / imports without errors** — Python: `python -c "import main"` passes; TypeScript: `npm run build` succeeds in `ui/whiztant-overlay/`
2. **The specific behavior requested works** — verified manually or via test, not just "it looks right"
3. **No regressions introduced** — the three F9 modes, Ctrl+Space overlay, pill notifications, and task system still function
4. **No new files created unless necessary** — prefer editing existing files
5. **Build artifact is up to date** — if `whiztant-overlay` was changed, `npm run build` was re-run

For UI changes in `whiztant-overlay`: task is NOT done until `npm run build` completes successfully.

For Python changes: task is NOT done until `python main.py` starts without errors in the terminal.

---

## File Location Quick Reference

| Thing | Path |
|---|---|
| App entry | `main.py` |
| Core logic | `core/` |
| WizType subsystem | `core/wiztype/` |
| Agent navigation spec | `WHISrules.md` |
| Agent rules folder | `agent_rules/` |
| WebSocket bridge | `core/ws_bridge.py` |
| FastAPI server | `core/server.py` |
| Tasks CRUD | `core/tasks.py` |
| Task storage | `memory/tasks.json` |
| Theme storage | `memory/theme.json` |
| Memory storage | `memory/memory.json` |
| Electron overlay root | `ui/whiztant-overlay/` |
| Electron main process | `ui/whiztant-overlay/src/main/` |
| Electron preload | `ui/whiztant-overlay/src/preload/index.ts` |
| Overlay renderer | `ui/whiztant-overlay/src/renderer/overlay/` |
| Pill renderer | `ui/whiztant-overlay/src/renderer/pill/` |
| Settings renderer | `ui/whiztant-overlay/src/renderer/settings/` |
| Shared types/IPC | `ui/whiztant-overlay/src/renderer/shared/` |
| Notification components | `ui/whiztant-overlay/src/renderer/shared/notifications/` |
| React overlay launcher | `ui/react_overlay.py` |
| tkinter chat overlay fallback | `ui/chat_overlay.py` |
| Design tokens (Python) | `ui/constants.py`, `ui/theme.py` |
| Logo SVG | `wiztantW.svg` |
| Website | `whiztant-website/` |
| Implementation plans | `Plans_Implementation/` |
| Python deps | `requirements.txt` |
| Windows build script | `build/windows/build.bat` |
| Linux build script | `build/linux/build.sh` |
| Windows PyInstaller spec | `build/windows/whiztant.spec` |
| Linux PyInstaller spec | `build/linux/whiztant_linux.spec` |
| Tests | `tests/` |
| STT tests | `tests/stt_tests/` |
| WizType tests | `tests/test_wiztype_*.py` |
| Tune Hub specs | `TuneHubSpecifications/` |

---

# Tune Hub — Universal Meta-Learning System

## What is Tune Hub?

Tune Hub is wiztant's **universal meta-learning system** — a personalization engine that observes, learns, and optimizes configuration parameters across every wiztant feature. It transforms a generic AI assistant into a deeply personal productivity tool by learning the user's unique patterns, vocabulary, workflows, and preferences.

**Core principle:** Every feature tuner is a self-contained plugin implementing `TuneBase`. Adding a new tuner (e.g., BrowserAgentTuner) requires zero changes to TuneHub core.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DESKTOP 1 (Production)                    │
│   RePrompt / Dictation / Agent / FutureFeature              │
│          └──────────────┬─────────────────┘                 │
│              Tune Application Middleware (Event Router)      │
│              TuneHub Core (Desktop 1 Node)                   │
│              Local Cache (SQLite + JSON)                     │
└─────────────────────────────────────────────────────────────┘
                              │ Async Message Queue (NATS / RabbitMQ / WebSocket)
┌─────────────────────────────────────────────────────────────┐
│                  DESKTOP 2 (Experimentation)                 │
│              TuneHub Core (Desktop 2 Node)                   │
│   RePromptTuner │ DictationTuner │ AgentTuner (Plugins)      │
│   Experimentation Engine & ML Pipeline                      │
│   Remote Storage Layer (Postgres + Redis / Encrypted S3)    │
└─────────────────────────────────────────────────────────────┘
```

**Key architectural decisions:**
- **Desktop 1 ↔ Desktop 2 separation:** Learning (expensive, experimental) runs on Desktop 2. Deployment (fast, deterministic) runs on Desktop 1. Communication via async message queue.
- **Event-driven tune application:** Feature triggers emit events; Tune Hub asynchronously resolves the best tune and injects it before the feature executes.
- **Credit-gated experimentation:** Every learning phase consumes credits. Credit tracking is first-class, not bolted-on.

## Core Abstractions

### Data Classes

| Class | Purpose |
|-------|---------|
| `ComplexityLevel` | `LOW` (Free), `MEDIUM` (Pro), `HIGH` (Power) — maps to pricing tier |
| `TuneStatus` | `DRAFT` → `PENDING_VALIDATION` → `VALIDATED` → `DEPLOYED` → `ARCHIVED` / `FAILED` |
| `CreditBudget` | Immutable credit allocation with `can_spend()` and `spend()` methods |
| `LearnedModel` | Generic container: `tune_id`, `feature_name`, `task_signature`, `payload`, `quality_score`, `complexity`, `status`, `version`, `parent_version` |
| `ExperimentResult` | Single experiment iteration: `config`, `output`, `score`, `credits_used`, `iteration` |

### TuneBase Abstract Class

Every tuner plugin MUST implement these methods (stateless — state flows through `LearnedModel` instances):

| Phase | Method | Runs On | Latency Requirement |
|-------|--------|---------|---------------------|
| Static Analysis | `estimate_complexity(task, context)` | Desktop 1 | < 100ms synchronous |
| Learning | `learn(task, budget, context, judge)` | Desktop 2 | Minutes to hours |
| Validation | `validate(model, hold_out_tasks, judge)` | Desktop 2 | Deterministic pass/fail |
| Deployment | `deploy(model)` | Desktop 2 → D1 | Async via message queue |
| Runtime | `apply(model, feature_input)` | Desktop 1 | < 50ms hot path |
| Fallback | `get_default_config(task)` | Desktop 1 | < 50ms deterministic |

**Plugin registration:** Subclasses auto-register via `class MyTuner(TuneBase, feature_name="my_feature")`.

### TuneHub Orchestrator

Thin orchestrator that delegates ALL feature-specific logic to TuneBase plugins. Never needs modification when adding features.

Key methods:
- `tune_feature(request: TuneRequest) → TuneResult` — full pipeline: tier check → complexity estimate → credit budget → learn → validate → deploy → persist → sync
- `resolve_tune(user_id, feature_name, task, feature_input) → Dict` — **synchronous hot path**, < 50ms, called on every feature trigger
- `rollback_tune(user_id, tune_id, to_version)` — Power tier only

## Feature-Specific Tuners

### RePromptTuner (`feature_name="reprompt"`)
**Learns:** Optimal persona blend weights for different task categories.
- **Personas:** `debug`, `build`, `research`, `write`, `plan`
- **Algorithm:** Multi-Task Bayesian Optimization with Thompson Sampling
  - Surrogate: Gaussian Process (Matern-5/2 kernel)
  - Acquisition: Expected Improvement (EI) with ξ=0.01
  - Task classifier: keyword + embedding ensemble
- **Convergence:** Quality plateau (std < 0.05, mean > 0.85) OR acquisition flat OR weight stability OR budget exhausted (max 12 iterations)
- **Credit target:** ~1,200 credits per task (optimized from ~2,346)

### DictationTuner (`feature_name="dictation"`)
**Learns:** Domain-specific vocabulary corrections.
- **Algorithm:** Context-Aware Active Learning with Confidence-Weighted Correction Map
  - Base: Trie-based prefix correction map with frequency weighting
  - Context classifier: Small transformer (DistilBERT-level) for 8 domains
  - Update rule: Exponential weighted moving average (α=0.7 favors recent)
- **Domains:** `general`, `software`, `crypto`, `medical`, `legal`, `creative_writing`, `business`, `custom`
- **Event-driven:** Each user interaction (transcription + possible edit) is one learning iteration
- **Credit target:** ~800 credits per domain

### AgentTuner (`feature_name="agent"`)
**Learns:** App behavior and automation sequences (recipes).
- **Algorithm:** Causal Reinforcement Learning with Program Synthesis (CRL-PS)
  - Exploration: Hierarchical task planner with macro-action library
  - Causal model: Structural Causal Model (SCM) with do-calculus
  - Policy: PPO with safety constraints
  - Program synthesis: DSL for action sequences → reusable recipes
- **Macro actions:** `click`, `double_click`, `right_click`, `type`, `hotkey`, `drag`, `scroll`, `wait`, `menu_select`, `dialog_click`, `slider_set`, `layer_select`, `adjustment_apply`
- **Credit target:** ~250 credits per recipe (optimized)

## Data Layer

### Tier-Aware Storage

| Capability | Free | Pro ($20/mo) | Power ($30/mo) |
|------------|------|--------------|----------------|
| Backend | Local SQLite | PostgreSQL + Redis | Encrypted PostgreSQL + Encrypted S3 |
| Tune limit | 1 total | Unlimited (soft cap 50/mo, hard 100) | Unlimited (soft cap 200/mo, hard 500) |
| Complexity | LOW only | LOW + MEDIUM | LOW + MEDIUM + HIGH |
| Versioning | No | Last 5 versions | Full history + rollback |
| Cross-machine sync | No | Yes (real-time, <30s) | Yes + selective sync + manual force |
| Sharing | No | Direct link (read-only import) | Marketplace publishing + selling |
| Encryption | None | TLS in transit | AES-256-GCM at rest + TLS |

### Schema (Pro/Power — PostgreSQL)

Core tables: `users`, `user_tunes`, `tune_versions`, `credit_ledger`, `sync_queue`, `tune_shares`, `marketplace_listings`

Free tier uses a single `local_tunes` SQLite table with `UNIQUE(feature_name, task_signature)`.

### Power Tier Encryption

Per-user AES-256-GCM encryption. Plaintext NEVER enters cloud DB. Keys managed by user-controlled provider. Associated data includes `user_id:tune_id` for binding.

## API Contracts

### Public REST API (FastAPI)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tune` | POST | Initiate learning for a feature |
| `/resolve` | POST | Hot-path tune resolution at feature trigger (< 50ms) |
| `/tunes/{user_id}` | GET | List user's tunes |
| `/tunes/{user_id}/{tune_id}` | DELETE | Delete a tune |
| `/tunes/{user_id}/{tune_id}/rollback` | POST | Rollback to version (Power only) |
| `/tunes/{user_id}/{tune_id}/share` | POST | Share tune (Pro/Power) |
| `/sync/pending` | GET | Pull pending syncs (Desktop 1 startup) |
| `/credits/{user_id}/balance` | GET | Check credit balance |

### Internal Protocols

- `ITunerPlugin` — Protocol that all tuners must satisfy
- `CreditTracker` — Abstract: `get_balance`, `reserve`, `consume`, `refund`, `grant`
- `DesktopBridge` — Async: `connect`, `publish`, `subscribe`, `unsubscribe`, `disconnect`

## System Flows

### Learning Phase (Desktop 2)
```
User Request → Parse feature → Check tier → Estimate complexity →
Credit budget setup → Experimentation loop → Aggregation →
Validation (hold-out tests) → [PASS: Deploy+Sync / FAIL: Refund 50%]
```

### Runtime Hot Path (Desktop 1)
```
Feature trigger → In-memory LRU cache lookup (< 5ms) →
SQLite lookup → Tune application (< 10ms) → Feature execution →
Optional: Quality feedback loop (thumbs-down queues re-tuning)
```

**Latency budget:** Total overhead < 60ms added to base feature latency.

### Deployment (D2 → D1)
```
Desktop 2: Tuner.deploy() → PUBLISH to message broker →
Message broker: ROUTE to D1 subscriber →
Desktop 1: Decrypt (Power) → Deserialize → Write SQLite → Update LRU cache →
ACK back to D2 → Status: DEPLOYED on both
```

## Tune Marketplace (Power Tier)

- **Browse:** All tiers can view; Pro/Power can import; Power can publish and sell
- **Pricing models:** Free, Credit Purchase (creator earns 70%, platform 30%), Freemium, Tip Jar
- **Discovery:** Featured (curated), Trending (7-day imports), Recommended (ML-driven), New Arrivals, Staff Picks
- **Trust & Safety:** PII auto-scanner, sandboxed testing before import, quality gate (>60 to publish), verified creator badges, review moderation pipeline
- **Creator revenue:** 70% of credit price as "Creator Credits" (convertible to cash at $0.0001/credit after $50 minimum)

## UX / Screen Flow

1. **Tune Hub Entry Screen** — "What do you want to optimize?" + feature selection grid (2×2 cards)
2. **Cost Estimate Screen** — Complexity badge + step-by-step plan + credit breakdown + time estimate
3. **Learning Progress Modal** — Animated progress steps + live metrics + "What's Happening" accordion + cancel/background options
4. **Tune Results Screen** — Before/After comparison + learned parameters visualization + quality score gauge
5. **Tune Management Dashboard** — Filter/sort by feature, status, quality; smart folders; sync status
6. **Tune Detail Panel** — Overview | Parameters | History | Advanced (Power) tabs
7. **Share to Marketplace Modal** — Visibility, pricing, tags, PII scanner
8. **Marketplace Browse Screen** — Category tabs, search, sort, tune cards
9. **"Tune Active" Micro-UI** — 4px colored ghost dot on feature icon (blue=RePrompt, green=Dictation, purple=Agent)

### Override Mechanisms
- **Temporary Override:** "Use Default This Time" — current session only
- **Session Override:** "Pause Tune for 1 Hour" — auto-resumes
- **Full Disable:** "Disable This Tune" — moves to Inactive
- **Global Override:** Settings → "Use Defaults for All Features"

## File Structure (Target)

```
tune_hub/
├── __init__.py
├── base.py                    # Core dataclasses, enums, exceptions
├── tune_base.py              # TuneBase abstract class
├── orchestrator.py           # TuneHub orchestrator
├── storage/
│   ├── abstract.py           # TuneStorage interface
│   ├── sqlite_store.py       # Free tier
│   ├── postgres_store.py     # Pro/Power
│   └── encryption.py         # Power tier crypto
├── credit_system/
│   ├── abstract.py
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
│   ├── abstract.py           # DesktopBridge
│   ├── nats_bridge.py
│   └── websocket_bridge.py
├── api/
│   ├── public.py             # FastAPI endpoints
│   └── internal.py
├── sync/
│   └── sync_manager.py
├── quality/
│   ├── judge.py
│   └── claude_judge.py
└── tests/
    ├── test_orchestrator.py
    ├── test_reprompt_tuner.py
    ├── test_credit_system.py
    └── test_encryption.py
```

## Rollout Plan

| Phase | Timeline | Scope |
|-------|----------|-------|
| Phase 0: Foundation | Weeks 1-4 | Internal dogfooding, stress testing, credit validation, UI polish |
| Phase 1: Controlled Beta | Weeks 5-8 | 500 invited users (200 Free, 200 Pro, 100 Power), RePrompt + Dictation only |
| Phase 2: Public Beta | Weeks 9-12 | Opt-in early access, all users can try, limited to RePrompt + Dictation |
| Phase 3: General Availability | Weeks 13-16 | All 4 features enabled, marketplace opens (Power publishing) |
| Phase 4: Expansion | Months 5-6 | Marketplace growth, enterprise pilot, international |

## Success Metrics

| Metric | Target |
|--------|--------|
| Tune creation rate (Month 1) | >30% of active users |
| Tune success rate | >85% |
| Learning success rate | >90% |
| Tune application latency | <100ms median |
| Sync success rate | >99% |
| Free → Pro conversion lift | +5pp vs pre-Tune Hub |
| Tune-Driven Engagement (12mo) | 60% of sessions involve active tune |

## Glossary

| Term | Definition |
|------|-----------|
| **Tune** | A learned configuration optimized for a specific user, feature, and task |
| **Task Signature** | Normalized task identifier (e.g., `coding_tasks`) used for tune lookup |
| **Credit** | Unit of experimentation cost. 1 credit ≈ 1 experiment iteration |
| **Desktop 1** | Production environment where features run and tunes are applied |
| **Desktop 2** | Experimentation environment where learning and validation occur |
| **Persona Blend** | Weighted combination of personas (debug, build, research, write, plan) for RePrompt |
| **Recipe** | Automation sequence for Agent tuner (list of actions in DSL) |
| **TuneHub** | The orchestrator that routes tuning requests to the correct tuner plugin |
| **Tuner Plugin** | Feature-specific implementation of TuneBase |
| **Ghost Indicator** | Subtle 4px dot showing a tune is active on a feature |
| **Complexity** | LOW (1-3 variations, ~100-800 credits) / MEDIUM (5-15, ~500-3,000) / HIGH (15-50+, ~2,000-10,000) |

---

*Tune Hub specifications sourced from:*
- `TuneHubSpecifications/tune_hub_architecture.md` — Technical architecture, class hierarchy, data layer, APIs
- `TuneHubSpecifications/tune_hub_product_strategy.md` — UX specification, pricing tiers, marketplace design, rollout plan
- `TuneHubSpecifications/tuner_implementation_plans.md` — Algorithm design, experimentation protocols, implementation phases for RePrompt, Dictation, and Agent tuners
