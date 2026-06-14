# Smart Task System (TaskStack 2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the rigid 15-minute reminder loop with a context-aware, graduated, and self-cleaning task reminder system that learns user behavior.

**Architecture:** Add lightweight focus-state inference, a smart delivery queue, snooze-pattern learning, and task decay/archival — all wired into the existing asyncio reminder scheduler without breaking the WebSocket protocol.

**Tech Stack:** Python 3.11, asyncio, existing OpenRouter client, existing ws_bridge broadcast system, pytest.

---

## Prerequisites

- [ ] Read and understand `docs/superpowers/specs/2026-05-30-smart-task-system-design.md`
- [ ] Verify tests pass before any changes: `pytest tests/test_tasks.py tests/test_reminder_scheduler.py -v` (or whatever test files exist)
- [ ] Work on a feature branch (not `main`)

---

## Task 1: Data Model & Settings Foundation

**Files:**
- Modify: `core/tasks.py` (schema normalization + archive helpers)
- Modify: `data/settings.json` (new toggles with defaults)
- Create: `tests/test_task_schema_migration.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_task_schema_migration.py`:
  ```python
  import sys, json
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.tasks import _normalize_task_schema

  def test_normalize_adds_new_fields():
      task = {"id": "t1", "text": "x"}
      norm = _normalize_task_schema(task)
      assert norm.get("archived_at") is None
      assert norm.get("archived_reason") is None
      assert norm.get("estimated_minutes") is None
      assert norm.get("energy_level") is None
      assert norm.get("urgency_score") == 0.0

  def test_normalize_preserves_existing_status():
      task = {"id": "t1", "text": "x", "status": "done"}
      norm = _normalize_task_schema(task)
      assert norm["status"] == "done"
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_task_schema_migration.py -v
  ```
  Expect failures on `archived_at`, `archived_reason`, `estimated_minutes`, `energy_level`, `urgency_score`.

- [ ] **Step 3: Write minimal implementation**
  In `core/tasks.py`, update `_normalize_task_schema`:
  ```python
  def _normalize_task_schema(task: dict) -> dict:
      task.setdefault("content", None)
      task.setdefault("task_type", None)
      task.setdefault("carried_over", False)
      task.setdefault("failed", False)
      task.setdefault("snoozed_until", None)
      task.setdefault("category", None)
      task.setdefault("difficulty", None)
      # NEW fields for TaskStack 2.0
      task.setdefault("archived_at", None)
      task.setdefault("archived_reason", None)
      task.setdefault("estimated_minutes", None)
      task.setdefault("energy_level", None)
      task.setdefault("urgency_score", 0.0)
      return task
  ```
  Also add archive helpers:
  ```python
  def archive_task(task_id: str, reason: str = "stale") -> Optional[dict]:
      data = _load()
      for task in data.get("tasks", []):
          if task.get("id") == task_id:
              task["status"] = "archived"
              task["archived_at"] = datetime.now(timezone.utc).isoformat()
              task["archived_reason"] = reason
              _save(data)
              _notify_overlay()
              return task
      return None

  def unarchive_task(task_id: str) -> Optional[dict]:
      data = _load()
      for task in data.get("tasks", []):
          if task.get("id") == task_id and task.get("status") == "archived":
              task["status"] = "pending"
              task["archived_at"] = None
              task["archived_reason"] = None
              _save(data)
              _notify_overlay()
              return task
      return None

  def get_archived_tasks() -> list[dict]:
      return [t for t in get_tasks() if t.get("status") == "archived"]

  def get_stale_tasks(days: int = 14) -> list[dict]:
      cutoff = datetime.now(timezone.utc) - timedelta(days=days)
      stale = []
      for task in get_tasks():
          if task.get("status") not in ("pending", "in_progress"):
              continue
          created = task.get("created_at")
          if not created:
              continue
          try:
              created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
              if created_dt < cutoff:
                  stale.append(task)
          except Exception:
              continue
      return stale
  ```
  Update `edit_task_fields` to accept the new fields:
  ```python
  if "estimated_minutes" in fields:
      val = fields["estimated_minutes"]
      task["estimated_minutes"] = int(val) if val is not None else None
  if "energy_level" in fields:
      val = fields["energy_level"]
      task["energy_level"] = val if val in ("low", "medium", "high", None) else task.get("energy_level")
  ```

