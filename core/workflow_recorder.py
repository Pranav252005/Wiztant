"""
core/workflow_recorder.py — Stub. Workflow recording is not yet implemented.
"""
from __future__ import annotations


class _Recorder:
    is_recording = False

    def start_recording(self):
        pass

    def stop_recording(self, skill_name: str = "", description: str = "") -> dict | None:
        return None


class SkillStore:
    def list_all(self) -> list:
        return []

    def get(self, name: str) -> dict | None:
        return None


_recorder = _Recorder()


def get_recorder() -> _Recorder:
    return _recorder
