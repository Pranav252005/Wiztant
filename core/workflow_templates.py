"""core/workflow_templates.py — Daily-life workflow templates for Workflow Mode.

Templates encode multi-app recipes for common daily tasks. Each template defines
a sequence of WorkflowSteps that the orchestrator executes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.workflow_runtime import WorkflowPlan, WorkflowStep
from core.workflow_planner import WorkflowPlanner

log = logging.getLogger("core.workflow_templates")


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class WorkflowTemplate:
    """A reusable daily-life workflow recipe."""

    id: str
    name: str
    description: str
    apps_required: List[str]
    params_schema: List[dict] = field(default_factory=list)
    steps: List[WorkflowStep] | None = None  # None = use dynamic planner
    examples: List[str] = field(default_factory=list)


# =============================================================
#  BUILT-IN TEMPLATES
# =============================================================

# Parameter placeholders are injected via simple str.format on step params.
# Use {param_name} syntax in step param values.


def _build_morning_standup() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="morning_standup",
        name="Morning Standup",
        description="Open Jira, list your assigned tickets, copy status, open Slack, paste to standup channel.",
        apps_required=["browser", "slack"],
        params_schema=[
            {"name": "channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #standup"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to Jira", params={"url": "https://jira.atlassian.com"}),
            WorkflowStep(id="3", app="browser", action="read_screen", description="Read assigned tickets", params={}),
            WorkflowStep(id="4", app="browser", action="copy", description="Copy ticket status", params={}),
            WorkflowStep(id="5", app="slack", action="open_app", description="Open Slack", params={"app_name": "slack"}),
            WorkflowStep(id="6", app="slack", action="focus_window", description="Focus Slack", params={"window_title_pattern": "Slack"}),
            WorkflowStep(id="7", app="slack", action="click", description="Open channel", params={}),
            WorkflowStep(id="8", app="slack", action="type", description="Type standup update", params={"text": "Standup update: {ticket_status}"}),
            WorkflowStep(id="9", app="slack", action="hotkey", description="Send message", params={"keys": ["return"]}),
            WorkflowStep(id="10", app="slack", action="wait", description="Wait for replies", params={"seconds": 30}),
            WorkflowStep(id="11", app="slack", action="read_screen", description="Read replies", params={}),
            WorkflowStep(id="12", app="system", action="return_result", description="Summarize standup", params={"summary": "Standup posted to {channel}. Replies summarized."}),
        ],
        examples=[
            "Post my Jira ticket status to #standup and tell me what people replied",
            "Do my morning standup update in Slack",
        ],
    )


def _build_ticket_to_slack() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="ticket_to_slack",
        name="Ticket to Slack",
        description="Create a Jira ticket and send the link to a Slack channel.",
        apps_required=["browser", "slack"],
        params_schema=[
            {"name": "description", "label": "Ticket Description", "type": "text", "placeholder": "e.g. Login button broken on mobile"},
            {"name": "channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #engineering"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to Jira", params={"url": "https://jira.atlassian.com"}),
            WorkflowStep(id="3", app="browser", action="click", description="Click Create", params={}),
            WorkflowStep(id="4", app="browser", action="type", description="Enter ticket description", params={"text": "{description}"}),
            WorkflowStep(id="5", app="browser", action="hotkey", description="Submit ticket", params={"keys": ["ctrl", "return"]}),
            WorkflowStep(id="6", app="browser", action="wait", description="Wait for page load", params={"seconds": 2}),
            WorkflowStep(id="7", app="browser", action="copy", description="Copy ticket URL", params={}),
            WorkflowStep(id="8", app="slack", action="open_app", description="Open Slack", params={"app_name": "slack"}),
            WorkflowStep(id="9", app="slack", action="focus_window", description="Focus Slack", params={"window_title_pattern": "Slack"}),
            WorkflowStep(id="10", app="slack", action="click", description="Open channel", params={}),
            WorkflowStep(id="11", app="slack", action="paste", description="Paste ticket link", params={}),
            WorkflowStep(id="12", app="slack", action="hotkey", description="Send message", params={"keys": ["return"]}),
            WorkflowStep(id="13", app="slack", action="wait", description="Wait for replies", params={"seconds": 60}),
            WorkflowStep(id="14", app="slack", action="read_screen", description="Read replies", params={}),
            WorkflowStep(id="15", app="system", action="return_result", description="Return result", params={"summary": "Ticket created and shared in {channel}. Replies summarized."}),
        ],
        examples=[
            "Create a Jira ticket for the login bug and send it to #engineering",
            "File a ticket about the API error and post the link in Slack",
        ],
    )


def _build_email_triage() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="email_triage",
        name="Email Triage",
        description="Open your email client, scan unread messages, flag urgent ones, and summarize to clipboard.",
        apps_required=["browser"],
        params_schema=[
            {"name": "email_url", "label": "Email URL", "type": "text", "placeholder": "e.g. https://mail.google.com"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to email", params={"url": "{email_url}"}),
            WorkflowStep(id="3", app="browser", action="read_screen", description="Scan unread emails", params={}),
            WorkflowStep(id="4", app="browser", action="click", description="Open first urgent email", params={}),
            WorkflowStep(id="5", app="browser", action="read_screen", description="Read email content", params={}),
            WorkflowStep(id="6", app="browser", action="copy", description="Copy summary", params={}),
            WorkflowStep(id="7", app="system", action="return_result", description="Return triage summary", params={"summary": "Email triage complete. Urgent items copied to clipboard."}),
        ],
        examples=[
            "Triage my unread emails and copy a summary",
            "Check Gmail for urgent messages and summarize them",
        ],
    )


def _build_research_digest() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="research_digest",
        name="Research Digest",
        description="Search the web, open top results, extract key points, and summarize to clipboard.",
        apps_required=["browser"],
        params_schema=[
            {"name": "query", "label": "Search Query", "type": "text", "placeholder": "e.g. Python asyncio best practices"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to search engine", params={"url": "https://google.com"}),
            WorkflowStep(id="3", app="browser", action="click", description="Focus search box", params={}),
            WorkflowStep(id="4", app="browser", action="type", description="Type query", params={"text": "{query}"}),
            WorkflowStep(id="5", app="browser", action="hotkey", description="Submit search", params={"keys": ["return"]}),
            WorkflowStep(id="6", app="browser", action="wait", description="Wait for results", params={"seconds": 2}),
            WorkflowStep(id="7", app="browser", action="read_screen", description="Read search results", params={}),
            WorkflowStep(id="8", app="browser", action="click", description="Open first result", params={}),
            WorkflowStep(id="9", app="browser", action="read_screen", description="Read article", params={}),
            WorkflowStep(id="10", app="browser", action="copy", description="Copy key points", params={}),
            WorkflowStep(id="11", app="system", action="return_result", description="Return digest", params={"summary": "Research on '{query}' complete. Key points copied to clipboard."}),
        ],
        examples=[
            "Research Python asyncio best practices and summarize",
            "Search for remote work productivity tips and copy the best ones",
        ],
    )


def _build_meeting_prep() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="meeting_prep",
        name="Meeting Prep",
        description="Check your calendar for the next meeting, look up attendees, and summarize a brief on each.",
        apps_required=["browser"],
        params_schema=[
            {"name": "calendar_url", "label": "Calendar URL", "type": "text", "placeholder": "e.g. https://calendar.google.com"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to calendar", params={"url": "{calendar_url}"}),
            WorkflowStep(id="3", app="browser", action="read_screen", description="Read next meeting", params={}),
            WorkflowStep(id="4", app="browser", action="click", description="Open meeting details", params={}),
            WorkflowStep(id="5", app="browser", action="read_screen", description="Read attendee list", params={}),
            WorkflowStep(id="6", app="browser", action="navigate_to", description="Go to LinkedIn", params={"url": "https://linkedin.com"}),
            WorkflowStep(id="7", app="browser", action="type", description="Search attendee", params={"text": "{attendee_name}"}),
            WorkflowStep(id="8", app="browser", action="hotkey", description="Submit search", params={"keys": ["return"]}),
            WorkflowStep(id="9", app="browser", action="read_screen", description="Read profile summary", params={}),
            WorkflowStep(id="10", app="browser", action="copy", description="Copy brief", params={}),
            WorkflowStep(id="11", app="system", action="return_result", description="Return meeting brief", params={"summary": "Meeting prep complete. Attendee brief copied to clipboard."}),
        ],
        examples=[
            "Prep me for my next meeting by looking up attendees",
            "Check my calendar and brief me on who I'm meeting",
        ],
    )


def _build_status_update() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="status_update",
        name="Status Update",
        description="Gather project status from Jira/Notion and send an update to Slack.",
        apps_required=["browser", "slack"],
        params_schema=[
            {"name": "project_url", "label": "Project Board URL", "type": "text", "placeholder": "e.g. https://notion.so/..."},
            {"name": "slack_channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #general"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to project board", params={"url": "{project_url}"}),
            WorkflowStep(id="3", app="browser", action="read_screen", description="Read project status", params={}),
            WorkflowStep(id="4", app="browser", action="copy", description="Copy status summary", params={}),
            WorkflowStep(id="5", app="slack", action="open_app", description="Open Slack", params={"app_name": "slack"}),
            WorkflowStep(id="6", app="slack", action="focus_window", description="Focus Slack", params={"window_title_pattern": "Slack"}),
            WorkflowStep(id="7", app="slack", action="click", description="Open channel", params={}),
            WorkflowStep(id="8", app="slack", action="paste", description="Paste status update", params={}),
            WorkflowStep(id="9", app="slack", action="hotkey", description="Send message", params={"keys": ["return"]}),
            WorkflowStep(id="10", app="system", action="return_result", description="Confirm delivery", params={"summary": "Status update sent to {slack_channel}."}),
        ],
        examples=[
            "Send a project status update to #general from our Notion board",
            "Post today's Jira sprint status to Slack",
        ],
    )


def _build_approval_loop() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="approval_loop",
        name="Approval Loop",
        description="Open a tool with pending approvals, screenshot each, summarize what needs approval, and ask you yes/no for each.",
        apps_required=["browser"],
        params_schema=[
            {"name": "approvals_url", "label": "Approvals Page URL", "type": "text", "placeholder": "e.g. https://jira.atlassian.com/approvals"},
        ],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", description="Open browser", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", description="Go to approvals", params={"url": "{approvals_url}"}),
            WorkflowStep(id="3", app="browser", action="read_screen", description="Read pending approvals", params={}),
            WorkflowStep(id="4", app="browser", action="screenshot", description="Screenshot approval list", params={}),
            WorkflowStep(id="5", app="system", action="ask_human", description="Ask for approval decision", params={"question": "Approve this item? (yes/no)"}, requires_decision=True),
            WorkflowStep(id="6", app="system", action="return_result", description="Return approval status", params={"summary": "Approval loop complete. Decisions recorded."}),
        ],
        examples=[
            "Run through my pending Jira approvals and ask me for each one",
            "Check my PR approvals and guide me through them",
        ],
    )


def _build_info_gather() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="info_gather",
        name="Info Gather",
        description="Freeform: describe what info you need and the agent searches across apps to find it.",
        apps_required=[],
        params_schema=[
            {"name": "query", "label": "What do you need to know?", "type": "text", "placeholder": "e.g. What is the deadline for the Q3 roadmap?"},
        ],
        steps=None,  # Uses dynamic planner
        examples=[
            "Find the Q3 roadmap deadline",
            "What did Sarah say about the API changes in Slack?",
            "Get me the latest sales numbers from the dashboard",
        ],
    )


# =============================================================
#  REGISTRY
# =============================================================

class TemplateRegistry:
    """Registry of built-in workflow templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, WorkflowTemplate] = {
            t.id: t
            for t in [
                _build_morning_standup(),
                _build_ticket_to_slack(),
                _build_email_triage(),
                _build_research_digest(),
                _build_meeting_prep(),
                _build_status_update(),
                _build_approval_loop(),
                _build_info_gather(),
            ]
        }
        self._planner = WorkflowPlanner()

    def resolve(self, preset_id: str, user_params: Dict[str, Any]) -> WorkflowPlan:
        """Resolve a template ID into a WorkflowPlan, injecting user params."""
        template = self._templates.get(preset_id)
        if template is None:
            log.warning("Unknown preset '%s', returning fallback plan", preset_id)
            return self._fallback_plan(preset_id)

        if template.steps is None:
            # Dynamic planner mode
            query = user_params.get("query", user_params.get("description", " Gather information"))
            return self._planner.plan(query)

        # Static template: inject params and build plan
        injected_steps = self._inject_params(template.steps, user_params)
        return WorkflowPlan(
            intent=template.name,
            apps_required=template.apps_required,
            steps=injected_steps,
            estimated_budget=len(injected_steps) * 2,
            result_type="summary",
        )

    def list_templates(self) -> List[WorkflowTemplate]:
        """Return all registered templates."""
        return list(self._templates.values())

    # ── Internal helpers ───────────────────────────────────────────────────

    def _inject_params(self, steps: List[WorkflowStep], user_params: Dict[str, Any]) -> List[WorkflowStep]:
        """Replace {placeholder} syntax in step params with user-provided values."""
        injected: List[WorkflowStep] = []
        for step in steps:
            new_params: Dict[str, Any] = {}
            for key, val in step.params.items():
                if isinstance(val, str):
                    try:
                        new_params[key] = val.format(**user_params)
                    except KeyError:
                        # Placeholder not provided by user — leave as-is
                        new_params[key] = val
                else:
                    new_params[key] = val
            injected.append(
                WorkflowStep(
                    id=step.id,
                    app=step.app,
                    action=step.action,
                    description=step.description,
                    params=new_params,
                    verification=step.verification,
                    requires_decision=step.requires_decision,
                )
            )
        return injected

    def _fallback_plan(self, preset_id: str) -> WorkflowPlan:
        """Return a safe fallback plan for unknown presets."""
        return WorkflowPlan(
            intent=f"Unknown preset: {preset_id}",
            apps_required=[],
            steps=[
                WorkflowStep(
                    id="1",
                    app="system",
                    action="ask_human",
                    description=f"Preset '{preset_id}' not found",
                    params={"question": f"I don't recognize '{preset_id}'. What would you like me to do?"},
                    requires_decision=True,
                ),
                WorkflowStep(
                    id="2",
                    app="system",
                    action="return_result",
                    description="Awaiting clarification",
                    params={"summary": "Awaiting user input."},
                ),
            ],
            estimated_budget=5,
            result_type="summary",
        )
