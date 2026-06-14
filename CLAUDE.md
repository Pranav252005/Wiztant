# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

> This file is kept in sync with `AGENTS.md`. If the two ever disagree, `AGENTS.md` is the source of truth for project facts; update both when something changes.

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

- **Product name:** Wiztant (intended branding). Note: the codebase still contains many "Whiztant" references in strings, file names, and legacy docs — update to "Wiztant" when you touch those lines, but do not do a global rename unless asked.
- **What it is:** Windows AI operating assistant (Linux supported for development), distributed as a portable executable, sold as SaaS.
- **Builder:** Solo project by Pranav (venkatesh is the same person).
- **Root directory:** `C:\whis\` (Windows), `/home/user/whis/` or similar (Linux dev).
- **Distribution:** Single portable executable; no installer, no registry writes.

---

## Application Architecture

Wiztant has **three separate applications** that must not be confused:

### 1. Python Backend
- **Entry point:** `main.py` → `app/main.py` → `run_app()`. Loads `.env`, runs health checks, initializes `data/` and `memory/`, imports core subsystems, registers global hotkeys via the Platform Abstraction Layer (PAL), starts uvicorn on `127.0.0.1:8765`, starts the WebSocket bridge on `localhost:9120`, and spins up background threads (system context scanner, background agent, system tray, task reminders, overlay launcher).
- **Core logic:** `core/` — 50+ top-level modules plus `core/agent_v2/` and `core/tune_hub/`.
- **Agent rules:** `agent_rules/` — markdown navigation/shortcut/app specs consumed by the UI-TARS agent.
- **Platform abstraction:** `platforms/` — isolates all OS-specific code behind abstract base classes. Factory at `platforms/factory.py` does lazy imports so Linux never loads `win32api` and vice versa.
- **No PyQt6 main window** — the Python side is headless backend + tray icon only (`core/tray.py`). PyQt6/tkinter are used only for the tray icon and minimal overlays (`ui/`).

### 2. Electron Overlay (React + TypeScript) ← ACTIVE UI
- **Location:** `ui/whiztant-overlay/`  ← THIS IS THE ONE TO EDIT
- **Stack:** Electron 33 + React 18 + TypeScript 5.7 + Tailwind CSS 3.4 + Framer Motion + electron-vite
- **Build:** `npm run build` → outputs to `out/`
- **Three BrowserWindows:**
  - Pill — bottom-center always-on-top wave indicator
  - Overlay — chat/tasks/agent panel (Ctrl+Space to toggle)
  - Settings — theme + feature toggles + agent integrations
- **On-demand:** TaskPanel windows (one per task id, frameless, positioned right of overlay)
- **IPC:** Electron ↔ Python via WebSocket on `ws://localhost:9120` (`core/ws_bridge.py`). Electron main also reads/writes `memory/tasks.json` directly via Node fs.
- **Performance rule:** Overlay uses `setOpacity(0/1)` for show/hide — NEVER `hide()/show()` (causes DWM repaint lag on Windows).

### 3. Marketing Website
- **Location:** `whiztant-website/`
- **Stack:** React 19 + Vite 6 + Tailwind CSS v3 + PostCSS + Autoprefixer + GSAP + Framer Motion + Spline + React Router 7
- **Payments:** Stripe + Razorpay
- **Deploy:** Manual to Netlify (`netlify.toml` present; no CI/CD pipeline)
- **PostCSS config:** `postcss.config.cjs` (CJS, not `.js`, because `package.json` has `"type": "module"`)

### Legacy / Do Not Use
- `ui/wiztant-clui/` — archived, superseded by `whiztant-overlay`
- `ui/wiztant-app/` — older React app, also superseded
- `overlay/whiztant-overlay/` — legacy Electron overlay, superseded
- `core/wiztype/` — entire subsystem removed

---

## Languages & Runtimes

