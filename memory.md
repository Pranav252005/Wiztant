# Wiztant Memory

Last updated: 2026-04-18
Scope reviewed:
- Python backend: `C:\whis\main.py` + `C:\whis\core\`
- Electron overlay: `C:\whis\ui\whiztant-overlay\`
- Website: `C:\whis\whiztant-website\`
- Implementation plans: `C:\whis\Plans_Implementation\`

---

## 1) Architecture — Three Separate Apps

### 1.1 Python Backend (headless)
- Entry: `C:\whis\main.py` — starts uvicorn on port 8765, WebSocket bridge on port 9120, system tray, F9 hotkeys, WizType
- **No PyQt6 main window.** Python is entirely headless backend + tray icon.
- Core modules: `core/agent.py`, `core/voice.py`, `core/hotkeys.py`, `core/tasks.py`, `core/ws_bridge.py`, `core/tts.py`, `core/vlm.py`, `core/memory.py`, `core/background_agent.py`, `core/vocab.py`, `core/guardrails.py`
- WizType subsystem: `core/wiztype/`

### 1.2 Electron Overlay — ACTIVE UI
- **Location:** `C:\whis\ui\whiztant-overlay\` ← this is the one to edit
- Stack: Electron + React 18 + TypeScript + Tailwind + Framer Motion + electron-vite
- Three BrowserWindows: Pill (bottom-center always-on-top), Overlay (340×420 chat+tasks+agent, Ctrl+Space), Settings (theme + WizType config)
- On-demand: TaskPanel windows (one per task id, 340×420 frameless, positioned right of overlay)
- IPC: Electron ↔ Python via WebSocket on `ws://localhost:9120` (ws_bridge.py)
- Task IPC: Electron main also reads/writes `C:\whis\memory\tasks.json` directly via Node fs

### 1.3 Marketing Website
- **Location:** `C:\whis\whiztant-website\`
- Stack: React + Vite + Tailwind CSS v3
- Deploy: `deploy.bat` → Netlify

### Legacy — Do Not Use
- `C:\whis\ui\wiztant-clui\` — archived (moved to `_waste_archive`), superseded by `whiztant-overlay`
- `C:\whis\ui\wiztant-app\` — older React app, also superseded

---

## 2) Hotkey Behavior (actual runtime — main.py + core/hotkeys.py)

| Trigger | Mode | What it does |
|---|---|---|
| F9 ×1 | Dictation | Whisper STT → paste at cursor |
| F9 ×2 | Conversation | Voice loop with GPT-5.4 + Kokoro TTS |
| F9 ×3 | Agent | UI-TARS 1.5 7B screen-to-action loop |
| Ctrl+Space | Overlay toggle | Show/hide 340×420 overlay |
| F10 | Task hotkey | PLANNED — voice task creation ("Add Task" pill state) |

Note: F9 ×2 and F9 ×3 modes are implemented in main.py. The old memory.md noted a mismatch but this is now resolved — all 3 modes are live in the current codebase.

---

## 3) Task System (fully implemented)

### Storage
- **`C:\whis\memory\tasks.json`** — canonical storage for both Python and Electron
- (NOT `%APPDATA%\Wiztant\tasks.json` — that was old; one-time migration already ran)

### Schema
```
id, text, status, source, created_at, due_at, completed_at,
parent_id, content, task_type (large/small), carried_over, failed
```

### Python backend (`core/tasks.py`)
- Full CRUD: `add_task`, `mark_done`, `delete_task`, `toggle_status`, `get_tasks`, `get_task_history`
- Voice parsing: `parse_task_command()` with regex + Levenshtein fuzzy matching
- Task refiner: calls OpenRouter LLM to clean up voice-spoken task text
- Session continuity: `save_session_as_task()` saves last 10 messages + title
- Due-alert helpers: `get_due_today_undone`, `get_carried_over_undone`, `reschedule_to_tomorrow`, `mark_failed`
- Daily suggestion: `get_daily_task_suggestion()` from last 10 days of history

### Electron overlay (ipc.ts + renderer)
- All IPC handlers wired: `task:getAll`, `task:save`, `task:update`, `task:delete`, `task:markDone`, `task:openPanel`, `task:reschedule`, `task:undoSave`
- `useTasks.ts` hook wraps IPC with local state + refresh
- `TasksPanel.tsx` — full UI with add-form, due-time pickers, Today/Undone/history sections
- `TaskTile.tsx` — LARGE/SMALL badge, due label, overdue/failed styling, opens panel on click
- `TaskPanel.tsx` — side window with title input, content textarea, due pickers, Save button
- TaskPanel window: hash-routed (`#/task-panel?task=...`), positioned right of overlay

