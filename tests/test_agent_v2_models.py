from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2.models import MasterPlan, Layer, Phase, Subphase, VerificationType


def test_subphase_defaults():
    s = Subphase(id="1.1.1", description="Scaffold auth middleware", tool="cursor")
    assert s.status == "pending"
    assert s.verification == {"type": VerificationType.TSC, "command": "npx tsc --noEmit"}


def test_layer_serialization():
    layer = Layer(
        id="L2",
        name="Auth & Security",
        phases=[
            Phase(
                id="P2.1",
                name="Google OAuth",
                subphases=[
                    Subphase(id="2.1.1", description="Install next-auth", tool="warp", action={"type": "command", "value": "npm install next-auth"}),
                ],
            )
        ],
    )
    data = layer.model_dump()
    assert data["id"] == "L2"
    assert data["phases"][0]["subphases"][0]["status"] == "pending"


def test_master_plan_validation():
    plan = MasterPlan(
        project_id="proj_test_001",
        project_path="/tmp/test",
        description="Test plan",
        stack=["nextjs", "typescript"],
        layers=[
            Layer(id="L1", name="Data & Schema", phases=[]),
            Layer(id="L2", name="Auth & Security", phases=[]),
        ],
    )
    assert plan.current_subphase_id is None
    assert plan.status == "draft"
