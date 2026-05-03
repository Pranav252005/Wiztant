# Wiztant — Application Memory

> **Last updated:** Post-cleanup (TuneHub credit system removed, WizType removed, all old UI purged).  
> **Owner:** Pranav (solo project).  
> **Root directory:** `C:\whis\`

---

## 1. Product Identity

- **Name:** Wiztant (formerly "Whiztant" — old name, never use in new docs)
- **What it is:** Windows AI operating assistant — portable `.exe` (no installation required), sold as SaaS
- **Builder:** Pranav, solo project
- **Distribution:** Single portable executable; no installer, no registry writes
- **Root directory:** `C:\whis\` (expected working directory at runtime)

---

## 2. Architecture (3 Apps)

### 2.1 Python Backend (headless)
- **Entry point:** `main.py` → delegates to `app/main.py`
- **What it does:**
  - Starts FastAPI server on **port 8765**
  - Starts WebSocket bridge on **port 9120**
  - Initializes system tray icon (uses PyQt6 only for the tray, **not** a main window)
  - Registers global hotkeys (F9, Ctrl+Space, Ctrl+Shift+Space, Esc)
  - The backend is **headless** — there is no PyQt6 main window; all visual UI lives in the Electron overlay
- **Process role:** AI orchestration, dictation pipeline, task scheduling, TuneHub tuning, feature gating

### 2.2 Electron Overlay (active UI)
- **Location:** `ui/whiztant-overlay/`
- **Stack:** Electron + React 19 + TypeScript + Tailwind CSS + Framer Motion + electron-vite
- **Windows:**
  - **Pill** — bottom-center always-on-top wave indicator (`Pill.tsx`)
  - **Overlay** — 340×420 main panel, toggled with `Ctrl+Space`
  - **Settings** — configuration window
  - **TaskPanel** — on-demand frameless windows, one per task, 340×420, positioned to the right of the overlay
- **IPC mechanism:** Electron ↔ Python via WebSocket `ws://localhost:9120` (implemented in `core/ws_bridge.py` ↔ `renderer/shared/useBridge.ts`)
- **Direct FS access:** Electron main process reads/writes `memory/tasks.json` via Node `fs` module (canonical task storage)

### 2.3 Marketing Website
- **Location:** `whiztant-website/`
- **Stack:** React + Vite + Tailwind CSS v3
- **Deploy:** `deploy.bat` → Netlify (currently manual)
- **PostCSS config:** `postcss.config.cjs` (CJS because `package.json` has `"type": "module"`)

---

## 3. Tech Stack (Current Only)

| Layer | Technologies |
|---|---|
| **Backend** | Python 3, FastAPI, WebSocket (port 9120), SQLite, Supabase client |
| **AI/ML** | Custom STT engine, VLM (vision-language model), agent engine, task classifier |
| **Desktop UI** | Electron, React 19, TypeScript, Tailwind CSS, Framer Motion, electron-vite |
| **Website** | React, Vite, Tailwind CSS v3 |
| **System integration** | Global hotkeys, system tray (PyQt6 minimal), window manager |
| **Data** | JSON files (`memory/`, `data/`), SQLite (`data/tune_hub.db`) |

**Removed / No longer in codebase:**
- PyQt6 main window (backend is headless)
- `core/wiztype/` — entire subsystem removed
- `ui/wiztant-clui/` — does not exist
- `ui/wiztant-app/` — does not exist
- `core/tts.py` — removed
- Credit system in TuneHub — removed entirely

---

## 4. Directory Structure (Only What Exists Now)

