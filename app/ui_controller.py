"""app/ui_controller.py — Orchestrates UI overlays without moving the cross-platform overlay code.

The actual overlay implementations (Electron, tkinter) live in `ui/`.
This module is the conductor that imports and manages them.
"""
from __future__ import annotations

import threading
from typing import Any, Optional


class UIController:
    """Manages the lifecycle of all UI overlays."""

    def __init__(self):
        self._react_overlay = None
        self._chat_overlay = None
        self._agent_overlay = None

    # ── React / Electron overlay ────────────────────────────────────────────────

    def start_react_overlay(self) -> bool:
        """Start the React/Electron overlay process if not running."""
        try:
            from ui.react_overlay import ensure_react_overlay_running
            ensure_react_overlay_running()
            return True
        except Exception as e:
            print(f"[UIController] React overlay start error: {e}")
            return False

    def show_react_overlay(self) -> None:
        try:
            from ui.react_overlay import show_react_overlay
            show_react_overlay()
        except Exception as e:
            print(f"[UIController] Show overlay error: {e}")

    def hide_react_overlay(self) -> None:
        try:
            from ui.react_overlay import hide_react_overlay_if_visible
            hide_react_overlay_if_visible()
        except Exception as e:
            print(f"[UIController] Hide overlay error: {e}")

    def toggle_react_overlay(self) -> None:
        try:
            from ui.react_overlay import toggle_react_overlay
            toggle_react_overlay()
        except Exception as e:
            print(f"[UIController] Toggle overlay error: {e}")

    def stop_react_overlay(self) -> None:
        try:
            from ui.react_overlay import stop_overlay
            stop_overlay()
        except Exception as e:
            print(f"[UIController] Stop overlay error: {e}")

    # ── Python tkinter overlays ─────────────────────────────────────────────────

    def show_chat_overlay(self) -> None:
        try:
            from ui.chat_overlay import show_chat_overlay
            show_chat_overlay()
        except Exception as e:
            print(f"[UIController] Tune overlay error: {e}")

    def show_agent_confirmation(self, task: str, on_confirm, on_cancel) -> None:
        try:
            from ui.agent_confirmation_overlay import show_confirmation_overlay
            show_confirmation_overlay(task, on_confirm, on_cancel)
        except Exception as e:
            print(f"[UIController] Agent confirmation error: {e}")

    def show_agent_results(self) -> None:
        try:
            from ui.agent_results_panel import show_results_panel
            show_results_panel()
        except Exception as e:
            print(f"[UIController] Agent results error: {e}")


# ── Singleton ─────────────────────────────────────────────────────────────────

_ui_controller: Optional[UIController] = None


def get_ui_controller() -> UIController:
    global _ui_controller
    if _ui_controller is None:
        _ui_controller = UIController()
    return _ui_controller
