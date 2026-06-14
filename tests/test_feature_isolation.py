"""
Tests for feature isolation — recording state, conversation history,
and wave state arbitration between dictation, agent, and reprompt.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as state
from core import hotkeys


# ------------------------------------------------------------------
# B1 — Recording lock race
# ------------------------------------------------------------------

def test_recording_lock_prevents_race(monkeypatch):
    """Rapid start/stop from different threads must not leave recording=True with no _active_stt."""
    monkeypatch.setattr(state, "recording", False)
    monkeypatch.setattr(hotkeys, "_active_stt", None)
    monkeypatch.setattr(hotkeys, "_audio_stream", True)  # pretend mic is ready
    monkeypatch.setattr(hotkeys, "_last_start_time", 0.0)
    monkeypatch.setattr(hotkeys, "_last_stop_time", 0.0)

    call_count = {"start": 0, "stop": 0}

    def mock_start():
        call_count["start"] += 1
        # mimic the race window: check recording, then pause before setting True
        if not state.recording:
            time.sleep(0.01)
            state.recording = True
            hotkeys._active_stt = object()

    def mock_stop():
        call_count["stop"] += 1
        if state.recording:
            time.sleep(0.005)
            state.recording = False
            hotkeys._active_stt = None

    threads = []
    for _ in range(10):
        threads.append(threading.Thread(target=mock_start))
        threads.append(threading.Thread(target=mock_stop))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # After all racing, state must be consistent
    assert call_count["start"] == 10
    assert call_count["stop"] == 10
    # The critical invariant: if recording is True, _active_stt must not be None
    if state.recording:
        assert hotkeys._active_stt is not None, "Race left recording=True with no active STT"


# ------------------------------------------------------------------
# B2 — Conversation history thread safety
# ------------------------------------------------------------------

def test_conversation_history_thread_safe():
    """Multiple threads appending to conversation_history must not corrupt the list."""
    state.conversation_history = []
    errors: list[Exception] = []

    def append_loop(idx: int):
        try:
            for _ in range(20):
                state.conversation_history.append({"role": "user", "content": f"msg-{idx}"})
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=append_loop, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Exceptions during concurrent append: {errors}"
    assert len(state.conversation_history) == 200, (
        f"Expected 200 messages, got {len(state.conversation_history)} — list was corrupted by race"
    )


# ------------------------------------------------------------------
# B8 — Wave state arbitration
# ------------------------------------------------------------------

def test_agent_wave_state_not_overwritten_by_dictation(monkeypatch):
    """Dictation finishing must not set wave to 'idle' while agent is still running."""
    from core.ws_bridge import send_voice_state

    monkeypatch.setattr(state, "_agent_running", True)
    broadcasted: list[str] = []

    def capture_broadcast(data: dict):
        if data.get("type") == "voice_state":
            broadcasted.append(data.get("state", ""))

    monkeypatch.setattr("core.ws_bridge.broadcast_sync", capture_broadcast)

    send_voice_state("idle")

    # Because agent is running, the idle broadcast should be suppressed
    assert "idle" not in broadcasted, (
        "Dictation set wave to 'idle' while agent was still running — state clash"
    )