| Layer | Language | Runtime / Framework |
|---|---|---|
| Python backend | Python 3.11 | asyncio, uvicorn, FastAPI, pynput, websockets |
| Electron overlay | TypeScript | React 18, Electron 33, Vite, Framer Motion |
| Website | TypeScript / JSX | React 19, Vite 6, Tailwind CSS v3 |
| STT | — | Groq Whisper Large v3 Turbo (cloud) + faster-whisper (local fallback) |
| Agent planner | — | Qwen 3-VL-235B via OpenRouter (vision + text) |
| Agent executor | — | UI-TARS 1.5 7B via OpenRouter (vision) |
| Auth | — | Supabase |
| Cost tracking | — | Helicone |
| License validation | — | LemonSqueezy |

---

## Feature Modes (Hotkeys)

| Trigger | Mode | What it does |
|---|---|---|
| **F9 ×1** | Dictation | STT engine transcribes → smart paste at cursor |
| **F9 ×2+** | Agent toggle | Toggles Agent mode on/off (Three-Brain screen-to-action loop) |
| **Ctrl+Space** | Overlay toggle | Show/hide chat+tasks+agent overlay |
| **Ctrl+Shift+Space** | WizPrompt / RePrompt | Reads clipboard → optimizes via TuneHub persona weights + preset → writes back |
| **Esc** | Dismiss overlay | Closes overlay |
| **F10** | Task voice | Configurable task creation hotkey (`data/settings.json` → `task_hotkey`). Partially implemented. |

**Note:** The old "Conversation" mode (F9×2 voice loop with GPT + TTS) was removed when `core/tts.py` was deleted. Platform-specific TTS lives in `platforms/*/tts.py`.

---

## Agent Mode

The agent is a **Three-Brain screen-to-action loop** (Planner → Vision → Executor) plus a multi-app workflow agent ("The Bridge").

### Key modules
- `core/agent_orchestrator.py` — Three-Brain orchestrator (Planner → Vision → Executor); F9×2 entry point.
- `core/agent_executor.py` — Executor Brain (UI-TARS) predicting GUI actions from screenshots.
- `core/agent_actions.py` — action primitives (click, type, scroll, etc.).
- `core/workflow_runtime.py` — workflow execution runtime; only permits UI-navigation actions.
- `core/workflow_planner.py` — converts intent into a structured `WorkflowPlan`.
- `core/agent_v2_engine.py` + `core/agent_v2/` — "The Bridge" multi-app workflow agent + TuneHub learning.
- **Agent presets:** `core/agent_presets.py` — 11 built-in presets; UI in `AgentV2Panel.tsx`; bridge message `agent_v2:run_preset`.

### Agent Integrations / App Authorization ← NEW
Lets the agent sign into apps (Slack, Gmail, anything) automatically. Supports **both** OAuth and a credential vault.

- **Vault module:** `core/integrations.py`
  - **Local-only, encrypted:** secrets are **never** sent to any cloud/app DB. Stored Fernet-encrypted at `~/.wiztant/integrations.enc`. Encryption key lives in the OS keyring when available, else a `0600` `~/.wiztant/vault.key` fallback.
  - **Two auth types:** `credential` (login fields the screen agent types) and `oauth` (PKCE loopback flow; providers `google`, `slack`, `github`).
  - **Secrets never reach the LLM:** the planner only sees `list_public()` / `agent_context_block()` — app names + which field keys exist, no values. To type a secret the agent emits a placeholder `{{cred:App:field}}` (e.g. `{{cred:Slack:password}}`); `core/agent_actions._resolve_credentials()` substitutes the real value at type time (TypeAction path only).
  - **OTP / 2FA:** the agent pauses and asks the user; codes are never stored.
- **On-demand OAuth fallback:** when the agent opens an app the user never configured in Settings, `core/integrations.ensure_authorized(app)` runs OAuth directly. Resolution order: (1) vault hit → ok; (2) known OAuth provider + built-in client ID → run OAuth now and store; (3) otherwise → ask the user to set it up. Hooked into `core/workflow_runtime.py` on the `open_app` action. App→provider mapping via `detect_provider()` (e.g. "Gmail" → google).
  - **Built-in OAuth client IDs** come from env vars: `WIZTANT_<PROVIDER>_CLIENT_ID` / `WIZTANT_<PROVIDER>_CLIENT_SECRET` (e.g. `WIZTANT_GOOGLE_CLIENT_ID`). Until these are set, direct OAuth can't fire and the agent falls back to asking the user.
