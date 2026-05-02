"""
=============================================================
  WHIZTANT — Personal AI Operating Assistant
=============================================================
  Run:  python main.py
  Set DEBUG=true in .env for verbose startup logging.
=============================================================
"""

import sys
import os
import json
import threading
import time
import subprocess
import uvicorn
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path so `core` and `ui` resolve
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)  # ensure CWD = project root for any relative paths

# =============================================================
#  LOAD .env
# =============================================================

# Load .env: project root first, then XDG fallback for Linux installs
_env_candidates = [os.path.join(_ROOT, ".env")]
if sys.platform.startswith("linux"):
    import pathlib as _pathlib
    _xdg_cfg = os.getenv("XDG_CONFIG_HOME", str(_pathlib.Path.home() / ".config"))
    _env_candidates.append(os.path.join(_xdg_cfg, "whiztant", ".env"))

_env_path = next((p for p in _env_candidates if os.path.exists(p)), _env_candidates[0])
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8", errors="replace") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def _dbg(msg: str):
    if DEBUG:
        print(msg)

_dbg("[.env] loaded")

# =============================================================
#  DATA DIRECTORY INITIALIZER
#  Runs before any module import so every module can assume
#  these files exist and are valid JSON where applicable.
# =============================================================

def _init_data_dir():
    data = Path(_ROOT) / "data"
    data.mkdir(exist_ok=True)

    # Plain log files — create empty if missing
    for log_name in ("whiztant.log", "system_changes.log"):
        p = data / log_name
        if not p.exists():
            p.touch()
            _dbg(f"[Data] created {p.name}")

    # JSON files — create with valid empty default if missing or corrupt
    _json_defaults = {
        "undo_stack.json": [],
        "license.json":    {},
        "session.json":    {},
    }
    for fname, default in _json_defaults.items():
        p = data / fname
        if not p.exists():
            p.write_text(json.dumps(default, indent=2), encoding="utf-8")
            _dbg(f"[Data] created {p.name}")
        else:
            # Validate existing JSON — reset to default if corrupt
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"[Data] {p.name} was corrupt — resetting to default")
                p.write_text(json.dumps(default, indent=2), encoding="utf-8")

_init_data_dir()

# =============================================================
#  STARTUP HEALTH CHECK
#  Validates required .env keys. Missing keys show a winotify
#  toast and disable that feature — never crash the app.
# =============================================================

