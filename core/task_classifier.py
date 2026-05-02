"""
core/task_classifier.py — Smart classification for voice-added tasks.

Given a new spoken task and the existing open tasks, decide whether the new
text is:
  - new        → a fresh, independent task
  - duplicate  → same task already tracked (skip the add)
  - subtask    → related to an existing parent task (attach as subtask)

Algorithm (cheap → expensive):
  1. Exact normalized match → duplicate.
  2. Shared salient subject check → if no overlap, return new.
  3. LLM arbitration on shared-subject pair → duplicate | subtask | independent.

LLM is optional. When unavailable, shared-subject falls back to `subtask`
(never to `duplicate`, which would silently discard the spoken task).
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

try:
    from core.tasks import _request_openrouter_text  # type: ignore
except Exception:  # pragma: no cover
    _request_openrouter_text = None  # type: ignore


_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "at", "by",
    "with", "is", "are", "be", "do", "does", "done", "get", "make", "up",
    "this", "that", "it", "its", "my", "our", "your", "their",
    "today", "tomorrow", "now", "please", "task", "tasks", "todo", "need",
    "needs", "should", "must", "want", "wants", "add", "create", "new", "set",
}

# Matches tokens that are likely proper nouns / project names / domains:
# all-caps words, Mixed-Case words, dotted things like shivora.com, hyphen names.
_SUBJECT_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower()).strip(" ,.-:;")


def _subject_tokens(text: str) -> set[str]:
    """Extract salient subject tokens: uppercase / mixed-case words, domains,
    and any known vocab `actual` terms. Lowercased for comparison.
    """
    tokens: set[str] = set()
    for match in _SUBJECT_PATTERN.finditer(text or ""):
        tok = match.group(0)
        if len(tok) < 3 or tok.lower() in _STOPWORDS:
            continue
        # Proper-noun-ish: starts uppercase, OR all caps, OR contains . or -
        if tok[0].isupper() or tok.isupper() or "." in tok or "-" in tok:
            tokens.add(tok.lower())
    # Also include anything the vocab store has learned as a spelled-out term.
    try:
        from core.vocab import _get_corrections  # type: ignore
        for entry in _get_corrections():
            actual = (entry.get("actual") or "").lower()
            if actual and actual in text.lower():
                tokens.add(actual)
    except Exception:
        pass
    return tokens


def _shared_subject(a: str, b: str) -> Optional[str]:
    sa = _subject_tokens(a)
    sb = _subject_tokens(b)
    common = sa & sb
    if not common:
        return None
    # Pick the longest shared subject for a human-readable reason string.
    return max(common, key=len)


def _llm_arbitrate(new_text: str, existing_text: str) -> Optional[dict]:
    """Ask the LLM whether `new_text` duplicates, refines, or is independent
    of `existing_text`. Returns {"relation": ..., "reason": ...} or None.
    """
    if _request_openrouter_text is None:
        return None
    if not os.getenv("OPENROUTER_API_KEY", ""):
        return None
    system = (
        "You classify task pairs. Respond with a single-line JSON object: "
        '{"relation":"duplicate|subtask|independent","reason":"<short>"}. '
        'Use "duplicate" only when both describe the same action on the same '
        'subject. Use "subtask" when the new task is a narrower step, '
        'detail, or time-bound refinement of the existing task. Otherwise '
        '"independent". No extra text.'
    )
    user = f"EXISTING TASK: {existing_text}\nNEW TASK: {new_text}"
    try:
        raw = _request_openrouter_text(system, user, max_tokens=80) or ""
    except Exception:
        return None
    raw = raw.strip()
    if not raw:
        return None
    # Strip code fences if any.
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    # Extract the first JSON object.
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except Exception:
        return None
    relation = str(obj.get("relation", "")).strip().lower()
    if relation not in {"duplicate", "subtask", "independent"}:
        return None
    return {"relation": relation, "reason": str(obj.get("reason", "")).strip()}


def _strip_subject(text: str, subject: str) -> str:
    """Remove the subject token from the start/end of a task so a subtask
    reads cleanly ('shivora website due 6 pm' → 'due 6 pm')."""
    if not subject:
        return text
    pattern = re.compile(r"\b" + re.escape(subject) + r"\b", re.IGNORECASE)
    stripped = pattern.sub("", text)
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,.-:;")
    return stripped or text


def classify(candidate_text: str, existing: list[dict]) -> dict:
    """Classify a new task candidate against existing open tasks.

    Returns one of:
      {"action": "new"}
      {"action": "duplicate", "parent_id": str, "parent_text": str,
       "reason": str}
      {"action": "subtask", "parent_id": str, "parent_text": str,
       "subtask_text": str, "reason": str}
    """
    if not candidate_text or not candidate_text.strip():
        return {"action": "new"}

    cand_norm = _normalize(candidate_text)
    open_tasks = [t for t in (existing or []) if t.get("status") != "done"]

    # 1. Exact normalized match → duplicate.
    for task in open_tasks:
        if _normalize(task.get("text", "")) == cand_norm:
            return {
                "action": "duplicate",
                "parent_id": task.get("id", ""),
                "parent_text": task.get("text", ""),
                "reason": "exact match",
            }

    # 2. Shared salient subject check.
    best_task = None
    best_subject = None
    for task in open_tasks:
        shared = _shared_subject(candidate_text, task.get("text", ""))
        if shared:
            best_task = task
            best_subject = shared
            break

    if best_task is None:
        return {"action": "new"}

    # 3. LLM arbitration.
    verdict = _llm_arbitrate(candidate_text, best_task.get("text", ""))
    if verdict is None:
        # Fallback: shared subject → treat as subtask (never silently drop).
        subtask_text = _strip_subject(candidate_text, best_subject or "")
        return {
            "action": "subtask",
            "parent_id": best_task.get("id", ""),
            "parent_text": best_task.get("text", ""),
            "subtask_text": subtask_text,
            "reason": f"shares subject '{best_subject}'",
        }

    relation = verdict["relation"]
    if relation == "duplicate":
        return {
            "action": "duplicate",
            "parent_id": best_task.get("id", ""),
            "parent_text": best_task.get("text", ""),
            "reason": verdict.get("reason") or "same task",
        }
    if relation == "subtask":
        subtask_text = _strip_subject(candidate_text, best_subject or "")
        return {
            "action": "subtask",
            "parent_id": best_task.get("id", ""),
            "parent_text": best_task.get("text", ""),
            "subtask_text": subtask_text,
            "reason": verdict.get("reason") or "refines existing task",
        }
    return {"action": "new"}
