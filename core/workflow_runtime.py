"""core/workflow_runtime.py — Restricted action executor for Workflow Mode.

The WorkflowRuntime ONLY permits UI-navigation actions (open app, click, type,
scroll, etc.). Any file write, git operation, shell execution, or code creation
immediately raises WorkflowActionBlocked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from platforms.factory import get_system_access
from core.guardrails import WorkflowGuardrails


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class WorkflowStep:
    """A single step in a workflow plan."""

    id: str
    app: str  # "browser", "slack", "jira", "notion", etc.
    action: str  # one of ALLOWED_ACTIONS
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[str] = None
    requires_decision: bool = False


@dataclass
class WorkflowPlan:
    """A dynamically generated or static workflow plan."""

    intent: str
    apps_required: List[str] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    estimated_budget: int = 20  # max screenshots / LLM calls
    result_type: str = "summary"  # "summary", "link", "clipboard", "notification"


class WorkflowActionBlocked(Exception):
    """Raised when a disallowed action is attempted in Workflow Mode."""

    pass


# ── Allowed actions ──────────────────────────────────────────────────────────

ALLOWED_ACTIONS = {
    "open_app",
    "focus_window",
    "navigate_to",
    "click",
    "type",
    "scroll",
    "hotkey",
    "copy",
    "paste",
    "screenshot",
    "wait",
    "read_screen",
    "ask_human",
    "return_result",
}

# ── Action-to-system-access mapping ──────────────────────────────────────────

_ACTION_DELEGATES: Dict[str, str] = {
    "open_app": "launch_app",
    "focus_window": "raise_window",
    "click": "click",
    "type": "type_text",
    "scroll": "scroll",
    "hotkey": "hotkey",
    "copy": "get_clipboard",
    "paste": "set_clipboard",
    "screenshot": "take_screenshot",
    "wait": None,  # handled inline
    "read_screen": "take_screenshot",  # screenshot sent to vision model later
    "navigate_to": None,  # handled inline (browser launch)
}


class WorkflowRuntime:
    """Runtime that executes workflow steps with strict action restrictions."""

    def __init__(self) -> None:
        self.action_log: List[Dict[str, Any]] = field(default_factory=list)
        self.finalized: bool = False
        self.result_summary: str = ""
        self._guardrails = WorkflowGuardrails()
        self._guardrail_violation: str | None = None
        # Initialize action_log properly since dataclass field doesn't auto-init in normal class
        self.action_log = []

    # ── Core execution ───────────────────────────────────────────────────────

    def execute(self, action_type: str, **kwargs: Any) -> Any:
        """Execute a single workflow action if allowed, else raise."""
        if action_type not in ALLOWED_ACTIONS:
            raise WorkflowActionBlocked(
                f"Action '{action_type}' is not allowed in Workflow Mode."
            )

        # ── Guardrail checks ─────────────────────────────────────────────────
        blocked, reason = self._guardrails.check_time_ceiling()
        if blocked:
            self._guardrail_violation = reason
            raise WorkflowActionBlocked(f"Guardrail: {reason}")

        if action_type == "type":
            blocked, reason = self._guardrails.check_type_input(kwargs.get("text", ""))
            if blocked:
                self._guardrail_violation = reason
                raise WorkflowActionBlocked(f"Guardrail: {reason}")

        if action_type == "navigate_to":
            blocked, reason = self._guardrails.check_navigate_url(kwargs.get("url", ""))
            if blocked:
                self._guardrail_violation = reason
                raise WorkflowActionBlocked(f"Guardrail: {reason}")

        if action_type == "screenshot":
            blocked, reason = self._guardrails.check_screenshot_budget()
            if blocked:
                self._guardrail_violation = reason
                raise WorkflowActionBlocked(f"Guardrail: {reason}")
            self._guardrails.record_screenshot()

        # ── Auto-authorization ───────────────────────────────────────────────
        # When opening an app, make sure the agent can sign in. If the user
        # never configured it in Settings, wire directly to OAuth on demand.
        if action_type == "open_app":
            app_name = kwargs.get("app_name") or kwargs.get("app") or ""
            if app_name:
                try:
                    from core.integrations import ensure_authorized
                    auth = ensure_authorized(app_name)
                    if auth.get("status") == "needs_setup":
                        # Surface to the user instead of guessing credentials.
                        self._handle_ask_human(
                            question=(
                                f"To continue I need access to {app_name}. Please add it under "
                                f"Settings → Integrations (or complete the sign-in), then resume."
                            )
                        )
                except Exception as _auth_err:
                    import logging
                    logging.getLogger("core.workflow_runtime").warning(
                        "ensure_authorized(%s) failed: %s", app_name, _auth_err
                    )

        # Always log before execution
        log_entry = {"action": action_type, "params": kwargs, "result": None}

        if action_type == "ask_human":
            result = self._handle_ask_human(**kwargs)
        elif action_type == "return_result":
            result = self._handle_return_result(**kwargs)
        elif action_type == "wait":
            result = self._handle_wait(**kwargs)
        elif action_type == "navigate_to":
            result = self._handle_navigate_to(**kwargs)
        else:
            result = self._delegate_to_system(action_type, **kwargs)

        log_entry["result"] = result
        self.action_log.append(log_entry)
        return result

    # ── Internal handlers ────────────────────────────────────────────────────

    def _delegate_to_system(self, action_type: str, **kwargs: Any) -> Any:
        """Delegate allowed actions to the platform system access driver."""
        sys_access = get_system_access()
        method_name = _ACTION_DELEGATES.get(action_type)
        if method_name is None:
            raise WorkflowActionBlocked(
                f"Action '{action_type}' has no system delegate mapping."
            )
        method = getattr(sys_access, method_name)
        return method(**kwargs)

    def _handle_ask_human(self, question: str, timeout: int = 300) -> Dict[str, Any]:
        """Return a gate request for the orchestrator to await user input."""
        return {
            "type": "gate_request",
            "question": question,
            "timeout": timeout,
        }

    def _handle_return_result(self, summary: str) -> str:
        """Finalize the workflow run and store the result summary."""
        self.finalized = True
        self.result_summary = summary
        return summary

    def _handle_wait(self, seconds: float = 1.0, **kwargs: Any) -> None:
        """Pause execution for the specified duration."""
        import time

        time.sleep(seconds)
        return None

    def _handle_navigate_to(self, url: str, **kwargs: Any) -> bool:
        """Open a URL in the default browser."""
        sys_access = get_system_access()
        return sys_access.open_browser(url)
