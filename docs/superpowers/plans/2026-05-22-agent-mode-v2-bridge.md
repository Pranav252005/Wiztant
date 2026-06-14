# Agent Mode v2 — The Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Desktop Context Bridge — an OS-level orchestrator that bridges gaps between apps, automates multi-app workflows, and identifies files for the IDE without editing code itself.

**Architecture:** Agent Mode v2 reuses the existing Three-Brain Agent (Vision → Planner → Executor → Actions) but adds workflow templates, file identification without file reading, clipboard error detection, app profiles, and a new engine orchestrator that can run pre-built multi-app recipes.

**Tech Stack:** Python 3.11, existing OpenRouter integrations, existing pyautogui/pynput action runtime, existing WebSocket bridge, React/TypeScript overlay.

---

## File Map

### New Files (Backend)
- `core/agent_v2_engine.py` — Main orchestrator, workflow runner
- `core/agent_v2_templates.py` — Pre-built workflow template definitions
- `core/agent_v2_filefinder.py` — File identification engine (no file reading)
- `core/agent_v2_clipboard.py` — Clipboard monitoring, error detection
- `core/agent_v2_profiles.py` — App profiles (Terminal, Browser, Cursor, Figma, etc.)
- `core/agent_v2_revert.py` — Revert sequences for destructive actions

### Modified Files (Backend)
- `core/ws_bridge.py` — Add v2-specific WebSocket events
- `core/agent.py` — Route to v2 engine for template-based workflows

### New Files (Overlay)
- `ui/whiztant-overlay/src/renderer/overlay/AgentV2Panel.tsx` — V2 agent status panel

### Modified Files (Overlay)
- `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx` — Add AgentV2Panel tab
- `ui/whiztant-overlay/src/renderer/overlay/TopTabBar.tsx` — Add "Agent" tab for v2

---

## Task 1: Workflow Templates & App Profiles

**Files:**
- Create: `core/agent_v2_profiles.py`
- Create: `core/agent_v2_templates.py`

**Steps:**
1. Define `AppProfile` dataclass with app name, window title patterns, executable names, focus/switch methods
2. Define `WorkflowTemplate` dataclass with id, name, apps_required, estimated_steps, steps list
3. Define `WorkflowStep` dataclass with id, app, action, command/url/ui_target, verification, decision gate
4. Implement 5 core templates: github_ssh_clone, figma_to_cursor_component, terminal_error_to_cursor_fix, jira_commit_push, slack_to_notion_prd
5. Implement template registry with `get_template(id)` and `list_templates()`

## Task 2: File Finder (No File Reading)

**Files:**
- Create: `core/agent_v2_filefinder.py`

**Steps:**
1. Define `FileFinder` class with allowed sources (git status, find command, error stack traces, IDE file tree screenshot, project heuristics)
2. Implement `from_git_status(cwd)` → recently modified files
3. Implement `from_keyword_search(cwd, keywords)` → find . -iname "*keyword*"
4. Implement `from_error_stacktrace(error_text)` → parse File "path", line N
5. Implement `from_project_heuristics(cwd, framework)` → Next.js, React, etc. patterns
6. Implement `identify_file(intent, context)` → orchestrates all sources, returns top candidate with confidence
7. Implement `get_file_tree_screenshot()` → captures IDE sidebar for vision analysis

## Task 3: Clipboard Monitor & Error Detection

**Files:**
- Create: `core/agent_v2_clipboard.py`

**Steps:**
1. Define `ClipboardMonitor` class with polling interval
2. Implement `detect_error_pattern(text)` → regex for stack traces, module not found, permission denied, etc.
3. Implement `start_monitoring()`, `stop_monitoring()`
4. Implement `get_last_error()` → returns last detected error with context
5. Implement `on_error_detected(callback)` → async callback when error found

## Task 4: Agent V2 Engine

**Files:**
- Create: `core/agent_v2_engine.py`

**Steps:**
1. Define `AgentV2Engine` class that orchestrates the workflow execution loop
2. Import existing brains: `VisionBrain`, `PlannerBrain`, `ExecutorBrain`, `ActionExecutor`
3. Import new modules: `WorkflowTemplate`, `FileFinder`, `ClipboardMonitor`, `AppProfile`
4. Implement `run_workflow(template, params)` → main execution loop with 100-step budget
5. Implement heartbeat loop: screenshot → vision.analyze() → check subtask complete → executor.predict() → action.execute()
6. Implement pause/resume with state serialization
7. Implement decision gates after destructive actions
8. Integrate with `AgentStateMachine` for budget tracking

## Task 5: WebSocket Events Integration

**Files:**
- Modify: `core/ws_bridge.py`

**Steps:**
1. Add v2 event handlers: `agent_v2:initiate`, `agent_v2:select_template`, `agent_v2:pause`, `agent_v2:resume`, `agent_v2:decision`, `agent_v2:abort`
2. Add v2 broadcast helpers: `send_agent_v2_status_update()`, `send_agent_v2_step_complete()`, `send_agent_v2_paused()`, `send_agent_v2_completed()`, `send_agent_v2_error()`
3. Wire engine events to WebSocket broadcasts

## Task 6: Overlay UI — Agent V2 Panel

**Files:**
- Create: `ui/whiztant-overlay/src/renderer/overlay/AgentV2Panel.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/overlay/TopTabBar.tsx`

**Steps:**
1. Create AgentV2Panel with workflow status display (current step, progress bar, step budget, apps chain)
2. Add template selection UI
3. Add pause/resume/abort controls
4. Add decision gate UI (Accept/Deny/Revert)
5. Wire WebSocket v2 events to panel state
6. Add "Agent" tab to TopTabBar (feature-gated by `features.agent`)

## Task 7: Build & Verification

**Steps:**
1. Python import test: `python -c "import core.agent_v2_engine; import core.agent_v2_templates; import core.agent_v2_filefinder; import core.agent_v2_clipboard; import core.agent_v2_profiles; import core.agent_v2_revert"`
2. TypeScript build: `cd ui/whiztant-overlay && npm run build`
3. Verify no regressions in existing agent mode
