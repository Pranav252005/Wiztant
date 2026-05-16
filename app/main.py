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
from datetime import datetime, timedelta, timezone
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

# ─── Feature flags ───────────────────────────────────────────
_FEATURE_FLAGS = {"agent": True, "tasks": True, "reprompt": True, "tunehub": True}

def _load_feature_flags():
    """Read feature flags from data/settings.json. All features default to enabled."""
    global _FEATURE_FLAGS
    try:
        settings_path = _ROOT / "data" / "settings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            features = data.get("features", {})
            if isinstance(features, dict):
                for key in _FEATURE_FLAGS:
                    if key in features and isinstance(features[key], bool):
                        _FEATURE_FLAGS[key] = features[key]
        _dbg(f"[Features] loaded: {_FEATURE_FLAGS}")
    except Exception as e:
        _dbg(f"[Features] load error: {e}")

_load_feature_flags()


def _save_feature_flags(features: dict):
    """Save feature flags to data/settings.json."""
    try:
        settings_path = _ROOT / "data" / "settings.json"
        data = {}
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        data["features"] = features
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        _dbg(f"[Features] save error: {e}")


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
_credit_reset_timer: threading.Timer | None = None

# Reminder tracking: task_id -> {"pre_due_warned": bool, "due_warned": bool, "overdue_reminder_count": int, "last_overdue_reminder": float}
# Used to implement the aggressive multi-stage reminder schedule without spamming.
_reminder_tracker: dict[str, dict] = {}
_REMINDER_CHECK_INTERVAL_SEC = 15 * 60  # 15 minutes


def _get_task_settings() -> dict:
    """Load task reminder settings, with sensible defaults."""
    import json as _json
    import os
    try:
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
                if isinstance(data, dict):
                    return {
                        "reminder_interval_min": int(data.get("reminder_interval_min", 15)),
                        "pre_due_warning": bool(data.get("pre_due_warning", True)),
                        "carry_over": bool(data.get("carry_over", True)),
                    }
    except Exception:
        pass
    return {"reminder_interval_min": 15, "pre_due_warning": True, "carry_over": True}


def _due_reminder():
    """Periodic reminder for carried-over tasks (legacy, kept for compatibility)."""
    global _due_reminder_timer
    try:
        from core.tasks import get_carried_over_undone, is_snoozed
        tasks = [t for t in get_carried_over_undone() if not is_snoozed(t)]
        if tasks:
            broadcast_sync({
                "type": "due_reminder",
                "count": len(tasks),
                "tasks": [
                    {"id": task.get("id"), "title": task.get("text", ""), "scheduled_for": task.get("due_at")}
                    for task in tasks
                ],
            })
        if get_carried_over_undone():
            _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
            _due_reminder_timer.daemon = True
            _due_reminder_timer.start()
        else:
            _due_reminder_timer = None
    except Exception:
        _due_reminder_timer = None


def _cleanup_stale_tracker(tasks: list):
    """Remove tracker entries for tasks that no longer exist or are completed."""
    global _reminder_tracker
    valid_ids = {t.get("id", "") for t in tasks}
    _reminder_tracker = {k: v for k, v in _reminder_tracker.items() if k in valid_ids}


def _monthly_credit_reset_check():
    """Periodic check to apply monthly credit resets. Runs every hour."""
    global _credit_reset_timer
    try:
        from core.credit_system import check_monthly_reset, get_current_user_id
        user_id = get_current_user_id()
        if check_monthly_reset(user_id):
            print(f"[Credits] Monthly reset applied for {user_id}")
    except Exception as e:
        print(f"[Credits] Monthly reset check error: {e}")
    finally:
        _credit_reset_timer = threading.Timer(3600, _monthly_credit_reset_check)
        _credit_reset_timer.daemon = True
        _credit_reset_timer.start()


