"""platforms/linux/tts.py — Linux TTS implementing BaseTTS."""
from __future__ import annotations

import subprocess
from typing import Dict

from platforms.abstract import BaseTTS


class LinuxTTS(BaseTTS):
    """Linux TTS via Kokoro (cross-platform engine) with PulseAudio/ALSA playback."""

    def speak(self, text: str, voice: str | None = None, blocking: bool = False) -> None:
        """Speak text via Kokoro (local neural TTS)."""
        try:
            from core.voice import _speak_kokoro
            _speak_kokoro(text, voice=voice, blocking=blocking)
        except Exception as e:
            print(f"[TTS/Linux] Kokoro failed: {e}")

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
        """Play an audio file using PulseAudio or ALSA."""
        try:
            subprocess.run(["paplay", filepath], timeout=30, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                subprocess.run(["aplay", filepath], timeout=30, check=True)
            except Exception as e:
                print(f"[TTS/Linux] No audio playback available: {e}")