- [ ] **Step 4: Update `data/settings.json`**
  Add new keys (with defaults that preserve current behavior if toggles are false):
  ```json
  {
    "smart_reminders": true,
    "morning_briefing_enabled": true,
    "morning_briefing_time": "08:00",
    "archive_after_days": 14,
    "overdue_digest_mode": "daily",
    "focus_detection_enabled": true,
    "min_deep_work_minutes": 5
  }
  ```

- [ ] **Step 5: Run tests to verify they pass**
  ```bash
  pytest tests/test_task_schema_migration.py -v
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add core/tasks.py data/settings.json tests/test_task_schema_migration.py
  git commit -m "taskstack-2.0: add archive, stale, energy schema + settings toggles"
  ```

---

## Task 2: Focus State Detection Module

**Files:**
- Create: `core/focus_state.py`
- Create: `tests/test_focus_state.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_focus_state.py`:
  ```python
  import sys
  from pathlib import Path
  from datetime import datetime, timedelta, timezone
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.focus_state import FocusStateTracker, _score_state

  def test_deep_work_detected_with_recent_keystrokes_and_same_window():
      tracker = FocusStateTracker()
      now = datetime.now(timezone.utc)
      # Simulate 6 minutes of same window + keystrokes
      tracker._history = [
          {"window": "code.exe", "has_input": True, "fullscreen": False, "ts": now - timedelta(minutes=i)}
          for i in range(6, 0, -1)
      ]
      state = tracker.infer_state()
      assert state == "deep_work"

  def test_idle_detected_after_no_input():
      tracker = FocusStateTracker()
      now = datetime.now(timezone.utc)
      tracker._history = [
          {"window": "browser.exe", "has_input": False, "fullscreen": False, "ts": now - timedelta(minutes=3)}
      ]
      assert tracker.infer_state() == "idle"

  def test_active_when_recent_input_not_deep():
      tracker = FocusStateTracker()
      now = datetime.now(timezone.utc)
      tracker._history = [
          {"window": "browser.exe", "has_input": True, "fullscreen": False, "ts": now - timedelta(seconds=30)}
      ]
      assert tracker.infer_state() == "active"
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_focus_state.py -v
  ```

- [ ] **Step 3: Write minimal implementation**
  Create `core/focus_state.py`:
  ```python
  """core/focus_state.py — Lightweight focus-state inference.

  Infers user attention state from window title sampling and input activity.
  No screenshots, no content analysis. Privacy-safe heuristics only.
  """
  from __future__ import annotations

  import json
  import os
  import threading
  from collections import deque
  from datetime import datetime, timedelta, timezone
  from pathlib import Path
  from typing import Optional

  _STATE_PATH = Path(__file__).resolve().parent.parent / "memory" / "focus_state.json"
  _HISTORY_SEC = 360  # 6 minutes of history
  _DEEP_WORK_MIN = 5   # minutes of same-window + input to count as deep
  _IDLE_SEC = 120      # 2 minutes no input = idle
  _AWAY_SEC = 600      # 10 minutes no input = away

  class FocusStateTracker:
      """Thread-safe focus state tracker with in-memory history."""

      def __init__(self, history_minutes: int = 6) -> None:
          self._lock = threading.Lock()
          self._history: deque[dict] = deque()
          self._history_sec = history_minutes * 60
          self._current_state = "unknown"

      def record(self, window_title: str, has_input: bool, fullscreen: bool = False) -> None:
          now = datetime.now(timezone.utc)
          with self._lock:
              self._history.append({
                  "window": window_title,
                  "has_input": has_input,
                  "fullscreen": fullscreen,
                  "ts": now.isoformat(),
              })
              self._prune(now)
              self._current_state = self._infer(now)

      def _prune(self, now: datetime) -> None:
          cutoff = now - timedelta(seconds=self._history_sec)
          while self._history:
              try:
                  ts = datetime.fromisoformat(self._history[0]["ts"].replace("Z", "+00:00"))
                  if ts < cutoff:
                      self._history.popleft()
                  else:
                      break
              except Exception:
                  self._history.popleft()

      def _infer(self, now: datetime) -> str:
          if not self._history:
              return "unknown"

          # Check for away first
          try:
              last_ts = datetime.fromisoformat(self._history[-1]["ts"].replace("Z", "+00:00"))
              if (now - last_ts).total_seconds() > _AWAY_SEC:
                  return "away"
              if (now - last_ts).total_seconds() > _IDLE_SEC:
                  return "idle"
          except Exception:
              pass

          # Deep work: same window for >= DEEP_WORK_MIN with majority input
          if len(self._history) >= 3:
              try:
                  recent = list(self._history)
                  window_counts: dict[str, int] = {}
                  input_count = 0
                  for entry in recent:
                      w = entry["window"]
                      window_counts[w] = window_counts.get(w, 0) + 1
                      if entry["has_input"]:
                          input_count += 1
                  most_common_window = max(window_counts, key=window_counts.get)
                  window_duration_sec = 0
                  for entry in reversed(recent):
                      if entry["window"] == most_common_window:
                          try:
                              ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                              window_duration_sec = (now - ts).total_seconds()
                          except Exception:
                              continue
                      else:
                          break
                  majority_input = input_count >= len(recent) * 0.5
                  if window_duration_sec >= _DEEP_WORK_MIN * 60 and majority_input:
                      return "deep_work"
              except Exception:
                  pass

          return "active"

      def infer_state(self) -> str:
          with self._lock:
              return self._current_state

      def is_breakpoint(self) -> bool:
          """True if current state transition makes this a good time to interrupt."""
          # Simplistic: idle/active/unknown are breakpoints; deep_work is not
          return self.infer_state() in ("idle", "active", "unknown")

      def persist(self) -> None:
          try:
              _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
              with self._lock:
                  data = {
                      "state": self._current_state,
                      "recorded_at": datetime.now(timezone.utc).isoformat(),
                      "history_count": len(self._history),
                  }
              tmp = _STATE_PATH.with_suffix(".tmp")
              with open(tmp, "w", encoding="utf-8") as f:
                  json.dump(data, f)
              os.replace(str(tmp), str(_STATE_PATH))
          except Exception:
              pass

  # Singleton for the app
  _tracker: Optional[FocusStateTracker] = None
  _tracker_lock = threading.Lock()

  def get_tracker() -> FocusStateTracker:
      global _tracker
      with _tracker_lock:
          if _tracker is None:
              _tracker = FocusStateTracker()
          return _tracker
  ```

