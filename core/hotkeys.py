"""
Whiztant core/hotkeys.py — F9 handler with refined tap timing,
recording control, and audio callback.

Tap behavior:
  F9 x1  → Dictation: record, transcribe, paste
  F9 x2  → Toggle Agent mode on / off
  F9 x3+ → Toggle Agent mode on / off
"""

import json
import os
import subprocess
import sys
import time
import tempfile
import threading

import numpy as np
import soundfile as sf
import pyperclip

# Lazy import keyboard — not available on Linux without root, so never crash on import.
_keyboard_module = None

def _keyboard():
    global _keyboard_module
    if _keyboard_module is None:
        try:
            import keyboard as _kb
            _keyboard_module = _kb
        except Exception:
            _keyboard_module = False
    return _keyboard_module

import core as state
from core.voice import transcribe_wav
from core.stt_engine import (
    StreamingSTT,
    start_streaming_stt,
    stop_streaming_stt,
    smart_paste,
)
from core.stt_refiner import STTRefiner
from core.smart_paste import SmartPasteEngine
from core.vocab import VocabManager
from core.dictation_memory import add_memory as _add_dictation_memory

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")


def _load_task_hotkey() -> str:
    """Load the user-configured task-creation hotkey (default F10)."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        key = str(data.get("task_hotkey", "f10")).strip().lower()
        return key or "f10"
    except Exception:
        return "f10"


def _load_task_hotkey_taps() -> int:
    """Load tap count for single-key task hotkey (default 1)."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        taps = int(data.get("task_hotkey_taps", 1))
        return max(1, min(5, taps))
    except Exception:
        return 1


def _load_shortcuts_enabled() -> bool:
    """Load whether custom shortcuts are enabled (default False)."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("shortcuts_enabled", False))
    except Exception:
        return False


def _load_task_creation_mode() -> str:
    """Load task creation preference: 'hotkey' (F10) or 'smart' (dictation detection)."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        mode = str(data.get("task_creation_mode", "hotkey")).strip().lower()
        return mode if mode in ("hotkey", "smart") else "hotkey"
    except Exception:
        return "hotkey"


