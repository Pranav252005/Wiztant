"""Safety guardrails for Agent v2: path sandbox, command whitelist, cost ceiling."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

COST_CEILING_USD = 10.0

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bformat\s+(?:C:|/dev/)"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bnpm\s+publish\b"),
    re.compile(r"\bvercel\s+--prod\b"),
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b"),
]

_COMMAND_WHITELIST = {
    "npx",
    "npm",
    "node",
    "git",
    "tsc",
    "eslint",
    "prettier",
    "curl",
    "mkdir",
    "cp",
    "mv",
    "ls",
    "cat",
    "echo",
    "supabase",
}


def is_destructive_command(command: str) -> bool:
    """Return True if command matches a known destructive pattern."""
    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return True
    return False


def sandbox_path(target: Path, project_root: Path) -> bool:
    """Ensure target is within project_root."""
    try:
        target.resolve().relative_to(project_root.resolve())
        return True
    except ValueError:
        return False


class Guardrails:
    """Per-project guardrail state."""

    def __init__(self, project_path: str) -> None:
        self.project_root = Path(project_path).resolve()
        self.cost_accumulated: float = 0.0
        self.files_created_this_phase: int = 0
        self.max_files_per_phase: int = 15

    def can_spend(self, amount: float) -> bool:
        return (self.cost_accumulated + amount) <= COST_CEILING_USD

    def record_spend(self, amount: float) -> None:
        self.cost_accumulated += amount

    def allow_file_creation(self) -> bool:
        return self.files_created_this_phase < self.max_files_per_phase

    def record_file_created(self) -> None:
        self.files_created_this_phase += 1

    def reset_phase_counter(self) -> None:
        self.files_created_this_phase = 0

    def validate_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Return (ok, reason)."""
        if is_destructive_command(command):
            return False, "destructive command blocked"
        cleaned = re.sub(r"^[A-Z_]+=\S+\s+", "", command).strip()
        first = cleaned.split()[0] if cleaned else ""
        if first and first not in _COMMAND_WHITELIST:
            return False, f"command '{first}' not in whitelist"
        return True, None