- [ ] **Step 4: Run tests to verify they pass**
  ```bash
  pytest tests/test_focus_state.py -v
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add core/focus_state.py tests/test_focus_state.py
  git commit -m "taskstack-2.0: add lightweight focus-state tracker"
  ```

---

## Task 3: Snooze Pattern Learning Module

**Files:**
- Create: `core/snooze_patterns.py`
- Create: `tests/test_snooze_patterns.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_snooze_patterns.py`:
  ```python
  import sys, json, os, tempfile
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.snooze_patterns import SnoozeLearner

  def test_records_snooze_and_suggests():
      with tempfile.TemporaryDirectory() as tmpdir:
          path = Path(tmpdir) / "snooze.json"
          learner = SnoozeLearner(path)
          learner.record_snooze("College", 480)   # 8 hours
          learner.record_snooze("College", 500)
          learner.record_snooze("Home", 60)
          college = learner.suggest("College", top_n=3)
          assert len(college) > 0
          # Most common for College should be around 8h
          assert college[0]["minutes"] == 480
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_snooze_patterns.py -v
  ```

- [ ] **Step 3: Write minimal implementation**
  Create `core/snooze_patterns.py`:
  ```python
  """core/snooze_patterns.py — Learn snooze preferences per category + time-of-day."""
  from __future__ import annotations

  import json
  import os
  import threading
  from collections import Counter
  from datetime import datetime, timezone
  from pathlib import Path
  from typing import Optional

  _DEFAULT_PATH = Path(__file__).resolve().parent.parent / "memory" / "snooze_patterns.json"

  class SnoozeLearner:
      def __init__(self, path: Optional[Path] = None) -> None:
          self._path = path or _DEFAULT_PATH
          self._lock = threading.Lock()
          self._data = self._load()

      def _load(self) -> dict:
          if not self._path.exists():
              return {"category": {}, "time_of_day": {}}
          try:
              with open(self._path, "r", encoding="utf-8") as f:
                  data = json.load(f)
                  if isinstance(data, dict):
                      return data
          except Exception:
              pass
          return {"category": {}, "time_of_day": {}}

      def _save(self) -> None:
          try:
              self._path.parent.mkdir(parents=True, exist_ok=True)
              tmp = self._path.with_suffix(".tmp")
              with open(tmp, "w", encoding="utf-8") as f:
                  json.dump(self._data, f, indent=2)
              os.replace(str(tmp), str(self._path))
          except Exception:
              pass

      def record_snooze(self, category: Optional[str], minutes: int) -> None:
          cat = (category or "default").strip()
          bucket = self._time_bucket()
          with self._lock:
              cat_hist = self._data.setdefault("category", {}).setdefault(cat, [])
              cat_hist.append(minutes)
              # Keep last 20 per category
              self._data["category"][cat] = cat_hist[-20:]

              tod_hist = self._data.setdefault("time_of_day", {}).setdefault(bucket, [])
              tod_hist.append(minutes)
              self._data["time_of_day"][bucket] = tod_hist[-20:]

              self._save()

      def suggest(self, category: Optional[str], top_n: int = 3) -> list[dict]:
          cat = (category or "default").strip()
          with self._lock:
              cat_hist = self._data.get("category", {}).get(cat, [])

          if not cat_hist:
              return self._default_suggestions()

          c = Counter(cat_hist)
          most_common = c.most_common(top_n)
          suggestions = []
          for minutes, count in most_common:
              label = self._label_for(minutes)
              suggestions.append({"minutes": minutes, "label": label, "confidence": count / len(cat_hist)})
          return suggestions

      def _time_bucket(self) -> str:
          hour = datetime.now().hour
          if 5 <= hour < 12:
              return "morning"
          if 12 <= hour < 17:
              return "afternoon"
          if 17 <= hour < 22:
              return "evening"
          return "night"

      def _label_for(self, minutes: int) -> str:
          if minutes < 60:
              return f"{minutes} min"
          if minutes < 120:
              return "1 hour"
          if minutes < 1440:
              return f"{minutes // 60} hours"
          if minutes == 1440:
              return "1 day"
          return f"{minutes // 1440} days"

      def _default_suggestions(self) -> list[dict]:
          return [
              {"minutes": 15, "label": "15 min", "confidence": 0.0},
              {"minutes": 60, "label": "1 hour", "confidence": 0.0},
              {"minutes": 1440, "label": "1 day", "confidence": 0.0},
          ]
  ```