def _load_setting(key: str, default=None):
    """Read a setting from data/settings.json."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key, default)
    except Exception:
        return default


def _save_setting(key: str, value) -> None:
    """Write a setting to data/settings.json."""
    try:
        data = {}
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[key] = value
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Settings] Failed to save {key}: {e}")


_audio_stream = None
_last_pasted_text: list = [""]  # single-element mutable cell for last dictation result
_active_stt: StreamingSTT | None = None
_last_stt_text: str = ""

# ── Multi-monitor focus tracking ────────────────────────────────────────────
# Saved at recording start so paste lands in the correct window/field.
_recording_start_focus: dict = {}  # {"window_id": str|None, "desktop_id": str|None, "cursor": (x, y), "timestamp": float}


def _save_recording_focus() -> None:
    """Capture the currently active window, desktop, and mouse position before dictation.

    On X11 this gives us a window ID we can restore. On Wayland we at least
    have the cursor position so we can click back into the right field.
    We also record the current virtual desktop so we never force-switch
    workspaces on restore.
    """
    global _recording_start_focus
    focus = {"window_id": None, "desktop_id": None, "cursor": (0, 0), "timestamp": time.time()}

    # 1. Try to get active window ID (X11 / XWayland)
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            wid = result.stdout.strip()
            if wid and wid.isdigit():
                focus["window_id"] = wid
    except Exception:
        pass

    # 2. Remember the current virtual desktop so we don't switch workspaces later
    try:
        result = subprocess.run(
            ["xdotool", "get_desktop"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            focus["desktop_id"] = result.stdout.strip()
    except Exception:
        pass

    # 3. Get cursor position (works on X11 and most Wayland setups)
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            x = y = 0
            for line in result.stdout.strip().split("\n"):
                if line.startswith("X="):
                    x = int(line.split("=", 1)[1])
                elif line.startswith("Y="):
                    y = int(line.split("=", 1)[1])
            focus["cursor"] = (x, y)
    except Exception:
        pass

    _recording_start_focus = focus


def _restore_recording_focus() -> None:
    """Restore focus to the window/field that was active when recording started."""
    focus = _recording_start_focus
    if not focus:
        return

    window_id = focus.get("window_id")
    saved_desktop = focus.get("desktop_id")
    cursor_x, cursor_y = focus.get("cursor", (0, 0))

    # If no window was captured, nothing to restore
    if not window_id:
        return

    # Check if the target window is already active
    already_active = False
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            already_active = result.stdout.strip() == window_id
    except Exception:
        pass

    if already_active:
        return

    # Get current desktop
    current_desktop = None
    try:
        result = subprocess.run(
            ["xdotool", "get_desktop"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            current_desktop = result.stdout.strip()
    except Exception:
        pass

    # Find out which desktop the saved window is actually on.
    # If it's on a different desktop, don't force-switch workspaces —
    # the user moved intentionally. Just paste into whatever is active here.
    window_desktop = None
    try:
        result = subprocess.run(
            ["xdotool", "get_desktop_for_window", window_id],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            window_desktop = result.stdout.strip()
    except Exception:
        pass

    if window_desktop is not None and current_desktop is not None:
        if window_desktop != current_desktop:
            print(f"[Focus] Saved window is on desktop {window_desktop}, current is {current_desktop}; not switching")
            return

    # We're on the same desktop as the saved window, but it's not active.
    # Restore it so paste lands in the right field.
    try:
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", window_id],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass

    try:
        subprocess.run(
            ["xdotool", "windowfocus", "--sync", window_id],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass

    try:
        subprocess.run(
            ["wmctrl", "-ia", window_id],
            capture_output=True, timeout=1,
        )
    except Exception:
        pass

    time.sleep(0.08)

    # Verify the window actually became active
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0 and result.stdout.strip() == window_id:
            print(f"[Focus] Restored window {window_id}")
            return
    except Exception:
        pass

    # Final fallback: click at the saved cursor position to refocus the
    # specific text field within the window (handles cases where window
    # activation succeeded but input focus didn't land in the text box).
    if cursor_x or cursor_y:
        try:
            subprocess.run(
                ["xdotool", "mousemove", str(cursor_x), str(cursor_y)],
                capture_output=True, timeout=1,
            )
            time.sleep(0.05)
            subprocess.run(
                ["xdotool", "click", "1"],
                capture_output=True, timeout=1,
            )
            time.sleep(0.05)
        except Exception:
            pass


def _paste_clipboard() -> bool:
    """Simulate Ctrl+V paste at the active cursor. Returns True on success."""
    try:
        from platforms.factory import get_system_access
        system = get_system_access()
        ok, _ = system.hotkey("ctrl", "v")
        return ok
    except Exception:
        return False

# Mic level publisher: runs while recording, pushes state.audio_level to the
# overlay WS at ~25 Hz so the pill wave can scale its amplitude live.
_mic_publisher_stop = None
_mic_publisher_thread = None


def _try_ws_send(fn, *args, **kwargs):
    """Best-effort WS send — swallow errors so voice flow never dies on a missing bridge."""
    try:
        from core.ws_bridge import (
            send_mic_level as _send_mic_level,
            send_voice_state as _send_voice_state,
        )
    except Exception:
        return
    try:
        if fn == "mic":
            _send_mic_level(*args, **kwargs)
        elif fn == "state":
            _send_voice_state(*args, **kwargs)
    except Exception:
        pass


def _start_mic_publisher():
    """Spin up a lightweight thread that polls state.audio_level → WS."""
    global _mic_publisher_stop, _mic_publisher_thread
    if _mic_publisher_thread is not None and _mic_publisher_thread.is_alive():
        return
    stop = threading.Event()
    _mic_publisher_stop = stop

    # Reasonable normalization: microphone RMS on 16-bit audio typically
    # sits in the 50–3000 range during speech. Divide by 4000 and clamp.
    def _loop():
        while not stop.is_set():
            level = float(getattr(state, "audio_level", 0.0) or 0.0)
            norm = max(0.0, min(1.0, level / 4000.0))
            _try_ws_send("mic", norm)
            stop.wait(0.04)  # ~25 Hz

    t = threading.Thread(target=_loop, daemon=True)
    _mic_publisher_thread = t
    t.start()


def _stop_mic_publisher():
    global _mic_publisher_stop, _mic_publisher_thread
    if _mic_publisher_stop is not None:
        _mic_publisher_stop.set()
        _mic_publisher_stop = None
    # Defensive: also clear the thread handle so the next start isn't
    # blocked by a dying thread that hasn't exited yet.
    if _mic_publisher_thread is not None:
        _mic_publisher_thread = None
    # Push a final 0 so the pill wave settles immediately.
    _try_ws_send("mic", 0.0)

# =============================================================
#  AUDIO CALLBACK
# =============================================================

def audio_callback(indata, frames, time_info, status):
    try:
        audio_np = np.frombuffer(indata, dtype=np.int16)
        rms = float(np.sqrt(np.mean(audio_np.astype(np.float32) ** 2)))
        state.audio_level = rms

        if state.recording:
            state.audio_frames.append(audio_np.copy())
            if _active_stt is not None:
                _active_stt.append_frame(audio_np.copy())
    except Exception as e:
        print(f"[Audio] callback error: {e}")


def _ensure_audio_stream():
    """Create or reuse the permanent microphone stream so F9/F10 is instant."""
    global _audio_stream
    import sounddevice as sd
    if _audio_stream is None:
        _audio_stream = sd.RawInputStream(
            samplerate=16000,
            blocksize=1024,
            dtype="int16",
            channels=1,
            callback=audio_callback,
            latency="low",
        )
    if not getattr(_audio_stream, "active", False):
        try:
            _audio_stream.start()
        except Exception as e:
            print(f"[Audio] Failed to start microphone stream: {e}")
            _audio_stream = None
            raise RuntimeError("Microphone unavailable") from e


# =============================================================
#  TRANSCRIBE + DISPATCH
# =============================================================

def _format_time_label(due_iso):
    if not due_iso:
        return ""
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(str(due_iso).replace("Z", "+00:00")).astimezone()
        return dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return ""


def _handle_new_task(candidate_text: str, due_at):
    """Classify voice text + add as new task / subtask / duplicate notice."""
    from core.tasks import add_task, add_subtask, get_tasks, get_task_snapshot
    from core.task_classifier import classify as _classify_task
    from core.ws_bridge import send_tasks_update, send_pill_notice, broadcast_sync

    verdict = _classify_task(candidate_text, get_tasks())
    if verdict["action"] == "duplicate":
        parent_id = verdict.get("parent_id", "")
        existing = next((t for t in get_tasks() if t.get("id") == parent_id), None)
        hour = 0
        minute = 0
        existing_due = existing.get("due_at") if existing else None
        if existing_due:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(str(existing_due).replace("Z", "+00:00")).astimezone()
                hour = dt.hour
                minute = dt.minute
            except Exception:
                pass
        broadcast_sync({
            "type": "task_duplicate",
            "existing_task": {
                "id": parent_id,
                "title": verdict.get("parent_text") or candidate_text,
                "scheduled_for": existing_due or "",
                "hour": hour,
                "minute": minute,
            },
            "new_time": _format_time_label(due_at),
        })
        send_pill_notice(
            "duplicate",
            "Already tracked",
            verdict.get("parent_text") or candidate_text,
        )
        return
    if verdict["action"] == "subtask":
        parent_id = verdict.get("parent_id", "")
        subtask_text = verdict.get("subtask_text") or candidate_text
        saved = add_subtask(parent_id, subtask_text, source="voice", due_at=due_at)
        send_pill_notice(
            "subtask",
            f"Added to: {verdict.get('parent_text', '')}",
            subtask_text,
        )
        if saved:
            broadcast_sync({
                "type": "task_saved",
                "task": saved,
                "reply": f"✓ Added subtask: \"{subtask_text[:40]}\"",
            })
        snapshot = get_task_snapshot()
        send_tasks_update(snapshot.get("tasks", []))
        return
    saved = add_task(candidate_text, source="voice", due_at=due_at)
    if saved:
        broadcast_sync({
            "type": "task_saved",
            "task": saved,
            "reply": f"✓ Task saved: \"{candidate_text[:40]}\"",
        })
    else:
        send_pill_notice("added", "Task added", candidate_text)
    snapshot = get_task_snapshot()
    send_tasks_update(snapshot.get("tasks", []))


# Pending task confirmations: confirm_id -> {text, due_at}
_pending_task_confirmations: dict = {}


def _propose_task_for_confirmation(text: str, due_at, raw_text: str = ""):
    """Send a task_confirm_request to the pill instead of saving immediately.

    The pill will show a confirmation bar; when the user approves, the
    frontend sends task_confirm_approve back to ws_bridge.py, which then
    calls _handle_new_task to actually save the task.
    """
    import uuid
    confirm_id = f"confirm_{uuid.uuid4().hex[:8]}"
    _pending_task_confirmations[confirm_id] = {
        "text": text,
        "due_at": due_at,
        "raw_text": raw_text or text,
    }
    from core.ws_bridge import broadcast_sync
    broadcast_sync({
        "type": "task_confirm_request",
        "payload": {
            "id": confirm_id,
            "parsed_title": text,
            "due_datetime": due_at,
            "has_time": bool(due_at and ("T" in str(due_at) or ":" in str(due_at))),
            "has_date": bool(due_at),
        },
    })


def transcribe_and_dispatch(captured_stt: str = "", captured_frames: list = None):
    # If this was an F10 task-capture recording, route to the task pipeline.
    if getattr(state, "_task_recording", False):
        state._task_recording = False
        _task_transcribe_and_save()
        return

    global _last_stt_text

    # Use captured snapshots if provided (prevents race with duplicate start_recording).
    text = ""
    _was_streaming = False
    if captured_stt:
        text = captured_stt
        _was_streaming = True
        # Also clear the live variable so it doesn't leak to the next session
        _last_stt_text = ""
        try:
            from core.voice import clean_transcript
            text = clean_transcript(text)
        except Exception as e:
            print(f"[STT] clean_transcript error: {e}")
    elif _last_stt_text:
        text = _last_stt_text
        _last_stt_text = ""
        _was_streaming = True
        try:
            from core.voice import clean_transcript
            text = clean_transcript(text)
        except Exception as e:
            print(f"[STT] clean_transcript error: {e}")

    audio_frames = captured_frames if captured_frames is not None else state.audio_frames
    if not text and not audio_frames:
        print("[Audio] No frames captured.")
        _try_ws_send("state", "error", "No audio captured")
        if state.overlay:
            state.overlay.set_idle()
        return

    if not text:
        audio_np = np.concatenate(audio_frames).astype(np.float32)

        peak = float(np.max(np.abs(audio_np)))
        if peak < state.SILENCE_THRESHOLD:
            print(f"[Audio] Too quiet (peak={peak:.0f}), skipping.")
            _try_ws_send("state", "error", "Audio too quiet")
            return

        audio_np /= peak + 1e-6

        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        sf.write(tmp_wav, audio_np, 16000)

        _try_ws_send("state", "processing")
        text = transcribe_wav(tmp_wav)

        try:
            os.remove(tmp_wav)
        except Exception:
            pass

        if not text:
            print("[Whisper] No speech detected.")
            _try_ws_send("state", "error", "No speech detected")
            if state.overlay:
                state.overlay.set_idle()
            return

    # ── Reject obvious junk / hallucinations early ──────────────
    # Do this before any printing or mode-specific processing so junk
    # never reaches the clipboard, tasks, or AI history.
    _agent_is_active = getattr(state, "_agent_running", False)
    if not state.agent_mode and not _agent_is_active and _is_dictation_junk(text):
        print(f"[Dictation] Rejected junk/hallucination: {text!r}")
        _try_ws_send("state", "error", "No speech detected")
        if state.overlay:
            state.overlay.set_idle()
        return

    # Only log the final transcript after we've confirmed it's not junk.
    if _was_streaming:
        print(f"\n[STT] Final (streamed): {text}")
    else:
        print(f"\nYou: {text}")

    # Tune Hub: apply learned dictation corrections if available
    try:
        from core.tune_hub.middleware import TuneApplicationMiddleware
        middleware = getattr(state, "tune_middleware", None)
        if middleware:
            import os as _os
            import hashlib as _hashlib
            _user = _os.environ.get("USER", _os.environ.get("USERNAME", "local"))
            _host = _os.environ.get("HOSTNAME", "unknown")
            _user_id = _hashlib.sha256(f"{_user}@{_host}".encode()).hexdigest()[:16]
            tuned = middleware.apply(
                user_id=_user_id,
                feature_name="dictation",
                task=text,
                feature_input={"text": text},
            )
            tuned_text = tuned.get("text", text)
            if tuned_text and tuned_text != text:
                print(f"[TuneHub] Dictation tune applied: {text[:60]}... → {tuned_text[:60]}...")
                text = tuned_text
    except Exception:
        pass

    if state.agent_mode or _agent_is_active:
        # Agent mode — send to AI
        print("[STT] Transcribing for agent...")
        if state.overlay:
            state.overlay.set_thinking()
        _try_ws_send("state", "processing", text)
        from core.agent import add_history_message, ask_ai
        add_history_message("user", text)
        _add_dictation_memory(text, text, mode="agent")

        def _run():
            try:
                ask_ai(text, user_already_added=True)
            except Exception as e:
                print(f"[AI] Error: {e}")
                _try_ws_send("state", "error", str(e))
                if state.overlay:
                    state.overlay.set_idle()

        threading.Thread(target=_run, daemon=True).start()
        # Track insights for agent voice command
        try:
            from core.insights_tracker import record_event
            word_count = len(text.split())
            record_event("words_dictated", word_count)
            record_event("voice_command")
            record_event("ai_prompt")
        except Exception:
            pass
    else:
        # ── Dictation credit deduction (after validation, before processing) ──
        try:
            from core.credit_system import deduct, get_current_user_id
            user_id = get_current_user_id()
            deduct(user_id, "dictation", 1, model="whisper-large-v3-turbo")
        except Exception:
            pass

        # ── Smart dictation: emails, scratch-that, symbols ────────
        # Runs on ALL tiers (free included) — fast, local, zero-cost.
        original_text = text
        try:
            from core.dictation_smart import smart_dictate
            smart_result = smart_dictate(text)
            if smart_result["text"] != text:
                text = smart_result["text"]
                if smart_result.get("changes"):
                    print(f"[SmartDictate] {', '.join(smart_result['changes'])}")
        except Exception as e:
            print(f"[SmartDictate] Error: {e}")

        # ── Phonetic fuzzy + domain-aware corrections ─────────────
        _context_words = text.split()
        try:
            from core.dictation_correction import apply_corrections
            text, phonetic_changes = apply_corrections(text, context_window=_context_words)
            if phonetic_changes:
                print(f"[Phonetic] {', '.join(phonetic_changes)}")
        except Exception as e:
            print(f"[Phonetic] Error: {e}")

        # Check for voice task commands before pasting
        from core.tasks import (
            parse_task_command, mark_done, delete_task, edit_task_text, edit_task_due,
            get_task_snapshot, parse_due_time, default_noon_due_at,
            refine_task_text, extract_task_mention, verify_task_intent,
            is_explicit_task_command,
        )
        from core.ws_bridge import send_tasks_update, send_pill_notice

        # ── "update memory <spell>" voice command ──────────────────
        # Handled BEFORE task parsing so it never pastes.
        import re as _re
        mem_upd = _re.match(
            r'^\s*(?:update|change|fix)\s+(?:my\s+)?(?:memory|spelling|vocab(?:ulary)?)\b[\s,:.\-]*(.*)$',
            text,
            _re.IGNORECASE,
        )
        if mem_upd:
            tail = mem_upd.group(1).strip(" ,.-:;")
            # _collapse_spelled_out handles the add-or-update + pill notice.
            from core.voice import _collapse_spelled_out as _collapse
            produced = _collapse(tail) if tail else ""
            if not produced or produced.strip() == tail.strip():
                # Nothing recognizable was spelled out — tell the user.
                send_pill_notice(
                    "error",
                    "Spell it out",
                    "Say 'update memory S-H-E-V-O-R-A' to change a spelling.",
                )
            _try_ws_send("state", "idle")
            if state.overlay:
                state.overlay.set_idle()
            _add_dictation_memory(original_text, text, mode="dictation")
            return

        # /task slash-command — explicit task capture.
        # Whisper typically emits "slash task ...", but we also accept "/task ..."
        # or "slashtask ...". Everything after the trigger becomes the task;
        # if no time is specified, default to 12 PM.
        slash = _re.match(
            r'^\s*(?:/\s*task|slash[\s-]*task)\b[\s,:.\-]*(.*)$',
            text,
            _re.IGNORECASE,
        )
        if slash:
            rest = slash.group(1).strip(" ,.-:;")
            if rest:
                cleaned, due_at = parse_due_time(rest)
                refined = refine_task_text(cleaned) or cleaned
                if not due_at:
                    due_at = default_noon_due_at()
                _propose_task_for_confirmation(refined, due_at, text)
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return

        cmd = parse_task_command(text)
        if cmd:
            action = cmd["action"]
            if action == "add":
                _propose_task_for_confirmation(cmd["text"], cmd.get("due_at"), text)
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            elif action == "done" and cmd.get("task_id"):
                mark_done(cmd["task_id"])
                snapshot = get_task_snapshot()
                send_tasks_update(snapshot.get("tasks", []))
                print(f"[Task] Done: {cmd['text']}")
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            elif action == "in_progress" and cmd.get("task_id"):
                from core.tasks import mark_in_progress
                mark_in_progress(cmd["task_id"])
                snapshot = get_task_snapshot()
                send_tasks_update(snapshot.get("tasks", []))
                print(f"[Task] Started: {cmd['text']}")
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            elif action == "delete" and cmd.get("task_id"):
                delete_task(cmd["task_id"])
                snapshot = get_task_snapshot()
                send_tasks_update(snapshot.get("tasks", []))
                print(f"[Task] Deleted: {cmd['text']}")
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            elif action == "edit" and cmd.get("task_id"):
                edit_task_text(cmd["task_id"], cmd["text"])
                snapshot = get_task_snapshot()
                send_tasks_update(snapshot.get("tasks", []))
                print(f"[Task] Updated: {cmd['text']}")
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            elif action == "reschedule" and cmd.get("task_id") and cmd.get("due_at"):
                edit_task_due(cmd["task_id"], cmd["due_at"])
                snapshot = get_task_snapshot()
                send_tasks_update(snapshot.get("tasks", []))
                print(f"[Task] Rescheduled: {cmd['text']}")
                _try_ws_send("state", "idle")
                if state.overlay:
                    state.overlay.set_idle()
                _add_dictation_memory(original_text, text, mode="dictation")
                return
            # list or unmatched — fall through to paste

        # ── Smart task detection (when F10 hotkey is disabled) ─────
        # Two-layer strict gate:
        #   1. Explicit prefix regex (fast path) → create task immediately.
        #   2. Borderline mention → LLM intent verification → only create
        #      if the model confirms explicit_task_request with confidence ≥ 0.8.
        #   3. If LLM rejects or is uncertain → fall through to normal paste.
        task_mode = _load_task_creation_mode()
        if task_mode == "smart" and not cmd:
            candidate = extract_task_mention(text)
            if candidate:
                # Distinguish explicit prefix match from borderline mention
                if is_explicit_task_command(text):
                    # Layer 1: explicit command — fast path, no LLM needed
                    cleaned, due_at = parse_due_time(candidate)
                    refined = refine_task_text(cleaned) or cleaned
                    if refined:
                        _propose_task_for_confirmation(refined, due_at, text)
                        _try_ws_send("state", "idle")
                        if state.overlay:
                            state.overlay.set_idle()
                        _add_dictation_memory(original_text, text, mode="dictation")
                        return
                else:
                    # Layer 2: borderline mention — run LLM verification
                    verified = verify_task_intent(candidate)
                    if verified:
                        cleaned, due_at = parse_due_time(verified)
                        refined = refine_task_text(cleaned) or cleaned
                        if refined:
                            _propose_task_for_confirmation(refined, due_at, text)
                            _try_ws_send("state", "idle")
                            if state.overlay:
                                state.overlay.set_idle()
                            _add_dictation_memory(original_text, text, mode="dictation")
                            return
                    # If LLM rejected → fall through to paste below

        # Dictation mode — refine, apply vocab, format, paste (or preview)
        _last_pasted_text[0] = text
        paste_ok = False

        # Production STT pipeline: refine -> vocab -> format -> paste/preview
        try:
            # Step 1: AI refinement (Pro/Power tier or when USE_LLM_POLISH is on)
            if getattr(state, "USE_LLM_POLISH", False) or os.getenv("TIER", "free").lower() in ["pro", "power"]:
                _refiner = STTRefiner()
                _vocab_mgr = VocabManager()
                _refiner.set_vocab(_vocab_mgr.vocab_db)
                refined_result = _refiner.refine_transcript(text)
                if not refined_result.get("error"):
                    text = refined_result["refined"]
                    if refined_result.get("changes"):
                        print(f"[STT] Refinements: {refined_result['changes']}")

            # Step 2: Apply vocabulary corrections
            _vocab_mgr = VocabManager()
            corrected, vocab_changes = _vocab_mgr.apply_corrections(text)
            if vocab_changes:
                print(f"[STT] Vocab fixes: {vocab_changes}")
                text = corrected
        except Exception as e:
            print(f"[STT] Refinement error: {e}")

        # ── Live Dictation Preview (non-blocking) ─────────────────
        if _load_setting("live_dictation_preview", True):
            import uuid as _uuid
            _preview_session = f"preview-{_uuid.uuid4().hex[:12]}"
            from core.dictation_correction import start_undo_hook
            start_undo_hook(_preview_session, original_text, text)
            # Persist to dictation memory so the preview has a real database ID
            _preview_entry = _add_dictation_memory(original_text, text, mode="dictation")
            from core.ws_bridge import broadcast_sync, send_pill_notice
            broadcast_sync({
                "type": "dictation_preview",
                "text": text,
                "original_text": original_text,
                "session_id": _preview_session,
                "id": _preview_entry.get("id", ""),
            })
            send_pill_notice(
                "updated",
                "Dictation ready",
                "Edit in the pill preview, then copy or optimize.",
                duration_ms=3000,
            )
            # NOTE: we do NOT return here. The preview is shown as a convenience,
            # but dictation still pastes/copies automatically so the flow never breaks.

        # ── Normal paste branch ───────────────────────────────────
        def _copy_to_clipboard_robust(t: str) -> bool:
            """Copy text to clipboard with platform fallback and logging."""
            try:
                import pyperclip
                pyperclip.copy(t)
                return True
            except Exception as e:
                print(f"[Clipboard] pyperclip failed: {e}")
            try:
                from platforms.factory import get_system_access
                system = get_system_access()
                system.set_clipboard(t)
                return True
            except Exception as e:
                print(f"[Clipboard] platform fallback failed: {e}")
            return False

        # Pull the saved window ID so we can paste directly to it even if
        # focus was stolen by the overlay or window manager.
        _saved_window_id = _recording_start_focus.get("window_id")

        try:
            # Step 3: Restore focus to the field that was active when recording
            # started, then paste. Critical for multi-monitor setups.
            _restore_recording_focus()

            # Smart format + paste
            _paste_engine = SmartPasteEngine()
            formatted = _paste_engine.format_for_task(text)
            paste_ok, msg = _paste_engine.paste_text(
                formatted, format_type="plain", window_id=_saved_window_id
            )
            if not paste_ok:
                # Fallback: legacy smart_paste provides an additional set of
                # paste strategies (type_text, etc.).  A small delay lets any
                # stuck keys from the previous attempt settle before we try
                # another injection method.
                time.sleep(0.15)
                paste_ok = smart_paste(text, window_id=_saved_window_id)
                if not paste_ok:
                    if _copy_to_clipboard_robust(text):
                        from core.ws_bridge import send_pill_notice
                        send_pill_notice("added", "Copied to clipboard", text[:60])
                    else:
                        from core.ws_bridge import send_pill_notice
                        send_pill_notice("error", "Clipboard failed", "Could not copy dictation text")
        except Exception as e:
            print(f"[STT] Pipeline error: {e}")
            # Fallback to raw text with a small safety delay
            time.sleep(0.15)
            paste_ok = smart_paste(text, window_id=_saved_window_id)
            if not paste_ok:
                if _copy_to_clipboard_robust(text):
                    from core.ws_bridge import send_pill_notice
                    send_pill_notice("added", "Copied to clipboard", text[:60])
                else:
                    from core.ws_bridge import send_pill_notice
                    send_pill_notice("error", "Clipboard failed", "Could not copy dictation text")

        if paste_ok:
            print(f"\n✅ PASTED: {text[:100]}")
            # Notify overlay so it can play the green paste-complete flash.
            _try_ws_send("state", "pasted", text)
        else:
            print(f"\n❌ PASTE FAILED — copied to clipboard: {text[:100]}")
            _try_ws_send("state", "error", "Paste failed — copied to clipboard")
        if state.overlay:
            state.overlay.set_idle()

        # Track insights for dictation
        try:
            from core.insights_tracker import record_event
            word_count = len(text.split())
            record_event("words_dictated", word_count)
            record_event("personal_message")
            record_event("voice_command")
        except Exception:
            pass

        # Save to local dictation memory (customer computer only — no cloud)
        _add_dictation_memory(original_text, text, mode="dictation")


# =============================================================
#  RECORDING CONTROL
# =============================================================

_last_start_time = 0.0
_START_DEBOUNCE_SEC = 0.3
_start_recording_lock = threading.Lock()

_last_stop_time = 0.0
_STOP_DEBOUNCE_SEC = 0.3
_stop_recording_lock = threading.Lock()


def start_recording():
    global _audio_stream, _active_stt, _last_stt_text, _last_start_time

    # Credit gate for pure dictation (not agent voice input)
    if not state.agent_mode and not getattr(state, "_agent_running", False):
        try:
            from core.credit_system import can_afford, get_current_user_id
            user_id = get_current_user_id()
            if not can_afford(user_id, 1):
                from core.toast import show_toast
                from core.ws_bridge import send_pill_notice
                show_toast("Dictation blocked — out of credits", "Wiztant")
                _try_ws_send("state", "error", "Insufficient credits for dictation. Upgrade at whiztant.app/pricing")
                send_pill_notice("error", "0 Credits", "Dictation blocked. Upgrade at whiztant.app/pricing", duration_ms=4000)
                return
        except Exception as e:
            # Log the error but do not silently bypass the gate.
            # If the credit system is broken, we allow dictation to fail-open
            # so the user is not locked out of basic functionality.
            print(f"[Hotkeys] Credit gate error (allowing dictation): {e}")

    cancel_pending_f9_taps()

    with _start_recording_lock:
        if state.recording:
            print("[Hotkeys] start_recording ignored — already recording")
            return

        now = time.time()
        if now - _last_start_time < _START_DEBOUNCE_SEC:
            print(f"[Hotkeys] start_recording debounced ({now - _last_start_time:.2f}s)")
            return
        _last_start_time = now

    # ═══════════════════════════════════════════════════════════════════════
    #  PRE-RECORDING SETUP — all heavy/slow work BEFORE state.recording = True
    #  so the first 1–2 seconds of speech are never lost to init lag.
    # ═══════════════════════════════════════════════════════════════════════
    try:
        _ensure_audio_stream()
    except Exception as e:
        print(f"[Audio] Failed to open microphone: {e}")
        _try_ws_send("state", "error", "Microphone unavailable")
        return

    # Remember where the user was typing so paste lands on the right screen/field.
    _save_recording_focus()

    # Start the production streaming STT engine for live preview (no auto-stop)
    _active_stt = StreamingSTT()
    _active_stt.start()

    # Clear buffers atomically with the recording flag
    state.audio_frames = []
    _last_stt_text = ""

    # ═══════════════════════════════════════════════════════════════════════
    #  START RECORDING — from this point the audio callback captures frames
    # ═══════════════════════════════════════════════════════════════════════
    state.recording = True

    # Immediate feedback
    print("\n🎙️  RECORDING STARTED — speak now, press F9 to stop")
    print("[Hotkeys] start_recording called")
    _try_ws_send("state", "listening")
    if state.overlay:
        state.overlay.set_listening()
    _start_mic_publisher()


def _stop_recording(process_audio: bool):
    global _audio_stream, _active_stt, _last_stt_text, _last_stop_time

    cancel_pending_f9_taps()

    with _stop_recording_lock:
        if not state.recording:
            return

        now = time.time()
        if now - _last_stop_time < _STOP_DEBOUNCE_SEC:
            print(f"[Hotkeys] _stop_recording debounced ({now - _last_stop_time:.2f}s)")
            return
        _last_stop_time = now
        state.recording = False

    # Keep the microphone stream alive so the next F9 is instant.
    # The callback ignores frames when state.recording is False.

    # Always stop the mic publisher so the pill wave settles.
    _stop_mic_publisher()

    # Stop the streaming STT engine and capture its final text
    stt_text = ""
    if _active_stt is not None:
        stt_text = _active_stt.request_stop()
        _active_stt = None
    if stt_text:
        _last_stt_text = stt_text

    if not process_audio:
        _try_ws_send("state", "idle")
        if state.overlay:
            state.overlay.set_idle()
        return

    print("\n⏹️  RECORDING STOPPED — processing transcription...")
    _try_ws_send("state", "processing")

    # Snapshot frames + streaming text at stop time so a duplicate start_recording()
    # (e.g. from Electron + pynput both handling F9) can't clear them before we process.
    _captured_stt = _last_stt_text
    _captured_frames = list(state.audio_frames)

    def _process():
        time.sleep(0.15)
        transcribe_and_dispatch(captured_stt=_captured_stt, captured_frames=_captured_frames)

    threading.Thread(target=_process, daemon=True).start()


def stop_and_process():
    _stop_recording(process_audio=True)


def cancel_active_recording():
    _stop_recording(process_audio=False)


# =============================================================
#  F9 HANDLER — refined tap counter
#
#  1 tap  → dictation (record / stop+paste)
#  2 taps → toggle Agent mode on / off
#
#  Timer window: 0.4s (balances speed vs. multi-tap detection)
# =============================================================

_TAP_WINDOW = 0.4
_f9_lock = threading.Lock()


def cancel_pending_f9_taps():
    """Cancel any pending F9 tap timer and reset the counter.

    Called when Electron (via WS) handles the same physical key so Python's
    pynput fallback doesn't fire a stale tap window and restart dictation.
    """
    with _f9_lock:
        state._f9_count = 0
        if state._f9_timer is not None:
            state._f9_timer.cancel()
            state._f9_timer = None


def _on_f9_taps(count: int):
    if state.recording:
        # Defence against double-registration race: if recording started
        # very recently (< 0.6 s) this pynput tap is almost certainly a
        # stale echo of the same physical keypress that Electron already
        # handled. Ignore it so we don't stop after 400 ms.
        if count == 1 and time.time() - _last_start_time < 0.6:
            print("[Hotkeys] Ignoring pynput stop — recording started by Electron very recently")
            return
        # Stop any active recording (F9 dictation or F10 task capture).
        # This makes F9 a universal "stop recording" key.
        stop_and_process()
        return

    if count == 1:
        # If an agent task is already running (e.g. from chat panel), treat F9×1
        # as agent voice input rather than plain dictation.
        if getattr(state, "_agent_running", False):
            state.agent_mode = True
        start_recording()
    elif count >= 2:
        # Agent mode coming soon — disabled for now.
        # toggle_agent_mode()
        pass


def f9_handler():
    with _f9_lock:
        state._f9_count += 1

        if state._f9_timer is not None:
            state._f9_timer.cancel()

        def _fire():
            with _f9_lock:
                n = state._f9_count
                state._f9_count = 0
            _on_f9_taps(n)

        state._f9_timer = threading.Timer(_TAP_WINDOW, _fire)
        state._f9_timer.daemon = True
        state._f9_timer.start()


def toggle_chat_overlay():
    try:
        from ui.agent_confirmation_overlay import get_agent_confirmation_overlay
        from ui.react_overlay import toggle_react_overlay as _toggle
        _confirmation_overlay = get_agent_confirmation_overlay()
        if _confirmation_overlay.has_active_confirmation():
            _confirmation_overlay.toggle()
            return
        _toggle()
    except Exception as e:
        print(f"[Hotkeys] toggle_react_overlay error: {e}")


def hide_chat_overlay_if_visible():
    try:
        from ui.react_overlay import hide_react_overlay_if_visible as _hide
        _hide()
    except Exception as e:
        print(f"[Hotkeys] hide_react_overlay error: {e}")


_last_toggle_time = 0.0
_agent_toggle_lock = threading.Lock()


def toggle_agent_mode():
    """Toggle agent_mode on/off. Mirrors the tray menu behavior."""
    global _last_toggle_time
    with _agent_toggle_lock:
        try:
            import core as state
            from core.toast import show_toast
            from core.ws_bridge import send_wave_state, broadcast_sync

            cancel_pending_f9_taps()

            now = time.time()
            if now - _last_toggle_time < 0.6:
                print(f"[Hotkeys] toggle_agent_mode debounced ({now - _last_toggle_time:.2f}s)")
                return
            _last_toggle_time = now
            prev_mode = getattr(state, "agent_mode", False)
            state.agent_mode = not prev_mode
            mode_name = "Agent" if state.agent_mode else "Dictation"
            show_toast(f"{mode_name} mode ready", "Wiztant")
            print(f"[Hotkeys] Mode toggled: {mode_name} (was {'Agent' if prev_mode else 'Dictation'})")

            # Notify overlay so the pill can show the correct visual state
            broadcast_sync({"type": "agent_mode", "enabled": state.agent_mode})
            send_wave_state("agent" if state.agent_mode else "idle")
            print(f"[Hotkeys] Broadcast agent_mode={state.agent_mode} + wave_state={'agent' if state.agent_mode else 'idle'}")
        except Exception as e:
            print(f"[Hotkeys] toggle_agent_mode error: {e}")


# Track the last calendar day we showed the carry-over digest so it only fires once/day.
_TASK_DIGEST_DATE: str = ""


def _maybe_show_carry_over_digest():
    """On first F10 of the day, auto-reschedule yesterday's pending tasks and flash a notice."""
    global _TASK_DIGEST_DATE
    from datetime import date, timedelta
    from core.tasks import get_yesterday_pending_summary, reschedule_to_tomorrow, get_tasks
    from core.ws_bridge import send_pill_notice

    today = date.today().isoformat()
    if _TASK_DIGEST_DATE == today:
        return
    _TASK_DIGEST_DATE = today

    summary = get_yesterday_pending_summary()
    if not summary:
        return

    yesterday = date.today() - timedelta(days=1)
    yday_key = yesterday.isoformat()
    carried = 0
    for t in get_tasks():
        created = str(t.get("created_at") or "")[:10]
        if t.get("status") != "done" and created == yday_key:
            if reschedule_to_tomorrow(t["id"]):
                carried += 1

    if carried:
        send_pill_notice("updated", f"{carried} task(s) carried over", summary, duration_ms=4000)
    else:
        send_pill_notice("updated", "Carry-over done", summary, duration_ms=3000)


