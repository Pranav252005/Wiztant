"""core/dictation_correction.py — Unified dictation correction learning pipeline.

Three interconnected features:
  1. Undo Hook        — capture real user edits from the preview window
  2. Phonetic Fuzzy   — Double Metaphone + Soundex indexed correction map
  3. Domain Context   — previous 3-5 words disambiguate multi-domain terms
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from metaphone import doublemetaphone as _dm  # type: ignore
except Exception:
    _dm = None

# ── Domain keyword maps ───────────────────────────────────────
_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "crypto": {
        "eth", "ethereum", "bitcoin", "btc", "wallet", "token", "defi",
        "nft", "blockchain", "swap", "stake", "dao", "airdrop", "ledger",
    },
    "medical": {
        "patient", "diagnosis", "symptom", "treatment", "arrhythmia",
        "prescription", "medication", "dosage", "clinical", "prognosis",
    },
    "devops": {
        "deploy", "prod", "production", "staging", "ci", "cd", "pipeline",
        "kubernetes", "docker", "terraform", "ansible", "git", "github",
    },
}

# ── Soundex fallback (inline, no external dep) ────────────────
_VOWELS_Y = set("aeiouy")
_SOUNDEX_MAP = str.maketrans(
    "bfpvcgjkqsxzdtlmnr",
    "111122222222334556"
)


def _soundex(word: str) -> str:
    """Simple Soundex encoder (4-char code)."""
    w = (word or "").strip().lower()
    if not w:
        return "0000"
    head = w[0].upper()
    # Drop first letter, translate consonants to digits
    tail = w[1:].translate(_SOUNDEX_MAP)
    # Drop vowels, y, h, w (Soundex ignores these after first letter)
    _drop = _VOWELS_Y | {"h", "w"}
    tail = "".join(c for c in tail if c not in _drop)
    # Collapse consecutive same digits
    collapsed = []
    for c in tail:
        if not collapsed or c != collapsed[-1]:
            collapsed.append(c)
    # Pad or trim to 3 digits
    result = head + "".join(collapsed[:3])
    return (result + "000")[:4]


# ── Phonetic key builder ──────────────────────────────────────
def phonetic_keys(word: str) -> Tuple[str, str]:
    """Return (double_metaphone_primary, soundex) for a word."""
    w = (word or "").strip().lower()
    if not w:
        return "", ""
    dm_primary = ""
    if _dm is not None:
        try:
            p, _ = _dm(w)
            dm_primary = p or ""
        except Exception:
            pass
    return dm_primary, _soundex(w)


# ── Domain detection ──────────────────────────────────────────
def detect_domain(context_words: List[str]) -> Optional[str]:
    """Scan the previous 3-5 words and return the best-matching domain."""
    if not context_words:
        return None
    window = [w.lower().strip(".,;:!?") for w in context_words[-5:]]
    scores: dict[str, int] = defaultdict(int)
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for w in window:
            if w in keywords:
                scores[domain] += 1
    if not scores:
        return None
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] >= 1 else None


# ── Correction storage ────────────────────────────────────────
_CORRECTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "dictation_corrections.json"
_corrections_lock = threading.Lock()


def _load_corrections() -> List[dict]:
    _CORRECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _CORRECTIONS_PATH.exists():
        return []
    try:
        with open(_CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("corrections", [])
    except Exception:
        return []


def _save_corrections(corrections: List[dict]) -> None:
    tmp = _CORRECTIONS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"corrections": corrections}, f, indent=2, ensure_ascii=False)
    tmp.replace(_CORRECTIONS_PATH)


# In-memory phonetic index: phonetic_key -> list of correction entries
_phonetic_index: Dict[str, List[dict]] = {}
_index_built = False


def _build_index() -> None:
    """Rebuild the in-memory phonetic index from disk."""
    global _phonetic_index, _index_built
    corrections = _load_corrections()
    idx: Dict[str, List[dict]] = defaultdict(list)
    for entry in corrections:
        dm = entry.get("dm_key", "")
        sx = entry.get("soundex_key", "")
        if dm:
            idx[dm].append(entry)
        if sx and sx != dm:
            idx[sx].append(entry)
    _phonetic_index = dict(idx)
    _index_built = True


def _ensure_index() -> None:
    if not _index_built:
        _build_index()


def _index_entry(entry: dict) -> None:
    """Add a single entry to the in-memory index."""
    global _phonetic_index
    dm = entry.get("dm_key", "")
    sx = entry.get("soundex_key", "")
    if dm:
        _phonetic_index.setdefault(dm, []).append(entry)
    if sx and sx != dm:
        _phonetic_index.setdefault(sx, []).append(entry)


# ── Public API: record a correction ───────────────────────────
def record_correction(
    source: str,
    target: str,
    context_before: List[str] | None = None,
    confidence: float = 1.0,
    domain: str | None = None,
) -> dict:
    """Store a ground-truth correction pair, building/updating the phonetic index."""
    _ensure_index()
    source = source.strip()
    target = target.strip()
    if not source or not target or source.lower() == target.lower():
        return {}

    domain = domain or detect_domain(context_before or [])
    dm_key, sx_key = phonetic_keys(source)

    entry = {
        "id": f"{abs(hash(source + target)) % 100000000:08d}",
        "source": source,
        "target": target,
        "dm_key": dm_key,
        "soundex_key": sx_key,
        "domain": domain,
        "confidence": confidence,
        "frequency": 1,
        "context_signature": (context_before or [])[-3:],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    with _corrections_lock:
        corrections = _load_corrections()
        # Find existing entry with same source+domain (or just same source)
        existing_idx = None
        for i, c in enumerate(corrections):
            if c.get("source", "").lower() == source.lower():
                if domain and c.get("domain") == domain:
                    existing_idx = i
                    break
                if not domain or not c.get("domain"):
                    existing_idx = i
                    break
        if existing_idx is not None:
            old = corrections[existing_idx]
            old["target"] = target
            old["frequency"] = old.get("frequency", 0) + 1
            old["confidence"] = min(1.0, old.get("confidence", 0) + 0.05)
            old["updated_at"] = datetime.now(timezone.utc).isoformat()
            old["domain"] = domain or old.get("domain")
            entry = old
        else:
            corrections.append(entry)
        _save_corrections(corrections)
        _index_entry(entry)

    return entry


# ── Public API: apply corrections to text ─────────────────────
def apply_corrections(
    text: str,
    min_confidence: float = 0.7,
    context_window: List[str] | None = None,
) -> Tuple[str, List[str]]:
    """Apply phonetic+domain-aware corrections to text.

    Returns:
        (corrected_text, list_of_changes)
    """
    _ensure_index()
    if not text or not text.strip():
        return text, []

    active_domain = detect_domain(context_window or [])
    words = text.split()
    corrected_words = []
    changes: List[str] = []

    for i, word in enumerate(words):
        # Extract leading/trailing punctuation, keep core word
        m = re.match(r"^(?P<pre>[^\w]*)(?P<core>\w+)(?P<post>[^\w]*)$", word)
        if not m:
            corrected_words.append(word)
            continue
        pre, core, post = m.group("pre"), m.group("core"), m.group("post")
        if len(core) < 3:
            corrected_words.append(word)
            continue

        dm_key, sx_key = phonetic_keys(core)
        candidates: List[dict] = []
        for key in (dm_key, sx_key):
            if key and key in _phonetic_index:
                candidates.extend(_phonetic_index[key])

        if not candidates:
            corrected_words.append(word)
            continue

        # Filter by domain if we detected one
        if active_domain:
            domain_matches = [c for c in candidates if c.get("domain") == active_domain]
            if domain_matches:
                candidates = domain_matches

        # Filter by confidence
        candidates = [c for c in candidates if c.get("confidence", 0) >= min_confidence]
        if not candidates:
            corrected_words.append(word)
            continue

        # Deduplicate by source
        seen_sources: set[str] = set()
        unique: List[dict] = []
        for c in candidates:
            s = c.get("source", "").lower()
            if s not in seen_sources:
                seen_sources.add(s)
                unique.append(c)
        candidates = unique

        if len(candidates) == 1:
            # Auto-replace silently
            target = candidates[0]["target"]
            corrected_words.append(pre + target + post)
            changes.append(f"{core}->{target}")
        else:
            # Multiple candidates — pick highest frequency
            best = max(candidates, key=lambda c: c.get("frequency", 0))
            target = best["target"]
            corrected_words.append(pre + target + post)
            changes.append(f"{core}->{target}")

    return " ".join(corrected_words), changes


# ── Undo Hook subsystem ───────────────────────────────────────
_UNDO_HOOKS: dict[str, dict] = {}  # session_id -> hook state
_HOOK_LOCK = threading.Lock()


def start_undo_hook(session_id: str, original_text: str, stt_text: str) -> None:
    """Called when dictation pastes into the preview window. Starts the 5s timer."""
    with _HOOK_LOCK:
        # Cancel any existing timer for this session
        old = _UNDO_HOOKS.pop(session_id, None)
        if old and old.get("timer") and old["timer"].is_alive():
            old["timer"].cancel()

        _UNDO_HOOKS[session_id] = {
            "original_text": original_text,
            "stt_text": stt_text,
            "current_text": stt_text,
            "optimized_text": None,
            "started_at": time.time(),
            "edited": False,
            "copied": False,
            "copy_at": 0.0,
            "closed": False,
            "timer": None,
        }

        def _expire():
            with _HOOK_LOCK:
                hook = _UNDO_HOOKS.get(session_id)
                if not hook:
                    return
                # If copy happened, wait the configured extra time
                if hook.get("copied"):
                    wait_sec = _load_copy_wait_sec()
                    elapsed_since_copy = time.time() - hook["copy_at"]
                    if elapsed_since_copy < wait_sec:
                        # Reschedule for remaining time
                        remaining = wait_sec - elapsed_since_copy
                        timer = threading.Timer(remaining, _expire)
                        timer.daemon = True
                        timer.start()
                        hook["timer"] = timer
                        return
                _finalize_hook(session_id)

        timer = threading.Timer(5.0, _expire)
        timer.daemon = True
        timer.start()
        _UNDO_HOOKS[session_id]["timer"] = timer


def _load_copy_wait_sec() -> int:
    try:
        settings_path = Path(__file__).resolve().parent.parent / "data" / "settings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return int(data.get("correction_copy_wait_sec", 3))
    except Exception:
        pass
    return 3


def on_preview_edit(session_id: str, new_text: str) -> None:
    """Called when user manually edits text in the preview window."""
    with _HOOK_LOCK:
        hook = _UNDO_HOOKS.get(session_id)
        if not hook:
            return
        hook["current_text"] = new_text
        hook["edited"] = True


def on_preview_undo(session_id: str, new_text: str) -> None:
    """Called when user hits undo in the preview window."""
    with _HOOK_LOCK:
        hook = _UNDO_HOOKS.get(session_id)
        if not hook:
            return
        hook["current_text"] = new_text
        hook["edited"] = True


def on_preview_copy(session_id: str) -> None:
    """Called when user copies text from the preview window."""
    with _HOOK_LOCK:
        hook = _UNDO_HOOKS.get(session_id)
        if not hook:
            return
        hook["copied"] = True
        hook["copy_at"] = time.time()


def on_preview_close(session_id: str) -> None:
    """Called when user closes the preview window."""
    with _HOOK_LOCK:
        hook = _UNDO_HOOKS.get(session_id)
        if not hook:
            return
        hook["closed"] = True
        _finalize_hook(session_id)


def on_preview_optimize(session_id: str, optimized: str) -> None:
    """Called when user optimizes the prompt in the preview window."""
    with _HOOK_LOCK:
        hook = _UNDO_HOOKS.get(session_id)
        if not hook:
            return
        hook["optimized_text"] = optimized
        hook["edited"] = True


def _finalize_hook(session_id: str) -> None:
    """Finalize the undo hook: store the correction pair if text changed."""
    hook = _UNDO_HOOKS.pop(session_id, None)
    if not hook:
        return

    # Cancel any pending timer
    timer = hook.get("timer")
    if timer and timer.is_alive():
        timer.cancel()

    stt_text = hook.get("stt_text", "")
    final_text = hook.get("optimized_text") or hook.get("current_text", "")

    if not stt_text or not final_text or stt_text.strip() == final_text.strip():
        return

    # Compute per-word diffs for confidence scoring
    stt_words = stt_text.split()
    final_words = final_text.split()

    # Simple approach: if lengths differ significantly, store whole-text correction
    # Otherwise, store per-word corrections for words that changed
    if len(stt_words) == len(final_words):
        for sw, fw in zip(stt_words, final_words):
            if sw.lower() != fw.lower():
                ctx = stt_words[: stt_words.index(sw)] if sw in stt_words else []
                record_correction(sw, fw, context_before=ctx, confidence=0.85)
    else:
        # Store as a phrase-level correction
        record_correction(stt_text, final_text, confidence=0.7)

    # Also push to vocab for immediate effect in the next dictation
    try:
        from core.vocab import add_correction
        for sw, fw in zip(stt_words, final_words):
            if sw.lower() != fw.lower() and len(sw) > 2:
                add_correction(sw, fw)
    except Exception:
        pass


def get_correction_stats() -> dict:
    """Return statistics about the correction system."""
    _ensure_index()
    corrections = _load_corrections()
    domains: dict[str, int] = defaultdict(int)
    for c in corrections:
        d = c.get("domain") or "general"
        domains[d] += 1
    return {
        "total_corrections": len(corrections),
        "phonetic_index_keys": len(_phonetic_index),
        "domain_breakdown": dict(domains),
    }
