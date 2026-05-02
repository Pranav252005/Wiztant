from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os


@dataclass
class ThemeColors:
    """Theme palette for Python-driven overlay surfaces."""
    bg_primary: str = "#0d0605"
    bg_secondary: str = "#1a1815"
    bg_tertiary: str = "#2a2420"
    text_primary: str = "#faf6f1"
    text_secondary: str = "#c9bfb5"
    border: str = "#3a3430"
    primary: str = "#6b2737"
    primary_hover: str = "#8a3347"
    accent: str = "#C4956A"
    success: str = "#4a7c59"
    warning: str = "#d4883b"
    danger: str = "#cc6633"


class AppTheme:
    """
    Centralized theme system for Python-owned UI surfaces.

    Design notes carried over from youthful-thompson / Claude-style UI:
    - glassy layered surfaces with low-contrast borders
    - 12-16px radii for cards and dialogs
    - muted tertiary text with strong primary headings
    - short, soft motion (roughly 150-300ms ease-out)
    """

    def __init__(self, config_path: Path | None = None):
        self.base_dir = Path(__file__).resolve().parent
        self.project_root = self.base_dir.parent
        self.config_path = config_path or (self.base_dir / "theme-config.json")
        self.current_theme = "whiztant"
        self.logo_path = self._resolve_logo_path()
        self.colors = self._load_theme()

    def _resolve_logo_path(self) -> Path:
        candidates = [
            self.base_dir / "assets" / "whiztant-logo.png",
            self.project_root / "ui" / os.getenv("WHIZTANT_OVERLAY_UI", "wiztant-clui") / "public" / "wiztantW.svg",
            self.project_root / "wiztantW.svg",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def _read_config(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "current_theme": "whiztant",
            "themes": {
                "whiztant": asdict(ThemeColors()),
            },
        }

    def _load_theme(self) -> ThemeColors:
        config = self._read_config()
        self.current_theme = config.get("current_theme", self.current_theme)
        colors_dict = config.get("themes", {}).get(self.current_theme, {})
        try:
            return ThemeColors(**colors_dict)
        except TypeError:
            return ThemeColors()

    def switch_theme(self, theme_name: str):
        config = self._read_config()
        themes = config.get("themes", {})
        if theme_name not in themes:
            raise ValueError(f"Unknown theme: {theme_name}")
        config["current_theme"] = theme_name
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self.current_theme = theme_name
        self.colors = ThemeColors(**themes[theme_name])

    def to_css_variables(self) -> str:
        variables = self.to_css_var_map()
        return "\n".join(f"{key}: {value};" for key, value in variables.items())

    def to_css_var_map(self, prefix: str = "--confirm") -> dict[str, str]:
        return {
            f"{prefix}-bg-primary": self.colors.bg_primary,
            f"{prefix}-bg-secondary": self.colors.bg_secondary,
            f"{prefix}-bg-tertiary": self.colors.bg_tertiary,
            f"{prefix}-text-primary": self.colors.text_primary,
            f"{prefix}-text-secondary": self.colors.text_secondary,
            f"{prefix}-border": self.colors.border,
            f"{prefix}-primary": self.colors.primary,
            f"{prefix}-primary-hover": self.colors.primary_hover,
            f"{prefix}-accent": self.colors.accent,
            f"{prefix}-success": self.colors.success,
            f"{prefix}-warning": self.colors.warning,
            f"{prefix}-danger": self.colors.danger,
        }


app_theme = AppTheme()
