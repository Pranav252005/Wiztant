from __future__ import annotations
import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2.memory import AgentMemoryV2


def test_ensure_index():
    with tempfile.TemporaryDirectory() as tmp:
        m = AgentMemoryV2(base_dir=tmp)
        m.ensure_index()
        index_path = Path(tmp) / "agent_index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text())
        assert data["version"] == "1"
        assert data["projects"] == {}


def test_register_project():
    with tempfile.TemporaryDirectory() as tmp:
        m = AgentMemoryV2(base_dir=tmp)
        m.register_project("proj_001", "~/Projects/test", ["nextjs", "typescript"])
        proj = m.get_project("proj_001")
        assert proj["path"] == "~/Projects/test"
        assert proj["stack"] == ["nextjs", "typescript"]


def test_run_directory():
    with tempfile.TemporaryDirectory() as tmp:
        m = AgentMemoryV2(base_dir=tmp)
        run_dir = m.ensure_run_dir("proj_001", "run_001")
        assert run_dir.exists()
        assert (run_dir / "master_plan.json").exists()
        assert (run_dir / "phase_manifest.json").exists()
