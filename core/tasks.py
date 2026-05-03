"""
core/tasks.py - Task CRUD + voice command parser.

Storage: %APPDATA%\Wiztant\tasks.json
"""

import json
import os
import random
import re
import string
import sys
import requests
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MEMORY_DIR = _PROJECT_ROOT / "memory"
_TASKS_PATH = _MEMORY_DIR / "tasks.json"


def _notify_overlay():
    """Broadcast tasks/update to all connected overlay clients."""
    try:
        from core.ws_bridge import send_tasks_update
        send_tasks_update([])
    except Exception:
        pass


def _normalize_task_schema(task: dict) -> dict:
    task.setdefault("content", None)
    task.setdefault("task_type", None)
    task.setdefault("carried_over", False)
    task.setdefault("failed", False)
    task.setdefault("snoozed_until", None)
    return task

# Legacy path — migrated on first load if a newer memory/tasks.json is absent.
# Only relevant on Windows; Linux never had this path.
_LEGACY_APPDATA = os.environ.get("APPDATA")
if _LEGACY_APPDATA:
    _LEGACY_TASKS_PATH = Path(_LEGACY_APPDATA) / "Wiztant" / "tasks.json"
else:
    _LEGACY_TASKS_PATH = Path("/dev/null")  # never exists on Linux