def _due_check():
    global _due_check_timer, _due_reminder_timer
    try:
        from core.tasks import get_due_today_undone, get_due_soon, is_snoozed, mark_failed
        settings = _get_task_settings()

        # ── 1. Pre-due warnings (tasks due within 30 minutes) ──
        if settings.get("pre_due_warning", True):
            soon_tasks = get_due_soon(minutes=30)
            for task in soon_tasks:
                tid = task.get("id", "")
                tracker = _reminder_tracker.setdefault(tid, {})
                if not tracker.get("pre_due_warned", False):
                    due_at = task.get("due_at", "")
                    minutes_remaining = 0
                    try:
                        from datetime import datetime as _dt
                        dt = _dt.fromisoformat(str(due_at).replace("Z", "+00:00"))
                        now = _dt.now(timezone.utc)
                        minutes_remaining = max(0, int((dt - now).total_seconds() / 60))
                    except Exception:
                        pass
                    broadcast_sync({
                        "type": "pill_notification",
                        "payload": {
                            "task_id": tid,
                            "title": task.get("text", ""),
                            "due_datetime": due_at,
                            "notification_type": "pre_due",
                            "minutes_remaining": minutes_remaining,
                        },
                    })
                    tracker["pre_due_warned"] = True

        # ── 2. Tasks that are due today / right now ──
        tasks = get_due_today_undone()
        if tasks:
            second_miss = [task for task in tasks if task.get("carried_over")]
            first_miss = [task for task in tasks if not task.get("carried_over")]

            # Second miss → mark as failed
            if second_miss:
                failed_tasks = []
                for task in second_miss:
                    if is_snoozed(task):
                        continue
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

            # First miss → due alert + aggressive reminders
            if first_miss:
                now_ts = datetime.now(timezone.utc).timestamp()
                newly_due = []
                for task in first_miss:
                    tid = task.get("id", "")
                    tracker = _reminder_tracker.setdefault(tid, {})
                    if not tracker.get("due_warned", False):
                        newly_due.append(task)
                        tracker["due_warned"] = True

                if newly_due:
                    broadcast_sync({
                        "type": "due_alert",
                        "count": len(newly_due),
                        "tasks": [{"id": t.get("id"), "title": t.get("text", "")} for t in newly_due],
                    })
                    for task in newly_due:
                        broadcast_sync({
                            "type": "pill_notification",
                            "payload": {
                                "task_id": task.get("id"),
                                "title": task.get("text", ""),
                                "due_datetime": task.get("due_at"),
                                "notification_type": "due_now",
                                "minutes_remaining": 0,
                            },
                        })

                # Aggressive overdue reminders: every 15 minutes while overdue
                for task in first_miss:
                    tid = task.get("id", "")
                    tracker = _reminder_tracker.setdefault(tid, {})
                    last_reminder = tracker.get("last_overdue_reminder", 0)
                    if now_ts - last_reminder >= _REMINDER_CHECK_INTERVAL_SEC:
                        tracker["last_overdue_reminder"] = now_ts
                        tracker["overdue_reminder_count"] = tracker.get("overdue_reminder_count", 0) + 1
                        broadcast_sync({
                            "type": "overdue_reminder",
                            "task": {"id": tid, "title": task.get("text", "")},
                            "reminder_count": tracker["overdue_reminder_count"],
                        })
                        broadcast_sync({
                            "type": "pill_notification",
                            "payload": {
                                "task_id": tid,
                                "title": task.get("text", ""),
                                "due_datetime": task.get("due_at"),
                                "notification_type": "overdue",
                                "minutes_remaining": 0,
                            },
                        })

        # ── 3. Carried-over undone tasks ──
        try:
            from core.tasks import get_carried_over_undone
            carried = [t for t in get_carried_over_undone() if not is_snoozed(t)]
            if carried and (_due_reminder_timer is None or not _due_reminder_timer.is_alive()):
                _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
                _due_reminder_timer.daemon = True
                _due_reminder_timer.start()
        except Exception:
            pass

        # Clean up tracker entries for completed / deleted tasks
        try:
            from core.tasks import get_tasks
            _cleanup_stale_tracker(get_tasks())
        except Exception:
            pass

    except Exception:
        pass
    finally:
        # Reschedule every 15 minutes instead of waiting for 18:00
        _due_check_timer = threading.Timer(_REMINDER_CHECK_INTERVAL_SEC, _due_check)
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

