"""
core/agent_v2_engine.py — Agent Mode v2: The Bridge orchestrator.

Coordinates multi-app workflows using the existing Three-Brain Agent stack
(Vision → Planner → Executor → Actions) plus workflow templates, file
identification, clipboard monitoring, and app profiles.

The Bridge Agent never reads code files. It identifies them by name/path
and tells the IDE which file to open. The IDE does the actual editing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.agent_engine import call_api, OMNI_MODEL, EXECUTOR_MODEL, PLANNER_MODEL
from core.agent_vision import VisionBrain
from core.agent_planner import PlannerBrain
from core.agent_executor import ExecutorBrain
from core.agent_actions import ActionExecutor, count_step_cost, WaitAction
from core.agent_state import AgentStateMachine, AgentSession, AgentPlan, StepBudgetExceeded
from core.agent_screenshots import ScreenshotManager

from core.agent_v2_profiles import AppProfile, ProfileRegistry, focus_app, get_active_app_title, get_registry as get_profile_registry
from core.agent_v2_templates import WorkflowTemplate, WorkflowStep, TemplateRegistry, get_registry as get_template_registry
from core.agent_v2_filefinder import FileFinder, FileIdentificationResult
from core.agent_v2_clipboard import ClipboardMonitor, DetectedError
from core.agent_v2_revert import RevertEngine, get_engine as get_revert_engine
from core.agent_v2_orchestrator import WorkflowOrchestrator

# TuneHub learning integration
try:
    from core.tune_hub.adaptive_matcher import AdaptiveMatcher, get_matcher, MatchResult
    from core.tune_hub.browser_agent import LearnedWorkflow
    _TUNEHUB_AVAILABLE = True
except Exception:
    _TUNEHUB_AVAILABLE = False

log = logging.getLogger("core.agent_v2_engine")


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class WorkflowContext:
    """Runtime context for a workflow execution."""

    template_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    current_step_index: int = 0
    apps_used: List[str] = field(default_factory=list)
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    file_identifications: List[FileIdentificationResult] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "params": self.params,
            "current_step_index": self.current_step_index,
            "apps_used": self.apps_used,
            "step_results": self.step_results,
            "errors_encountered": self.errors_encountered,
        }


# =============================================================
#  EVENT BROADCAST HELPERS
# =============================================================

def _broadcast(event_type: str, payload: Dict[str, Any]) -> None:
    """Broadcast an event to the overlay via WebSocket."""
    try:
        from core.ws_bridge import broadcast_sync
        broadcast_sync({"type": event_type, **payload})
    except Exception as e:
        log.warning("Broadcast failed: %s", e)


def broadcast_status(
    workflow_name: str,
    current_step: int,
    total_steps: int,
    current_app: str,
    current_action: str,
    steps_used: int,
    steps_budget: int,
    apps_chain: List[str],
) -> None:
    _broadcast("agent_v2/status_update", {
        "workflow_name": workflow_name,
        "current_step": current_step,
        "total_steps": total_steps,
        "current_app": current_app,
        "current_action": current_action,
        "steps_used": steps_used,
        "steps_budget": steps_budget,
        "apps_chain": apps_chain,
    })


def broadcast_step_complete(step: Dict[str, Any], requires_decision: bool) -> None:
    _broadcast("agent_v2/step_complete", {
        "step": step,
        "requires_decision": requires_decision,
    })


def broadcast_paused(pause_context: Dict[str, Any], screenshot_b64: str = "") -> None:
    _broadcast("agent_v2/paused", {
        "pause_context": pause_context,
        "live_screenshot": screenshot_b64,
    })


def broadcast_completed(summary: Dict[str, Any], total_steps_used: int, apps_used: List[str]) -> None:
    _broadcast("agent_v2/completed", {
        "summary": summary,
        "total_steps_used": total_steps_used,
        "apps_used": apps_used,
    })


def broadcast_error(message: str, app: str, recoverable: bool) -> None:
    _broadcast("agent_v2/error", {
        "message": message,
        "app": app,
        "recoverable": recoverable,
    })


def broadcast_decision_gate(step_id: int, description: str, app: str) -> None:
    _broadcast("agent_v2/decision_gate", {
        "step_id": step_id,
        "description": description,
        "app": app,
    })


# -- TuneHub Learning Broadcasts --

def broadcast_learning_started(workflow_name: str, query: str, estimated_time: int) -> None:
    _broadcast("tunehub:learning_started", {
        "workflow_name": workflow_name,
        "query": query,
        "estimated_time": estimated_time,
    })


def broadcast_learning_progress(percent: int, current_source: str, steps_found: int) -> None:
    _broadcast("tunehub:learning_progress", {
        "percent": percent,
        "current_source": current_source,
        "steps_found": steps_found,
    })


def broadcast_learning_complete(
    template: Dict[str, Any],
    confidence: float,
    sources: List[str],
    requires_review: bool,
) -> None:
    _broadcast("tunehub:learning_complete", {
        "template": template,
        "confidence": confidence,
        "sources": sources,
        "requires_review": requires_review,
    })


def broadcast_learning_failed(reason: str, fallback: str) -> None:
    _broadcast("tunehub:learning_failed", {
        "reason": reason,
        "fallback": fallback,
    })


# =============================================================
#  AGENT V2 ENGINE
# =============================================================

class AgentV2Engine:
    """
    Main orchestrator for Agent Mode v2 — The Bridge.

    Reuses the existing Three-Brain stack and adds:
    - Workflow template execution
    - Multi-app switching
    - File identification without file reading
    - Clipboard error detection
    - Decision gates with revert support
    """

    def __init__(self) -> None:
        self.vision = VisionBrain(model=OMNI_MODEL)
        self.planner = PlannerBrain(model=PLANNER_MODEL)
        self.executor = ExecutorBrain(model=EXECUTOR_MODEL)
        self.action_runtime = ActionExecutor()
        self.screenshots = ScreenshotManager()
        self.file_finder = FileFinder()
        self.file_finder.set_vision_brain(self.vision)
        self.clipboard = ClipboardMonitor()
        self.revert_engine = get_revert_engine()
        self.profile_registry = get_profile_registry()
        self.template_registry = get_template_registry()
        self._workflow_orchestrator = WorkflowOrchestrator()

        self._state: Optional[AgentStateMachine] = None
        self._context: Optional[WorkflowContext] = None
        self._template: Optional[WorkflowTemplate] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._decision_event = threading.Event()
        self._decision_result: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    # -- Public API --

    def initiate_workflow(
        self,
        template_id: str,
        params: Dict[str, Any],
        voice: bool = False,
    ) -> str:
        """
        Start a new workflow from a template.

        Deprecated: routes into WorkflowOrchestrator.
        """
        log.warning("initiate_workflow is deprecated — routing to WorkflowOrchestrator")
        return self._workflow_orchestrator.initiate(template_id, params)

    def initiate_freeform(self, intent: str, screenshot=None, system_prompt_addendum: str = "") -> str:
        """
        Start a freeform workflow without a template.

        Deprecated: routes into WorkflowOrchestrator.
        """
        log.warning("initiate_freeform is deprecated — routing to WorkflowOrchestrator")
        return self._workflow_orchestrator.initiate("info_gather", {"query": intent})

    def initiate_preset(self, preset_id: str, intent: str, params: Dict[str, Any]) -> str:
        """
        Start a workflow from an agent preset.

        Routes into WorkflowOrchestrator.
        """
        merged_params = dict(params)
        if intent:
            merged_params["intent"] = intent
        return self._workflow_orchestrator.initiate(preset_id, merged_params)

    def pause(self, reason: str = "user_request") -> None:
        """Pause the current workflow."""
        self._workflow_orchestrator.pause(reason)
        if self._state:
            self._state.pause(reason)
            self._pause_event.set()
            broadcast_paused({
                "reason": reason,
                "current_step": self._context.current_step_index if self._context else 0,
                "session_id": self._state.session.session_id,
            })
            log.info("AgentV2 paused: %s", reason)

    def resume(self) -> None:
        """Resume a paused workflow."""
        if self._state:
            self._state.resume()
            self._pause_event.clear()
            log.info("AgentV2 resumed")

    def abort(self) -> None:
        """Abort the current workflow."""
        self._stop_event.set()
        if self._state:
            self._state.abort("user_aborted")
        self.clipboard.stop_monitoring()
        log.info("AgentV2 aborted")

    def submit_decision(self, decision: str) -> None:
        """Submit a decision from a decision gate (accept/deny/retry)."""
        self._decision_result = decision
        self._decision_event.set()
        log.info("AgentV2 decision submitted: %s", decision)

    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        if self._state is None:
            return {"status": "idle"}
        return {
            "status": self._state.session.status.value,
            "session_id": self._state.session.session_id,
            "steps_used": self._state.session.steps_used,
            "steps_budget": self._state.session.steps_budget,
            "current_step": self._context.current_step_index if self._context else 0,
            "template_id": self._context.template_id if self._context else "",
        }

    # -- TuneHub Adaptive Matching --

    def initiate_with_matching(self, intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use adaptive matcher to decide: execute existing, adapt, or learn.

        Returns a dict with action and session_id (if started).
        """
        if not _TUNEHUB_AVAILABLE:
            # Fallback: try exact match then freeform
            tpl = self.template_registry.get(intent.replace(" ", "_").lower())
            if tpl:
                session_id = self.initiate_workflow(tpl.id, params)
                return {"action": "execute", "template_id": tpl.id, "session_id": session_id}
            session_id = self.initiate_freeform(intent)
            return {"action": "freeform", "session_id": session_id}

        matcher = get_matcher()
        result = matcher.match(intent)

        if result.action == "execute":
            session_id = self.initiate_workflow(result.template_id, params)
            return {"action": "execute", "template_id": result.template_id, "session_id": session_id, "match_score": result.match_score}

        if result.action == "adapt":
            if result.adapted_template:
                self._template = result.adapted_template
                self._context = WorkflowContext(
                    template_id=result.adapted_template.id,
                    params=params,
                )
                session = AgentSession(
                    session_id=str(uuid.uuid4())[:8],
                    steps_budget=100,
                )
                self._state = AgentStateMachine(session)
                self._stop_event.clear()
                self._pause_event.clear()
                self.clipboard.start_monitoring()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
                return {"action": "adapt", "template_id": result.template_id, "session_id": session.session_id, "match_score": result.match_score}

        if result.action == "learn":
            # Start learning in background
            threading.Thread(target=self._learn_async, args=(intent,), daemon=True).start()
            return {"action": "learning", "message": result.message, "closest_templates": result.closest_templates}

        return {"action": "failed", "message": result.message}

    def _learn_async(self, intent: str) -> None:
        """Background learning thread."""
        if not _TUNEHUB_AVAILABLE:
            broadcast_learning_failed("TuneHub not available", "manual_input")
            return

        matcher = get_matcher()
        broadcast_learning_started(intent, matcher._build_search_query(intent), 45)

        try:
            # Run async learning in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(matcher.learn(intent))
            loop.close()

            if result.action == "learned" and result.learned_workflow:
                workflow = result.learned_workflow
                broadcast_learning_complete(
                    workflow.to_dict(),
                    workflow.confidence,
                    workflow.sources,
                    workflow.confidence < 0.85,
                )
            else:
                broadcast_learning_failed(result.message, "try_similar")

        except Exception as e:
            log.error("Background learning failed: %s", e)
            broadcast_learning_failed(str(e), "manual_input")

    # -- Internal Execution --

    def _on_clipboard_error(self, error: DetectedError) -> None:
        """Callback when clipboard monitor detects an error."""
        log.info("Clipboard error detected during workflow: %s", error.summary())
        if self._context:
            self._context.errors_encountered.append(error.summary())
        # Don't auto-pause — let the vision loop catch it and decide

    def _run_loop(self) -> None:
        """Main template-based execution loop."""
        if self._state is None or self._template is None or self._context is None:
            return

        self._state.start_execution()
        steps = self._template.steps

        try:
            while self._context.current_step_index < len(steps):
                if self._stop_event.is_set():
                    break

                # Wait if paused
                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.2)

                if self._stop_event.is_set():
                    break

                step = steps[self._context.current_step_index]
                self._execute_step(step)
                self._context.current_step_index += 1

            if not self._stop_event.is_set():
                self._state.complete("Workflow completed successfully")
                broadcast_completed(
                    {"message": "Workflow completed", "template": self._template.name},
                    int(self._state.session.steps_used),
                    self._context.apps_used,
                )
                self._open_outcome()

        except StepBudgetExceeded as e:
            log.error("Step budget exceeded: %s", e)
            self._state.fail(str(e))
            broadcast_error(str(e), "engine", recoverable=False)

        except Exception as e:
            log.error("Workflow execution error: %s", e, exc_info=True)
            self._state.fail(str(e))
            broadcast_error(str(e), "engine", recoverable=True)

        finally:
            self.clipboard.stop_monitoring()
            self._state.save()

    def _run_loop_freeform(self) -> None:
        """Freeform execution loop using the planner's milestones."""
        if self._state is None or self._context is None:
            return

        self._state.start_execution()
        plan = self._state.session.plan
        if plan is None:
            self._state.fail("No plan generated")
            return

        try:
            for idx, milestone in enumerate(plan.milestones):
                if self._stop_event.is_set():
                    break

                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.2)

                if self._stop_event.is_set():
                    break

                self._state.session.current_step = idx + 1
                self._state.session.current_action = milestone.title

                # Broadcast status
                broadcast_status(
                    workflow_name="Freeform",
                    current_step=idx + 1,
                    total_steps=len(plan.milestones),
                    current_app="unknown",
                    current_action=milestone.title,
                    steps_used=int(self._state.session.steps_used),
                    steps_budget=self._state.session.steps_budget,
                    apps_chain=self._context.apps_used,
                )

                # Execute milestone via Three-Brain loop
                self._execute_milestone(milestone)
                milestone.status = "completed"

                # Consume steps based on expected IDE actions
                self._state.consume_steps(milestone.expected_ide_actions)

            if not self._stop_event.is_set():
                self._state.complete("Freeform task completed")
                broadcast_completed(
                    {"message": "Task completed"},
                    int(self._state.session.steps_used),
                    self._context.apps_used,
                )
                self._open_outcome()

        except StepBudgetExceeded as e:
            log.error("Step budget exceeded: %s", e)
            self._state.fail(str(e))
            broadcast_error(str(e), "engine", recoverable=False)

        except Exception as e:
            log.error("Freeform execution error: %s", e, exc_info=True)
            self._state.fail(str(e))
            broadcast_error(str(e), "engine", recoverable=True)

        finally:
            self.clipboard.stop_monitoring()
            self._state.save()

    def _execute_step(self, step: WorkflowStep) -> None:
        """Execute a single workflow step."""
        if self._state is None or self._context is None or self._template is None:
            return

        log.info("Executing step %d: %s (%s)", step.id, step.action, step.app)
        self._state.session.current_step = step.id
        self._state.session.current_action = step.description

        # Track apps used
        if step.app not in self._context.apps_used:
            self._context.apps_used.append(step.app)

        # Focus the target app
        profile = self.profile_registry.get(step.app)
        if profile:
            focus_app(profile)

        # Broadcast status
        broadcast_status(
            workflow_name=self._template.name,
            current_step=step.id,
            total_steps=len(self._template.steps),
            current_app=step.app,
            current_action=step.description,
            steps_used=int(self._state.session.steps_used),
            steps_budget=self._state.session.steps_budget,
            apps_chain=self._context.apps_used,
        )

        # Execute based on action type
        result: Dict[str, Any] = {"success": True, "output": ""}

        if step.action in ("check_ssh_key", "generate_ssh_key", "copy_public_key",
                           "git_clone", "git_add", "git_commit", "git_push"):
            result = self._run_terminal_action(step)
        elif step.action in ("open_github_keys", "open_jira_ticket", "open_url"):
            result = self._run_browser_action(step)
        elif step.action in ("click_new_key", "click_add_key", "click", "type_key_title",
                             "paste_key", "type", "transition_ticket", "add_comment"):
            result = self._run_ui_action(step)
        elif step.action in ("screenshot_component", "detect_error", "identify_file",
                             "analyze_design"):
            result = self._run_vision_action(step)
        elif step.action in ("create_file", "type_prompt", "type_fix_prompt"):
            result = self._run_cursor_action(step)
        elif step.action == "wait_generation":
            result = self._run_wait_action(step)
        elif step.action == "ask_accept":
            result = self._run_decision_gate(step)
        else:
            # Generic UI-TARS execution
            result = self._run_ui_action(step)

        # Record result
        self._context.step_results.append({
            "step_id": step.id,
            "action": step.action,
            "app": step.app,
            "success": result.get("success", False),
            "output": result.get("output", ""),
        })

        # Consume step budget
        step_cost = step.step_cost
        if step.action in ("type_prompt", "type_fix_prompt") and step.input_text:
            step_cost = 2.0 if len(step.input_text) > 100 else 1.0
        self._state.consume_steps(step_cost)

        # Broadcast completion
        broadcast_step_complete(
            {"id": step.id, "action": step.action, "app": step.app, **result},
            requires_decision=step.requires_decision,
        )

    def _execute_milestone(self, milestone) -> None:
        """Execute a planner milestone using the Three-Brain heartbeat.

        Each milestone runs a vision-action loop until:
        - The task is visibly completed AND at least one real action was taken
        - The loop budget is exhausted
        - The user pauses/aborts
        """
        if self._state is None:
            return

        log.info("Executing milestone: %s", milestone.title)

        # Ensure we always get at least a few loops; default to 3 if unspecified
        max_loops = max(milestone.expected_ide_actions * 3, 3)
        history: List[str] = []
        real_actions_taken = 0  # Count of non-wait actions actually executed

        for loop in range(max_loops):
            if self._stop_event.is_set() or self._pause_event.is_set():
                break

            # 1. Screenshot
            screenshot = self.screenshots.capture()

            # 2. Vision
            perception = self.vision.analyze(screenshot, question=milestone.prompt)

            # Check for completion ONLY after at least one real action was taken.
            # This prevents the agent from declaring "done" on an idle screen
            # before it has done any work.
            if real_actions_taken > 0 and self.vision.detects_completion():
                log.info("Milestone completion detected: %s", milestone.title)
                break

            # Check for errors
            if self.vision.detects_error():
                errors = perception.get("detected_errors", [])
                if errors:
                    log.warning("Vision detected error: %s", errors[0])

            # 3. Executor
            hints = {
                "tool": perception.get("tool_detected", "unknown"),
                "window_state": perception.get("window_state", "unknown"),
                "elements": perception.get("visible_elements", {}),
            }
            actions = self.executor.predict(screenshot, milestone.prompt, hints, history)

            if not actions:
                actions = [WaitAction(seconds=1.5)]

            # 4. Execute actions individually so we can broadcast each one
            for action in actions:
                if self._stop_event.is_set():
                    break

                action_name = type(action).__name__
                action_desc = self._action_description(action)

                # Broadcast to UI so user sees what's actually happening
                broadcast_step_complete(
                    {
                        "id": f"{milestone.step_id}.{loop + 1}",
                        "action": action_name,
                        "app": perception.get("tool_detected", "unknown"),
                        "description": action_desc,
                        "success": None,  # Will update after execution
                        "output": "",
                    },
                    requires_decision=False,
                )

                ok, msg = self.action_runtime.execute(action)
                self._state.consume_steps(getattr(action, "step_cost", 1.0))

                # Update the broadcast with result
                broadcast_step_complete(
                    {
                        "id": f"{milestone.step_id}.{loop + 1}",
                        "action": action_name,
                        "app": perception.get("tool_detected", "unknown"),
                        "description": action_desc,
                        "success": ok,
                        "output": msg,
                    },
                    requires_decision=False,
                )

                if ok:
                    history.append(f"{action_name}: {msg}")
                    if not isinstance(action, WaitAction):
                        real_actions_taken += 1
                else:
                    log.warning("Action failed in milestone: %s", msg)
                    # Don't break on single action failure — let the vision loop recover

            # 5. Wait for UI to settle
            time.sleep(0.5)

            # Budget check
            if self._state.session.steps_used >= self._state.session.steps_budget:
                raise StepBudgetExceeded("Budget exhausted during milestone execution")

        if real_actions_taken == 0:
            log.warning("Milestone '%s' completed with zero real actions taken", milestone.title)
            # Still mark complete but warn — the planner may have given an impossible milestone
            broadcast_error(
                f"Milestone '{milestone.title}' could not execute any actions. "
                "The screen may be unresponsive or the task unclear.",
                app="engine",
                recoverable=True,
            )

    def _run_terminal_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a terminal command."""
        if not step.command:
            return {"success": False, "output": "No command"}

        try:
            import subprocess
            result = subprocess.run(
                step.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Auto-inputs (e.g., Enter for default paths)
            for auto_input in step.auto_inputs:
                # This is a simplification; real implementation would use pynput
                pass

            output = result.stdout + result.stderr
            success = result.returncode == 0

            return {"success": success, "output": output[:500]}

        except Exception as e:
            return {"success": False, "output": str(e)}

    def _run_browser_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Open a URL in the browser."""
        if not step.url:
            return {"success": False, "output": "No URL"}

        try:
            import subprocess
            cmd = f"xdg-open '{step.url}'" if subprocess.run(["which", "xdg-open"], capture_output=True).returncode == 0 else None
            if cmd:
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2.0)
                return {"success": True, "output": f"Opened {step.url}"}
            return {"success": False, "output": "No browser launcher available"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def _run_ui_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a UI action via UI-TARS."""
        screenshot = self.screenshots.capture()
        task = step.description
        if step.ui_target:
            task = f"Click the '{step.ui_target}' element. {step.description}"
        if step.input_text:
            task = f"Type '{step.input_text}' into the appropriate field. {step.description}"

        actions = self.executor.predict(screenshot, task)
        if not actions:
            return {"success": False, "output": "No actions predicted"}

        cost, messages = self.action_runtime.execute_many(actions)
        if self._state:
            self._state.consume_steps(cost)

        return {"success": True, "output": "; ".join(messages)}

    def _run_vision_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a vision-based analysis step."""
        screenshot = self.screenshots.capture()

        if step.action == "identify_file":
            # Use the file finder
            intent = self._context.params.get("intent", "fix the error")
            error_text = self._context.params.get("error_message", "")
            result = self.file_finder.identify(intent, error_text=error_text, screenshot=screenshot)
            if result.top_candidate:
                self._context.file_identifications.append(result)
                self._context.params["file_path"] = result.top_candidate.path
                return {
                    "success": True,
                    "output": f"Identified: {result.top_candidate.path} (confidence: {result.top_candidate.confidence:.0%})",
                }
            return {"success": False, "output": "Could not identify file"}

        if step.action == "detect_error":
            last_error = self.clipboard.get_last_error()
            if last_error:
                self._context.params["error_message"] = last_error.text
                return {"success": True, "output": last_error.summary()}
            return {"success": False, "output": "No error detected in clipboard"}

        # Generic vision analysis
        perception = self.vision.analyze(screenshot, question=step.description)
        return {
            "success": True,
            "output": json.dumps(perception, default=str)[:300],
        }

    def _run_cursor_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute an action in Cursor (type prompt, create file, etc.)."""
        profile = self.profile_registry.get("cursor")
        if profile:
            focus_app(profile)

        screenshot = self.screenshots.capture()
        task = step.description
        if step.input_text:
            rendered = step.input_text.format(**self._context.params)
            task = f'Type this exact prompt into the chat: "{rendered}"'

        actions = self.executor.predict(screenshot, task)
        if not actions:
            return {"success": False, "output": "No actions predicted"}

        cost, messages = self.action_runtime.execute_many(actions)
        if self._state:
            self._state.consume_steps(cost)

        return {"success": True, "output": "; ".join(messages)}

    def _run_wait_action(self, step: WorkflowStep) -> Dict[str, Any]:
        """Wait for generation/loading to complete."""
        max_wait = 60  # seconds
        poll_interval = 2.0
        elapsed = 0.0

        while elapsed < max_wait:
            if self._stop_event.is_set():
                break
            time.sleep(poll_interval)
            elapsed += poll_interval

            screenshot = self.screenshots.capture()
            perception = self.vision.analyze(screenshot)

            if not perception.get("is_loading", False) and not perception.get("is_generating", False):
                return {"success": True, "output": f"Waited {elapsed:.0f}s, generation complete"}

        return {"success": True, "output": f"Waited {max_wait}s (timeout)"}

    def _run_decision_gate(self, step: WorkflowStep) -> Dict[str, Any]:
        """Pause for user decision (Accept/Deny/Revert)."""
        self._decision_event.clear()
        self._decision_result = None

        broadcast_decision_gate(step.id, step.description, step.app)

        # Wait for user decision
        decision = "accept"
        if self._decision_event.wait(timeout=300):  # 5 minute timeout
            decision = self._decision_result or "accept"

        if decision == "deny":
            # Attempt revert
            action_type = self._infer_revert_type(step)
            revert_result = self.revert_engine.revert(action_type, self._context.params)
            return {
                "success": False,
                "output": f"Denied. Revert: {revert_result}",
                "revert": revert_result,
            }

        if decision == "retry":
            # Retry the same step
            self._context.current_step_index -= 1  # Will be incremented back
            return {"success": True, "output": "Retry requested"}

        return {"success": True, "output": "Accepted"}

    def _action_description(self, action) -> str:
        """Return a human-readable description of an action for UI display."""
        from core.agent_actions import (
            ClickAction, DoubleClickAction, TypeAction, PressAction,
            ScrollAction, WaitAction, DragAction,
        )
        if isinstance(action, ClickAction):
            return f"Click at screen position ({action.x_norm:.2f}, {action.y_norm:.2f})"
        if isinstance(action, DoubleClickAction):
            return f"Double-click at screen position ({action.x_norm:.2f}, {action.y_norm:.2f})"
        if isinstance(action, TypeAction):
            preview = action.text[:40] + "..." if len(action.text) > 40 else action.text
            return f"Type: '{preview}'"
        if isinstance(action, PressAction):
            return f"Press key: {action.key}"
        if isinstance(action, ScrollAction):
            return f"Scroll {action.direction} {action.amount} units"
        if isinstance(action, WaitAction):
            return f"Wait {action.seconds}s for UI to settle"
        if isinstance(action, DragAction):
            return f"Drag from ({action.x1_norm:.2f}, {action.y1_norm:.2f}) to ({action.x2_norm:.2f}, {action.y2_norm:.2f})"
        return f"Execute {type(action).__name__}"

    def _open_outcome(self) -> None:
        """After workflow completion, open/reveal the final result to the user.

        This ensures the user can see what the agent actually produced instead of
        just reading "Workflow Complete" in the overlay.
        """
        if self._context is None:
            return

        params = self._context.params
        intent = params.get("intent", "")
        template_id = self._context.template_id

        try:
            from platforms.factory import get_agent_runtime
            rt = get_agent_runtime()

            # Template-based outcomes
            if template_id == "github_ssh_clone":
                repo_url = params.get("repo_url", "")
                repo_name = repo_url.split("/")[-1].replace(".git", "") if repo_url else "repo"
                # Open file manager to the cloned repo folder
                rt.open_app("file manager")
                return

            if template_id == "jira_commit_push":
                # Open terminal to show the pushed branch
                rt.open_app("terminal")
                return

            # Freeform / preset outcomes — infer from intent keywords
            intent_lower = intent.lower()

            # Screenshot / save image tasks → open file manager / image viewer
            if any(k in intent_lower for k in ("screenshot", "screenshots", "save image", "capture")):
                rt.open_app("file manager")
                return

            # Browser / web tasks → focus or open browser
            if any(k in intent_lower for k in ("browser", "website", "open chrome", "open firefox", "go to ", "navigate to ")):
                rt.open_app("chrome") or rt.open_app("firefox")
                return

            # IDE / code tasks → focus IDE
            if any(k in intent_lower for k in ("cursor", "windsurf", "vscode", "vs code", "code ", "file ", "component", "create ", "write ")):
                rt.open_app("cursor") or rt.open_app("vscode")
                return

            # Notion / docs tasks → focus Notion
            if any(k in intent_lower for k in ("notion", "document", "doc ", "prd", "page")):
                rt.open_app("notion")
                return

            # Terminal / command tasks
            if any(k in intent_lower for k in ("terminal", "command", "run ", "npm ", "git ", "python ")):
                rt.open_app("terminal")
                return

            # Default: try to open file manager so user can see something happened
            rt.open_app("file manager")

        except Exception as e:
            log.warning("Outcome opening failed: %s", e)

    def _infer_revert_type(self, step: WorkflowStep) -> str:
        """Map a step to its revert action type."""
        mapping = {
            "git_clone": "git_clone",  # No direct revert, but we could delete
            "git_commit": "git_commit",
            "git_push": "git_push",
            "git_add": "git_add",
            "generate_ssh_key": "github_ssh_key",
            "click_add_key": "github_ssh_key",
            "create_file": "file_create",
            "type_prompt": "cursor_chat",
            "type_fix_prompt": "cursor_chat",
        }
        return mapping.get(step.action, "cursor_chat")
