# Due Alert + Task Saved Confirmation Window — Design Spec
**Date:** 2026-04-18
**Repo roots:**
- Electron UI: `C:\whis\ui\whiztant-overlay\`
- Python backend: `C:\whis\whiztant-app\`

---

## Overview

Two related features that add task-lifecycle notifications to the Whiztant pill:

1. **Due Alert** — At 6pm daily, if today's tasks are not done, the pill shows a persistent red banner. Dismissing or clicking "Reschedule Tomorrow" carries the task forward. Reminders fire every 4 hours the next day. If the task is still undone at the *next* day's 6pm, it moves to an "Undone" section in the Tasks tab permanently.

2. **Task Saved Confirmation Window** — When a task is saved via the `/task` speech command, a small transparent `BrowserWindow` opens showing the full task content and time. The user can open the main chat window from it or close it. Auto-sizes to content, max height = main overlay height (~420px), scrollable if overflow.

---

## Part 1: Due Alert

### 1.1 Task Schema Changes

Add two new fields to each task object in `data/tasks.json`:

```json
{
  "carried_over": false,
  "failed": false
}
```

- `carried_over: true` — set when a task is rescheduled past its original due date via the due alert
- `failed: true` — set at the second 6pm miss; task moves to "Undone" section, no further alerts

All existing tasks without these fields default to `false`.

### 1.2 Python: New Helpers in `core/task_manager.py`

**New functions to add:**

```
get_due_today_undone() -> list[dict]
  Returns tasks where scheduled_for == today AND done == False AND failed == False

get_carried_over_undone() -> list[dict]
  Returns tasks where carried_over == True AND done == False AND failed == False

reschedule_to_tomorrow(task_id: str) -> bool
  Sets scheduled_for = tomorrow, carried_over = True, saves

mark_failed(task_id: str) -> bool
  Sets failed = True, saves
