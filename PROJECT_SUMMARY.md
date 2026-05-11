# Wiztant — Project Summary

> **Last updated:** 2026-05-04 (post-cleanup: TuneHub credit system removed, WizType removed, old UI purged, preset system added, feature toggles active).  
> **Owner:** Pranav (solo project).  
> **Root directory:** `C:\whis\`

---

## Overview

**Wiztant** is a Windows AI operating assistant distributed as a portable executable (no installation required) and sold as SaaS. It enables hands-free computer control through a single hotkey (`F9`) with two active modes, plus a chat overlay toggled via `Ctrl+Space` and a clipboard optimizer via `Ctrl+Shift+Space`.

---

## Architecture (Three Separate Apps)

| Application | Stack | Entry Point | Purpose |
|---|---|---|---|
| **Python Backend** | Python 3.11 + FastAPI + WebSocket | `main.py` → `app/main.py` | Headless AI orchestration, STT, agent loop, tasks, memory, TuneHub |
| **Electron Overlay** | Electron 33 + React 19 + TypeScript + Tailwind + Framer Motion | `ui/whiztant-overlay/` | Active UI: pill, overlay, settings, task panels |
| **Marketing Website** | React 19 + Vite + Tailwind CSS v3 | `whiztant-website/` | Static SPA deployed to Netlify |

### Python Backend (Headless)
- **Entry:** `main.py` → `app/main.py` → `run_app()`
- **Servers:** FastAPI on `localhost:8765`, WebSocket bridge on `localhost:9120`
- **Tray:** PyQt6 used only for system tray icon (no main window)
- **Hotkeys:** F9 (dictation / agent toggle), Ctrl+Space (overlay), Ctrl+Shift+Space (WizPrompt), Esc (dismiss)
- **Core:** `core/` — 50+ modules (~17,700 lines)
- **Platform abstraction:** `platforms/factory.py` with lazy imports for cross-platform safety

### Electron Overlay (Active UI)
- **Location:** `ui/whiztant-overlay/`
- **Build:** `npm run build` → `out/`
- **Windows:** Pill (bottom-center wave), Overlay (340×420, Ctrl+Space), Settings (theme + toggles)
- **On-demand:** TaskPanel windows (one per task, 340×420, right of overlay)
- **IPC:** WebSocket `ws://localhost:9120` ↔ `core/ws_bridge.py`; direct FS read/write to `memory/tasks.json`
- **Performance:** `setOpacity(0/1)` only — never `hide()/show()`

### Marketing Website
- **Location:** `whiztant-website/`
- **Deploy:** Manual to Netlify (`deploy.bat`)
- **PostCSS:** `postcss.config.cjs` (CJS because `package.json` is ESM)

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11, FastAPI, WebSocket (port 9120), SQLite, Supabase client |
| **AI/ML** | Custom STT engine, VLM, agent engine, task classifier |
| **Desktop UI** | Electron 33, React 19, TypeScript, Tailwind CSS, Framer Motion, electron-vite |
| **Website** | React 19, Vite, Tailwind CSS v3 |
| **System integration** | Global hotkeys, system tray (PyQt6 minimal), window manager |
| **Data** | JSON files (`memory/`, `data/`), SQLite (`data/tune_hub.db`) |

**Removed subsystems:** `core/tts.py`, `core/wiztype/`, `core/tune_hub/credit_system/`, `ui/chat_overlay.py`, `ui/toast.py`

---

## Feature Modes

| Trigger | Mode | What It Does |
|---|---|---|
| **F9 ×1** | **Dictation** | STT engine transcribes → smart formatting → paste at cursor |
| **F9 ×2+** | **Agent Toggle** | Toggles UI-TARS agent mode on/off (screen-to-action loop) |
| **Ctrl+Space** | **Overlay Toggle** | Show/hide 340×420 overlay panel |
| **Ctrl+Shift+Space** | **WizPrompt** | Reads clipboard → optimizes via TuneHub persona weights + preset → writes back |
| **Esc** | **Dismiss** | Closes overlay |
| **F10** | **Task Voice** | PLANNED — voice-only task creation |

### Dictation Flow
1. F9 pressed once → starts recording
2. `core/stt_engine.py` + `core/stt_refiner.py` transcribe
3. `core/dictation_smart.py` applies smart formatting
4. `core/smart_paste.py` pastes at cursor
5. `core/dictation_memory.py` learns patterns

### Agent Flow
1. F9 pressed twice (or held) → toggles Agent mode
2. `core/agent_engine.py` + `core/agent.py` take control
3. Navigate, click, type via `core/navigation_brain.py` + `core/window_manager.py`
4. `core/guardrails.py` enforce safety limits
5. `core/background_agent.py` for ambient tasks

