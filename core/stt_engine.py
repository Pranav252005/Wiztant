"""
core/stt_engine.py — Production-grade streaming STT pipeline for Wiztant dictation.

Features:
  • Chunked streaming transcription (re-transcribe accumulated audio every ~1.5s)
  • Rolling-context prompt (last 150 tokens of prior transcript → Groq prompt)
  • Energy-based VAD auto-stop (silence > 1.5s triggers stop)
  • Smart paste via direct type-injection (clipboard fallback)
  • Live interim transcript broadcast to overlay
  • Context-aware LLM polish (last 3 utterances as style context)

Usage (from hotkeys.py):
    from core.stt_engine import StreamingSTT
    stt = StreamingSTT()
    stt.start()
    ... audio frames accumulate ...
    stt.stop()  # returns final transcript
"""

from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

import core as state
from core.ws_bridge import send_voice_state, send_mic_level, broadcast_sync

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

CHUNK_SEC = 1.5           # Seconds between interim transcription requests
SILENCE_SEC = 1.5         # Seconds of silence before auto-stop
MAX_RECORD_SEC = 999999   # Effectively unlimited
PROMPT_MAX_TOKENS = 150   # Approximate token budget for Groq prompt param
INTERIM_JITTER_SEC = 0.2  # Minimum time between identical interim broadcasts

# ═══════════════════════════════════════════════════════════════════════════════
#  ROLLING CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

_last_final_texts: deque[str] = deque(maxlen=10)
_last_prompt: str = ""
_lock = threading.Lock()


def _update_context(final_text: str) -> None:
    """Append a final transcript to the rolling context window."""
    with _lock:
        if final_text and final_text not in _last_final_texts:
            _last_final_texts.append(final_text)
        _rebuild_prompt()


def _rebuild_prompt() -> None:
    """Build a prompt string from the last N utterances + Tune keywords, capped at ~PROMPT_MAX_TOKENS."""
    global _last_prompt
    parts = []
    total_len = 0

    # Inject Tune keywords first (highest priority for recognition)
    try:
        from core.tune import get_tune_keywords
        keywords = get_tune_keywords()
        if keywords:
            kw_text = "Recognize: " + ", ".join(keywords)
            est = len(kw_text) // 4 + 1
            if est <= PROMPT_MAX_TOKENS:
                parts.append(kw_text)
                total_len += est
    except Exception:
        pass

    for txt in reversed(_last_final_texts):
        # Rough token estimate: 1 token ≈ 4 chars for English
        est = len(txt) // 4 + 1
        if total_len + est > PROMPT_MAX_TOKENS:
            break
        parts.insert(0, txt)
        total_len += est
    _last_prompt = " ".join(parts)


def get_rolling_prompt() -> str:
    """Return the current rolling prompt for Groq Whisper API."""
    with _lock:
        return _last_prompt


def clear_rolling_context() -> None:
    """Clear the rolling prompt (e.g. on mode switch or explicit reset)."""
    global _last_prompt
    with _lock:
        _last_final_texts.clear()
        _last_prompt = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  CONTEXT-AWARE LLM POLISH
# ═══════════════════════════════════════════════════════════════════════════════

def _contextual_llm_polish(text: str) -> str:
    """Polish transcript with recent utterances as style context."""
    try:
        from core.agent import call_llm
        from core.voice import _llm_polish

        with _lock:
            context = list(_last_final_texts)[-3:]

        ctx_block = ""
        if context:
            ctx_block = (
                "Recent user utterances (match style, capitalization, and spelling):\n"
                + "\n".join(f"- {c}" for c in context)
                + "\n\n"
            )

        result = call_llm(
            messages=[{
                "role": "user",
                "content": (
                    f"{ctx_block}"
                    "Fix ONLY spelling, punctuation, and proper noun capitalisation "
                    "in this voice transcript. Do NOT rephrase or change meaning. "
                    "Match the style and spelling conventions of the recent utterances above. "
                    f"Return ONLY the corrected text.\n\nTranscript: {text}"
                )
            }],
            max_tokens=300
        )
        result = result.strip()
        if abs(len(result) - len(text)) > len(text) * 0.4:
            return text
        return result
    except Exception as e:
        print(f"[Polish] Skipped: {e}")
        return text


# ═══════════════════════════════════════════════════════════════════════════════
#  SMART PASTE
# ═══════════════════════════════════════════════════════════════════════════════