```
C:\whis\
├── main.py                      # Entry point — delegates to app/main.py
├── app/
│   └── main.py                  # Backend bootstrap (FastAPI + WebSocket + tray + hotkeys)
├── core/                        # Python backend modules
│   ├── __init__.py
│   ├── agent.py
│   ├── agent_engine.py
│   ├── agent_isolation.py
│   ├── agent_task_queue.py
│   ├── agent_unified.py
│   ├── background_agent.py
│   ├── dictation_memory.py
│   ├── dictation_smart.py
│   ├── guardrails.py
│   ├── hotkeys.py
│   ├── insights_tracker.py
│   ├── license.py
│   ├── memory.py
│   ├── navigation_brain.py
│   ├── platform_backends.py
│   ├── presets.py               # RePrompt preset definitions
│   ├── server.py                # FastAPI HTTP API (port 8765)
│   ├── smart_paste.py
│   ├── stt_engine.py
│   ├── stt_refiner.py
│   ├── supabase_client.py
│   ├── system_access.py
│   ├── system_context.py
│   ├── task_classifier.py
│   ├── tasks.py                 # Task CRUD + reminders + snooze
│   ├── toast.py
│   ├── tray.py                  # System tray (PyQt6 minimal)
│   ├── tune.py
│   ├── tune_prompts.py
│   ├── usage.py
│   ├── vlm.py
│   ├── vocab.py
│   ├── voice.py
│   ├── window_manager.py
│   ├── wizprompt.py             # RePrompt engine (consumes TuneHub persona_weights + presets)
│   ├── wizprompt2.py
│   ├── ws_bridge.py             # WebSocket bridge (port 9120)
│   └── tune_hub/                # TuneHub subsystem (post-cleanup)
│       ├── __init__.py
│       ├── base.py
│       ├── factory.py
│       ├── middleware.py        # Has _enabled flag with enable()/disable()
│       ├── orchestrator.py
│       ├── storage.py
│       ├── tune_base.py
│       ├── api/
│       │   └── public.py
│       ├── tuners/
│       │   ├── agent_tuner.py   # Sets feature_input["task"]
│       │   ├── dictation_tuner.py  # Calls process_transcription(), sets feature_input["text"]
│       │   └── reprompt_tuner.py   # Provides persona_weights to wizprompt.py
│       └── tests/
│           ├── test_base.py
│           ├── test_middleware.py
│           ├── test_orchestrator.py
│           ├── test_storage.py
│           ├── test_tuners.py
│           └── test_utils.py
├── data/
│   ├── settings.json            # App settings + feature flags
│   ├── tune_hub.db              # TuneHub SQLite database
│   └── tune_models/             # Tune model storage
├── memory/
│   ├── tasks.json               # Canonical task storage (shared Python + Electron)
│   ├── theme.json               # Active theme
│   ├── memory.json              # General memory
│   └── overlay_position.json    # Overlay window position
├── ui/
│   └── whiztant-overlay/        # Electron overlay app
│       └── src/
│           ├── main/
│           │   └── index.ts     # Electron main process
│           └── renderer/
│               ├── shared/
│               │   ├── ipc.ts
│               │   ├── themes.ts
│               │   ├── types.ts
│               │   ├── useBridge.ts     # WebSocket hook ↔ ws_bridge.py
│               │   ├── usePillNotifications.ts
│               │   └── notifications/   # Notification components
│               ├── components/
│               │   ├── AgentPanel.tsx
│               │   ├── MemoriesPanel.tsx
│               │   ├── MemoryPanel.tsx
│               │   ├── Overlay.tsx
│               │   ├── Pill.tsx
│               │   ├── StreakPanel.tsx
│               │   ├── TaskPanel.tsx
│               │   ├── TaskTile.tsx
│               │   ├── TasksPanel.tsx
│               │   ├── TopTabBar.tsx
│               │   ├── TopTabContent.tsx
│               │   ├── TuneHubPanel.tsx
│               │   ├── VocabCorrectModal.tsx
│               │   └── WizPromptPanel.tsx   # Has preset dropdown
│               ├── settings/
│               │   ├── Settings.tsx
│               │   └── InsightsTab.tsx
│               └── ...
├── whiztant-website/            # Marketing website
│   ├── deploy.bat               # Manual deploy to Netlify
│   └── postcss.config.cjs       # CJS config (package.json is ESM)
├── platforms/
├── scripts/
├── tests/                       # Root-level tests
├── vendor/
├── build.bat
├── requirements.txt
└── .windsurfrules, AGENTS.md, CLAUDE.md, etc.
```

---

## 5. Core Features & Data Flow

