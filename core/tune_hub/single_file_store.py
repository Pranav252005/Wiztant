"""Single-file canonical store for TuneHub tuned parameters.

Each tunable feature writes to exactly ONE file on deploy().
Feature consumers read from that same file at runtime.
This guarantees the tune is isolated to a single known location.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

# =============================================================
#  CONSTANTS
# =============================================================

TUNE_MODELS_DIR = Path("data/tune_models")

CANONICAL_FILES: Dict[str, Path] = {
    "reprompt": TUNE_MODELS_DIR / "reprompt_tune.json",
    "dictation": TUNE_MODELS_DIR / "dictation_tune.json",
    "agent": TUNE_MODELS_DIR / "agent_tune.json",
}


# =============================================================
#  PUBLIC API
# =============================================================


def write_tune_file(feature_name: str, data: Dict[str, Any]) -> Path:
    """Write tuned parameters to the canonical file for a feature.

    Args:
        feature_name: One of "reprompt", "dictation", "agent".
        data: JSON-serializable dict of tuned parameters.

    Returns:
        Path to the written file.
    """
    TUNE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = CANONICAL_FILES[feature_name]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def read_tune_file(feature_name: str) -> Optional[Dict[str, Any]]:
    """Read tuned parameters from the canonical file for a feature.

    Args:
        feature_name: One of "reprompt", "dictation", "agent".

    Returns:
        The parsed JSON dict, or None if the file does not exist or is unreadable.
    """
    path = CANONICAL_FILES.get(feature_name)
    if not path or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_tune_file(feature_name: str) -> None:
    """Remove the canonical tune file for a feature, if it exists."""
    path = CANONICAL_FILES.get(feature_name)
    if path and path.exists():
        path.unlink()
