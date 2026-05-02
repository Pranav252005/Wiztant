"""Model persistence helpers for Tune Hub.

Handles saving/loading learned models, observation histories, and
intermediate checkpoints to disk.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict, Optional


class TuneModelPersistence:
    """Persistence manager for tuner models and observations."""

    def __init__(self, base_dir: str = "data/tune_models") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str, feature_name: str, task_signature: str, suffix: str) -> Path:
        """Build a safe file path from identifiers."""
        safe_sig = task_signature.replace("/", "_").replace("\\", "_")[:64]
        safe_user = user_id.replace("/", "_").replace("\\", "_")[:32]
        filename = f"{safe_user}_{feature_name}_{safe_sig}{suffix}"
        return self.base_dir / filename

    def save_observations(
        self,
        user_id: str,
        feature_name: str,
        task_signature: str,
        observations: list[dict],
    ) -> Path:
        """Save observation history as JSON lines."""
        path = self._path(user_id, feature_name, task_signature, "_observations.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for obs in observations:
                f.write(json.dumps(obs, default=str) + "\n")
        return path

    def load_observations(
        self, user_id: str, feature_name: str, task_signature: str
    ) -> list[dict]:
        """Load observation history."""
        path = self._path(user_id, feature_name, task_signature, "_observations.jsonl")
        if not path.exists():
            return []
        observations = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    observations.append(json.loads(line))
        return observations

    def save_checkpoint(
        self,
        user_id: str,
        feature_name: str,
        task_signature: str,
        checkpoint_data: Dict[str, Any],
    ) -> Path:
        """Save a binary checkpoint (e.g., GP state, policy weights)."""
        path = self._path(user_id, feature_name, task_signature, "_checkpoint.pkl")
        with open(path, "wb") as f:
            pickle.dump(checkpoint_data, f)
        return path

    def load_checkpoint(
        self, user_id: str, feature_name: str, task_signature: str
    ) -> Optional[Dict[str, Any]]:
        """Load a binary checkpoint."""
        path = self._path(user_id, feature_name, task_signature, "_checkpoint.pkl")
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def save_json(
        self,
        user_id: str,
        feature_name: str,
        task_signature: str,
        data: Dict[str, Any],
        suffix: str = "_data.json",
    ) -> Path:
        """Save arbitrary JSON data."""
        path = self._path(user_id, feature_name, task_signature, suffix)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    def load_json(
        self, user_id: str, feature_name: str, task_signature: str, suffix: str = "_data.json"
    ) -> Optional[Dict[str, Any]]:
        """Load arbitrary JSON data."""
        path = self._path(user_id, feature_name, task_signature, suffix)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_all(self, user_id: str, feature_name: str, task_signature: str) -> None:
        """Remove all persisted files for a tune."""
        safe_sig = task_signature.replace("/", "_").replace("\\", "_")[:64]
        safe_user = user_id.replace("/", "_").replace("\\", "_")[:32]
        prefix = f"{safe_user}_{feature_name}_{safe_sig}"
        for path in self.base_dir.glob(f"{prefix}*"):
            path.unlink()