- [ ] **Step 4: Run tests to verify they pass**
  ```bash
  pytest tests/test_snooze_patterns.py -v
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add core/snooze_patterns.py tests/test_snooze_patterns.py
  git commit -m "taskstack-2.0: add snooze pattern learner"
  ```

---

## Task 4: Smart Delivery Engine

**Files:**
- Create: `core/smart_delivery.py`
- Create: `tests/test_smart_delivery.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_smart_delivery.py`:
  ```python
  import sys, json, os, tempfile
  from pathlib import Path
  from datetime import datetime, timezone, timedelta
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.smart_delivery import SmartDeliveryQueue, _urgency_tier

  def test_urgency_tier_gentle_for_pre_due():
      due = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
      assert _urgency_tier(due) == "gentle"

  def test_urgency_tier_standard_for_past_due():
      due = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
      assert _urgency_tier(due) == "standard"

  def test_queue_holds_during_deep_work():
      with tempfile.TemporaryDirectory() as tmpdir:
          q = SmartDeliveryQueue(queue_path=Path(tmpdir) / "queue.json")
          q.enqueue("task_1", "gentle", {"text": "x"})
          assert len(q._queue) == 1
          assert not q.should_deliver_now("deep_work")
          assert q.should_deliver_now("idle")
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_smart_delivery.py -v
  ```

