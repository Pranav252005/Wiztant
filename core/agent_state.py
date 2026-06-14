"""
core/agent_state.py — Session state, step budget, pause/resume for the Three-Brain Agent.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("core.agent_state")

# =============================================================
#  CONSTANTS
# =============================================================

AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "100"))
BUDGET_WARNING_1 = int(os.getenv("AGENT_BUDGET_WARN_1", "80"))
BUDGET_WARNING_2 = int(os.getenv("AGENT_BUDGET_WARN_2", "90"))


class SessionStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class Milestone:
    step_id: int
    title: str
    prompt: str = ""
    expected_ide_actions: int = 1
    verification_cues: List[str] = field(default_factory=list)
    status: str = "pending"  # pending | active | completed | failed


@dataclass
class AgentPlan:
    plan_id: str = ""
    detected_tool: str = "unknown"
    tool_confidence: float = 0.0
    estimated_steps: int = 0
    milestones: List[Milestone] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "detected_tool": self.detected_tool,
            "tool_confidence": self.tool_confidence,
            "estimated_steps": self.estimated_steps,
            "milestones": [asdict(m) for m in self.milestones],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentPlan":
        milestones = [Milestone(**m) for m in data.get("milestones", [])]
        return cls(
            plan_id=data.get("plan_id", ""),
            detected_tool=data.get("detected_tool", "unknown"),
            tool_confidence=data.get("tool_confidence", 0.0),
            estimated_steps=data.get("estimated_steps", 0),
            milestones=milestones,
        )


@dataclass
class PauseSnapshot:
    timestamp: str = ""
    screenshot_b64: str = ""
    steps_used: int = 0
    current_step: int = 0
    step_progress: str = ""
    ide_state: str = ""
    completed_files: List[str] = field(default_factory=list)
    pending_milestones: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: SessionStatus = SessionStatus.IDLE
    plan: Optional[AgentPlan] = None
    steps_used: float = 0.0
    steps_budget: int = AGENT_MAX_STEPS
    current_step: int = 0
    current_action: str = ""
    pause_snapshot: Optional[PauseSnapshot] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "steps_used": self.steps_used,
            "steps_budget": self.steps_budget,
            "current_step": self.current_step,
            "current_action": self.current_action,
            "pause_snapshot": self.pause_snapshot.to_dict() if self.pause_snapshot else None,
            "execution_log": self.execution_log,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def log_action(self, action_type: str, details: Dict[str, Any]) -> None:
        """Append an action to the execution log."""
        self.execution_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": details,
        })
        self.updated_at = datetime.now(timezone.utc).isoformat()


# =============================================================
#  STATE MACHINE
# =============================================================

class AgentStateMachine:
    """Manages agent session lifecycle and step budget."""

    def __init__(self, session: Optional[AgentSession] = None) -> None:
        self.session = session or AgentSession()
        self._paused = False
        self._budget_warning_issued: set[int] = set()

    # -- Transitions --

    def start_planning(self) -> None:
        self.session.status = SessionStatus.PLANNING
        self._log_transition("planning")

    def start_execution(self) -> None:
        self.session.status = SessionStatus.RUNNING
        self._log_transition("running")

    def pause(self, reason: str = "user_request") -> None:
        self._paused = True
        self.session.status = SessionStatus.PAUSED
        self.session.pause_snapshot = PauseSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            steps_used=self.session.steps_used,
            current_step=self.session.current_step,
            ide_state=self.session.current_action,
        )
        log.info("Session %s paused: %s", self.session.session_id, reason)

    def resume(self) -> None:
        self._paused = False
        self.session.status = SessionStatus.RUNNING
        self.session.pause_snapshot = None
        log.info("Session %s resumed", self.session.session_id)

    def complete(self, result: str = "") -> None:
        self.session.status = SessionStatus.COMPLETED
        self.session.current_action = result
        log.info("Session %s completed", self.session.session_id)

    def fail(self, reason: str = "") -> None:
        self.session.status = SessionStatus.FAILED
        self.session.current_action = reason
        log.info("Session %s failed: %s", self.session.session_id, reason)

    def abort(self, reason: str = "") -> None:
        self.session.status = SessionStatus.ABORTED
        self.session.current_action = reason
        log.info("Session %s aborted: %s", self.session.session_id, reason)

    # -- Budget --

    def consume_steps(self, cost: float) -> None:
        """Consume step budget. Raises on over-budget."""
        self.session.steps_used += cost
        self._check_budget_warnings()
        if self.session.steps_used >= self.session.steps_budget:
            raise StepBudgetExceeded(
                f"Step budget exhausted: {self.session.steps_used}/{self.session.steps_budget}"
            )

    def _check_budget_warnings(self) -> None:
        used = self.session.steps_used
        budget = self.session.steps_budget
        pct = (used / budget) * 100 if budget else 0

        if pct >= BUDGET_WARNING_2 and BUDGET_WARNING_2 not in self._budget_warning_issued:
            self._budget_warning_issued.add(BUDGET_WARNING_2)
            log.warning("CRITICAL: %s/%s steps used (%.0f%%)", used, budget, pct)
        elif pct >= BUDGET_WARNING_1 and BUDGET_WARNING_1 not in self._budget_warning_issued:
            self._budget_warning_issued.add(BUDGET_WARNING_1)
            log.warning("WARNING: %s/%s steps used (%.0f%%)", used, budget, pct)

    @property
    def steps_remaining(self) -> float:
        return max(0.0, self.session.steps_budget - self.session.steps_used)

    @property
    def is_paused(self) -> bool:
        return self._paused or self.session.status == SessionStatus.PAUSED

    @property
    def is_running(self) -> bool:
        return self.session.status == SessionStatus.RUNNING

    # -- Persistence --

    def save(self, path: Optional[Path] = None) -> Path:
        """Save session state to disk for crash recovery."""
        if path is None:
            base = Path(__file__).parent.parent / "memory" / "agent_sessions"
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"session_{self.session.session_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.session.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> "AgentStateMachine":
        """Restore session state from disk."""
        data = json.loads(path.read_text(encoding="utf-8"))
        session = AgentSession(**{k: v for k, v in data.items() if k in AgentSession.__dataclass_fields__})
        if data.get("plan"):
            session.plan = AgentPlan.from_dict(data["plan"])
        if data.get("pause_snapshot"):
            session.pause_snapshot = PauseSnapshot(**data["pause_snapshot"])
        session.status = SessionStatus(data.get("status", "idle"))
        return cls(session)

    def _log_transition(self, to_state: str) -> None:
        log.info("Session %s → %s", self.session.session_id, to_state)


class StepBudgetExceeded(Exception):
    """Raised when the agent exceeds its step budget."""