### Dictation (F9 ×1)
1. F9 pressed once → starts recording
2. STT engine (`core/stt_engine.py` + `core/stt_refiner.py`) transcribes
3. `core/dictation_smart.py` applies smart formatting
4. Text pasted at cursor position (`core/smart_paste.py`)
5. `core/dictation_memory.py` learns patterns

### Agent Mode (F9 ×2+)
1. F9 pressed twice (or held) → toggles Agent mode on/off
2. Agent engine (`core/agent_engine.py` + `core/agent.py`) takes control
3. Can navigate, click, type via `core/navigation_brain.py` + `core/window_manager.py`
4. Guardrails (`core/guardrails.py`) enforce safety limits
5. Background agent (`core/background_agent.py`) for ambient tasks

### RePrompt (Ctrl+Shift+Space)
1. Reads clipboard
2. `core/wizprompt.py` optimizes content using:
   - TuneHub `RePromptTuner` `persona_weights`
   - Selected preset from `core/presets.py` (adds `system_prompt_addendum` + `agent_focus`)
3. Optimized text written back to clipboard / pasted

### WizPrompt Panel + Presets
- UI: `WizPromptPanel.tsx` has a dropdown for presets
- Backend: `core/presets.py` defines defaults
- API: `GET /presets` in `core/server.py`
- Presets: `product_review`, `idea_review`, `code_review`, `code_creation`, `general`

### Task System
- Full CRUD in `core/tasks.py`
- UI: `TasksPanel.tsx`, `TaskPanel.tsx`, `TaskTile.tsx`
- Storage: `memory/tasks.json`
- Reminders: 15-minute check cycle
- Snooze: 4 presets (15min, 30min, 1hr, 1440min)

### TuneHub Tuning
- `DictationTuner.apply()` → calls `process_transcription()`, sets `feature_input["text"]`
- `AgentTuner.apply()` → modifies task, sets `feature_input["task"]`
- `RePromptTuner` → provides `persona_weights` consumed by `core/wizprompt.py`
- `middleware.py` has `_enabled` flag with `enable()`/`disable()` methods

---

## 6. Communication (Python ↔ Electron)

| Channel | Port / Path | Purpose |
|---|---|---|
| **WebSocket** | `ws://localhost:9120` | Real-time bidirectional IPC: notifications, state sync, commands |
| **HTTP API** | `http://localhost:8765` | FastAPI REST endpoints (e.g., `GET /presets`) |
| **Direct FS** | `memory/tasks.json` | Electron main reads/writes tasks directly via Node `fs` |

- WebSocket bridge: `core/ws_bridge.py` (Python) ↔ `renderer/shared/useBridge.ts` (Electron renderer)
- HTTP API: `core/server.py` (FastAPI)

---

## 7. TuneHub Architecture (Post-Cleanup)

TuneHub is the adaptive tuning subsystem. After cleanup, it contains:

### Files
```
core/tune_hub/
├── __init__.py
├── base.py
├── factory.py
├── middleware.py          # _enabled flag, enable()/disable() methods
├── orchestrator.py
├── storage.py
├── tune_base.py
├── api/
│   └── public.py
├── tuners/
│   ├── agent_tuner.py     # Sets feature_input["task"]
│   ├── dictation_tuner.py # Calls process_transcription(), sets feature_input["text"]
│   └── reprompt_tuner.py  # Provides persona_weights to wizprompt.py
└── tests/
    ├── test_base.py
    ├── test_middleware.py
    ├── test_orchestrator.py
    ├── test_storage.py
    ├── test_tuners.py
    └── test_utils.py
```

### Key Behaviors
- **Phase 1 (current):** Manual/seed tuning — no actual model training yet
- **Phase 2 (future):** Actual model training pipeline
- **Credit system:** REMOVED — no `CreditBudget`, no `InsufficientCreditsError`, no pricing tiers enforced in TuneHub
- **Middleware:** Can be globally enabled/disabled via `enable()`/`disable()`

