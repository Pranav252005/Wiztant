"""
core/tune_hub/adaptive_matcher.py — Adaptive workflow matching + learning trigger.

Decides whether to:
1. Execute existing template (match_score > 0.85)
2. Adapt closest template (0.50 < match_score < 0.85)
3. Trigger learning (match_score < 0.50)

Also manages persona weights that influence how the agent learns and adapts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agent_v2_templates import WorkflowTemplate, TemplateRegistry, get_registry as get_template_registry
from core.tune_hub.browser_agent import TuneHubBrowserAgent, LearnedWorkflow

log = logging.getLogger("core.tune_hub.adaptive_matcher")

# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class MatchResult:
    """Result of matching user intent to templates."""

    action: str  # "execute" | "adapt" | "learn" | "failed"
    template_id: Optional[str] = None
    match_score: float = 0.0
    adapted_template: Optional[WorkflowTemplate] = None
    learned_workflow: Optional[LearnedWorkflow] = None
    message: str = ""
    closest_templates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PersonaWeights:
    """Persona weights that influence learning and adaptation."""

    automation_focus: float = 0.5
    ui_focus: float = 0.5
    coding_focus: float = 0.5
    debug_focus: float = 0.3
    security_focus: float = 0.3

    def to_dict(self) -> Dict[str, float]:
        return {
            "automation_focus": self.automation_focus,
            "ui_focus": self.ui_focus,
            "coding_focus": self.coding_focus,
            "debug_focus": self.debug_focus,
            "security_focus": self.security_focus,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "PersonaWeights":
        return cls(
            automation_focus=data.get("automation_focus", 0.5),
            ui_focus=data.get("ui_focus", 0.5),
            coding_focus=data.get("coding_focus", 0.5),
            debug_focus=data.get("debug_focus", 0.3),
            security_focus=data.get("security_focus", 0.3),
        )


# =============================================================
#  LEARNED TEMPLATE STORAGE
# =============================================================

LEARNED_DIR = Path(__file__).parent.parent.parent / "memory" / "agent_templates" / "learned"


def _ensure_learned_dir() -> Path:
    LEARNED_DIR.mkdir(parents=True, exist_ok=True)
    return LEARNED_DIR


def save_learned_template(workflow: LearnedWorkflow) -> Path:
    """Save a learned workflow to disk."""
    directory = _ensure_learned_dir()
    path = directory / f"{workflow.template_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(workflow.to_dict(), indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    log.info("Saved learned template: %s", path)
    return path


def load_learned_templates() -> List[Dict[str, Any]]:
    """Load all learned templates from disk."""
    directory = _ensure_learned_dir()
    templates = []
    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates.append(data)
        except Exception as e:
            log.warning("Failed to load learned template %s: %s", path, e)
    return templates


def load_learned_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Load a specific learned template."""
    directory = _ensure_learned_dir()
    path = directory / f"{template_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to load learned template %s: %s", path, e)
    return None


def delete_learned_template(template_id: str) -> bool:
    """Delete a learned template."""
    directory = _ensure_learned_dir()
    path = directory / f"{template_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# =============================================================
#  ADAPTIVE MATCHER
# =============================================================