- [ ] **Step 3: Write minimal implementation**
  Create `core/smart_delivery.py`:
  ```python
  """core/smart_delivery.py — Queue and breakpoint delivery engine for reminders."""
  from __future__ import annotations

  import json
  import os
  import threading
  from datetime import datetime, timedelta, timezone
  from pathlib import Path
  from typing import Optional

  _DEFAULT_QUEUE_PATH = Path(__file__).resolve().parent.parent / "memory" / "reminder_queue.json"

  def _urgency_tier(due_at_iso: str) -> str:
      try:
          due = datetime.fromisoformat(str(due_at_iso).replace("Z", "+00:00"))
          now = datetime.now(timezone.utc)
          minutes_to_due = (due - now).total_seconds() / 60
          if minutes_to_due > 0 and minutes_to_due <= 30:
              return "gentle"
          if minutes_to_due <= 0 and minutes_to_due > -30:
              return "standard"
          if minutes_to_due <= -30:
              return "digest"
          return "upcoming"
      except Exception:
          return "standard"

  class SmartDeliveryQueue:
      """Thread-safe reminder queue with persistence."""

      def __init__(self, queue_path: Optional[Path] = None) -> None:
          self._path = queue_path or _DEFAULT_QUEUE_PATH
          self._lock = threading.Lock()
          self._queue = self._load()

      def _load(self) -> list[dict]:
          if not self._path.exists():
              return []
          try:
              with open(self._path, "r", encoding="utf-8") as f:
                  data = json.load(f)
                  if isinstance(data, list):
                      return data
          except Exception:
              pass
          return []

      def _save(self) -> None:
          try:
              self._path.parent.mkdir(parents=True, exist_ok=True)
              tmp = self._path.with_suffix(".tmp")
              with open(tmp, "w", encoding="utf-8") as f:
                  json.dump(self._queue, f, indent=2)
              os.replace(str(tmp), str(self._path))
          except Exception:
              pass

      def enqueue(self, task_id: str, tier: str, payload: dict) -> None:
          with self._lock:
              # De-dupe
              self._queue = [q for q in self._queue if q.get("task_id") != task_id]
              self._queue.append({
                  "task_id": task_id,
                  "tier": tier,
                  "payload": payload,
                  "enqueued_at": datetime.now(timezone.utc).isoformat(),
              })
              self._save()

      def dequeue_all(self, focus_state: str) -> list[dict]:
          if not self.should_deliver_now(focus_state):
              return []
          with self._lock:
              items = list(self._queue)
              self._queue.clear()
              self._save()
          return items

      def should_deliver_now(self, focus_state: str) -> bool:
          # Never deliver during deep_work; deliver at breakpoints
          return focus_state not in ("deep_work", "away")

      def peek(self) -> list[dict]:
          with self._lock:
              return list(self._queue)

      def remove(self, task_id: str) -> None:
          with self._lock:
              self._queue = [q for q in self._queue if q.get("task_id") != task_id]
              self._save()
  ```

- [ ] **Step 4: Run tests to verify they pass**
  ```bash
  pytest tests/test_smart_delivery.py -v
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add core/smart_delivery.py tests/test_smart_delivery.py
  git commit -m "taskstack-2.0: add smart delivery queue with urgency tiers"
  ```

---

## Task 5: Task Decay & Archival

**Files:**
- Create: `core/task_decay.py`
- Create: `tests/test_task_decay.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_task_decay.py`:
  ```python
  import sys, json
  from pathlib import Path
  from datetime import datetime, timezone, timedelta
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.task_decay import DecayScanner, _load_settings

  def test_decay_scanner_flags_old_pending_tasks():
      old = datetime.now(timezone.utc) - timedelta(days=20)
      tasks = [
          {"id": "t1", "text": "old task", "status": "pending", "created_at": old.isoformat()},
          {"id": "t2", "text": "new task", "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()},
          {"id": "t3", "text": "done", "status": "done", "created_at": old.isoformat()},
      ]
      scanner = DecayScanner(days=14)
      stale = scanner.find_stale(tasks)
      assert len(stale) == 1
      assert stale[0]["id"] == "t1"
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_task_decay.py -v
  ```

- [ ] **Step 3: Write minimal implementation**
  Create `core/task_decay.py`:
  ```python
  """core/task_decay.py — Stale task detection and archival workflows."""
  from __future__ import annotations

  import json
  from datetime import datetime, timedelta, timezone
  from pathlib import Path
  from typing import Optional

  _SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"

  def _load_settings() -> dict:
      try:
          if _SETTINGS_PATH.exists():
              with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                  data = json.load(f)
                  if isinstance(data, dict):
                      return data
      except Exception:
          pass
      return {}

  class DecayScanner:
      def __init__(self, days: Optional[int] = None) -> None:
          settings = _load_settings()
          self._days = days if days is not None else int(settings.get("archive_after_days", 14))

      def find_stale(self, tasks: list[dict]) -> list[dict]:
          cutoff = datetime.now(timezone.utc) - timedelta(days=self._days)
          stale = []
          for task in tasks:
              if task.get("status") not in ("pending", "in_progress"):
                  continue
              created = task.get("created_at")
              if not created:
                  continue
              try:
                  created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                  if created_dt < cutoff:
                      stale.append(task)
              except Exception:
                  continue
          return stale

      def build_review_payload(self, tasks: list[dict]) -> dict:
          return {
              "type": "stuck_tasks_review",
              "count": len(tasks),
              "tasks": [{"id": t["id"], "text": t.get("text", ""), "created_at": t.get("created_at")} for t in tasks],
          }
  ```

- [ ] **Step 4: Run tests to verify they pass**
  ```bash
  pytest tests/test_task_decay.py -v
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add core/task_decay.py tests/test_task_decay.py
  git commit -m "taskstack-2.0: add task decay scanner for stale task detection"
  ```

