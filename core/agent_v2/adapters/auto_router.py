"""
Auto Router — intelligently routes subphases to the best IDE tool.

Reads tool preferences from agent memory and routes based on subphase type.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.agent_v2.adapters.base import ToolAdapter
from core.agent_v2.adapters.cursor_adapter import CursorAdapter
from core.agent_v2.adapters.windsurf_adapter import WindsurfAdapter
from core.agent_v2.adapters.vscode_adapter import VSCodeAdapter
from core.agent_v2.adapters.lovable_adapter import LovableAdapter


# Default routing rules: which tool is best for which type of work
_DEFAULT_ROUTES: Dict[str, List[str]] = {
    # Schema / Database
    "schema": ["cursor", "windsurf", "vscode"],
    "database": ["cursor", "windsurf", "vscode"],
    "prisma": ["cursor", "windsurf", "vscode"],
    "migration": ["cursor", "windsurf", "vscode"],
    # Auth
    "auth": ["cursor", "windsurf", "vscode"],
    "login": ["cursor", "windsurf", "vscode"],
    "oauth": ["cursor", "windsurf", "vscode"],
    # API / Backend
    "api": ["cursor", "windsurf", "vscode"],
    "route": ["cursor", "windsurf", "vscode"],
    "endpoint": ["cursor", "windsurf", "vscode"],
    "handler": ["cursor", "windsurf", "vscode"],
    "middleware": ["cursor", "windsurf", "vscode"],
    "server": ["cursor", "windsurf", "vscode"],
    # UI / Frontend
    "ui": ["lovable", "cursor", "windsurf", "vscode"],
    "component": ["lovable", "cursor", "windsurf", "vscode"],
    "page": ["lovable", "cursor", "windsurf", "vscode"],
    "layout": ["lovable", "cursor", "windsurf", "vscode"],
    "style": ["lovable", "cursor", "windsurf", "vscode"],
    "theme": ["lovable", "cursor", "windsurf", "vscode"],
    "css": ["lovable", "cursor", "windsurf", "vscode"],
    "tailwind": ["lovable", "cursor", "windsurf", "vscode"],
    "responsive": ["lovable", "cursor", "windsurf", "vscode"],
    "animation": ["lovable", "cursor", "windsurf", "vscode"],
    # Terminal / Deploy
    "deploy": ["warp", "cursor", "vscode"],
    "terminal": ["warp", "cursor", "vscode"],
    "docker": ["warp", "cursor", "vscode"],
    "ci": ["warp", "cursor", "vscode"],
    "cd": ["warp", "cursor", "vscode"],
    "script": ["warp", "cursor", "vscode"],
    # Config
    "config": ["cursor", "vscode", "windsurf"],
    "env": ["cursor", "vscode", "windsurf"],
    "setup": ["cursor", "vscode", "windsurf"],
}


class AutoRouter:
    """Routes subphases to the best available IDE tool."""

    def __init__(self, tool_preferences: Optional[Dict[str, str]] = None) -> None:
        self._adapters: Dict[str, ToolAdapter] = {
            "cursor": CursorAdapter(),
            "windsurf": WindsurfAdapter(),
            "vscode": VSCodeAdapter(),
            "lovable": LovableAdapter(),
        }
        self._preferences = tool_preferences or {}

    def get_adapter(self, tool: str) -> ToolAdapter:
        adapter = self._adapters.get(tool)
        if not adapter:
            raise ValueError(f"No adapter registered for tool: {tool}")
        return adapter

    def _detect_category(self, description: str) -> str:
        """Detect the category of work from the subphase description."""
        lower = description.lower()
        for category, keywords in {
            "schema": ["schema", "prisma", "drizzle", "model", "table", "migration", "seed"],
            "auth": ["auth", "login", "logout", "register", "oauth", "jwt", "session", "password"],
            "api": ["api", "route", "endpoint", "handler", "controller", "middleware", "trpc", "graphql"],
            "ui": ["ui", "component", "page", "layout", "style", "theme", "css", "tailwind", "shadcn", "responsive", "animation"],
            "deploy": ["deploy", "docker", "kubernetes", "terraform", "ci", "cd", "pipeline", "vercel", "netlify"],
            "terminal": ["terminal", "script", "bash", "shell", "command"],
            "config": ["config", "env", "setup", "settings", "tsconfig", "eslint", "prettier"],
        }.items():
            if any(kw in lower for kw in keywords):
                return category
        return "general"

    def route(self, description: str, preferred_tool: Optional[str] = None) -> str:
        """
        Determine the best tool for a given subphase description.

        1. If user has a preference for this category, use it (if available)
        2. If a preferred_tool is specified, try it first
        3. Otherwise, use default routing based on category
        4. Fallback to first available tool
        """
        category = self._detect_category(description)

        # 1. User preference for this category
        if category in self._preferences:
            pref = self._preferences[category]
            if pref in self._adapters and self._adapters[pref].is_available():
                return pref

        # 2. Explicit preferred tool
        if preferred_tool and preferred_tool in self._adapters:
            if self._adapters[preferred_tool].is_available():
                return preferred_tool

        # 3. Default routing for category
        candidates = _DEFAULT_ROUTES.get(category, ["cursor", "windsurf", "vscode"])
        for tool in candidates:
            if tool in self._adapters and self._adapters[tool].is_available():
                return tool

        # 4. Fallback: first available tool
        for tool, adapter in self._adapters.items():
            if adapter.is_available():
                return tool

        # 5. Desperate fallback: cursor (most common)
        return "cursor"

    def list_available(self) -> List[str]:
        """Return a list of available tools."""
        return [name for name, adapter in self._adapters.items() if adapter.is_available()]
