# Wiztant — Comprehensive Application Memory

> **Last updated:** 2026-05-04  
> **Product:** Wiztant — Windows AI Operating Assistant  
> **Builder:** Pranav (solo project)  
> **Distribution:** Portable `.exe` (no install), sold as SaaS  
> **Root:** `C:\whis\`  

---

## 1. Product Identity

**Wiztant** is a Windows-native AI productivity assistant that operates as an overlay on top of any application. It provides voice-controlled dictation, conversation, autonomous agent execution, task management with smart reminders, AI prompt optimization (RePrompt), and an AI calibration engine (TuneHub) that learns user preferences across all features.

The name is **Wiztant** (never "Whiztant" — that was the old name).

---

## 2. Architecture — Three Separate Applications

### 2.1 Python Backend (Headless)
- **Entry:** `main.py` — starts FastAPI (port 8765), WebSocket bridge (port 9120), system tray, global hotkeys, feature initialization
- **No PyQt6 main window.** Python is entirely headless backend + system tray icon.
- **Core modules:** `core/llm_interface.py`, `core/memory.py`, `core/tasks.py`, `core/agent.py`, `core/shared/agent.py`, `core/voice.py`, `core/hotkeys.py`, `core/ws_bridge.py`, `core/server.py`, `core/tune_hub/`, `core/wizprompt.py`, `core/wiztype/`, `core/background_agent.py`, `core/vocab.py`, `core/system_context.py`, `core/navigation_brain.py`
- **Agent rules:** `agent_rules/` — markdown specs for navigation, shortcuts, and apps (used by the autonomous agent)

### 2.2 Electron Overlay (ACTIVE UI)
- **Location:** `ui/whiztant-overlay/` ← **This is the one to edit**
- **Stack:** Electron + React 19 + TypeScript + Tailwind CSS + Framer Motion + electron-vite + Lucide React
- **Windows:**
  - **Pill** — bottom-center always-on-top wave indicator (state-aware coloring)
  - **Overlay** — 340×420 main panel (Chat/Memories/Tasks/Agent/TuneHub tabs), toggled via `Ctrl+Alt+W`
  - **Settings** — configuration window (API keys, theme, WizType, feature toggles, presets)
  - **TaskPanel** — on-demand per-task edit window (340×420 frameless, positioned right of overlay)
- **IPC:** Electron ↔ Python via WebSocket on `ws://localhost:9120` (`ws_bridge.py`)
- **Direct FS access:** Electron main also reads/writes `memory/tasks.json` directly via Node fs

### 2.3 Marketing Website
- **Location:** `whiztant-website/`
- **Stack:** React + Vite + Tailwind CSS v3
- **Deploy:** `deploy.bat` → Netlify
- **PostCSS config:** `postcss.config.cjs` (CJS, not `.js`, because `package.json` has `"type": "module"`)

### Legacy — Do Not Use
- `ui/wiztant-clui/` — archived, superseded by `whiztant-overlay`
- `ui/wiztant-app/` — older React app, also superseded

---

## 3. Tech Stack

| Layer | Language | Runtime / Framework / Libraries |
|---|---|---|
| Python backend | Python 3.12 | asyncio, uvicorn, FastAPI, websockets, pynput, Pillow, PyQt5 (tray only) |
| Electron overlay | TypeScript | React 19, Electron, Vite, Framer Motion, Tailwind CSS, Lucide React, esbuild |
| Website | TypeScript / JSX | React, Vite, Tailwind CSS v3 |
| Voice Wake Word | — | Picovoice Porcupine ("Whiz" wake word) |
| Voice STT | — | Picovoice Cheetah (on-device streaming STT) |
| LLM Routing | — | Groq, OpenRouter, OpenAI-compatible APIs via `LLMInterface` |
| TTS | — | Kokoro (local), 6 voices, `af_nova` default |
| Agent Planner | — | Qwen 3.6 Plus free via OpenRouter (text-only) |
| Agent Executor | — | UI-TARS 1.5 7B via OpenRouter (vision) |
| Auth | — | Supabase |
| Cost Tracking | — | Helicone |
| Vector Search | — | ChromaDB (for memory semantic search) |
| Dev Tools | — | `uv` for Python package management, `npm` for frontend |

---

## 4. Directory Structure

