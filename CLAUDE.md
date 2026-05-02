"" 
# CLAUDE.md

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
- **What it is:** Windows AI operating assistant, distributed as a portable `.exe` (no install), sold as SaaS
- **Builder:** Solo project by Pranav (venkatesh is the same person)
- **Root directory:** `C:\whis\`

---

## Application Architecture

Wiztant has **three separate applications** that must not be confused:

### 1. Python Backend
- **Entry point:** `C:\whis\main.py` — starts uvicorn on port 8765, WebSocket bridge on port 9120, system tray, F9 hotkeys, WizType
- **Core logic:** `C:\whis\core\` — agent, voice, hotkeys, tasks, ws_bridge, tts, vlm, memory, background_agent, vocab, guardrails, wiztype/
- **Agent rules:** `C:\whis\agent_rules\` — markdown specs for navigation, shortcuts, apps (used by UI-TARS agent)
- **No PyQt6 main window** — the Python side is headless backend + tray icon only

### 2. Electron Overlay (React + TypeScript) ← ACTIVE UI
- **Location:** `C:\whis\ui\whiztant-overlay\`  ← THIS IS THE ONE TO EDIT
- **Stack:** Electron + React 18 + TypeScript + Tailwind + Framer Motion + electron-vite
- **Three BrowserWindows:**
  - Pill — bottom-center always-on-top wave indicator
  - Overlay — 340×420 chat/tasks/agent panel (Ctrl+Space to toggle)
  - Settings — theme + WizType config
- **On-demand:** TaskPanel windows (one per task id, 340×420 frameless, positioned right of overlay)
- **IPC:** Electron ↔ Python via WebSocket on `ws://localhost:9120` (ws_bridge.py)
- **Task IPC:** Electron main also reads/writes `C:\whis\memory\tasks.json` directly via Node fs

