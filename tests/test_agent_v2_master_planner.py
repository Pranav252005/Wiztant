from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2.master_planner import MasterPlanner, detect_stack


def test_detect_stack_nextjs():
    pkg = Path("package.json")
    pkg.write_text('{"dependencies":{"next":"^14"}}')
    try:
        stack = detect_stack(Path("."))
        assert "nextjs" in stack
    finally:
        pkg.unlink()


def test_master_planner_generates_layers():
    planner = MasterPlanner()
    plan = planner.create_plan(
        project_id="proj_test",
        project_path="/tmp/test",
        description="A simple todo app",
        stack=["nextjs", "typescript", "tailwind"],
    )
    assert len(plan.layers) == 5
    assert plan.layers[0].id == "L1"
    assert plan.layers[0].name == "Data & Schema"
    assert plan.status == "draft"
