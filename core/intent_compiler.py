"""
Whiztant core/intent_compiler.py — Intent Compiler

Decomposes high-level user goals into executable dependency graphs.
Each node is a concrete step with dependencies, verification, and
checkpoint support. Steps without dependencies can run in parallel.

Pipeline:
  1. Decompose: LLM generates a JSON dependency graph from user goal
  2. Execute:   Topological sort → run ready steps → verify → next
  3. Re-plan:   On failure, send context back to LLM for alternative
"""

import os
import json
import time
import asyncio
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from openai import OpenAI

import core as state


# ── Config ────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "data" / "skills"

def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Step Status ───────────────────────────────────────────────────────────────

class StepStatus(str, Enum):
    PENDING  = "pending"
    READY    = "ready"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


# ── Step dataclass ────────────────────────────────────────────────────────────

@dataclass
class Step:
    id: str
    action: str
    tool: str = "agent"          # agent | cli | browser | text_edit | skill
    target_app: str = ""
    estimated_minutes: float = 1.0
    depends_on: List[str] = field(default_factory=list)
    checkpoint: bool = False
    verification: str = ""
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    retries: int = 0
    skill_name: str = ""         # if tool == "skill", the skill file name


# ── Planner Prompt ────────────────────────────────────────────────────────────

COMPILER_SYSTEM_PROMPT = (
    "You are an intent compiler for a Windows AI assistant called Whiztant. "
    "The user gives you a high-level goal. You decompose it into a dependency graph "
    "of concrete, executable steps.\n\n"
    "Available tool types:\n"
    "- agent: GUI automation via screenshot + click/type (default)\n"
    "- cli: Terminal/PowerShell command execution\n"
    "- browser: Open URL or navigate in browser\n"
    "- text_edit: Edit a file in an editor\n"
    "- skill: Execute a previously recorded workflow skill\n"
    "{skills_section}\n"
    "Rules:\n"
    "- Each step must have a unique id (s1, s2, ...).\n"
    "- depends_on lists step ids that must complete before this step can start.\n"
    "- Steps without dependencies can run in parallel.\n"
    "- Set checkpoint: true for steps that should pause and ask the user before continuing.\n"
    "- verification describes how to confirm the step succeeded.\n"
    "- estimated_minutes is a rough estimate for user display.\n"
    "- Break complex tasks into small, atomic, independently verifiable steps.\n"
    "- Be specific — name exact apps, menus, buttons, URLs, commands.\n"
    "- Prefer keyboard-first app navigation when a reliable shortcut exists.\n"
    "- Always set target_app to the exact app, website, or Windows surface being used.\n"
    "- For browser tasks, prefer address bar navigation, tab shortcuts, and site-specific labels.\n"
    "- For desktop app tasks, prefer launch, focus, search, ribbon, sidebar, and dialog steps that are visually verifiable.\n"
    "- Never combine multiple UI goals into one step; one visible outcome per step.\n"
    "- If a task involves sign-in, permissions, destructive actions, payments, or sending data externally, insert a checkpoint before that step.\n"
    "- Avoid vague actions like 'handle the app' or 'do the setup'. Use exact visible operations.\n"
    "- Return ONLY valid JSON. No markdown, no explanation.\n\n"
    "Output format:\n"
    "{{\n"
    '  "goal": "One sentence summary of the goal",\n'
    '  "steps": [\n'
    "    {{\n"
    '      "id": "s1",\n'
    '      "action": "Specific action description",\n'
    '      "tool": "agent",\n'
    '      "target_app": "App Name",\n'
    '      "estimated_minutes": 2,\n'
    '      "depends_on": [],\n'
    '      "checkpoint": false,\n'
    '      "verification": "How to verify success"\n'
    "    }}\n"
    "  ]\n"
    "}}"
)


# ── Skills discovery ──────────────────────────────────────────────────────────

def list_skills() -> List[Dict]:
    """Return list of available recorded skills from data/skills/."""
    skills = []
    if not _SKILLS_DIR.exists():
        return skills
    for path in _SKILLS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            skills.append({
                "name": path.stem,
                "description": data.get("description", ""),
                "steps": len(data.get("steps", [])),
            })
        except Exception:
            continue
    return skills


def _build_skills_section() -> str:
    """Build the skills section for the planner prompt."""
    skills = list_skills()
    if not skills:
        return ""
    lines = ["Available recorded skills (use tool='skill' and set skill_name):"]
    for s in skills:
        lines.append(f"  - {s['name']}: {s['description']} ({s['steps']} steps)")
    return "\n".join(lines) + "\n"


# ── PlannerEngine ─────────────────────────────────────────────────────────────