- **Bridge messages (`core/ws_bridge.py`):** `integrations/list`, `integrations/save`, `integrations/delete`, `integrations/oauth/start` → broadcasts `integrations/update`, `integrations/oauth/result`, `integrations/error`.
- **UI:** `IntegrationsTab` + `IntegrationForm` in `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` (Settings → "Integrations" tab). Add credential-vault apps with custom key/value fields, or connect via OAuth.

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

- **Overlay themes** (5): `onyx`, `graphite`, `porcelain`, `midnight`, `ember` — stored in `memory/theme.json`
- **Python tokens:** `ui/constants.py` and `ui/theme.py`
- **Website tokens:** Tailwind config + CSS classes: `.glass`, `.gradient-text`, `.btn-primary`, `.btn-ghost`, `.card`, `.eyebrow`, `.kbd`, `.prose-dark`, `.page-wrap`, `.section`, `.section-alt`
- **Logo:** `wiztantW.svg` (do NOT regenerate programmatically — always load from file)

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

---

## Preset Systems

### RePrompt presets
- **File:** `core/presets.py` — `product_review`, `idea_review`, `code_review`, `code_creation`, `general`
- **UI:** Dropdown in `WizPromptPanel.tsx`; **API:** `GET /presets`; consumed by `core/wizprompt.py`.

### Agent presets (The Bridge)
- **File:** `core/agent_presets.py` — 11 built-in presets (Development / Productivity / System).
- **UI:** Dropdown in `AgentV2Panel.tsx`; **API:** `GET /agent_presets`; **Bridge:** `agent_v2:run_preset`.
- No emojis in the agent UI; button label "Run Agent"; tab label "Agent".

---

## Task System & Reminders

### Storage — CRITICAL
Tasks are stored at **`memory/tasks.json`** (NOT `data/tasks.json`). Both the Python backend (`core/tasks.py`) and the Electron main process (`ipc.ts`) read/write this same file. Always use `memory/tasks.json`.

### Schema
```
id, text, status, source, created_at, due_at, completed_at,
parent_id, content, task_type (large/small), carried_over, failed,
progress, reminder_sent, snoozed_until
```

### Reminders & Snooze
- **Check cycle:** every 15 minutes; 30-min pre-due warning; due alert at `due_at`; overdue repeats every 15 min.
- **Snooze presets:** configurable in `data/settings.json` (default 15min, 60min, 1440min). Functions in `core/tasks.py`: `snooze_task`, `is_snoozed`, `clear_snooze`.
- **WebSocket broadcasts:** `due_alert`, `due_reminder`, `tasks_failed`, `task_saved`, `pill/notice`.

---

## Code Style Guidelines

### Python
- `from __future__ import annotations` at the top of every module.
- Type hints where practical; `snake_case` funcs/vars, `PascalCase` classes, `UPPER_CASE` constants.
- Module-level docstrings; section headers (`# === SECTION ===`).
- **Lazy imports for platform-specific modules** (see `platforms/factory.py`) so cross-platform imports never crash at startup.
- **Defensive coding:** wrap optional subsystems in `try/except` so missing API keys / unavailable platforms degrade gracefully.
- Prefer `pathlib.Path` over `os.path` for new code.

### TypeScript / React
- Explicit types; avoid `any`. Functional components with hooks.
- The overlay uses `setOpacity(0/1)` for show/hide — never `hide()/show()` on BrowserWindow.

---

## Testing

**Framework:** `pytest` (with `pytest-asyncio`, `pytest-cov`).

```bash
pytest tests/                                   # all
pytest tests/test_tasks.py                      # one file
pytest tests/stt_tests/test_integration.py
pytest core/tune_hub/tests/test_orchestrator.py
```

