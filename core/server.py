"""
Wiztant FastAPI Bridge Server
Exposes the core module over HTTP so the React UI can communicate with it.
Run: python -m core.server   (from c:\whis directory)
"""
import os
import sys
import time
import json
import threading
from pathlib import Path

# Add parent dir to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Installing required packages: fastapi uvicorn pydantic")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]", "pydantic"])
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn

app = FastAPI(title="Wiztant Core API", version="1.0.0")

# ── Tune Hub integration ──
try:
    from core.tune_hub.api.public import router as tunehub_router
    from core.tune_hub.factory import create_tune_hub
    app.include_router(tunehub_router)
    app.state.tune_hub = create_tune_hub(tier="free")
except Exception as _e:
    print(f"[TuneHub] Could not initialize: {_e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5173",
        "app://.",
        "file://",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try importing core modules (graceful fallback if not available)
_core_available = False
try:
    import core.agent as agent_module
    import core as state
    _core_available = True
    print("[server] Core module loaded.")
except Exception as e:
    print(f"[server] Core module not available: {e}")
    state = None
    agent_module = None

_agent_stop = threading.Event()

# ── Models ──────────────────────────────────────────────────────────────────

class TuneRequest(BaseModel):
    content: str

class AgentRequest(BaseModel):
    task: str

class TierRequest(BaseModel):
    tier: str

class LicenseActivateRequest(BaseModel):
    key: str

class VoiceRequest(BaseModel):
    voice_id: str
    speed: float = 1.0

class WizPromptRequest(BaseModel):
    prompt: str
    model: str | None = None
    preset: str | None = "general_polish"
    ephemeral: bool | None = False

class WizPromptFeedbackRequest(BaseModel):
    original: str
    optimized: str
    final: str
    was_edited: bool = False
    feedback: str | None = None
    preset: str | None = None
    model: str | None = None
    emotion: str | None = None
    ephemeral: bool | None = False


class ProjectStartRequest(BaseModel):
    project_path: str
    description: str
    stack: list[str] = []
    approval_mode: str = "step-by-step"


class ProjectActionRequest(BaseModel):
    action: str  # "approve" | "pause" | "resume"

# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/ping")
def ping():
    return {"ok": True}

@app.get("/status")
def status():
    username = os.environ.get("USERNAME", "Commander")
    tier = os.environ.get("CURRENT_TIER", "pro")
    return {
        "neural": "stable",
        "latency": 18,
        "tier": tier,
        "username": username,
    }

@app.get("/auth/session")
def auth_session():
    session_path = ROOT / "data" / "session.json"
    try:
        data = json.loads(session_path.read_text())
        return {"username": data.get("username", "Commander"), "tier": data.get("tier", "pro")}
    except Exception:
        return {"username": os.environ.get("USERNAME", "Commander"), "tier": os.environ.get("CURRENT_TIER", "pro")}

@app.post("/auth/signout")
def auth_signout():
    if _core_available:
        try:
            import core.supabase_client as sc
            sc.sign_out()
        except Exception:
            pass
    return {"ok": True}

@app.post("/tune")
async def tune(req: TuneRequest):
    try:
        from core.credit_system import can_afford, deduct, get_current_user_id
        user_id = get_current_user_id()
        if not can_afford(user_id, 1):
            return {"ok": False, "type": "error", "reply": "Insufficient credits for chat. Upgrade at whiztant.app/pricing", "applied": [], "errors": ["credits"]}
        from core.tune import process_tune, tune_reply_to_dict
        result = process_tune(req.content)
        deduct(user_id, "chat", 1)
        return tune_reply_to_dict(result)
    except Exception as e:
        return {"ok": False, "type": "error", "reply": f"Tune error: {e}", "applied": [], "errors": [str(e)]}

@app.post("/agent/run")
async def agent_run(req: AgentRequest):
    if _core_available and agent_module:
        try:
            from core.credit_system import can_afford, get_current_user_id, calculate_agent_credits
            user_id = get_current_user_id()
            estimated_steps = max(3, 1 + len(req.task.split()) // 10)
            estimated_cost = calculate_agent_credits(estimated_steps)
            if not can_afford(user_id, estimated_cost):
                return {"ok": False, "detail": f"Insufficient credits for agent. Need ~{estimated_cost} credits."}
            steps: list[str] = []
            def step_cb(text: str, status: str = "done"):
                steps.append(text)
            if hasattr(state, "_agent_step_page_cb"):
                state._agent_step_page_cb = step_cb
            # ask_ai handles both chat and agent routing; force_agent=True
            # makes it skip the chat path and go straight to the agent executor.
            agent_module.ask_ai(req.task, force_agent=True)
            return {"ok": True, "steps": steps}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        time.sleep(1)
        return {"ok": True, "steps": ["Simulated: Task queued", f"Simulated: Executing '{req.task[:40]}'", "Simulated: Done"]}

@app.post("/agent/stop")
def agent_stop():
    if _core_available and state and hasattr(state, "_agent_stop_event"):
        state._agent_stop_event.set()
    return {"ok": True}

# ── TaskStack AI Toggle ─────────────────────────────────────────────────────

_TASK_AI_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")

@app.get("/settings/task_ai_enabled")
def get_task_ai_enabled():
    try:
        data = {}
        if os.path.exists(_TASK_AI_SETTINGS_PATH):
            with open(_TASK_AI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        return {"ok": True, "enabled": bool(data.get("task_ai_enabled", True))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/settings/task_ai_enabled")
def set_task_ai_enabled(body: dict):
    try:
        data = {}
        if os.path.exists(_TASK_AI_SETTINGS_PATH):
            with open(_TASK_AI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["task_ai_enabled"] = bool(body.get("enabled", True))
        os.makedirs(os.path.dirname(_TASK_AI_SETTINGS_PATH), exist_ok=True)
        with open(_TASK_AI_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return {"ok": True, "enabled": data["task_ai_enabled"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/undo")
def agent_undo():
    if _core_available:
        try:
            import core.system_access as sys_acc
            sys_acc.undo_last_action()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": True}

@app.get("/system/log")
def system_log():
    if _core_available:
        try:
            import core.system_access as sys_acc
            return sys_acc.load_undo_stack() or []
        except Exception:
            pass
    return []

@app.post("/system/tier")
def system_tier(req: TierRequest):
    os.environ["SYSTEM_ACCESS_TIER"] = req.tier
    return {"ok": True, "tier": req.tier}

@app.get("/license/tier")
def license_tier():
    try:
        from core.license import get_current_tier
        tier = get_current_tier()
    except Exception:
        tier = os.environ.get("CURRENT_TIER", "free")
    return {"tier": tier}

@app.post("/license/activate")
def license_activate(req: LicenseActivateRequest):
    try:
        from core.license import activate_license, get_current_tier
        ok = activate_license(req.key.strip())
        if ok:
            tier = get_current_tier()
            return {"ok": True, "tier": tier}
        from core.license import validate_license
        result = validate_license(req.key.strip())
        return {"ok": False, "message": result.get("message", "Activation failed.")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tts/voices")
def tts_voices():
    # TTS removed — return empty list for compatibility
    return []

@app.post("/tts/voice")
def tts_set_voice(req: VoiceRequest):
    # TTS removed — accept and no-op for compatibility
    return {"ok": True}

@app.post("/voice/dictate")
def voice_dictate():
    if _core_available:
        try:
            import core.hotkeys as hk
            hk._on_f9_taps(1)
        except Exception:
            pass
    return {"ok": True}

@app.post("/voice/stop")
def voice_stop():
    # TTS removed — no speaker to stop
    return {"ok": True}

@app.post("/wizprompt/optimize")
async def wizprompt_optimize(req: WizPromptRequest):
    try:
        from core.wizprompt import optimize_prompt_with_dynamic_agents
        result = await optimize_prompt_with_dynamic_agents(req.prompt, model=req.model, preset=req.preset)
        return {"ok": True, **result, "ephemeral": req.ephemeral or False}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/presets")
async def get_presets():
    from core.presets import get_all_presets, preset_to_dict
    return {"presets": [preset_to_dict(p) for p in get_all_presets()]}

@app.post("/wizprompt/feedback")
async def wizprompt_feedback(req: WizPromptFeedbackRequest):
    if req.ephemeral:
        return {"ok": True, "skipped": True, "reason": "ephemeral"}
    try:
        import core.wizprompt_memory as mem
        result = await mem.remember_optimization(
            original_prompt=req.original,
            optimized_prompt=req.optimized,
            final_prompt=req.final,
            was_edited=req.was_edited,
            feedback=req.feedback,
            preset=req.preset,
            model=req.model,
            emotion=req.emotion,
        )
        # Store in the visible memory stack so users can browse past reprompts
        try:
            from core.dictation_memory import add_memory
            add_memory(
                original_text=req.original,
                final_text=req.final or req.optimized,
                mode="reprompt",
            )
        except Exception:
            pass
        return {"ok": True, "example_id": result["example_id"], "cluster_id": result["cluster_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/wizprompt/examples")
async def wizprompt_examples(prompt: str, preset: str | None = None, limit: int = 3):
    try:
        import core.wizprompt_memory as mem
        examples, cluster_id, bias = await mem.retrieve_examples_for_prompt(prompt, preset, limit)
        return {
            "ok": True,
            "examples": examples,
            "cluster_id": cluster_id,
            "style_bias": bias,
            "example_count": mem.get_example_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Credit System Endpoints ─────────────────────────────────────────────────

@app.get("/credits/balance")
def credits_balance():
    try:
        from core.credit_system import (
            get_balance, get_tier, get_tier_credits, get_current_user_id, get_reset_at
        )
        user_id = get_current_user_id()
        balance = get_balance(user_id)
        tier = get_tier(user_id)
        allocation = get_tier_credits(tier)
        reset_at = get_reset_at(user_id)
        return {
            "ok": True,
            "user_id": user_id,
            "balance": balance,
            "tier": tier,
            "monthly_allocation": allocation,
            "reset_at": reset_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/credits/history")
def credits_history(limit: int = 50):
    try:
        from core.credit_system import _get_manager, get_current_user_id
        user_id = get_current_user_id()
        manager = _get_manager()
        user_data = manager._get_user_data(user_id)
        transactions = user_data.get("transactions", [])
        return {
            "ok": True,
            "user_id": user_id,
            "transactions": transactions[-limit:],
            "count": len(transactions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/credits/calculate")
async def credits_calculate(body: dict):
    try:
        from core.credit_system import (
            calculate_reprompt_credits,
            calculate_tunehub_credits,
            preview_dictation_cost,
            get_all_model_options,
        )
        feature = body.get("feature", "")
        if feature == "dictation":
            return {"ok": True, **preview_dictation_cost()}
        elif feature == "reprompt":
            model = body.get("model")
            return {"ok": True, **{
                "feature": "reprompt",
                "model": model,
                "credits": calculate_reprompt_credits(model),
            }}
        elif feature == "tunehub":
            complexity = body.get("complexity", "LOW")
            feature_model = body.get("feature_model")
            judge_model = body.get("judge_model")
            return {"ok": True, **{
                "feature": "tunehub",
                "complexity": complexity,
                "credits": calculate_tunehub_credits(complexity, feature_model, judge_model),
            }}
        elif feature == "models":
            return {"ok": True, **get_all_model_options()}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown feature: {feature}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


try:
    from core.agent_v2.master_planner import MasterPlanner, detect_stack
    from core.agent_v2.phase_engine import PhaseEngine
    from core.agent_v2.memory import AgentMemoryV2
    from core.agent_v2.models import MasterPlan
    from core.agent_v2.plan_executor import PlanExecutor
    _agent_v2_available = True
except Exception as _e:
    print(f"[server] Agent v2 not available: {_e}")
    _agent_v2_available = False

_agent_v2_engines: dict[str, PhaseEngine] = {}
_agent_v2_executors: dict[str, PlanExecutor] = {}
_agent_v2_memory = AgentMemoryV2() if _agent_v2_available else None


@app.post("/agent/project/start")
async def agent_project_start(req: ProjectStartRequest):
    if not _agent_v2_available:
        raise HTTPException(status_code=503, detail="Agent v2 not available")

    # ── Intent Gate: validate the build request ──
    try:
        from core.agent_v2.intent_gate import gate_check
        permitted, reason, confidence = gate_check(req.description, use_llm_fallback=True)
        if not permitted:
            print(f"[IntentGate] BLOCKED build request (confidence={confidence}): {reason[:80]}")
            raise HTTPException(status_code=400, detail=reason)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[IntentGate] Error in project start (fail-open): {e}")

    import uuid
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    planner = MasterPlanner()
    from pathlib import Path
    stack = req.stack or detect_stack(Path(req.project_path))
    plan = planner.create_plan(
        project_id=project_id,
        project_path=req.project_path,
        description=req.description,
        stack=stack,
    )
    plan.approval_mode = req.approval_mode
    _agent_v2_memory.register_project(project_id, req.project_path, stack)
    run_dir = _agent_v2_memory.ensure_run_dir(project_id, f"run_{project_id}")
    _agent_v2_memory.write_run_artifact(f"run_{project_id}", "master_plan.json", plan.model_dump())
    engine = PhaseEngine(plan)
    executor = PlanExecutor(plan)

    # Wire executor events to WebSocket bridge
    def _bridge_emit(event_type: str, payload: dict) -> None:
        try:
            from core.ws_bridge import broadcast_sync
            broadcast_sync({"type": event_type, "project_id": project_id, **payload})
        except Exception:
            pass

    executor._emit = _bridge_emit
    _agent_v2_engines[project_id] = engine
    _agent_v2_executors[project_id] = executor
    return {"project_id": project_id, "plan": plan.model_dump(), "run_dir": str(run_dir)}


@app.get("/agent/project/{project_id}/status")
async def agent_project_status(project_id: str):
    engine = _agent_v2_engines.get(project_id)
    executor = _agent_v2_executors.get(project_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        "state": engine.state.name,
        "current_layer": engine.plan.current_layer_id,
        "current_phase": engine.plan.current_phase_id,
        "current_subphase": engine.plan.current_subphase_id,
        "plan": engine.plan.model_dump(),
        "ui_score": getattr(executor, '_last_ui_score', None) if executor else None,
        "needs_approval": engine.state.name in ("PAUSED", "CHECKPOINT"),
        "approval_reason": getattr(executor, '_last_approval_reason', None) if executor else None,
    }


@app.post("/agent/project/{project_id}/approve")
async def agent_project_approve(project_id: str, req: ProjectActionRequest):
    engine = _agent_v2_engines.get(project_id)
    executor = _agent_v2_executors.get(project_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Project not found")
    if req.action == "approve":
        if engine.state.name == "IDLE":
            engine.start()
            # Kick off async execution
            if executor:
                import asyncio
                asyncio.create_task(executor.execute())
        else:
            engine.advance()
            if executor:
                executor.resume()
        return {"status": "ok", "state": engine.state.name}
    if req.action == "pause":
        engine.pause()
        if executor:
            executor.pause()
        return {"status": "paused", "state": engine.state.name}
    if req.action == "resume":
        engine.resume()
        if executor:
            executor.resume()
        return {"status": "resumed", "state": engine.state.name}
    raise HTTPException(status_code=400, detail="Invalid action")


if __name__ == "__main__":
    print("[Wiztant] Starting core API server on http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