# key → which feature it gates (used in toast message)
_REQUIRED_KEYS = {
    "OPENAI_API_KEY":       "Chat / Agent",
    "GROQ_API_KEY":         "Cloud STT (Whisper)",
    "SUPABASE_URL":         "Auth & Usage sync",
    "OPENROUTER_API_KEY":   "UI-TARS Agent",
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

    # Import toast lazily — winotify may not be installed in dev
    try:
        from winotify import Notification
        def _toast(title: str, msg: str):
            n = Notification(app_id="Whiztant", title=title, msg=msg, duration="short")
            n.show()
    except Exception:
        def _toast(title: str, msg: str):
            print(f"[Config] {title}: {msg}")

    for key, feature in missing:
        print(f"[Config] MISSING: {key}  ({feature} disabled)")
        _toast(
            f"Missing config: {key}",
            f"{feature} will be disabled. Edit {_env_path} to fix.",
        )

    if len(missing) == len(_REQUIRED_KEYS):
        print("[Config] WARNING: No API keys configured. Running in offline demo mode.")

_health_check()

# =============================================================
#  IMPORTS — order matters (voice loads Whisper, agent registers tools)
# =============================================================

import core                        # shared state + config

# =============================================================
#  PLATFORM DETECTION — import the right platform modules
# =============================================================

if sys.platform == "win32":
    PLATFORM = "windows"
    from core.windows import hotkeys, vlm, tts, window_mgmt, config as platform_config
    _dbg("[Platform] Windows modules loaded")
elif sys.platform.startswith("linux"):
    PLATFORM = "linux"
    from core.linux import hotkeys, vlm, tts, window_mgmt, config as platform_config
    _dbg("[Platform] Linux modules loaded")
else:
    raise RuntimeError(f"[Platform] Unsupported OS: {sys.platform}")

# Shared (platform-agnostic) modules
from core import memory as memory_mod
_dbg("[Memory] module imported")

from core import voice
_dbg("[Voice] module imported (Groq cloud STT)")

from core import agent             # registers tools, sets up OpenAI client
_dbg(f"[Agent] tools registered: {len(agent.TOOLS)} tools")

from core.ws_bridge import start_ws_bridge, send_pill_notice, broadcast_sync


def seconds_until(hour: int, minute: int = 0) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _due_reminder():
    try:
        from core.tasks import get_carried_over_undone

        tasks = get_carried_over_undone()
        if tasks:
            broadcast_sync({
                "type": "due_reminder",
                "count": len(tasks),
                "tasks": [
                    {
                        "id": task.get("id"),
                        "title": task.get("text", ""),
                        "scheduled_for": task.get("due_at"),
                    }
                    for task in tasks
                ],
            })
            threading.Timer(4 * 3600, _due_reminder).start()
    except Exception:
        pass


def _due_check():
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
                        failed_tasks.append({
                            "id": task.get("id"),
                            "title": task.get("text", ""),
                        })
                if failed_tasks:
                    broadcast_sync({
                        "type": "tasks_failed",
                        "tasks": failed_tasks,
                    })

            if first_miss:
                broadcast_sync({
                    "type": "due_alert",
                    "count": len(first_miss),
                    "tasks": [
                        {"id": task.get("id"), "title": task.get("text", "")}
                        for task in first_miss
                    ],
                })
                threading.Timer(4 * 3600, _due_reminder).start()
    except Exception:
        pass
    finally:
        threading.Timer(seconds_until(18, 0), _due_check).start()

# =============================================================
#  SYSTEM CONTEXT — scan on first run, schedule hourly/daily updates
# =============================================================

def _init_sys_ctx():
    try:
        from core.system_context import initialize_system_context
        ldr, sched = initialize_system_context(Path("data"))
        core.system_context_loader = ldr
        core.system_context_scheduler = sched
    except Exception as _e:
        print(f"[SysCtx] Startup error: {_e}")

threading.Thread(target=_init_sys_ctx, daemon=True, name="sys-ctx-init").start()

# =============================================================
#  INIT
# =============================================================

# Memory
core.MEMORY_ENABLED = memory_mod.init()
_dbg(f"[Memory] {'enabled' if core.MEMORY_ENABLED else 'disabled'}")

# Platform setup (creates data dirs, logs platform info)
platform_config.setup()

# Register F9 (delegates to platform-specific implementation)
hotkeys.register_hotkeys()
_dbg(f"[Hotkeys] registered via {PLATFORM} module")

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

# React overlay will be started on-demand via Ctrl+Space hotkey
# No need to start it here

# System tray icon
try:
    from core.tray import start_tray
    start_tray()
except Exception as _e:
    print(f"[Tray] Could not start tray: {_e}")

try:
    from core.wiztype import ensure_wiztype_started_from_config
    ensure_wiztype_started_from_config()
    _dbg("[WizType] initialized")
except Exception as _e:
    print(f"[WizType] Could not initialize: {_e}")

# =============================================================
#  START ELECTRON APP
# =============================================================

def run_electron():
    _dbg("[Electron] Starting UI...")
    requested_ui = os.getenv("WHIZTANT_DESKTOP_UI", "whiztant-overlay")
    fallback_ui = "whiztant-overlay"

    def _ensure_ui_dependencies(target_path: str, target_name: str):
        required_packages = ("vite", "electron", "concurrently", "wait-on")
        node_modules_path = os.path.join(target_path, "node_modules")
        needs_install = (not os.path.exists(node_modules_path)) or any(
            not os.path.exists(os.path.join(node_modules_path, package_name))
            for package_name in required_packages
        )

        if needs_install:
            print(f"[Whiztant] Installing desktop UI dependencies for {target_name}...")
            result = subprocess.run(
                "npm install",
                cwd=target_path,
                shell=True,
                env=os.environ.copy(),
            )
            if result.returncode != 0:
                raise RuntimeError(f"npm install failed for {target_name} (exit {result.returncode})")

    def _start_ui(target_path: str):
        # Use dev server if no build exists; preview requires pre-built out/
        cmd = "npm run dev" if not os.path.exists(os.path.join(target_path, "out")) else "npm run start"
        return subprocess.Popen(
            cmd,
            cwd=target_path,
            shell=True,
            env=os.environ.copy(),
        )

    ui_name = requested_ui
    ui_path = os.path.join(_ROOT, "ui", ui_name)

    if not os.path.exists(ui_path):
        print(f"[Whiztant] UI '{ui_name}' not found. Falling back to '{fallback_ui}'.")
        ui_name = fallback_ui
        ui_path = os.path.join(_ROOT, "ui", ui_name)

    try:
        _ensure_ui_dependencies(ui_path, ui_name)
        proc = _start_ui(ui_path)
        return proc
    except Exception as e:
        print(f"[Electron] Failed to start UI '{ui_name}': {e}")
        if ui_name != fallback_ui:
            fallback_path = os.path.join(_ROOT, "ui", fallback_ui)
            if os.path.exists(fallback_path):
                try:
                    print(f"[Whiztant] Falling back to '{fallback_ui}'.")
                    _ensure_ui_dependencies(fallback_path, fallback_ui)
                    return _start_ui(fallback_path)
                except Exception as fallback_error:
                    print(f"[Electron] Fallback UI failed: {fallback_error}")
        return None
#  MAIN SERVER
# =============================================================

def run_app():
    _tier  = os.getenv("CURRENT_TIER", "free")
    _model = agent.get_model()

    _dbg(f"\n[Whiztant] Ready — {_tier.upper()} tier, model: {_model}")
    if not DEBUG:
        print(f"[Whiztant] Ready — {_tier.upper()} tier")

    from core.toast import toast_ready
    toast_ready(_tier)

    electron_proc = run_electron()

    from core.server import app
    print("[Whiztant] Starting API backend on http://localhost:8765")
    print("[Whiztant] Press Ctrl+Space to toggle overlay")

    # Schedule a startup pill nudge if yesterday's pending tasks exist
    def _startup_nudge():
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

    threading.Thread(target=_startup_nudge, daemon=True, name="startup-nudge").start()

    try:
        from core.tasks import get_carried_over_undone
        threading.Timer(seconds_until(18, 0), _due_check).start()
        if get_carried_over_undone():
            threading.Timer(4 * 3600, _due_reminder).start()
    except Exception:
        pass

    # Start the overlay in the background so it stays resident as a minimized
    # pill and Ctrl+Space expands it instantly without a cold launch.
    def _start_overlay_bg():
        try:
            from ui.react_overlay import ensure_react_overlay_running
            ensure_react_overlay_running()
        except Exception as overlay_error:
            print(f"[Whiztant] Overlay startup skipped: {overlay_error}")
    threading.Thread(target=_start_overlay_bg, daemon=True).start()

    def _terminate_process_tree(proc):
        if not proc:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    f"taskkill /PID {proc.pid} /T /F",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc.terminate()
        except Exception:
            pass

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
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
    except KeyboardInterrupt:
        _shutdown_active_work()
        print("[Whiztant] Shutting down...")
    finally:
        _shutdown_active_work()
        # Stop background agent manager (kills any running browser processes)
        try:
            from core.background_agent import stop_background_agent
            stop_background_agent()
        except Exception:
            pass
        # Clean up overlay process if running
        try:
            from ui.react_overlay import stop_overlay
            stop_overlay()
        except Exception:
            pass
        if electron_proc:
            _terminate_process_tree(electron_proc)

if __name__ == "__main__":
    run_app()
