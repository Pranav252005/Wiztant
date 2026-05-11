from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2.guardrails import (
    Guardrails,
    is_destructive_command,
    sandbox_path,
    COST_CEILING_USD,
)


def test_destructive_detection():
    assert is_destructive_command("rm -rf /") is True
    assert is_destructive_command("git push origin main") is True
    assert is_destructive_command("npm install lodash") is False
    assert is_destructive_command("npx tsc --noEmit") is False


def test_sandbox_path():
    base = Path("/home/user/projects/my-app")
    assert sandbox_path(base / "src/index.ts", base) is True
    assert sandbox_path(Path("/etc/passwd"), base) is False


def test_cost_ceiling():
    g = Guardrails(project_path="/tmp/test")
    assert g.can_spend(5.0) is True
    assert g.can_spend(COST_CEILING_USD + 1.0) is False
    g.record_spend(8.0)
    assert g.can_spend(3.0) is False  # 8 + 3 > 10
