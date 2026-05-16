"""
core/dictation_smart.py — Local deterministic post-processing for dictated text.

Runs on ALL dictation output (free tier included) before any AI refinement.
Fast, zero-cost, no API calls.

Features:
  1. Email recognition   — "shivora at gmail dot com" → "shivora@gmail.com"
  2. Scratch-that        — "the password is PR scratch that the password is ABC" → "the password is ABC"
  3. Common spoken symbols — "percent" → "%", "dollar" → "$", etc. (when unambiguous)
"""

import re
from typing import Tuple, List

# ── Scratch-that phrases ──────────────────────────────────────
# When these appear, everything BEFORE the phrase is discarded.
# The last occurrence wins if multiple appear.
_SCRATCH_PHRASES = [
    "scratch that",
    "delete that",
    "scratch this",
    "delete this",
    "no wait",
    "no scratch",
    "correction",
    "actually i meant",
    "actually i mean",
    "i mean",
    "wait no",
    "never mind",
    "nevermind",
    "ignore that",
    "ignore this",
    "redo that",
    "take that back",
    "scratch the last",
]

# Build a single regex: case-insensitive, word boundaries where helpful.
_SCRATCH_PATTERN = re.compile(
    r"[\s.,;:!?]*\b(?:"
    + "|".join(re.escape(p).replace(r"\ ", r"[\s.,;:!?]+") for p in _SCRATCH_PHRASES)
    + r")\b[\s.,;:!?]*",
    re.IGNORECASE,
)

# ── Email spoken-form detection (token-based) ─────────────────
# Handles:
#   "shivora at gmail dot com" → "shivora@gmail.com"
#   "john dot doe at company dot co dot uk" → "john.doe@company.co.uk"
#   "at the rate", "at the rate of"
#   "dot", "period", "point"
#
# Uses token scanning rather than pure regex to correctly handle overlapping
# candidates (e.g. "me at john dot doe … at company …").

_DOT_WORDS = {"dot", "period", "point", "."}
_AT_WORDS = {"at", "@"}


def _tokenize_for_email(text: str) -> list:
    """Split text into (token, is_word, start_pos, end_pos) tuples."""
    tokens = []
    for m in re.finditer(r"(\w+|[^\w\s]+|\s+)", text):
        t = m.group(1)
        tokens.append((t, t.isalnum() and t[0].isalnum(), m.start(), m.end()))
    return tokens