```
C:\whis\
├── main.py                          # Application entry point
├── core/
│   ├── llm_interface.py             # Unified LLM abstraction (groq, openrouter, etc.)
│   ├── memory.py                    # Memory storage + ChromaDB semantic search
│   ├── tasks.py                     # Task CRUD, reminders, snooze, due-time logic
│   ├── agent.py                     # Main agent orchestrator
│   ├── shared/
│   │   └── agent.py                 # Agent execution engine with 16+ tools
│   ├── voice.py                     # Voice recording + TTS + wake word
│   ├── hotkeys.py                   # Global hotkey handling (pynput)
│   ├── ws_bridge.py                 # WebSocket bridge (Python ↔ Electron)
│   ├── server.py                    # FastAPI HTTP server (port 8765)
│   ├── wizprompt.py                 # RePrompt prompt optimization engine
│   ├── wizprompt2.py                # Backup/secondary prompt optimizer
│   ├── presets.py                   # Preset system for RePrompt (NEW)
│   ├── tune_hub/                    # AI calibration engine
│   │   ├── middleware.py            # Request interception + tuner routing
│   │   ├── orchestrator.py          # Pipeline: input → tune → apply → sync
│   │   ├── factory.py               # Service factory + lifespan
│   │   ├── base.py                  # TuneMeta, TuneRequest, TuneResult
│   │   ├── tune_base.py             # BaseTuner, TuneModel, TuneStore
│   │   ├── storage.py               # Tune persistence
│   │   ├── api/
│   │   │   └── public.py            # Public API endpoints
│   │   └── tuners/
│   │       ├── dictation_tuner.py   # Dictation/text correction tuner
│   │       ├── agent_tuner.py       # Agent recipe tuner
│   │       └── wizprompt_tuner.py   # RePrompt persona tuner
│   ├── wiztype/                     # Keyboard prediction subsystem
│   ├── background_agent.py          # Background/idle agent manager
│   ├── vocab.py                     # Vocab correction system
│   ├── system_context.py            # System context scanner
│   ├── navigation_brain.py          # App navigation brain
│   ├── guardrails.py              # Content safety guardrails
│   └── __init__.py                  # Core package init with middleware integration
├── app/
│   └── main.py                      # FastAPI app with middleware + routes
├── ui/
│   ├── whiztant-overlay/            # ACTIVE Electron UI
│   │   ├── src/
│   │   │   ├── main/                # Electron main process + IPC
│   │   │   ├── preload/             # Preload script (bridge exposure)
│   │   │   ├── renderer/
│   │   │   │   ├── overlay/         # Overlay components (Chat, Tasks, Agent, TuneHub)
│   │   │   │   │   ├── Overlay.tsx      # Main overlay shell
│   │   │   │   │   ├── TopTabBar.tsx    # Tab navigation bar
│   │   │   │   │   ├── ChatPanel.tsx      # Chat interface
│   │   │   │   │   ├── AgentPanel.tsx     # Agent execution panel
│   │   │   │   │   ├── TasksPanel.tsx     # Task list view
│   │   │   │   │   ├── TaskTile.tsx       # Individual task card
│   │   │   │   │   ├── TaskPanel.tsx      # Per-task edit panel
│   │   │   │   │   ├── TuneHubPanel.tsx   # TuneHub calibration UI
│   │   │   │   │   ├── WizPromptPanel.tsx # RePrompt optimization UI
│   │   │   │   │   └── Ghost.tsx          # Memory ghost overlay
│   │   │   │   ├── pill/            # Pill wave indicator
│   │   │   │   │   └── Pill.tsx
│   │   │   │   ├── settings/        # Settings panels
│   │   │   │   │   └── Settings.tsx     # Main settings (API, theme, features)
│   │   │   │   └── shared/          # Shared hooks, types, utils
│   │   │   │       ├── useBridge.ts     # WebSocket bridge hook
│   │   │   │       ├── useAudioRecorder.ts # Voice recording hook
│   │   │   │       ├── useTasks.ts      # Tasks state hook
│   │   │   │       ├── ipc.ts           # IPC handlers (Electron ↔ renderer)
│   │   │   │       └── notifications/   # Notification system
│   │   │   └── assets/              # Static assets
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── tsconfig.json
│   ├── react_overlay_runner.py      # Python runner for React overlay
│   └── wiztant-clui/                # ARCHIVED — do not use
├── whiztant-website/                # Marketing website
├── agent_rules/                     # Agent navigation specs (markdown)
├── memory/                          # Runtime data storage
│   ├── tasks.json                   # Task canonical storage
│   ├── theme.json                   # Active theme
│   ├── vocab.json                   # Vocab corrections
│   ├── settings.json                # App settings
│   └── chroma_db/                   # ChromaDB vector store
├── data/                            # Static/config data
├── docs/                            # Documentation
├── requirements.txt                 # Python dependencies
└── wiztantW.svg                   # Logo (load from file, never regenerate)
```