### RePrompt Flow
1. Ctrl+Shift+Space reads clipboard
2. `core/wizprompt.py` optimizes using:
   - TuneHub `RePromptTuner` `persona_weights`
   - Selected preset from `core/presets.py` (`system_prompt_addendum` + `agent_focus`)
3. Optimized text written back to clipboard / pasted

---

## Core Systems

### Task System
- **File:** `core/tasks.py`
- **Storage:** `memory/tasks.json` (canonical, shared Python + Electron)
- **Schema:** id, text, status, source, created_at, due_at, completed_at, parent_id, content, task_type (large/small), carried_over, failed, progress, reminder_sent, snoozed_until
- **Features:** Full CRUD, voice parsing, due-time extraction, LLM refiner, daily suggestion, snooze (15min/30min/1hr/1440min), reminders every 15min, pre-due 30min warning, carry-over, failed state
- **UI:** `TasksPanel.tsx`, `TaskPanel.tsx`, `TaskTile.tsx`

### Notification System
- **Queue:** `usePillNotifications.ts` manages notification queue
- **Renderer:** Dispatches to typed components (TaskSaved, DueAlert, DueReminder, DuplicateTask)
- **Python timers:** `_due_check()` at 18:00 daily, `_due_reminder()` every 4h for carried-over tasks, startup nudge at 8s
- **WebSocket broadcasts:** `due_alert`, `due_reminder`, `tasks_failed`, `task_saved`, `pill/notice`

### TuneHub (Phase 1)
- **Location:** `core/tune_hub/`
- **State:** Manual/seed tuning only — no model training pipeline yet
- **Tuners:** `DictationTuner` (sets `feature_input["text"]` via `process_transcription()`), `AgentTuner` (sets `feature_input["task"]`), `RePromptTuner` (provides `persona_weights` to `wizprompt.py`)
- **Middleware:** `_enabled` flag with `enable()`/`disable()`
- **Storage:** SQLite (`data/tune_hub.db`) + JSON (`data/tune_models/`)
- **Credit system:** REMOVED entirely

### Feature Toggles
- **Keys:** `agent`, `tunehub`, `tasks`, `reprompt` — all default `true`
- **Frontend:** `localStorage` + `Settings.tsx` toggles
- **Backend:** `data/settings.json` `"features"` key + conditional init blocks in `app/main.py`

### Preset System
- **File:** `core/presets.py`
- **Presets:** `product_review`, `idea_review`, `code_review`, `code_creation`, `general`
- **UI:** Dropdown in `WizPromptPanel.tsx`
- **API:** `GET /presets` in `core/server.py`

---