```

### 1.3 Python: Timers in `main.py`

**Pattern:** mirror the existing `threading.Timer(8.0, _startup_nudge)` exactly.

**New utility:**
```python
def seconds_until(hour: int, minute: int = 0) -> float:
    """Seconds from now until the next occurrence of HH:MM (today or tomorrow)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()
```

**`_due_check()` — fires at 6pm daily:**
```
1. Call get_due_today_undone()
2. If any results:
   a. Separate into two groups:
      - carried_over == True → these are SECOND misses → call mark_failed() for each → broadcast {type: "tasks_failed", tasks: [...]}
      - carried_over == False → first miss → broadcast {type: "due_alert", count: N, tasks: [{id, title}]}
3. Re-schedule: threading.Timer(seconds_until(18, 0), _due_check).start()
```

Start at app boot:
```python
threading.Timer(seconds_until(18, 0), _due_check).start()
```

**`_due_reminder()` — fires every 4 hours, only when carried-over tasks exist:**
```
1. Call get_carried_over_undone()
2. If any results:
   broadcast {type: "due_reminder", count: N, tasks: [{id, title, scheduled_for}]}
   Re-schedule: threading.Timer(4 * 3600, _due_reminder).start()
3. If no results: stop (do NOT re-schedule — nothing left to remind about)
```

**Two start points for `_due_reminder`:**

At app boot (catches cases where tasks were rescheduled in a previous session):
```python
if get_carried_over_undone():
    threading.Timer(4 * 3600, _due_reminder).start()
```

After `_due_check` broadcasts a `due_alert` (some of those tasks will likely be rescheduled):
```python
# Inside _due_check(), after broadcasting due_alert:
threading.Timer(4 * 3600, _due_reminder).start()
```

Note: Python cannot observe when Electron calls `task:reschedule` (that IPC writes directly to `tasks.json`). The 4h timer self-stops when `get_carried_over_undone()` returns empty, so starting it eagerly after a `due_alert` is safe — worst case it fires once and finds nothing.

### 1.4 WebSocket Messages

| `type` | When | Payload |
|---|---|---|
| `due_alert` | 6pm, first miss | `{type, count: N, tasks: [{id, title}]}` |
| `due_reminder` | Every 4h, carried-over | `{type, count: N, tasks: [{id, title, scheduled_for}]}` |
| `tasks_failed` | 6pm, second miss | `{type, tasks: [{id, title}]}` (renderer updates Tasks tab) |

### 1.5 Electron: New IPC

**Preload (`src/preload/index.ts`) — add:**
```typescript
rescheduleTask: (id: string): Promise<boolean> =>
  ipcRenderer.invoke('task:reschedule', id)
```

**Main (`src/main/index.ts`) — add handler:**
```typescript
ipcMain.handle('task:reschedule', (_e, id: string) => {
  // Read tasks.json, set scheduled_for = tomorrow ISO date string, carried_over = true, save
})
```

**Preload type (`src/preload/index.d.ts`) — extend Task:**
```typescript
carried_over: boolean
failed: boolean
```

### 1.6 React: `DueAlert.tsx`

**Location:** `src/renderer/src/components/DueAlert.tsx`

**Props:**
```typescript
interface Props {
  tasks: { id: string; title: string }[]
  onReschedule: (id: string) => void
  onDismissAll: () => void   // dismissing all = reschedule all
}
```

**Visual:**
- Collapsed state (default): red banner on the pill — `"N tasks due — not done ▾"`
- Expanded state (on click): lists each task in red text with a `"Reschedule Tomorrow"` button per task
- ✕ button: calls `onDismissAll` which reschedules all tasks, closes banner
- Clicking `"Reschedule Tomorrow"` on a single task reschedules just that one; when all are rescheduled the banner closes
- Stays visible until all tasks are rescheduled or ✕ is pressed — no auto-dismiss

**Colours:** red (`#EF4444` / `text-red-500`), dark background consistent with existing pill theme (`#1C0A0A`)

### 1.7 React: `DueReminder.tsx`

**Location:** `src/renderer/src/components/DueReminder.tsx`

**Props:**
```typescript
interface Props {
  tasks: { id: string; title: string; scheduled_for: string }[]
  onDismiss: () => void
}
```

**Visual:**
- Softer gold banner (not red — reminder, not hard deadline): `"You have N carried-over tasks from yesterday"`
- Expands to show task titles
- ✕ dismisses for this reminder cycle (will show again in 4h if still undone)
- No reschedule button — user manages via Tasks tab

### 1.8 React: Tasks Tab — "Undone" Section

**File:** `src/renderer/src/pages/TasksTab.tsx` (existing, modify)

Add a third section below the existing "Completed" section:

```
Active tasks
Completed tasks
─────────────────
Undone (missed)       ← new
```

Filter: `tasks.filter(t => t.failed === true)`

**Visual:** muted red task tiles with a label `"Not completed — please review"` beneath the title. No action buttons other than Delete.

### 1.9 React: `App.tsx` — Wire Up

In the existing WS message handler, add:

```typescript
case 'due_alert':
  setDueAlert({ tasks: msg.tasks, count: msg.count })
  break
case 'due_reminder':
  setDueReminder({ tasks: msg.tasks })
  break
case 'tasks_failed':
  // Refresh task list so failed tasks appear in Undone section
  refresh()
  break
```

Render (alongside existing `StartupNudge`):
```tsx
{dueAlert   && <DueAlert   tasks={dueAlert.tasks}   onReschedule={...} onDismissAll={...} />}
{dueReminder && <DueReminder tasks={dueReminder.tasks} onDismiss={...} />}
```

---

## Part 2: Task Saved Confirmation Window

### 2.1 Trigger

When Python saves a task via the `/task` speech command, it already broadcasts:
```json
{ "type": "task_saved", "task": { ...full task object... }, "reply": "..." }
```

The Electron **main process** intercepts this WS message and calls `openTaskConfirmWindow(task)`.

> Note: the main process receives WS messages via the existing Python↔Electron WebSocket bridge. Find wherever `startup_nudge` is forwarded to the renderer and add `task_saved` handling at the same level — but route it to `openTaskConfirmWindow` instead of forwarding to the renderer.

### 2.2 Window Factory: `src/main/windows/taskConfirmWindow.ts`

```
- frameless, transparent, alwaysOnTop, skipTaskbar
- Width: 320px (fixed)
- Height: auto-sized to content, min 120px, max 420px
- Position: centred on the primary display (pill position varies per setup, centre is always safe)
- Only one instance at a time — if one is open, close it and open the new one
- Passes task via URL hash param (same pattern as TaskPanel)
```

**Top bar buttons (rendered inside the window):**
- **Top-left:** Chat icon button — calls `ipcRenderer.send('confirm:open-chat')` → main process focuses/shows the main overlay window
- **Top-right:** ✕ button — `window.close()`

### 2.3 New IPC Channel

**Main process:**
```typescript
ipcMain.on('confirm:open-chat', () => {
  // Focus the main overlay BrowserWindow
  const overlay = BrowserWindow.getAllWindows().find(w => !w.isDestroyed() && w !== confirmWin)
  overlay?.show()
  overlay?.focus()
})
```

### 2.4 React View: `src/renderer/src/components/TaskConfirmView.tsx`

Reads task from URL hash param (same `decodeURIComponent(JSON.parse(...))` pattern as `TaskPanel.tsx`).

**Layout (top to bottom):**
```
┌─────────────────────────────────────┐
│ [Chat icon]              [✕ Close]  │  ← fixed header, draggable
├─────────────────────────────────────┤
│  ✓ Task Saved                        │
│                                     │
│  [Task Title]                        │
│  Today at HH:MM                     │
│                                     │
│  [Full task content — scrollable    │
│   if content exceeds window height] │
└─────────────────────────────────────┘
```

**Sizing behaviour:**
- The window height is determined by content
- The content area (`overflow-y-auto`) scrolls if the full task content would exceed 420px
- Fixed header stays pinned; content area fills remaining space

**Styling:** consistent with existing pill theme — dark background (`#1C0A0A`), gold accents (`#C4956A`), cream text (`#FAF6F1`)

### 2.5 Routing

In `App.tsx` (or the renderer entry), detect the `#/task-confirm` hash route and render `<TaskConfirmView />` instead of the overlay — same pattern already used for `TaskPanel`.

---

## File Map Summary

| Action | File | What changes |
|---|---|---|
| Modify | `C:\whis\whiztant-app\core\task_manager.py` | Add `carried_over`, `failed` fields; 4 new helper functions |
| Modify | `C:\whis\whiztant-app\main.py` | `seconds_until()`, `_due_check()`, `_due_reminder()`, timers at boot |
| Modify | `src/preload/index.ts` | Add `rescheduleTask` IPC method |
| Modify | `src/preload/index.d.ts` | Add `carried_over`, `failed` to Task type; add `rescheduleTask` to API |
| Modify | `src/main/index.ts` | Add `task:reschedule` IPC handler; add `task_saved` WS → `openTaskConfirmWindow` |
| **Create** | `src/main/windows/taskConfirmWindow.ts` | BrowserWindow factory for task confirm |
| **Create** | `src/renderer/src/components/DueAlert.tsx` | Red due alert banner (persistent) |
| **Create** | `src/renderer/src/components/DueReminder.tsx` | Gold 4h reminder banner |
| **Create** | `src/renderer/src/components/TaskConfirmView.tsx` | Task saved confirmation window view |
| Modify | `src/renderer/src/pages/TasksTab.tsx` | Add "Undone" section for failed tasks |
| Modify | `src/renderer/src/App.tsx` | Wire WS cases, render DueAlert/DueReminder, add `/task-confirm` route |

---

## Assumptions to Verify Before Implementation

1. **WS message routing in main process** — Confirm where the Python→Electron WebSocket messages are received in `src/main/index.ts` (or a separate ws-client file). The `task_saved` case must be caught here to call `openTaskConfirmWindow`, not forwarded to renderer.
2. **Existing hash routing** — Confirm the renderer uses hash-based routing (`#/task-panel`, etc.) so that `#/task-confirm` works the same way.
3. **`threading.Timer` event loop** — The `_due_check` broadcast uses `asyncio.run_coroutine_threadsafe(broadcast(msg), loop)` — same pattern as `_startup_nudge`. Confirm the event loop reference is available at module level.
4. **`seconds_until(18, 0)` edge case** — If the app starts after 6pm, `seconds_until` returns time until 6pm *tomorrow*, which is correct. Verify the function handles midnight crossover.
5. **Single confirm window** — If `task_saved` fires while a confirm window is already open (e.g. rapid /task commands), the old window closes and a new one opens. Confirm this is the desired UX.