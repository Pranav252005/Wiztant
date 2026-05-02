"""
Deprecated TTS module. All functions are no-ops maintained for backward compatibility.
"""

from typing import Dict

def speak(text: str, voice: str | None = None, blocking: bool = False) -> None:
    return

def stop_speaking() -> None:
    return

def get_voices() -> Dict[str, dict]:
    return {}

def set_voice(voice_id: str) -> bool:
    return True

def set_speed(speed: float) -> None:
    return
