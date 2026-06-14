"""
core/agent_profiles.py — Tool detection and IDE profiles for the Three-Brain Agent.

Each profile tells the Executor where UI elements are located (normalized coords)
and provides tool-specific prompt templates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================
#  TOOL PROFILE BASE
# =============================================================

@dataclass
class ToolProfile:
    name: str = "unknown"
    chat_input_selector: tuple[float, float] = (0.0, 0.0)
    send_button_selector: tuple[float, float] = (0.0, 0.0)
    revert_button_selector: tuple[float, float] = (0.0, 0.0)
    accept_button_selector: tuple[float, float] = (0.0, 0.0)
    agent_mode_toggle: tuple[float, float] = (0.0, 0.0)
    prompt_template: str = "{instruction}"
    supported_actions: List[str] = field(default_factory=lambda: [
        "click", "type", "press", "scroll", "wait", "double_click", "drag"
    ])

    def format_prompt(self, instruction: str) -> str:
        return self.prompt_template.format(instruction=instruction)


# =============================================================
#  IDE PROFILES
# =============================================================

class CursorProfile(ToolProfile):
    def __init__(self) -> None:
        super().__init__(
            name="cursor",
            chat_input_selector=(0.12, 0.89),
            send_button_selector=(0.88, 0.89),
            revert_button_selector=(0.72, 0.34),
            accept_button_selector=(0.82, 0.34),
            agent_mode_toggle=(0.15, 0.15),
            prompt_template=(
                "Use the @codebase context. Follow the existing code style.\n\n"
                "{instruction}"
            ),
        )


class WindsurfProfile(ToolProfile):
    def __init__(self) -> None:
        super().__init__(
            name="windsurf",
            chat_input_selector=(0.10, 0.90),
            send_button_selector=(0.90, 0.90),
            revert_button_selector=(0.70, 0.32),
            accept_button_selector=(0.80, 0.32),
            agent_mode_toggle=(0.15, 0.15),
            prompt_template=(
                "Use @@file references for context. Follow the existing code style.\n\n"
                "{instruction}"
            ),
        )


class VSCodeProfile(ToolProfile):
    def __init__(self) -> None:
        super().__init__(
            name="vscode",
            chat_input_selector=(0.12, 0.88),
            send_button_selector=(0.88, 0.88),
            revert_button_selector=(0.70, 0.35),
            accept_button_selector=(0.80, 0.35),
            agent_mode_toggle=(0.12, 0.12),
            prompt_template=(
                "Use the existing workspace context. Follow the existing code style.\n\n"
                "{instruction}"
            ),
        )


# =============================================================
#  PROFILE REGISTRY
# =============================================================

_PROFILES: Dict[str, ToolProfile] = {
    "cursor": CursorProfile(),
    "windsurf": WindsurfProfile(),
    "vscode": VSCodeProfile(),
}

_TOOL_KEYWORDS: Dict[str, List[str]] = {
    "cursor": ["cursor", "cursor ide", "cursor editor"],
    "windsurf": ["windsurf", "windsurf ide", "codeium"],
    "vscode": ["vscode", "vs code", "visual studio code", "code"],
}


def get_profile(tool_name: str) -> ToolProfile:
    """Get a tool profile by name. Returns generic if unknown."""
    key = tool_name.lower().strip()
    return _PROFILES.get(key, ToolProfile(name=key))


def detect_tool_from_text(text: str) -> Optional[str]:
    """Fast keyword-based tool detection from user text."""
    lower = text.lower()
    for tool, keywords in _TOOL_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return tool
    return None


def detect_tool_from_vision(vision_result: Dict[str, Any]) -> tuple[str, float]:
    """Extract tool detection from vision model JSON result."""
    tool = vision_result.get("tool_detected", "unknown")
    confidence = vision_result.get("tool_confidence", 0.0)
    return tool, float(confidence)


def list_supported_tools() -> List[str]:
    return list(_PROFILES.keys())
