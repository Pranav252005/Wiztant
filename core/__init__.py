"""
Whiztant core package — shared state, config, and constants.
All mutable state lives here so every module can read/write it.
"""

import os
import threading
import pathlib

# =============================================================
#  PROJECT ROOT
# =============================================================
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# =============================================================
#  CONFIG
# =============================================================

SILENCE_THRESHOLD   = 300
MAX_HISTORY         = 21
MAX_TOOL_TURNS      = 4
USE_LLM_POLISH      = False

SCREENSHOT_DIR          = str(PROJECT_ROOT / "agent_screenshots")
SCREENSHOT_INTERVAL     = 1.2
SCREENSHOT_FILENAME_FMT = "agent_screen_{index}.png"

MEMORY_DIR  = PROJECT_ROOT / "memory"
MEMORY_FILE = MEMORY_DIR / "memory.json"

# =============================================================
#  SHARED MUTABLE STATE
# =============================================================

recording            = False
agent_mode           = False
thinking             = False
conversation_history = []
audio_frames         = []
audio_level          = 0.0

tts_process          = None
tts_lock             = threading.Lock()

MEMORY_ENABLED       = False

# F9 tap state
_f9_count            = 0
_f9_timer            = None
TAP_WINDOW           = 0.42

# Agent screenshot state
_agent_screenshot_thread     = None
_agent_screenshot_stop_event = None
_agent_screenshot_lock       = threading.Lock()
_agent_latest_screenshot_paths: list[str] = []
_agent_stop_event            = None
_agent_running               = False
_task_recording              = False
_agent_confirmation_overlay_active = False
_agent_confirmation_overlay_minimized = False

overlay = None
chat_overlay = None
_agent_step_page_cb = None   # optional per-page step callback set by AgentPage

# Workflow recorder state
workflow_recording       = False
_workflow_recorder       = None

# System context (set by initialize_system_context on startup)
system_context_loader    = None
system_context_scheduler = None

# Tune Hub user settings (persisted via settings.json, mutable at runtime)
tune_hub_settings: dict = {}