_TASK_REFINER_MODEL = os.getenv("TASK_REFINER_MODEL", os.getenv("AGENT_PLANNER_MODEL", "qwen/qwen3-vl-30b-a3b-instruct"))
_OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
_OR_BASE_URL = (os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") or "https://openrouter.ai/api/v1").rstrip("/")
_OR_URL = _OR_BASE_URL if _OR_BASE_URL.endswith("/chat/completions") else f"{_OR_BASE_URL}/chat/completions"
_OR_HEADERS = {
    "Authorization": f"Bearer {_OR_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://whiztant.com",
    "X-Title": "Whiztant",
}
_SUGGESTION_CACHE = {"key": "", "text": None}

# Content length threshold to classify a task as 'large' for dedicated panel
_TASK_LARGE_THRESHOLD = 400


def _tasks_path() -> Path:
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    # One-time migration from legacy %APPDATA%\Wiztant\tasks.json
    try:
        if not _TASKS_PATH.exists() and _LEGACY_TASKS_PATH.exists():
            _TASKS_PATH.write_bytes(_LEGACY_TASKS_PATH.read_bytes())
    except Exception:
        pass
    return _TASKS_PATH


def _load() -> dict:
    path = _tasks_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("tasks", [])
                    data.setdefault("history", [])
                    changed = False
                    normalized_tasks = []
                    for task in data.get("tasks", []):
                        if isinstance(task, dict):
                            before = dict(task)
                            normalized = _normalize_task_schema(task)
                            normalized_tasks.append(normalized)
                            if normalized != before:
                                changed = True
                    data["tasks"] = normalized_tasks
                    if changed:
                        _save(data)
                    return data
        except Exception:
            pass
    return {"tasks": [], "history": []}


def _save(data: dict) -> None:
    path = _tasks_path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def _new_id() -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"task_{ts}_{rand}"


def get_tasks() -> list:
    return _load().get("tasks", [])


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _history_entry(task: dict) -> dict:
    completed_at = task.get("completed_at") or datetime.now(timezone.utc).isoformat()
    return {
        "task_id": task.get("id", ""),
        "text": task.get("text", "").strip(),
        "source": task.get("source", "typed"),
        "created_at": task.get("created_at"),
        "completed_at": completed_at,
    }


def _upsert_history_entry(data: dict, task: dict) -> None:
    history = [entry for entry in data.setdefault("history", []) if entry.get("task_id") != task.get("id")]
    history.append(_history_entry(task))
    data["history"] = sorted(history, key=lambda entry: entry.get("completed_at", ""), reverse=True)


def _remove_history_entry(data: dict, task_id: str) -> None:
    data["history"] = [entry for entry in data.setdefault("history", []) if entry.get("task_id") != task_id]


def get_task_history(limit: Optional[int] = None) -> list:
    history = sorted(_load().get("history", []), key=lambda entry: entry.get("completed_at", ""), reverse=True)
    return history[:limit] if limit else history


def _suggestion_fallback(day_map: dict[str, list[str]], recent_days: list[str]) -> Optional[str]:
    phrases = Counter()
    originals: dict[str, str] = {}
    for day in recent_days:
        for text in day_map.get(day, []):
            cleaned = _normalize_space(text)
            if not cleaned:
                continue
            key = cleaned.lower()
            phrases[key] += 1
            originals.setdefault(key, cleaned)
    if not phrases:
        return None
    top = [originals[key] for key, _ in phrases.most_common(3)]
    if len(top) == 1:
        return f"Based on your last 10 days, you could focus on {top[0]} today."
    if len(top) == 2:
        return f"Based on your last 10 days, you could focus on {top[0]} and {top[1]} today."
    return f"Based on your last 10 days, you could focus on {top[0]}, {top[1]}, and {top[2]} today."


def _request_openrouter_text(system_prompt: str, user_prompt: str, max_tokens: int = 140) -> str:
    if not _OR_KEY:
        return ""
    try:
        response = requests.post(
            _OR_URL,
            headers=_OR_HEADERS,
            json={
                "model": _TASK_REFINER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            return "\n".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
        return str(content).strip()
    except Exception:
        return ""


def refine_task_text(task_text: str) -> str:
    cleaned = _normalize_space(task_text).strip(" .,-")
    if not cleaned:
        return ""
    refined = _request_openrouter_text(
        "You lightly refine a spoken task fragment for a task list. Preserve meaning, scope, and urgency. Remove filler words only. Do not add new details. Return only the refined task text.",
        cleaned,
        max_tokens=80,
    )
    refined = _normalize_space(refined).strip(" .,-")
    if not refined:
        return cleaned
    if len(refined) > max(len(cleaned) * 2, len(cleaned) + 40):
        return cleaned
    return refined


def get_daily_task_suggestion() -> Optional[str]:
    today_key = datetime.now().astimezone().date().isoformat()
    day_map: dict[str, list[str]] = defaultdict(list)
    for entry in get_task_history():
        completed_at = str(entry.get("completed_at", "") or "")
        text = _normalize_space(str(entry.get("text", "") or ""))
        if not completed_at or not text:
            continue
        day_key = completed_at[:10]
        if day_key >= today_key:
            continue
        day_map[day_key].append(text)
    distinct_days = sorted(day_map.keys())
    if len(distinct_days) < 10:
        return None
    recent_days = distinct_days[-10:]
    cache_key = json.dumps({day: day_map[day] for day in recent_days}, sort_keys=True)
    if _SUGGESTION_CACHE["key"] == cache_key:
        return _SUGGESTION_CACHE["text"]
    summary = "\n".join(f"{day}: {', '.join(day_map[day][:6])}" for day in recent_days)
    suggestion = _request_openrouter_text(
        "You write one short, plain-text daily task suggestion from the last 10 days of completed tasks. Keep it practical, concise, and grounded in the provided history. Do not mention the history explicitly. Return only one sentence.",
        summary,
        max_tokens=90,
    )
    suggestion = _normalize_space(suggestion).strip()
    if not suggestion:
        suggestion = _suggestion_fallback(day_map, recent_days)
    _SUGGESTION_CACHE["key"] = cache_key
    _SUGGESTION_CACHE["text"] = suggestion
    return suggestion


def get_task_snapshot(history_limit: int = 40) -> dict:
    return {
        "tasks": get_tasks(),
        "history": get_task_history(limit=history_limit),
        "suggestion": get_daily_task_suggestion(),
    }


def add_task(text: str, source: str = "typed", due_at: Optional[str] = None,
             parent_id: Optional[str] = None) -> dict:
    data = _load()
    task = _normalize_task_schema({
        "id": _new_id(),
        "text": text.strip(),
        "status": "pending",
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_at": due_at,
        "completed_at": None,
        "parent_id": parent_id,
    })
    data.setdefault("tasks", []).append(task)
    _save(data)
    _notify_overlay()
    return task


def get_yesterday_pending_summary() -> Optional[str]:
    try:
        now_local = datetime.now().astimezone()
        today_key = now_local.date().isoformat()
        yday_key = (now_local.date() - timedelta(days=1)).isoformat()
        tasks = get_tasks()
        y_pending: list[dict] = []
        for t in tasks:
            if t.get("status") == "done":
                continue
            created_at = str(t.get("created_at") or "")
            if not created_at:
                continue
            # created_at is UTC ISO; compare by YYYY-MM-DD prefix safely
            day_key = created_at[:10]
            if day_key == yday_key:
                y_pending.append(t)
        if not y_pending:
            return None
        y_pending_sorted = sorted(y_pending, key=lambda x: x.get("created_at", ""))
        count = len(y_pending_sorted)
        head = (y_pending_sorted[0].get("text") or "").strip()
        if count == 1:
            return f"Yesterday: {head}"
        return f"Yesterday: {head} (+{count-1} more)"
    except Exception:
        return None


def add_subtask(parent_id: str, text: str, source: str = "voice",
                due_at: Optional[str] = None) -> Optional[dict]:
    """Attach a new task as a subtask of parent_id. Returns None if the
    parent id is not present."""
    if not parent_id:
        return None
    data = _load()
    tasks = data.get("tasks", [])
    if not any(t.get("id") == parent_id for t in tasks):
        return None
    task = _normalize_task_schema({
        "id": _new_id(),
        "text": text.strip(),
        "status": "pending",
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_at": due_at,
        "completed_at": None,
        "parent_id": parent_id,
    })
    tasks.append(task)
    data["tasks"] = tasks
    _save(data)
    _notify_overlay()
    return task


def mark_done(task_id: str) -> Optional[dict]:
    data = _load()
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            task["status"] = "done"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            _upsert_history_entry(data, task)
            _save(data)
            _notify_overlay()
            return task
    return None


def mark_in_progress(task_id: str) -> Optional[dict]:
    """Mark a task as in-progress."""
    data = _load()
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            task["status"] = "in_progress"
            task["completed_at"] = None
            _save(data)
            _notify_overlay()
            return task
    return None


def delete_task(task_id: str) -> Optional[dict]:
    data = _load()
    tasks = data.get("tasks", [])
    for index, task in enumerate(tasks):
        if task.get("id") == task_id:
            removed = tasks.pop(index)
            _remove_history_entry(data, task_id)
            _save(data)
            _notify_overlay()
            return removed
    return None


def toggle_status(task_id: str) -> Optional[dict]:
    data = _load()
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            if task["status"] == "done":
                task["status"] = "pending"
                task["completed_at"] = None
                _remove_history_entry(data, task_id)
            else:
                task["status"] = "done"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()
                _upsert_history_entry(data, task)
            _save(data)
            _notify_overlay()
            return task
    return None


def edit_task_text(task_id: str, new_text: str) -> Optional[dict]:
    """Update a task's text/title in-place."""
    data = _load()
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["text"] = new_text.strip()
            _save(data)
            _notify_overlay()
            return task
    return None


def edit_task_due(task_id: str, new_due_at: str) -> Optional[dict]:
    """Update a task's due date/time in-place."""
    data = _load()
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["due_at"] = new_due_at
            _save(data)
            return task
    return None


def edit_task_fields(task_id: str, fields: dict) -> Optional[dict]:
    """Update arbitrary task fields in-place."""
    data = _load()
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            old_text = task.get("text", "")
            if "text" in fields:
                task["text"] = str(fields["text"]).strip()
            if "content" in fields:
                task["content"] = str(fields["content"]).strip() if fields["content"] is not None else None
            if "due_at" in fields:
                task["due_at"] = fields["due_at"] if fields["due_at"] is not None else None
            if "task_type" in fields:
                task["task_type"] = fields["task_type"] if fields["task_type"] in ("large", "small") else None
            if "status" in fields:
                task["status"] = fields["status"] if fields["status"] in ("pending", "done") else task.get("status", "pending")
            if "completed_at" in fields:
                task["completed_at"] = fields["completed_at"]
            _normalize_task_schema(task)
            _save(data)
            _notify_overlay()

            return task
    return None


def save_session_as_task(title: str, prompt_content: str) -> dict:
    """Create a task capturing a session transcript/content body.

    - text: short title/summary (derived from recent user message)
    - content: full prompt/session body
    - task_type: 'large' if content length > threshold, else 'small'
    """
    title = _normalize_space(title).strip(" .,-") or "Session continuation"
    content = str(prompt_content or "").strip()
    task_type = "large" if len(content) > _TASK_LARGE_THRESHOLD else "small"

    data = _load()
    task = _normalize_task_schema({
        "id": _new_id(),
        "text": title,
        "status": "pending",
        "source": "typed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_at": None,
        "completed_at": None,
        "parent_id": None,
        "content": content,
        "task_type": task_type,
    })
    data.setdefault("tasks", []).append(task)
    _save(data)
    _notify_overlay()
    return task


def get_due_today_undone() -> list[dict]:
    today_key = datetime.now().astimezone().date().isoformat()
    due_today = []
    for task in get_tasks():
        _normalize_task_schema(task)
        if task.get("status") == "done" or task.get("failed"):
            continue
        if is_snoozed(task):
            continue
        due_at = str(task.get("due_at") or "")
        if not due_at:
            continue
        try:
            due_local = datetime.fromisoformat(due_at.replace("Z", "+00:00")).astimezone()
        except Exception:
            continue
        if due_local.date().isoformat() == today_key:
            due_today.append(task)
    return due_today


def get_carried_over_undone() -> list[dict]:
    carried = []
    for task in get_tasks():
        _normalize_task_schema(task)
        if task.get("status") == "done" or task.get("failed"):
            continue
        if task.get("carried_over"):
            carried.append(task)
    return carried


def is_snoozed(task: dict) -> bool:
    """Check if a task has an active snooze (snoozed_until is set and in the future)."""
    snoozed_until = task.get("snoozed_until")
    if not snoozed_until:
        return False
    try:
        snooze_dt = datetime.fromisoformat(str(snoozed_until).replace("Z", "+00:00"))
        return snooze_dt > datetime.now(timezone.utc)
    except Exception:
        return False


def snooze_task(task_id: str, minutes: int) -> Optional[dict]:
    """Snooze a task for the given number of minutes. Returns the updated task or None."""
    data = _load()
    snooze_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["snoozed_until"] = snooze_until.isoformat()
            _save(data)
            _notify_overlay()
            return task
    return None


def clear_snooze(task_id: str) -> Optional[dict]:
    """Remove the snooze from a task. Returns the updated task or None."""
    data = _load()
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["snoozed_until"] = None
            _save(data)
            _notify_overlay()
            return task
    return None


def get_snooze_presets() -> list[int]:
    """Return default snooze preset durations in minutes."""
    return [15, 30, 60, 1440]


def get_due_soon(minutes: int = 30) -> list[dict]:
    """Return pending tasks that are due within the next N minutes but not yet overdue."""
    now_utc = datetime.now(timezone.utc)
    soon = now_utc + timedelta(minutes=minutes)
    due_soon = []
    for task in get_tasks():
        _normalize_task_schema(task)
        if task.get("status") == "done" or task.get("failed"):
            continue
        if is_snoozed(task):
            continue
        due_at = task.get("due_at")
        if not due_at:
            continue
        try:
            due_dt = datetime.fromisoformat(str(due_at).replace("Z", "+00:00"))
            if now_utc <= due_dt <= soon:
                due_soon.append(task)
        except Exception:
            continue
    return due_soon


def reschedule_to_tomorrow(task_id: str) -> bool:
    data = _load()
    tomorrow = (datetime.now().astimezone() + timedelta(days=1)).date()
    for task in data.get("tasks", []):
        _normalize_task_schema(task)
        if task.get("id") != task_id:
            continue
        due_at = task.get("due_at")
        hour = 18
        minute = 0
        if due_at:
            try:
                due_local = datetime.fromisoformat(str(due_at).replace("Z", "+00:00")).astimezone()
                hour = due_local.hour
                minute = due_local.minute
            except Exception:
                pass
        next_due = datetime.now().astimezone().replace(
            year=tomorrow.year,
            month=tomorrow.month,
            day=tomorrow.day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        task["due_at"] = next_due.astimezone(timezone.utc).isoformat()
        task["carried_over"] = True
        task["failed"] = False
        _save(data)
        _notify_overlay()
        return True
    return False


def mark_failed(task_id: str) -> bool:
    data = _load()
    for task in data.get("tasks", []):
        _normalize_task_schema(task)
        if task.get("id") != task_id:
            continue
        task["failed"] = True
        task["carried_over"] = False
        _save(data)
        _notify_overlay()
        return True
    return False


_ADD_PATTERNS = [
    # Explicit prefix: "this is a task ..." / "this is task ..."
    re.compile(r"^(?:this\s+is\s+(?:a\s+|an\s+|the\s+)?task)\s*[:\-,]?\s+(.+)$", re.IGNORECASE),
    # "add/create/new/make/set up (a/an/the) task (to|for|:|-)? X"
    re.compile(r"^(?:add|create|new|make|set\s+up)\s+(?:a\s+|an\s+|the\s+)?task(?:\s*[:\-,]|\s+for|\s+to)?\s+(.+)$", re.IGNORECASE),
    # "add X as a task"
    re.compile(r"^(?:add|create|new|make|set\s+up)\s+(.+?)\s+(?:as|to)\s+(?:a\s+)?task$", re.IGNORECASE),
    # "task: X" / "task - X" / "todo: X" — requires explicit separator to avoid false positives
    re.compile(r"^(?:task|todo|to\s+do)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]

# Implicit phrasing ("I need to ...", "remind me to ...") is intentionally
# NOT treated as a task command — those should paste normally. The user must
# prefix with "task ..." / "this is a task ..." / "add task ..." explicitly.
_IMPLICIT_ADD_PATTERNS: list[re.Pattern] = []

_DONE_PATTERNS = [
    re.compile(r"^(?:done|complete|finish|mark\s+done)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^mark\s+(.+?)\s+as\s+(?:done|complete|finished)$", re.IGNORECASE),
    re.compile(r"^(?:set|change)\s+(.+?)\s+(?:to|as)\s+(?:done|complete|finished)$", re.IGNORECASE),
]

_DELETE_PATTERNS = [
    re.compile(r"^(?:delete|remove)\s+task\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:delete|remove)\s+(.+)$", re.IGNORECASE),
]

_IN_PROGRESS_PATTERNS = [
    re.compile(r"^(?:start|begin|work\s+on|mark\s+in\s+progress|set\s+to\s+in\s+progress)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^mark\s+(.+?)\s+as\s+(?:in\s+progress|started|active)$", re.IGNORECASE),
    re.compile(r"^(?:set|change)\s+(.+?)\s+(?:to|as)\s+(?:in\s+progress|started|active)$", re.IGNORECASE),
]

_LIST_PATTERNS = [
    re.compile(r"^(?:list|show|read)\s+(?:my\s+)?tasks?$", re.IGNORECASE),
]

# Voice editing: "change task X to Y", "rename task X to Y"
_EDIT_PATTERNS = [
    re.compile(r"^(?:change|rename|update|edit)\s+(?:task\s+)?(.+?)\s+(?:to|into|as)\s+(.+)$", re.IGNORECASE),
]

# Voice reschedule: "move task X to 3pm", "reschedule task X for tomorrow at 10"
_RESCHEDULE_PATTERNS = [
    re.compile(r"^(?:move|reschedule|push|delay)\s+(?:task\s+)?(.+?)\s+(?:to|for|at|by)\s+(.+)$", re.IGNORECASE),
]

_DUE_TIME_PATTERNS = [
    # (today/tomorrow) (at) HH(:MM) (am/pm)  — most specific first
    re.compile(
        r"\b((?:today|tomorrow))\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        re.IGNORECASE,
    ),
    # by/before/at (today/tomorrow) HH(:MM) (am/pm)
    re.compile(
        r"\b(?:by|before|at)\s+((?:today|tomorrow)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        re.IGNORECASE,
    ),
    # bare time HH(:MM) am/pm
    re.compile(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        re.IGNORECASE,
    ),
]

_DAY_ONLY_PATTERNS = [
    re.compile(r"\b(today|tomorrow)\b", re.IGNORECASE),
]

_WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "weds": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_WEEKDAY_PATTERN = re.compile(
    r"\b(?:on\s+|next\s+)?(monday|mon|tuesday|tue|tues|wednesday|wed|weds|thursday|thu|thurs|friday|fri|saturday|sat|sunday|sun)\b",
    re.IGNORECASE,
)


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def _find_best_task_match(query: str, tasks: list) -> Optional[dict]:
    query_l = query.lower().strip()
    # Strip common filler prefixes that don't help matching
    for prefix in ("working on ", "the ", "my ", "this ", "that "):
        if query_l.startswith(prefix):
            query_l = query_l[len(prefix):]
    best = None
    best_score = 0.0
    for task in tasks:
        text = task.get("text", "").lower()
        max_len = max(len(query_l), len(text))
        if max_len == 0:
            continue
        # Substring match: if query is contained in task text, strong bonus
        if query_l in text:
            score = 0.6 + 0.4 * (len(query_l) / len(text))
        else:
            dist = _levenshtein(query_l, text)
            score = 1.0 - dist / max_len
        if score > best_score:
            best_score = score
            best = task
    if best_score >= 0.70:
        return best
    return None


def _strip_match(text: str, match: re.Match) -> str:
    cleaned = f"{text[:match.start()]} {text[match.end():]}"
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def _parse_due_time(task_text: str) -> tuple[str, Optional[str]]:
    now = datetime.now().astimezone()
    text = task_text.strip()

    # 1. Time-based patterns (includes today/tomorrow + time)
    # Find the leftmost match across all patterns so that e.g.
    # "tomorrow at 3pm" wins over the bare "3pm" inside it.
    best_match = None
    for pattern in _DUE_TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            if best_match is None or match.start() < best_match.start():
                best_match = match

    if best_match:
        match = best_match
        groups = match.groups()
        # Patterns 1 & 2 have 4 groups: day_hint, hour, minute, am_pm
        # Pattern 3 (bare time) has 3 groups: hour, minute, am_pm
        if len(groups) == 4:
            day_hint = (groups[0] or "").strip().lower()
            hour = int(groups[1])
            minute = int(groups[2] or "0")
            am_pm = (groups[3] or "").lower()
        else:
            day_hint = ""
            hour = int(groups[0])
            minute = int(groups[1] or "0")
            am_pm = (groups[2] or "").lower()

        if hour > 23 or minute > 59:
            return text, None

        if am_pm:
            if hour > 12 or hour == 0:
                return text, None
            if am_pm == "pm" and hour != 12:
                hour += 12
            if am_pm == "am" and hour == 12:
                hour = 0

        due_date = now.date()
        if "tomorrow" in day_hint:
            due_date = due_date + timedelta(days=1)

        due_local = now.replace(
            year=due_date.year,
            month=due_date.month,
            day=due_date.day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        if not day_hint and due_local <= now:
            due_local = due_local + timedelta(days=1)

        cleaned = _strip_match(text, match)
        if cleaned:
            return cleaned, due_local.astimezone(timezone.utc).isoformat()

    # 2. Bare day patterns (today / tomorrow) without explicit time → default noon
    for pattern in _DAY_ONLY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        day_hint = match.group(1).lower()
        due_date = now.date()
        if "tomorrow" in day_hint:
            due_date = due_date + timedelta(days=1)
        due_local = now.replace(
            year=due_date.year,
            month=due_date.month,
            day=due_date.day,
            hour=12,
            minute=0,
            second=0,
            microsecond=0,
        )
        if due_local <= now:
            due_local = due_local + timedelta(days=1)
        cleaned = _strip_match(text, match)
        if cleaned:
            return cleaned, due_local.astimezone(timezone.utc).isoformat()

    # 3. Weekday patterns (Monday, next Tuesday, etc.)
    match = _WEEKDAY_PATTERN.search(text)
    if match:
        weekday_name = match.group(1).lower()
        target_dow = _WEEKDAY_MAP.get(weekday_name)
        if target_dow is not None:
            today_dow = now.weekday()
            days_ahead = (target_dow - today_dow) % 7
            if days_ahead == 0:
                days_ahead = 7  # if today, assume next week
            due_date = now.date() + timedelta(days=days_ahead)
            due_local = now.replace(
                year=due_date.year,
                month=due_date.month,
                day=due_date.day,
                hour=12,
                minute=0,
                second=0,
                microsecond=0,
            )
            cleaned = _strip_match(text, match)
            if cleaned:
                return cleaned, due_local.astimezone(timezone.utc).isoformat()

    return text, None


def parse_due_time(text: str) -> tuple[str, Optional[str]]:
    """Public wrapper — returns (cleaned_text, due_at_iso_or_None)."""
    return _parse_due_time(text)


# Matches "separately" plus common Whisper mistranscriptions of it.
_SEPARATELY_PATTERN = re.compile(
    r"\b("
    r"separately|separate\s*ly|separate\s+lee|"
    r"(?:as\s+|in\s+|into\s+)?separate\s+tasks?|"
    r"sabre\s*tri|saver\s*tree|sever\s*ately|sep[ae]r[ae]t[ei]ly"
    r")\b",
    re.IGNORECASE,
)


def _count_due_markers(text: str) -> int:
    """Count distinct time-of-day markers (e.g., 'by 6pm', 'tomorrow at 10')."""
    spans: list[tuple[int, int]] = []
    for pattern in _DUE_TIME_PATTERNS:
        for match in pattern.finditer(text):
            spans.append(match.span())
    # De-dupe overlapping spans so two patterns matching the same phrase count once.
    spans.sort()
    count = 0
    last_end = -1
    for start, end in spans:
        if start >= last_end:
            count += 1
            last_end = end
    return count


def split_separately(text: str) -> Optional[list[str]]:
    """
    Split a single utterance into multiple task fragments when the user
    either:
      - says "separately" (or a Whisper mistranscription like "sabretri"), OR
      - packs ≥2 distinct due-time markers into one utterance
        (e.g., "...by 7 PM tomorrow. Finish the oil website by 12 PM tomorrow").

    Splits on ' and ' / ';' / '.' sentence boundaries, falling back to commas.
    Returns a list of ≥2 fragments when a split is warranted, otherwise None.
    """
    if not text:
        return None

    has_marker = bool(_SEPARATELY_PATTERN.search(text))
    multiple_due = _count_due_markers(text) >= 2
    if not has_marker and not multiple_due:
        return None

    cleaned = _SEPARATELY_PATTERN.sub(" ", text) if has_marker else text
    cleaned = _normalize_space(cleaned).strip(" ,.-;:")
    if not cleaned:
        return None

    # Step 1: strong boundaries only — sentence terminators / semicolons.
    chunks = [c for c in re.split(r"\s*[;.]\s*", cleaned) if c.strip()]
    if not chunks:
        chunks = [cleaned]

    # Step 2: for each chunk, only sub-split on ' and ' if it STILL contains
    # ≥2 due markers (otherwise "and" is part of one task, e.g.
    # "integrate with Zuba base and all tasks by 12 PM").
    expanded: list[str] = []
    for chunk in chunks:
        if _count_due_markers(chunk) >= 2:
            expanded.extend(
                part for part in re.split(r"\s+and\s+", chunk, flags=re.IGNORECASE)
                if part.strip()
            )
        else:
            expanded.append(chunk)

    # Step 3: if we still have one chunk but an explicit marker was present,
    # fall back to comma split so users saying "X, Y, Z separately" still splits.
    if len(expanded) < 2 and has_marker:
        expanded = [c for c in re.split(r"\s*,\s*", cleaned) if c.strip()]

    result: list[str] = []
    for part in expanded:
        fragment = _normalize_space(part).strip(" ,.-;:")
        if fragment and len(fragment.split()) >= 2:
            result.append(fragment)

    return result if len(result) >= 2 else None


def default_noon_due_at() -> str:
    """12:00 local time today, or tomorrow if already past noon. Returns UTC ISO."""
    now = datetime.now().astimezone()
    noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    if noon <= now:
        noon = noon + timedelta(days=1)
    return noon.astimezone(timezone.utc).isoformat()


def _extract_task_candidate(transcript: str) -> Optional[str]:
    # Strip leading punctuation that Whisper sometimes emits (",", ".", etc.)
    text = _normalize_space(transcript).lstrip(" ,.-:;")
    for pattern in _ADD_PATTERNS:
        match = pattern.match(text)
        if match:
            candidate = match.group(1).strip(" ,.-:;")
            if candidate:
                return candidate
    return None


def parse_task_command(transcript: str) -> Optional[dict]:
    """
    Parse a voice transcript for a task command.

    Returns:
      {"action": "add", "text": "buy milk", "due_at": "..."}
      {"action": "done", "task_id": "task_xxx", "text": "buy milk"}
      {"action": "delete", "task_id": "task_xxx", "text": "buy milk"}
      {"action": "in_progress", "task_id": "task_xxx", "text": "buy milk"}
      {"action": "list"}
    """
    t = _normalize_space(transcript)
    for pattern in _LIST_PATTERNS:
        if pattern.match(t):
            return {"action": "list"}
    for action, patterns in (("done", _DONE_PATTERNS), ("delete", _DELETE_PATTERNS), ("in_progress", _IN_PROGRESS_PATTERNS)):
        for pattern in patterns:
            match = pattern.match(t)
            if not match:
                continue
            query = match.group(1).strip()
            tasks = get_tasks()
            matched = _find_best_task_match(query, tasks)
            if matched:
                return {"action": action, "task_id": matched["id"], "text": matched["text"]}
            return {"action": action, "text": query, "task_id": None}

    # Voice editing: "change task X to Y"
    for pattern in _EDIT_PATTERNS:
        match = pattern.match(t)
        if match:
            query = match.group(1).strip()
            new_text = match.group(2).strip()
            tasks = get_tasks()
            matched = _find_best_task_match(query, tasks)
            if matched:
                return {"action": "edit", "task_id": matched["id"], "text": new_text, "old_text": matched["text"]}
            return {"action": "edit", "text": new_text, "query": query, "task_id": None}

    # Voice reschedule: "move task X to 3pm"
    for pattern in _RESCHEDULE_PATTERNS:
        match = pattern.match(t)
        if match:
            query = match.group(1).strip()
            time_phrase = match.group(2).strip()
            tasks = get_tasks()
            matched = _find_best_task_match(query, tasks)
            _, due_at = _parse_due_time(f"by {time_phrase}")
            if matched:
                return {"action": "reschedule", "task_id": matched["id"], "due_at": due_at, "text": matched["text"]}
            return {"action": "reschedule", "query": query, "due_at": due_at, "task_id": None}

    candidate = _extract_task_candidate(t)
    if candidate:
        task_text, due_at = _parse_due_time(candidate)
        task_text = refine_task_text(task_text)
        if task_text:
            return {"action": "add", "text": task_text, "due_at": due_at, "raw_text": candidate}
    return None