---

## 5. Core Features & Data Flow

### 5.1 Feature Overview (with Toggle Support)

| Feature | Toggle Key | What It Does | Trigger |
|---|---|---|---|
| **Chat / Tune** | N/A (always on) | Conversational AI with memory + web search | Type in chat panel |
| **Memories** | N/A (always on) | Voice/text memory capture with semantic search | `Alt+M` toggle, `Alt+G` ghost |
| **Agent** | `features.agent` | Autonomous task execution with 16+ tools | `F9` double-tap |
| **TuneHub** | `features.tunehub` | AI calibration — learns user preferences per feature | Background (intercepted) |
| **Tasks** | `features.tasks` | Task management with smart reminders + snooze | Voice or manual add |
| **RePrompt** | `features.reprompt` | Ctrl+Shift+Space prompt optimization with presets | `Ctrl+Shift+Space` |

### 5.2 Voice Flow

```
User says "Whiz" → Porcupine wake word → Pill shows listening state
User speaks → Cheetah STT streams text → Sent to Python backend
Backend routes to appropriate feature (chat/agent/task/dictation)
Response generated via LLMInterface → Kokoro TTS → Audio playback
Pill wave state changes: idle → recording → thinking → speaking → idle
```

### 5.3 Dictation Flow

```
F9 ×1 tap → Voice recording starts → Cheetah STT → Text generated
→ TuneHub DictationTuner applies learned corrections →
→ Text pasted at cursor position (simulated keystrokes via pynput)
```

### 5.4 Agent Flow

```
F9 double-tap → Agent mode activated
User speaks task → LLM planner (Qwen) generates step plan
→ Each step: screenshot → UI-TARS vision model → action (click/type/scroll)
→ AgentTuner injects learned recipes if available
→ Step progress streamed to AgentPanel.tsx in real-time
→ Completion/done/result states shown in overlay
```

### 5.5 RePrompt Flow

```
Ctrl+Shift+Space → WizPromptPanel opens
User enters raw prompt → Selects preset (optional) → Optimize
→ Preset system_prompt_addendum injected
→ 3 AI agents run in parallel: structure, semantic, edge_case
→ Results synthesized into optimized prompt
→ History tracked with reversion support
```

### 5.6 TuneHub Flow

```
Every feature request (dictation, agent, reprompt) passes through TuneHub middleware
Middleware checks if a learned TuneModel exists for the feature context
If yes: Tuner.apply() transforms the input (corrections, recipes, personas)
Tuned output forwarded to the actual feature
User feedback (thumbs up/down) triggers incremental learning
Tune models synced to backend for cross-device use
```

---

## 6. Communication (Python ↔ Electron)

### 6.1 WebSocket Bridge (Port 9120)
- **File:** `core/ws_bridge.py` (Python server) + `renderer/shared/useBridge.ts` (Electron client)
- **Protocol:** Bidirectional JSON messages

**Electron → Python message types:**
- `voice_command` — Voice input to process
- `optimize_prompt` — RePrompt optimization request
- `tasks/*` — Task CRUD operations
- `chat` — Chat messages
- `features/update` — Feature toggle changes
- `features/get` — Request current feature flags
- `tasks/snooze` — Snooze a task
- `tasks/settings/set` — Task settings update
- `tune/*` — TuneHub calibration requests

**Python → Electron message types:**
- `chat/stream` — Streaming chat responses
- `agent/step` — Agent execution step updates
- `due_alert` — Task due alert (6pm first miss)
- `due_reminder` — Overdue reminder (every 15 min when overdue)
- `due_soon` — Pre-due warning (30 min before due)
- `tasks/update` — Task list refresh
- `features/update` — Feature toggle broadcast (cross-client sync)
- `pill/*` — Pill state changes and notifications
- `tune/ready` — TuneHub model ready notification

