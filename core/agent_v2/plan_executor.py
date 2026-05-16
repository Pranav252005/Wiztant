"""
core/agent_v2/plan_executor.py — Systematic plan execution engine.

Executes MasterPlan step-by-step: stages prompts in IDEs, waits for
approval, runs verification, handles failures, and triggers the
Build-Browse-Fix loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.agent_v2.models import MasterPlan, Layer, Phase, Subphase, VerificationType
from core.agent_v2.adapters.stager import Stager
from core.agent_v2.prompt_optimizer import optimize_subphase_prompt, build_fix_prompt
from core.agent_v2.browser_verify import verify_localhost
from core.agent_v2.ui_analyzer import analyze_ui, filter_critical_issues, score_passes
from core.agent_v2.guardrails import Guardrails
from platforms.factory import get_agent_runtime


class PlanExecutor:
    """Executes a MasterPlan with human-in-the-loop gates."""

    def __init__(
        self,
        plan: MasterPlan,
        stager: Optional[Stager] = None,
        guardrails: Optional[Guardrails] = None,
    ) -> None:
        self.plan = plan
        self.stager = stager or Stager(plan.tool_preferences)
        self.guardrails = guardrails or Guardrails(plan.project_path)
        self.runtime = get_agent_runtime()
        self._paused = False
        self._cancelled = False

    # -- State Control --

    def pause(self) -> None:
        self._paused = True
        self.plan.status = "paused"

    def resume(self) -> None:
        self._paused = False
        self.plan.status = "running"

    def cancel(self) -> None:
        self._cancelled = True
        self.plan.status = "cancelled"

    # -- Main Execution Loop --

    async def execute(self) -> Dict[str, Any]:
        """Execute the full plan layer by layer."""
        self.plan.status = "running"
        result = {"completed_layers": [], "failed_subphases": [], "total_subphases": 0}

        for layer in self.plan.layers:
            if self._cancelled:
                break

            layer_result = await self._execute_layer(layer)
            result["completed_layers"].append(layer_result)

            if layer_result.get("needs_approval"):
                return result

        # Final verification: browser + UI analysis
        if not self._cancelled:
            await self._run_browser_verification()

        self.plan.status = "completed" if not self._cancelled else "cancelled"
        return result

    async def _execute_layer(self, layer: Layer) -> Dict[str, Any]:
        """Execute a single layer. Returns status dict."""
        layer.status = "running"
        self.plan.current_layer_id = layer.id
        self._emit("agent.phase_start", {"layerId": layer.id, "layerName": layer.name})

        for phase in layer.phases:
            phase.status = "running"
            self.plan.current_phase_id = phase.id

            for subphase in phase.subphases:
                if self._cancelled:
                    break

                # Wait if paused
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)

                sp_result = await self._execute_subphase(subphase)
                if sp_result.get("needs_approval"):
                    return {"layerId": layer.id, "needs_approval": True}

            if self._cancelled:
                break
            phase.status = "done"

        if self._cancelled:
            layer.status = "paused"
        else:
            layer.status = "done"

        # Git checkpoint after layer
        self._git_checkpoint(f"wip(agent): {layer.id} — {layer.name}")

        # Ask for approval before next layer
        self._emit("agent.needs_approval", {
            "layerId": layer.id,
            "reason": f"Layer {layer.id} ({layer.name}) completed. Approve to continue?",
        })

        return {"layerId": layer.id, "status": layer.status}

    async def _execute_subphase(self, subphase: Subphase) -> Dict[str, Any]:
        """Execute a single subphase: stage → wait → verify → retry."""
        subphase.status = "staging"
        subphase.started_at = datetime.now(timezone.utc).isoformat()
        self.plan.current_subphase_id = subphase.id

        # 1. Optimize prompt
        try:
            optimized_prompt = await optimize_subphase_prompt(subphase, self.plan)
        except Exception as e:
            optimized_prompt = subphase.description
            print(f"[PlanExecutor] Prompt optimization failed: {e}")

        # 2. Route to adapter and stage
        tool = subphase.tool
        if tool == "auto":
            from core.agent_v2.adapters.auto_router import AutoRouter
            router = AutoRouter(self.plan.tool_preferences)
            tool = router.route(subphase.description)

        action = {"type": "prompt", "value": optimized_prompt}
        stage_result = await self.stager.stage_subphase(tool, action)

        if not stage_result.get("staged"):
            subphase.status = "failed"
            subphase.retry_count += 1
            return {"subphaseId": subphase.id, "error": stage_result.get("error")}

        self._emit("agent.subphase_staged", {
            "subphaseId": subphase.id,
            "tool": tool,
            "prompt": optimized_prompt,
        })

        # 3. WAIT for user to execute in IDE and signal continue
        # In the current architecture, the user reviews the staged prompt,
        # presses Enter in the IDE, then clicks "Continue" in the overlay.
        # The overlay sends a WebSocket / REST signal to resume.
        # For now, we assume the phase engine handles the wait externally.
        subphase.status = "verifying"

        # 4. Run verification
        verification_passed = await self._run_verification(subphase)

        if verification_passed:
            subphase.status = "done"
            subphase.completed_at = datetime.now(timezone.utc).isoformat()
            self._emit("agent.subphase_done", {
                "subphaseId": subphase.id,
                "verification": subphase.verification.get("type", "tsc"),
            })
            self.guardrails.reset_phase_counter()
            return {"subphaseId": subphase.id, "status": "done"}

        # 5. Retry with fix prompt
        if subphase.retry_count < self.guardrails.max_files_per_phase:
            subphase.retry_count += 1
            fix_prompt = build_fix_prompt(
                f"Verification failed for {subphase.id}",
                "",
                "warning",
                tool,
            )
            await self.stager.stage_subphase(tool, {"type": "prompt", "value": fix_prompt})
            self._emit("agent.subphase_failed", {
                "subphaseId": subphase.id,
                "error": f"Verification failed. Retry {subphase.retry_count}/{self.guardrails.max_files_per_phase}",
            })
            return {"subphaseId": subphase.id, "retry": True}

        subphase.status = "failed"
        self._emit("agent.subphase_failed", {
            "subphaseId": subphase.id,
            "error": "Max retries exceeded",
        })
        return {"subphaseId": subphase.id, "status": "failed"}

    async def _run_verification(self, subphase: Subphase) -> bool:
        """Run the verification command for a subphase."""
        vtype = subphase.verification.get("type", VerificationType.TSC)
        command = subphase.verification.get("command", "")

        if not command:
            if vtype == VerificationType.TSC:
                command = "npx tsc --noEmit"
            elif vtype == VerificationType.ESLINT:
                command = "npx eslint . --ext .ts,.tsx"
            elif vtype == VerificationType.CURL:
                command = "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/api/health"
            else:
                return True  # Manual / screenshot / migration skip

        # Validate command through guardrails
        ok, reason = self.guardrails.validate_command(command)
        if not ok:
            print(f"[PlanExecutor] Verification command blocked: {reason}")
            return False

        try:
            import subprocess
            result = subprocess.run(
                command,
                cwd=self.plan.project_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            passed = result.returncode == 0
            self._emit(
                "agent.verification_pass" if passed else "agent.verification_fail",
                {"subphaseId": subphase.id, "type": vtype, "output": result.stdout + result.stderr},
            )
            return passed
        except Exception as e:
            self._emit("agent.verification_fail", {
                "subphaseId": subphase.id,
                "type": vtype,
                "output": str(e),
            })
            return False

    async def _run_browser_verification(self) -> None:
        """After layers complete, open browser, screenshot, analyze UI."""
        self._emit("agent.phase_start", {"layerId": "VERIFY", "layerName": "Browser Verification"})

        img, status = verify_localhost(self.plan.project_path, self.runtime)
        if img is None:
            self._emit("agent.verification_fail", {
                "subphaseId": "browser",
                "type": "screenshot",
                "output": status,
            })
            return

        analysis, analysis_status = await analyze_ui(img)

        self._emit("agent.ui_analysis", {
            "score": analysis.get("overall_score", 0),
            "issues": analysis.get("issues", []),
        })

        # If score is below threshold, trigger fix loop
        if not score_passes(analysis, threshold=80):
            critical = filter_critical_issues(analysis)
            for issue in critical:
                fix = build_fix_prompt(
                    issue["description"],
                    issue.get("element_location", ""),
                    issue["severity"],
                )
                # Stage fix prompt in the default tool
                tool = self.plan.tool_preferences.get("default", "cursor")
                await self.stager.stage_subphase(tool, {"type": "prompt", "value": fix})

    def _git_checkpoint(self, message: str) -> None:
        """Create a git checkpoint if inside a repo."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.plan.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=self.plan.project_path,
                    capture_output=True,
                    timeout=10,
                )
                subprocess.run(
                    ["git", "commit", "-m", message, "--no-verify"],
                    cwd=self.plan.project_path,
                    capture_output=True,
                    timeout=10,
                )
        except Exception as e:
            print(f"[PlanExecutor] Git checkpoint skipped: {e}")

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit a WebSocket event to the overlay."""
        try:
            from core.ws_bridge import broadcast_sync
            broadcast_sync({"type": event_type, **payload})
        except Exception:
            pass
