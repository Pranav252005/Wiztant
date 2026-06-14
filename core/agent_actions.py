"""
core/agent_actions.py — Action dataclasses, parsing, and execution runtime for the Three-Brain Agent.

Wraps the platform agent runtime with safety bounds and step-cost tracking.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("core.agent_actions")

# Placeholder the agent may emit to type a stored secret without the secret ever
# passing through the LLM. Form: {{cred:App Name:field_key}}  e.g. {{cred:Slack:password}}
_CRED_PLACEHOLDER = re.compile(r"\{\{\s*cred:([^:}]+):([^}]+?)\s*\}\}")


def _resolve_credentials(text: str) -> str:
    """Replace {{cred:App:field}} placeholders with vault values at type time."""
    if not text or "{{cred:" not in text:
        return text

    def _sub(m: "re.Match[str]") -> str:
        app, field = m.group(1).strip(), m.group(2).strip()
        try:
            from core.integrations import get_credentials
            creds = get_credentials(app)
            if creds:
                val = (creds.get("fields") or {}).get(field)
                if val is not None:
                    return val
        except Exception as e:
            log.warning("credential resolve failed for %s.%s: %s", app, field, e)
        return ""  # unknown credential — type nothing rather than the placeholder

    return _CRED_PLACEHOLDER.sub(_sub, text)

# =============================================================
#  ACTION DATACLASSES
# =============================================================

@dataclass
class ClickAction:
    x_norm: float
    y_norm: float
    button: str = "left"
    step_cost: float = 1.0

@dataclass
class DoubleClickAction:
    x_norm: float
    y_norm: float
    button: str = "left"
    step_cost: float = 1.0

@dataclass
class TypeAction:
    text: str
    step_cost: float = 1.0

    def __post_init__(self):
        if len(self.text) > 100:
            self.step_cost = 2.0

@dataclass
class PressAction:
    key: str
    step_cost: float = 0.5

@dataclass
class ScrollAction:
    x_norm: float
    y_norm: float
    direction: str  # "up" or "down"
    amount: int = 3
    step_cost: float = 1.0

@dataclass
class WaitAction:
    seconds: float = 1.5
    step_cost: float = 0.0

@dataclass
class DragAction:
    x1_norm: float
    y1_norm: float
    x2_norm: float
    y2_norm: float
    step_cost: float = 2.0


AgentAction = ClickAction | DoubleClickAction | TypeAction | PressAction | ScrollAction | WaitAction | DragAction


# =============================================================
#  ACTION PARSER
# =============================================================

def _strip_quotes(val: str) -> str:
    """Remove surrounding quotes from a string."""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def _extract_coords(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract x,y coordinates from various UI-TARS formats.

    Handles:
        (0.45,0.67)     -> normalized
        (868,131)       -> absolute pixels
        start_box='(868,131)' -> absolute pixels from start_box
    """
    # Try start_box format: start_box='(868,131)'
    m = re.search(r"start_box\s*=\s*['\"]\((\d+),(\d+)\)['\"]", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))

    # Try plain coordinates: (0.45,0.67) or (868,131)
    m = re.search(r"\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    return None, None


def _is_absolute_pixel(x: float, y: float) -> bool:
    """Detect whether coordinates are absolute pixels (>1.0) or normalized (0-1)."""
    return x > 1.0 or y > 1.0


def _normalize_if_needed(x: float, y: float, screen_w: int = 1920, screen_h: int = 1080) -> Tuple[float, float]:
    """Convert absolute pixels to normalized 0-1 coordinates."""
    if _is_absolute_pixel(x, y):
        return min(x / screen_w, 1.0), min(y / screen_h, 1.0)
    return x, y


def parse_ui_tars_output(raw: str, screen_w: int = 1920, screen_h: int = 1080) -> List[AgentAction]:
    """
    Parse UI-TARS raw output into structured actions.

    Supports multiple formats that different UI-TARS model versions return:
        CLICK(0.12,0.89)                    # normalized (legacy)
        CLICK(start_box='(868,131)')        # absolute pixels (OpenRouter UI-TARS 1.5)
        LEFT_DOUBLE_CLICK(start_box='(868,131)')
        RIGHT_CLICK(start_box='(868,131)')
        TYPE(content='hello')               # newer UI-TARS format
        TYPE("hello") or TYPE(hello)        # older / simplified format
        PRESS("enter") or PRESS(enter)
        SCROLL(start_box='(500,500)', direction='down', scroll_offset=3)
        SCROLL("down",3)
        WAIT(2)
        DRAG(start_box='(100,100)', end_box='(200,200)')
        DRAG(0.1,0.2,0.3,0.4)
    """
    actions: List[AgentAction] = []
    if not raw:
        return actions

    # Strip outer quotes that some APIs wrap responses in
    raw = _strip_quotes(raw.strip())

    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # --- CLICK variants ---
        if re.match(r'CLICK\b', line, re.IGNORECASE) and not re.match(r'DOUBLE_CLICK|RIGHT_CLICK', line, re.IGNORECASE):
            x, y = _extract_coords(line)
            if x is not None and y is not None:
                xn, yn = _normalize_if_needed(x, y, screen_w, screen_h)
                actions.append(ClickAction(x_norm=xn, y_norm=yn))
                continue

        # --- LEFT_DOUBLE_CLICK / DOUBLE_CLICK ---
        if re.match(r'(LEFT_)?DOUBLE_CLICK\b', line, re.IGNORECASE):
            x, y = _extract_coords(line)
            if x is not None and y is not None:
                xn, yn = _normalize_if_needed(x, y, screen_w, screen_h)
                actions.append(DoubleClickAction(x_norm=xn, y_norm=yn))
                continue

        # --- RIGHT_CLICK ---
        if re.match(r'RIGHT_CLICK\b', line, re.IGNORECASE):
            x, y = _extract_coords(line)
            if x is not None and y is not None:
                xn, yn = _normalize_if_needed(x, y, screen_w, screen_h)
                # Right-click via ClickAction with right button
                actions.append(ClickAction(x_norm=xn, y_norm=yn, button="right"))
                continue

        # --- TYPE variants ---
        # TYPE(content='hello') or TYPE("hello") or TYPE(hello)
        m = re.search(r'TYPE\s*\(\s*(?:content\s*=\s*)?[\'"]?([^\'"\)]*)[\'"]?\s*\)', line, re.IGNORECASE)
        if m:
            text = m.group(1).strip()
            if text:
                actions.append(TypeAction(text=text))
                continue

        # --- PRESS / HOTKEY variants ---
        # PRESS("enter") or PRESS(enter) or HOTKEY(['ctrl','c'])
        m = re.search(r'PRESS\s*\(\s*[\'"]?([^\'"\)]*)[\'"]?\s*\)', line, re.IGNORECASE)
        if m:
            key = m.group(1).lower().strip()
            if key:
                actions.append(PressAction(key=key))
                continue

        # HOTKEY(['ctrl', 'c']) -> translate to PressAction with combined key
        m = re.search(r'HOTKEY\s*\(\s*\[(.*?)\]\s*\)', line, re.IGNORECASE)
        if m:
            keys_raw = m.group(1)
            keys = [k.strip().strip("'\"").lower() for k in keys_raw.split(",") if k.strip()]
            if keys:
                # Store as a single press with '+' separator for downstream handling
                actions.append(PressAction(key="+".join(keys)))
                continue

        # --- SCROLL variants ---
        # SCROLL(start_box='(500,500)', direction='down', scroll_offset=3)
        m = re.search(r'SCROLL\s*\(.*direction\s*=\s*[\'"](up|down)[\'"].*\)', line, re.IGNORECASE)
        if m:
            direction = m.group(1).lower()
            # Try to extract scroll amount
            am = re.search(r'scroll_offset\s*=\s*(\d+)', line, re.IGNORECASE)
            amount = int(am.group(1)) if am else 3
            x, y = _extract_coords(line)
            if x is not None and y is not None:
                xn, yn = _normalize_if_needed(x, y, screen_w, screen_h)
                actions.append(ScrollAction(x_norm=xn, y_norm=yn, direction=direction, amount=amount))
                continue
            actions.append(ScrollAction(x_norm=0.5, y_norm=0.5, direction=direction, amount=amount))
            continue

        # SCROLL("down",3) legacy
        m = re.match(r'SCROLL\s*\(\s*[\'"]?(up|down)[\'"]?\s*,\s*(\d+)\s*\)', line, re.IGNORECASE)
        if m:
            actions.append(ScrollAction(
                x_norm=0.5, y_norm=0.5,
                direction=m.group(1).lower(),
                amount=int(m.group(2)),
            ))
            continue

        # --- WAIT ---
        m = re.match(r'WAIT\s*\(\s*([0-9.]+)\s*\)', line, re.IGNORECASE)
        if m:
            actions.append(WaitAction(seconds=float(m.group(1))))
            continue

        # --- DRAG variants ---
        # DRAG(start_box='(100,100)', end_box='(200,200)')
        m = re.search(r'DRAG\s*\(', line, re.IGNORECASE)
        if m:
            # Extract two coordinate pairs
            coords = re.findall(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", line)
            if len(coords) >= 2:
                x1, y1 = float(coords[0][0]), float(coords[0][1])
                x2, y2 = float(coords[1][0]), float(coords[1][1])
                x1n, y1n = _normalize_if_needed(x1, y1, screen_w, screen_h)
                x2n, y2n = _normalize_if_needed(x2, y2, screen_w, screen_h)
                actions.append(DragAction(x1_norm=x1n, y1_norm=y1n, x2_norm=x2n, y2_norm=y2n))
                continue

        # DRAG(x1,y1,x2,y2) legacy
        m = re.match(
            r'DRAG\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)',
            line, re.IGNORECASE,
        )
        if m:
            actions.append(DragAction(
                x1_norm=float(m.group(1)),
                y1_norm=float(m.group(2)),
                x2_norm=float(m.group(3)),
                y2_norm=float(m.group(4)),
            ))
            continue

        log.warning("Unparseable UI-TARS line: %s", line)

    return actions


def count_step_cost(actions: List[AgentAction]) -> float:
    """Sum the step cost of a list of actions."""
    return sum(getattr(a, "step_cost", 1.0) for a in actions)


# =============================================================
#  ACTION EXECUTOR
# =============================================================

class ActionExecutor:
    """Executes parsed actions via the platform runtime with safety bounds."""

    def __init__(self, runtime=None) -> None:
        self._runtime = runtime
        self._screen_w: int = 1920
        self._screen_h: int = 1080
        self._refresh_screen_size()

    def _get_runtime(self):
        if self._runtime is None:
            from platforms.factory import get_agent_runtime
            self._runtime = get_agent_runtime()
        return self._runtime

    def _refresh_screen_size(self) -> None:
        try:
            w, h = self._get_runtime().screen_size()
            self._screen_w = w
            self._screen_h = h
        except Exception as e:
            log.warning("Could not get screen size, using defaults: %s", e)

    def _to_pixels(self, x_norm: float, y_norm: float) -> Tuple[int, int]:
        """Convert normalized 0-1 coordinates to absolute screen pixels."""
        x = int(x_norm * self._screen_w)
        y = int(y_norm * self._screen_h)
        # Clamp to screen bounds with 1px margin
        x = max(1, min(x, self._screen_w - 1))
        y = max(1, min(y, self._screen_h - 1))
        return x, y

    def execute(self, action: AgentAction) -> Tuple[bool, str]:
        """Execute a single action. Returns (success, message)."""
        try:
            rt = self._get_runtime()

            if isinstance(action, ClickAction):
                x, y = self._to_pixels(action.x_norm, action.y_norm)
                return rt.click(x, y, button=action.button)

            if isinstance(action, DoubleClickAction):
                x, y = self._to_pixels(action.x_norm, action.y_norm)
                # Try double-click via click with clicks=2 if supported
                try:
                    return rt.click(x, y, button=action.button, clicks=2)
                except TypeError:
                    # Fallback: click twice
                    rt.click(x, y, button=action.button)
                    rt.click(x, y, button=action.button)
                    return True, "double-clicked (fallback)"

            if isinstance(action, TypeAction):
                return rt.type_text(_resolve_credentials(action.text))

            if isinstance(action, PressAction):
                # Handle hotkey sequences like "ctrl+c", "ctrl+shift+t"
                if "+" in action.key:
                    keys = [k.strip() for k in action.key.split("+") if k.strip()]
                    return rt.hotkey(*keys)
                return rt.press_key(action.key)

            if isinstance(action, ScrollAction):
                x, y = self._to_pixels(action.x_norm, action.y_norm)
                amount = action.amount if action.direction == "up" else -action.amount
                return rt.scroll(x, y, amount)

            if isinstance(action, WaitAction):
                import time
                time.sleep(action.seconds)
                return True, f"waited {action.seconds}s"

            if isinstance(action, DragAction):
                x1, y1 = self._to_pixels(action.x1_norm, action.y1_norm)
                x2, y2 = self._to_pixels(action.x2_norm, action.y2_norm)
                rt.move(x1, y1)
                import time
                time.sleep(0.1)
                # Drag via click-and-hold + move + release
                # Platform runtimes may not support drag directly; use pyautogui fallback
                try:
                    import pyautogui
                    pyautogui.mouseDown()
                    pyautogui.moveTo(x2, y2, duration=0.3)
                    pyautogui.mouseUp()
                    return True, f"dragged ({x1},{y1}) -> ({x2},{y2})"
                except Exception as e:
                    return False, f"drag failed: {e}"

            return False, f"Unknown action type: {type(action).__name__}"

        except Exception as e:
            log.error("Action execution failed: %s", e, exc_info=True)
            return False, str(e)

    def execute_many(self, actions: List[AgentAction]) -> Tuple[float, List[str]]:
        """Execute multiple actions. Returns (total_cost, messages)."""
        messages: List[str] = []
        for action in actions:
            ok, msg = self.execute(action)
            messages.append(msg)
            if not ok:
                log.warning("Action failed: %s", msg)
                break
        total_cost = count_step_cost(actions)
        return total_cost, messages
