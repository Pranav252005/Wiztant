"""
Whiztant core/agent_task_queue.py — Background agent task data model and queue utilities.

AgentTask is the unit of work for the background agent system.
Each task tracks its lifecycle from queued → executing → complete/failed.
"""

import uuid
import time
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


# ── Persistent task log ──────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TASKS_LOG_PATH = _PROJECT_ROOT / "data" / "agent_tasks.json"


@dataclass
class AgentTask:
    """Single background agent task with full lifecycle tracking."""

    task_id: str
    description: str
    status: str                                 # queued | starting | executing | complete | failed | cancelled
    created_at: datetime

    # Task classification
    task_type: str = "browser"              # browser | registry | settings | game | system | nvidia

    # Completion
    completed_at: Optional[datetime] = None

    # Browser context (set when task starts executing)
    browser_pid: Optional[int] = None
    browser_handle: Optional[int] = None

    # Result payload
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Progress
    current_step: int = 0
    total_steps: int = 0
    progress_percent: int = 0

    def to_dict(self) -> dict:
        """Serialize for JSON storage and UI display."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "task_type": self.task_type,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percent": self.progress_percent,
            "result": self.result,
            "error": self.error,
        }

    @staticmethod
    def from_dict(d: dict) -> "AgentTask":
        return AgentTask(
            task_id=d["task_id"],
            description=d["description"],
            status=d["status"],
            task_type=d.get("task_type", "browser"),
            created_at=datetime.fromisoformat(d["created_at"]),
            completed_at=datetime.fromisoformat(d["completed_at"]) if d.get("completed_at") else None,
            current_step=d.get("current_step", 0),
            total_steps=d.get("total_steps", 0),
            progress_percent=d.get("progress_percent", 0),
            result=d.get("result"),
            error=d.get("error"),
        )

    @property
    def elapsed_seconds(self) -> float:
        end = self.completed_at or datetime.now()
        return (end - self.created_at).total_seconds()

    @property
    def progress_label(self) -> str:
        if self.status == "queued":
            return "Queued"
        if self.status == "starting":
            return "Starting..."
        if self.status == "executing":
            if self.total_steps > 0:
                return f"Step {self.current_step}/{self.total_steps}"
            return f"Step {self.current_step}"
        if self.status == "complete":
            return "Done"
        if self.status == "failed":
            return f"Failed: {(self.error or 'unknown')[:40]}"
        if self.status == "cancelled":
            return "Cancelled"
        return self.status.capitalize()


def generate_task_id() -> str:
    """Generate a unique, human-readable task ID."""
    return f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"


# ── Persistent log helpers ───────────────────────────────────────────────────

def save_task_to_log(task: AgentTask) -> None:
    """Append or update a task in the persistent log file."""
    _TASKS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tasks = load_task_log()
    # Replace existing entry or append
    tasks = [t for t in tasks if t["task_id"] != task.task_id]
    tasks.append(task.to_dict())
    # Keep only the last 100 tasks
    tasks = tasks[-100:]
    _TASKS_LOG_PATH.write_text(json.dumps(tasks, indent=2), encoding="utf-8")


def load_task_log() -> List[dict]:
    """Load the persistent task log. Returns empty list if missing or corrupt."""
    if not _TASKS_LOG_PATH.exists():
        return []
    try:
        return json.loads(_TASKS_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
