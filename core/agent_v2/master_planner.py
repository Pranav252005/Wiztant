"""Master planner: detect stack, select template, generate master_plan.json."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.agent_v2.models import Layer, MasterPlan, Phase, Subphase, VerificationType


def detect_stack(project_path: Path) -> List[str]:
    """Detect tech stack from cwd heuristics."""
    stack: set[str] = set()
    pkg = project_path / "package.json"
    if pkg.exists():
        content = pkg.read_text(encoding="utf-8")
        if '"next"' in content:
            stack.add("nextjs")
        if '"react"' in content:
            stack.add("react")
        if '"tailwind"' in content or '"tailwindcss"' in content:
            stack.add("tailwind")
        if '"supabase"' in content:
            stack.add("supabase")
    if (project_path / "tsconfig.json").exists():
        stack.add("typescript")
    if list(project_path.glob("*.prisma")):
        stack.add("prisma")
    if (project_path / "vercel.json").exists():
        stack.add("vercel")
    return sorted(stack)


_WEB_APP_LAYERS = [
    Layer(
        id="L1",
        name="Data & Schema",
        phases=[
            Phase(
                id="P1.1",
                name="Database Schema Design",
                subphases=[
                    Subphase(id="1.1.1", description="Read existing schema / infer from files", tool="auto", verification={"type": VerificationType.MANUAL}),
                    Subphase(id="1.1.2", description="Draft Prisma / Supabase schema in Cursor", tool="cursor", action={"type": "prompt", "value": "Draft the database schema for this project based on the requirements."}, verification={"type": VerificationType.TSC}),
                ],
            ),
        ],
    ),
    Layer(
        id="L2",
        name="Auth & Security",
        phases=[
            Phase(
                id="P2.1",
                name="Authentication Setup",
                subphases=[
                    Subphase(id="2.1.1", description="Install auth library (next-auth / supabase-auth)", tool="warp", action={"type": "command", "value": "npm install next-auth"}, verification={"type": VerificationType.TSC}),
                    Subphase(id="2.1.2", description="Configure auth providers in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                ],
            ),
        ],
    ),
    Layer(
        id="L3",
        name="API & Business Logic",
        phases=[
            Phase(
                id="P3.1",
                name="Core API Routes",
                subphases=[
                    Subphase(id="3.1.1", description="Read current schema", tool="auto", verification={"type": VerificationType.MANUAL}),
                    Subphase(id="3.1.2", description="Draft GET route in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                    Subphase(id="3.1.3", description="Draft POST route in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                    Subphase(id="3.1.4", description="Verify with tsc + curl test", tool="warp", action={"type": "command", "value": "npx tsc --noEmit && curl http://localhost:3000/api/health"}, verification={"type": VerificationType.CURL}),
                ],
            ),
        ],
    ),
    Layer(
        id="L4",
        name="UI & Frontend",
        phases=[
            Phase(
                id="P4.1",
                name="Page Components",
                subphases=[
                    Subphase(id="4.1.1", description="Scaffold dashboard page in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                    Subphase(id="4.1.2", description="Scaffold detail page in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                ],
            ),
        ],
    ),
    Layer(
        id="L5",
        name="Integration & Deploy",
        phases=[
            Phase(
                id="P5.1",
                name="Deployment Config",
                subphases=[
                    Subphase(id="5.1.1", description="Draft Vercel config in Cursor", tool="cursor", verification={"type": VerificationType.TSC}),
                    Subphase(id="5.1.2", description="Stage deploy command in Warp", tool="warp", action={"type": "command", "value": "vercel --confirm"}, verification={"type": VerificationType.MANUAL}),
                ],
            ),
        ],
    ),
]


class MasterPlanner:
    """Generates master plans from user ideas."""

    def create_plan(
        self,
        project_id: str,
        project_path: str,
        description: str,
        stack: Optional[List[str]] = None,
    ) -> MasterPlan:
        stack = stack or detect_stack(Path(project_path))
        layers = [layer.model_copy(deep=True) for layer in _WEB_APP_LAYERS]
        now = datetime.now(timezone.utc).isoformat()
        return MasterPlan(
            project_id=project_id,
            project_path=project_path,
            description=description,
            stack=stack,
            layers=layers,
            status="draft",
            created_at=now,
            updated_at=now,
        )

    def self_optimize_plan(self, plan: MasterPlan) -> MasterPlan:
        """Stub: calls WizPrompt RePrompt with project_architect preset."""
        return plan