def _start_task_recording():
    """F10: Start a voice capture session that will be saved as a task."""
    global _audio_stream

    if state.recording:
        return

    _maybe_show_carry_over_digest()

    try:
        _ensure_audio_stream()
    except Exception as e:
        print(f"[Audio] Failed to open microphone: {e}")
        _try_ws_send("state", "error", "Microphone unavailable")
        return

    state.audio_frames = []
    state._task_recording = True

    # Start recording atomically so no frames are lost during setup
    state.recording = True

    if state.overlay:
        state.overlay.set_listening()

    time.sleep(0.05)
    print("\n🎙️  RECORDING TASK — speak now, press F10 to save")
    # Pass a "task" hint so the overlay can render the Add Task label variant.
    _try_ws_send("state", "listening", "task")
    _start_mic_publisher()


_TASK_JUNK_TOKENS = {
    "", "so", "oh", "uh", "um", "hmm", "hm", "ok", "okay", "yeah", "yes",
    "no", "thanks", "thank", "bye", "hi", "hello", "hey", "what", "huh",
    "wait", "stop", "cancel",
}


def _looks_like_task(text: str) -> bool:
    """Return True if the transcript plausibly represents a task.

    A task needs at least 3 words OR a verb-like token after the Whisper
    artifacts are stripped. One-word fillers ("so", "oh", "thanks") and
    empty strings are always rejected.
    """
    if not text:
        return False
    raw = text.strip().lower().strip(" .,!?:;-")
    if not raw:
        return False
    # Tokenize on whitespace.
    tokens = [t.strip(" .,!?:;-\"'") for t in raw.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    # Single-token filler? Reject.
    if len(tokens) == 1:
        return False
    # Strip leading junk filler tokens, then require ≥ 2 real words left.
    while tokens and tokens[0] in _TASK_JUNK_TOKENS:
        tokens.pop(0)
    if len(tokens) < 2:
        return False
    # Require at least one token with 3+ letters (avoid "so oh").
    if not any(len(t) >= 3 and t.isalpha() for t in tokens):
        return False
    return True


# Common Whisper hallucinations and junk utterances that should never be pasted.
_DICTATION_JUNK_PHRASES = {
    "thank you",
    "thanks",
    "thank",
    "thanks for watching",
    "subtitles by",
    "subtitle by",
    "closed caption",
    "please subscribe",
    "like and subscribe",
    "subscribe now",
    "goodbye",
    "bye",
    "umm",
    "uhh",
    "hmm",
    "mm hmm",
    "mhm",
}


def _is_dictation_junk(text: str) -> bool:
    """Return True if the transcript is an obvious Whisper hallucination or filler.

    Dictation is more lenient than task capture — short real words are allowed.
    We only reject empty strings, exact hallucination phrases, and lone
    single-token fillers.
    """
    if not text or not text.strip():
        return True
    normalized = text.strip().lower().strip(" .,!?:;-")
    if not normalized:
        return True
    # Exact phrase match for known hallucinations.
    if normalized in _DICTATION_JUNK_PHRASES:
        return True
    # Single filler word with no surrounding context.
    tokens = [t.strip(" .,!?:;-\"'") for t in normalized.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return True
    if len(tokens) == 1 and tokens[0] in _TASK_JUNK_TOKENS:
        return True
    return False


def _task_transcribe_and_save():
    """Transcribe the F10 recording and save it as a task via the shared pipeline."""
    from core.tasks import parse_due_time, default_noon_due_at, refine_task_text, split_separately

    if not state.audio_frames:
        print("[Audio] No frames captured.")
        _try_ws_send("state", "error", "No audio captured")
        if state.overlay:
            state.overlay.set_idle()
        return

    audio_np = np.concatenate(state.audio_frames).astype(np.float32)
    peak = float(np.max(np.abs(audio_np)))
    if peak < state.SILENCE_THRESHOLD:
        print("[Audio] Too quiet, skipping.")
        _try_ws_send("state", "error", "Audio too quiet")
        if state.overlay:
            state.overlay.set_idle()
        return

    audio_np /= peak + 1e-6
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    sf.write(tmp_wav, audio_np, 16000)

    _try_ws_send("state", "processing")
    text = transcribe_wav(tmp_wav)
    try:
        os.remove(tmp_wav)
    except Exception:
        pass

    if not text or not text.strip():
        print("[Whisper] No speech detected.")
        _try_ws_send("state", "error", "No speech detected")
        if state.overlay:
            state.overlay.set_idle()
        return

    print(f"[Task] Captured: {text}")

    # If the user explicitly said "separately" (or "as separate tasks"), split
    # the utterance into multiple tasks and save each one independently. Each
    # fragment gets its own due-time parse + refinement. Without that marker,
    # the entire utterance stays as a single task (existing behavior).
    fragments = split_separately(text.strip())
    if fragments:
        print(f"[Task] 'separately' detected — splitting into {len(fragments)} tasks")
        saved_any = False
        for fragment in fragments:
            frag_cleaned, frag_due = parse_due_time(fragment)
            if not _looks_like_task(frag_cleaned):
                print(f"[Task] Skipping fragment (not a task): {frag_cleaned!r}")
                continue
            frag_refined = refine_task_text(frag_cleaned) or frag_cleaned
            if not frag_due:
                frag_due = default_noon_due_at()
            try:
                _propose_task_for_confirmation(frag_refined, frag_due, text)
                _add_dictation_memory(text, frag_refined, mode="task")
                saved_any = True
            except Exception as e:
                print(f"[Task] Save failed for fragment {frag_refined!r}: {e}")
        if not saved_any:
            from core.ws_bridge import send_pill_notice
            send_pill_notice("error", "Not a task", text[:60])
        _try_ws_send("state", "idle")
        if state.overlay:
            state.overlay.set_idle()
        return

    cleaned, due_at = parse_due_time(text.strip())

    # Validate that this actually looks like a task before saving.
    # Heuristic: need ≥ 3 words and at least one non-filler alphabetic token.
    # If it's one-word junk (Whisper artifacts like "so", "oh", "thanks"),
    # flash a red pill notice and decline — never save.
    if not _looks_like_task(cleaned):
        print(f"[Task] Declined (not a task): {cleaned!r}")
        from core.ws_bridge import send_pill_notice
        send_pill_notice(
            "error",
            "Not a task",
            cleaned[:60] if cleaned else "Nothing captured",
        )
        _try_ws_send("state", "idle")
        if state.overlay:
            state.overlay.set_idle()
        return

    refined = refine_task_text(cleaned) or cleaned
    if not due_at:
        due_at = default_noon_due_at()

    try:
        _propose_task_for_confirmation(refined, due_at, text)
        _add_dictation_memory(text, refined, mode="task")
    except Exception as e:
        print(f"[Task] Save failed: {e}")

    _try_ws_send("state", "idle")
    if state.overlay:
        state.overlay.set_idle()


def task_hotkey_handler():
    """F10 (or user-configured key): toggle a task-capture voice recording."""
    # If an F10 task recording is already in progress, treat as stop+save.
    if state.recording and getattr(state, "_task_recording", False):
        stop_and_process()
        return
    # If an F9 dictation is in progress, treat F10 as "stop dictation"
    # instead of starting a conflicting task recording.
    if state.recording:
        stop_and_process()
        return
    _start_task_recording()


def flag_wrong_word():
    """Ctrl+Shift+V — flag the last dictated word as wrong and open vocab correction in overlay."""
    text = _last_pasted_text[0]
    if not text:
        print("[Vocab] No recent dictation to flag")
        return
    # Extract last word as the suspect
    words = text.strip().split()
    heard = words[-1] if words else text
    context_before = " ".join(words[:-1]) if len(words) > 1 else ""
    from core.ws_bridge import send_vocab_correct
    send_vocab_correct(heard, context_before=context_before, context_after="")
    print(f"[Vocab] Flagged: {heard}")


def _capture_active_field_text() -> str:
    """Select all text in the active input field and cut it to clipboard. Returns the cut text."""
    from platforms.factory import get_system_access
    system = get_system_access()
    # Clear clipboard first to guarantee we never read stale content
    pyperclip.copy("")
    ok, _ = system.hotkey("ctrl", "a")
    if not ok:
        raise RuntimeError("Failed to send Ctrl+A")
    time.sleep(0.05)
    ok, _ = system.hotkey("ctrl", "x")
    if not ok:
        raise RuntimeError("Failed to send Ctrl+X")
    time.sleep(0.05)
    return pyperclip.paste() or ""


def optimize_clipboard_prompt():
    """Ctrl+Shift+Space — capture text from active field, open Reprompt tab, optimize, copy result."""
    # Step 1: Capture text from active input field
    try:
        text = _capture_active_field_text()
    except Exception as e:
        print(f"[Hotkeys] Failed to capture active field text: {e}")
        from core.ws_bridge import send_pill_notice
        send_pill_notice("error", "Capture failed", "Could not select and cut text from active field.", duration_ms=3000)
        return

    if not text or not text.strip():
        from core.ws_bridge import send_pill_notice
        send_pill_notice("error", "No text captured", "Active field appears empty.", duration_ms=3000)
        return

    # Step 2: Open overlay and navigate to Reprompt tab
    try:
        from ui.react_overlay import show_react_overlay
        show_react_overlay()
    except Exception as e:
        print(f"[Hotkeys] Failed to show overlay: {e}")

    from core.ws_bridge import broadcast_sync, get_reprompt_ready_event
    broadcast_sync({
        "type": "reprompt_init",
        "text": text,
    })

    # Step 3: Wait for overlay ready confirmation, then optimize
    def _run():
        import asyncio
        from core.wizprompt import optimize_prompt_with_dynamic_agents
        from core.ws_bridge import broadcast_sync, send_pill_notice

        ready_event = get_reprompt_ready_event()
        ready = ready_event.wait(timeout=3.0)
        if not ready:
            print("[Hotkeys] Overlay ready timeout — proceeding with optimization anyway")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(optimize_prompt_with_dynamic_agents(text))
            optimized = result.get("optimized_prompt", "")
            if optimized:
                # Step 4: Copy result to clipboard
                pyperclip.copy(optimized)
                broadcast_sync({
                    "type": "wizprompt_result",
                    "optimized": optimized,
                    "original": text,
                    "agent_count": result.get("agent_count", 0),
                    "emotion": result.get("emotional_state"),
                    "prompt_size": result.get("prompt_size"),
                    "line_count": result.get("line_count", 0),
                    "framing_directive": result.get("framing_directive"),
                    "synthesis_failed": result.get("synthesis_failed", False),
                    "critiques": result.get("critiques", {}),
                    "examples_used": result.get("examples_used", 0),
                    "example_ids": result.get("example_ids", []),
                })
                # Store in few-shot memory (background, no feedback yet)
                def _store():
                    try:
                        import core.wizprompt_memory as mem
                        sloop = asyncio.new_event_loop()
                        asyncio.set_event_loop(sloop)
                        sloop.run_until_complete(
                            mem.remember_optimization(
                                original_prompt=text,
                                optimized_prompt=optimized,
                                final_prompt=optimized,
                                preset=result.get("preset_used"),
                                model=result.get("model_used"),
                                emotion=result.get("emotional_state"),
                            )
                        )
                        sloop.close()
                    except Exception as se:
                        print(f"[Hotkeys] background store error: {se}")
                threading.Thread(target=_store, daemon=True).start()

                # Store in the visible memory stack
                try:
                    _add_dictation_memory(
                        original_text=text,
                        final_text=optimized,
                        mode="reprompt",
                    )
                except Exception:
                    pass
                send_pill_notice(
                    "updated",
                    "Prompt optimized",
                    f"Copied to clipboard • {result.get('agent_count', 0)} agents used",
                    duration_ms=3000,
                )
            else:
                send_pill_notice("error", "Optimization failed", "Synthesis returned empty.", duration_ms=3000)
        except Exception as e:
            send_pill_notice("error", "Optimization failed", str(e)[:60], duration_ms=3000)
        finally:
            loop.close()

    threading.Thread(target=_run, daemon=True).start()


def register_hotkeys():
    """Register global hotkeys via the Python keyboard library.

    This function is the Windows-side implementation.
    Linux uses core/linux/hotkeys.py (Electron + pynput fallback).
    """
    hotkeys_to_register = [
        ("f9", f9_handler, True),
        ("ctrl+space", toggle_chat_overlay, False),
        ("ctrl+shift+space", optimize_clipboard_prompt, False),
        ("escape", hide_chat_overlay_if_visible, False),
        ("ctrl+shift+v", flag_wrong_word, False),
    ]

    kb = _keyboard()
    if not kb:
        print("[Hotkeys] keyboard library unavailable — skipping Python-side hotkey registration")
        return

    registered = 0
    for key, handler, suppress in hotkeys_to_register:
        try:
            kb.add_hotkey(key, handler, suppress=suppress)
            registered += 1
        except Exception as e:
            print(f"[Hotkeys] Failed to register '{key}': {e}")

    # Task-creation hotkey (remappable via data/settings.json → "task_hotkey").
    task_mode = _load_task_creation_mode()
    shortcuts_enabled = _load_shortcuts_enabled()
    if task_mode == "hotkey" or shortcuts_enabled:
        task_key = _load_task_hotkey()
        try:
            kb.add_hotkey(task_key, task_hotkey_handler)
            registered += 1
            print(f"[Hotkeys] Task hotkey registered: {task_key.upper()}")
        except Exception as e:
            print(f"[Hotkeys] Failed to register task hotkey '{task_key}': {e}. Falling back to F10.")
            try:
                kb.add_hotkey("f10", task_hotkey_handler)
                registered += 1
            except Exception as e2:
                print(f"[Hotkeys] F10 fallback also failed: {e2}")
    else:
        print("[Hotkeys] Task creation mode = smart — task hotkey disabled")
    
    if registered > 0:
        print(f"[Hotkeys] {registered} hotkey(s) registered successfully")
    else:
        print("[Hotkeys] WARNING: No hotkeys registered - app may have limited functionality")
