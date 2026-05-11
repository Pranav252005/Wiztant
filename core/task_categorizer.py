"""Hybrid task categorizer: keyword (offline) + optional LLM fallback (online)."""

from __future__ import annotations

import os
from typing import Optional

_OR_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Built-in keyword maps for offline detection
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "College": [
        "homework", "assignment", "exam", "quiz", "class", "professor", "lecture",
        "course", "semester", "grade", "college", "university", "study", "lab",
        "thesis", "dissertation", "academic", "textbook", "tutorial", "campus",
    ],
    "Home": [
        "clean", "cook", "laundry", "groceries", "buy", "home", "house", "room",
        "kitchen", "dinner", "family", "repair", "fix", "wash", "dishes", "vacuum",
        "garden", "shopping", "bills", "rent", "doctor", "appointment",
    ],
    "Solopreneur": [
        "wiztant", "whiztant", "app", "website", "marketing", "saas", "customer",
        "feature", "release", "deploy", "branding", "newsletter", "seo",
        "analytics", "stripe", "subscription", "pricing", "demo", "onboarding",
    ],
    "Solo Project": [
        "my project", "personal project", "portfolio", "side project",
        "practice", "learn", "by myself", "on my own", "solo", "hobby",
    ],
    "Group Project": [
        "team", "group", "collaborate", "classmate", "partner", "peer",
        "group project", "team meeting", "collaboration", "joint", "together with",
    ],
}

DIFFICULTY_KEYWORDS: dict[str, list[str]] = {
    "easy": ["easy", "simple", "quick", "fast", "minor", "trivial", "brief", "small fix"],
    "hard": ["hard", "difficult", "complex", "challenging", "tough", "major", "big", "complicated", "intensive"],
}


def _score_categories(text: str) -> dict[str, int]:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in lowered)
    return scores


def categorize_task(text: str) -> str:
    scores = _score_categories(text)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] > 0:
        return best
    return "Other"


def estimate_difficulty(text: str) -> str:
    lowered = text.lower()
    easy_hits = sum(1 for kw in DIFFICULTY_KEYWORDS["easy"] if kw in lowered)
    hard_hits = sum(1 for kw in DIFFICULTY_KEYWORDS["hard"] if kw in lowered)
    if easy_hits > hard_hits:
        return "easy"
    if hard_hits > easy_hits:
        return "hard"
    length = len(text.strip())
    if length < 25:
        return "easy"
    if length > 150:
        return "hard"
    return "medium"


def categorize_with_llm(text: str, categories: list[str]) -> Optional[str]:
    """Optional LLM fallback. Returns None on any failure so caller can fall back."""
    if not _OR_KEY:
        return None
    try:
        from core.tasks import _request_openrouter_text
        cat_list = ", ".join(categories)
        result = _request_openrouter_text(
            "You categorize tasks. Reply with ONLY the exact category name from the provided list. No extra text.",
            f"Categories: {cat_list}\nTask: {text}",
            max_tokens=20,
        )
        result = result.strip().strip('"').strip("'")
        if result in categories:
            return result
    except Exception:
        pass
    return None


def auto_categorize(text: str, categories: Optional[list[str]] = None) -> tuple[str, str]:
    """Return (category, difficulty). Uses keyword first; tries LLM only when keyword yields 'Other'."""
    cat = categorize_task(text)
    diff = estimate_difficulty(text)
    if cat == "Other" and categories:
        llm_cat = categorize_with_llm(text, categories)
        if llm_cat:
            cat = llm_cat
    return cat, diff
