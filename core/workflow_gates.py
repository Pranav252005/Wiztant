"""core/workflow_gates.py — Async Decision Gates for Workflow Mode.

When the agent needs user input mid-workflow, it creates a decision gate.
The user is notified on their desktop and can respond via the overlay.
If no response arrives before the timeout, a safe default is chosen.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("core.workflow_gates")


# Keywords that suggest a destructive or risky action
_DESTRUCTIVE_KEYWORDS = [
    "delete", "remove", "drop", "erase", "wipe", "destroy", "discard",
    "reject", "deny", "cancel", "abort", "revoke", "uninstall",
    "format", "clear", "reset", "purge",
]


@dataclass
class DecisionGate:
    """A single pending decision gate."""

    gate_id: str
    question: str
    options: List[str]
    timeout: float
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    choice: str = ""
    _event: threading.Event = field(default_factory=threading.Event)


class GateManager:
    """Manages creation, waiting, and resolution of workflow decision gates."""

    def __init__(self) -> None:
        self._gates: Dict[str, DecisionGate] = {}
        self._lock = threading.Lock()

    def create_gate(
        self,
        question: str,
        options: List[str],
        timeout: float = 300.0,
    ) -> str:
        """Create a new decision gate and return its ID."""
        gate_id = f"gate_{uuid.uuid4().hex[:8]}"
        gate = DecisionGate(
            gate_id=gate_id,
            question=question,
            options=options or ["yes", "no"],
            timeout=timeout,
        )
        with self._lock:
            self._gates[gate_id] = gate
        log.info("Created gate %s: %s (options=%s, timeout=%s)", gate_id, question, options, timeout)
        return gate_id

    def await_decision(self, gate_id: str) -> str:
        """Block until the gate is resolved or times out. Returns the choice."""
        with self._lock:
            gate = self._gates.get(gate_id)
        if gate is None:
            log.warning("await_decision called for unknown gate %s", gate_id)
            return self._safe_default("unknown")

        # Wait for the event or timeout
        gate._event.wait(timeout=gate.timeout)

        with self._lock:
            gate.resolved = True
            if gate.choice:
                log.info("Gate %s resolved with choice: %s", gate_id, gate.choice)
                return gate.choice
            else:
                default = self._safe_default(gate.question)
                log.info("Gate %s timed out, using safe default: %s", gate_id, default)
                return default

    def resolve(self, gate_id: str, choice: str) -> bool:
        """Resolve a gate with the user's choice. Returns True if successful."""
        with self._lock:
            gate = self._gates.get(gate_id)
            if gate is None:
                log.warning("resolve called for unknown gate %s", gate_id)
                return False
            gate.choice = choice
            gate.resolved = True
            gate._event.set()
        log.info("Gate %s manually resolved with: %s", gate_id, choice)
        return True

    def get_gate(self, gate_id: str) -> Optional[DecisionGate]:
        """Return a gate by ID, or None if not found."""
        with self._lock:
            return self._gates.get(gate_id)

    def cleanup(self, gate_id: str) -> None:
        """Remove a gate from memory."""
        with self._lock:
            self._gates.pop(gate_id, None)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _safe_default(self, question: str) -> str:
        """Determine the safe default choice based on the question content."""
        lower_q = question.lower()
        if any(kw in lower_q for kw in _DESTRUCTIVE_KEYWORDS):
            return "no"
        return "yes"