### Removed from TuneHub
- `core/tune_hub/credit_system/` (entire directory — `abstract.py`, `free_tracker.py`, `pro_tracker.py`, `__init__.py`)
- `core/tune_hub/tests/test_credit_system.py`
- `core/tune_hub/tests/test_marketplace.py`

---

## 8. Feature Toggles System

### 4 Features
| Key | Description | Default |
|---|---|---|
| `agent` | Agent mode (F9 ×2) | `true` |
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

## 9. Preset System (RePrompt)

- **File:** `core/presets.py` (new addition)
- **Default presets:** `product_review`, `idea_review`, `code_review`, `code_creation`, `general`
- **UI:** Dropdown selector in `WizPromptPanel.tsx`
- **API:** `GET /presets` exposed in `core/server.py`
- **Integration:** `core/wizprompt.py` consumes the selected preset's `system_prompt_addendum` + `agent_focus`

---

## 10. Task System & Reminders (with Snooze)

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
- **4 presets:** 15min, 30min, 1hr, 1440min (tomorrow)
- **Functions in `core/tasks.py`:**
  - `snooze_task(task_id, minutes)`
  - `is_snoozed(task)`
  - `clear_snooze(task_id)`

### Settings (tasks tab)
- Reminder interval
- Default due time
- Snooze presets
- Pre-due warning toggle
- Carry-over toggle

---

## 11. Hotkeys & Shortcuts (Only Existing)

| Trigger | Action |
|---|---|
| **F9 ×1** | Dictation: record → transcribe → paste at cursor |
| **F9 ×2+** | Toggle Agent mode on/off |
| **Ctrl+Space** | Toggle overlay open/close (340×420 panel) |
| **Ctrl+Shift+Space** | WizPrompt: optimize clipboard contents |
| **Esc** | Dismiss overlay |

**Not yet built:** F10 task hotkey (voice-only task creation)

---

## 12. Design System (Verified)

### Themes (5)
| Theme | Status |
|---|---|
| `onyx` | Available |
| `graphite` | Available |
| `porcelain` | Available |
| `midnight` | Available |
| `ember` | Available |

- **Persistence:** `memory/theme.json`
- **Tokens defined in:** `renderer/shared/themes.ts`

### Approximate Color Tokens (from code)
- Background: `#07070f`
- Surface: `#0f0f1a`
- Primary: `#c0c1ff` (indigo)
- Secondary: `#d0bcff` (purple)
- Tertiary: `#4cd7f6` (teal)
- Text: `#e2e2e2`
- Muted: `#6b7280`

---

## 13. File Quick Reference (Accurate Paths)

### Entry & Bootstrap
| File | Role |
|---|---|
| `main.py` | Root entry — delegates to `app/main.py` |
| `app/main.py` | Bootstrap: FastAPI (8765) + WebSocket (9120) + tray + hotkeys |

### Core Backend
| File | Role |
|---|---|
| `core/server.py` | FastAPI HTTP API |
| `core/ws_bridge.py` | WebSocket bridge (port 9120) |
| `core/tasks.py` | Task CRUD, reminders, snooze |
| `core/presets.py` | RePrompt preset definitions |
| `core/wizprompt.py` | RePrompt engine |
| `core/hotkeys.py` | Global hotkey registration |
| `core/tray.py` | System tray icon |
| `core/stt_engine.py` | Speech-to-text |
| `core/agent_engine.py` | Agent orchestration |
| `core/tune_hub/orchestrator.py` | TuneHub orchestration |
| `core/tune_hub/middleware.py` | Enable/disable gating |

### Electron Overlay
| File | Role |
|---|---|
| `ui/whiztant-overlay/src/main/index.ts` | Electron main process |
| `ui/whiztant-overlay/src/renderer/components/Overlay.tsx` | Main overlay panel |
| `ui/whiztant-overlay/src/renderer/components/Pill.tsx` | Bottom wave indicator |
| `ui/whiztant-overlay/src/renderer/components/TopTabBar.tsx` | Tab navigation |
| `ui/whiztant-overlay/src/renderer/components/WizPromptPanel.tsx` | RePrompt UI |
| `ui/whiztant-overlay/src/renderer/components/TasksPanel.tsx` | Task list |
| `ui/whiztant-overlay/src/renderer/components/Settings.tsx` | Settings window |
| `ui/whiztant-overlay/src/renderer/shared/useBridge.ts` | WebSocket hook |
| `ui/whiztant-overlay/src/renderer/shared/themes.ts` | Theme tokens |

