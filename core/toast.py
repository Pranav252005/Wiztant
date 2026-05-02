import os
import sys
import threading
from pathlib import Path

# Get absolute path to icon for notifications
ICON_PATH = str(Path(__file__).parent.parent / "whiztant.ico")
if not Path(ICON_PATH).exists():
    ICON_PATH = ""


def show_toast(message: str, title: str = "Whiztant",
               duration: str = "short"):
    """
    Terminal-only status notification (no OS pop-ups).
    Prints to stdout so the user sees status in the terminal window.
    """
    print(f"[{title}] {message}")

# Pre-defined toasts used throughout the app
def toast_listening():
    show_toast("Listening...", "🎙️ Whiztant")

def toast_transcribing():
    show_toast("Transcribing...", "🤔 Whiztant")

def toast_pasted(text_preview: str = ""):
    preview = f': "{text_preview[:40]}..."' if text_preview else ""
    show_toast(f"Pasted{preview}", "✅ Whiztant")

def toast_agent_started():
    show_toast("Agent mode activated", "⚡ Whiztant")

def toast_agent_done(result: str = ""):
    preview = f": {result[:50]}" if result else ""
    show_toast(f"Task complete{preview}", "✅ Whiztant")

def toast_error(message: str):
    show_toast(message, "❌ Whiztant")

def toast_limit_reached(feature: str):
    show_toast(
        f"Monthly {feature} limit reached. Upgrade your plan.",
        "🚫 Whiztant"
    )

def toast_ready(tier: str):
    show_toast(
        f"Running on {tier.upper()} plan — press F9 to start",
        "✅ Whiztant"
    )

def toast_action_blocked(reason: str):
    show_toast(f"Dangerous action blocked: {reason}", "🚫 Whiztant")

def toast_safety_alert(msg: str):
    show_toast(msg, "⚠️ Whiztant")

def toast_undo_available():
    show_toast("Undo available — press Ctrl+Z or click Undo in overlay", "↩️ Whiztant")
