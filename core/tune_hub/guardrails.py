"""
TuneHub boundary guardrails — enforce that tuners can only touch
registered features and inject whitelisted keys.

Prevents:
- Path traversal in persistence
- Arbitrary key injection into feature_input
- Mutation of non-injectable keys
- Feature spoofing / unknown feature resolution
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Dict, Tuple


# =============================================================
#  CONSTANTS
# =============================================================


ALLOWED_FEATURES: frozenset[str] = frozenset({"reprompt", "dictation", "agent"})

# Keys each tuner is permitted to add or modify in feature_input.
INJECTABLE_KEYS: Dict[str, frozenset[str]] = {
    "reprompt": frozenset({"persona_weights", "tune_id", "task_type"}),
    "dictation": frozenset({
        "correction_map",
        "tune_id",
        "domain",
        "auto_apply_threshold",
        "text",
        "applied_corrections",
    }),
    "agent": frozenset({"recipe", "tune_id", "dsl_code", "recipe_hint"}),
}

# Safe suffixes for persistence files.
ALLOWED_SUFFIXES: frozenset[str] = frozenset({".json", ".jsonl", ".pkl"})


# =============================================================
#  EXCEPTIONS
# =============================================================


class TuneBoundaryViolation(Exception):
    """Raised when a tuner violates an architectural boundary."""

    pass


# =============================================================
#  GUARD
# =============================================================


class TuneBoundaryGuard:
    """
    Central authority for TuneHub boundary enforcement.

    Stateless — all decisions are deterministic given inputs.
    """

    @classmethod
    def validate_feature_name(cls, feature_name: str) -> Tuple[bool, str]:
        """
        Return (ok, reason). Rejects unknown or empty feature names.
        """
        if not feature_name or not isinstance(feature_name, str):
            return False, "feature_name must be a non-empty string"
        if feature_name not in ALLOWED_FEATURES:
            return False, f"feature '{feature_name}' is not in ALLOWED_FEATURES"
        return True, ""

    @classmethod
    def validate_injection(
        cls,
        feature_name: str,
        original: Dict[str, Any],
        modified: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Return (ok, reason). Ensures:
        1. feature_name is known
        2. No keys were removed
        3. Only injectable keys were added or changed
        4. Non-injectable keys retain their original values
        """
        ok, reason = cls.validate_feature_name(feature_name)
        if not ok:
            return False, reason

        allowed = INJECTABLE_KEYS.get(feature_name, frozenset())

        # Rule 1: no keys removed
        for key in original:
            if key not in modified:
                return False, f"key '{key}' was removed from feature_input"

        # Rule 2: only allowed keys may be added or modified
        for key, new_val in modified.items():
            if key not in original:
                if key not in allowed:
                    return (
                        False,
                        f"key '{key}' is not an injectable key for feature '{feature_name}'",
                    )
            else:
                old_val = original[key]
                if key not in allowed and new_val != old_val:
                    return (
                        False,
                        f"key '{key}' was mutated but is not injectable for feature '{feature_name}'",
                    )

        return True, ""

    @classmethod
    def sanitize_persistence_path(
        cls,
        base_dir: Path,
        user_id: str,
        feature_name: str,
        task_signature: str,
        suffix: str,
    ) -> Path:
        """
        Build a safe file path under base_dir.

        Raises:
            TuneBoundaryViolation: If path would escape base_dir or contains unsafe characters.
            ValueError: If suffix is not in ALLOWED_SUFFIXES.
        """
        if not any(str(suffix).endswith(ext) for ext in ALLOWED_SUFFIXES):
            raise ValueError(
                f"suffix '{suffix}' is not allowed; must end with one of {ALLOWED_SUFFIXES}"
            )

        for raw_name, raw_val in [
            ("user_id", user_id),
            ("feature_name", feature_name),
            ("task_signature", task_signature),
        ]:
            if ".." in raw_val:
                raise TuneBoundaryViolation(
                    f"'{raw_name}' contains path traversal '..': {raw_val!r}"
                )

        safe_user = cls._sanitize_segment(user_id, max_len=32)
        safe_feature = cls._sanitize_segment(feature_name, max_len=32)
        safe_sig = cls._sanitize_segment(task_signature, max_len=64)

        filename = f"{safe_user}_{safe_feature}_{safe_sig}{suffix}"
        target = base_dir / filename

        # Resolve to absolute and ensure it is still under base_dir
        try:
            resolved = target.resolve(strict=False)
            resolved_base = base_dir.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise TuneBoundaryViolation(f"path resolution failed: {exc}") from exc

        if not str(resolved).startswith(str(resolved_base) + "/") and resolved != resolved_base:
            raise TuneBoundaryViolation(
                f"path '{resolved}' escapes base directory '{resolved_base}'"
            )

        return target

    @classmethod
    def ensure_immutable_input(cls, feature_input: Dict[str, Any]) -> Dict[str, Any]:
        """Return a deep copy so the original dict is never mutated in-place."""
        return copy.deepcopy(feature_input)

    @staticmethod
    def _sanitize_segment(segment: str, max_len: int = 64) -> str:
        """
        Strip path separators, null bytes, parent references, and control chars.
        """
        if not isinstance(segment, str):
            segment = str(segment)
        # Null bytes
        segment = segment.replace("\x00", "")
        # Path traversal
        segment = segment.replace("..", "_")
        # Directory separators
        segment = segment.replace("/", "_").replace("\\", "_")
        # Control characters
        segment = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", segment)
        # Length limit
        return segment[:max_len]