---

## 4) Notification System (fully implemented)

### How it works
- `usePillNotifications.ts` in `renderer/shared/` manages notification queue
- `NotificationRenderer.tsx` dispatches to 4 typed components:
  - `TaskSavedNotification` — task title + Edit/Save/Decline (5s auto-save)
  - `DueAlertNotification` — persistent red banner, per-task Reschedule Tomorrow
  - `DueReminderNotification` — gold reminder banner, dismiss-only
  - `DuplicateTaskNotification` — gold duplicate warning

### Python timer logic (main.py)
- `_due_check()` fires at 18:00 daily via `seconds_until(18,0)` threading.Timer
- `_due_reminder()` fires every 4h when carried-over tasks exist
- Startup nudge fires 8s after boot via `get_yesterday_pending_summary()`

### WebSocket broadcasts (ws_bridge.py)
- `due_alert` — 6pm first miss
- `due_reminder` — every 4h for carried-over tasks
- `tasks_failed` — 6pm second miss → tasks get `failed=true`
- `task_saved` — task saved via voice or "save this for tomorrow"
- `pill/notice` — generic pill flash

---

## 5) WizType Subsystem (fully implemented)

- **Location:** `C:\whis\core\wiztype\`
- Hooks into all system keyboard input via pynput
- Debounced inference on each keystroke
- Correction mode: suggests corrected spelling if mid-word (Tab accept, Esc dismiss)
- Next-word mode: suggests next word after space/enter
- Uses Ollama local inference by default; custom model via `MODEL_CUSTOM` env var
- `SuggestionOverlay` renders suggestion inline near cursor
- Config: `data/wiztype_config.json` — `enabled`, `current_model`, `debounce_ms`
- Integration: `ensure_wiztype_started_from_config()` called at startup in main.py

---

## 6) Design System

```
Background:  #07070f
Primary:     #c0c1ff  (indigo)
Secondary:   #d0bcff  (purple)
Tertiary:    #4cd7f6  (teal)
```

Wave states: idle `#7B2241` (burgundy) · recording (mic-reactive) · thinking `#C4956A` (cappuccino) · speaking `#1a3a6b` (dark blue) · agent `#2d6e3e` (green)

Overlay themes (5): `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — persisted to `memory/theme.json`

---

## 7) Pricing

| Plan | Monthly | Annual | Limits |
|---|---|---|---|
| Free | $0 | — | 15 chats/mo |
| Pro | $15 | $165/yr | 300 chats, 50 agent, 30 UI-TARS |
| Power | $25 | $275/yr | 500 chats, 200 agent, 200 UI-TARS |

Trial: 3 days, 30 msgs, 3 agent tasks, no credit card required

---

## 8) What Still Needs Building

- [ ] **F10 task hotkey** — voice-only task creation; spec: `Plans_Implementation/whiztant-f10-task-hotkey-prompt.md`
  - `record_task_voice()` in `core/voice.py`
  - `_parse_task_from_speech()` LLM extractor
  - `task_recording` pill wave state in `Pill.tsx` (purple/indigo "Add Task" label)
  - F10 listener in `core/hotkeys.py`
- [ ] Final smoke test: full task create→panel→edit→save flow + `tsc --noEmit`
- [ ] Website deploy CI/CD (currently manual `deploy.bat`)

---

## 9) Key File Map

| Thing | Path |
|---|---|
| App entry | `C:\whis\main.py` |
| Core logic | `C:\whis\core\` |
| WizType subsystem | `C:\whis\core\wiztype\` |
| WebSocket bridge | `C:\whis\core\ws_bridge.py` |
| Tasks CRUD | `C:\whis\core\tasks.py` |
| Task storage | `C:\whis\memory\tasks.json` |
| Theme storage | `C:\whis\memory\theme.json` |
| Electron overlay root | `C:\whis\ui\whiztant-overlay\` |
| Electron main + IPC | `C:\whis\ui\whiztant-overlay\src\main\` |
| Preload | `C:\whis\ui\whiztant-overlay\src\preload\index.ts` |
| Overlay renderer | `C:\whis\ui\whiztant-overlay\src\renderer\overlay\` |
| Pill renderer | `C:\whis\ui\whiztant-overlay\src\renderer\pill\` |
| Settings renderer | `C:\whis\ui\whiztant-overlay\src\renderer\settings\` |
| Shared types + notifications | `C:\whis\ui\whiztant-overlay\src\renderer\shared\` |
| Logo SVG | `C:\whis\wiztantW.svg` |
| Website | `C:\whis\whiztant-website\` |
| Implementation plans | `C:\whis\Plans_Implementation\` |
