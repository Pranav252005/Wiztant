"""Phase Engine state machine for Agent v2."""

from __future__ import annotations

import asyncio
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

from core.agent_v2.models import Layer, MasterPlan, Phase, Subphase
from core.agent_v2.checkpoint import git_checkpoint


class EngineState(Enum):
    IDLE = auto()
    PLANNING = auto()
    STAGING = auto()
    VERIFYING = auto()
    CHECKPOINT = auto()
    PAUSED = auto()
    DONE = auto()
    FAILED = auto()


class PhaseEngine:
    """Executes one subphase at a time."""

    def __init__(self, plan: MasterPlan) -> None:
        self.plan = plan
        self.state = EngineState.IDLE
        self.current_layer: Optional[Layer] = None
        self.current_phase: Optional[Phase] = None
        self.current_subphase: Optional[Subphase] = None
        self._listeners: list[Callable[[str, dict], None]] = []
        self._paused = False

    def add_listener(self, fn: Callable[[str, dict], None]) -> None:
        self._listeners.append(fn)

    def _emit(self, event: str, payload: dict) -> None:
        for fn in self._listeners:
            try:
                fn(event, payload)
            except Exception:
                pass

    def start(self) -> None:
        if self.state != EngineState.IDLE:
            raise RuntimeError("Engine already started")
        self.state = EngineState.PLANNING
        self._emit("agent.phase_start", {"plan_id": self.plan.project_id, "layer": None, "phase": None})
        self.state = EngineState.STAGING
        self._advance_pointer()

    def _advance_pointer(self) -> None:
        """Set current_layer/phase/subphase to the next pending item."""
        for layer in self.plan.layers:
            for phase in layer.phases:
                for sub in phase.subphases:
                    if sub.status == "pending":
                        self.current_layer = layer
                        self.current_phase = phase
                        self.current_subphase = sub
                        self.plan.current_layer_id = layer.id
                        self.plan.current_phase_id = phase.id
                        self.plan.current_subphase_id = sub.id
                        return
        self.current_layer = None
        self.current_phase = None
        self.current_subphase = None

    def advance(self) -> None:
        """Complete current subphase and move to next."""
        if self._paused:
            self.state = EngineState.PAUSED
            return

        if self.current_subphase:
            self._complete_subphase(self.current_subphase)
            self._emit("agent.step_complete", {
                "plan_id": self.plan.project_id,
                "subphase_id": self.current_subphase.id,
            })

        self._advance_pointer()
        if self.current_subphase is None:
            self.state = EngineState.DONE
            self._emit("agent.phase_start", {"plan_id": self.plan.project_id, "status": "completed"})
            git_checkpoint(Path(self.plan.project_path), f"wip(agent): {self.plan.project_id} — all layers complete")
        else:
            self.state = EngineState.STAGING
            self._emit("agent.phase_start", {
                "plan_id": self.plan.project_id,
                "layer": self.current_layer.id if self.current_layer else None,
                "phase": self.current_phase.id if self.current_phase else None,
                "subphase": self.current_subphase.id,
            })

    def _complete_subphase(self, sub: Subphase) -> None:
        sub.status = "done"
        if self.current_phase and all(s.status == "done" for s in self.current_phase.subphases):
            self.current_phase.status = "done"
            msg = f"wip(agent): {self.current_layer.id}-{self.current_phase.id} — {self.current_phase.name}"
            git_checkpoint(Path(self.plan.project_path), msg)
        if self.current_layer and all(p.status == "done" for p in self.current_layer.phases):
            self.current_layer.status = "done"
            self._emit("agent.needs_approval", {
                "plan_id": self.plan.project_id,
                "message": f"{self.current_layer.name} complete. Approve next layer?",
            })

    def pause(self) -> None:
        self._paused = True
        self.state = EngineState.PAUSED
        self._emit("agent.limit_hit", {"plan_id": self.plan.project_id, "reason": "user_paused"})

    def resume(self) -> None:
        self._paused = False
        self.state = EngineState.STAGING
        self._emit("agent.phase_start", {"plan_id": self.plan.project_id, "status": "resumed"})

    async def run_verification(self, sub: Subphase) -> tuple[bool, Optional[str]]:
        """Run the verification command for a subphase. Returns (ok, error)."""
        self.state = EngineState.VERIFYING
        v = sub.verification
        if v.get("type") == "tsc":
            cmd = v.get("command", "npx tsc --noEmit")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.plan.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            ok = proc.returncode == 0
            return ok, (stderr.decode() if stderr else None)
        if v.get("type") == "curl":
            cmd = v.get("command", "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.plan.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            code = stdout.decode().strip()
            ok = code.startswith("2")
            return ok, f"HTTP {code}"
        return True, None