def _scan_email_at_index(tokens: list, at_idx: int) -> Tuple[int, int, str]:
    """
    Given a token index pointing at an 'at' token, try to build an email
    by expanding left (local) and right (domain).

    Pattern:  word (dot word)*  at  word (dot word)+

    Returns (start_pos, end_pos, email) or (-1, -1, "") if invalid.
    """
    if at_idx >= len(tokens):
        return -1, -1, ""

    at_token, _, at_start, at_end = tokens[at_idx]
    if at_token.strip().lower() not in _AT_WORDS:
        return -1, -1, ""

    # ── Handle "at the rate" / "at the rate of" ──
    skip_after_at = 0
    if at_token.strip().lower() == "at":
        # Scan forward for "the rate" or "the rate of", skipping whitespace
        j = at_idx + 1
        while j < len(tokens) and tokens[j][0].strip() == "":
            j += 1
        if j < len(tokens) and tokens[j][0].strip().lower() == "the":
            j += 1
            while j < len(tokens) and tokens[j][0].strip() == "":
                j += 1
            if j < len(tokens) and tokens[j][0].strip().lower() == "rate":
                skip_after_at = j - at_idx  # everything up to and including "rate"
                j += 1
                while j < len(tokens) and tokens[j][0].strip() == "":
                    j += 1
                if j < len(tokens) and tokens[j][0].strip().lower() == "of":
                    skip_after_at = j - at_idx  # include "of" too

    # ── Expand left: local part ──
    # Pattern going left from 'at': word (dot word)*
    local_parts = []
    local_start_pos = at_start
    i = at_idx - 1
    expect_dot = False  # First we need a word, then optionally a dot

    while i >= 0:
        token, is_word, s, e = tokens[i]
        if not is_word:
            if token.strip() == "":
                i -= 1
                continue
            if token.strip() == "." and expect_dot:
                local_parts.insert(0, ".")
                i -= 1
                expect_dot = False
                continue
            break

        word = token.strip().lower()
        if expect_dot:
            if word in _DOT_WORDS:
                local_parts.insert(0, ".")
                i -= 1
                expect_dot = False  # After dot, expect word next
                continue
            else:
                break  # Expected dot but got regular word — stop
        else:
            # Expecting a word
            local_parts.insert(0, token.strip())
            local_start_pos = s
            expect_dot = True  # After word, next could be dot or stop
            i -= 1
            continue

    if not local_parts:
        return -1, -1, ""

    # Clean consecutive dots
    local_clean = []
    for p in local_parts:
        if p == ".":
            if local_clean and local_clean[-1] != ".":
                local_clean.append(p)
        else:
            local_clean.append(p)
    if not local_clean or local_clean[0] == ".":
        return -1, -1, ""
    local = "".join(local_clean)

    # ── Expand right: domain part ──
    # Pattern going right from 'at': word (dot word)+
    domain_parts = []
    domain_end_pos = at_end
    i = at_idx + 1 + skip_after_at
    expect_dot = False
    dot_count = 0

    while i < len(tokens):
        token, is_word, s, e = tokens[i]
        if not is_word:
            if token.strip() == "":
                i += 1
                continue
            if token.strip() == "." and expect_dot:
                # Peek ahead: only consume the dot if a word follows it
                j = i + 1
                while j < len(tokens) and tokens[j][0].strip() == "":
                    j += 1
                if j < len(tokens) and tokens[j][1]:  # next non-ws token is a word
                    domain_parts.append(".")
                    dot_count += 1
                    i += 1
                    expect_dot = False
                    continue
                else:
                    break  # Dot with no following word — stop (likely punctuation)
            break

        word = token.strip().lower()
        if expect_dot:
            if word in _DOT_WORDS:
                # Peek ahead: only consume the dot if a word follows it
                j = i + 1
                while j < len(tokens) and tokens[j][0].strip() == "":
                    j += 1
                if j < len(tokens) and tokens[j][1]:  # next non-ws token is a word
                    domain_parts.append(".")
                    dot_count += 1
                    i += 1
                    expect_dot = False
                    continue
                else:
                    break  # Dot with no following word — stop (likely punctuation)
            else:
                break  # Expected dot but got regular word — stop
        else:
            domain_parts.append(token.strip())
            domain_end_pos = e
            expect_dot = True
            i += 1
            continue

    if not domain_parts:
        return -1, -1, ""

    # Clean consecutive dots
    domain_clean = []
    for p in domain_parts:
        if p == ".":
            if domain_clean and domain_clean[-1] != ".":
                domain_clean.append(p)
        else:
            domain_clean.append(p)
    if not domain_clean or domain_clean[-1] == ".":
        return -1, -1, ""
    domain = "".join(domain_clean)

    # Require at least one dot in the domain
    if dot_count < 1:
        return -1, -1, ""

    email = f"{local}@{domain}"
    return local_start_pos, domain_end_pos, email


def _find_all_emails(text: str) -> list:
    """Return list of (start, end, email) tuples for all valid spoken emails."""
    tokens = _tokenize_for_email(text)
    candidates = []
    for idx, (token, is_word, s, e) in enumerate(tokens):
        if not is_word:
            continue
        word = token.strip().lower()
        if word in _AT_WORDS:
            start_pos, end_pos, email = _scan_email_at_index(tokens, idx)
            if start_pos >= 0:
                candidates.append((start_pos, end_pos, email))
    return candidates


def _replace_emails(text: str) -> Tuple[str, int]:
    """
    Find all spoken-email sequences and replace them.
    Prefers longer matches over shorter ones to avoid partial matches.
    """
    if not text or not text.strip():
        return text, 0

    candidates = _find_all_emails(text)
    if not candidates:
        return text, 0

    # Sort by length descending so longer matches win
    candidates.sort(key=lambda c: c[1] - c[0], reverse=True)

    result = []
    last_end = 0
    used_spans = []
    count = 0

    for start, end, email in candidates:
        # Skip if this overlaps with an already-used span
        if any(start < u_end and end > u_start for u_start, u_end in used_spans):
            continue

        result.append(text[last_end:start])
        result.append(email)
        used_spans.append((start, end))
        last_end = end
        count += 1

    result.append(text[last_end:])
    return "".join(result), count


# ── Spoken symbol conversion (unambiguous contexts only) ──────
# Only convert when the word is clearly a symbol instruction, not regular prose.
# Applied AFTER email conversion so we don't double-process.
_SYMBOL_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    # Percent sign — only when it looks like a number context
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+percent\b", re.IGNORECASE), r"\1%"),
    # Dollar sign — number context
    (re.compile(r"\bdollar sign\s+(\d+)\b", re.IGNORECASE), r"$\1"),
    (re.compile(r"\bdollars?\s+(\d+)\b", re.IGNORECASE), r"$\1"),
    # Hash / pound
    (re.compile(r"\bhash\s+(\w+)", re.IGNORECASE), r"#\1"),
    (re.compile(r"\bpound sign\b", re.IGNORECASE), "#"),
    # Ampersand
    (re.compile(r"\band sign\b", re.IGNORECASE), "&"),
    (re.compile(r"\bampersand\b", re.IGNORECASE), "&"),
    # Asterisk / star
    (re.compile(r"\basterisk\b", re.IGNORECASE), "*"),
    (re.compile(r"\bstar\s+(\w+)", re.IGNORECASE), r"*\1"),
    # Plus
    (re.compile(r"\bplus sign\b", re.IGNORECASE), "+"),
    # Equals
    (re.compile(r"\bequals sign\b", re.IGNORECASE), "="),
    # Standalone symbols that may slip through or appear in non-email contexts
    (re.compile(r"\bslash\b", re.IGNORECASE), "/"),
    # NOTE: "\but\b" → "@" was removed because it destroys normal English sentences.
    # Email @ conversion is already handled by the dedicated email scanner above.
    (re.compile(r"\bat\s+the\s+rate\b", re.IGNORECASE), "@"),
]


