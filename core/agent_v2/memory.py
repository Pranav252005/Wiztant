"""Agent v2 memory: Hermes ledger (agent_index.json) + per-run directories."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class AgentMemoryV2:
    """Manages agent_index.json and memory/agent_runs/{run_id}/ directories."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "agent_index.json"

    def _load_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"version": "1", "projects": {}}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"version": "1", "projects": {}}

    def _save_index(self, data: Dict[str, Any]) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.index_path)

    def ensure_index(self) -> None:
        """Create index if missing."""
        if not self.index_path.exists():
            self._save_index({"version": "1", "projects": {}})

    def register_project(self, project_id: str, path: str, stack: list[str]) -> None:
        """Register or update a project in the Hermes ledger."""
        data = self._load_index()
        data["projects"][project_id] = {
            "path": path,
            "stack": stack,
            "patterns": [],
            "tool_preferences": {},
            "last_run_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_index(data)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_index()
        return data["projects"].get(project_id)

    def update_project_patterns(self, project_id: str, pattern_type: str, value: str, confidence: float) -> None:
        data = self._load_index()
        proj = data["projects"].get(project_id)
        if not proj:
            return
        existing = [p for p in proj.get("patterns", []) if not (p["type"] == pattern_type and p["value"] == value)]
        existing.append({"type": pattern_type, "value": value, "confidence": confidence})
        proj["patterns"] = existing
        self._save_index(data)

    def ensure_run_dir(self, project_id: str, run_id: str) -> Path:
        """Create and return the run directory with skeleton files."""
        run_dir = self.base_dir / "agent_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["master_plan.json", "phase_manifest.json", "execution.json", "artifacts.json"]:
            fpath = run_dir / fname
            if not fpath.exists():
                fpath.write_text("{}")
        return run_dir

    def write_run_artifact(self, run_id: str, filename: str, payload: Dict[str, Any]) -> None:
        run_dir = self.base_dir / "agent_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        fpath = run_dir / filename
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_run_artifact(self, run_id: str, filename: str) -> Optional[Dict[str, Any]]:
        fpath = self.base_dir / "agent_runs" / run_id / filename
        if not fpath.exists():
            return None
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