### 6.2 HTTP API (Port 8765)
- **File:** `core/server.py` (FastAPI)
- **Endpoints:**
  - `POST /chat` — Chat completion
  - `POST /wizprompt/optimize` — Prompt optimization
  - `GET /presets` — List all RePrompt presets
  - `GET /tasks` — Get all tasks
  - `POST /tasks` — Create task
  - `PUT /tasks/{id}` — Update task
  - `DELETE /tasks/{id}` — Delete task
  - `GET /tunes` — List TuneHub models
  - `POST /tunes` — Create tune
  - `GET /tunes/{id}` — Get tune details
  - `POST /tunes/{id}/feedback` — Submit tune feedback
  - `POST /tunes/{id}/share` — Share tune
  - `POST /tunes/{id}/rollback` — Rollback tune

### 6.3 Direct File Access
- **Tasks:** Electron main reads/writes `memory/tasks.json` directly via Node fs
- **Theme:** `memory/theme.json` — read by both Python and Electron
- **Settings:** `memory/settings.json` — feature toggles and app config
- **Vocab:** `memory/vocab.json` — learned word corrections

---

## 7. TuneHub Architecture (AI Calibration Engine)

### 7.1 Purpose
TuneHub is an AI calibration engine that intercepts feature requests, applies learned user preference models (tunes), and continuously improves based on user feedback (thumbs up/down).

### 7.2 Components

| Component | File | Role |
|---|---|---|
| **Middleware** | `core/tune_hub/middleware.py` | Intercepts all feature requests, routes to tuners |
| **Orchestrator** | `core/tune_hub/orchestrator.py` | Pipeline: validate → resolve model → apply → sync |
| **Factory** | `core/tune_hub/factory.py` | Creates services with lifespan management |
| **Base** | `core/tune_hub/base.py` | TuneMeta, TuneRequest, TuneResult dataclasses |
| **TuneBase** | `core/tune_hub/tune_base.py` | BaseTuner, TuneModel, TuneStore |
| **Storage** | `core/tune_hub/storage.py` | Tune persistence layer |
| **API** | `core/tune_hub/api/public.py` | REST endpoints for tunes |

### 7.3 Tuners

| Tuner | File | What It Tunes | Output Key |
|---|---|---|---|
| **DictationTuner** | `tuners/dictation_tuner.py` | Text corrections, word substitutions, formatting | `text` |
| **AgentTuner** | `tuners/agent_tuner.py` | Automation recipes, DSL sequences, step patterns | `task` |
| **RePromptTuner** | `tuners/wizprompt_tuner.py` | Persona weights, tone adjustments, style preferences | `persona_weights` |

### 7.4 Data Flow

```
Feature request → Middleware.apply() → Orchestrator.tune_request()
→ BaseTuner.apply() injects learned model data into feature_input
→ feature_input passes to actual feature consumer
→ Consumer uses tuned data (e.g., corrected text, enhanced task)
→ User gives feedback → TuneStore.update_rating() → Model improvement
```

### 7.5 Middleware Enable/Disable
The middleware has an `_enabled` flag:
- `middleware.enable()` — Turns on TuneHub interception
- `middleware.disable()` — Bypasses TuneHub (features work without tuning)
- Default: `True` (enabled)

---

## 8. Feature Toggles System

### 8.1 Storage
- **Frontend:** `localStorage` keys:
  - `whiztant.feature.agent`
  - `whiztant.feature.tunehub`
  - `whiztant.feature.tasks`
  - `whiztant.feature.reprompt`
- **Backend:** `memory/settings.json` under `"features"` key
- **Default:** All features enabled (`true`)

### 8.2 Frontend Gating
- `Settings.tsx` — Toggle switches with descriptions
- `Overlay.tsx` — Conditionally renders panels based on toggles
- `TopTabBar.tsx` — Only shows tabs for enabled features
- `useBridge.ts` — Listens for `features/update` to sync across clients

### 8.3 Backend Gating
- `app/main.py` — Wraps feature initialization in conditional blocks
- Agent init only runs if `features.agent` is true
- TuneHub init only runs if `features.tunehub` is true
- Task reminder timer only runs if `features.tasks` is true
- Background agent only starts if `features.agent` is true

---

## 9. Preset System (RePrompt)

### 9.1 Purpose
Presets provide pre-configured optimization targets for RePrompt, allowing users to optimize prompts for specific purposes (code review, product feedback, etc.) without manually describing the target each time.

### 9.2 Default Presets

| ID | Name | Focus | Description |
|---|---|---|---|
| `product_review` | Product Review | semantic | Optimize for product feedback and reviews |
| `idea_review` | Idea Review | structure | Optimize for evaluating and refining ideas |
| `code_review` | Code Review | edge_case | Optimize for reviewing code and technical implementation |
| `code_creation` | Code Creation | structure | Optimize for generating code from descriptions |
| `general` | General Optimization | balanced | Standard multi-agent prompt optimization |

