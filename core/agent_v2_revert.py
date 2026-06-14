"""
core/agent_v2_revert.py — Revert sequences for the Bridge Agent.

When the user denies a destructive or significant action, this module knows
how to undo it on a per-app, per-action-type basis.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("core.agent_v2_revert")


# =============================================================
#  REVERT ACTION
# =============================================================

@dataclass
class RevertAction:
    """A single revert step."""

    description: str
    app: str = "terminal"
    command: Optional[str] = None
    ui_task: Optional[str] = None


# =============================================================
#  REVERT SEQUENCES BY ACTION TYPE
# =============================================================

REVERT_SEQUENCES: Dict[str, List[RevertAction]] = {
    "git_commit": [
        RevertAction(
            description="Undo last commit, keep changes",
            app="terminal",
            command="git reset --soft HEAD~1",
        ),
    ],
    "git_push": [
        RevertAction(
            description="Force-push previous state (destructive — use with caution)",
            app="terminal",
            command="git push origin +HEAD~1:HEAD",
        ),
    ],
    "git_add": [
        RevertAction(
            description="Unstage all changes",
            app="terminal",
            command="git reset HEAD",
        ),
    ],
    "github_ssh_key": [
        RevertAction(
            description="Delete local SSH key",
            app="terminal",
            command="rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub",
        ),
        RevertAction(
            description="Open GitHub settings to delete key manually",
            app="browser",
            ui_task="Navigate to GitHub → Settings → SSH Keys → Delete the key",
        ),
    ],
    "file_create": [
        RevertAction(
            description="Delete created file",
            app="terminal",
            command="rm -f {file_path}",
        ),
    ],
    "cursor_chat": [
        RevertAction(
            description="Revert Cursor chat / undo last edit",
            app="cursor",
            ui_task="Press Ctrl+Z or use Cursor's revert button",
        ),
    ],
    "jira_comment": [
        RevertAction(
            description="Open Jira and delete the comment",
            app="browser",
            ui_task="Navigate to ticket → Comments → Delete comment",
        ),
    ],
    "jira_transition": [
        RevertAction(
            description="Transition Jira ticket back to previous state",
            app="browser",
            ui_task="Navigate to ticket → Transition back to previous status",
        ),
    ],
    "notion_page": [
        RevertAction(
            description="Move Notion page to trash",
            app="browser",
            ui_task="Open page → ⋮ → Move to trash",
        ),
    ],
    "npm_install": [
        RevertAction(
            description="Remove installed packages and restore lockfile",
            app="terminal",
            command="git checkout -- package-lock.json pnpm-lock.yaml yarn.lock 2>/dev/null; git checkout -- node_modules 2>/dev/null; rm -rf node_modules",
        ),
    ],
}


# =============================================================
#  REVERT ENGINE
# =============================================================

class RevertEngine:
    """
    Knows how to undo actions performed by the Bridge Agent.

    Each action type has a predefined revert sequence. The engine can
    execute terminal commands directly, or return UI tasks for apps
    that need manual intervention.
    """

    def __init__(self) -> None:
        self._sequences = dict(REVERT_SEQUENCES)

    def get_revert_sequence(self, action_type: str) -> List[RevertAction]:
        """Get the revert sequence for an action type."""
        return self._sequences.get(action_type, [])

    def register_sequence(self, action_type: str, sequence: List[RevertAction]) -> None:
        """Register a custom revert sequence."""
        self._sequences[action_type] = sequence

    def render_sequence(
        self,
        action_type: str,
        context: Dict[str, Any],
    ) -> List[RevertAction]:
        """
        Render a revert sequence with context variables substituted.

        Example context: {"file_path": "components/Button.tsx"}
        """
        sequence = self.get_revert_sequence(action_type)
        rendered: List[RevertAction] = []
        for step in sequence:
            cmd = step.command
            if cmd:
                try:
                    cmd = cmd.format(**context)
                except KeyError:
                    pass  # Keep unsubstituted if key missing
            rendered.append(RevertAction(
                description=step.description,
                app=step.app,
                command=cmd,
                ui_task=step.ui_task,
            ))
        return rendered

    def execute_terminal_revert(self, action: RevertAction) -> tuple[bool, str]:
        """Execute a terminal-based revert action."""
        if not action.command:
            return False, "No command"
        try:
            result = subprocess.run(
                action.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, result.stdout or "OK"
            return False, result.stderr or "Command failed"
        except Exception as e:
            return False, str(e)

    def revert(self, action_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a full revert sequence for an action type.

        Returns a result dict with:
        - success: bool
        - steps: list of {description, success, output}
        - manual_steps: list of UI tasks that need human action
        """
        sequence = self.render_sequence(action_type, context)
        results = []
        manual_steps = []

        for step in sequence:
            if step.command and step.app == "terminal":
                ok, output = self.execute_terminal_revert(step)
                results.append({
                    "description": step.description,
                    "app": step.app,
                    "success": ok,
                    "output": output,
                })
                if not ok:
                    log.warning("Revert step failed: %s — %s", step.description, output)
            elif step.ui_task:
                manual_steps.append({
                    "description": step.description,
                    "app": step.app,
                    "task": step.ui_task,
                })

        return {
            "success": all(r["success"] for r in results) if results else True,
            "steps": results,
            "manual_steps": manual_steps,
        }


# Singleton
_default_engine: Optional[RevertEngine] = None


def get_engine() -> RevertEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = RevertEngine()
    return _default_engine
