"""
Wiztant core/tray.py — System tray icon (pystray).
Menu items:
  • Status / usage summary
  • Show overlay / Hide overlay
  • Undo last action
  • License activation
  • Quit
Call start_tray() from main.py after the waveform overlay is running.
"""

import io
import os
import subprocess
import sys
import threading
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_ICON_PATH = _ROOT / "wiztantW.svg"


# ── dynamic label ─────────────────────────────────────────────────────────────

def _usage_label(item) -> str:
    """Called by pystray each time the menu is rendered — always fresh."""
    try:
        from core.usage import get_remaining, get_tier, TIER_LIMITS
        tier = get_tier()
        remaining = get_remaining("chat", tier)
        limit = TIER_LIMITS.get(tier, {}).get("chat", 0)
        return f"Tunes left: {remaining} / {limit}  •  {tier.upper()}"
    except Exception:
        return "Wiztant"


def _overlay_running_label(item) -> str:
    try:
        from ui.react_overlay import _is_process_alive
        return "Overlay: Running" if _is_process_alive() else "Overlay: Stopped"
    except Exception:
        return "Overlay: Unknown"


def _theme_label(item) -> str:
    return "Theme: Graphite Dark"


def _mode_label(item) -> str:
    try:
        import core as state
        if getattr(state, "agent_mode", False):
            return "Mode: Agent"
        return "Mode: Dictation"
    except Exception:
        return "Mode: Unknown"


def _recording_label(item) -> str:
    try:
        import core as state
        return "Recording: Active" if getattr(state, "recording", False) else "Recording: Idle"
    except Exception:
        return "Recording: Unknown"


# ── callbacks ─────────────────────────────────────────────────────────────────

