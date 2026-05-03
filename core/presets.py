"""Preset system for RePrompt/WizPrompt optimization targets."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json
import os


@dataclass
class Preset:
    """A RePrompt optimization preset."""
    id: str
    name: str
    description: str
    category: str  # "company" | "user"
    system_prompt_addendum: str  # Injected into synthesis agent
    agent_focus: Optional[str] = None  # Which agent to prioritize: structure, semantic, edge_case, emotional
    icon: Optional[str] = None


# Company-defined default presets
DEFAULT_PRESETS = [
    Preset(
        id="product_review",
        name="Product Review",
        description="Optimize for product feedback and reviews",
        category="company",
        system_prompt_addendum="Focus on actionable feedback, user impact, constructive criticism, and specific recommendations. Evaluate the product from multiple user perspectives.",
        agent_focus="semantic",
        icon="star",
    ),
    Preset(
        id="idea_review",
        name="Idea Review",
        description="Optimize for evaluating and refining ideas",
        category="company",
        system_prompt_addendum="Focus on feasibility, innovation potential, resource requirements, risks, and implementation path. Challenge assumptions and identify hidden opportunities.",
        agent_focus="structure",
        icon="lightbulb",
    ),
    Preset(
        id="code_review",
        name="Code Review",
        description="Optimize for reviewing code and technical implementation",
        category="company",
        system_prompt_addendum="Focus on readability, edge cases, security vulnerabilities, performance bottlenecks, and maintainability. Suggest specific improvements with code examples.",
        agent_focus="edge_case",
        icon="code",
    ),
    Preset(
        id="code_creation",
        name="Code Creation",
        description="Optimize for generating code from descriptions",
        category="company",
        system_prompt_addendum="Focus on clean architecture, comprehensive documentation, testability, error handling, and best practices. Generate production-ready code with comments.",
        agent_focus="structure",
        icon="terminal",
    ),
    Preset(
        id="general",
        name="General Optimization",
        description="Standard multi-agent prompt optimization",
        category="company",
        system_prompt_addendum="Apply balanced optimization across all dimensions: structure, clarity, edge cases, and emotional framing.",
        agent_focus=None,
        icon="zap",
    ),
]

# Path for user-created presets
_USER_PRESETS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "user_presets.json")


def get_all_presets() -> List[Preset]:
    """Return all presets (company defaults + user-created)."""
    presets = list(DEFAULT_PRESETS)
    presets.extend(_load_user_presets())
    return presets


def get_preset_by_id(preset_id: str) -> Optional[Preset]:
    """Find a preset by ID."""
    for preset in get_all_presets():
        if preset.id == preset_id:
            return preset
    return None


def add_user_preset(preset: Preset) -> None:
    """Add a user-created preset."""
    user_presets = _load_user_presets()
    preset.category = "user"
    user_presets.append(preset)
    _save_user_presets(user_presets)


def delete_user_preset(preset_id: str) -> bool:
    """Delete a user preset. Returns True if deleted."""
    user_presets = _load_user_presets()
    original_len = len(user_presets)
    user_presets = [p for p in user_presets if p.id != preset_id]
    if len(user_presets) < original_len:
        _save_user_presets(user_presets)
        return True
    return False


def _load_user_presets() -> List[Preset]:
    """Load user-created presets from disk."""
    if not os.path.exists(_USER_PRESETS_PATH):
        return []
    try:
        with open(_USER_PRESETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Preset(**p) for p in data]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def _save_user_presets(presets: List[Preset]) -> None:
    """Save user-created presets to disk."""
    os.makedirs(os.path.dirname(_USER_PRESETS_PATH), exist_ok=True)
    with open(_USER_PRESETS_PATH, "w", encoding="utf-8") as f:
        json.dump([{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "system_prompt_addendum": p.system_prompt_addendum,
            "agent_focus": p.agent_focus,
            "icon": p.icon,
        } for p in presets], f, indent=2)


def preset_to_dict(preset: Preset) -> dict:
    """Convert a Preset to a dictionary for JSON serialization."""
    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "category": preset.category,
        "system_prompt_addendum": preset.system_prompt_addendum,
        "agent_focus": preset.agent_focus,
        "icon": preset.icon,
    }
