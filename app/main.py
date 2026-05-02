"""app/main.py — Unified cross-platform entry point for Whiztant.

Boots the agent, voice, memory, and UI systems via the Platform Abstraction Layer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path so `core`, `ui`, and `platforms` resolve
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

import uvicorn
from platforms.factory import (
    get_hotkeys,
    get_platform_name,
    get_system_access,
    get_tts,
    get_vlm,
    get_window_mgmt,
)

# =============================================================
#  LOAD .env (via python-dotenv for robust parsing)
# =============================================================

_env_candidates = [str(_ROOT / ".env")]
if sys.platform.startswith("linux"):
    import pathlib as _pathlib
    _xdg_cfg = os.getenv("XDG_CONFIG_HOME", str(_pathlib.Path.home() / ".config"))
    _env_candidates.append(os.path.join(_xdg_cfg, "whiztant", ".env"))

_env_path = next((p for p in _env_candidates if os.path.exists(p)), _env_candidates[0])

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path, override=True)
except Exception:
    # Fallback manual parser if python-dotenv unavailable
    if os.path.exists(_env_path):
        with open(_env_path, "r", encoding="utf-8", errors="replace") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#"):
                    continue
                if "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip()
                if "#" in _v and not (_v.startswith('"') or _v.startswith("'")):
                    _v = _v.split("#", 1)[0].strip()
                if (_v.startswith('"') and _v.endswith('"')) or (_v.startswith("'") and _v.endswith("'")):
                    _v = _v[1:-1]
                os.environ[_k] = _v

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PLATFORM = get_platform_name()


def _dbg(msg: str):
    if DEBUG:
        print(msg)


_dbg("[.env] loaded")

# =============================================================
#  DATA DIRECTORY INITIALIZER
# =============================================================


def _init_data_dir():
    data = _ROOT / "data"
    data.mkdir(exist_ok=True)

    for log_name in ("whiztant.log", "system_changes.log"):
        p = data / log_name
        if not p.exists():
            p.touch()
            _dbg(f"[Data] created {p.name}")

    _json_defaults = {
        "undo_stack.json": [],
        "license.json": {},
        "session.json": {},
    }
    for fname, default in _json_defaults.items():
        p = data / fname
        if not p.exists():
            p.write_text(json.dumps(default, indent=2), encoding="utf-8")
            _dbg(f"[Data] created {p.name}")
        else:
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"[Data] {p.name} was corrupt — resetting to default")
                p.write_text(json.dumps(default, indent=2), encoding="utf-8")


_init_data_dir()

# =============================================================
#  STARTUP HEALTH CHECK
# =============================================================

_REQUIRED_KEYS = {
    "OPENAI_API_KEY": "Tune / Agent",
    "GROQ_API_KEY": "Cloud STT (Whisper)",
    "SUPABASE_URL": "Auth & Usage sync",
    "OPENROUTER_API_KEY": "UI-TARS Agent",
    "LEMONSQUEEZY_API_KEY": "License validation",
}


def _health_check():
    missing = []
    for key, feature in _REQUIRED_KEYS.items():
        val = os.getenv(key, "").strip()
        if not val:
            missing.append((key, feature))

    if not missing:
        _dbg("[Health] All required keys present.")
        return

    try:
        from platforms.factory import get_platform_name
        if get_platform_name() == "windows":
            from winotify import Notification

            def _toast(title: str, msg: str):
                n = Notification(app_id="Whiztant", title=title, msg=msg, duration="short")
                n.show()
        else:
            def _toast(title: str, msg: str):
                print(f"[Config] {title}: {msg}")
    except Exception:
        def _toast(title: str, msg: str):
            print(f"[Config] {title}: {msg}")

    for key, feature in missing:
        print(f"[Config] MISSING: {key}  ({feature} disabled)")
        _toast(f"Missing config: {key}", f"{feature} will be disabled. Edit {_env_path} to fix.")

    if len(missing) == len(_REQUIRED_KEYS):
        print("[Config] WARNING: No API keys configured. Running in offline demo mode.")


_health_check()

# =============================================================
#  IMPORTS — order matters (voice loads Whisper, agent registers tools)
# =============================================================

import core  # shared state + config

# Platform drivers (lazy — no cross-platform import crashes)
_hotkeys = get_hotkeys()
_wm = get_window_mgmt()
_system = get_system_access()
_vlm = get_vlm()
_tts = get_tts()

# Platform config setup
if PLATFORM == "linux":
    from platforms.linux import config as platform_config
else:
    from platforms.windows import config as platform_config

_dbg("[Platform] drivers loaded")

from core import memory as memory_mod
_dbg("[Memory] module imported")

from core import voice
_dbg("[Voice] module imported (Groq cloud STT)")

from core import agent  # registers tools, sets up OpenAI client
_dbg(f"[Agent] tools registered: {len(agent.TOOLS)} tools")

from core.ws_bridge import start_ws_bridge, send_pill_notice, broadcast_sync


# =============================================================
#  HELPERS
# =============================================================

def seconds_until(hour: int, minute: int = 0) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


# Singleton guards to prevent duplicate background timers/threads across reloads.
_due_check_timer: threading.Timer | None = None
_due_reminder_timer: threading.Timer | None = None
_startup_nudge_thread: threading.Thread | None = None
_overlay_thread: threading.Thread | None = None


def _due_reminder():
    global _due_reminder_timer
    try:
        from core.tasks import get_carried_over_undone
        tasks = get_carried_over_undone()
        if tasks:
            broadcast_sync({
                "type": "due_reminder",
                "count": len(tasks),
                "tasks": [
                    {"id": task.get("id"), "title": task.get("text", ""), "scheduled_for": task.get("due_at")}
                    for task in tasks
                ],
            })
        # Only reschedule if there are still undone tasks; otherwise let _due_check restart it.
        if get_carried_over_undone():
            _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
            _due_reminder_timer.daemon = True
            _due_reminder_timer.start()
        else:
            _due_reminder_timer = None
    except Exception:
        _due_reminder_timer = None


def _due_check():
    global _due_check_timer, _due_reminder_timer
    try:
        from core.tasks import get_due_today_undone, mark_failed
        tasks = get_due_today_undone()
        if tasks:
            second_miss = [task for task in tasks if task.get("carried_over")]
            first_miss = [task for task in tasks if not task.get("carried_over")]

            if second_miss:
                failed_tasks = []
                for task in second_miss:
                    if mark_failed(task.get("id", "")):
                        failed_tasks.append({"id": task.get("id"), "title": task.get("text", "")})
                if failed_tasks:
                    broadcast_sync({"type": "tasks_failed", "tasks": failed_tasks})
                    try:
                        from core.tasks import get_task_snapshot
                        snapshot = get_task_snapshot()
                        broadcast_sync({
                            "type": "tasks/update",
                            "payload": snapshot.get("tasks", []),
                            "history": snapshot.get("history", []),
                            "suggestion": snapshot.get("suggestion"),
                        })
                    except Exception:
                        pass

            if first_miss:
                broadcast_sync({
                    "type": "due_alert",
                    "count": len(first_miss),
                    "tasks": [{"id": task.get("id"), "title": task.get("text", "")} for task in first_miss],
                })
                # Cancel any existing reminder before starting a fresh one so they don't pile up.
                if _due_reminder_timer is not None:
                    _due_reminder_timer.cancel()
                _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
                _due_reminder_timer.daemon = True
                _due_reminder_timer.start()
    except Exception:
        pass
    finally:
        _due_check_timer = threading.Timer(seconds_until(18, 0), _due_check)
        _due_check_timer.daemon = True
        _due_check_timer.start()


# =============================================================
#  SYSTEM CONTEXT
# =============================================================

_sys_ctx_thread: threading.Thread | None = None


def _init_sys_ctx():
    global _sys_ctx_thread
    try:
        from core.system_context import initialize_system_context
        ldr, sched = initialize_system_context(Path("data"))
        core.system_context_loader = ldr
        core.system_context_scheduler = sched
    except Exception as _e:
        print(f"[SysCtx] Startup error: {_e}")
    finally:
        _sys_ctx_thread = None


if _sys_ctx_thread is None or not _sys_ctx_thread.is_alive():
    _sys_ctx_thread = threading.Thread(target=_init_sys_ctx, daemon=True, name="sys-ctx-init")
    _sys_ctx_thread.start()

# =============================================================
#  INIT
# =============================================================

core.MEMORY_ENABLED = memory_mod.init()
_dbg(f"[Memory] {'enabled' if core.MEMORY_ENABLED else 'disabled'}")

platform_config.setup()

# Register hotkeys via PAL
_hotkeys.register_hotkeys()
_dbg("[Hotkeys] registered")

# Linux fallback: register F9/F10/Escape via pynput in case Electron globalShortcut fails
# (common on Wayland). Debounce in toggle_agent_mode prevents double-toggle on X11.
if PLATFORM == "linux":
    try:
        from core.hotkeys import f9_handler, task_hotkey_handler, hide_chat_overlay_if_visible
        _hotkeys.register("f9", f9_handler)
        _hotkeys.register("f10", task_hotkey_handler)
        _hotkeys.register("escape", hide_chat_overlay_if_visible)
        print("[Hotkeys/Linux] pynput fallback registered for F9, F10, Escape")
    except Exception as e:
        print(f"[Hotkeys/Linux] pynput fallback registration failed: {e}")

# Start WS bridge for Electron overlay IPC
try:
    start_ws_bridge()
    _dbg("[WS] Bridge started on ws://localhost:9120")
except Exception as _e:
    print(f"[WS] Could not start WebSocket bridge: {_e}")

# Background agent manager
try:
    from core.background_agent import init_background_agent
    _bg_mgr = init_background_agent()
    _dbg("[BG Agent] Background agent manager started")
except Exception as _e:
    print(f"[BG Agent] Could not start background agent: {_e}")
    _bg_mgr = None

# System tray icon
try:
    from core.tray import start_tray
    start_tray()
except Exception as _e:
    print(f"[Tray] Could not start tray: {_e}")

# WizType
try:
    from core.wiztype import ensure_wiztype_started_from_config
    ensure_wiztype_started_from_config()
    _dbg("[WizType] initialized")
except Exception as _e:
    print(f"[WizType] Could not initialize: {_e}")

# Tune Hub middleware — wires learned parameters into feature hot paths
try:
    from core.tune_hub.factory import create_tune_hub
    from core.tune_hub.middleware import TuneApplicationMiddleware
    from core.tune_hub.quality.judge import LLMJudge

    # Load persisted Tune Hub settings
    _tunehub_settings_path = _ROOT / "data" / "tunehub_settings.json"
    if _tunehub_settings_path.exists():
        try:
            core.tune_hub_settings = json.loads(_tunehub_settings_path.read_text(encoding="utf-8"))
        except Exception:
            core.tune_hub_settings = {}

    def _judge_factory():
        """Create LLMJudge with user-selected model from settings."""
        model = core.tune_hub_settings.get("model", "")
        return LLMJudge(model=model) if model else LLMJudge()

    _tune_hub_tier = os.getenv("CURRENT_TIER", "free")
    _tune_hub = create_tune_hub(tier=_tune_hub_tier, judge_factory=_judge_factory)
    core.tune_hub = _tune_hub
    core.tune_middleware = TuneApplicationMiddleware(_tune_hub)
    _dbg("[TuneHub] middleware initialized")
except Exception as _e:
    print(f"[TuneHub] Could not initialize: {_e}")
    core.tune_hub = None
    core.tune_middleware = None


# =============================================================
#  MAIN SERVER
# =============================================================

def run_app():
    global _startup_nudge_thread, _overlay_thread, _due_check_timer, _due_reminder_timer
    _tier = os.getenv("CURRENT_TIER", "free")
    _model = agent.get_model()

    _dbg(f"\n[Whiztant] Ready — {_tier.upper()} tier, model: {_model}")
    if not DEBUG:
        print(f"[Whiztant] Ready — {_tier.upper()} tier")

    try:
        from core.toast import toast_ready
        toast_ready(_tier)
    except Exception:
        pass

    from core.server import app
    print("[Whiztant] Starting API backend on http://localhost:8765")
    print("[Whiztant] Press Ctrl+Space to toggle overlay")

    # Startup nudge
    def _startup_nudge():
        global _startup_nudge_thread
        try:
            from core.tasks import get_yesterday_pending_summary
            time.sleep(8)
            summary = get_yesterday_pending_summary()
            if summary:
                send_pill_notice(
                    kind="updated",
                    title="You have tasks from yesterday",
                    summary=summary,
                    duration_ms=3200,
                )
        except Exception:
            pass
        finally:
            _startup_nudge_thread = None

    if _startup_nudge_thread is None or not _startup_nudge_thread.is_alive():
        _startup_nudge_thread = threading.Thread(target=_startup_nudge, daemon=True, name="startup-nudge")
        _startup_nudge_thread.start()

    try:
        from core.tasks import get_carried_over_undone
        if _due_check_timer is None or not _due_check_timer.is_alive():
            _due_check_timer = threading.Timer(seconds_until(18, 0), _due_check)
            _due_check_timer.daemon = True
            _due_check_timer.start()
        if get_carried_over_undone():
            if _due_reminder_timer is None or not _due_reminder_timer.is_alive():
                _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
                _due_reminder_timer.daemon = True
                _due_reminder_timer.start()
    except Exception:
        pass

    # Start overlay in background
    def _start_overlay_bg():
        global _overlay_thread
        try:
            from ui.react_overlay import ensure_react_overlay_running
            ensure_react_overlay_running()
        except Exception as overlay_error:
            print(f"[Whiztant] Overlay startup skipped: {overlay_error}")
        finally:
            _overlay_thread = None

    if _overlay_thread is None or not _overlay_thread.is_alive():
        _overlay_thread = threading.Thread(target=_start_overlay_bg, daemon=True, name="overlay-start")
        _overlay_thread.start()

    def _shutdown_active_work():
        try:
            from core.hotkeys import cancel_active_recording
            cancel_active_recording()
        except Exception:
            pass
        try:
            stop_event = getattr(core, "_agent_stop_event", None)
            if stop_event is not None:
                stop_event.set()
        except Exception:
            pass
        try:
            from core.wiztype import shutdown_wiztype
            shutdown_wiztype()
        except Exception:
            pass
        try:
            from core.agent import _save_conversation_history
            _save_conversation_history()
        except Exception:
            pass

    try:
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
    except KeyboardInterrupt:
        _shutdown_active_work()
        print("[Whiztant] Shutting down...")
    finally:
        _shutdown_active_work()
        try:
            from core.background_agent import stop_background_agent
            stop_background_agent()
        except Exception:
            pass
        try:
            from ui.react_overlay import stop_overlay
            stop_overlay()
        except Exception:
            pass


if __name__ == "__main__":
    run_app()
