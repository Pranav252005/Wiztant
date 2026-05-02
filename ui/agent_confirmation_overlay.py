import threading
import time
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

import core as state
from ui.react_overlay import show_react_overlay
from ui.theme import app_theme


@dataclass
class TaskConfirmation:
    task_name: str
    description: str
    steps_summary: list[str]
    estimated_time_seconds: int
    is_reversible: bool
    complications: list[str]
    full_plan: dict
    task_id: str


class AgentConfirmationOverlay:
    """
    Bridge-backed confirmation overlay shown inside the Electron/React overlay.

    Design notes from youthful-thompson / Claude-inspired surfaces:
    - rounded glass panel with soft border + elevated shadow
    - muted copy with stronger display title
    - quick 180-300ms slide/fade motion instead of abrupt modal jumps
    - compact minimize state that preserves context without blocking the user
    """

    def __init__(self):
        self.is_visible = False
        self.is_minimized = False
        self.pending_confirmation: dict[str, Any] | None = None
        self.user_choice: str | None = None
        self._choice_event = threading.Event()
        self._lock = threading.Lock()

    def _normalize_confirmation(self, confirmation_data: Any) -> dict[str, Any]:
        if is_dataclass(confirmation_data):
            data = asdict(confirmation_data)
        elif hasattr(confirmation_data, "__dict__") and not isinstance(confirmation_data, dict):
            data = dict(vars(confirmation_data))
        else:
            data = dict(confirmation_data)

        data.setdefault("task_type", "agent")
        data.setdefault("estimated_time", data.get("estimated_time_seconds", 0))
        data.setdefault("steps_summary", [])
        data.setdefault("complications", [])
        data.setdefault("full_plan", {})
        data.setdefault("task_id", "")
        data["themeVars"] = app_theme.to_css_var_map()
        data["themeName"] = app_theme.current_theme
        data["logoPath"] = str(app_theme.logo_path)
        return data

    def show_confirmation(self, confirmation_data: Any) -> str:
        payload = self._normalize_confirmation(confirmation_data)
        with self._lock:
            self.pending_confirmation = payload
            self.is_visible = True
            self.is_minimized = False
            self.user_choice = None
            self._choice_event.clear()
            state._agent_confirmation_overlay_active = True
            state._agent_confirmation_overlay_minimized = False

        show_react_overlay()
        time.sleep(0.2)
        self._broadcast("show", payload)

        self._choice_event.wait(timeout=300)
        choice = self.user_choice or "cancel"
        if choice == "cancel" and self.is_visible:
            self.hide()
        self.user_choice = None
        return choice

    def show_detail_overlay(self, confirmation_data: Any):
        payload = self._normalize_confirmation(confirmation_data)
        self._broadcast("show", payload | {"detailOpen": True})

    def minimize(self):
        with self._lock:
            if not self.is_visible:
                return
            self.is_minimized = True
            state._agent_confirmation_overlay_minimized = True
        self._broadcast("minimize")

    def restore(self):
        with self._lock:
            if not self.is_visible:
                return
            self.is_minimized = False
            state._agent_confirmation_overlay_minimized = False
        self._broadcast("restore")

    def toggle(self):
        if self.is_minimized:
            self.restore()
        else:
            self.minimize()

    def hide(self):
        with self._lock:
            self.is_visible = False
            self.is_minimized = False
            self.pending_confirmation = None
            state._agent_confirmation_overlay_active = False
            state._agent_confirmation_overlay_minimized = False
        self._broadcast("hide")

    def on_user_choice(self, choice: str):
        with self._lock:
            self.user_choice = choice
            self.is_visible = False
            self.is_minimized = False
            state._agent_confirmation_overlay_active = False
            state._agent_confirmation_overlay_minimized = False
        self._broadcast("hide")
        self._choice_event.set()

    def get_bridge_snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.is_visible or not self.pending_confirmation:
                return None
            payload = dict(self.pending_confirmation)
            payload["minimized"] = self.is_minimized
            return {
                "type": "agent_confirmation",
                "action": "show",
                "payload": payload,
            }

    def has_active_confirmation(self) -> bool:
        with self._lock:
            return self.is_visible

    def _broadcast(self, action: str, payload: dict[str, Any] | None = None):
        from core.ws_bridge import broadcast_sync

        message = {"type": "agent_confirmation", "action": action}
        if payload is not None:
            message["payload"] = payload
        broadcast_sync(message)


_instance: AgentConfirmationOverlay | None = None
_instance_lock = threading.Lock()


def get_agent_confirmation_overlay() -> AgentConfirmationOverlay:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = AgentConfirmationOverlay()
    return _instance


def show_confirmation(confirmation: TaskConfirmation) -> str:
    return get_agent_confirmation_overlay().show_confirmation(confirmation)


def show_detail_overlay(confirmation: TaskConfirmation):
    get_agent_confirmation_overlay().show_detail_overlay(confirmation)