def smart_paste(text: str, window_id: Optional[str] = None) -> bool:
    """
    Paste text into the active window.

    Strategy:
      1. Windows: type_text (pyautogui) first — rock-solid.
      2. Linux: clipboard + Ctrl+V first — xdotool/wtype are more reliable
         than pynput which may silently fail on Wayland.
      3. Fallback across platforms when primary method fails.

    Args:
        text: The text to paste.
        window_id: If provided on Linux, xdotool sends the key directly
                   to this window via --window, bypassing focus issues.
    """
    import shutil

    def _linux_clip_copy(t: str) -> bool:
        enc = t.encode("utf-8")
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard", "-in"],
            ["xsel", "-b", "-i"],
        ):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=enc, timeout=3, check=True)
                    return True
                except Exception:
                    pass
        return False

    if not text:
        return False

    if sys.platform == "win32":
        # Windows: direct type injection is reliable
        if len(text) < 800:
            try:
                from core.platform_backends import type_text
                ok, msg = type_text(text, interval=0.005)
                if ok:
                    print(f"[Paste] Typed: {msg}")
                    return True
            except Exception as e:
                print(f"[Paste] type_text failed: {e}")

    # Universal: clipboard + simulate Ctrl+V
    try:
        import pyperclip
        pyperclip.copy(text)
        print("[Paste] Copied to clipboard")
    except Exception as e:
        print(f"[Paste] pyperclip copy failed: {e}")
        if sys.platform == "win32":
            print("[Paste] All clipboard methods failed on Windows")
            return False
        if not _linux_clip_copy(text):
            print("[Paste] All clipboard methods failed")
            return False

    clipboard_delay = 0.5 if sys.platform != "win32" else 0.2
    time.sleep(clipboard_delay)

    def _safe_keyboard_paste() -> bool:
        """keyboard library with explicit safety releases."""
        try:
            import keyboard as _kb
            _kb.press("ctrl")
            _kb.press("v")
            time.sleep(0.05)
            _kb.release("v")
            _kb.release("ctrl")
            time.sleep(0.05)
            try:
                _kb.release("v")
            except Exception:
                pass
            try:
                _kb.release("ctrl")
            except Exception:
                pass
            print("[Paste] keyboard library ctrl+v succeeded")
            return True
        except Exception as e:
            print(f"[Paste] keyboard library failed: {e}")
            return False

    # Detect Wayland so we paste from the same clipboard backend we copied to.
    _is_wayland = (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )

    # Cache whether wtype is known-broken on this compositor.
    _wtype_broken = False

    # ═════════════════════════════════════════════════════════════════════════
    #  WAYLAND: keyboard library FIRST — it's the only method that reliably
    #  injects into native Wayland windows (evdev bypass). xdotool without
    #  --window returns exit 0 but does NOTHING on native Wayland, so we must
    #  not trust it as a primary method.
    # ═════════════════════════════════════════════════════════════════════════
    if _is_wayland:
        if _safe_keyboard_paste():
            return True

        if window_id and shutil.which("xdotool"):
            try:
                subprocess.run(
                    ["xdotool", "key", "--window", window_id, "ctrl+v"],
                    timeout=2,
                    check=True,
                )
                print(f"[Paste] xdotool --window {window_id} ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] xdotool --window failed: {e}")

        if shutil.which("dotool"):
            try:
                subprocess.run(
                    ["dotool"],
                    input="key ctrl+v\n",
                    text=True,
                    timeout=2,
                    check=True,
                )
                print("[Paste] dotool ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] dotool failed: {e}")

        if shutil.which("ydotool"):
            try:
                subprocess.run(["ydotool", "key", "ctrl+v"], timeout=2, check=True)
                print("[Paste] ydotool ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] ydotool failed: {e}")

        if shutil.which("wtype") and not _wtype_broken:
            try:
                result = subprocess.run(
                    ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                print("[Paste] wtype ctrl+v succeeded")
                return True
            except subprocess.CalledProcessError as e:
                err = (e.stderr or "").lower()
                if "compositor does not support" in err or "virtual keyboard" in err:
                    print("[Paste] wtype unsupported by compositor — skipping future attempts")
                    _wtype_broken = True
                else:
                    print(f"[Paste] wtype failed: {e}")
            except Exception as e:
                print(f"[Paste] wtype failed: {e}")

        # DO NOT use plain xdotool on Wayland — false positive (returns 0,
        # does nothing for native Wayland windows).

    # ═════════════════════════════════════════════════════════════════════════
    #  X11: xdotool is rock-solid. keyboard library as fallback.
    # ═════════════════════════════════════════════════════════════════════════
    else:
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "key", "ctrl+v"], timeout=2, check=True)
                print("[Paste] xdotool ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] xdotool failed: {e}")

        if shutil.which("dotool"):
            try:
                subprocess.run(
                    ["dotool"],
                    input="key ctrl+v\n",
                    text=True,
                    timeout=2,
                    check=True,
                )
                print("[Paste] dotool ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] dotool failed: {e}")

        if shutil.which("ydotool"):
            try:
                subprocess.run(["ydotool", "key", "ctrl+v"], timeout=2, check=True)
                print("[Paste] ydotool ctrl+v succeeded")
                return True
            except Exception as e:
                print(f"[Paste] ydotool failed: {e}")

        if _safe_keyboard_paste():
            return True

    # Final fallback: use the cached platform system access instead of
    # creating a fresh pynput Controller (which re-triggers accessibility
    # approval dialogs every single time).
    try:
        from platforms.factory import get_system_access
        system = get_system_access()
        ok, _ = system.hotkey("ctrl", "v")
        if ok:
            print("[Paste] system access hotkey succeeded")
            return True
    except Exception as e:
        print(f"[Paste] system access hotkey failed: {e}")

    # Final fallback: direct type injection (Linux only)
    if sys.platform != "win32":
        try:
            from core.platform_backends import type_text
            ok, msg = type_text(text, interval=0.005)
            if ok:
                print(f"[Paste] type_text fallback succeeded: {msg}")
                return True
        except Exception as e:
            print(f"[Paste] type_text fallback failed: {e}")

    print("[Paste] All paste methods exhausted — text is on clipboard")
    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIO HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _frames_to_wav_bytes(frames: list[np.ndarray], sample_rate: int = 16000) -> bytes:
    """Convert a list of int16 numpy arrays to in-memory WAV bytes."""
    if not frames:
        return b""
    audio_np = np.concatenate(frames).astype(np.float32)
    peak = float(np.max(np.abs(audio_np))) or 1.0
    if peak > 1.0:
        audio_np /= peak
    buf = io.BytesIO()
    sf.write(buf, audio_np, sample_rate, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def _energy_is_speech(level: float, threshold: float = 300.0) -> bool:
    """Simple energy-based speech detection."""
    return level > threshold


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAMING STT
# ═══════════════════════════════════════════════════════════════════════════════

class StreamingSTT:
    """
    Handles live dictation with chunked transcription, VAD auto-stop,
    rolling prompt context, and smart paste.
    """

    def __init__(
        self,
        chunk_sec: float = CHUNK_SEC,
        silence_sec: float = SILENCE_SEC,
        max_sec: float = MAX_RECORD_SEC,
        on_auto_stop: Optional[callable] = None,
    ):
        self.chunk_sec = chunk_sec
        self.silence_sec = silence_sec
        self.max_sec = max_sec
        self.on_auto_stop = on_auto_stop

        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stop_event = threading.Event()
        self._final_text: str = ""

        self._silence_start: Optional[float] = None
        self._vad_thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin streaming STT session."""
        with self._lock:
            self._frames = []
            self._recording = True
            self._stop_event.clear()
            self._final_text = ""
            self._silence_start = None
            self._start_time = time.time()

        self._vad_thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._vad_thread.start()

        send_voice_state("listening")
        print("[STT] Streaming started")

    def append_frame(self, frame: np.ndarray) -> None:
        """Call this from the audio callback for every new frame."""
        with self._lock:
            if self._recording:
                self._frames.append(frame.copy())

    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def request_stop(self) -> str:
        """Signal stop and return the final polished transcript."""
        with self._lock:
            if not self._recording:
                return self._final_text
            self._recording = False

        self._stop_event.set()
        # Don't join our own threads — the caller (hotkeys) handles mic teardown
        # and threads are daemons anyway. Joining from within a callback deadlocks.
        return self._finalize()

    # ── Internal loops ───────────────────────────────────────────────────────

    def _vad_loop(self) -> None:
        """Monitor audio_level from core state and auto-stop ONLY on max duration."""
        while not self._stop_event.is_set():
            time.sleep(0.15)
            elapsed = time.time() - self._start_time
            if elapsed > self.max_sec:
                print("[STT] Max duration reached — auto-stopping")
                self._auto_stop()
                return

    def _auto_stop(self) -> None:
        """Called by VAD loop to trigger a graceful stop."""
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        self._stop_event.set()
        send_voice_state("processing")
        # Finalize so the transcript is captured and returned on next request_stop()
        self._finalize()
        if self.on_auto_stop:
            try:
                self.on_auto_stop()
            except Exception as e:
                print(f"[STT] auto-stop callback error: {e}")

    # ── Transcription ──────────────────────────────────────────────────────────

    def _snapshot_frames(self) -> list[np.ndarray]:
        with self._lock:
            return list(self._frames)

    def _transcribe_chunk(self, frames: list[np.ndarray], final: bool = False) -> str:
        """Send accumulated audio to Whisper and return raw or cleaned text."""
        from core.voice import clean_transcript, WHISPER_PROVIDER, GROQ_API_KEY

        audio_bytes = _frames_to_wav_bytes(frames)
        if not audio_bytes:
            return ""

        prompt = get_rolling_prompt() if not final else ""

        if WHISPER_PROVIDER == "groq" and GROQ_API_KEY:
            try:
                text = _transcribe_groq_with_prompt(audio_bytes, prompt)
            except Exception as e:
                print(f"[STT] Groq interim failed: {e}")
                text = ""
        else:
            text = ""

        # For interim results we skip heavy post-processing (no LLM polish)
        if final and text:
            text = clean_transcript(text)
            if getattr(state, "USE_LLM_POLISH", False):
                text = _contextual_llm_polish(text)
            _update_context(text)
        elif text:
            # Light cleaning only for interim (fast)
            text = _light_clean(text)

        return text

    def _finalize(self) -> str:
        """Perform final transcription with full audio and all correction layers."""
        frames = self._snapshot_frames()
        if not frames:
            return ""

        send_voice_state("processing")
        text = self._transcribe_chunk(frames, final=True)
        self._final_text = text
        return text


# ═══════════════════════════════════════════════════════════════════════════════
#  LIGHT CLEAN (kept for backwards compat — no longer used for interim results)
# ═══════════════════════════════════════════════════════════════════════════════

_LIGHT_REPLACEMENTS = [
    (re.compile(r"\bi\b"), "I"),
    (re.compile(r"\bi'm\b"), "I'm"),
    (re.compile(r"\bi'll\b"), "I'll"),
    (re.compile(r"\bi've\b"), "I've"),
    (re.compile(r"\bdont\b"), "don't"),
    (re.compile(r"\bwont\b"), "won't"),
    (re.compile(r"\bcant\b"), "can't"),
    (re.compile(r"\bthats\b"), "that's"),
]


def _light_clean(text: str) -> str:
    """Fast regex-only cleanup for interim previews."""
    if not text:
        return text
    for pattern, repl in _LIGHT_REPLACEMENTS:
        text = pattern.sub(repl, text)
    # Capitalize first char
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


# ═══════════════════════════════════════════════════════════════════════════════
#  GROQ TRANSCRIPTION WITH PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def _transcribe_groq_with_prompt(audio_bytes: bytes, prompt: str) -> str:
    """Groq transcription with optional rolling-context prompt."""
    from core.voice import _get_groq_client, WHISPER_MODEL

    client = _get_groq_client()
    if client is None:
        raise RuntimeError("Groq API key not configured")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.close()

        with open(tmp.name, "rb") as _f:
            kwargs = {
                "file": ("audio.wav", _f.read()),
                "model": WHISPER_MODEL,
                "response_format": "text",
                "language": "en",
                "temperature": 0.0,
            }
            if prompt:
                # Groq prompt max ~224 tokens; we cap at 1200 chars to be safe
                kwargs["prompt"] = prompt[:1200]

            transcription = client.audio.transcriptions.create(**kwargs)
        return transcription.text.strip() if hasattr(transcription, "text") else transcription.strip()
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKWARDS COMPAT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

_current_stt: Optional[StreamingSTT] = None


def get_active_stt() -> Optional[StreamingSTT]:
    return _current_stt


def start_streaming_stt() -> StreamingSTT:
    """Global helper used by hotkeys.py to start a streaming session."""
    global _current_stt
    _current_stt = StreamingSTT()
    _current_stt.start()
    return _current_stt


def stop_streaming_stt() -> str:
    """Global helper used by hotkeys.py to stop and return final text."""
    global _current_stt
    if _current_stt is None:
        return ""
    text = _current_stt.request_stop()
    _current_stt = None
    return text
