"""
core/agent_v2/prompt_optimizer.py — WizPrompt integration for IDE Controller Agent.

Optimizes every prompt before staging it in an IDE AI chat panel.
Adds architectural context, do's/don'ts, and style anchors.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from core.agent_v2.models import MasterPlan, Subphase


# Do's and Don'ts per architectural layer
_LAYER_RULES: Dict[str, Dict[str, List[str]]] = {
    "L1": {
        "do": [
            "Use Prisma or Drizzle schemas with proper relations",
            "Create migration files for every schema change",
            "Add seed data for development",
            "Use Zod or Valibot for runtime validation",
            "Index foreign keys and search columns",
        ],
        "dont": [
            "Skip migrations or use raw SQL for schema changes",
            "Store sensitive data unencrypted",
            "Forget to add createdAt/updatedAt timestamps",
            "Use auto-increment IDs for public-facing resources",
        ],
    },
    "L2": {
        "do": [
            "Use Supabase Auth or Clerk for authentication",
            "Implement Row Level Security (RLS) policies",
            "Use JWT with short expiry + refresh tokens",
            "Hash passwords with bcrypt/argon2 (never store plaintext)",
            "Implement MFA where possible",
        ],
        "dont": [
            "Roll your own authentication",
            "Store passwords or tokens in localStorage",
            "Skip RLS on Supabase tables",
            "Return sensitive user data in public API responses",
            "Use predictable session IDs",
        ],
    },
    "L3": {
        "do": [
            "Use tRPC, REST, or GraphQL with strict typing",
            "Validate all inputs with Zod before processing",
            "Return proper HTTP status codes",
            "Implement rate limiting on public endpoints",
            "Use structured error responses",
            "Add OpenAPI/Swagger docs where applicable",
        ],
        "dont": [
            "Skip input validation",
            "Return 200 OK for errors",
            "Expose stack traces in production",
            "Allow unrestricted query depth (GraphQL)",
            "Trust client-side validation alone",
        ],
    },
    "L4": {
        "do": [
            "Use Tailwind CSS with design tokens",
            "Use Shadcn/ui or Radix for accessible components",
            "Implement dark mode with CSS variables",
            "Use semantic HTML and ARIA labels",
            "Ensure keyboard navigation works",
            "Test responsive breakpoints (mobile-first)",
            "Use Next.js Image component for optimization",
        ],
        "dont": [
            "Use inline styles",
            "Skip accessibility (a11y) attributes",
            "Hardcode colors instead of CSS variables",
            "Forget loading/error states",
            "Use unoptimized images",
            "Break mobile layout",
        ],
    },
    "L5": {
        "do": [
            "Use environment variables for secrets",
            "Add health check endpoints",
            "Configure proper CORS policies",
            "Use Vercel/Netlify config files",
            "Set up CI/CD with GitHub Actions",
            "Add logging and error tracking (Sentry)",
        ],
        "dont": [
            "Hardcode API keys or secrets",
            "Skip CI checks before deploy",
            "Deploy without health checks",
            "Use wildcard CORS in production",
            "Forget to set NODE_ENV=production",
        ],
    },
}


async def optimize_subphase_prompt(
    subphase: Subphase,
    plan: MasterPlan,
    model: Optional[str] = None,
    use_memory: bool = True,
) -> str:
    """
    Optimize a subphase prompt using WizPrompt, then inject
    architectural context and do's/don'ts.
    """
    raw_prompt = subphase.description
    layer_id = subphase.id.split(".")[0] if "." in subphase.id else "L1"

    # 1. Optimize via WizPrompt
    optimized = raw_prompt
    try:
        from core.wizprompt import optimize_prompt_with_dynamic_agents
        result = await optimize_prompt_with_dynamic_agents(
            user_prompt=raw_prompt,
            model=model,
            preset="project_architect",
            mode="fast",
        )
        if isinstance(result, dict) and "optimized_prompt" in result:
            optimized = result["optimized_prompt"]
        elif isinstance(result, dict) and "prompt" in result:
            optimized = result["prompt"]
    except Exception as e:
        print(f"[PromptOptimizer] WizPrompt failed ({e}), using raw prompt")
        optimized = raw_prompt

    # 2. Build context block
    context_lines = [
        f"# Context",
        f"- Project: {plan.project_path}",
        f"- Stack: {', '.join(plan.stack)}",
        f"- Layer: {layer_id}",
        f"- Subphase: {subphase.id}",
        f"- Tool: {subphase.tool}",
        f"- Verification: {subphase.verification.get('type', 'tsc')}",
    ]

    # Add completed dependencies
    completed = _get_completed_subphases(plan)
    if completed:
        context_lines.append(f"- Completed dependencies: {', '.join(completed[-5:])}")  # Last 5

    context_lines.append("")

    # 3. Add layer-specific rules
    rules = _LAYER_RULES.get(layer_id, _LAYER_RULES["L1"])
    context_lines.append("# Do")
    for rule in rules["do"]:
        context_lines.append(f"- {rule}")
    context_lines.append("")
    context_lines.append("# Don't")
    for rule in rules["dont"]:
        context_lines.append(f"- {rule}")
    context_lines.append("")

    # 4. Add style anchors from memory (if enabled)
    if use_memory:
        try:
            from core.wizprompt_memory import get_style_anchor
            anchor = get_style_anchor()
            if anchor:
                context_lines.append(f"# Style Anchor")
                context_lines.append(anchor)
                context_lines.append("")
        except Exception:
            pass

    # 5. Combine
    context_lines.append("# Task")
    context_lines.append(optimized)
    context_lines.append("")
    context_lines.append("# Important")
    context_lines.append("- Write clean, production-ready code")
    context_lines.append("- Follow the stack conventions listed above")
    context_lines.append("- Do NOT include explanations or markdown outside code blocks")
    context_lines.append("- Ensure the code compiles/passes TypeScript checks")

    return "\n".join(context_lines)


def _get_completed_subphases(plan: MasterPlan) -> List[str]:
    """Return a list of completed subphase IDs."""
    completed: List[str] = []
    for layer in plan.layers:
        for phase in layer.phases:
            for sp in phase.subphases:
                if sp.status == "done":
                    completed.append(sp.id)
    return completed


def build_fix_prompt(
    issue_description: str,
    component_file: str,
    severity: str,
    tool: str = "cursor",
) -> str:
    """Build a WizPrompt-optimized fix prompt for a UI issue."""
    return (
        f"Fix the following UI issue in {component_file}:\n"
        f"- Problem: {issue_description}\n"
        f"- Severity: {severity}\n\n"
        f"Apply the fix using {tool} and ensure the component still compiles. "
        f"Do NOT include explanations outside code blocks. "
        f"Use Tailwind CSS and follow the existing component patterns."
    )