class AdaptiveMatcher:
    """
    Matches user intent to existing templates and decides the best action:
    execute, adapt, or learn.
    """

    EXECUTE_THRESHOLD = 0.85
    ADAPT_THRESHOLD = 0.50

    def __init__(self) -> None:
        self.template_registry = get_template_registry()
        self.persona = self._load_persona()
        self._browser_agent: Optional[TuneHubBrowserAgent] = None

    def _load_persona(self) -> PersonaWeights:
        """Load persona weights from settings or use defaults."""
        try:
            settings_path = Path(__file__).parent.parent.parent / "data" / "settings.json"
            if settings_path.exists():
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                persona = data.get("tunehub", {}).get("persona", {})
                if persona:
                    return PersonaWeights.from_dict(persona)
        except Exception as e:
            log.warning("Failed to load persona weights: %s", e)
        return PersonaWeights()

    def _get_browser_agent(self) -> TuneHubBrowserAgent:
        if self._browser_agent is None:
            self._browser_agent = TuneHubBrowserAgent()
        return self._browser_agent

    def match(self, intent: str) -> MatchResult:
        """
        Match user intent against all templates and decide action.

        Returns MatchResult with recommended action.
        """
        intent_lower = intent.lower()
        all_templates = self._get_all_templates()

        if not all_templates:
            return MatchResult(
                action="learn",
                message="No templates available. Learning required.",
            )

        # Score each template
        scored = []
        for tpl in all_templates:
            score = self._score_match(intent_lower, tpl)
            scored.append((score, tpl))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top_tpl = scored[0]

        closest = [
            {"template_id": tpl["id"], "name": tpl.get("name", ""), "score": round(score, 2)}
            for score, tpl in scored[:3]
        ]

        if top_score >= self.EXECUTE_THRESHOLD:
            return MatchResult(
                action="execute",
                template_id=top_tpl["id"],
                match_score=top_score,
                message=f"Found matching template: {top_tpl.get('name', top_tpl['id'])} ({top_score:.0%} confidence)",
                closest_templates=closest,
            )

        if top_score >= self.ADAPT_THRESHOLD:
            adapted = self._attempt_adapt(intent, top_tpl)
            return MatchResult(
                action="adapt",
                template_id=top_tpl["id"],
                match_score=top_score,
                adapted_template=adapted,
                message=f"Closest template: {top_tpl.get('name', top_tpl['id'])} — adapting ({top_score:.0%} match)",
                closest_templates=closest,
            )

        return MatchResult(
            action="learn",
            match_score=top_score,
            message=f"No suitable template found. Best match: {top_tpl.get('name', top_tpl['id'])} at {top_score:.0%}. Triggering learning.",
            closest_templates=closest,
        )

    async def learn(self, intent: str, query: Optional[str] = None) -> MatchResult:
        """
        Trigger background learning for an unknown workflow.

        Returns MatchResult with learned workflow.
        """
        search_query = query or self._build_search_query(intent)
        template_id = self._sanitize_id(intent)

        log.info("Starting learning for: %s (query: %s)", intent, search_query)

        try:
            agent = self._get_browser_agent()
            workflow = await agent.research(search_query, template_id)

            # Apply persona weights
            workflow.persona_weights = self.persona.to_dict()

            # Save to disk
            save_learned_template(workflow)

            # Register in template registry
            from core.agent_v2_templates import WorkflowTemplate, WorkflowStep
            steps = [WorkflowStep(**s) for s in workflow.steps]
            tpl = WorkflowTemplate(
                id=workflow.template_id,
                name=workflow.name,
                apps_required=workflow.apps_required,
                estimated_steps=workflow.estimated_steps,
                estimated_budget=workflow.estimated_budget,
                description=workflow.description,
                steps=steps,
            )
            self.template_registry.register(tpl)

            return MatchResult(
                action="learned",
                template_id=workflow.template_id,
                match_score=workflow.confidence,
                learned_workflow=workflow,
                message=f"Learned new workflow: {workflow.name} (confidence: {workflow.confidence:.0%})",
            )

        except Exception as e:
            log.error("Learning failed: %s", e)
            return MatchResult(
                action="failed",
                message=f"Learning failed: {e}",
            )

    def _get_all_templates(self) -> List[Dict[str, Any]]:
        """Get all templates including built-in and learned."""
        templates = [tpl.to_dict() for tpl in self.template_registry.list_all()]
        learned = load_learned_templates()
        # Merge, with learned templates taking precedence on ID conflict
        seen = {t["id"]: t for t in templates}
        for lt in learned:
            tid = lt.get("template_id")
            if tid and tid not in seen:
                # Convert learned format to standard template format
                seen[tid] = {
                    "id": tid,
                    "name": lt.get("name", tid),
                    "description": lt.get("description", ""),
                    "apps_required": lt.get("apps_required", []),
                    "estimated_steps": lt.get("estimated_steps", 0),
                    "estimated_budget": lt.get("estimated_budget", 0),
                    "steps": lt.get("steps", []),
                    "learned": True,
                    "confidence": lt.get("confidence", 0.5),
                }
        return list(seen.values())

    def _score_match(self, intent: str, tpl: Dict[str, Any]) -> float:
        """Score how well a template matches the user intent."""
        scores = []

        # Name match
        name = tpl.get("name", "").lower()
        if name:
            scores.append(self._token_overlap(intent, name))

        # Description match
        desc = tpl.get("description", "").lower()
        if desc:
            scores.append(self._token_overlap(intent, desc) * 0.8)

        # ID match
        tid = tpl.get("id", "").lower()
        if tid:
            scores.append(self._token_overlap(intent, tid) * 0.9)

        # Apps match (e.g., "deploy to vercel" matches templates with "browser")
        apps = " ".join(tpl.get("apps_required", [])).lower()
        if apps:
            scores.append(self._token_overlap(intent, apps) * 0.5)

        # Keyword extraction from intent
        keywords = self._extract_keywords(intent)
        for kw in keywords:
            if kw in name or kw in desc or kw in tid:
                scores.append(0.3)

        # Learned templates get slight penalty unless high confidence
        if tpl.get("learned"):
            confidence = tpl.get("confidence", 0.5)
            scores = [s * confidence for s in scores]

        return max(scores) if scores else 0.0

    def _token_overlap(self, a: str, b: str) -> float:
        """Simple token overlap similarity."""
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        return len(intersection) / max(len(tokens_a), len(tokens_b))

    def _extract_keywords(self, intent: str) -> List[str]:
        """Extract meaningful keywords from intent."""
        # Remove common stop words
        stop_words = {"the", "a", "an", "to", "my", "me", "i", "you", "for", "with", "how", "do", "can", "please", "help", "want", "need", "would", "like", "this", "that", "it", "is", "are", "be", "being", "been"}
        words = intent.lower().split()
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _build_search_query(self, intent: str) -> str:
        """Build an optimal search query from intent, influenced by persona."""
        base = intent.lower()

        # Persona influences what we search for
        if self.persona.automation_focus > 0.7:
            base += " cli command line"
        if self.persona.coding_focus > 0.7:
            base += " developer documentation"
        if self.persona.ui_focus > 0.7:
            base += " dashboard tutorial"

        return base[:200]

    def _sanitize_id(self, intent: str) -> str:
        """Convert intent to a safe template ID."""
        sanitized = re.sub(r'[^a-z0-9_]+', '_', intent.lower().strip())[:50]
        return sanitized.strip('_')

    def _attempt_adapt(self, intent: str, base_tpl: Dict[str, Any]) -> Optional[WorkflowTemplate]:
        """Attempt to adapt an existing template to a new intent."""
        from core.agent_v2_templates import WorkflowTemplate, WorkflowStep

        try:
            steps = [WorkflowStep(**s) for s in base_tpl.get("steps", [])]
            adapted = WorkflowTemplate(
                id=f"{base_tpl['id']}_adapted",
                name=f"{base_tpl.get('name', 'Adapted')} (custom)",
                apps_required=base_tpl.get("apps_required", []),
                estimated_steps=base_tpl.get("estimated_steps", 0),
                estimated_budget=base_tpl.get("estimated_budget", 0),
                description=f"Adapted from {base_tpl.get('name', '')} for: {intent}",
                steps=steps,
            )
            return adapted
        except Exception as e:
            log.warning("Adaptation failed: %s", e)
            return None


# Singleton
_default_matcher: Optional[AdaptiveMatcher] = None


def get_matcher() -> AdaptiveMatcher:
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = AdaptiveMatcher()
    return _default_matcher