### 9.3 Architecture
- **Data:** `core/presets.py` — `Preset` dataclass + `DEFAULT_PRESETS` + user preset CRUD
- **API:** `server.py` `GET /presets` endpoint
- **UI:** `WizPromptPanel.tsx` — Dropdown selector fetched from `/presets`
- **Integration:** `wizprompt.py` — Injects `system_prompt_addendum` into synthesis agent, prioritizes `agent_focus` agent

### 9.4 User Presets
Users can create custom presets. User presets stored in `data/user_presets.json` with `"category": "user"`.

---

## 10. Task System & Reminders

### 10.1 Schema
```
id, text, status, source, created_at, due_at, completed_at,
parent_id, content, task_type (large/small), carried_over, failed,
progress, reminder_sent, snoozed_until
```

### 10.2 Storage
Canonical: `memory/tasks.json` (both Python and Electron access this file)

### 10.3 Reminder Schedule
| Event | Timing | Action |
|---|---|---|
| Pre-due warning | 30 min before due | `due_soon` WS message → gold banner |
| Due alert | At due time | `due_alert` WS message → red banner |
| Overdue repeat | Every 15 min while overdue | `due_reminder` WS message |
| Daily check | Continuous (every 15 min) | Checks all due/soon/overdue tasks |

### 10.4 Snooze
- **Presets:** 15 min, 30 min, 1 hour, Tomorrow (1440 min)
- **Function:** `tasks.snooze_task(task_id, minutes)` → sets `snoozed_until` UTC timestamp
- **UI:** Snooze button on TaskTile with dropdown; snoozed tasks show clock icon + dimmed state
- **Filtering:** Snoozed tasks are filtered out from `get_due_tasks()` until snooze expires

### 10.5 Task Settings
- Reminder interval: 5/15/30/60 min
- Default due time: time picker (e.g., 5:00 PM)
- Snooze presets: multi-select which options appear
- Pre-due warning: toggle (default ON)
- Carry over unfinished: toggle (default ON)

---

## 11. Hotkeys & Shortcuts

| Trigger | Mode | What It Does |
|---|---|---|
| `Ctrl+Alt+W` | Overlay toggle | Show/hide main overlay |
| `Ctrl+Alt+Space` | Voice input | Start voice recording (hold while speaking) |
| `Ctrl+Shift+Space` | RePrompt | Open WizPrompt panel for prompt optimization |
| `F9` ×1 | Dictation | Whisper STT → paste at cursor |
| `F9` ×2 | Agent toggle | Toggle autonomous agent mode |
| `Alt+M` | Memories | Toggle memories overlay |
| `Alt+G` | Ghost | Toggle memory ghost (translucent overlay) |
| `Alt+T` | Tasks | Quick task view |
| `Esc` | Dismiss | Close overlay / dismiss notifications |

---

## 12. Design System

### 12.1 Color Tokens
```
Background:  #07070f
Surface:     #0f0f1a
Primary:     #c0c1ff  (indigo)
Secondary:   #d0bcff  (purple)
Tertiary:    #4cd7f6  (teal)
Success:     #4ade80  (green)
Warning:     #fbbf24  (amber)
Danger:      #ef4444  (red)
Text:        #e2e2e2  (light gray)
Muted:       #6b7280  (medium gray)
```

### 12.2 Wave States (Pill)
| State | Color | Meaning |
|---|---|---|
| Idle | `#7B2241` (burgundy) | Waiting |
| Recording | mic-reactive | Listening to user |
| Thinking | `#C4956A` (cappuccino) | AI processing |
| Speaking | `#1a3a6b` (dark blue) | AI talking |
| Agent | `#2d6e3e` (green) | Autonomous agent active |

### 12.3 Themes (5)
`onyx`, `graphite`, `porcelain`, `midnight`, `ember` — persisted to `memory/theme.json`, synced to all windows.

---

## 13. Pricing

| Plan | Monthly | Annual | Limits |
|---|---|---|---|
| Free | $0 | — | 15 chats/mo |
| Pro | $15 | $165/yr | 300 chats, 50 agent, 30 UI-TARS |
| Power | $25 | $275/yr | 500 chats, 200 agent, 200 UI-TARS |

Trial: 3 days, 30 msgs, 3 agent tasks, no credit card required.

---

## 14. File Quick Reference

