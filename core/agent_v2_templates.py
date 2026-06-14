"""
core/agent_v2_templates.py — Pre-built workflow templates for the Bridge Agent.

Templates encode multi-app recipes that the agent can execute without planning
from scratch every time. Each template defines a sequence of steps across apps.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger("core.agent_v2_templates")


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class WorkflowStep:
    """A single step in a workflow template."""

    id: int
    app: str  # profile name: terminal, browser, cursor, etc.
    action: str  # action type: check_ssh_key, generate_ssh_key, open_url, click, type, etc.
    description: str = ""
    command: Optional[str] = None  # for terminal actions
    url: Optional[str] = None  # for browser actions
    ui_target: Optional[str] = None  # for UI-TARS actions
    input_text: Optional[str] = None  # text to type
    verification: Optional[str] = None  # how to verify completion
    auto_inputs: List[str] = field(default_factory=list)  # auto-pressed keys (e.g., ["\n", "\n"])
    on_fail: Optional[str] = None  # step to jump to on failure
    on_success: Optional[str] = None  # step to jump to on success
    requires_decision: bool = False  # pause for Accept/Deny after this step
    step_cost: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "app": self.app,
            "action": self.action,
            "description": self.description,
            "command": self.command,
            "url": self.url,
            "ui_target": self.ui_target,
            "input_text": self.input_text,
            "verification": self.verification,
            "auto_inputs": self.auto_inputs,
            "on_fail": self.on_fail,
            "on_success": self.on_success,
            "requires_decision": self.requires_decision,
            "step_cost": self.step_cost,
        }


@dataclass
class WorkflowTemplate:
    """A reusable multi-app workflow recipe."""

    id: str
    name: str
    apps_required: List[str]
    estimated_steps: int
    estimated_budget: int
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "apps_required": self.apps_required,
            "estimated_steps": self.estimated_steps,
            "estimated_budget": self.estimated_budget,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }


# =============================================================
#  BUILT-IN TEMPLATES
# =============================================================

CLIPBOARD_CMD = (
    "xclip -selection clipboard"
    if __import__("subprocess").run(["which", "xclip"], capture_output=True).returncode == 0
    else "xsel --clipboard --input"
    if __import__("subprocess").run(["which", "xsel"], capture_output=True).returncode == 0
    else "cat"
)


def _github_ssh_clone() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="github_ssh_clone",
        name="Clone Private GitHub Repo",
        apps_required=["terminal", "browser"],
        estimated_steps=9,
        estimated_budget=15,
        description="Generate SSH key, add to GitHub, clone private repo",
        steps=[
            WorkflowStep(
                id=1,
                app="terminal",
                action="check_ssh_key",
                description="Check for existing SSH key",
                command="ls ~/.ssh/id_*.pub",
                verification="output_contains_id_ed25519",
                on_fail="continue_to_step_2",
                on_success="skip_to_step_4",
            ),
            WorkflowStep(
                id=2,
                app="terminal",
                action="generate_ssh_key",
                description="Generate new SSH key",
                command="ssh-keygen -t ed25519 -C '{user_email}'",
                verification="key_files_created",
                auto_inputs=["\n", "\n"],
            ),
            WorkflowStep(
                id=3,
                app="terminal",
                action="copy_public_key",
                description="Copy public key to clipboard",
                command="cat ~/.ssh/id_ed25519.pub | {clipboard_cmd}",
                verification="clipboard_contains_ssh_key",
            ),
            WorkflowStep(
                id=4,
                app="browser",
                action="open_github_keys",
                description="Open GitHub SSH keys settings",
                url="https://github.com/settings/keys",
                verification="page_title_contains_SSH",
            ),
            WorkflowStep(
                id=5,
                app="browser",
                action="click_new_key",
                description="Click 'New SSH key' button",
                ui_target="new_ssh_key_button",
                verification="form_visible",
            ),
            WorkflowStep(
                id=6,
                app="browser",
                action="type_key_title",
                description="Type SSH key title",
                input_text="{machine_name}",
                verification="title_field_filled",
            ),
            WorkflowStep(
                id=7,
                app="browser",
                action="paste_key",
                description="Paste SSH key into key field",
                verification="key_field_filled",
            ),
            WorkflowStep(
                id=8,
                app="browser",
                action="click_add_key",
                description="Click 'Add SSH key' button",
                ui_target="add_ssh_key_button",
                verification="success_message_or_key_listed",
                requires_decision=True,
            ),
            WorkflowStep(
                id=9,
                app="terminal",
                action="git_clone",
                description="Clone the repository",
                command="git clone {repo_url}",
                verification="clone_success_message",
            ),
        ],
    )


def _figma_to_cursor_component() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="figma_to_cursor_component",
        name="Figma to Cursor Component",
        apps_required=["figma", "cursor"],
        estimated_steps=6,
        estimated_budget=12,
        description="See a design in Figma, create matching component in Cursor",
        steps=[
            WorkflowStep(
                id=1,
                app="figma",
                action="screenshot_component",
                description="Screenshot the selected component in Figma",
                verification="screenshot_captured",
            ),
            WorkflowStep(
                id=2,
                app="cursor",
                action="analyze_design",
                description="Vision analysis extracts colors, sizes, spacing",
                verification="design_specs_extracted",
            ),
            WorkflowStep(
                id=3,
                app="cursor",
                action="create_file",
                description="Create new component file",
                input_text="{component_path}",
                verification="file_created",
            ),
            WorkflowStep(
                id=4,
                app="cursor",
                action="type_prompt",
                description="Type component generation prompt into Cursor chat",
                input_text="Create a {component_name} component with these exact specs: {design_specs}",
                verification="prompt_submitted",
            ),
            WorkflowStep(
                id=5,
                app="cursor",
                action="wait_generation",
                description="Wait for Cursor to generate the component",
                verification="generation_complete",
            ),
            WorkflowStep(
                id=6,
                app="cursor",
                action="ask_accept",
                description="Ask user to accept the generated component",
                requires_decision=True,
                verification="user_decided",
            ),
        ],
    )


def _terminal_error_to_cursor_fix() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="terminal_error_to_cursor_fix",
        name="Terminal Error to Cursor Fix",
        apps_required=["terminal", "cursor"],
        estimated_steps=5,
        estimated_budget=8,
        description="Copy terminal error, find file, tell Cursor to fix",
        steps=[
            WorkflowStep(
                id=1,
                app="terminal",
                action="detect_error",
                description="Detect error in clipboard or screenshot",
                verification="error_detected",
            ),
            WorkflowStep(
                id=2,
                app="cursor",
                action="identify_file",
                description="Identify likely file from error stack trace or file tree",
                verification="file_identified",
            ),
            WorkflowStep(
                id=3,
                app="cursor",
                action="type_fix_prompt",
                description="Type fix prompt into Cursor chat",
                input_text="Fix this error in {file_path}: {error_message}",
                verification="prompt_submitted",
            ),
            WorkflowStep(
                id=4,
                app="cursor",
                action="wait_generation",
                description="Wait for Cursor to generate the fix",
                verification="generation_complete",
            ),
            WorkflowStep(
                id=5,
                app="cursor",
                action="ask_accept",
                description="Ask user to accept the fix",
                requires_decision=True,
                verification="user_decided",
            ),
        ],
    )


def _jira_commit_push() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="jira_commit_push",
        name="Jira Commit & Push",
        apps_required=["browser", "terminal"],
        estimated_steps=8,
        estimated_budget=12,
        description="Update Jira ticket, write commit, push",
        steps=[
            WorkflowStep(
                id=1,
                app="browser",
                action="open_jira_ticket",
                description="Open Jira ticket URL",
                url="{jira_ticket_url}",
                verification="ticket_page_loaded",
            ),
            WorkflowStep(
                id=2,
                app="browser",
                action="transition_ticket",
                description="Click 'Start Progress' or 'Done'",
                ui_target="transition_button",
                verification="status_changed",
            ),
            WorkflowStep(
                id=3,
                app="browser",
                action="add_comment",
                description="Add comment with commit message",
                input_text="{commit_message}",
                verification="comment_posted",
            ),
            WorkflowStep(
                id=4,
                app="terminal",
                action="git_add",
                description="Stage all changes",
                command="git add .",
                verification="files_staged",
            ),
            WorkflowStep(
                id=5,
                app="terminal",
                action="git_commit",
                description="Write commit with ticket ID",
                command='git commit -m "{ticket_id}: {commit_message}"',
                verification="commit_created",
            ),
            WorkflowStep(
                id=6,
                app="terminal",
                action="git_push",
                description="Push to current branch",
                command="git push origin {current_branch}",
                verification="push_successful",
            ),
            WorkflowStep(
                id=7,
                app="browser",
                action="refresh_ticket",
                description="Refresh Jira ticket",
                verification="linked_commit_visible",
            ),
            WorkflowStep(
                id=8,
                app="browser",
                action="ask_accept",
                description="Ask user to accept the workflow",
                requires_decision=True,
                verification="user_decided",
            ),
        ],
    )


def _slack_to_notion_prd() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="slack_to_notion_prd",
        name="Slack to Notion PRD",
        apps_required=["slack", "notion"],
        estimated_steps=5,
        estimated_budget=8,
        description="Copy Slack requirements message, create structured PRD in Notion",
        steps=[
            WorkflowStep(
                id=1,
                app="slack",
                action="detect_requirements",
                description="Detect copied message with requirements",
                verification="requirements_detected",
            ),
            WorkflowStep(
                id=2,
                app="notion",
                action="create_new_page",
                description="Open new page in Product workspace",
                url="https://notion.so/new",
                verification="new_page_open",
            ),
            WorkflowStep(
                id=3,
                app="notion",
                action="type_title",
                description="Type PRD title",
                input_text="PRD: {project_name}",
                verification="title_filled",
            ),
            WorkflowStep(
                id=4,
                app="notion",
                action="paste_structured_content",
                description="Paste structured content: Problem, Solution, Features, Timeline",
                verification="content_pasted",
            ),
            WorkflowStep(
                id=5,
                app="notion",
                action="format_page",
                description="Format headers, add toggle lists",
                verification="formatting_complete",
            ),
        ],
    )


# =============================================================
#  TEMPLATE REGISTRY
# =============================================================

class TemplateRegistry:
    """Registry of workflow templates for the Bridge Agent."""

    def __init__(self) -> None:
        self._templates: dict[str, WorkflowTemplate] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for builder in (
            _github_ssh_clone,
            _jira_commit_push,
            _slack_to_notion_prd,
        ):
            tpl = builder()
            self._templates[tpl.id] = tpl
        self._load_learned_templates()

    def _load_learned_templates(self) -> None:
        """Load previously learned templates from disk."""
        try:
            from core.tune_hub.adaptive_matcher import load_learned_templates
            learned = load_learned_templates()
            for data in learned:
                try:
                    steps = [WorkflowStep(**s) for s in data.get("steps", [])]
                    tpl = WorkflowTemplate(
                        id=data["template_id"],
                        name=data.get("name", data["template_id"]),
                        apps_required=data.get("apps_required", []),
                        estimated_steps=data.get("estimated_steps", len(steps)),
                        estimated_budget=data.get("estimated_budget", 20),
                        description=data.get("description", ""),
                        steps=steps,
                    )
                    self._templates[tpl.id] = tpl
                except Exception as e:
                    import logging
                    logging.getLogger("core.agent_v2_templates").warning("Failed to load learned template %s: %s", data.get("template_id"), e)
        except Exception:
            pass  # Graceful fallback if adaptive_matcher not available

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_all(self) -> List[WorkflowTemplate]:
        """List all registered templates."""
        return list(self._templates.values())

    def list_ids(self) -> List[str]:
        """List all registered template IDs."""
        return list(self._templates.keys())

    def register(self, template: WorkflowTemplate) -> None:
        """Register a custom template."""
        self._templates[template.id] = template

    def render_step(
        self,
        step: WorkflowStep,
        params: Dict[str, Any],
    ) -> WorkflowStep:
        """Render a step's dynamic fields with user-provided parameters."""
        data = step.to_dict()
        for key in ("command", "url", "input_text", "ui_target", "verification"):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = val.format(
                    user_email=params.get("user_email", "user@example.com"),
                    machine_name=params.get("machine_name", "Wiztant-Machine"),
                    repo_url=params.get("repo_url", ""),
                    component_name=params.get("component_name", "Component"),
                    component_path=params.get("component_path", "components/Component.tsx"),
                    design_specs=params.get("design_specs", ""),
                    file_path=params.get("file_path", ""),
                    error_message=params.get("error_message", ""),
                    jira_ticket_url=params.get("jira_ticket_url", ""),
                    ticket_id=params.get("ticket_id", ""),
                    commit_message=params.get("commit_message", ""),
                    current_branch=params.get("current_branch", "main"),
                    project_name=params.get("project_name", "New Project"),
                    clipboard_cmd=CLIPBOARD_CMD,
                )
        return WorkflowStep(**data)

    def render_template(
        self,
        template_id: str,
        params: Dict[str, Any],
    ) -> Optional[WorkflowTemplate]:
        """Render a full template with user-provided parameters."""
        tpl = self.get(template_id)
        if tpl is None:
            return None
        rendered_steps = [self.render_step(s, params) for s in tpl.steps]
        return WorkflowTemplate(
            id=tpl.id,
            name=tpl.name,
            apps_required=tpl.apps_required,
            estimated_steps=tpl.estimated_steps,
            estimated_budget=tpl.estimated_budget,
            description=tpl.description,
            steps=rendered_steps,
        )


# Singleton registry
_default_registry: Optional[TemplateRegistry] = None


def get_registry() -> TemplateRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = TemplateRegistry()
    return _default_registry
