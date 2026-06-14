"""core/workflow_result.py — Workflow Result Summarizer & Delivery.

Compresses a workflow action log into a human-readable summary via LLM,
then delivers the result to the user through clipboard, WebSocket, and pill.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.agent_engine import call_api, OMNI_MODEL, TEMP_THINK, THINK_MAX_TOKENS

log = logging.getLogger("core.workflow_result")


_SUMMARIZER_PROMPT = """You are a Workflow Result Summarizer. The agent just completed a workflow across multiple apps.

Here is the action log (JSON):
{action_log}

Summarize what was accomplished in 1-3 sentences.
If a specific answer was found (e.g., a ticket number, a reply, a price), state it clearly.
If the workflow failed, explain why and what the user should do next.
Be concise. The user is busy.
"""


class WorkflowResult:
    """Summarizes workflow action logs and delivers results to the user."""

    def summarize(self, action_log: List[Dict[str, Any]]) -> str:
        """Summarize an action log into a concise human-readable string."""
        if not action_log:
            return "No actions were recorded."

        log_json = "\n".join(
            f"- {entry['action']}: {entry.get('result', 'no result')}"
            for entry in action_log
        )

        messages = [
            {"role": "system", "content": "You are a concise workflow summarizer."},
            {"role": "user", "content": _SUMMARIZER_PROMPT.format(action_log=log_json)},
        ]

        try:
            summary = call_api(
                model=OMNI_MODEL,
                messages=messages,
                temperature=TEMP_THINK,
                max_tokens=THINK_MAX_TOKENS,
            )
        except Exception as e:
            log.error("Summarization API call failed: %s", e)
            summary = "Workflow completed, but I couldn't generate a summary."

        return summary.strip() or "Workflow completed."

    def deliver(
        self,
        result_text: str,
        ws_bridge: Any,
        system_access: Any,
    ) -> None:
        """Deliver a result to the user via clipboard, overlay, and pill."""
        # 1. Copy to clipboard
        try:
            system_access.set_clipboard(result_text)
        except Exception as e:
            log.warning("Clipboard copy failed: %s", e)

        # 2. Broadcast to overlay
        try:
            ws_bridge.broadcast_sync({
                "type": "workflow/result",
                "summary": result_text,
            })
        except Exception as e:
            log.warning("WebSocket broadcast failed: %s", e)

        # 3. Pill notification
        try:
            ws_bridge.broadcast_sync({
                "type": "pill/notice",
                "message": self._truncate(result_text, 60),
            })
        except Exception as e:
            log.warning("Pill notice failed: %s", e)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."