def apply_scratch_that(text: str) -> Tuple[str, bool]:
    """
    Remove text before the last scratch-that phrase.

    Returns:
        (cleaned_text, was_modified)
    """
    if not text or not text.strip():
        return text, False

    # Find all split points
    splits = list(_SCRATCH_PATTERN.finditer(text))
    if not splits:
        return text, False

    # Use the LAST scratch phrase — keep only what comes after it
    last_match = splits[-1]
    cleaned = text[last_match.end():].strip()

    return cleaned, True


def convert_emails(text: str) -> Tuple[str, int]:
    """
    Convert spoken email forms to real email addresses.

    Returns:
        (converted_text, count)
    """
    if not text or not text.strip():
        return text, 0
    return _replace_emails(text)


def convert_symbols(text: str) -> Tuple[str, int]:
    """
    Convert spoken symbols to actual characters in appropriate contexts.

    Returns:
        (converted_text, count)
    """
    if not text or not text.strip():
        return text, 0

    count = 0
    result = text
    for pattern, replacement in _SYMBOL_REPLACEMENTS:
        new_result, n = pattern.subn(replacement, result)
        if n:
            result = new_result
            count += n

    return result, count


# ── Entity / known-word corrections ───────────────────────────
# Applies the massive dictionaries from core.voice (AI names, frameworks,
# file extensions, etc.) as a backup layer when clean_transcript() was
# skipped — e.g. streaming STT path before the hotkeys.py fix.
# Also provides detailed change logging so the user can see what was fixed.

# Eagerly load entity dictionaries from core.voice (best-effort)
_ENTITY_MULTI_FIXES: List[Tuple[re.Pattern, str]] = []
_ENTITY_SINGLE_PATTERN: re.Pattern | None = None
_ENTITY_SINGLE_MAP: dict = {}

try:
    from core.voice import WORD_FIXES as _WORD_FIXES
    for _heard, _actual in _WORD_FIXES.items():
        if " " in _heard:
            _ENTITY_MULTI_FIXES.append((re.compile(r'\b' + re.escape(_heard) + r'\b', re.IGNORECASE), _actual))
        else:
            _ENTITY_SINGLE_MAP[_heard.lower()] = _actual
    if _ENTITY_SINGLE_MAP:
        _ENTITY_SINGLE_PATTERN = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in _ENTITY_SINGLE_MAP) + r')\b',
            re.IGNORECASE
        )
except Exception:
    pass  # Fallback: empty patterns (no entity fixes)


def convert_entities(text: str) -> Tuple[str, int, List[str]]:
    """
    Apply known-entity corrections (AI names, frameworks, file extensions, etc.).

    Returns:
        (converted_text, count, list_of_changes)
    """
    if not text or not text.strip():
        return text, 0, []

    if not _ENTITY_MULTI_FIXES and not _ENTITY_SINGLE_PATTERN:
        return text, 0, []

    result = text
    changes: List[str] = []
    count = 0

    # Multi-word first (so "chat gpt" wins over "gpt" alone)
    for pattern, actual in _ENTITY_MULTI_FIXES:
        new_result, n = pattern.subn(actual, result)
        if n:
            # Extract what changed for logging
            for m in pattern.finditer(result):
                heard = m.group(0)
                if heard != actual:
                    changes.append(f'{heard}->{actual}')
                    count += 1
            result = new_result

    # Single-word
    if _ENTITY_SINGLE_PATTERN and _ENTITY_SINGLE_MAP:
        for m in _ENTITY_SINGLE_PATTERN.finditer(result):
            heard = m.group(0)
            actual = _ENTITY_SINGLE_MAP.get(heard.lower(), heard)
            if heard != actual:
                changes.append(f'{heard}->{actual}')
                count += 1
        # Now do the actual replacement in one pass
        result = _ENTITY_SINGLE_PATTERN.sub(
            lambda m: _ENTITY_SINGLE_MAP.get(m.group(0).lower(), m.group(0)),
            result
        )

    return result, count, changes