# Linux fallback: register F9/F10/Escape via pynput ONLY on Wayland where
# Electron globalShortcut fails. On X11 Electron handles these fine; registering
# both causes a double-fire race (Electron starts recording, pynput stops it
# 400 ms later from the same physical keypress).
if PLATFORM == "linux":
    _is_wayland = (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )
    if _is_wayland:
        try:
            from core.hotkeys import f9_handler, task_hotkey_handler, hide_chat_overlay_if_visible
            from core.hotkeys import _load_task_creation_mode, _load_shortcuts_enabled
            _hotkeys.register("f9", f9_handler)
            _hotkeys.register("escape", hide_chat_overlay_if_visible)
            if _load_task_creation_mode() == "hotkey" or _load_shortcuts_enabled():
                _hotkeys.register("f10", task_hotkey_handler)
                print("[Hotkeys/Linux/Wayland] pynput fallback registered for F9, F10, Escape")
            else:
                print("[Hotkeys/Linux/Wayland] pynput fallback registered for F9, Escape (F10 disabled — smart mode)")
        except Exception as e:
            print(f"[Hotkeys/Linux/Wayland] pynput fallback registration failed: {e}")
    else:
        print("[Hotkeys/Linux/X11] Skipping pynput fallback — Electron globalShortcut active")

# Pre-warm microphone stream in the background so first F9/F10 is instant.
# Only the initial PortAudio init takes time; subsequent presses reuse the stream.
def _prewarm_mic():
    try:
        from core.hotkeys import _ensure_audio_stream
        _ensure_audio_stream()
        print("[Audio] Microphone stream pre-warmed")
    except Exception as e:
        print(f"[Audio] Mic pre-warm skipped: {e}")

threading.Thread(target=_prewarm_mic, daemon=True, name="mic-prewarm").start()

# Start WS bridge for Electron overlay IPC
try:
    start_ws_bridge()
    _dbg("[WS] Bridge started on ws://localhost:9120")
except Exception as _e:
    print(f"[WS] Could not start WebSocket bridge: {_e}")

# Background agent manager (only if agent feature enabled)
_bg_mgr = None
if _FEATURE_FLAGS.get("agent", True):
    try:
        from core.background_agent import init_background_agent
        _bg_mgr = init_background_agent()
        _dbg("[BG Agent] Background agent manager started")
    except Exception as _e:
        print(f"[BG Agent] Could not start background agent: {_e}")
else:
    _dbg("[BG Agent] Skipped (agent feature disabled)")

# System tray icon
try:
    from core.tray import start_tray
    start_tray()
except Exception as _e:
    print(f"[Tray] Could not start tray: {_e}")

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
#  FEATURE FLAG API (used by ws_bridge)
# =============================================================

def get_feature_flags() -> dict:
    """Return current feature flags."""
    return dict(_FEATURE_FLAGS)


def update_feature_flags(features: dict) -> dict:
    """Update feature flags, persist to disk, and return the new state."""
    global _FEATURE_FLAGS
    for key in _FEATURE_FLAGS:
        if key in features and isinstance(features[key], bool):
            _FEATURE_FLAGS[key] = features[key]
    _save_feature_flags(dict(_FEATURE_FLAGS))
    _dbg(f"[Features] updated: {_FEATURE_FLAGS}")
    return dict(_FEATURE_FLAGS)


# =============================================================
#  MAIN SERVER
# =============================================================

def run_app():
    global _startup_nudge_thread, _overlay_thread, _due_check_timer, _due_reminder_timer, _credit_reset_timer
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

    # Start monthly credit reset checker (every hour)
    if _credit_reset_timer is None or not _credit_reset_timer.is_alive():
        _credit_reset_timer = threading.Timer(60, _monthly_credit_reset_check)
        _credit_reset_timer.daemon = True
        _credit_reset_timer.start()

    if _FEATURE_FLAGS.get("tasks", True):
        try:
            from core.tasks import get_carried_over_undone, is_snoozed
            if _due_check_timer is None or not _due_check_timer.is_alive():
                _due_check_timer = threading.Timer(30, _due_check)
                _due_check_timer.daemon = True
                _due_check_timer.start()
            carried = [t for t in get_carried_over_undone() if not is_snoozed(t)]
            if carried:
                if _due_reminder_timer is None or not _due_reminder_timer.is_alive():
                    _due_reminder_timer = threading.Timer(4 * 3600, _due_reminder)
                    _due_reminder_timer.daemon = True
                    _due_reminder_timer.start()
        except Exception:
            pass
    else:
        _dbg("[Tasks] Due-check timer skipped (tasks feature disabled)")

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
