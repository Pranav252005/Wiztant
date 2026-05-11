"""Preset system for RePrompt/WizPrompt optimization targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
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
    agent_focus: Optional[str] = None  # Which agent to prioritize
    icon: Optional[str] = None
    display_name: Optional[str] = None
    recommended_for: Optional[str] = None


# Company-defined default presets (10 total)
DEFAULT_PRESETS = [
    Preset(
        id="general_polish",
        name="General Polish",
        display_name="General Polish",
        description="Any text that needs grammar fixes, clarity, and a natural tone.",
        recommended_for="Any text that needs grammar fixes, clarity, and a natural tone.",
        category="company",
        system_prompt_addendum=(
            "You are a precise editor. Take the user's clipboard text and rewrite it to be "
            "grammatically correct, concise, and clear. Preserve the original intent and tone "
            "unless it is overly casual or unprofessional. Remove filler words, fix punctuation, "
            "and improve flow. Do not add fluff. Return only the rewritten text with no preamble."
        ),
        agent_focus="clarity",
        icon="sparkles",
    ),
    Preset(
        id="code_creation",
        name="Code Creation",
        display_name="Code Creation",
        description="Turning natural language descriptions, pseudocode, or rough logic into production-ready code.",
        recommended_for="Turning natural language descriptions, pseudocode, or rough logic into production-ready code.",
        category="company",
        system_prompt_addendum=(
            "You are a senior software engineer. The user has pasted a rough description, "
            "pseudocode, or broken code snippet. Write clean, idiomatic, well-documented code "
            "that solves the described problem. Add comments for complex logic, use best practices "
            "for the inferred language, and include a brief explanation of the approach only if "
            "the input was ambiguous. Return only the code and necessary comments."
        ),
        agent_focus="code",
        icon="code",
    ),
    Preset(
        id="code_review",
        name="Code Review",
        display_name="Code Review",
        description="Pasted code snippets that need bug detection, performance tuning, or style fixes.",
        recommended_for="Pasted code snippets that need bug detection, performance tuning, or style fixes.",
        category="company",
        system_prompt_addendum=(
            "You are a rigorous code reviewer. Analyze the pasted code for bugs, security issues, "
            "performance bottlenecks, and style violations. Provide a concise list of issues found "
            "(with line references if possible) and then provide the corrected version of the code. "
            "Be direct and actionable. Do not be overly verbose."
        ),
        agent_focus="code",
        icon="search",
    ),
    Preset(
        id="prompt_engineer",
        name="Prompt Engineer",
        display_name="Prompt Engineer",
        description="Optimizing AI prompts for better structure, specificity, and output quality.",
        recommended_for="Optimizing AI prompts for better structure, specificity, and output quality.",
        category="company",
        system_prompt_addendum=(
            "You are an expert prompt engineer. The user has pasted a prompt they intend to send "
            "to an AI model. Rewrite it to be more effective: add specific constraints, request "
            "structured output (JSON/markdown where appropriate), clarify the role/persona, and "
            "eliminate ambiguity. Do not change the core task. Return only the optimized prompt."
        ),
        agent_focus="optimization",
        icon="message-square",
    ),
    Preset(
        id="idea_refinement",
        name="Idea Refinement",
        display_name="Idea Refinement",
        description="Raw thoughts, brainstorming notes, or half-baked concepts that need structure.",
        recommended_for="Raw thoughts, brainstorming notes, or half-baked concepts that need structure.",
        category="company",
        system_prompt_addendum=(
            "You are a product strategist. The user has pasted a rough idea or brainstorming notes. "
            "Refine it into a structured concept with: (1) Core Problem, (2) Proposed Solution, "
            "(3) Key Features, (4) Target Audience, (5) Potential Challenges. Keep the original "
            "voice and enthusiasm but add rigor. Return only the structured refinement."
        ),
        agent_focus="creativity",
        icon="lightbulb",
    ),
    Preset(
        id="product_spec",
        name="Product Spec",
        display_name="Product Spec",
        description="Converting rambling product thoughts into a formal PRD or feature specification.",
        recommended_for="Converting rambling product thoughts into a formal PRD or feature specification.",
        category="company",
        system_prompt_addendum=(
            "You are a technical product manager. Convert the user's pasted notes into a concise "
            "Product Requirements Document (PRD) section. Include: Objective, User Story, Acceptance "
            "Criteria, and Open Questions. Use professional PM language. If the input is vague, "
            "note assumptions. Return only the spec content."
        ),
        agent_focus="product",
        icon="file-text",
    ),
    Preset(
        id="technical_writing",
        name="Technical Writing",
        display_name="Technical Writing",
        description="Documentation, READMEs, API docs, or explanations that need professional polish.",
        recommended_for="Documentation, READMEs, API docs, or explanations that need professional polish.",
        category="company",
        system_prompt_addendum=(
            "You are a technical writer. Rewrite the pasted text into clear, scannable documentation. "
            "Use headers, bullet points, and code blocks where appropriate. Ensure the tone is helpful "
            "but concise. Fix any ambiguous technical explanations. Return only the polished documentation."
        ),
        agent_focus="documentation",
        icon="book-open",
    ),
    Preset(
        id="communication",
        name="Communication",
        display_name="Communication",
        description="Emails, Slack messages, DMs, or any workplace communication that needs tone adjustment.",
        recommended_for="Emails, Slack messages, DMs, or any workplace communication that needs tone adjustment.",
        category="company",
        system_prompt_addendum=(
            "You are a professional communication coach. Rewrite the pasted message to be clear, "
            "polite, and appropriately formal for workplace communication. Fix passive-aggressive tone, "
            "remove unnecessary words, and ensure the call-to-action or request is obvious. Maintain "
            "the sender's intent. Return only the rewritten message."
        ),
        agent_focus="communication",
        icon="mail",
    ),
    Preset(
        id="bug_report",
        name="Bug Report",
        display_name="Bug Report",
        description="Scattered complaints or screenshots of errors that need to become actionable bug reports.",
        recommended_for="Scattered complaints or screenshots of errors that need to become actionable bug reports.",
        category="company",
        system_prompt_addendum=(
            "You are a QA engineer. The user has pasted a messy description of a bug. Structure it "
            "into a proper bug report with: Title, Steps to Reproduce, Expected Behavior, Actual Behavior, "
            "and Environment (infer if possible). Ask clarifying questions only if critical info is missing. "
            "Return only the structured bug report."
        ),
        agent_focus="technical",
        icon="bug",
    ),
    Preset(
        id="cli_command",
        name="CLI Command",
        display_name="CLI Command",
        description="Natural language requests that need to be converted into accurate terminal commands.",
        recommended_for="Natural language requests that need to be converted into accurate terminal commands.",
        category="company",
        system_prompt_addendum=(
            "You are a Linux/macOS systems expert. The user has pasted a natural language request "
            "(e.g., 'find all files modified yesterday'). Convert it into the most efficient, safe "
            "terminal command. Prefer modern tools (fd, ripgrep, fzf) over legacy ones when appropriate. "
            "Add a one-line explanation of what the command does. Warn if the command is destructive. "
            "Return only the command and explanation."
        ),
        agent_focus="technical",
        icon="terminal",
    ),
    Preset(
        id="project_architect",
        name="Project Architect",
        display_name="Project Architect",
        description="Decomposes a product idea into layered architecture with phases and subphases.",
        recommended_for="Decomposing a product idea into layered architecture with phases and subphases.",
        category="company",
        system_prompt_addendum=(
            "You are a senior software architect. The user describes a product they want to build. "
            "Decompose it into the 5 standard layers: L1 Data & Schema, L2 Auth & Security, "
            "L3 API & Business Logic, L4 UI & Frontend, L5 Integration & Deploy. "
            "For each layer, list phases. For each phase, list subphases with: id, description, tool (cursor/warp/lovable/auto), "
            "action type (prompt or command), and verification criteria. "
            "Return ONLY valid JSON matching the MasterPlan schema. No prose."
        ),
        agent_focus="architecture",
        icon="layout",
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
        json.dump([preset_to_dict(p) for p in presets], f, indent=2)


def preset_to_dict(preset: Preset) -> dict:
    """Convert a Preset to a dictionary for JSON serialization."""
    return {
        "id": preset.id,
        "name": preset.name,
        "display_name": preset.display_name,
        "description": preset.description,
        "recommended_for": preset.recommended_for,
        "category": preset.category,
        "system_prompt_addendum": preset.system_prompt_addendum,
        "agent_focus": preset.agent_focus,
        "icon": preset.icon,
    }
