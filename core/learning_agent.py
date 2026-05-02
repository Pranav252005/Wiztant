"""
core/learning_agent.py — Auto-learn vocabulary corrections from user edits.

Whenever the user edits text that originally came from dictation (or anywhere
in the app), this module compares the original with the corrected version,
finds word-level changes, and silently saves them to vocab.json so that the
next time Whisper mis-hears the same word, it is auto-corrected.
"""

import difflib
import re
from typing import List, Tuple

from core.vocab import add_correction


def _tokenize(text: str) -> List[str]:
    """Split text into word-ish tokens, preserving spacing info roughly."""
    return re.findall(r"[A-Za-z0-9_\-\']+|[.,!?;:/@#%&*()\[\]{}]", text or "")


def _is_trivial_change(original: str, corrected: str) -> bool:
    """Ignore pure case changes, punctuation-only changes, or tiny edits."""
    if original.lower() == corrected.lower():
        return True
    # Ignore pure punctuation differences
    orig_alpha = re.sub(r"[^a-z0-9]", "", original.lower())
    corr_alpha = re.sub(r"[^a-z0-9]", "", corrected.lower())
    if orig_alpha == corr_alpha:
        return True
    return False


def learn_from_edit(original: str, corrected: str) -> List[Tuple[str, str]]:
    """
    Compare original text with user-corrected text and save word-level
    corrections to the vocabulary database.

    Returns a list of (heard, actual) tuples that were learned.
    """
    original = (original or "").strip()
    corrected = (corrected or "").strip()
    if not original or not corrected:
        return []

    # Fast path: if the strings are identical, nothing to learn
    if original == corrected:
        return []

    orig_tokens = _tokenize(original)
    corr_tokens = _tokenize(corrected)

    # Use SequenceMatcher to find aligned word changes
    sm = difflib.SequenceMatcher(None, orig_tokens, corr_tokens)

    learned: List[Tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            orig_chunk = " ".join(orig_tokens[i1:i2])
            corr_chunk = " ".join(corr_tokens[j1:j2])
            # Only learn single-word → single-word replacements
            if (i2 - i1) == 1 and (j2 - j1) == 1:
                heard = orig_chunk.strip()
                actual = corr_chunk.strip()
                if heard and actual and not _is_trivial_change(heard, actual):
                    # Additional guard: don't save very long strings as "words"
                    if len(heard) <= 40 and len(actual) <= 40:
                        add_correction(heard, actual)
                        learned.append((heard, actual))
        elif tag == "insert":
            # User added words — not a mis-hearing, skip
            pass
        elif tag == "delete":
            # User deleted words — could be a false positive from Whisper,
            # but we don't have a clean "heard→actual" mapping, so skip
            pass

    return learned