class PlannerEngine:
    """Calls LLM to decompose a goal into a dependency graph of steps."""

    def __init__(self):
        self._client = OpenAI(
            api_key=_cfg("OPENROUTER_API_KEY"),
            base_url=_cfg("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )

    def compile(self, goal: str, screenshot_b64: str = None) -> Dict:
        """
        Decompose a high-level goal into a step graph.
        Returns {"goal": str, "steps": [step_dict, ...]}
        """
        model = _cfg("PLANNER_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")
        skills_section = _build_skills_section()
        system = COMPILER_SYSTEM_PROMPT.format(skills_section=skills_section)

        user_content: list = []
        if screenshot_b64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            })
        user_content.append({
            "type": "text",
            "text": f"Goal: {goal}",
        })

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        raw = ""
        for attempt in range(2):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    max_tokens=1024,
                )
                raw = resp.choices[0].message.content.strip()

                # Strip <think> tags
                if "<think>" in raw:
                    raw = raw[raw.rfind("</think>") + len("</think>"):].strip()
                raw = raw.replace("```json", "").replace("```", "").strip()

                plan = json.loads(raw)

                # Validate
                if "steps" not in plan or not isinstance(plan["steps"], list):
                    raise ValueError("Plan missing 'steps' array")
                if not plan["steps"]:
                    raise ValueError("Plan has zero steps")

                return plan

            except json.JSONDecodeError:
                if attempt == 0:
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": "Invalid JSON. Return ONLY the JSON object.",
                    })
                    continue
                raise RuntimeError(f"Compiler returned invalid JSON: {raw[:200]}")
            except Exception as e:
                raise RuntimeError(f"Compiler error: {e}")

        raise RuntimeError("Compiler returned no result")

    def replan_step(self, failed_step: Dict, failure_reason: str,
                    screenshot_b64: str = None) -> Dict:
        """
        Given a failed step and reason, generate an alternative approach.
        Returns a single replacement step dict.
        """
        model = _cfg("PLANNER_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")

        user_content: list = []
        if screenshot_b64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            })
        user_content.append({
            "type": "text",
            "text": (
                f"This step failed:\n{json.dumps(failed_step, indent=2)}\n\n"
                f"Failure reason: {failure_reason}\n\n"
                "Generate ONE alternative step that achieves the same goal "
                "using a different approach. Return ONLY the JSON step object."
            ),
        })

        messages = [
            {"role": "system", "content": "You are a re-planning agent. Generate an alternative step."},
            {"role": "user", "content": user_content},
        ]

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=400,
            )
            raw = resp.choices[0].message.content.strip()
            if "<think>" in raw:
                raw = raw[raw.rfind("</think>") + len("</think>"):].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            print(f"[IntentCompiler] Re-plan failed: {e}")
            return None


# ── ExecutionGraph ────────────────────────────────────────────────────────────

class ExecutionGraph:
    """
    Manages a dependency graph of Steps.
    Provides topological ordering and ready-step detection.
    """

    def __init__(self, plan: Dict):
        self.goal = plan.get("goal", "")
        self.steps: Dict[str, Step] = {}
        for s in plan.get("steps", []):
            step = Step(
                id=s["id"],
                action=s.get("action", ""),
                tool=s.get("tool", "agent"),
                target_app=s.get("target_app", ""),
                estimated_minutes=float(s.get("estimated_minutes", 1)),
                depends_on=s.get("depends_on", []),
                checkpoint=s.get("checkpoint", False),
                verification=s.get("verification", ""),
                skill_name=s.get("skill_name", ""),
            )
            self.steps[step.id] = step

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def completed(self) -> int:
        return sum(1 for s in self.steps.values() if s.status == StepStatus.DONE)

    @property
    def failed_steps(self) -> List[Step]:
        return [s for s in self.steps.values() if s.status == StepStatus.FAILED]

    @property
    def all_done(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.SKIPPED, StepStatus.FAILED)
            for s in self.steps.values()
        )

    def get_ready_steps(self) -> List[Step]:
        """Return steps whose dependencies are all satisfied and status is PENDING."""
        ready = []
        for step in self.steps.values():
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                dep_step is not None and dep_step.status in (StepStatus.DONE, StepStatus.SKIPPED)
                for dep_id in step.depends_on
                for dep_step in [self.steps.get(dep_id)]
            )
            if deps_met:
                step.status = StepStatus.READY
                ready.append(step)
        return ready

    def mark_done(self, step_id: str, result: str = ""):
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.DONE
            self.steps[step_id].result = result

    def mark_failed(self, step_id: str, reason: str = ""):
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.FAILED
            self.steps[step_id].result = reason
            self.steps[step_id].retries += 1

    def mark_skipped(self, step_id: str):
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.SKIPPED

    def mark_running(self, step_id: str):
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.RUNNING

    def replace_step(self, old_id: str, new_step_dict: Dict):
        """Replace a failed step with a re-planned alternative."""
        if old_id not in self.steps:
            return
        old = self.steps[old_id]
        new = Step(
            id=old_id,
            action=new_step_dict.get("action", old.action),
            tool=new_step_dict.get("tool", old.tool),
            target_app=new_step_dict.get("target_app", old.target_app),
            estimated_minutes=float(new_step_dict.get("estimated_minutes", old.estimated_minutes)),
            depends_on=old.depends_on,
            checkpoint=new_step_dict.get("checkpoint", old.checkpoint),
            verification=new_step_dict.get("verification", old.verification),
            skill_name=new_step_dict.get("skill_name", old.skill_name),
            status=StepStatus.PENDING,
            retries=old.retries,
        )
        self.steps[old_id] = new

    def to_summary(self) -> List[Dict]:
        """Return a serializable summary for UI display."""
        return [
            {
                "id": s.id,
                "action": s.action,
                "tool": s.tool,
                "target_app": s.target_app,
                "estimated_minutes": s.estimated_minutes,
                "depends_on": s.depends_on,
                "checkpoint": s.checkpoint,
                "status": s.status.value,
                "result": s.result,
            }
            for s in self.steps.values()
        ]


