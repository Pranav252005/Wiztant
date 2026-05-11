"""
core/tune.py — Tune Engine: parses user corrections with GPT-5-nano and applies them.

The Tune hub replaces "Chat" as the place where users upgrade their agent.
Free-form text is parsed into structured corrections and routed to:
  • vocab.json      (STT word corrections)
  • memory.json     (agent behavior / user facts)
  • tune_keywords.json (STT prompt boost words)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from core.tune_prompts import TUNE_CLARIFY_FALLBACK, TUNE_SYSTEM_PROMPT

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# gpt-5-nano is OpenAI's newest cheapest model but currently has API issues with
# structured JSON output. gpt-4.1-nano is the cheapest stable alternative.
def _load_model_setting(key: str, default: str) -> str:
    try:
        import json
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return os.getenv(key, default)

TUNE_MODEL = _load_model_setting("TUNE_MODEL", "anthropic/claude-sonnet-4")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TUNE_KEYWORDS_PATH = _PROJECT_ROOT / "data" / "tune_keywords.json"

# ═══════════════════════════════════════════════════════════════════════════════
#  OPENAI CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

_openai_api_key = os.getenv("OPENAI_API_KEY", "")
_tune_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _tune_client
    if _tune_client is None and _openai_api_key:
        _tune_client = OpenAI(api_key=_openai_api_key)
    if _tune_client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured. Cannot use Tune.")
    return _tune_client


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TuneResult:
    ok: bool = False
    type: str = "clarify"          # vocab | memory | keywords | clarify
    items: List[dict] = field(default_factory=list)
    reply: str = ""
    applied: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
#  KEYWORDS STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_keywords() -> List[str]:
    if _TUNE_KEYWORDS_PATH.exists():
        try:
            data = json.loads(_TUNE_KEYWORDS_PATH.read_text(encoding="utf-8"))
            return data.get("keywords", [])
        except Exception:
            pass
    return []


def _save_keywords(keywords: List[str]) -> None:
    _TUNE_KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _TUNE_KEYWORDS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"keywords": keywords}, f, indent=2)
    tmp.replace(_TUNE_KEYWORDS_PATH)


def add_tune_keywords(new_words: List[str]) -> None:
    existing = set(_load_keywords())
    for w in new_words:
        existing.add(w.strip())
    _save_keywords(sorted(existing))


def get_tune_keywords() -> List[str]:
    return _load_keywords()


# ═══════════════════════════════════════════════════════════════════════════════
#  PARSER (GPT-5-nano)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_with_llm(text: str) -> dict:
    client = _get_client()
    resp = client.chat.completions.create(
        model=TUNE_MODEL,
        messages=[
            {"role": "system", "content": TUNE_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_completion_tokens=300,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════════
#  APPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_vocab(items: List[dict]) -> tuple[List[str], List[str]]:
    applied: List[str] = []
    errors: List[str] = []
    try:
        from core.vocab import add_correction
        for item in items:
            heard = str(item.get("heard", "")).strip()
            actual = str(item.get("actual", "")).strip()
            if heard and actual:
                add_correction(heard, actual, case_sensitive=False)
                applied.append(f"{heard} → {actual}")
            else:
                errors.append(f"Invalid vocab entry: {item}")
    except Exception as e:
        errors.append(f"Vocab apply failed: {e}")
    return applied, errors


def _apply_memory(items: List[dict]) -> tuple[List[str], List[str]]:
    applied: List[str] = []
    errors: List[str] = []
    try:
        import core.memory as memory_mod
        for item in items:
            cat = str(item.get("category", "preferences")).strip()
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if not key or not value:
                errors.append(f"Invalid memory entry: {item}")
                continue
            ok = memory_mod.update_from_tune(cat, key, value)
            if ok:
                applied.append(f"{cat}.{key} = {value}")
            else:
                errors.append(f"Failed to save memory: {item}")
    except Exception as e:
        errors.append(f"Memory apply failed: {e}")
    return applied, errors


def _apply_keywords(items: List[str]) -> tuple[List[str], List[str]]:
    applied: List[str] = []
    errors: List[str] = []
    try:
        words = [str(w).strip() for w in items if str(w).strip()]
        if words:
            add_tune_keywords(words)
            applied.extend(words)
    except Exception as e:
        errors.append(f"Keywords apply failed: {e}")
    return applied, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def process_tune(text: str) -> TuneResult:
    """
    Parse a user message from the Tune hub and apply corrections.
    Returns a TuneResult with confirmation reply and applied changes.
    """
    result = TuneResult()
    if not text or not text.strip():
        result.reply = "Type a correction or preference and I'll save it."
        return result

    # Parse intent with GPT-5-nano
    try:
        parsed = _parse_with_llm(text.strip())
    except Exception as e:
        result.reply = f"I couldn't parse that right now: {e}"
        result.errors.append(str(e))
        return result

    result.type = parsed.get("type", "clarify")
    result.items = parsed.get("items", [])
    result.reply = parsed.get("reply", TUNE_CLARIFY_FALLBACK)

    if result.type == "vocab":
        applied, errors = _apply_vocab(result.items)
        result.applied = applied
        result.errors = errors
        result.ok = len(applied) > 0

    elif result.type == "memory":
        applied, errors = _apply_memory(result.items)
        result.applied = applied
        result.errors = errors
        result.ok = len(applied) > 0

    elif result.type == "keywords":
        applied, errors = _apply_keywords(result.items)
        result.applied = applied
        result.errors = errors
        result.ok = len(applied) > 0

    else:
        # clarify or unknown
        result.ok = False

    return result


def tune_reply_to_dict(result: TuneResult) -> dict:
    """Serialize a TuneResult for the FastAPI response."""
    return {
        "ok": result.ok,
        "type": result.type,
        "reply": result.reply,
        "applied": result.applied,
        "errors": result.errors,
    }