---

## Task 6: Refactor Reminder Scheduler for Smart Delivery

**Files:**
- Modify: `core/reminder_scheduler.py`
- Modify: `tests/test_reminder_scheduler.py` (or create if absent)

- [ ] **Step 1: Write the failing test**
  If `tests/test_reminder_scheduler.py` does not exist, create it:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  from core.reminder_scheduler import ReminderScheduler

  def test_scheduler_loads_settings_with_smart_flags():
      sched = ReminderScheduler()
      settings = sched._get_task_settings()
      # Should contain new keys with defaults
      assert "smart_reminders" in settings
      assert "overdue_digest_mode" in settings
  ```
  Run: `pytest tests/test_reminder_scheduler.py -v`

- [ ] **Step 2: Run test to verify it fails**
  Expect failure if new settings keys aren't returned by `_get_task_settings`.

- [ ] **Step 3: Write minimal implementation**
  Modify `core/reminder_scheduler.py`:

  Update imports at top:
  ```python
  from core.focus_state import get_tracker as get_focus_tracker
  from core.smart_delivery import SmartDeliveryQueue, _urgency_tier
  from core.snooze_patterns import SnoozeLearner
  from core.task_decay import DecayScanner
  ```

  In `__init__`, add:
  ```python
  self._delivery_queue = SmartDeliveryQueue()
  self._snooze_learner = SnoozeLearner()
  self._decay_scanner = DecayScanner()
  self._focus_tracker = get_focus_tracker()
  ```

  Update `_get_task_settings` defaults:
  ```python
  return {
      "reminder_interval_min": int(data.get("reminder_interval_min", 15)),
      "pre_due_warning": bool(data.get("pre_due_warning", True)),
      "carry_over": bool(data.get("carry_over", True)),
      "smart_reminders": bool(data.get("smart_reminders", True)),
      "overdue_digest_mode": str(data.get("overdue_digest_mode", "daily")),
      "focus_detection_enabled": bool(data.get("focus_detection_enabled", True)),
  }
  ```

  Rewrite `_check_all` reminder logic. Replace the aggressive overdue loop (lines 343-372) and the carried-over section (lines 374-384) with:
  ```python
  # --- Smart delivery path ---
  smart_enabled = settings.get("smart_reminders", True)
  focus_enabled = settings.get("focus_detection_enabled", True)
  focus_state = self._focus_tracker.infer_state() if focus_enabled else "unknown"

  # 1. Pre-due warnings (gentle tier)
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
              if smart_enabled and focus_state == "deep_work":
                  self._delivery_queue.enqueue(tid, "gentle", {
                      "title": task.get("text", ""),
                      "due_datetime": due_at,
                      "notification_type": "pre_due",
                      "minutes_remaining": minutes_remaining,
                  })
              else:
                  broadcast_sync({
                      "type": "pill_notification",
                      "payload": {
                          "task_id": tid,
                          "title": task.get("text", ""),
                          "due_datetime": due_at,
                          "notification_type": "pre_due",
                          "minutes_remaining": minutes_remaining,
                          "tier": "gentle",
                      },
                  })
              tracker["pre_due_warned"] = True

  # 2. Due-now tasks (standard tier)
  tasks_due = get_due_today_undone()
  if tasks_due:
      second_miss = [t for t in tasks_due if t.get("carried_over")]
      first_miss = [t for t in tasks_due if not t.get("carried_over")]

      # Second miss → mark failed (keep existing behavior)
      if second_miss:
          failed_tasks = []
          for task in second_miss:
              if is_snoozed(task):
                  continue
              if mark_failed(task.get("id", "")):
                  failed_tasks.append({"id": task.get("id"), "title": task.get("text", "")})
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

      # First miss → standard tier (immediate if possible, else queue)
      if first_miss:
          newly_due = []
          for task in first_miss:
              tid = task.get("id", "")
              tracker = self._tracker.setdefault(tid, {})
              if not tracker.get("due_warned", False):
                  newly_due.append(task)
                  tracker["due_warned"] = True

          if newly_due:
              for task in newly_due:
                  tid = task.get("id", "")
                  if smart_enabled and focus_state == "deep_work":
                      self._delivery_queue.enqueue(tid, "standard", {
                          "title": task.get("text", ""),
                          "due_datetime": task.get("due_at"),
                          "notification_type": "due_now",
                          "minutes_remaining": 0,
                      })
                  else:
                      broadcast_sync({
                          "type": "pill_notification",
                          "payload": {
                              "task_id": tid,
                              "title": task.get("text", ""),
                              "due_datetime": task.get("due_at"),
                              "notification_type": "due_now",
                              "minutes_remaining": 0,
                              "tier": "standard",
                          },
                      })
              broadcast_sync({
                  "type": "due_alert",
                  "count": len(newly_due),
                  "tasks": [{"id": t.get("id"), "title": t.get("text", "")} for t in newly_due],
              })

          # Overdue digest (daily mode replaces aggressive 15-min loop)
          if settings.get("overdue_digest_mode", "daily") == "daily":
              # Overdue tasks are batched into the next briefing cycle, not spammed here.
              # We still update tracker counts so the briefing knows they're overdue.
              for task in first_miss:
                  tid = task.get("id", "")
                  tracker = self._tracker.setdefault(tid, {})
                  tracker["overdue_reminder_count"] = tracker.get("overdue_reminder_count", 0) + 1
                  tracker["last_overdue_reminder"] = now_utc.isoformat()
          else:
              # Legacy aggressive mode (fallback)
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
                      tracker["last_overdue_reminder"] = now_utc.isoformat()
                      tracker["overdue_reminder_count"] = tracker.get("overdue_reminder_count", 0) + 1
                      broadcast_sync({
                          "type": "overdue_reminder",
                          "task": {"id": tid, "title": task.get("text", "")},
                          "reminder_count": tracker["overdue_reminder_count"],
                      })

  # 3. Deliver queued items at breakpoints
  if smart_enabled:
      queued = self._delivery_queue.dequeue_all(focus_state)
      for item in queued:
          payload = item.get("payload", {})
          payload["task_id"] = item.get("task_id")
          payload["tier"] = item.get("tier")
          broadcast_sync({
              "type": "pill_notification",
              "payload": payload,
          })

  # 4. Stuck task scan (daily, once per day)
  if not hasattr(self, '_last_decay_scan') or (now_ts - self._last_decay_scan) >= 86400:
      stale = self._decay_scanner.find_stale(get_tasks())
      if stale:
          broadcast_sync(self._decay_scanner.build_review_payload(stale))
      self._last_decay_scan = now_ts
  ```

- [ ] **Step 4: Run tests to verify they pass**
  ```bash
  pytest tests/test_reminder_scheduler.py -v
  ```
  Also run broader tests to check for regressions:
  ```bash
  pytest tests/test_tasks.py -v
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add core/reminder_scheduler.py tests/test_reminder_scheduler.py
  git commit -m "taskstack-2.0: refactor scheduler for smart delivery + decay scan"
  ```

---

## Task 7: Wire Focus State Sampling into the App Loop

**Files:**
- Modify: `core/system_context.py` (or wherever window/input sampling already happens)
- Modify: `app/main.py` (if needed to init focus tracker sampling)

- [ ] **Step 1: Identify existing sampling loop**
  `core/system_context.py` already samples active window titles periodically. We can hook into that loop to also call `focus_state.get_tracker().record(...)`.

- [ ] **Step 2: Add focus sampling to system context scanner**
  In `core/system_context.py`, find the loop that samples window titles. After getting the window title, add:
  ```python
  try:
      from core.focus_state import get_tracker
      tracker = get_tracker()
      # Infer input from the fact that a scan happened recently + window is same
      # Simplistic: if this scan fired, the system is not away
      tracker.record(window_title, has_input=True, fullscreen=is_fullscreen)
  except Exception:
      pass
  ```
  (Note: `is_fullscreen` can be inferred from window bounds matching screen bounds via existing window mgmt platform calls.)

- [ ] **Step 3: Verify no startup crash**
  ```bash
  python -c "import main"
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add core/system_context.py
  git commit -m "taskstack-2.0: wire focus state sampling into system context scanner"
  ```

---

## Task 8: Server Endpoints for Archive & Smart Snooze

**Files:**
- Modify: `core/server.py`

- [ ] **Step 1: Add archive/unarchive endpoints**
  Find where other task endpoints are defined in `core/server.py`. Add:
  ```python
  @app.post("/tasks/{task_id}/archive")
  async def archive_task_endpoint(task_id: str):
      from core.tasks import archive_task
      result = archive_task(task_id)
      if result:
          return {"success": True, "task": result}
      return {"success": False, "error": "Task not found"}

  @app.post("/tasks/{task_id}/unarchive")
  async def unarchive_task_endpoint(task_id: str):
      from core.tasks import unarchive_task
      result = unarchive_task(task_id)
      if result:
          return {"success": True, "task": result}
      return {"success": False, "error": "Task not found"}

  @app.get("/tasks/stuck")
  async def stuck_tasks_endpoint(days: int = 14):
      from core.task_decay import DecayScanner
      from core.tasks import get_tasks
      scanner = DecayScanner(days=days)
      return {"tasks": scanner.find_stale(get_tasks())}

  @app.get("/tasks/snooze-suggestions")
  async def snooze_suggestions_endpoint(category: str = "default"):
      from core.snooze_patterns import SnoozeLearner
      learner = SnoozeLearner()
      return {"suggestions": learner.suggest(category)}
  ```

- [ ] **Step 2: Verify server imports**
  ```bash
  python -c "from core.server import app; print('OK')"
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add core/server.py
  git commit -m "taskstack-2.0: add archive, stuck-tasks, and snooze-suggestion endpoints"
  ```

---

## Task 9: WebSocket Protocol Updates

**Files:**
- Modify: `core/ws_bridge.py`

- [ ] **Step 1: Add new message type constants/handlers**
  In `core/ws_bridge.py`, ensure these message types are documented and handled:
  - `stuck_tasks_review` — already broadcast from scheduler
  - `morning_briefing` — will be added later; for now just document it in a comment
  - `pill_notification` payload now includes `"tier"` field

  Add a helper to broadcast morning briefing (can be called by scheduler or external trigger):
  ```python
  def broadcast_morning_briefing(tasks_today: list, overdue: list, suggestion: str = "") -> None:
      broadcast_sync({
          "type": "morning_briefing",
          "tasks_today": tasks_today,
          "overdue": overdue,
          "suggestion": suggestion,
      })
  ```

- [ ] **Step 2: Verify imports**
  ```bash
  python -c "from core.ws_bridge import broadcast_sync; print('OK')"
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add core/ws_bridge.py
  git commit -m "taskstack-2.0: add morning_briefing broadcast helper + tiered pill docs"
  ```

---

## Task 10: Integration Verification

- [ ] **Step 1: Run all task-related tests**
  ```bash
  pytest tests/test_task_schema_migration.py tests/test_focus_state.py tests/test_snooze_patterns.py tests/test_smart_delivery.py tests/test_task_decay.py tests/test_reminder_scheduler.py tests/test_tasks.py -v
  ```

- [ ] **Step 2: Run full import test**
  ```bash
  python -c "import main"
  ```

- [ ] **Step 3: Spot-check the data/settings.json schema**
  Verify all new keys are present and defaults are reasonable.

- [ ] **Step 4: Commit any final fixes**

---

## Post-Implementation: Overlay UI Work (Separate Plan)

The Electron overlay will need UI updates to render:
- Tiered pill notifications (gentle vs standard styling)
- Smart snooze buttons with dynamic labels
- Stuck tasks review banner
- Morning briefing panel

**This plan intentionally covers only the Python backend.** A separate frontend plan should be written after the backend is merged and the WebSocket messages are stable.

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every requirement in the design doc maps to at least one task.
    - Focus state detection → Task 2
    - Smart delivery / breakpoints → Task 4 + Task 6
    - Graduated urgency → Task 4 + Task 6
    - Smart snooze learning → Task 3
    - Task decay + archive → Task 1 (schema) + Task 5 + Task 8
    - Morning briefing hook → Task 9
    - Settings toggles → Task 1 + Task 6
- [ ] **Placeholder scan:** No "TBD", "TODO", or "implement later" strings in plan.
- [ ] **Type consistency:** All new functions use consistent signatures (task_id: str, return Optional[dict]).
- [ ] **Backward compatibility:** All new fields have defaults. `overdue_digest_mode: "daily"` is new default but `"immediate"` preserves old behavior.
- [ ] **Test coverage:** Every new module has a dedicated test file.

---

## Execution Handoff Options

1. **Subagent-Driven Development (Recommended)** — Dispatch a fresh subagent per task. Review between tasks. Good for parallelizing independent modules (Tasks 2, 3, 4, 5 can run in parallel after Task 1).
2. **Inline Execution via executing-plans** — Execute tasks sequentially in this session using checkpoints. Good for keeping full context.

**Recommended order:** Task 1 → Tasks 2-5 (parallelizable) → Task 6 → Tasks 7-9 → Task 10.
