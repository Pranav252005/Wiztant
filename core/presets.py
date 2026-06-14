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


# Company-defined default presets
DEFAULT_PRESETS = [
    Preset(
        id="general_polish",
        name="General Polish",
        display_name="General Polish",
        description="Any text that needs grammar fixes, clarity, and a natural tone.",
        recommended_for="Any text that needs grammar fixes, clarity, and a natural tone.",
        category="company",
        system_prompt_addendum=(
            "You are an expert editor and copywriter. Your sole task is to polish the user's text.\n"
            "- Fix grammar, spelling, and punctuation errors.\n"
            "- Improve sentence flow and clarity.\n"
            "- Remove filler words, redundancy, and awkward phrasing.\n"
            "- Preserve the original tone, voice, and intent exactly.\n"
            "- Do NOT reframe the text as an AI prompt.\n"
            "- Do NOT add a role, persona, or character voice.\n"
            "- Do NOT expand the scope, add new ideas, or change the meaning.\n"
            "- Do NOT include a summary or 'Optimizations Applied' section.\n"
            "Return ONLY the polished text. No preamble."
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
            "You are a senior software engineer specializing in clean, production-ready code. "
            "The user has provided a rough description, pseudocode, or broken code snippet.\n"
            "Your task: produce precise, idiomatic, well-documented code that solves exactly what was described.\n"
            "- Infer the correct programming language and paradigms from context.\n"
            "- Include clear comments for complex logic only.\n"
            "- Follow security best practices and defensive programming.\n"
            "- Use modern, readable patterns.\n"
            "- Do NOT add features, error handling, or functionality beyond what was explicitly requested.\n"
            "- Do NOT include explanations, setup instructions, or usage examples unless the input was ambiguous.\n"
            "- Do NOT change the core problem being solved.\n"
            "Return ONLY the code and necessary comments. No preamble."
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
            "You are a meticulous staff engineer and code reviewer. The user has pasted code that needs expert analysis.\n"
            "Your task: perform a rigorous review focused on:\n"
            "1. Bugs and logic errors — identify runtime failures and incorrect behavior.\n"
            "2. Security vulnerabilities — spot injection risks, leaks, unsafe operations, and trust boundaries.\n"
            "3. Performance bottlenecks — highlight inefficiencies and algorithmic issues.\n"
            "4. Style and readability — note naming, formatting, and clarity problems.\n"
            "5. Edge cases and error handling — find missing validations and failure modes.\n"
            "Output format:\n"
            "- Concise list of issues found (with line references where possible).\n"
            "- Corrected version of the code addressing all critical issues.\n"
            "Be direct, specific, and actionable. Do NOT be overly verbose. Do NOT change the code's overall purpose or add unrelated features. "
            "Return only the review and corrected code. No preamble."
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
            "You are an elite prompt engineer. The user has provided a raw prompt they intend to send to an AI. "
            "Your task is to rewrite it into a perfectly structured, production-ready prompt.\n"
            "- Assign a specific, highly relevant role/persona that matches the task domain.\n"
            "- Define the task with crystal-clear instructions and expected output format.\n"
            "- Add necessary constraints, context, and boundaries.\n"
            "- Remove all ambiguity, filler, and vague language.\n"
            "- Use structured sections: Role, Task, Context, Constraints, Output Format.\n"
            "- Do NOT change the core intent or add new tasks not mentioned by the user.\n"
            "- Do NOT add unnecessary verbosity or fluff.\n"
            "Return ONLY the optimized prompt. No preamble, no summary."
        ),
        agent_focus="optimization",
        icon="message-square",
    ),
    Preset(
        id="idea_refinement",
        name="Idea Refinement",
        display_name="Idea Refinement",
        description="Raw thoughts, brainstorming notes, or half-baked concepts that need structure and depth.",
        recommended_for="Raw thoughts, brainstorming notes, or half-baked concepts that need structure and depth.",
        category="company",
        system_prompt_addendum=(
            "You are a product strategist and visionary thinker. The user has shared a raw idea, concept, or one-sentence thought.\n"
            "Your task: deeply ideate and expand upon it to create a comprehensive, inspiring concept.\n"
            "- Explore the full conceptual breadth and depth of the idea.\n"
            "- Identify the core problem/opportunity and the unique value proposition.\n"
            "- Propose key features, target audience, and potential directions.\n"
            "- Surface risks, assumptions, and open questions.\n"
            "- Deeply expand the creative vision and conceptual span.\n"
            "- Make the idea feel fully realized and thought-through.\n"
            "CRITICAL: Do NOT provide technical implementation details, architecture, code, or step-by-step build instructions.\n"
            "Do NOT add features that completely diverge from the user's core concept.\n"
            "Return a comprehensive, structured concept refinement with no preamble."
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
            "You are a senior product manager who writes world-class PRDs. The user has provided rambling notes or a rough feature description.\n"
            "Your task: convert it into a professional Product Requirements Document section.\n"
            "Include:\n"
            "1. Objective / Goal — what this achieves.\n"
            "2. User Story — who benefits and why.\n"
            "3. Functional Requirements — what the system must do.\n"
            "4. Acceptance Criteria — specific, testable conditions for success.\n"
            "5. Non-Goals — what is explicitly out of scope.\n"
            "6. Open Questions — what needs decision or research.\n"
            "Use professional PM language. If the input is vague, note assumptions clearly.\n"
            "CRITICAL: Do NOT include implementation details, tech stack choices, or code.\n"
            "Return only the spec content. No preamble."
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
            "You are a technical documentation specialist who writes READMEs, API docs, and technical guides. The user has provided rough text or notes.\n"
            "Your task: rewrite it into clear, scannable, professional documentation.\n"
            "- Use appropriate headers, bullet points, and code blocks.\n"
            "- Ensure the tone is helpful, precise, and concise.\n"
            "- Fix ambiguous technical explanations.\n"
            "- Structure it like documentation (Overview, Usage, Examples, Notes).\n"
            "- Do NOT add information not present in the original text.\n"
            "- Do NOT include a role/persona framing.\n"
            "Return only the polished documentation. No preamble."
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
            "You are a workplace communication specialist. The user has written a message intended for {variant}.\n"
            "Your task: rewrite it to be clear, professional, and appropriately toned.\n"
            "- Match the expected etiquette and formality level for {variant}.\n"
            "- Fix passive-aggressive, overly blunt, or unclear tone.\n"
            "- Remove unnecessary words while preserving the full intent.\n"
            "- Ensure the call-to-action or request is obvious.\n"
            "- Do NOT add information not in the original message.\n"
            "- Do NOT change the core request or soften accountability.\n"
            "Return only the rewritten message. No preamble."
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
            "You are a QA engineer and debugging specialist. The user has described a bug, error, or issue.\n"
            "Your task: structure it into a perfectly actionable bug report.\n"
            "Include:\n"
            "1. Title / Summary — concise description of the issue.\n"
            "2. Steps to Reproduce — numbered, specific, and minimal.\n"
            "3. Expected Behavior — what should happen.\n"
            "4. Actual Behavior — what actually happens, including exact error messages.\n"
            "5. Environment — OS, browser, version (infer if possible from context).\n"
            "6. Severity Assessment — impact level.\n"
            "7. Possible Root Cause Analysis — only if clearly inferable from the description.\n"
            "Ask clarifying questions ONLY if critical info is missing.\n"
            "Do NOT add unrelated issues or inflate severity.\n"
            "Return only the structured bug report. No preamble."
        ),
        agent_focus="technical",
        icon="bug",
    ),
    Preset(
        id="project_architect",
        name="Project Architect",
        display_name="Project Architect",
        description="Decomposes a product idea into layered architecture with phases and subphases.",
        recommended_for="Decomposing a product idea into layered architecture with phases and subphases.",
        category="company",
        system_prompt_addendum=(
            "Decompose the user's product idea into the 5 standard layers: L1 Data & Schema, L2 Auth & Security, "
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