# ── Re-glue spaced sequences ─────────────────────────────────
# Fixes cases where upstream _smart_punctuation() split apart glued tokens.
_REGLUE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # File extensions / TLDs
    (re.compile(r'\.\s+(com|org|net|io|ai|py|js|ts|json|txt|md|html|css|env|exe|git|yml|yaml)', re.IGNORECASE), r'.\1'),
    # @ symbol glued to domain/email local part
    (re.compile(r'@\s+(\w+)'), r'@\1'),
    # Slash glued to path
    (re.compile(r'/\s+(\S+)'), r'/\1'),
]


def _reglue_spaced_sequences(text: str) -> Tuple[str, int]:
    """Fix spaced-out extensions, URLs, and symbols. Returns (fixed_text, count)."""
    if not text or not text.strip():
        return text, 0
    count = 0
    for pattern, replacement in _REGLUE_PATTERNS:
        new_text, n = pattern.subn(replacement, text)
        if n:
            text = new_text
            count += n
    return text, count


def smart_dictate(text: str) -> dict:
    """
    Full smart dictation pipeline.

    Order matters:
      1. scratch-that  (remove bad text first)
      2. entity fixes  (AI names, frameworks, file extensions)
      3. email conversion
      4. symbol conversion
      5. re-glue       (fix spaced-out extensions / paths)

    Returns:
        {
            "text": str,           # final processed text
            "original": str,       # input text
            "scratch_applied": bool,
            "entities_fixed": int,
            "emails_converted": int,
            "symbols_converted": int,
            "changes": List[str],  # human-readable log of changes
        }
    """
    if not text or not text.strip():
        return {
            "text": text,
            "original": text,
            "scratch_applied": False,
            "entities_fixed": 0,
            "emails_converted": 0,
            "symbols_converted": 0,
            "reglued": 0,
            "changes": [],
        }

    original = text
    changes: List[str] = []

    # Step 1: scratch-that
    text, scratched = apply_scratch_that(text)
    if scratched:
        changes.append("scratch-that: removed text before correction phrase")
        if not text.strip():
            return {
                "text": "",
                "original": original,
                "scratch_applied": True,
                "entities_fixed": 0,
                "emails_converted": 0,
                "symbols_converted": 0,
                "reglued": 0,
                "changes": changes,
            }

    # Step 2: entity / known-word fixes
    text, entity_count, entity_changes = convert_entities(text)
    if entity_count:
        changes.append(f"entity: fixed {entity_count} known word(s)")
        changes.extend(entity_changes)

    # Step 3: emails
    text, email_count = convert_emails(text)
    if email_count:
        changes.append(f"email: converted {email_count} spoken email(s)")

    # Step 4: symbols
    text, sym_count = convert_symbols(text)
    if sym_count:
        changes.append(f"symbol: converted {sym_count} spoken symbol(s)")

    # Step 5: re-glue spaced-out extensions / paths / emails
    text, glue_count = _reglue_spaced_sequences(text)
    if glue_count:
        changes.append(f"re-glue: fixed {glue_count} spaced sequence(s)")

    return {
        "text": text,
        "original": original,
        "scratch_applied": scratched,
        "entities_fixed": entity_count,
        "emails_converted": email_count,
        "symbols_converted": sym_count,
        "reglued": glue_count,
        "changes": changes,
    }


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        # Emails
        ("My email is shivora at gmail dot com", "My email is shivora@gmail.com"),
        ("Contact me at john dot doe at company dot co dot uk", "Contact me at john.doe@company.co.uk"),
        ("Reach out to admin at the rate of example dot org", "Reach out to admin@example.org"),
        ("Email: test at domain period com", "Email: test@domain.com"),
        # Scratch-that
        ("The password would be PR scratch that the password would be ABC", "the password would be ABC"),
        ("Send it to john at gmail dot com no wait send it to jane at gmail dot com", "send it to jane@gmail.com"),
        ("The meeting is at 5pm actually i meant 6pm", "6pm"),
        ("scratch that hello world", "hello world"),
        # Symbols
        ("The tax is 15 percent", "The tax is 15%"),
        ("It costs dollar sign 50", "It costs $50"),
        # Entities
        ("I use chat gpt and open ai", "I use ChatGPT and OpenAI"),
        ("He uses deep seek and grok", "He uses DeepSeek and Grok"),
        # Combined
        ("My email is old at yahoo dot com scratch that my email is new at gmail dot com", "my email is new@gmail.com"),
    ]

    for inp, expected in tests:
        result = smart_dictate(inp)
        ok = "✅" if result["text"] == expected else "❌"
        print(f"{ok}  IN:  {inp}")
        print(f"   OUT: {result['text']}")
        if result["text"] != expected:
            print(f"   EXP: {expected}")
        print(f"   Changes: {result['changes']}")
        print()