- Mock external APIs (`unittest.mock.patch`, monkeypatch); use `tmp_path` for hermetic file I/O.
- `tests/conftest.py` injects the project root into `sys.path`.
- No E2E tests for the overlay IPC protocol — add pytest-based tests when modifying bridge code.

---

## Security Considerations

- **`.env` contains secrets** — API keys for OpenAI, OpenRouter, Groq, Supabase, Helicone, LemonSqueezy, plus `WIZTANT_*_CLIENT_ID/SECRET` OAuth client creds. Never commit `.env`.
- **Integration secrets stay local** — `core/integrations.py` stores everything Fernet-encrypted under `~/.wiztant/`, never in any cloud/app DB, and never exposes plaintext secrets to the LLM (placeholder substitution only).
- **Agent guardrails** — `core/guardrails.py` blocks destructive actions via regex, validates coordinates, detects no-progress loops. `core/agent_v2/guardrails.py` adds cost/file/step ceilings, command validation, path sandboxing, secret scanning. Respect and update these when adding agent capabilities.
- **Isolated input** — background agent tasks use `AgentInputContext` (`core/agent_isolation.py`) to send input without stealing focus.
- **No sandbox escape** — the agent runs with the user's permissions. Do not add elevation prompts or UAC bypasses.

---

## File Location Quick Reference

| Thing | Path |
|---|---|
| App entry | `main.py` |
| Core logic | `core/` |
| Agent navigation spec | `WHISrules.md` |
| Agent rules folder | `agent_rules/` |
| Agent integrations vault | `core/integrations.py` (data: `~/.wiztant/`) |
| WebSocket bridge | `core/ws_bridge.py` |
| FastAPI server | `core/server.py` |
| Tasks CRUD | `core/tasks.py` |
| Task storage | `memory/tasks.json` |
| Theme storage | `memory/theme.json` |
| Settings + feature flags | `data/settings.json` |
| Electron overlay root | `ui/whiztant-overlay/` |
| Electron main process | `ui/whiztant-overlay/src/main/index.ts` |
| Electron preload | `ui/whiztant-overlay/src/preload/index.ts` |
| Overlay renderer | `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx` |
| Pill renderer | `ui/whiztant-overlay/src/renderer/pill/Pill.tsx` |
| Settings renderer | `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` |
| Shared types/IPC | `ui/whiztant-overlay/src/renderer/shared/` |
| Notification components | `ui/whiztant-overlay/src/renderer/shared/notifications/` |
| Logo SVG | `wiztantW.svg` |
| Website | `whiztant-website/` |
| Implementation plans | `Plans_Implementation/` |
| Python deps | `requirements.txt` |
| Windows build script | `build.bat` |
| Tests | `tests/` |

---

## Definition of Done

A task is **complete** when:

1. **Code compiles / imports without errors** — Python: `python -c "import main"` passes; TypeScript: `npm run build` succeeds in `ui/whiztant-overlay/`.
2. **The specific behavior requested works** — verified manually or via test, not just "it looks right".
3. **No regressions introduced** — the F9 modes (dictation + agent toggle), Ctrl+Space overlay, pill notifications, and task system still function.
4. **No new files created unless necessary** — prefer editing existing files.
5. **Build artifact is up to date** — if `whiztant-overlay` was changed, `npm run build` was re-run.

For UI changes in `whiztant-overlay`: task is NOT done until `npm run build` completes successfully.
For Python changes: task is NOT done until `python main.py` starts without errors.

---

## Legacy Features — DO NOT USE in New Code

Removed; must not be referenced in new code or docs:

- `core/wiztype/` (entire subsystem)
- `core/action_optimizer.py`, `core/agent_s3_wrapper.py`, `core/app_detector.py`, `core/intent_compiler.py`, `core/learning_agent.py`, `core/system_task_executor.py`, `core/workflow_recorder.py`
- `tests/test_wiztype_*.py`, `ui/chat_overlay.py`
- `main_old.py`, root `package-lock.json`, `docs/WIZTYPE.md`, `data/wiztype_config.json`
- Conversation mode (F9×2 voice loop with TTS) — removed with `core/tts.py`
