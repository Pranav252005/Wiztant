"""
core/agent_orchestrator.py — Three-Brain Agent orchestrator.

Replaces core/agent_unified.py as the F9×2 agent mode entry point.

Architecture:
  1. PLANNER (Qwen3-VL-235B) → generates structured plan from user spec + screenshot
  2. VISION  (Gemini Flash)   → monitors IDE state every heartbeat
  3. EXECUTOR (UI-TARS 7B)    → predicts GUI actions from screenshot + task

Heartbeat loop:
  vision.analyze() → state check → plan.current_task → executor.predict() →
  action_executor.execute() → verify change → broadcast status
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from core.agent_engine import parse_json, to_base64
from core.agent_state import AgentSession, AgentStateMachine, AgentPlan, Milestone, SessionStatus
from core.agent_profiles import detect_tool_from_text, get_profile
from core.agent_screenshots import ScreenshotManager, get_active_window_title
from core.agent_vision import VisionBrain
from core.agent_executor import ExecutorBrain
from core.agent_planner import PlannerBrain
from core.agent_actions import ActionExecutor, count_step_cost, WaitAction
from core import guardrails as _gr

log = logging.getLogger("core.agent_orchestrator")

# =============================================================
#  CONSTANTS
# =============================================================

HEARTBEAT_INTERVAL = 2.5  # seconds between vision polls
ACTION_SETTLE_DELAY = 1.5  # seconds to wait after action before verify
MAX_VERIFY_WAIT = 5.0  # max seconds to wait for screen change


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point — drop-in replacement for run_unified_agent()
# ═══════════════════════════════════════════════════════════════════════════════

async def run_agent_session(
    task: str,
    runtime,
    speak_fn: Callable | None = None,
    set_wave_state_fn: Callable | None = None,
    append_chat_fn: Callable | None = None,
    stop_event=None,
    max_steps: int = 0,
    credit_check_fn: Callable | None = None,
    steps_taken_ref: list | None = None,
    token_usage_ref: dict | None = None,
) -> str:
    """
    Run the Three-Brain agent session. Returns a status message.

    Signature matches the old run_unified_agent() for drop-in replacement.
    """
    speak_fn = speak_fn or (lambda *_a, **_k: None)
    set_wave_state_fn = set_wave_state_fn or (lambda *_a, **_k: None)
    append_chat_fn = append_chat_fn or (lambda *_a, **_k: None)
    credit_check_fn = credit_check_fn or (lambda *_a, **_k: True)

    # Initialize state machine — fall back to user-configured limit, then 100
    budget = max_steps
    if budget <= 0:
        try:
            import json as _json
            from pathlib import Path as _Path
            _settings = _json.loads(
                (_Path(__file__).parent.parent / "data" / "settings.json").read_text(encoding="utf-8")
            )
            budget = int(_settings.get("agent_max_steps", 0))
        except Exception:
            budget = 0
    if budget <= 0:
        budget = 100
    session = AgentSession(steps_budget=budget)
    sm = AgentStateMachine(session)

    # Initialize brains
    planner = PlannerBrain()
    vision = VisionBrain()
    executor = ExecutorBrain()
    screenshot_mgr = ScreenshotManager()
    action_exec = ActionExecutor(runtime)

    # Start token accounting for this session so the planner/vision/executor
    # API calls are tallied per model and the caller can bill on real usage.
    from core.agent_engine import reset_token_usage, get_token_usage
    reset_token_usage()

    log.info("=== Three-Brain Agent task: %r ===", task)
    append_chat_fn("assistant", f"[Agent] Starting: {task}")
    set_wave_state_fn("agent")

    # -- Phase 1: Planning --
    sm.start_planning()
    set_wave_state_fn("thinking")

    try:
        init_screenshot = screenshot_mgr.capture_active_window(runtime)
    except Exception as e:
        log.warning("Initial screenshot failed: %s", e)
        init_screenshot = None

    if init_screenshot is not None:
        append_chat_fn("assistant", "[Agent] Analyzing screen and building plan...")
        plan = planner.create_plan(task, init_screenshot)
        session.plan = plan
        tool_name = plan.detected_tool if plan.detected_tool != "unknown" else detect_tool_from_text(task)
        profile = get_profile(tool_name or "")
        append_chat_fn(
            "assistant",
            f"[Agent] Plan ready: {len(plan.milestones)} milestones, "
            f"~{plan.estimated_steps} steps. Tool: {profile.name}",
        )
    else:
        # Fallback: no screenshot available
        from core.agent_state import AgentPlan, Milestone
        plan = AgentPlan(
            plan_id="fallback",
            detected_tool=detect_tool_from_text(task) or "unknown",
            milestones=[Milestone(step_id=1, title="Execute request", prompt=task)],
        )
        session.plan = plan
        profile = get_profile("unknown")

    # -- Phase 2+3: Execution Loop --
    sm.start_execution()
    set_wave_state_fn("agent")

    loop_history: List[str] = []
    last_screenshot_hash = ""
    unchanged_count = 0

    try:
        while sm.is_running and not sm.is_paused:
            if stop_event and stop_event.is_set():
                sm.abort("stopped_by_user")
                return "Stopped by user"

            # Credit check (skip on first iteration — pre-paid)
            if session.current_step > 0 and not credit_check_fn(session.current_step):
                msg = "Agent stopped: credits exhausted."
                append_chat_fn("assistant", f"[Agent] {msg}")
                sm.fail(msg)
                _send_done(msg, success=False)
                if steps_taken_ref is not None:
                    steps_taken_ref.append(session.current_step)
                return msg

            # 1. CAPTURE — What do we see?
            try:
                screenshot = screenshot_mgr.capture_active_window(runtime)
                screenshot_hash = screenshot_mgr.quick_hash(screenshot)
            except Exception as e:
                log.error("Screenshot capture failed: %s", e)
                sm.fail("screenshot_capture_failed")
                return f"Screenshot capture failed: {e}"

            # 2. VISION — Analyze current state
            set_wave_state_fn("thinking")
            state_desc = vision.analyze(screenshot)

            # Auto-pause triggers
            if vision.detects_error():
                sm.pause("ide_error_detected")
                append_chat_fn("assistant", "[Agent] Auto-paused: IDE error detected")
                _send_paused(sm.session)
                break

            if vision.detects_completion() and session.current_step > 0:
                # Mark current milestone complete and pause for decision
                if session.plan and session.current_step < len(session.plan.milestones):
                    session.plan.milestones[session.current_step].status = "completed"
                sm.pause("milestone_complete")
                append_chat_fn(
                    "assistant",
                    f"[Agent] Step {session.current_step + 1} complete. Paused for review.",
                )
                _send_step_complete(session)
                break

            # 3. PLAN CHECK — What should we do next?
            current_task = task  # fallback
            if session.plan and session.current_step < len(session.plan.milestones):
                milestone = session.plan.milestones[session.current_step]
                current_task = milestone.prompt or milestone.title

            # 4. EXECUTOR — Predict action
            hints: Dict[str, Any] = {}
            if vision._last_result:
                hints = vision._last_result.get("visible_elements", {})

            actions = executor.predict_with_retry(
                screenshot=screenshot,
                task=current_task,
                hints=hints,
                history=loop_history[-5:],
            )

            action_summary = " | ".join(type(a).__name__.replace("Action", "") for a in actions)
            log.info("Step %d: %s", session.current_step + 1, action_summary)
            append_chat_fn("assistant", f"[Agent] Step {session.current_step + 1}: {action_summary}")

            # 5. GUARDRAILS — Safety check before execution
            for action in actions:
                action_text = repr(action)
                safety, reason = _gr.classify_action(action_text)
                _gr.AgentAuditLogger.log_decision(
                    intent=task, action=action_text, safety=safety, reason=reason
                )
                if safety == "blocked":
                    log.warning("Guardrail blocked: %s", reason)
                    append_chat_fn("assistant", f"[Agent] Blocked: {reason}")
                    sm.fail(f"blocked: {reason}")
                    _send_blocked(reason)
                    if steps_taken_ref is not None:
                        steps_taken_ref.append(session.current_step)
                    return f"Blocked by safety guardrail: {reason}"

            # 6. ACTION RUNTIME — Execute
            set_wave_state_fn("agent")
            step_cost, messages = action_exec.execute_many(actions)
            session.log_action("execute", {"actions": action_summary, "messages": messages})

            # 7. BUDGET — Track consumption
            try:
                sm.consume_steps(step_cost)
            except Exception as e:
                msg = str(e)
                append_chat_fn("assistant", f"[Agent] {msg}")
                sm.fail(msg)
                _send_done(msg, success=False)
                if steps_taken_ref is not None:
                    steps_taken_ref.append(session.current_step)
                return msg

            # 8. VERIFY — Did the action work?
            time.sleep(ACTION_SETTLE_DELAY)
            try:
                new_screenshot = screenshot_mgr.capture_active_window(runtime)
                new_hash = screenshot_mgr.quick_hash(new_screenshot)
            except Exception:
                new_hash = ""

            if new_hash != screenshot_hash:
                unchanged_count = 0
                append_chat_fn("assistant", f"[Agent] Verified change after step {session.current_step + 1}")
            else:
                unchanged_count += 1
                append_chat_fn(
                    "assistant",
                    f"[Agent] Warning: no visible change after step {session.current_step + 1}",
                )
                if unchanged_count >= 3:
                    sm.pause("no_visible_progress")
                    append_chat_fn(
                        "assistant",
                        "[Agent] Paused: no visible progress after 3 attempts.",
                    )
                    _send_paused(sm.session)
                    break

            # 9. LOOP DETECTION
            loop_history.append(action_summary)
            if _gr.detect_loop([(h, "") for h in loop_history[-10:]]):
                msg = "Loop detected — aborting"
                log.warning(msg)
                sm.fail(msg)
                _send_blocked("loop_detected")
                if steps_taken_ref is not None:
                    steps_taken_ref.append(session.current_step)
                return msg

            # 10. FEEDBACK — Broadcast status
            session.current_step += 1
            session.current_action = action_summary
            _send_status(session, state_desc)

            # Advance milestone if applicable
            if session.plan and session.current_step < len(session.plan.milestones):
                session.plan.milestones[session.current_step].status = "active"

            # Heartbeat delay
            time.sleep(HEARTBEAT_INTERVAL)

    except Exception as e:
        log.error("Agent orchestrator error: %s", e, exc_info=True)
        sm.fail(str(e))
        append_chat_fn("assistant", f"[Agent] Error: {e}")
        if steps_taken_ref is not None:
            steps_taken_ref.append(session.current_step)
        return f"Agent error: {e}"

    finally:
        set_wave_state_fn("idle")
        sm.save()
        # Hand the per-model token totals back to the caller for billing.
        if token_usage_ref is not None:
            token_usage_ref.update(get_token_usage())

    # Determine final status
    if sm.session.status == SessionStatus.PAUSED:
        _send_paused(sm.session)
        return f"Agent paused at step {session.current_step + 1}"

    if sm.session.status == SessionStatus.COMPLETED:
        msg = "Task completed successfully"
        _send_done(msg, success=True)
        if steps_taken_ref is not None:
            steps_taken_ref.append(session.current_step)
        return msg

    msg = f"Agent finished ({sm.session.status.value}) at step {session.current_step + 1}"
    _send_done(msg, success=sm.session.status == SessionStatus.COMPLETED)
    if steps_taken_ref is not None:
        steps_taken_ref.append(session.current_step)
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
#  WebSocket bridge helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _send_status(session: AgentSession, ide_state: Dict[str, Any]):
    try:
        from core.ws_bridge import broadcast_sync
        broadcast_sync({
            "type": "agent_status_update",
            "status": session.status.value,
            "current_step": session.current_step,
            "total_steps": len(session.plan.milestones) if session.plan else 0,
            "steps_used": session.steps_used,
            "steps_budget": session.steps_budget,
            "current_action": session.current_action,
            "ide_state": ide_state.get("window_state", "unknown"),
        })
    except Exception:
        pass


def _send_step_complete(session: AgentSession):
    try:
        from core.ws_bridge import send_agent_step_v2
        milestone = None
        if session.plan and session.current_step < len(session.plan.milestones):
            milestone = session.plan.milestones[session.current_step]
        title = milestone.title if milestone else "Step complete"
        send_agent_step_v2(
            task_id="agent-task",
            step=session.current_step + 1,
            of=len(session.plan.milestones) if session.plan else 1,
            action=title,
        )
    except Exception:
        pass


def _send_paused(session: AgentSession):
    try:
        from core.ws_bridge import broadcast_sync
        broadcast_sync({
            "type": "agent_paused",
            "pause_context": session.pause_snapshot.to_dict() if session.pause_snapshot else {},
            "can_replan": True,
        })
    except Exception:
        pass


def _send_done(result: str, success: bool = True):
    try:
        from core.ws_bridge import send_agent_done
        send_agent_done("agent-task", result, success=success)
    except Exception:
        pass


def _send_blocked(reason: str):
    try:
        from core.ws_bridge import send_agent_blocked
        send_agent_blocked("agent-task", reason, undoable=False)
    except Exception:
        pass