## Design System

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
- **Themes (5):** `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — persisted to `memory/theme.json`
- **Logo:** `wiztantW.svg` (always load from file, never generate programmatically)

---

## Pricing

| Plan | Monthly | Annual | Chat | Agent | UI-TARS |
|---|---|---|---|---|---|
| Free | $0 | — | 15/mo | — | — |
| Pro | $15 | $165/yr | 300/mo | 50/mo | 30/mo |
| Power | $25 | $275/yr | 500/mo | 200/mo | 200/mo |

- **Trial:** 3 days, 30 messages, 3 agent tasks, no credit card required
- Annual saves ~1 month vs monthly

---

## Authentication & Backend Services

| Service | Purpose |
|---|---|
| **Supabase** | Auth (email/password + Google OAuth), user data, insights tables |
| **Helicone** | Usage guard, cost tracking, request logging |
| **OpenRouter** | LLM gateway (GPT-5.4, UI-TARS 1.5 7B) |
| **Groq** | Whisper STT (cloud) |
| **LemonSqueezy** | License validation |

### Insights Schema
- `user_insights_lifetime` — lifetime counters per user (words dictated, fixes made, streaks, etc.)
- Daily insights table (implied)
- Row Level Security (RLS) policies ensure users can only read/upsert their own data.

---

## Development Commands

### Python Backend
```bash
pip install -r requirements.txt
python -c "import main"   # Verify imports
python main.py            # Run app
```

### Electron Overlay
```bash
cd ui/whiztant-overlay
npm run dev
npm run build             # Required before PyInstaller packaging
npm run typecheck
```

### Marketing Website
```bash
cd whiztant-website
npm run dev
npm run build
```

### Full Desktop Build
- **Windows:** `build/windows/build.bat`
- **Linux:** `build/linux/build.sh`
- **PyInstaller specs:** `build/windows/whiztant.spec`, `build/linux/whiztant_linux.spec`

---

## Directory Structure (Current)

```
C:\whis\
├── main.py                      # Entry point → delegates to app/main.py
├── app/
│   └── main.py                  # Bootstrap: FastAPI (8765) + WebSocket (9120) + tray + hotkeys
├── core/                        # Python backend modules (~17,700 lines)
│   ├── server.py                # FastAPI HTTP API
│   ├── ws_bridge.py             # WebSocket bridge (port 9120)
│   ├── tasks.py                 # Task CRUD, reminders, snooze
│   ├── presets.py               # RePrompt preset definitions
│   ├── wizprompt.py             # RePrompt engine
│   ├── wizprompt2.py
│   ├── hotkeys.py               # Global hotkey registration
│   ├── tray.py                  # System tray icon (PyQt6 minimal)
│   ├── stt_engine.py            # Speech-to-text
│   ├── stt_refiner.py
│   ├── dictation_smart.py
│   ├── dictation_memory.py
│   ├── smart_paste.py
│   ├── agent_engine.py          # Agent orchestration
│   ├── agent.py
│   ├── background_agent.py
│   ├── navigation_brain.py
│   ├── window_manager.py
│   ├── guardrails.py
│   ├── memory.py
│   ├── system_context.py
│   ├── vocab.py
│   ├── voice.py
│   ├── vlm.py
│   ├── task_classifier.py
│   ├── tune.py
│   ├── tune_prompts.py
│   ├── usage.py
│   ├── license.py
│   ├── supabase_client.py
│   ├── insights_tracker.py
│   ├── platform_backends.py
│   ├── system_access.py
│   └── tune_hub/                # TuneHub subsystem (Phase 1)
│       ├── middleware.py
│       ├── orchestrator.py
│       ├── storage.py
│       ├── tune_base.py
│       ├── base.py
│       ├── factory.py
│       ├── api/public.py
│       └── tuners/
│           ├── agent_tuner.py
│           ├── dictation_tuner.py
│           └── reprompt_tuner.py
├── data/
│   ├── settings.json            # App settings + feature flags
│   ├── tune_hub.db              # TuneHub SQLite database
│   └── tune_models/             # Tune model storage
├── memory/
│   ├── tasks.json               # Canonical task storage
│   ├── theme.json               # Active theme
│   ├── memory.json              # General memory
│   └── overlay_position.json    # Overlay window position
├── ui/
│   ├── whiztant-overlay/        # Electron overlay app
│   │   └── src/
│   │       ├── main/index.ts    # Electron main process
│   │       └── renderer/
│   │           ├── components/  # Overlay, Pill, TasksPanel, etc.
│   │           ├── settings/    # Settings, InsightsTab
│   │           └── shared/      # IPC, themes, types, useBridge, notifications
│   └── react_overlay.py         # React overlay launcher
├── whiztant-website/            # Marketing website
├── platforms/                   # OS abstraction layer
├── agent_rules/                 # Markdown specs for agent navigation
├── tests/                       # Pytest suite (~313 cases)
├── scripts/                     # STT stress tests, real-voice tests
├── build/
│   ├── windows/
│   └── linux/
└── TuneHubSpecifications/       # Roadmap specs (not yet implemented)
```

---

## Key Technical Decisions

1. **Portable executable** — No installer required; runs from any folder
2. **Headless Python backend** — No PyQt6 main window; all UI lives in Electron
3. **Opacity-based overlay toggle** — `setOpacity(0/1)` avoids Windows DWM repaint lag
4. **Dual STT pipeline** — Groq cloud primary, faster-whisper local fallback
5. **Helicone proxy** — All LLM requests routed through Helicone for usage tracking
6. **CJS PostCSS config** — Required because `package.json` has `"type": "module"`
7. **Direct FS task sync** — Electron main reads/writes `memory/tasks.json` directly to avoid IPC latency for task CRUD

---

## Known Limitations & Improvement Areas

- Overlay dropdown menus styling has theme variable gaps
- File upload refs in attach menu are wired but not connected to a backend handler
- No E2E tests for the overlay IPC protocol
- Website deploy is manual (`deploy.bat`) — no CI/CD pipeline
- F10 task hotkey planned but not implemented
- TypeScript `tsc --noEmit` verification not automated
- Python import test (`python -c "import main"`) not automated
- TuneHub Phase 2 (actual model training) not yet implemented

---

## Definition of Done

1. Code compiles / imports without errors (Python + TypeScript)
2. The specific behavior requested works — verified manually or via test
3. No regressions in F9 dictation, F9 agent toggle, Ctrl+Space overlay, pill notifications, task system
4. No new files created unless necessary
5. Build artifacts up to date (`npm run build` for UI changes, `python main.py` clean start for Python changes)

---

*Generated for Wiztant project documentation. Solo project by Pranav.*
