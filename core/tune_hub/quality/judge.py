"""Quality judge implementations for Tune Hub.

Provides multiple backends for scoring tuner outputs:
- BaseJudge: abstract interface
- SimpleJudge: fast heuristic (no API calls)
- RandomJudge: development/debug
- LLMJudge: OpenRouter-based LLM-as-judge
"""

from __future__ import annotations

import os
import random
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseJudge(ABC):
    """Abstract base for quality scoring backends."""

    @abstractmethod
    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        """Return quality score in range [0.0, 1.0]."""
        raise NotImplementedError


class RandomJudge(BaseJudge):
    """Development/debug judge that returns random scores."""

    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        return round(random.uniform(0.5, 0.95), 3)


class SimpleJudge(BaseJudge):
    """
    Simple heuristic judge based on output length and keyword presence.
    Used as a lightweight fallback when no LLM judge is available.
    """

    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        text = str(output)
        score = 0.5

        # Length heuristic: preferred range 50-500 chars
        length = len(text)
        if 50 <= length <= 500:
            score += 0.2
        elif length > 0:
            score += 0.1

        # Keyword presence from criteria
        task = criteria.get("task", "")
        task_lower = task.lower()
        if any(kw in text.lower() for kw in task_lower.split()[:3]):
            score += 0.15

        # Code block presence for coding tasks
        if "code" in task_lower and "```" in text:
            score += 0.15

        return min(score, 1.0)


class LLMJudge(BaseJudge):
    """
    LLM-as-judge using OpenRouter.

    Evaluates outputs against criteria using a strong language model.
    Falls back to SimpleJudge if API is unavailable.
    """

    DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"
    JUDGE_SYSTEM_PROMPT = (
        "You are an objective quality evaluator. "
        "Score the given output on accuracy, completeness, and clarity. "
        "Return ONLY a single float between 0.0 and 1.0. No explanation."
    )

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        fallback: BaseJudge | None = None,
    ):
        self.model = model or os.getenv("JUDGE_MODEL", self.DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        base = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.base_url = base.rstrip("/")
        if not self.base_url.endswith("/chat/completions"):
            self.base_url += "/chat/completions"
        self.fallback = fallback or SimpleJudge()
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://whiztant.com",
            "X-Title": "Whiztant",
        }

    def score(self, output: Any, criteria: Dict[str, Any]) -> float:
        if not self.api_key:
            return self.fallback.score(output, criteria)

        try:
            import requests

            task = criteria.get("task", "")
            user_prompt = self._build_prompt(output, task, criteria)

            response = requests.post(
                self.base_url,
                headers=self._headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 20,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return self._parse_score(content)
        except Exception:
            return self.fallback.score(output, criteria)

    def _build_prompt(self, output: Any, task: str, criteria: Dict[str, Any]) -> str:
        """Build evaluation prompt from criteria."""
        lines = [
            "Task:",
            task or "General task",
            "",
            "Output to evaluate:",
            str(output)[:2000],  # Truncate very long outputs
            "",
            "Score this output on a scale of 0.0 to 1.0.",
        ]
        return "\n".join(lines)

    def _parse_score(self, text: str) -> float:
        """Extract float score from LLM response."""
        text = text.strip()
        # Try to find a float in the text
        import re

        matches = re.findall(r"0?\.\d+|1\.0+|\d+\.\d+", text)
        if matches:
            try:
                score = float(matches[0])
                return max(0.0, min(1.0, score))
            except ValueError:
                pass
        return self.fallback.score(text, {})


class ClaudeJudge(LLMJudge):
    """Convenience alias for LLMJudge defaulting to Claude."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        fallback: BaseJudge | None = None,
    ):
        super().__init__(
            model="anthropic/claude-sonnet-4-20250514",
            api_key=api_key,
            base_url=base_url,
            fallback=fallback,
        )
