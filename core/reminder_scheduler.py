"""
core/reminder_scheduler.py — Persistent, async-safe reminder state + scheduler.

Replaces the legacy threading.Timer-based _due_check / _due_reminder
machinery in app/main.py with an asyncio-native implementation that:
  - Persists reminder state atomically to memory/reminder_state.json
  - Hydrates state on startup
  - Polls memory/tasks.json for external modifications
  - Schedules cancellable, state-aware reminder checks
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MEMORY_DIR = _PROJECT_ROOT / "memory"
_TASKS_PATH = _MEMORY_DIR / "tasks.json"
_STATE_PATH = _MEMORY_DIR / "reminder_state.json"

_REMINDER_CHECK_INTERVAL_SEC = 15 * 60  # 15 minutes
_PRE_DUE_WINDOW_MINUTES = 30
_FILE_WATCH_INTERVAL_SEC = 2.0


class ReminderStateManager:
    """Atomic persistence layer for reminder tracker state."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def load(self) -> dict[str, dict]:
        """Hydrate tracker state from disk. Returns empty dict on missing/corrupt file."""
        async with self._lock:
            if not self._path.exists():
                return {}
            try:
                raw = self._path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    logger.warning("[ReminderState] Root is not a dict — starting fresh")
                    return {}
                validated: dict[str, dict] = {}
                for task_id, entry in data.items():
                    if not isinstance(entry, dict):
                        continue
                    validated[task_id] = {
                        "pre_due_warned": bool(entry.get("pre_due_warned", False)),
                        "due_warned": bool(entry.get("due_warned", False)),
                        "overdue_reminder_count": int(entry.get("overdue_reminder_count", 0)),
                        "last_overdue_reminder": entry.get("last_overdue_reminder"),
                    }
                return validated
            except json.JSONDecodeError as exc:
                logger.warning("[ReminderState] JSON corrupt (%s) — starting fresh", exc)
                return {}
            except OSError as exc:
                logger.error("[ReminderState] Read error (%s) — starting fresh", exc)
                return {}

    async def save(self, state: dict[str, dict]) -> None:
        """Atomically persist state using temp-file + os.replace."""
        async with self._lock:
            tmp = self._path.with_suffix(".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                os.replace(str(tmp), str(self._path))
            except Exception:
                # Clean up tmp on failure
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                raise


class ReminderScheduler:
    """Async-native reminder scheduler with file watching and persistent state."""

    def __init__(self) -> None:
        self._state_manager = ReminderStateManager(_STATE_PATH)
        self._tracker: dict[str, dict] = {}
        self._shutdown_event = asyncio.Event()
        self._check_event = asyncio.Event()  # triggered to wake the loop early
        self._task: Optional[asyncio.Task] = None
        self._watcher_task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks_mtime: float = 0.0
        self._tasks_size: int = 0

    # ------------------------------------------------------------------
    #  Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.debug("[ReminderScheduler] Already running")
            return

        def _run_loop():
            asyncio.run(self._run())

        self._thread = threading.Thread(target=_run_loop, daemon=True, name="reminder-scheduler")
        self._thread.start()
        logger.info("[ReminderScheduler] Background thread started")

    def stop(self, timeout: float = 5.0) -> None:
        """Signal shutdown and wait briefly for cleanup."""
        if not self._thread or not self._thread.is_alive():
            return
        if self._loop and self._shutdown_event:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
            self._loop.call_soon_threadsafe(self._check_event.set)
        self._thread.join(timeout=timeout)
        logger.info("[ReminderScheduler] Stopped")

    # ------------------------------------------------------------------
    #  Internal async runtime
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._tracker = await self._state_manager.load()
        logger.info("[ReminderScheduler] Hydrated %d tracker entries", len(self._tracker))

        # Initialize file watch baseline
        self._update_file_baseline()

        # Start file watcher
        self._watcher_task = asyncio.create_task(self._file_watcher(), name="reminder-watcher")

        # Initial check after a short delay (mimics legacy 30 s startup offset)
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=30.0)
            return  # shutdown requested before first check
        except asyncio.TimeoutError:
            pass

        await self._check_all()

        # Main loop
        while not self._shutdown_event.is_set():
            self._check_event.clear()
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=_REMINDER_CHECK_INTERVAL_SEC,
                )
                break  # shutdown
            except asyncio.TimeoutError:
                pass

            if self._check_event.is_set():
                # Woken by file watcher — run check immediately
                await self._check_all()
            else:
                # Normal periodic check
                await self._check_all()

        # Cancel watcher
        if self._watcher_task and not self._watcher_task.done():
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass

        # Final persistence
        await self._state_manager.save(self._tracker)
        logger.info("[ReminderScheduler] Final state persisted")

    # ------------------------------------------------------------------
    #  File watcher (polling-based, stdlib only)
    # ------------------------------------------------------------------

    def _update_file_baseline(self) -> None:
        try:
            st = _TASKS_PATH.stat()
            self._tasks_mtime = st.st_mtime
            self._tasks_size = st.st_size
        except FileNotFoundError:
            self._tasks_mtime = 0.0
            self._tasks_size = 0

    def _file_changed(self) -> bool:
        try:
            st = _TASKS_PATH.stat()
            changed = (st.st_mtime != self._tasks_mtime) or (st.st_size != self._tasks_size)
            if changed:
                self._tasks_mtime = st.st_mtime
                self._tasks_size = st.st_size
            return changed
        except FileNotFoundError:
            prev = self._tasks_mtime != 0.0 or self._tasks_size != 0
            self._tasks_mtime = 0.0
            self._tasks_size = 0
            return prev
        except OSError:
            return False

    async def _file_watcher(self) -> None:
        """Poll tasks.json for external modifications."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=_FILE_WATCH_INTERVAL_SEC,
                )
                return
            except asyncio.TimeoutError:
                pass

            if self._file_changed():
                logger.debug("[ReminderScheduler] tasks.json changed externally")
                self._check_event.set()
                if self._loop:
                    self._loop.call_soon_threadsafe(self._check_event.set)

    # ------------------------------------------------------------------
    #  Reminder logic
    # ------------------------------------------------------------------

    async def _check_all(self) -> None:
        """Run the full reminder evaluation cycle."""
        try:
            settings = self._get_task_settings()
            now_utc = datetime.now(timezone.utc)
            now_ts = now_utc.timestamp()

            # Lazy imports to avoid circular deps at module load time
            from core.tasks import (
                get_due_today_undone,
                get_due_soon,
                get_carried_over_undone,
                get_tasks,
                is_snoozed,
                mark_failed,
                get_task_snapshot,
            )
            from core.ws_bridge import broadcast_sync

            # 1. Pre-due warnings (tasks due within 30 minutes)
            if settings.get("pre_due_warning", True):
                soon_tasks = get_due_soon(minutes=_PRE_DUE_WINDOW_MINUTES)
                for task in soon_tasks:
                    tid = task.get("id", "")
                    tracker = self._tracker.setdefault(tid, {})
                    if not tracker.get("pre_due_warned", False):
                        due_at = task.get("due_at", "")
                        minutes_remaining = 0
                        try:
                            dt = datetime.fromisoformat(str(due_at).replace("Z", "+00:00"))
                            minutes_remaining = max(0, int((dt - now_utc).total_seconds() / 60))
                        except Exception:
                            pass
                        broadcast_sync({
                            "type": "pill_notification",
                            "payload": {
                                "task_id": tid,
                                "title": task.get("text", ""),
                                "due_datetime": due_at,
                                "notification_type": "pre_due",
                                "minutes_remaining": minutes_remaining,
                            },
                        })
                        tracker["pre_due_warned"] = True

            # 2. Tasks that are due today / right now
            tasks = get_due_today_undone()
            if tasks:
                second_miss = [t for t in tasks if t.get("carried_over")]
                first_miss = [t for t in tasks if not t.get("carried_over")]

                # Second miss → mark as failed
                if second_miss:
                    failed_tasks = []
                    for task in second_miss:
                        if is_snoozed(task):
                            continue
                        if mark_failed(task.get("id", "")):
                            failed_tasks.append({
                                "id": task.get("id"),
                                "title": task.get("text", ""),
                            })
                    if failed_tasks:
                        broadcast_sync({"type": "tasks_failed", "tasks": failed_tasks})
                        try:
                            snapshot = get_task_snapshot()
                            broadcast_sync({
                                "type": "tasks/update",
                                "payload": snapshot.get("tasks", []),
                                "history": snapshot.get("history", []),
                                "suggestion": snapshot.get("suggestion"),
                            })
                        except Exception:
                            pass

                # First miss → due alert + aggressive reminders
                if first_miss:
                    newly_due = []
                    for task in first_miss:
                        tid = task.get("id", "")
                        tracker = self._tracker.setdefault(tid, {})
                        if not tracker.get("due_warned", False):
                            newly_due.append(task)
                            tracker["due_warned"] = True

                    if newly_due:
                        broadcast_sync({
                            "type": "due_alert",
                            "count": len(newly_due),
                            "tasks": [{"id": t.get("id"), "title": t.get("text", "")} for t in newly_due],
                        })
                        for task in newly_due:
                            broadcast_sync({
                                "type": "pill_notification",
                                "payload": {
                                    "task_id": task.get("id"),
                                    "title": task.get("text", ""),
                                    "due_datetime": task.get("due_at"),
                                    "notification_type": "due_now",
                                    "minutes_remaining": 0,
                                },
                            })

                    # Aggressive overdue reminders: every 15 minutes while overdue
                    for task in first_miss:
                        tid = task.get("id", "")
                        tracker = self._tracker.setdefault(tid, {})
                        last_reminder = tracker.get("last_overdue_reminder")
                        last_ts = 0.0
                        if last_reminder:
                            try:
                                last_dt = datetime.fromisoformat(str(last_reminder).replace("Z", "+00:00"))
                                last_ts = last_dt.timestamp()
                            except Exception:
                                pass
                        if now_ts - last_ts >= _REMINDER_CHECK_INTERVAL_SEC:
                            tracker["last_overdue_reminder"] = datetime.now(timezone.utc).isoformat()
                            tracker["overdue_reminder_count"] = tracker.get("overdue_reminder_count", 0) + 1
                            broadcast_sync({
                                "type": "overdue_reminder",
                                "task": {"id": tid, "title": task.get("text", "")},
                                "reminder_count": tracker["overdue_reminder_count"],
                            })
                            broadcast_sync({
                                "type": "pill_notification",
                                "payload": {
                                    "task_id": tid,
                                    "title": task.get("text", ""),
                                    "due_datetime": task.get("due_at"),
                                    "notification_type": "overdue",
                                    "minutes_remaining": 0,
                                },
                            })

            # 3. Carried-over undone tasks (legacy due_reminder broadcast)
            carried = [t for t in get_carried_over_undone() if not is_snoozed(t)]
            if carried:
                broadcast_sync({
                    "type": "due_reminder",
                    "count": len(carried),
                    "tasks": [
                        {"id": t.get("id"), "title": t.get("text", ""), "scheduled_for": t.get("due_at")}
                        for t in carried
                    ],
                })

            # 4. Cleanup stale tracker entries for completed / deleted tasks
            valid_ids = {t.get("id", "") for t in get_tasks()}
            stale = [k for k in self._tracker if k not in valid_ids]
            for k in stale:
                del self._tracker[k]
            if stale:
                logger.debug("[ReminderScheduler] Cleaned up %d stale tracker entries", len(stale))

            # Persist after every check cycle
            await self._state_manager.save(self._tracker)

        except Exception:
            logger.exception("[ReminderScheduler] Error during check cycle")

    def _get_task_settings(self) -> dict:
        """Load task reminder settings with defaults."""
        try:
            settings_path = _PROJECT_ROOT / "data" / "settings.json"
            if settings_path.exists():
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {
                        "reminder_interval_min": int(data.get("reminder_interval_min", 15)),
                        "pre_due_warning": bool(data.get("pre_due_warning", True)),
                        "carry_over": bool(data.get("carry_over", True)),
                    }
        except Exception:
            pass
        return {"reminder_interval_min": 15, "pre_due_warning": True, "carry_over": True}
