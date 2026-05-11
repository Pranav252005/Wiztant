from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2.models import MasterPlan
from core.agent_v2.phase_engine import PhaseEngine, EngineState


def test_engine_lifecycle():
    plan = MasterPlan(
        project_id="proj_t",
        project_path="/tmp/t",
        description="test",
        stack=["nextjs"],
        layers=[
            {
                "id": "L1",
                "name": "Data",
                "phases": [
                    {
                        "id": "P1.1",
                        "name": "Schema",
                        "subphases": [
                            {"id": "1.1.1", "description": "Read schema", "tool": "auto"},
                            {"id": "1.1.2", "description": "Write schema", "tool": "cursor"},
                        ],
                    }
                ],
            }
        ],
    )
    engine = PhaseEngine(plan)
    assert engine.state == EngineState.IDLE
    engine.start()
    assert engine.state == EngineState.STAGING
    assert engine.current_subphase.id == "1.1.1"
    engine.advance()
    assert engine.current_subphase.id == "1.1.2"
    engine.advance()
    assert engine.state == EngineState.DONE