# ── CheckpointManager ────────────────────────────────────────────────────────

class CheckpointManager:
    """
    Handles checkpoint pauses — when a step has checkpoint=True,
    execution pauses and the user is asked to approve/skip/edit.
    """

    def __init__(self, speak_fn, transcribe_fn):
        self._speak = speak_fn
        self._transcribe = transcribe_fn

    async def check(self, step: Step) -> str:
        """
        Ask user whether to proceed with a checkpoint step.
        Returns: "proceed" | "skip" | "edit:<new_action>"
        """
        if not step.checkpoint:
            return "proceed"

        msg = f"Checkpoint: next step is '{step.action}'. Say proceed, skip, or describe a change."
        result = self._speak(msg)
        if asyncio.iscoroutine(result):
            await result

        answer = self._transcribe()
        if asyncio.iscoroutine(answer):
            answer = await answer
        answer = (answer or "proceed").strip().lower()

        if "skip" in answer:
            return "skip"
        if "proceed" in answer or "yes" in answer or "go" in answer:
            return "proceed"
        # Anything else is treated as an edit
        return f"edit:{answer}"


# ── Main Executor ─────────────────────────────────────────────────────────────

async def run_compiled_task(
    goal: str,
    speak_fn,
    transcribe_fn,
    set_wave_state_fn,
    append_chat_fn,
    stop_event: Optional[threading.Event] = None,
) -> str:
    """
    Full intent compiler pipeline:
      1. Decompose goal into dependency graph
      2. Execute steps in topological order
      3. Re-plan on failure
      4. Return summary
    """
    from platforms.windows._vlm_impl import _take_screenshot, _execute_single_step

    async def _speak(text: str):
        set_wave_state_fn("speaking")
        result = speak_fn(text)
        if asyncio.iscoroutine(result):
            await result
        set_wave_state_fn("agent")

    def _speak_sync(text: str):
        result = speak_fn(text)
        if asyncio.iscoroutine(result):
            asyncio.run(result)

    def _transcribe_sync() -> str:
        result = transcribe_fn()
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result or ""

    # ── Stage 1: Decompose ────────────────────────────────────────────────
    set_wave_state_fn("thinking")
    append_chat_fn("system", f"[Compiler] Goal: {goal}")

    try:
        screenshot_b64, _, physical_size = _take_screenshot()
        planner = PlannerEngine()
        plan = planner.compile(goal, screenshot_b64)
    except Exception as e:
        error = f"Failed to compile plan: {e}"
        append_chat_fn("assistant", f"[Compiler] {error}")
        await _speak(f"I couldn't create a plan: {e}")
        set_wave_state_fn("idle")
        return error

    graph = ExecutionGraph(plan)
    checkpoint_mgr = CheckpointManager(speak_fn, transcribe_fn)

    # Announce plan
    append_chat_fn("assistant", f"[Compiler] Plan: {graph.goal} — {graph.total} steps")
    for s in graph.steps.values():
        dep_str = f" (after {', '.join(s.depends_on)})" if s.depends_on else ""
        append_chat_fn("assistant", f"  {s.id}: {s.action} [{s.tool}]{dep_str}")

    await _speak(f"I have a {graph.total}-step plan for: {graph.goal}. Starting now.")

    # ── Stage 2: Execute ──────────────────────────────────────────────────
    max_actions = int(_cfg("AGENT_MAX_ACTIONS_PER_STEP", "5"))

    while not graph.all_done:
        if stop_event and stop_event.is_set():
            await _speak("Task stopped.")
            set_wave_state_fn("idle")
            return f"Stopped at {graph.completed}/{graph.total} steps."

        ready = graph.get_ready_steps()
        if not ready:
            # Deadlock — all remaining steps have unmet dependencies
            remaining = [
                s.id for s in graph.steps.values()
                if s.status in (StepStatus.PENDING, StepStatus.READY)
            ]
            if remaining:
                for sid in remaining:
                    graph.mark_skipped(sid)
                append_chat_fn("assistant", f"[Compiler] Skipped blocked steps: {', '.join(remaining)}")
            break

        # Execute ready steps one at a time (sequential for safety)
        for step in ready:
            if stop_event and stop_event.is_set():
                break

            # Checkpoint check
            decision = await checkpoint_mgr.check(step)
            if decision == "skip":
                graph.mark_skipped(step.id)
                append_chat_fn("assistant", f"[Compiler] Skipped {step.id}: {step.action}")
                continue
            elif decision.startswith("edit:"):
                step.action = decision[5:].strip()
                append_chat_fn("assistant", f"[Compiler] Edited {step.id}: {step.action}")

            graph.mark_running(step.id)
            append_chat_fn("assistant",
                f"[Compiler] Running {step.id}/{graph.total}: {step.action} [{step.tool}]")
            set_wave_state_fn("agent")

            # Route to appropriate executor
            try:
                if step.tool == "cli":
                    result = _execute_cli(step.action)
                elif step.tool == "skill":
                    result = await _execute_skill(step.skill_name, speak_fn, transcribe_fn,
                                                   set_wave_state_fn, append_chat_fn, stop_event)
                else:
                    # Default: GUI agent execution
                    screenshot_b64, _, physical_size = _take_screenshot()
                    step_result = await _execute_single_step(
                        step.action, screenshot_b64, physical_size,
                        _speak_sync, _transcribe_sync, max_actions=max_actions
                    )
                    result = "OK" if step_result.get("success") else step_result.get("error", "Failed")

            except Exception as e:
                result = f"Error: {e}"

            # Check result
            if result.startswith("OK") or result.startswith("DONE"):
                graph.mark_done(step.id, result)
                append_chat_fn("assistant", f"[Compiler] ✓ {step.id} complete")
            else:
                # Retry once with re-planning
                if step.retries < 1:
                    graph.mark_failed(step.id, result)
                    append_chat_fn("assistant",
                        f"[Compiler] {step.id} failed: {result}. Re-planning...")

                    try:
                        screenshot_b64, _, _ = _take_screenshot()
                        alt = planner.replan_step(
                            asdict(step), result, screenshot_b64
                        )
                        if alt:
                            graph.replace_step(step.id, alt)
                            append_chat_fn("assistant",
                                f"[Compiler] Re-planned {step.id}: {alt.get('action', '?')}")
                        else:
                            graph.mark_skipped(step.id)
                    except Exception:
                        graph.mark_skipped(step.id)
                else:
                    graph.mark_failed(step.id, result)
                    append_chat_fn("assistant", f"[Compiler] ✗ {step.id} failed: {result}")

            time.sleep(0.3)

    # ── Stage 3: Summary ──────────────────────────────────────────────────
    done = graph.completed
    total = graph.total
    failed = graph.failed_steps

    if failed:
        failed_ids = [s.id for s in failed]
        summary = f"Completed {done}/{total} steps. Failed: {', '.join(failed_ids)}."
    else:
        summary = f"Done. {graph.goal}"

    append_chat_fn("assistant", f"[Compiler] {summary}")
    set_wave_state_fn("speaking")
    await _speak(summary)
    set_wave_state_fn("idle")

    return summary


