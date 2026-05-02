"""platforms/windows/tts.py — Windows TTS implementing BaseTTS."""
from __future__ import annotations

from typing import Dict

from platforms.abstract import BaseTTS


class WindowsTTS(BaseTTS):
    """Windows TTS via Kokoro (cross-platform engine)."""

    def speak(self, text: str, voice: str | None = None, blocking: bool = False) -> None:
        """Speak text via Kokoro (local neural TTS)."""
        try:
            from core.voice import _speak_kokoro
            _speak_kokoro(text, voice=voice, blocking=blocking)
        except Exception as e:
            print(f"[TTS/Windows] Kokoro failed: {e}")

    def stop(self) -> None:
        try:
            from core.voice import _stop_kokoro
            _stop_kokoro()
        except Exception:
            pass

    def is_speaking(self) -> bool:
        return False

    # ── Legacy compatibility ──────────────────────────────────────────────────

    def get_voices(self) -> Dict[str, dict]:
        return {}

    def set_voice(self, voice_id: str) -> bool:
        return True

    def set_speed(self, speed: float) -> None:
        pass

    def play_audio_file(self, filepath: str) -> None:
        """Play an audio file on Windows."""
        import subprocess
        try:
            subprocess.run(["powershell", "-c", f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"], timeout=30, check=True)
        except Exception as e:
            print(f"[TTS/Windows] Audio playback failed: {e}")
