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

# In-memory fallback conversation history
_conversation: list[dict] = []
_agent_stop = threading.Event()

# ── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    content: str

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
    preset: str | None = "general"

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

@app.post("/chat")
async def chat(req: ChatRequest):
    global _conversation
    _conversation.append({"role": "user", "content": req.content})

    if _core_available and agent_module:
        try:
            response = agent_module.ask_ai(req.content)
            _conversation.append({"role": "assistant", "content": response})
            return {"role": "assistant", "content": response}
        except Exception as e:
            err = f"Core error: {e}"
            _conversation.append({"role": "assistant", "content": err})
            return {"role": "assistant", "content": err}
    else:
        # Fallback echo
        msg = f"[Backend offline] I received: '{req.content}'. Start the core server for real AI responses."
        _conversation.append({"role": "assistant", "content": msg})
        return {"role": "assistant", "content": msg}

@app.post("/tune")
async def tune(req: TuneRequest):
    try:
        from core.tune import process_tune, tune_reply_to_dict
        result = process_tune(req.content)
        return tune_reply_to_dict(result)
    except Exception as e:
        return {"ok": False, "type": "error", "reply": f"Tune error: {e}", "applied": [], "errors": [str(e)]}

@app.get("/history")
def get_history():
    if _core_available and state and hasattr(state, "conversation_history"):
        return state.conversation_history or []
    return _conversation

@app.post("/history/clear")
def clear_history():
    global _conversation
    _conversation = []
    if _core_available and state and hasattr(state, "conversation_history"):
        state.conversation_history = []
    # Also wipe the persisted file so history stays cleared across restarts.
    try:
        from core.agent import _CONVERSATION_HISTORY_PATH
        if _CONVERSATION_HISTORY_PATH.exists():
            _CONVERSATION_HISTORY_PATH.unlink()
    except Exception:
        pass
    return {"ok": True}

@app.post("/agent/run")
async def agent_run(req: AgentRequest):
    if _core_available and agent_module:
        try:
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
        os.environ["CURRENT_TIER"] = tier
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
        result = await optimize_prompt_with_dynamic_agents(req.prompt, model=req.model, preset_id=req.preset)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/presets")
async def get_presets():
    from core.presets import get_all_presets, preset_to_dict
    return {"presets": [preset_to_dict(p) for p in get_all_presets()]}

if __name__ == "__main__":
    print("[Wiztant] Starting core API server on http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
