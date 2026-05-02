# Task Panel + Session Continuity — Remaining Work

> Completed items have been removed. This file tracks only what is still to be implemented.

**Repo roots**
- Electron UI: `C:\whis\ui\whiztant-overlay\`
- Python backend: `C:\whis` (core at `C:\whis\core\`)

---

## Already Done (for context)

- Python WS bridge is live (`core/ws_bridge.py`, started from `main.py`).
- Tasks CRUD + snapshot push already wired end-to-end for the existing Tasks tab (`core/tasks.py` + `tasks/update`, `tasks/add`, `tasks/toggle_status`, `tasks/delete`).
- Startup nudge: 8s after boot, pill shows yesterday's pending summary via `send_pill_notice(...)` using `get_yesterday_pending_summary()`.
- Time input fix in `TasksPanel.tsx` — native time picker replaced with plain text `hh:mm` input.

---

## Remaining Tasks

### 1. Electron preload — expose task IPC on `window.api`

- [ ] In `ui/whiztant-overlay/src/preload/index.ts`, add:
  - `getTasks()`, `saveTask()`, `updateTask(id, fields)`, `deleteTask(id)`, `markDone(id)`, `openTaskPanel(task)`.
- [ ] Add `Task` interface + extend `window.api` typing (either `src/preload/index.d.ts` or an ambient `.d.ts`).
- [ ] `npx tsc --noEmit` passes.

### 2. Electron main — task IPC handlers + Task Panel BrowserWindow

- [ ] In `ui/whiztant-overlay/src/preload/index.ts`, add:
  - `getTasks()`, `saveTask()`, `updateTask(id, fields)`, `deleteTask(id)`, `markDone(id)`, `openTaskPanel(task)`.
- [ ] Add `Task` interface + extend `window.api` typing (either `src/preload/index.d.ts` or an ambient `.d.ts`).
- [ ] `npx tsc --noEmit` passes.

### 3. Renderer — `useTasks` hook

- [ ] Create `ui/whiztant-overlay/src/main/windows/taskPanel.ts` exporting `openTaskPanel(task, overlayBounds)`:
  - 340×420, frameless, transparent, alwaysOnTop, skipTaskbar, non-resizable.
  - Positioned to the right of the overlay (`x = overlay.x + overlay.width + 12`, same `y`).
  - One window per task id; pass task via `#/task-panel?task=<encoded JSON>`.
- [ ] In `src/main/ipc.ts` (or `index.ts`), add handlers:
  - `task:getAll`, `task:save`, `task:update`, `task:delete`, `task:markDone`, `task:openPanel`.
  - Reads/writes `C:\whis\memory\tasks.json` via Node `fs` directly (matches Python path — confirm this is `memory/tasks.json`, not `data/tasks.json`, since `core/tasks.py` uses `memory/`).
- [ ] Install `uuid` + `@types/uuid` if absent.

### 4. Renderer — `TaskTile` + enhanced Tasks tab

- [ ] Create `src/renderer/overlay/useTasks.ts` (location to match current overlay structure). Exposes: `tasks`, `loading`, `refresh`, `openPanel`, `markDone`, `updateTask`, `deleteTask`.
- [ ] Routes large tasks to `window.api.openTaskPanel(task)`; small tasks expand inline.

### 5. Renderer — `TaskPanel.tsx` (large-task BrowserWindow body)

- [ ] Create `TaskTile.tsx` with badge (LARGE/SMALL), title, time, inline edit for small tasks.
- [ ] Either extend the existing `TasksPanel.tsx` with a large/small tile mode, or add a sibling `TasksTab.tsx` that uses `TaskTile` + sections for Pending / Completed.
- [ ] Match the existing overlay theme tokens (`theme.inputBg`, `theme.border`, `theme.aiAccent`, etc.) — do NOT introduce new color codes; reuse what `TasksPanel.tsx` already uses so it stays visually consistent.

### 6. Optional: In-overlay `StartupNudge` banner

- [ ] Create `TaskPanel.tsx`:
  - Parses task from `window.location.hash` (`#/task-panel?task=...`).
  - Drag region header with title + copy + close buttons.
  - Editable textarea for content, title input, `hh:mm` time inputs (hours select 1–12, minutes free-text, no native time picker).
  - Save via `window.api.updateTask(id, fields)`; visual confirmation.
- [ ] Add hash-based routing in the renderer entry (render `TaskPanel` when `location.hash` starts with `#/task-panel`, else render the overlay).

### 7. Final smoke test

Note: A pill-level startup nudge is already implemented. This would be an in-overlay gold banner variant.

- [ ] Only do this if we want a secondary, click-to-jump banner inside the overlay (in addition to the pill).
- [ ] Would need a new WS message type (e.g., `startup_nudge`) emitted from Python alongside the pill notice, and a handler in `Overlay.tsx` that surfaces a dismissible banner that jumps to the Tasks tab on click.

### 8. Final smoke test

- [ ] Both processes start cleanly.
- [ ] Chat: `save this for tomorrow` creates a task and shows confirmation; no LLM call.
- [ ] Large task tile opens a new 340×420 window to the right; edits persist to `memory/tasks.json`.
- [ ] Small task tile expands inline; edits persist.
- [ ] Manually set a task's `created_at` to yesterday and restart — pill nudge fires after 8s (already working). If Step 7 is done, the in-overlay banner also appears.

---

## Open Questions / Assumptions

1. Tasks file path: we are on `memory/tasks.json` (Python side). Electron main process must read/write the same path, not `data/tasks.json`.
2. Renderer routing: the overlay is a single renderer entry; decide between hash-based switch at the entry point vs. a full router for `#/task-panel`.
3. Large/small classification: add `task_type` to the Python schema and include it in the `tasks/update` payload so the existing `TasksPanel.tsx` can also render the badge without an additional fetch.