### Data Files
| File | Role |
|---|---|
| `memory/tasks.json` | Task canonical storage |
| `memory/theme.json` | Active theme |
| `memory/memory.json` | General memory |
| `memory/overlay_position.json` | Overlay position |
| `data/settings.json` | App settings + feature flags |
| `data/tune_hub.db` | TuneHub SQLite |
| `data/tune_models/` | Tune model storage |

---

## 14. Recent Changes (What Was Just Done)

1. **WizType subsystem removed** — entire `core/wiztype/` directory deleted; no longer part of the app
2. **Old UI purged** — `ui/wiztant-clui/`, `ui/wiztant-app/` do not exist; `ui/chat_overlay.py`, `ui/toast.py` removed
3. **TuneHub credit system removed** — entire `credit_system/` directory + tests deleted; no pricing tiers enforced in backend
4. **Removed core files:** `action_optimizer.py`, `agent_s3_wrapper.py`, `app_detector.py`, `intent_compiler.py`, `learning_agent.py`, `shortcuts_loader.py`, `system_task_executor.py`, `tts.py`, `workflow_recorder.py`
5. **Removed tests:** All `test_wiztype_*.py` files, `test_credit_system.py`, `test_marketplace.py`
6. **Removed misc:** `main_old.py`, root `package-lock.json`, `docs/WIZTYPE.md`, `data/wiztype_config.json`
7. **TuneHub fixes applied:**
   - `DictationTuner.apply()` now calls `process_transcription()` and sets `feature_input["text"]`
   - `AgentTuner.apply()` now modifies task and sets `feature_input["task"]`
   - `core/wizprompt.py` consumes `persona_weights` from TuneHub `RePromptTuner`
   - `middleware.py` has `_enabled` flag with `enable()`/`disable()` methods
8. **Preset system added:** `core/presets.py` with 5 default presets, integrated into `WizPromptPanel.tsx` and `core/server.py`
9. **Backend clarified as headless** — no PyQt6 main window; tray-only

---

## 15. What Still Needs Building

| Item | Status |
|---|---|
| **F10 task hotkey** | Not built — voice-only task creation planned |
| **Website CI/CD** | Currently manual via `deploy.bat`; needs automated pipeline |
| **Build verification (TypeScript)** | `tsc --noEmit` after TS changes — not yet automated |
| **Python import test** | `python -c "import main"` after Python changes — not yet automated |
| **TuneHub Phase 2** | Actual model training (currently Phase 1: manual/seed only) |

---

## 16. Definition of Done

1. Code compiles/imports without errors
2. Specific behavior requested works
3. No regressions in:
   - F9 modes (dictation + agent toggle)
   - Overlay toggle (Ctrl+Space)
   - Pill notifications
   - Task system (CRUD + reminders + snooze)
4. No new files unless necessary
5. Build artifact up to date:
   - `npm run build` for UI
   - `python main.py` starts cleanly for backend

---

## Appendix: Legacy Features — DO NOT USE

The following were removed during cleanup and must not be referenced in new code or documentation:

- `core/wiztype/` (entire subsystem)
- `core/tune_hub/credit_system/` (entire directory)
- `core/action_optimizer.py`, `core/agent_s3_wrapper.py`, `core/app_detector.py`, `core/intent_compiler.py`, `core/learning_agent.py`, `core/shortcuts_loader.py`, `core/system_task_executor.py`, `core/tts.py`, `core/workflow_recorder.py`
- `tests/test_wiztype_*.py`
- `core/tune_hub/tests/test_credit_system.py`, `test_marketplace.py`
- `ui/chat_overlay.py`, `ui/toast.py`
- `main_old.py`, root `package-lock.json`, `docs/WIZTYPE.md`, `data/wiztype_config.json`
- "Whiztant" branding (old name)
