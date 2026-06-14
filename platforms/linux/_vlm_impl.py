"""platforms/linux/_vlm_impl.py — DEPRECATED shim.

The cross-platform agent loop now lives in core/agent_loop.py.
This re-export is kept temporarily for backward compatibility.
"""
from __future__ import annotations

from core.agent_loop import *  # noqa: F401,F403
from core.agent_loop import run_agent_loop, run_agent_task, run_agent_task_async  # noqa: F401