| Thing | Path |
|---|---|
| App entry | `main.py` |
| Core package | `core/` |
| LLM routing | `core/llm_interface.py` |
| Memory + semantic search | `core/memory.py` |
| Tasks CRUD + reminders | `core/tasks.py` |
| Agent execution | `core/shared/agent.py` |
| Voice + STT + TTS | `core/voice.py` |
| Global hotkeys | `core/hotkeys.py` |
| WebSocket bridge | `core/ws_bridge.py` |
| HTTP API server | `core/server.py` |
| RePrompt engine | `core/wizprompt.py` |
| Preset system | `core/presets.py` |
| TuneHub middleware | `core/tune_hub/middleware.py` |
| TuneHub orchestrator | `core/tune_hub/orchestrator.py` |
| WizType subsystem | `core/wiztype/` |
| Agent rules | `agent_rules/` |
| Background agent | `core/background_agent.py` |
| Electron main | `ui/whiztant-overlay/src/main/` |
| Preload script | `ui/whiztant-overlay/src/preload/index.ts` |
| Overlay shell | `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx` |
| Tab bar | `ui/whiztant-overlay/src/renderer/overlay/TopTabBar.tsx` |
| Settings panel | `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` |
| Task tile | `ui/whiztant-overlay/src/renderer/overlay/TaskTile.tsx` |
| WebSocket hook | `ui/whiztant-overlay/src/renderer/shared/useBridge.ts` |
| IPC handlers | `ui/whiztant-overlay/src/renderer/shared/ipc.ts` |
| Task storage | `memory/tasks.json` |
| Theme storage | `memory/theme.json` |
| Settings storage | `memory/settings.json` |
| Logo | `wiztantW.svg` |
| Website | `whiztant-website/` |

---

## 15. Recent Changes (2026-05-04)

### Cleanup v2
- Removed 29 dead files (9 core Python, 4 credit_system, 6 tests, 3 frontend legacy, 7 misc)
- Partial cleanups in 13 files removing dead imports, credit system refs, recording tool functions, WizType init blocks

### TuneHub Fixes
- Fixed DictationTuner.apply() — now calls process_transcription() and sets `feature_input["text"]`
- Fixed AgentTuner.apply() — now modifies task and sets `feature_input["task"]`
- RePrompt now consumes `persona_weights` from TuneHub RePromptTuner
- Middleware now has `enable()`/`disable()` flag

### Feature Toggles
- Added per-feature enable/disable toggles in Settings for Agent, TuneHub, Tasks, RePrompt
- Frontend conditional rendering in Overlay.tsx and TopTabBar.tsx
- Backend gating in app/main.py
- Cross-client sync via WebSocket

### Preset System
- Created `core/presets.py` with 5 default presets
- Added preset dropdown to WizPromptPanel.tsx
- Added `/presets` API endpoint
- Preset consumption in wizprompt.py optimization pipeline

### Reminder Fixes
- Added snooze_task(), is_snoozed(), clear_snooze() to tasks.py
- Changed reminder checks from daily 6pm to every 15 minutes
- Added 30-minute pre-due warnings
- Added snooze button with presets to TaskTile.tsx
- Replaced "Coming soon" Tasks settings tab with full settings

---

## 16. What Still Needs Building

- [ ] **F10 task hotkey** — voice-only task creation mode (`record_task_voice()` in `core/voice.py`; `task_recording` pill wave state)
- [ ] **Website CI/CD** — automated deploy instead of manual `deploy.bat`
- [ ] **Build verification** — `tsc --noEmit` smoke test after any TypeScript change
- [ ] **Python import test** — `python -c "import main"` after any Python change
- [ ] **TuneHub** — Phase 2: Model training (currently Phase 1: manual/seed), leaderboard, marketplace (post-cleanup)
- [ ] **RePrompt** — Undo/redo for prompt optimization history

---

## 17. Definition of Done

A task is **complete** when:

1. **Code compiles / imports without errors** — Python: `python -c "import main"` passes; TypeScript: `npm run build` succeeds in `ui/whiztant-overlay/`
2. **The specific behavior requested works** — verified manually or via test
3. **No regressions introduced** — F9 modes, overlay toggle, pill notifications, task system still function
4. **No new files created unless necessary** — prefer editing existing files
5. **Build artifact is up to date** — if `whiztant-overlay` changed, `npm run build` was re-run

For UI changes: NOT done until `npm run build` completes.  
For Python changes: NOT done until `python main.py` starts without errors.