# ── CLI executor ──────────────────────────────────────────────────────────────

def _execute_cli(command: str) -> str:
    """Execute a CLI command and return output."""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return f"OK: {result.stdout[:200]}"
        return f"FAILED (exit {result.returncode}): {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return "FAILED: Command timed out (30s)"
    except Exception as e:
        return f"FAILED: {e}"


# ── Skill executor ────────────────────────────────────────────────────────────

async def _execute_skill(
    skill_name: str,
    speak_fn,
    transcribe_fn,
    set_wave_state_fn,
    append_chat_fn,
    stop_event,
) -> str:
    """Execute a recorded skill from data/skills/."""
    skill_path = _SKILLS_DIR / f"{skill_name}.json"
    if not skill_path.exists():
        return f"FAILED: Skill '{skill_name}' not found"

    try:
        skill_data = json.loads(skill_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"FAILED: Could not load skill: {e}"

    # Import replay function from workflow recorder
    try:
        from core.workflow_recorder import replay_skill
        result = await replay_skill(
            skill_data, speak_fn, transcribe_fn,
            set_wave_state_fn, append_chat_fn, stop_event
        )
        return result
    except ImportError:
        return "FAILED: Workflow recorder not available"
    except Exception as e:
        return f"FAILED: Skill execution error: {e}"