def _on_show_overlay(icon, item):
    def _run():
        try:
            from ui.react_overlay import show_react_overlay
            show_react_overlay()
        except Exception as e:
            print(f"[Tray] Show overlay error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_hide_overlay(icon, item):
    def _run():
        try:
            from ui.react_overlay import hide_react_overlay_if_visible
            hide_react_overlay_if_visible()
        except Exception as e:
            print(f"[Tray] Hide overlay error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_set_dictation_mode(icon, item):
    def _run():
        try:
            import core as state
            from core.toast import show_toast
            if getattr(state, "_agent_running", False) and getattr(state, "_agent_stop_event", None):
                state._agent_stop_event.set()
            state.agent_mode = False
            show_toast("Dictation mode ready", "Wiztant")
        except Exception as e:
            print(f"[Tray] Dictation mode error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_set_agent_mode(icon, item):
    def _run():
        try:
            import core as state
            from core.toast import show_toast
            state.agent_mode = True
            show_toast("Agent mode ready", "Wiztant")
        except Exception as e:
            print(f"[Tray] Agent mode error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _recording_active(item) -> bool:
    try:
        import core as state
        return bool(getattr(state, "recording", False))
    except Exception:
        return False


def _recording_inactive(item) -> bool:
    return not _recording_active(item)


def _on_start_recording(icon, item):
    def _run():
        try:
            from core.hotkeys import start_recording
            start_recording()
        except Exception as e:
            print(f"[Tray] Start recording error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_stop_recording(icon, item):
    def _run():
        try:
            from core.hotkeys import stop_and_process
            stop_and_process()
        except Exception as e:
            print(f"[Tray] Stop recording error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _undo_has_entries(item) -> bool:
    """Called by pystray each render — greys out the item when stack is empty."""
    try:
        from core.system_access import UNDO_STACK
        return UNDO_STACK.exists() and UNDO_STACK.stat().st_size > 10
    except Exception:
        return False


def _on_undo(icon, item):
    def _run():
        try:
            from core.system_access import undo_last
            from core.toast import show_toast
            result = undo_last()
            show_toast(result, "Wiztant")
        except Exception as e:
            print(f"[Tray] Undo error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _bg_tasks_label(item) -> str:
    """Dynamic label showing background agent task counts."""
    try:
        from core.background_agent import get_background_agent_manager
        mgr = get_background_agent_manager()
        status = mgr.get_status()
        active = status["active"]
        queued = status["queued"]
        completed = status["completed"]
        return f"BG Tasks: {active} running, {queued} queued, {completed} done"
    except Exception:
        return "BG Tasks: --"


def _on_view_bg_tasks(icon, item):
    """Show the background agent results panel."""
    def _run():
        try:
            from ui.agent_results_panel import show_results_panel
            show_results_panel()
        except Exception as e:
            print(f"[Tray] View bg tasks error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _load_tray_image():
    try:
        from PIL import Image

        if _ICON_PATH.exists() and _ICON_PATH.suffix.lower() == ".svg":
            # PyQt6 SVG rendering requires a display — skip on headless Linux
            has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
            if has_display:
                try:
                    from PyQt6.QtCore import QByteArray, Qt
                    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
                    from PyQt6.QtSvg import QSvgRenderer

                    app = QGuiApplication.instance() or QGuiApplication([])
                    renderer = QSvgRenderer(str(_ICON_PATH))
                    if renderer.isValid():
                        size = 64
                        image = QImage(size, size, QImage.Format.Format_ARGB32)
                        image.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(image)
                        renderer.render(painter)
                        painter.end()

                        buffer = QByteArray()
                        from PyQt6.QtCore import QBuffer, QIODevice
                        qbuffer = QBuffer(buffer)
                        qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
                        image.save(qbuffer, "PNG")
                        qbuffer.close()
                        return Image.open(io.BytesIO(bytes(buffer))).convert("RGBA")
                except Exception as e:
                    print(f"[Tray] SVG render fallback failed: {e}")

        if _ICON_PATH.exists() and _ICON_PATH.suffix.lower() != ".svg":
            return Image.open(str(_ICON_PATH)).convert("RGBA")

        return Image.new("RGBA", (64, 64), color="#7A828E")
    except Exception as e:
        print(f"[Tray] Icon load error: {e}")
        from PIL import Image
        return Image.new("RGBA", (64, 64), color="#7A828E")


def _on_view_system_context(icon, item):
    def _run():
        try:
            import core as state
            from platforms.factory import get_system_access
            ldr = getattr(state, "system_context_loader", None)
            if ldr and ldr.context_file_exists():
                system = get_system_access()
                system.open_file(str(ldr.context_file))
            else:
                print("[Tray] System context file not yet generated")
        except Exception as e:
            print(f"[Tray] View sys ctx error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_refresh_system_context_full(icon, item):
    def _run():
        try:
            import core as state
            sched = getattr(state, "system_context_scheduler", None)
            if sched:
                sched.trigger_refresh("full")
        except Exception as e:
            print(f"[Tray] Full refresh error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_refresh_system_context_quick(icon, item):
    def _run():
        try:
            import core as state
            sched = getattr(state, "system_context_scheduler", None)
            if sched:
                sched.trigger_refresh("lightweight")
        except Exception as e:
            print(f"[Tray] Quick refresh error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _on_quit(icon, item):
    # Graceful shutdown to ensure overlay and background processes exit
    try:
        from core.hotkeys import cancel_active_recording
        cancel_active_recording()
    except Exception:
        pass
    try:
        import core as state
        stop_event = getattr(state, "_agent_stop_event", None)
        if stop_event is not None:
            stop_event.set()
    except Exception:
        pass
    try:
        from core.background_agent import stop_background_agent
        stop_background_agent()
    except Exception:
        pass
    try:
        from core.wiztype import shutdown_wiztype
        shutdown_wiztype()
    except Exception:
        pass
    try:
        from ui.react_overlay import stop_overlay
        stop_overlay()
    except Exception:
        pass
    try:
        icon.stop()
    except Exception:
        pass
    os._exit(0)


# ── public entry point ────────────────────────────────────────────────────────

_tray_icon = None

def start_tray():
    """Create the tray icon and run it detached. Returns the Icon or None."""
    global _tray_icon
    if _tray_icon is not None:
        return _tray_icon
    try:
        import pystray
        image = _load_tray_image()

        # Callables are re-evaluated on every menu open (usage label, undo enabled).
        menu = pystray.Menu(
            pystray.MenuItem(_usage_label, None, enabled=False),
            pystray.MenuItem(_overlay_running_label, None, enabled=False),
            pystray.MenuItem(_theme_label, None, enabled=False),
            pystray.MenuItem(_mode_label, None, enabled=False),
            pystray.MenuItem(_recording_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Overlay", _on_show_overlay),
            pystray.MenuItem("Hide Overlay", _on_hide_overlay),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Switch to Dictation", _on_set_dictation_mode),
            pystray.MenuItem("Switch to Agent", _on_set_agent_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Recording", _on_start_recording, enabled=_recording_inactive),
            pystray.MenuItem("Stop Recording and Send", _on_stop_recording, enabled=_recording_active),
            pystray.MenuItem("Undo Last Action", _on_undo, enabled=_undo_has_entries),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_bg_tasks_label, None, enabled=False),
            pystray.MenuItem("View Background Tasks", _on_view_bg_tasks),
            pystray.MenuItem("System Context", pystray.Menu(
                pystray.MenuItem("View System Context File", _on_view_system_context),
                pystray.MenuItem("Refresh Now (Full Scan)", _on_refresh_system_context_full),
                pystray.MenuItem("Refresh Now (Quick)", _on_refresh_system_context_quick),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _on_quit),
        )

        icon = pystray.Icon("Wiztant", image, "Wiztant", menu)
        icon.run_detached()
        _tray_icon = icon
        print("[Tray] System tray icon started")
        return icon
    except Exception as e:
        print(f"[Tray] Could not start tray icon: {e}")
        return None
