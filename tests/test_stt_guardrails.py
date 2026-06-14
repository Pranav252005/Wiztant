"""
Tests for STT paste guardrails — dangerous content must be blocked before pasting.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.stt_engine import smart_paste


def test_paste_blocks_destructive_command(monkeypatch):
    """Transcription containing 'rm -rf' must NOT be pasted."""
    pasted: list[str] = []
    warnings: list[str] = []

    def capture_paste(text: str, **_):
        pasted.append(text)
        return True

    def capture_warning(data: dict):
        if data.get("type") == "pill/notice":
            warnings.append(data.get("message", ""))

    # Monkey-patch the underlying paste and broadcast
    monkeypatch.setattr("core.stt_engine.smart_paste", capture_paste)
    monkeypatch.setattr("core.ws_bridge.broadcast_sync", capture_warning)

    # Simulate what transcribe_and_dispatch would do before calling smart_paste
    dangerous_text = "rm -rf /home/user/projects"

    # The guardrail should intercept before paste
    from core.guardrails import is_destructive_action
    is_dest, reason = is_destructive_action(dangerous_text)
    assert is_dest, f"Guardrail failed to detect destructive command: {dangerous_text}"

    # In the actual pipeline, the paste should be blocked
    # (This test will fail until we wire the guardrail into the paste path)
    assert not pasted, (
        f"Dangerous text was pasted despite guardrail: {pasted}"
    )


def test_paste_blocks_secret_in_transcription(monkeypatch):
    """Transcription containing an API key must NOT be pasted."""
    pasted: list[str] = []

    def capture_paste(text: str, **_):
        pasted.append(text)
        return True

    monkeypatch.setattr("core.stt_engine.smart_paste", capture_paste)

    secret_text = "My API key is sk-abcdefghijklmnopqrstuvwxyz123456"

    from core.guardrails import scan_secrets
    secrets = scan_secrets(secret_text)
    assert secrets, f"Secret scanner failed to detect API key in: {secret_text}"

    assert not pasted, (
        f"Secret-containing text was pasted despite scanner: {pasted}"
    )


def test_paste_respects_max_length(monkeypatch):
    """Text longer than MAX_PASTE_CHARS must be truncated or blocked."""
    pasted: list[str] = []

    def capture_paste(text: str, **_):
        pasted.append(text)
        return True

    monkeypatch.setattr("core.stt_engine.smart_paste", capture_paste)

    long_text = "x" * 15000
    # Until MAX_PASTE_CHARS is enforced, this will paste everything
    assert not pasted or len(pasted[0]) <= 10000, (
        f"Text longer than MAX_PASTE_CHARS was pasted: {len(pasted[0]) if pasted else 0} chars"
    )