### 3. Marketing Website
- **Location:** `C:\whis\whiztant-website\`
- **Stack:** React + Vite + Tailwind CSS v3
- **Deploy:** `deploy.bat` → Netlify
- **PostCSS config:** `postcss.config.cjs` (CJS, not `.js`, because `package.json` has `"type": "module"`)

### Legacy / Do Not Use
- `C:\whis\ui\wiztant-clui\` — archived, superseded by `whiztant-overlay`
- `C:\whis\ui\wiztant-app\` — older React app, also superseded

---

## Languages & Runtimes

| Layer | Language | Runtime / Framework |
|---|---|---|
| Python backend | Python 3.11 | asyncio, uvicorn, pynput, websockets |
| Electron overlay | TypeScript | React 18, Electron, Vite, Framer Motion |
| Website | TypeScript / JSX | React, Vite, Tailwind CSS v3 |
| STT | — | Groq Whisper Large v3 Turbo (cloud) + faster-whisper (local fallback) |
| TTS | — | Kokoro (local), 6 voices, `af_nova` default |
| Agent planner | — | Qwen 3.6 Plus free via OpenRouter (text-only) |
| Agent executor | — | UI-TARS 1.5 7B via OpenRouter (vision) |
| Auth | — | Supabase |
| Cost tracking | — | Helicone |

---

## Feature Modes

| Trigger | Mode | What it does |
|---|---|---|
| F9 ×1 | Dictation | Whisper transcription → paste at cursor |
| F9 ×2 | Conversation | Voice loop with GPT-5.4 + Kokoro TTS |
| F9 ×3 | Agent | UI-TARS screen-to-action loop |
| Ctrl+Space | Overlay toggle | Show/hide 340×420 chat+tasks+agent overlay |
| F10 (planned) | Task voice | Voice-only task creation with "Add Task" pill state |

---

## Design System (Electron overlay + website)

```
Background:  #07070f
Primary:     #c0c1ff  (indigo)
Secondary:   #d0bcff  (purple)
Tertiary:    #4cd7f6  (teal)
```

- **Wave states:** idle `#7B2241` (burgundy), recording (mic-reactive), thinking `#C4956A` (cappuccino), speaking `#1a3a6b` (dark blue), agent `#2d6e3e` (green)
- **Overlay themes** (5): `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — stored in `memory/theme.json`
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

## What's Been Built

### Python Backend
- [x] F9 hotkey with 3-mode detection (debounced counter)
- [x] Dictation: Groq Whisper STT → clipboard paste
- [x] Conversation: voice loop with GPT-5.4 + Kokoro TTS, 6 voices
- [x] Agent: UI-TARS 1.5 7B screen-to-action loop with agent_rules/ navigation spec
- [x] System tray icon (winotify toasts on startup)
- [x] Supabase auth (email/password)
- [x] Usage guard via Helicone
- [x] WebSocket bridge on port 9120 (ws_bridge.py) — Python ↔ Electron IPC
- [x] FastAPI backend on port 8765 (core/server.py)
- [x] Task system (core/tasks.py): full CRUD, voice parsing, due-time extraction, LLM task refiner, daily suggestion
- [x] Task schema: id, text, status, source, created_at, due_at, completed_at, parent_id, content, task_type (large/small), carried_over, failed
- [x] Session continuity: "save this for tomorrow" → save_session_as_task()
- [x] Due-alert timers: _due_check() at 18:00 daily, _due_reminder() every 4h for carried-over tasks
- [x] Startup nudge: 8s after boot, pill flashes yesterday's pending task summary
- [x] WizType subsystem (core/wiztype/): keyboard hook, debounced inference, Ollama/custom model, Tab-to-accept suggestion overlay
- [x] Background agent manager (core/background_agent.py)
- [x] Memory system (core/memory.py)
- [x] System context scanner (core/system_context.py)
- [x] Vocab correction system (core/vocab.py)
- [x] Agent confirmation overlay (ui/agent_confirmation_overlay.py)

### Electron Overlay (whiztant-overlay)
- [x] Pill window — always-on-top, bottom-center, wave animation with state colors
- [x] Overlay window — 3-tab layout (Chat / Tasks / Agent), Ctrl+Space toggle
- [x] Settings window — theme picker, WizType config
- [x] Theme system — 5 themes, persisted to memory/theme.json, synced to all windows
- [x] WebSocket bridge client (useBridge.ts) — connects to Python on port 9120
- [x] Task system — full CRUD via IPC + fs direct (getTasks, saveTask, updateTask, deleteTask, markDone, openTaskPanel, rescheduleTask, undoTaskSave)
- [x] TasksPanel — task list with add-form, due-time picker (day + hh:mm + am/pm), Today section, Undone section, recent history
- [x] TaskTile — LARGE/SMALL badge, due label, overdue highlighting, failed state, voice badge
- [x] TaskPanel side window — 340×420 frameless, opens to the right of overlay, title input, content textarea, due pickers, Save button
- [x] useTasks hook — wraps IPC, local state sync, refresh
- [x] Notification system — usePillNotifications queue + NotificationRenderer dispatching 4 types:
  - TaskSavedNotification (Edit / Save / Decline, 5s auto-save)
  - DueAlertNotification (red, per-task Reschedule Tomorrow)
  - DueReminderNotification (gold, 4h carry-over reminder)
  - DuplicateTaskNotification (gold duplicate warning)
- [x] Task banners in Overlay.tsx — voice-added flash, halfway reminder, due-now danger banner
- [x] Agent panel (AgentPanel.tsx) — live step progress, blocked state with undo, done/result state
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

## What Still Needs Building

- [ ] **F10 task hotkey** — voice-only task creation mode; `record_task_voice()` in core/voice.py; `_parse_task_from_speech()` LLM extractor; `task_recording` pill wave state (purple/indigo "Add Task" label). Spec: `Plans_Implementation/whiztant-f10-task-hotkey-prompt.md`
- [ ] Final smoke test of task panel IPC + `tsc --noEmit` verification
- [ ] Website deploy CI/CD (currently manual `deploy.bat`)

---

## Task Storage — CRITICAL

Tasks are stored at **`C:\whis\memory\tasks.json`** (NOT `data/tasks.json`).

Both the Python backend (`core/tasks.py`) and the Electron main process (`ipc.ts`) read and write this same file. Always use `memory/tasks.json`.

---

## Definition of Done

A task is **complete** when:

1. **Code compiles / imports without errors** — Python: `python -c "import main"` passes; TypeScript: `npm run build` succeeds in `ui/whiztant-overlay/`
2. **The specific behavior requested works** — verified manually or via test, not just "it looks right"
3. **No regressions introduced** — the three F9 modes, Ctrl+Space overlay, pill notifications, and task system still function
4. **No new files created unless necessary** — prefer editing existing files
5. **Build artifact is up to date** — if `whiztant-overlay` was changed, `npm run build` was re-run

For UI changes in `whiztant-overlay`: task is NOT done until `npm run build` completes successfully in `C:\whis\ui\whiztant-overlay\`.

For Python changes: task is NOT done until `python main.py` starts without errors in the terminal.

---

## File Location Quick Reference

| Thing | Path |
|---|---|
| App entry | `C:\whis\main.py` |
| Core logic | `C:\whis\core\` |
| WizType subsystem | `C:\whis\core\wiztype\` |
| Agent navigation spec | `C:\whis\WHISrules.md` |
| Agent rules folder | `C:\whis\agent_rules\` |
| WebSocket bridge | `C:\whis\core\ws_bridge.py` |
| Tasks CRUD | `C:\whis\core\tasks.py` |
| Task storage | `C:\whis\memory\tasks.json` |
| Theme storage | `C:\whis\memory\theme.json` |
| Electron overlay root | `C:\whis\ui\whiztant-overlay\` |
| Electron main process | `C:\whis\ui\whiztant-overlay\src\main\` |
| Electron preload | `C:\whis\ui\whiztant-overlay\src\preload\index.ts` |
| Overlay renderer | `C:\whis\ui\whiztant-overlay\src\renderer\overlay\` |
| Pill renderer | `C:\whis\ui\whiztant-overlay\src\renderer\pill\` |
| Settings renderer | `C:\whis\ui\whiztant-overlay\src\renderer\settings\` |
| Shared types/IPC | `C:\whis\ui\whiztant-overlay\src\renderer\shared\` |
| Notification components | `C:\whis\ui\whiztant-overlay\src\renderer\shared\notifications\` |
| Logo SVG | `C:\whis\wiztantW.svg` |
| Website | `C:\whis\whiztant-website\` |
| Implementation plans | `C:\whis\Plans_Implementation\` |
