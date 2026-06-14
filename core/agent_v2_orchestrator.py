"""core/agent_v2_orchestrator.py — Workflow Copilot Orchestrator.

Main entry point for Workflow Mode. Receives a preset/intent from the overlay,
resolves it into a WorkflowPlan, executes steps via WorkflowRuntime, handles
decision gates, and delivers a summarized result back to the user.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

from platforms.factory import get_system_access, get_virtual_desktop
from core.ws_bridge import broadcast_sync
from core.workflow_runtime import WorkflowRuntime, WorkflowPlan, WorkflowStep
from core.workflow_templates import TemplateRegistry
from core.workflow_gates import GateManager
from core.workflow_result import WorkflowResult

log = logging.getLogger("core.agent_v2_orchestrator")


class WorkflowOrchestrator:
    """Orchestrates workflow execution from intent to result delivery."""

    def __init__(self) -> None:
        self._registry = TemplateRegistry()
        self.gate_manager = GateManager()
        self._result_deliverer = WorkflowResult()
        self._running = False
        self._paused = False
        self._origin_desktop: Optional[str] = None
        self._agent_desktop: Optional[str] = None

    def initiate(self, preset_id: str, params: Dict[str, Any]) -> str:
        """Start a workflow from a preset ID and user parameters."""
        self._running = True
        self._paused = False

        log.info("Workflow initiate: preset=%s params=%s", preset_id, params)

        # Resolve plan
        try:
            plan = self._registry.resolve(preset_id, params)
        except Exception as e:
            log.error("Plan resolution failed: %s", e)
            plan = self._fallback_plan(str(e))

        # Broadcast start
        self._broadcast("workflow/started", {
            "preset_id": preset_id,
            "intent": plan.intent,
            "total_steps": len(plan.steps),
            "apps_required": plan.apps_required,
        })

        # Save original window focus
        original_window = self._save_focus()

        # Enter isolated workspace (virtual desktop if available)
        self._enter_workspace()

        try:
            result = self._execute_plan(plan)
        except Exception as e:
            log.error("Workflow execution failed: %s\n%s", e, traceback.format_exc())
            result = f"Workflow failed: {e}"
            self._broadcast("workflow/error", {"error": str(e)})
        finally:
            # Always return to origin desktop and cleanup
            self._exit_workspace()
            self._restore_focus(original_window)
            self._running = False

        # Summarize and deliver
        try:
            summary = self._result_deliverer.summarize(self._get_action_log())
        except Exception as e:
            log.error("Result summarization failed: %s", e)
            summary = result

        self._deliver_result(summary)
        self._broadcast("workflow/completed", {"summary": summary})

        return summary

    def pause(self, reason: str = "user_request") -> None:
        """Pause the current workflow."""
        self._paused = True
        self._broadcast("workflow/paused", {"reason": reason})

    def resume(self) -> None:
        """Resume a paused workflow."""
        self._paused = False
        self._broadcast("workflow/resumed", {})

    def abort(self) -> None:
        """Abort the current workflow."""
        self._running = False
        self._broadcast("workflow/aborted", {})

    # ── Execution loop ─────────────────────────────────────────────────────

    def _execute_plan(self, plan: WorkflowPlan) -> str:
        """Execute all steps in a plan. Returns the raw result text."""
        runtime = WorkflowRuntime()
        result_text = "Workflow completed."

        for idx, step in enumerate(plan.steps):
            if not self._running:
                log.info("Workflow aborted at step %s", idx)
                break

            while self._paused:
                time.sleep(0.2)
                if not self._running:
                    break

            self._broadcast("workflow/step", {
                "step_index": idx,
                "total_steps": len(plan.steps),
                "app": step.app,
                "action": step.action,
                "description": step.description,
            })

            try:
                if step.action == "ask_human":
                    choice = self._handle_gate(step)
                    result_text = f"Gate resolved with: {choice}"
                else:
                    runtime.execute(step.action, **step.params)
            except Exception as e:
                log.warning("Step %s failed (%s): %s", idx, step.action, e)
                # Retry once
                try:
                    time.sleep(0.5)
                    if step.action == "ask_human":
                        choice = self._handle_gate(step)
                        result_text = f"Gate resolved with: {choice}"
                    else:
                        runtime.execute(step.action, **step.params)
                except Exception as e2:
                    log.error("Step %s retry failed: %s", idx, e2)
                    self._broadcast("workflow/error", {
                        "step_index": idx,
                        "action": step.action,
                        "error": str(e2),
                    })
                    result_text = f"Step failed: {step.description} — {e2}"
                    break

        # If runtime was finalized, use its summary
        if runtime.finalized and runtime.result_summary:
            result_text = runtime.result_summary

        # Store action log for summarization
        self._last_action_log = list(runtime.action_log)
        return result_text

    def _handle_gate(self, step: WorkflowStep) -> str:
        """Create a decision gate and block until resolved or timed out."""
        question = step.params.get("question", "Approve this step?")
        timeout = step.params.get("timeout", 300)
        gate_id = self.gate_manager.create_gate(
            question=question,
            options=["yes", "no", "edit"],
            timeout=timeout,
        )

        self._broadcast("workflow/gate", {
            "gate_id": gate_id,
            "question": question,
            "options": ["yes", "no", "edit"],
            "timeout": timeout,
        })

        # If running on a separate desktop, switch back to origin for user input
        self._switch_to_origin_for_gate()

        choice = self.gate_manager.await_decision(gate_id)
        self.gate_manager.cleanup(gate_id)

        # Return to agent desktop to continue execution
        self._switch_to_agent_desktop()

        return choice

    # ── Virtual Desktop lifecycle ──────────────────────────────────────────

    def _enter_workspace(self) -> None:
        """Create/switch to an isolated workspace for the agent."""
        try:
            vd = get_virtual_desktop()
            self._origin_desktop = vd.current_desktop()
            self._agent_desktop = vd.create_desktop("Wiztant Workflow")
            vd.switch_to_desktop(self._agent_desktop)
            log.info("Entered agent desktop %s from origin %s", self._agent_desktop, self._origin_desktop)
            self._broadcast("workflow/desktop", {
                "status": "entered",
                "agent_desktop": self._agent_desktop,
                "origin_desktop": self._origin_desktop,
            })
        except Exception as e:
            log.warning("Virtual desktop unavailable, running on current desktop: %s", e)
            self._origin_desktop = None
            self._agent_desktop = None

    def _exit_workspace(self) -> None:
        """Return to origin desktop and cleanup agent desktop."""
        if self._origin_desktop is None:
            return
        try:
            vd = get_virtual_desktop()
            vd.switch_to_desktop(self._origin_desktop)
            if self._agent_desktop:
                vd.close_desktop(self._agent_desktop)
            log.info("Returned to origin desktop %s", self._origin_desktop)
            self._broadcast("workflow/desktop", {
                "status": "returned",
                "origin_desktop": self._origin_desktop,
            })
        except Exception as e:
            log.warning("Virtual desktop cleanup failed: %s", e)
        finally:
            self._origin_desktop = None
            self._agent_desktop = None

    def _switch_to_origin_for_gate(self) -> None:
        """Temporarily switch to origin desktop for user interaction."""
        if self._origin_desktop is None:
            return
        try:
            vd = get_virtual_desktop()
            vd.switch_to_desktop(self._origin_desktop)
            log.info("Switched to origin desktop for gate")
        except Exception as e:
            log.warning("Failed to switch to origin desktop for gate: %s", e)

    def _switch_to_agent_desktop(self) -> None:
        """Switch back to agent desktop after gate resolution."""
        if self._agent_desktop is None:
            return
        try:
            vd = get_virtual_desktop()
            vd.switch_to_desktop(self._agent_desktop)
            log.info("Switched back to agent desktop")
        except Exception as e:
            log.warning("Failed to switch back to agent desktop: %s", e)

    # ── Focus management (Phase 1: window-based) ───────────────────────────

    def _save_focus(self) -> Any:
        """Save the current active window for later restoration."""
        try:
            return get_system_access().get_foreground_app()
        except Exception:
            return None

    def _restore_focus(self, original_window: Any) -> None:
        """Restore focus to the original window."""
        if original_window is None:
            return
        try:
            # Best-effort focus restoration
            get_system_access().ensure_app_open(original_window)
        except Exception:
            pass

    # ── Broadcasting & delivery ────────────────────────────────────────────

    def _broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Broadcast an event to the overlay via WebSocket."""
        try:
            broadcast_sync({"type": event_type, **payload})
        except Exception as e:
            log.warning("Broadcast failed: %s", e)

    def _deliver_result(self, summary: str) -> None:
        """Deliver the final result to the user."""
        try:
            sys_access = get_system_access()
            self._result_deliverer.deliver(summary, broadcast_sync, sys_access)
        except Exception as e:
            log.error("Result delivery failed: %s", e)

    def _get_action_log(self) -> List[Dict[str, Any]]:
        """Return the action log from the last execution."""
        return getattr(self, "_last_action_log", [])

    def _fallback_plan(self, error_reason: str) -> WorkflowPlan:
        """Return a safe fallback plan when resolution fails."""
        return WorkflowPlan(
            intent=f"Fallback: {error_reason}",
            apps_required=[],
            steps=[
                WorkflowStep(
                    id="1",
                    app="system",
                    action="ask_human",
                    description="Plan resolution failed",
                    params={"question": f"I couldn't plan that workflow ({error_reason}). Can you describe what you'd like me to do?"},
                    requires_decision=True,
                ),
                WorkflowStep(
                    id="2",
                    app="system",
                    action="return_result",
                    description="Awaiting user input",
                    params={"summary": "Awaiting clarification."},
                ),
            ],
        )
