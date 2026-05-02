"""
core/vocab.py — User-curated STT vocabulary corrections (Layer 3).

Storage: %APPDATA%\Wiztant\vocab.json
Format: {"corrections": [{"heard": "grock", "actual": "Groq", "case_sensitive": false, ...}]}
"""

import re
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    from metaphone import doublemetaphone as _doublemetaphone  # type: ignore
except Exception:  # pragma: no cover
    _doublemetaphone = None

try:
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore
except Exception:  # pragma: no cover
    _rf_fuzz = None

_APPDATA = Path(os.environ.get("APPDATA", Path.home())) / "Wiztant"
_VOCAB_PATH = _APPDATA / "vocab.json"

_vocab_cache: Optional[dict] = None


def _vocab_path() -> Path:
    _APPDATA.mkdir(parents=True, exist_ok=True)
    return _VOCAB_PATH


def load_vocab() -> dict:
    global _vocab_cache
    path = _vocab_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                _vocab_cache = json.load(f)
        except Exception:
            _vocab_cache = {"corrections": []}
    else:
        _vocab_cache = {"corrections": []}
    return _vocab_cache


def save_vocab(data: dict) -> None:
    global _vocab_cache
    path = _vocab_path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)
    _vocab_cache = data


def _get_corrections() -> list:
    if _vocab_cache is None:
        load_vocab()
    return _vocab_cache.get("corrections", [])


def apply_corrections(text: str) -> str:
    """Apply user-curated vocab corrections using word-boundary regex."""
    for entry in _get_corrections():
        heard = entry.get("heard", "")
        actual = entry.get("actual", "")
        if not heard or not actual:
            continue
        flags = 0 if entry.get("case_sensitive", False) else re.IGNORECASE
        text = re.sub(r'\b' + re.escape(heard) + r'\b', actual, text, flags=flags)
    return text


def add_correction(heard: str, actual: str, case_sensitive: bool = False) -> None:
    data = load_vocab()
    corrections = data.setdefault("corrections", [])
    # Update existing entry if same 'heard' word exists
    for entry in corrections:
        if entry.get("heard", "").lower() == heard.lower():
            entry["actual"] = actual
            entry["case_sensitive"] = case_sensitive
            save_vocab(data)
            return
    corrections.append({
        "heard": heard,
        "actual": actual,
        "case_sensitive": case_sensitive,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "frequency": 0,
        "phonetic": _phonetic_key(actual),
    })
    save_vocab(data)


# =============================================================
#  PHONETIC MATCHING (for spell-out memory updates)
# =============================================================

_VOWELS = set("aeiouy")


def _phonetic_key(word: str) -> str:
    """Return a stable phonetic key. Uses Double Metaphone if available,
    else a vowel-collapsing fallback (still lets SHIVORA / SHEVORA collide).
    """
    w = (word or "").strip().lower()
    if not w:
        return ""
    if _doublemetaphone is not None:
        try:
            primary, _ = _doublemetaphone(w)
            if primary:
                return primary
        except Exception:
            pass
    # Fallback: keep leading char + strip interior vowels + collapse repeats.
    head = w[0]
    tail = re.sub(r"(.)\1+", r"\1", "".join(c for c in w[1:] if c not in _VOWELS))
    return (head + tail).upper()


def _similarity(a: str, b: str) -> float:
    a = (a or "").lower()
    b = (b or "").lower()
    if not a or not b:
        return 0.0
    if _rf_fuzz is not None:
        try:
            return float(_rf_fuzz.ratio(a, b)) / 100.0
        except Exception:
            pass
    # Small Levenshtein fallback
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la < lb:
        a, b = b, a
        la, lb = lb, la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    dist = prev[-1]
    return 1.0 - dist / max(la, 1)


def find_phonetic_match(word: str, *, threshold: float = 0.72) -> Optional[dict]:
    """Find an existing correction that likely represents the same word.

    Matches on:
      1) exact phonetic key on `actual` OR `heard`, OR
      2) rapidfuzz ratio on `actual` above threshold (ignores exact same word).
    Returns the correction entry dict (by reference from the live cache) or None.
    """
    if not word:
        return None
    key_new = _phonetic_key(word)
    best = None
    best_score = 0.0
    for entry in _get_corrections():
        actual = entry.get("actual", "") or ""
        heard = entry.get("heard", "") or ""
        if actual.lower() == word.lower():
            # Already the same — not an update.
            return entry
        stored_key = entry.get("phonetic") or _phonetic_key(actual)
        if key_new and stored_key and key_new == stored_key:
            return entry
        heard_key = _phonetic_key(heard)
        if key_new and heard_key and key_new == heard_key:
            return entry
        score = _similarity(actual, word)
        if score > best_score:
            best_score = score
            best = entry
    if best is not None and best_score >= threshold:
        return best
    return None


def update_correction(old_actual: str, new_actual: str) -> bool:
    """Replace the entry whose `actual == old_actual` with new_actual.

    Also inserts a forward alias so both the old phonetic spelling and the new
    phonetic spelling route to `new_actual`. Returns True on success.
    """
    if not old_actual or not new_actual:
        return False
    data = load_vocab()
    corrections = data.setdefault("corrections", [])
    target = None
    for entry in corrections:
        if (entry.get("actual", "") or "").lower() == old_actual.lower():
            target = entry
            break
    if target is None:
        return False
    # Preserve the old heard-form as an alias so Whisper's earlier mis-hearings
    # still map forward. If the alias entry already exists, skip.
    old_heard = (target.get("heard", "") or "").lower()
    target["heard"] = new_actual.lower()
    target["actual"] = new_actual
    target["phonetic"] = _phonetic_key(new_actual)
    target["updated_at"] = datetime.now(timezone.utc).isoformat()
    if old_heard and old_heard != new_actual.lower() and not any(
        (e.get("heard", "") or "").lower() == old_heard for e in corrections if e is not target
    ):
        corrections.append({
            "heard": old_heard,
            "actual": new_actual,
            "case_sensitive": bool(target.get("case_sensitive", False)),
            "added_at": datetime.now(timezone.utc).isoformat(),
            "frequency": 0,
            "phonetic": _phonetic_key(new_actual),
            "alias_of": new_actual,
        })
    save_vocab(data)
    return True


def delete_correction(heard: str) -> bool:
    data = load_vocab()
    corrections = data.get("corrections", [])
    before = len(corrections)
    data["corrections"] = [e for e in corrections if e.get("heard", "").lower() != heard.lower()]
    if len(data["corrections"]) < before:
        save_vocab(data)
        return True
    return False
