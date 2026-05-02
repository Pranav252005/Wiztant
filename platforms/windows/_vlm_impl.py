"""
core/vlm.py — Whiztant intelligent agent runtime.
Two-path architecture: UIA (primary, fast) → Vision (fallback)
"""

from __future__ import annotations

import ast
import base64
import concurrent.futures
import ctypes
import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# Windows-only imports
if sys.platform == "win32":
    import winreg
else:
    winreg = None
from typing import Any, Callable, Dict, List, Optional, Tuple

import core as state

# PyAutoGUI is Windows-only; on Linux it crashes without tkinter
# Skip entirely on Linux - agent mouse control won't work but app will start
if sys.platform == "win32":
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        _PYAUTOGUI_OK = True
    except Exception as e:
        print(f"[VLM] WARNING: pyautogui not available: {e}")
        pyautogui = None
        _PYAUTOGUI_OK = False
else:
    pyautogui = None
    _PYAUTOGUI_OK = False

from openai import OpenAI
from core import shortcuts_loader
from core.agent_engine import (
    ACTION_SETTLE_DELAY,
    BROWSER_APPS as _BROWSER_APPS,
    BROWSER_LAUNCH_DELAY,
    CATEGORY_TO_FILE as _CATEGORY_TO_FILE,
    EXECUTOR_MODEL,
    EXEC_MAX_TOKENS,
    GROUND_IMG_MAX,
    KEYBOARD_SHORTCUTS,
    KNOWN_APPS as _KNOWN_APPS,
    LOAD_POLL_SECONDS,
    MAX_LOOP_STEPS,
    MAX_RESULT_SCROLLS,
    OCR_MAX_LINES,
    OMNI_MODEL,
    PAGE_LOAD_TIMEOUT,
    PLAN_MAX_TOKENS,
    SITE_ALIASES as _SITE_ALIASES,
    SITE_URLS as _SITE_URLS,
    STEP_PAUSE,
    TEMP_EXEC,
    TEMP_PLAN,
    TEMP_TARS,
    TEMP_THINK,
    TARS_MAX_TOKENS,
    THINK_MAX_TOKENS,
    canonicalize_url as _canonicalize_url,
    canonical_site_label as _canonical_site_label,
    entry_category as _entry_category,
    extract_click_target as _extract_click_target,
    extract_requested_app as _extract_requested_app,
    extract_requested_url as _extract_requested_url,
    is_research_task as _is_research_task,
    refine_element_target as _refine_element_target,
    refine_task_text as _refine_task_text,
)
from mss import mss
from PIL import Image, ImageGrab
from io import BytesIO

try:
    import pyperclip
except ImportError:
    pyperclip = None

# ── Optional: Tesseract OCR ───────────────────────────────────────────────────
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.getenv(
        "TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False

# ── Logging setup ─────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("data/whiztant.log", encoding="utf-8"),
        logging.FileHandler("data/agent_debug.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("core.vlm")

for _log_path in ("data/whiztant.log", "data/agent_debug.log"):
    _abs = os.path.abspath(_log_path)
    _root = logging.getLogger()
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == _abs
        for h in _root.handlers
    ):
        _root.addHandler(logging.FileHandler(_abs, encoding="utf-8"))

# ── DPI awareness ─────────────────────────────────────────────────────────────
_DPI_AWARENESS_SET = False
if sys.platform == "win32" and not _DPI_AWARENESS_SET:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _DPI_AWARENESS_SET = True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            _DPI_AWARENESS_SET = True
        except Exception:
            pass

# ── Config ────────────────────────────────────────────────────────────────────
_OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
_client = OpenAI(
    api_key=_OR_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://whiztant.com",
        "X-Title": "Whiztant",
    },
)

# ── Model Configuration ───────────────────────────────────────────────────────
# (Imported from core.agent_engine — keep local additions below)

_RULES_DIR = Path(__file__).parent.parent / "agent_rules"

# _CATEGORY_TO_FILE imported from core.agent_engine

# _KNOWN_APPS imported from core.agent_engine

# KEYBOARD_SHORTCUTS imported from core.agent_engine

# _BROWSER_APPS, _SITE_URLS, _SITE_ALIASES imported from core.agent_engine

_BROWSER_EXECUTABLES: dict[str, str] = {
    "chrome": "chrome.exe",
    "arc": "Arc.exe",
    "firefox": "firefox.exe",
    "msedge": "msedge.exe",
}

_BROWSER_PATHS: dict[str, tuple[str, ...]] = {
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
    "arc": tuple(
        path for path in (
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Arc", "Arc.exe"),
            r"C:\Program Files\Arc\Arc.exe",
        )
        if path
    ),
    "firefox": (
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ),
    "msedge": (
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ),
}

# _entry_category imported from core.agent_engine


# ══════════════════════════════════════════════════════════════════════════════
# TWO-PATH ARCHITECTURE — UIA (Primary) + Vision (Fallback)
# ══════════════════════════════════════════════════════════════════════════════

_UIA_SYSTEM_PROMPT = """\
You are a Windows desktop agent. You receive the UI accessibility tree of the
foreground window and a task. Return a single JSON action to complete one step.
Available actions:
{"action": "click_element", "title": "exact element title from tree"}
{"action": "type", "text": "text to type"}
{"action": "key", "key": "ctrl+s"}
{"action": "done", "result": "summary"}
{"action": "fallback", "reason": "UIA insufficient, need vision"}
Return ONLY valid JSON. No markdown, no explanation.
"""


def _get_uia_tree() -> str | None:
    """Dump the accessibility tree of the foreground window using pywinauto."""
    if sys.platform != "win32":
        return None
    try:
        from pywinauto import Desktop
        import win32gui
        desktop = Desktop(backend="uia")
        win = desktop.window(handle=win32gui.GetForegroundWindow())
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        win.print_control_identifiers(depth=4)
        sys.stdout = old
        tree = buf.getvalue().strip()
        return tree if len(tree) > 50 else None
    except Exception as e:
        log.warning("UIA tree failed: %s", e)
        return None


def _find_uia_element(title: str) -> Any:
    """Find a UI element by title in the current foreground window."""
    if sys.platform != "win32":
        return None
    try:
        from pywinauto import Desktop
        import win32gui
        desktop = Desktop(backend="uia")
        win = desktop.window(handle=win32gui.GetForegroundWindow())
        return win.child_window(title=title, found_index=0)
    except Exception as e:
        log.warning("UIA find element failed: %s", e)
        return None


def _ask_omni_uia(task: str, tree: str, step: int, repeat_warning: str = "") -> dict:
    """Ask OMNI_MODEL (MiMo-V2-Omni, text-only) to choose a UIA action based on the accessibility tree."""
    log.info("Step %d: UIA path", step + 1)
    user_content = f"Task: {task}\n\nUI Tree:\n{tree[:8000]}\n\n"
    if repeat_warning:
        user_content += f"WARNING: {repeat_warning}\n\n"
    user_content += "Next action (JSON only):"
    messages = [
        {"role": "system", "content": _UIA_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = _call_api(OMNI_MODEL, messages, TEMP_PLAN, 400)
    parsed = _parse_json(raw)
    if not parsed:
        log.warning("UIA planner returned invalid JSON: %s", raw[:200])
        return {"action": "fallback", "reason": "Invalid planner response"}
    return parsed


def _ask_omni_vision(task: str, step: int, repeat_warning: str = "") -> dict:
    """Path 2: Screenshot → OMNI_MODEL (MiMo-V2-Omni, vision mode) → optional EXECUTOR_MODEL (UI-TARS)."""
    log.info("Step %d: vision fallback", step + 1)
    img = _screenshot()
    b64 = _to_base64(img)

    # First ask OMNI_MODEL for planning (vision mode)
    vision_system = (
        "You are a Windows desktop agent. Analyze the screenshot and task. "
        "Return JSON with action plan: {"
        '"action": "click"|"type"|"key"|"scroll"|"uitars"|"done", '
        '"coordinate": [x, y] for click/scroll (0-1000 scale), '
        '"text": "text to type", "key": "ctrl+s", "reason": "explanation"}. '
        "CRITICAL: This is Windows. Never use 'cmd'. Use 'ctrl' or 'win' instead. "
        "Never output 'alt+tab'. Never output 'cmd+q' or 'cmd+w'. "
        "Valid modifier keys: ctrl, shift, alt, win. No cmd, no super, no meta."
    )
    text_content = f"Task: {task}\n\n"
    if repeat_warning:
        text_content += f"WARNING: {repeat_warning}\n\n"
    text_content += "Next action (JSON only):"
    messages = [
        {"role": "system", "content": vision_system},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": text_content},
        ]},
    ]
    raw = _call_api(OMNI_MODEL, messages, TEMP_EXEC, 400)
    parsed = _parse_json(raw)

    if not parsed:
        log.warning("Vision model returned invalid JSON: %s", raw[:200])
        return {"action": "fallback", "reason": "Invalid vision response"}

    # If vision model asks for uitars, route to EXECUTOR_MODEL for pixel execution
    if parsed.get("action") == "uitars":
        return _ask_uitars_executor(task, img)

    return parsed


def _ask_uitars_executor(instruction: str, img: Image.Image) -> dict:
    """Call UI-TARS executor for pixel-level execution."""
    system = (
        "You are a precise UI locator. Find the element and return its center coordinates.\n"
        "Coordinate system: 0-1000 scale. (0,0)=top-left, (1000,1000)=bottom-right.\n"
        "Return ONLY raw JSON:\n"
        '  Found:     {"action":"click","x":<int>,"y":<int>,"element":"<name>"}\n'
        '  Not found: {"action":"not_found","element":"<searched>"}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_to_base64(img)}"}},
            {"type": "text", "text": instruction},
        ]},
    ]
    raw = _call_api(EXECUTOR_MODEL, messages, TEMP_TARS, 150)
    return _parse_json(raw) or {"action": "not_found", "element": instruction}


def _execute_two_path(action: dict, step: int, task: str) -> tuple[bool, str]:
    """
    Execute an action from either UIA or Vision path.
    Returns (success, result_message).
    """
    a = action.get("action", "")

    # UIA path: click_element by title
    if a == "click_element":
        title = action.get("title", "")
        el = _find_uia_element(title)
        if el:
            try:
                el.click_input()
                time.sleep(0.5)
                return True, f"clicked element '{title}'"
            except Exception as e:
                log.warning("UIA click failed: %s", e)
                return False, f"UIA click failed: {e}"
        return False, f"element '{title}' not found"

    # Vision path: click by coordinate
    if a == "click":
        coords = action.get("coordinate") or [action.get("x"), action.get("y")]
        if coords and len(coords) >= 2:
            x_1000, y_1000 = coords[0], coords[1]
            clicked, msg = _perform_click_from_model(x_1000, y_1000, reason=f"step:{step}")
            return clicked, msg
        return False, "invalid click coordinates"

    if a == "type":
        text = action.get("text", "")
        pyautogui.hotkey("ctrl", "a")  # clear field first
        pyautogui.typewrite(text, interval=0.03)
        if text.startswith("http") or text.startswith("www"):
            time.sleep(0.3)
            pyautogui.press("enter")
        time.sleep(0.5)
        return True, f"typed '{text}'"

    if a == "key":
        key = action.get("key", "")
        # Block macOS/dangerous keys from firing on user's screen
        _BLOCKED_KEYS = {"cmd+q", "cmd+w", "cmd+tab", "alt+tab", "alt+f4", "super+q"}
        if key.lower() in _BLOCKED_KEYS:
            log.warning("Blocked unsafe key: %s", key)
            return False, f"blocked unsafe key: {key}"
        # Remap cmd → ctrl for Windows
        key = key.replace("cmd+", "ctrl+")
        keys = key.split("+")
        pyautogui.hotkey(*keys)
        time.sleep(0.5)
        return True, f"pressed {key}"

    if a == "scroll":
        coords = action.get("coordinate") or [action.get("x"), action.get("y")]
        if coords and len(coords) >= 2:
            x, y = _translate(coords[0], coords[1])
            if x is not None and y is not None:
                direction = -1 if action.get("direction") == "down" else 1
                amount = action.get("amount", 3) * direction
                pyautogui.scroll(amount, x=x, y=y)
                time.sleep(0.5)
                return True, f"scrolled at ({x}, {y})"
        return False, "invalid scroll coordinates"

    if a == "done":
        result = action.get("result", "Task completed")
        return True, f"done: {result}"

    if a == "fallback":
        reason = action.get("reason", "UIA insufficient")
        log.info("UIA fallback triggered: %s", reason)
        # Switch to vision fallback for this step
        vision_action = _ask_omni_vision(task, step)
        return _execute_two_path(vision_action, step, task)

    if a == "not_found":
        return False, f"target not found: {action.get('element', 'unknown')}"

    return False, f"unknown action: {a}"


def run_agent_loop(task: str, toast: Optional[Callable] = None, progress_cb: Optional[Callable] = None) -> str:
    """
    Main two-path agent loop.
    PATH 1: UIA (text-only, fast) via pywinauto accessibility tree + MiMo-V2-Pro
    PATH 2: Vision (fallback) via screenshot + Qwen3-VL + UI-TARS
    """
    log.info("=== Agent task (two-path): %r ===", task)
    if toast:
        toast("Whiztant", "Agent starting...")
    if progress_cb:
        progress_cb("step", "Initializing agent...")

    # Pre-flight: determine app to open and strategy
    preflight = _preflight(task)
    app_to_open = preflight.get("app_to_open") or preflight.get("app", "chrome")
    _ensure_app_open(app_to_open)

    # Track last 3 actions for repeat detection
    action_history: list[str] = []
    repeat_warning = ""

    for step in range(MAX_LOOP_STEPS):
        if progress_cb:
            progress_cb("step", f"Step {step + 1}: Analyzing...")

        # PATH 1: Try UIA first
        tree = _get_uia_tree()
        action: Optional[dict] = None

        if tree:
            action = _ask_omni_uia(task, tree, step, repeat_warning)
            if action.get("action") == "fallback":
                log.info("UIA returned fallback, switching to vision path")
                action = _ask_omni_vision(task, step, repeat_warning)
        else:
            log.info("No UIA tree available, using vision fallback")
            action = _ask_omni_vision(task, step, repeat_warning)

        if not action:
            msg = f"Step {step + 1}: No action returned from models"
            log.error(msg)
            if progress_cb:
                progress_cb("error", msg)
            continue

        # Execute the action
        success, result = _execute_two_path(action, step, task)
        log.info("Step %d result: %s", step + 1, result)

        # Track action for repeat detection
        action_str = json.dumps(action, sort_keys=True)
        action_history.append(action_str)
        if len(action_history) > 3:
            action_history.pop(0)
        # Check if same action repeated 3 times
        if len(action_history) == 3 and len(set(action_history)) == 1:
            repeat_warning = "Previous action failed or had no effect. Do NOT repeat it. Try a completely different approach to make progress on the task."
            log.warning("Repeat action detected — injecting warning into next prompt")
        else:
            repeat_warning = ""

        if action.get("action") == "done":
            if progress_cb:
                progress_cb("done", result)
            if toast:
                toast("Whiztant", result[:80])
            return result

        if not success:
            msg = f"Step {step + 1} failed: {result}"
            log.warning(msg)
            if progress_cb:
                progress_cb("error", msg)
            # Continue to next step to attempt recovery

        time.sleep(0.3)

    limit_msg = f"Reached {MAX_LOOP_STEPS}-step limit — task may be incomplete"
    log.warning(limit_msg)
    if progress_cb:
        progress_cb("error", limit_msg)
    if toast:
        toast("Whiztant", limit_msg[:80])
    return limit_msg


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _load_rule_file(category: str) -> str:
    candidates = _CATEGORY_TO_FILE.get(category.upper(), ("agent_navigation.md",))
    for filename in candidates:
        path = _RULES_DIR / filename
        if path.exists():
            content = path.read_text(encoding="utf-8")
            log.debug(f"Rule file: {filename} ({len(content):,} chars)")
            return content
    log.warning(f"Rule file not found for category {category}: {candidates}")
    return ""

# _canonicalize_url, _canonical_site_label, _refine_element_target,
# _refine_task_text, _is_research_task imported from core.agent_engine

def _quick_preflight(task: str) -> Optional[dict]:
    refined_task = _refine_task_text(task)
    lowered = refined_task.lower()
    if _is_research_task(refined_task):
        return None

    app_name = _extract_requested_app(refined_task)
    url, site_label = _extract_requested_url(refined_task)
    click_target = _extract_click_target(refined_task)
    browser_like = bool(url or click_target) or any(
        word in lowered for word in (
            "navigate",
            "go to",
            "visit",
            "open chrome",
            "open edge",
            "open firefox",
            "open arc",
            "open browser",
        )
    )
    if not browser_like:
        return None

    step_count = len([item for item in (app_name, url, click_target) if item]) or 1
    strategy_parts = []
    if app_name:
        strategy_parts.append(f"open {app_name}")
    if site_label:
        strategy_parts.append(f"go to {site_label}")
    if click_target:
        strategy_parts.append(f"click {click_target}")

    return {
        "clean_task": refined_task,
        "app_to_open": app_name,
        "step_count": step_count,
        "entry_point": app_name or ("browser" if url else "unknown"),
        "needs_research": False,
        "research_query": None,
        "keyboard_only": bool(url and not click_target),
        "strategy": ", then ".join(strategy_parts) or "fast browser execution",
    }

def _screenshot() -> Image.Image:
    with mss() as sct:
        m = sct.monitors[1]
        raw = sct.grab(m)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

def _to_base64(img: Image.Image) -> str:
    """Encode image as compact JPEG base64 for multimodal API calls.

    Downscales to GROUND_IMG_MAX longest side and uses JPEG quality 80.
    Cuts payload size ~5-10x vs full-res PNG, dramatically speeding up
    OpenRouter grounding calls.
    """
    scaled = img
    try:
        max_side = max(img.size)
        if max_side > GROUND_IMG_MAX:
            ratio = GROUND_IMG_MAX / float(max_side)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            scaled = img.resize(new_size, Image.LANCZOS)
        if scaled.mode != "RGB":
            scaled = scaled.convert("RGB")
    except Exception:
        scaled = img
    buf = BytesIO()
    try:
        scaled.save(buf, format="JPEG", quality=80, optimize=True)
    except Exception:
        buf = BytesIO()
        scaled.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def _ocr(img: Image.Image) -> str:
    if not TESSERACT_OK:
        return ""
    try:
        raw   = pytesseract.image_to_string(img)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return "\n".join(lines[:OCR_MAX_LINES])
    except Exception as e:
        log.warning(f"OCR error: {e}")
        return ""

def _screenshot_and_ocr() -> tuple[Image.Image, str]:
    img = _screenshot()
    return img, _ocr(img)

def _ocr_contains_any(ocr_text: str, needles: list[str]) -> bool:
    lowered = (ocr_text or "").lower()
    return any(needle.lower() in lowered for needle in needles if needle)

def _query_tokens(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(token) >= 3]

def _page_ready(target: str, ocr_text: str, query: str = "") -> bool:
    lowered = (ocr_text or "").lower()
    if not lowered.strip():
        return False
    loading_markers = ("loading", "redirecting", "please wait", "just a moment", "buffering")
    if any(marker in lowered for marker in loading_markers):
        return False
    if target == "youtube_home":
        return "youtube" in lowered and any(word in lowered for word in ("search", "home", "shorts", "subscriptions"))
    if target == "youtube_results":
        tokens = _query_tokens(query)
        token_match = not tokens or any(token in lowered for token in tokens)
        return "youtube" in lowered and token_match and any(word in lowered for word in ("filters", "views", "ago", "subscribers", "results"))
    if target == "youtube_video":
        tokens = _query_tokens(query)
        token_match = not tokens or any(token in lowered for token in tokens)
        return token_match and any(word in lowered for word in ("subscribe", "share", "save", "clip", "comments", "views"))
    return True

def _wait_for_page_state(target: str, query: str = "", timeout: float = PAGE_LOAD_TIMEOUT, progress_cb: Optional[Callable] = None) -> tuple[bool, str]:
    deadline = time.time() + max(1.0, timeout)
    attempt = 0
    latest_ocr = ""
    while time.time() < deadline:
        attempt += 1
        _, latest_ocr = _screenshot_and_ocr()
        short = latest_ocr[:180].replace("\n", " | ") if latest_ocr else "(no text detected)"
        log.info("Page wait %s attempt %s OCR: %s", target, attempt, short)
        if progress_cb:
            progress_cb("step", f"Waiting for {target} — check {attempt}: {short}")
        if _page_ready(target, latest_ocr, query=query):
            return True, f"page ready: {target}"
        time.sleep(LOAD_POLL_SECONDS)
    return False, f"timed out waiting for {target}: {latest_ocr[:180]}"

def _capture_progress_snapshot(label: str, progress_cb: Optional[Callable] = None) -> None:
    _, ocr_text = _screenshot_and_ocr()
    short = ocr_text[:180].replace("\n", " | ") if ocr_text else "(no text detected)"
    log.info("Snapshot after %s: %s", label, short)
    if progress_cb:
        progress_cb("step", f"Snapshot after {label}: {short}")

def _strip_code_fences(text: str) -> str:
    return re.sub(r"^```(?:json|python)?\s*|\s*```$", "", (text or "").strip(), flags=re.IGNORECASE | re.MULTILINE).strip()

def _extract_braced_object(text: str) -> Optional[str]:
    source = (text or "").strip()
    start = source.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(source[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    if depth > 0:
        return source[start:] + ("}" * depth)
    return source[start:]

def _parse_json(text: str) -> Optional[dict]:
    """Best-effort JSON parser for LLM responses.

    Strips <think> blocks (MiMo-V2-Omni), code fences, extracts the first
    balanced {...} object, normalizes common issues (smart quotes, trailing
    commas, unbalanced braces), and falls back to Python literal eval.
    Returns the parsed dict, or None if parsing fails.
    """
    if not text:
        return None
    # Strip model thinking blocks before any other processing
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    stripped = _strip_code_fences(text)
    candidates: list[str] = []
    braced = _extract_braced_object(stripped)
    if braced:
        candidates.append(braced)
    candidates.append(stripped)
    for candidate in candidates:
        normalized = _normalize_json_text(candidate)
        try:
            parsed = json.loads(normalized)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(_pythonize_json_text(normalized))
            if isinstance(parsed, dict):
                return _json_safe(parsed)
        except Exception:
            continue
    return None

def _normalize_json_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r":\s*\(([^()]+)\)", lambda match: ": [" + match.group(1).strip() + "]", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    if cleaned.count("{") > cleaned.count("}"):
        cleaned += "}" * (cleaned.count("{") - cleaned.count("}"))
    return cleaned

def _pythonize_json_text(text: str) -> str:
    python_text = (text or "").strip()
    python_text = re.sub(r"\bnull\b", "None", python_text, flags=re.IGNORECASE)
    python_text = re.sub(r"\btrue\b", "True", python_text, flags=re.IGNORECASE)
    python_text = re.sub(r"\bfalse\b", "False", python_text, flags=re.IGNORECASE)
    return python_text

def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        cleaned = value.strip()
        if re.fullmatch(r"-?\d+", cleaned):
            return int(cleaned)
        if re.fullmatch(r"-?\d+\.0+", cleaned):
            return int(float(cleaned))
    return None

def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value

def _extract_coordinate_pair(value: Any) -> Optional[Tuple[int, int]]:
    if isinstance(value, dict):
        x_val = _coerce_int(value.get("x"))
        y_val = _coerce_int(value.get("y"))
        if x_val is not None and y_val is not None:
            return x_val, y_val
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        x_val = _coerce_int(value[0])
        y_val = _coerce_int(value[1])
        if x_val is not None and y_val is not None:
            return x_val, y_val
    if isinstance(value, str):
        match = re.search(r"[\[(]\s*(-?\d+(?:\.0+)?)\s*,\s*(-?\d+(?:\.0+)?)\s*[\])]", value)
        if match:
            x_val = _coerce_int(match.group(1))
            y_val = _coerce_int(match.group(2))
            if x_val is not None and y_val is not None:
                return x_val, y_val
    return None

def _normalize_action_payload(payload: dict, raw_text: str) -> dict:
    normalized = _json_safe(payload)
    x_val = _coerce_int(normalized.get("x"))
    y_val = _coerce_int(normalized.get("y"))
    if x_val is None or y_val is None:
        x_pair = _extract_coordinate_pair(normalized.get("x"))
        if x_pair:
            if x_val is None:
                x_val = x_pair[0]
            if y_val is None:
                y_val = x_pair[1]
    if x_val is None or y_val is None:
        y_pair = _extract_coordinate_pair(normalized.get("y"))
        if y_pair:
            if x_val is None:
                x_val = y_pair[0]
            if y_val is None:
                y_val = y_pair[1]
    for key in ("coordinates", "coordinate", "coords", "position", "point", "location", "center"):
        pair = _extract_coordinate_pair(normalized.get(key))
        if not pair:
            continue
        if x_val is None:
            x_val = pair[0]
        if y_val is None:
            y_val = pair[1]
        if x_val is not None and y_val is not None:
            break
    if x_val is None or y_val is None:
        pair = _extract_coordinate_pair(raw_text)
        if pair:
            if x_val is None:
                x_val = pair[0]
            if y_val is None:
                y_val = pair[1]
    if x_val is not None:
        normalized["x"] = x_val
    if y_val is not None:
        normalized["y"] = y_val
    return normalized

def _validate_model_coordinates(x_1000: Any, y_1000: Any, reason: str = "") -> Optional[Tuple[int, int]]:
    x_val = _coerce_int(x_1000)
    y_val = _coerce_int(y_1000)
    if x_val is None or y_val is None:
        log.warning("Blocked click %s: non-integer model coordinates x=%r y=%r", reason or "(unknown)", x_1000, y_1000)
        return None
    if not (0 <= x_val <= 1000 and 0 <= y_val <= 1000):
        log.warning("Blocked click %s: out-of-range model coordinates x=%r y=%r", reason or "(unknown)", x_val, y_val)
        return None
    return x_val, y_val

def _virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """Return (left, top, width, height) of the full virtual desktop.

    Falls back to the primary monitor if MSS or win32 APIs are unavailable.
    """
    try:
        with mss() as sct:
            mon = sct.monitors[0]
            return int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"])
    except Exception:
        pass
    try:
        user32 = ctypes.windll.user32
        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
        return (
            int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN)),
            int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN)),
            int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)),
            int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)),
        )
    except Exception:
        w, h = pyautogui.size()
        return 0, 0, int(w), int(h)

def _validate_screen_coordinates(x: Any, y: Any, reason: str = "") -> Optional[Tuple[int, int]]:
    x_val = _coerce_int(x)
    y_val = _coerce_int(y)
    if x_val is None or y_val is None:
        log.warning("Blocked click %s: non-integer screen coordinates x=%r y=%r", reason or "(unknown)", x, y)
        return None
    left, top, width, height = _virtual_screen_bounds()
    if not (left <= x_val < left + width and top <= y_val < top + height):
        log.warning(
            "Blocked click %s: out-of-bounds screen coordinates x=%r y=%r bounds=(%r,%r,%r,%r)",
            reason or "(unknown)",
            x_val,
            y_val,
            left,
            top,
            width,
            height,
        )
        return None
    return x_val, y_val

def _translate(x_1000: Any, y_1000: Any, reason: str = "") -> Optional[tuple[int, int]]:
    pair = _validate_model_coordinates(x_1000, y_1000, reason=reason)
    if not pair:
        return None
    w, h = pyautogui.size()
    screen_x = int(pair[0] / 1000 * w)
    screen_y = int(pair[1] / 1000 * h)
    return _validate_screen_coordinates(screen_x, screen_y, reason=reason)

def _perform_click(x: Any, y: Any, reason: str = "") -> tuple[bool, str]:
    log.info("Click attempt %s: x=%r y=%r", reason or "(unknown)", x, y)
    pair = _validate_screen_coordinates(x, y, reason=reason)
    if not pair:
        return False, f"invalid click coordinates for {reason or 'action'}"
    try:
        pyautogui.moveTo(pair[0], pair[1], duration=0.15)
        time.sleep(ACTION_SETTLE_DELAY)
        pyautogui.click(pair[0], pair[1])
        time.sleep(STEP_PAUSE)
        return True, f"clicked at ({pair[0]}, {pair[1]})"
    except Exception as e:
        log.warning("Click failed %s: %s", reason or "(unknown)", e)
        return False, f"click failed for {reason or 'action'}: {e}"

def _perform_click_from_model(x_1000: Any, y_1000: Any, reason: str = "") -> tuple[bool, str]:
    log.info("Model click attempt %s: x=%r y=%r", reason or "(unknown)", x_1000, y_1000)
    # Some models return coords as a list packed into x (e.g. x=[359,271], y=None)
    # or as a [x, y] list in x. Normalize before translating.
    if isinstance(x_1000, (list, tuple)) and len(x_1000) >= 2 and (y_1000 is None or isinstance(y_1000, (list, tuple))):
        try:
            x_1000, y_1000 = x_1000[0], x_1000[1]
        except Exception:
            pass
    translated = _translate(x_1000, y_1000, reason=reason)
    if not translated:
        return False, f"invalid translated click coordinates for {reason or 'action'}"
    return _perform_click(translated[0], translated[1], reason=reason)

def _find_keyboard_shortcut(description: str) -> Optional[list[str]]:
    """
    Check if a plain-English action description matches a known keyboard shortcut.
    Returns pyautogui key list or None.
    """
    desc_lower = description.lower()
    for phrase, keys in KEYBOARD_SHORTCUTS.items():
        if phrase in desc_lower:
            return keys
    return None

# ══════════════════════════════════════════════════════════════════════════════
# API CALLERS
# ══════════════════════════════════════════════════════════════════════════════

def _call_api(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    thinking: bool = False,
) -> str:
    """Unified OpenRouter API caller via OpenAI SDK. Returns response text or '' on error."""
    if not model:
        return ""
    extra: dict = {}
    if thinking:
        extra["thinking"] = {"type": "enabled", "budget_tokens": THINK_MAX_TOKENS}
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra if extra else None,
            timeout=35,
        )
        content = resp.choices[0].message.content or ""
        if isinstance(content, list):
            return "\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
        return str(content).strip()
    except Exception as e:
        log.error("API error (model=%s): %s", model, e)
        if thinking:
            try:
                resp = _client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=35,
                )
                content = resp.choices[0].message.content or ""
                return str(content).strip()
            except Exception as retry_error:
                log.error("API retry error (model=%s): %s", model, retry_error)
    return ""

# _extract_requested_app, _extract_requested_url, _extract_click_target
# imported from core.agent_engine

def _extract_search_query(task: str) -> Optional[str]:
    source = (task or "").strip()
    patterns = [
        r"search\s+(?:up\s+)?(?:for\s+)?(.+?)(?:\s+(?:and|then)\s+play\b|\s+(?:and|then)\b|[\.,]|$)",
        r"look\s+up\s+(.+?)(?:\s+(?:and|then)\b|[\.,]|$)",
        r"find\s+(.+?)(?:\s+(?:and|then)\b|[\.,]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip(" .,")
            if query:
                return query
    return None

def _extract_video_recency_hint(task: str) -> Optional[str]:
    lowered = (task or "").lower()
    relative = re.search(r"\b\d+\s+(?:minute|hour|day|week|month|year)s?\s+ago\b", lowered)
    if relative:
        return relative.group(0)
    if "most recent" in lowered:
        return "most recent"
    if "latest" in lowered:
        return "latest"
    if "newest" in lowered:
        return "newest"
    return None

def _youtube_filter_code(recency_hint: str, task: str = "") -> Optional[str]:
    """Map a natural-language recency/sort hint to YouTube's ``sp=`` URL code.

    These are YouTube's public filter codes (base64-encoded protobuf). They
    are stable and let us jump straight to the filtered results page instead
    of clicking the Filters UI.

    Supported hints (checked against both hint and full task text):
      - "last hour"                               → EgIIAQ%3D%3D
      - "today"                                   → EgIIAg%3D%3D
      - "this week"                               → EgIIAw%3D%3D
      - "this month"                              → EgIIBA%3D%3D
      - "this year"                               → EgIIBQ%3D%3D
      - "latest", "most recent", "newest"         → CAI%3D (sort by date)
      - "most viewed", "top", "popular"           → CAM%3D (sort by views)
      - "highest rated"                           → CAE%3D (sort by rating)

    YouTube has no direct "oldest" filter; we sort by upload date and let
    the caller scroll to the bottom if needed.
    """
    text = f"{(recency_hint or '').lower()} {(task or '').lower()}"
    # Most specific time windows first.
    if re.search(r"last\s+hour|past\s+hour|in\s+the\s+last\s+hour", text):
        return "EgIIAQ%3D%3D"
    if re.search(r"\btoday\b|in\s+the\s+last\s+day|past\s+24\s*hours?", text):
        return "EgIIAg%3D%3D"
    if re.search(r"this\s+week|last\s+week|past\s+week|in\s+the\s+last\s+week", text):
        return "EgIIAw%3D%3D"
    if re.search(r"this\s+month|last\s+month|past\s+month|in\s+the\s+last\s+month", text):
        return "EgIIBA%3D%3D"
    if re.search(r"this\s+year|last\s+year|past\s+year|in\s+the\s+last\s+year", text):
        return "EgIIBQ%3D%3D"
    if re.search(r"most\s+viewed|most\s+views|top\s+video|popular", text):
        return "CAM%3D"
    if re.search(r"highest\s+rated|best\s+rated|top\s+rated", text):
        return "CAE%3D"
    if re.search(r"latest|most\s+recent|newest|new(est)?\s+video|just\s+uploaded|recent", text):
        return "CAI%3D"
    return None

def _wants_first_video(task: str) -> bool:
    lowered = (task or "").lower()
    triggers = (
        "play the first video",
        "play first video",
        "play the first result",
        "play first result",
        "open the first video",
        "open first video",
        "open the first result",
        "open first result",
        # Recency/sort phrases imply "open the top result of the filtered list"
        "play the latest",
        "play latest",
        "play the most recent",
        "play most recent",
        "play the newest",
        "play newest",
        "play the top",
        "play top",
        "play the most viewed",
        "open the latest",
        "open the most recent",
        "open the newest",
    )
    return any(trigger in lowered for trigger in triggers)

def _heuristic_plan(task: str, preflight: Optional[dict] = None) -> Optional[dict]:
    lowered = (task or "").lower()
    preflight = preflight or {}
    app_name = preflight.get("app_to_open") or _extract_requested_app(task)
    url, site_label = _extract_requested_url(task)
    click_target = _extract_click_target(task)
    search_query = _extract_search_query(task)
    recency_hint = _extract_video_recency_hint(task)
    wants_first_video = _wants_first_video(task)

    if not app_name and (url or any(word in lowered for word in ("browser", "navigate", "go to", "search"))):
        app_name = "chrome"

    actions: list[dict] = []
    steps: list[str] = []
    category = _entry_category(preflight.get("entry_point"))
    initial_action = None

    if app_name:
        initial_action = {"type": "open_app", "app": app_name}
        if app_name in _BROWSER_APPS or url:
            category = "D"

    # Fast-path: if this is a YouTube search task, skip the "click search bar"
    # grounding step entirely by navigating directly to the results URL.
    youtube_search_fastpath = (
        site_label == "youtube.com" and search_query and bool(search_query.strip())
    )

    # Compute the first URL we need to load, so we can pass it straight to the
    # browser at launch time (avoids Ctrl+L racing with a non-browser focus).
    first_url: Optional[str] = None
    if youtube_search_fastpath:
        from urllib.parse import quote_plus
        q = quote_plus(search_query.strip())
        filter_code = _youtube_filter_code(recency_hint or "", task)
        first_url = f"https://www.youtube.com/results?search_query={q}"
        if filter_code:
            first_url += f"&sp={filter_code}"
    elif url:
        first_url = url

    # If we're launching a browser AND have a first URL, merge them so Chrome
    # opens directly at the target page — guarantees browser has focus before
    # any subsequent keyboard input.
    browser_opens_url = (
        initial_action is not None
        and app_name in _BROWSER_APPS
        and first_url
    )
    if browser_opens_url:
        initial_action = {"type": "open_app", "app": app_name, "url": first_url}

    if url and not youtube_search_fastpath and not browser_opens_url:
        steps.append(f"Navigate to {site_label or url}")
        actions.append({"type": "navigate", "url": url})
        if site_label == "youtube.com":
            steps.append("Wait for YouTube home page to load")
            actions.append({"type": "wait_for_page", "target": "youtube_home"})

    if youtube_search_fastpath:
        label = search_query.strip() + (f" ({recency_hint})" if recency_hint else "")
        if not browser_opens_url:
            steps.append(f"Open YouTube search results for {label}")
            actions.append({"type": "navigate", "url": first_url})
        else:
            steps.append(f"Opening Chrome directly at YouTube results for {label}")
        steps.append("Wait for search results")
        actions.append({"type": "wait_for_page", "target": "youtube_results", "query": search_query.strip()})
    elif search_query:
        search_label = search_query.strip()
        target_instruction = "click youtube search bar" if site_label == "youtube.com" else "click search bar"
        steps.append(f"Focus search bar for {site_label or 'the page'}")
        actions.append({"type": "ask_uitars", "instruction": target_instruction})
        steps.append(f"Type search query {search_label}")
        actions.append({"type": "type", "text": search_label})
        steps.append("Submit search")
        actions.append({"type": "press", "key": "enter"})
        steps.append("Wait for search results")
        actions.append({"type": "wait_for_page", "target": "youtube_results", "query": search_label})

    if wants_first_video:
        steps.append("Open the first video result")
        actions.append({
            "type": "find_video_result",
            "query": search_query or "",
            "hint": recency_hint or "",
            "site": site_label or "",
            "max_scrolls": MAX_RESULT_SCROLLS,
        })
        steps.append("Wait for video playback to start")
        actions.append({"type": "wait_for_page", "target": "youtube_video", "query": search_query or ""})

    if click_target:
        cleaned_target = click_target
        cleaned_target = re.sub(r"\band\b.*$", "", cleaned_target).strip()
        cleaned_target = _refine_element_target(cleaned_target)
        if cleaned_target:
            steps.append(f"Click {cleaned_target}")
            actions.append({"type": "ask_uitars", "instruction": f"click {cleaned_target}"})

    if not initial_action and not actions:
        return None

    summary_parts = []
    if app_name:
        summary_parts.append(f"open {app_name}")
    if site_label or url:
        summary_parts.append(f"go to {site_label or url}")
    if search_query:
        summary_parts.append(f"search {search_query}")
    if wants_first_video:
        summary_parts.append("open the first video")
    if recency_hint:
        summary_parts.append(f"matching {recency_hint}")
    if click_target:
        summary_parts.append(f"click {click_target}")

    return {
        "category": category,
        "confidence": 0.72,
        "task_summary": ", then ".join(summary_parts) or task,
        "steps": steps,
        "initial_action": initial_action,
        "requires_uitars": any(action.get("type") == "ask_uitars" for action in actions),
        "_heuristic_actions": actions,
    }

def _execute_heuristic_plan(plan: dict, progress_cb: Optional[Callable] = None) -> str:
    actions = list(plan.get("_heuristic_actions", []))
    steps = list(plan.get("steps", []))
    if not actions:
        message = plan.get("task_summary", "Task completed")
        if progress_cb:
            progress_cb("done", message)
        return message

    for index, action in enumerate(actions, start=1):
        current_step = steps[index - 1] if index - 1 < len(steps) else str(action)
        if progress_cb:
            progress_cb("step", f"Step {index}/{len(actions)}: {current_step}")
        result = _execute(action, progress_cb=progress_cb)
        if re.search(r"could not find|failed|unknown action", result, re.IGNORECASE):
            message = f"Task failed: {result}"
            if progress_cb:
                progress_cb("error", message)
            return message
        _capture_progress_snapshot(current_step, progress_cb)

    message = plan.get("task_summary", "Task completed")
    if progress_cb:
        progress_cb("done", message)
    return message

def _instruction_variants(instruction: str) -> list[str]:
    base = (instruction or "").strip()
    if not base:
        return []

    target = re.sub(r"^click\s+", "", base, flags=re.IGNORECASE)
    refined_target = _refine_element_target(target)
    variants = [base, f"click {refined_target}"]

    if "sign in" in refined_target:
        variants.extend([
            "click sign in button",
            "click sign in",
            "click log in",
            "click login",
        ])

    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return deduped

def _uitars(img: Image.Image, instruction: str) -> Optional[dict]:
    system = (
        "You are a precise UI locator. Find the element and return its center coordinates.\n"
        "Coordinate system: 0-1000 scale. (0,0)=top-left, (1000,1000)=bottom-right.\n"
        "Return ONLY raw JSON:\n"
        '  Found:     {"action":"click","x":<int>,"y":<int>,"element":"<name>"}\n'
        '  Not found: {"action":"not_found","element":"<searched>"}'
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_to_base64(img)}"}},
                {"type": "text",      "text": instruction},
            ],
        },
    ]
    raw = _call_api(EXECUTOR_MODEL, messages, TEMP_TARS, TARS_MAX_TOKENS)
    return _parse_json(raw)

def _extract_command_path(command: str) -> Optional[str]:
    value = (command or "").strip()
    if not value:
        return None
    quoted = re.match(r'^"([^"]+\.exe)"', value, flags=re.IGNORECASE)
    if quoted:
        return quoted.group(1)
    unquoted = re.match(r'^([A-Za-z]:\\[^\r\n]+?\.exe)\b', value, flags=re.IGNORECASE)
    if unquoted:
        return unquoted.group(1)
    return None

def _lookup_registry_app_path(executable_name: str) -> Optional[str]:
    registry_paths = (
        rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
        rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
    )
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(hive, registry_path) as key:
                    raw_path, _ = winreg.QueryValueEx(key, "")
                command_path = _extract_command_path(str(raw_path)) or str(raw_path)
                if command_path and os.path.exists(command_path):
                    return command_path
            except Exception:
                continue
    return None

def _resolve_browser_path(app: str) -> Optional[str]:
    requested = (app or "").strip().lower()
    if requested in {"browser", "web browser", "default browser"}:
        requested = _get_default_browser_command()
    canonical = _KNOWN_APPS.get(requested, requested)
    executable_name = _BROWSER_EXECUTABLES.get(canonical)
    if not executable_name:
        return None
    for path in _BROWSER_PATHS.get(canonical, ()):
        if path and os.path.exists(path):
            return path
    return _lookup_registry_app_path(executable_name)

def _launch_browser(app: str, url: Optional[str] = None) -> str:
    browser_path = _resolve_browser_path(app)
    if not browser_path:
        log.error("Could not resolve browser path for %r", app)
        return f"failed to launch {app}: browser executable not found"
    try:
        command = [browser_path]
        if url:
            command.append(url)
        log.info("Launching browser %r via %s", app, browser_path)
        subprocess.Popen(command)
        time.sleep(BROWSER_LAUNCH_DELAY)
        return f"launched {app}"
    except Exception as e:
        log.error("_launch_browser(%r) failed: %s", app, e)
        return f"failed to launch {app}: {e}"

def _foreground_browser_window(app: str = "") -> bool:
    """Find a running browser window and bring it to the foreground.

    Safety net for cases where subprocess.Popen launched the browser but the
    window did not auto-foreground (happens when another app like Windsurf has
    focus and Windows blocks foreground changes).

    Returns True if a window was foregrounded, False otherwise.
    """
    try:
        import win32gui  # type: ignore
        import win32con  # type: ignore
    except Exception:
        # pywin32 not installed — best-effort fallback using ctypes.
        return _foreground_browser_window_ctypes(app)

    app_lower = (app or "").strip().lower()
    canonical = _KNOWN_APPS.get(app_lower, app_lower)
    # Map canonical names to substrings that appear in window titles.
    title_hints = {
        "chrome":   ("Google Chrome",),
        "msedge":   ("Microsoft\u2005Edge", "Microsoft Edge", "- Edge"),
        "firefox":  ("Mozilla Firefox", "- Firefox"),
        "brave":    ("Brave", "- Brave"),
        "arc":      ("Arc",),
        "opera":    ("Opera",),
        "vivaldi":  ("Vivaldi",),
        "comet":    ("Comet",),
    }.get(canonical, ("Google Chrome",))

    matches: list[int] = []

    def _cb(hwnd: int, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if any(hint.lower() in title.lower() for hint in title_hints):
            matches.append(hwnd)

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return False

    if not matches:
        return False

    hwnd = matches[0]
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Windows blocks SetForegroundWindow from background processes; nudge
        # via a brief Alt key press to reset the foreground lock.
        try:
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT down
            ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # ALT up
        except Exception:
            pass
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        return True
    except Exception as e:
        log.warning("Foreground browser failed: %s", e)
        return False


def _foreground_browser_window_ctypes(app: str = "") -> bool:
    """ctypes-only fallback that doesn't require pywin32."""
    try:
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        IsWindowVisible = user32.IsWindowVisible
        SetForegroundWindow = user32.SetForegroundWindow

        app_lower = (app or "").strip().lower()
        canonical = _KNOWN_APPS.get(app_lower, app_lower)
        hints = {
            "chrome":   ("Google Chrome",),
            "msedge":   ("Microsoft Edge", "- Edge"),
            "firefox":  ("Mozilla Firefox", "- Firefox"),
            "brave":    ("Brave",),
            "arc":      ("Arc",),
        }.get(canonical, ("Google Chrome",))

        matches: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(hwnd, _lparam):
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if any(h.lower() in title.lower() for h in hints):
                matches.append(int(hwnd))
            return True

        EnumWindows(_enum, 0)
        if not matches:
            return False
        try:
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 0x0002, 0)
        except Exception:
            pass
        SetForegroundWindow(matches[0])
        time.sleep(0.25)
        return True
    except Exception:
        return False


def _launch_app(app: str) -> str:
    """Launch a named application via the shell."""
    if not app:
        log.warning("_launch_app called with empty app name — skipping")
        return "no app specified"
    app_name = app.strip().lower()
    canonical = _KNOWN_APPS.get(app_name, app_name)
    if app_name in _BROWSER_APPS or canonical in _BROWSER_EXECUTABLES or app_name in {"browser", "web browser", "default browser"}:
        return _launch_browser(app_name)
    try:
        subprocess.Popen(app, shell=True)
        time.sleep(1.5)
        return f"launched {app}"
    except Exception as e:
        log.error("_launch_app(%r) failed: %s", app, e)
        return f"failed to launch {app}: {e}"


def _ensure_app_open(app_name: str):
    """Ensure app is open and in the foreground.

    1. Already focused → return immediately.
    2. Open but not focused → restore and bring to front.
    3. Not open → launch it.
    """
    import win32gui, win32con
    app_map = {
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "notepad": "notepad.exe",
        "explorer": "explorer.exe",
        "vscode": "code",
    }
    name_lower = app_name.lower()

    # Already focused?
    fw = win32gui.GetForegroundWindow()
    if name_lower in win32gui.GetWindowText(fw).lower():
        return

    # Open but not focused — find and raise it
    matches: list[int] = []
    def _find(hwnd, _):
        if name_lower in win32gui.GetWindowText(hwnd).lower():
            matches.append(hwnd)
    win32gui.EnumWindows(_find, None)
    if matches:
        win32gui.ShowWindow(matches[0], win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(matches[0])
        time.sleep(1.0)
        return

    # Not open — launch it
    exe = app_map.get(name_lower, app_name)
    subprocess.Popen([exe])
    time.sleep(2.5)

# ══════════════════════════════════════════════════════════════════════════════
# ACTION EXECUTOR
# ══════════════════════════════════════════════════════════════════════════════

def _execute(
    action: dict,
    prefetched_img: Optional[Image.Image] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    t = action.get("type", "")

    if t == "open_app":
        app_name = action.get("app", "")
        launch_url = action.get("url", "")
        if launch_url and (
            app_name.strip().lower() in _BROWSER_APPS
            or _KNOWN_APPS.get(app_name.strip().lower(), app_name) in _BROWSER_EXECUTABLES
        ):
            result = _launch_browser(app_name, url=launch_url)
        else:
            result = _launch_app(app_name)
        # Give the browser window time to gain foreground, then nudge it.
        if launch_url or app_name.strip().lower() in _BROWSER_APPS:
            _foreground_browser_window(app_name)
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "hotkey":
        keys = action.get("keys", [])
        pyautogui.hotkey(*keys)
        time.sleep(STEP_PAUSE)
        result = f"pressed {'+'.join(keys)}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "type":
        text = action.get("text", "")
        pyautogui.typewrite(text, interval=0.04)
        time.sleep(0.2)
        result = f"typed '{text}'"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "press":
        key = action.get("key", "enter")
        pyautogui.press(key)
        time.sleep(0.2)
        result = f"pressed {key}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "wait":
        secs = float(action.get("seconds", 1.0))
        time.sleep(secs)
        return f"waited {secs}s"

    if t == "wait_for_page":
        target = action.get("target", "page")
        query = action.get("query", "")
        ok, message = _wait_for_page_state(target, query=query, progress_cb=progress_cb)
        return message if ok else f"failed: {message}"

    if t == "navigate":
        url = _canonicalize_url(action.get("url", ""))
        # Safety: make sure a browser window is foreground before sending keys.
        # Protects against the Ctrl+L going to Windsurf / an IDE if the browser
        # didn't auto-foreground after launch.
        _foreground_browser_window(action.get("app", "chrome"))
        # Fast path: Ctrl+L to focus URL bar (reliable for any focused browser).
        # Ctrl+L also selects existing text, so a subsequent type replaces it.
        pyautogui.hotkey("ctrl", "l")
        time.sleep(ACTION_SETTLE_DELAY)
        pyautogui.typewrite(url, interval=0.01)
        time.sleep(ACTION_SETTLE_DELAY)
        pyautogui.press("enter")
        time.sleep(ACTION_SETTLE_DELAY)
        result = f"navigated to {url}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "find_video_result":
        query = action.get("query", "")
        hint = action.get("hint", "")
        max_scrolls = int(action.get("max_scrolls", MAX_RESULT_SCROLLS))
        # One concise instruction per scroll — more calls waste tokens & time.
        if query and hint:
            instruction = f"click the first youtube video thumbnail for {query} ({hint})"
        elif query:
            instruction = f"click the first youtube video thumbnail for {query}"
        else:
            instruction = "click the first youtube video thumbnail in the results"
        for scroll_index in range(max_scrolls + 1):
            img = _screenshot()
            if progress_cb:
                progress_cb("step", f"Finding first video {scroll_index + 1}/{max_scrolls + 1}...")
            result_data = _uitars(img, instruction)
            if result_data and result_data.get("action") == "click":
                clicked, _ = _perform_click_from_model(
                    result_data.get("x"),
                    result_data.get("y"),
                    reason=f"video_result:{instruction}",
                )
                if clicked:
                    return f"clicked '{result_data.get('element', instruction)}'"
            if scroll_index < max_scrolls:
                pyautogui.scroll(-500)
                time.sleep(0.6)
        return f"failed: could not find requested video result{f' ({hint})' if hint else ''}"

    if t == "ask_uitars":
        instruction = action.get("instruction", "")

        shortcut = _find_keyboard_shortcut(instruction)
        if shortcut:
            pyautogui.hotkey(*shortcut)
            time.sleep(STEP_PAUSE)
            result = f"keyboard: {'+'.join(shortcut)} (for '{instruction}')"
            if progress_cb:
                progress_cb("step", result)
            return result

        for attempt, candidate in enumerate(_instruction_variants(instruction), start=1):
            img = prefetched_img if attempt == 1 and prefetched_img else _screenshot()
            if progress_cb:
                progress_cb("step", f"Finding '{candidate}' on screen...")
            result_data = _uitars(img, candidate)
            if result_data and result_data.get("action") == "click":
                clicked, _ = _perform_click_from_model(
                    result_data.get("x"),
                    result_data.get("y"),
                    reason=f"uitars:{candidate}",
                )
                if clicked:
                    result = f"clicked '{result_data.get('element', candidate)}'"
                    if progress_cb:
                        progress_cb("step", result)
                    return result
        result = f"could not find: {instruction}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "screenshot":
        # Model-requested mid-loop screenshot for focus verification (RULE 0/7)
        img, ocr = _screenshot_and_ocr()
        short = ocr[:600] if ocr else "(no text detected)"
        return f"Screenshot captured. Visible text:\n{short}"

    if t in ("done", "failed"):
        return action.get("message", t)

    return f"unknown action: {t}"

# ══════════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT THINK  (runs before planning to resolve ambiguity)
# ══════════════════════════════════════════════════════════════════════════════

_THINK_SYSTEM = """\
You are the reasoning core of Whiztant, a Windows AI assistant.

Think through the user's task and output a clean execution strategy.

Reason about:
1. Exact intent.
2. Which app should open.
3. How many steps.
4. Whether the task needs research first.
5. Whether keyboard-only is possible.

Rules:
- Always use the exact app the user named.
- Never substitute one browser for another unless the user asked.
- Canonicalize outdated website names to the current live domain when navigating.
- Settings/theme/display tasks should use Win+I.
- Research tasks should set needs_research to true.
- Refine repeated user wording to the shortest actionable target while preserving the intended control.
- Preserve the final actionable UI target, such as "sign in button".

Return ONLY valid JSON:
{
  "clean_task": "<rewritten task>",
  "app_to_open": "<exact app name user said, or null>",
  "step_count": <int>,
  "entry_point": "<Win+I / Win+E / chrome / arc / comet / etc>",
  "needs_research": <true|false>,
  "research_query": "<YouTube search query or null>",
  "keyboard_only": <true|false>,
  "strategy": "<one sentence>"
}
"""

def _preflight(task: str) -> dict:
    log.info(f"Pre-flight think: {task!r}")
    quick = _quick_preflight(task)
    if quick:
        log.info(f"Quick pre-flight → app={quick.get('app_to_open')} strategy={quick.get('strategy')}")
        return quick

    refined_task = _refine_task_text(task)
    messages = [
        {"role": "system", "content": _THINK_SYSTEM},
        {"role": "user",   "content": f"Task: {refined_task}"},
    ]
    raw = _call_api(OMNI_MODEL, messages, TEMP_THINK, 600, thinking=False)
    result = _parse_json(raw)
    if result:
        result["clean_task"] = _refine_task_text(result.get("clean_task", refined_task))
        log.info(f"Pre-flight → app={result.get('app_to_open')} research={result.get('needs_research')}")
        return result

    log.warning("Pre-flight think failed — using defaults")
    return {
        "clean_task": refined_task,
        "app_to_open": None,
        "step_count": 3,
        "entry_point": "unknown",
        "needs_research": False,
        "research_query": None,
        "keyboard_only": False,
        "strategy": "standard execution",
    }

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — PLANNING
# ══════════════════════════════════════════════════════════════════════════════

_PLAN_SYSTEM = """\
You are the planning brain of Whiztant, a Windows AI assistant.

Absolute rule: never return coordinates. All clicks must use ask_uitars.

If the task requires opening an app, the first step must be {"type":"open_app","app":"<exact app name>"}.
Canonicalize outdated website names to the current live domain.
Refine repeated user wording to the shortest actionable target while preserving the intended control.

Return ONLY valid JSON:
{
  "category": "D",
  "confidence": 0.97,
  "task_summary": "<one line>",
  "steps": ["<step 1>", "<step 2>"],
  "initial_action": {"type": "open_app", "app": "chrome"},
  "requires_uitars": true
}
"""

def _phase1(task: str, preflight: dict) -> Optional[dict]:
    clean_task = preflight.get("clean_task", task)
    app_name = preflight.get("app_to_open", "")
    log.info(f"Phase 1 planning: {clean_task!r}")
    fast_plan = _heuristic_plan(clean_task, preflight)
    if fast_plan and (_extract_requested_url(clean_task)[0] or _extract_click_target(clean_task)):
        log.info("Phase 1 using fast deterministic browser plan")
        return fast_plan
    context = (
        f"Task: {clean_task}\n"
        f"App to open: {app_name or 'none specified'}\n"
        f"Entry point: {preflight.get('entry_point')}\n"
        f"Strategy: {preflight.get('strategy')}\n"
        f"Steps expected: {preflight.get('step_count')}\n"
    )
    category = _entry_category(preflight.get("entry_point"))
    rule_hint = _load_rule_file(category)
    shortcut_hint = shortcuts_loader.load_shortcuts(category)
    sys_prompt = _PLAN_SYSTEM
    if rule_hint:
        sys_prompt += f"\n\n## RULE FILE\n{rule_hint}"
    if shortcut_hint:
        sys_prompt += f"\n\n## Available shortcuts for this task:\n{shortcut_hint}"
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": context},
    ]
    raw = _call_api(OMNI_MODEL, messages, TEMP_PLAN, PLAN_MAX_TOKENS)
    plan = _parse_json(raw)
    if plan:
        plan = _sanitize_plan(plan)
        log.info(f"Plan: {len(plan.get('steps', []))} steps")
    return plan

def _sanitize_plan(plan: dict) -> dict:
    steps = plan.get("steps", [])
    cleaned: list = []
    for step in steps:
        action = step.get("action", step) if isinstance(step, dict) else step
        if isinstance(action, dict) and action.get("type") in ("click", "mouse_click") and ("x" in action or "y" in action):
            desc = action.get("description", action.get("element", "the target element"))
            action = {"type": "ask_uitars", "instruction": f"click {desc}"}
        if isinstance(step, dict) and "action" in step:
            step["action"] = action
            cleaned.append(step)
        else:
            cleaned.append(action)
    plan["steps"] = cleaned
    return plan

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════════════════

def _phase2_system(task: str, plan: dict, rule_content: str, system_context_md: str = "") -> str:
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan.get("steps", [])))
    return f"""\
You are a computer use agent executing tasks on the user's Windows desktop. You control the desktop by choosing actions: clicking, typing, pressing keys, navigating URLs, and taking screenshots to verify state.

## TASK
{task}

## ALL STEPS — COMPLETE EVERY SINGLE ONE
{steps_text}

## RULE FILE
{rule_content}

## FOCUS VERIFICATION RULES (non-negotiable)

RULE 0 — SCREENSHOT-FIRST PROTOCOL
Before issuing any action that sends keyboard input (type, press, hotkey), you MUST:
1. Ensure you have a fresh screenshot from this iteration's Screen OCR.
2. Identify the currently focused element — the element that will receive keyboard input RIGHT NOW.
3. Verify that focused element is the intended target.
4. If it is NOT the intended target → execute FOCUS ESCAPE PROCEDURE before typing.

RULE 1 — FOCUS IDENTIFICATION
Identify the focused element from the current Screen OCR / screenshot context:
- Text cursor visible in a text area, input field, code editor, or terminal → that element has focus.
- IDE/code editors (Windsurf, VSCode, Cursor): if the editor is foregrounded with a file open, ALL keyboard input goes to that file.
- Browser address bar: thin field at top, showing a URL or "Search or type a URL".
- In-page inputs: search bars, form fields — distinct from page background.
If you cannot confidently determine which element is focused, issue a screenshot action first.

RULE 2 — FOCUS ESCAPE PROCEDURE
When the focused element is NOT your intended target:
1. Do NOT type anything.
2. Identify the target application window (title bar, icon, visible UI).
3. Issue ask_uitars to click the title bar of the target window (brings it to foreground without activating an inner element).
4. If the app is not visible, issue ask_uitars to click its taskbar icon.
5. Issue a screenshot action and verify: title bar is active, no unintended input field is focused.
6. Issue ask_uitars to click the specific element that should receive input.
7. Issue another screenshot action and confirm cursor is in the correct field.
8. Only then issue type.

RULE 3 — APPLICATION SWITCHING
Never use hotkey Alt+Tab to switch applications unless you have confirmed no text field is currently focused.
Safe method: click the application icon in the taskbar via ask_uitars, or click a non-interactive area of the target window (title bar, toolbar, empty padding).

RULE 4 — BROWSER NAVIGATION PROCEDURE
For any task involving browser navigation:
1. screenshot → identify if target browser is the active foreground window.
   - If not → ask_uitars to click browser icon in taskbar.
   - screenshot → verify browser is now active.
2. ask_uitars to click the URL/address bar.
   - screenshot → verify cursor is in the URL bar.
3. type the URL → press enter.
   - screenshot → verify page started loading.
4. screenshot → verify page is fully loaded.
5. ask_uitars to click the target in-page element.
   - screenshot → verify element is focused.
6. type → press enter → screenshot → verify expected result.
Use the navigate action as a shortcut only when you have confirmed the browser already has focus.

RULE 5 — TASK EXECUTION LOOP
For every discrete action:
screenshot → identify current state → identify focused element → compare to intended target → redirect focus if needed → execute action → verify outcome via next iteration's Screen OCR → proceed or retry.
If the outcome does not match the expected state:
- Do NOT continue to the next step.
- Analyze what went wrong.
- Re-execute from the last verified correct state.

RULE 6 — IDE CONFLICT HANDLING
If Windsurf, VSCode, Cursor, or any IDE is open with an active file and cursor focus:
- Detection: code editor is foregrounded, file tab selected, cursor blinking in editor pane.
- Never type a URL or any task input while this state is active.
- Remediation: issue ask_uitars to click a blank area of the desktop background (outside all windows), then screenshot to confirm no text field is focused, then proceed with the target app.

RULE 7 — VERIFICATION CHECKPOINTS
Before marking any subtask as complete, take a screenshot and verify expected state is visible in OCR.
If verification fails → retry the subtask from scratch, not from an intermediate state.

ANTI-PATTERNS — NEVER DO THESE
- Do not issue type without confirming the correct element has focus via screenshot.
- Do not assume the application you last clicked is still in focus.
- Do not use Alt+Tab / hotkey app-switching without confirming no text field is active.
- Do not proceed to the next step after a failed verification — always retry the failed step.
- Do not infer focus from task context ("I just clicked the URL bar so it must be focused") — always confirm with a screenshot or OCR content.

## EXECUTION RULES
1. Never produce x/y coordinates — all clicks go through ask_uitars.
2. Never skip steps.
3. Prefer keyboard shortcuts before ask_uitars for known shortcuts (Ctrl+L for URL bar, etc.).
4. Do not declare done until OCR confirms all steps complete.
5. Return one JSON object only.
6. If the current action completes a listed step, include "completed_step": "<exact step text>".

## AVAILABLE ACTIONS
Open app:          {{"type":"open_app","app":"chrome"}}
Keyboard shortcut: {{"type":"hotkey","keys":["ctrl","l"]}}
Type text:         {{"type":"type","text":"youtube.com"}}
Press key:         {{"type":"press","key":"enter"}}
Wait:              {{"type":"wait","seconds":2}}
Navigate URL:      {{"type":"navigate","url":"https://youtube.com"}}
Find+click visual: {{"type":"ask_uitars","instruction":"click the search bar"}}
Verify focus/state:{{"type":"screenshot"}}
All steps done:    {{"type":"done","message":"Video is playing"}}
Unrecoverable:     {{"type":"failed","message":"reason"}}
{(chr(10) + "## SYSTEM CONTEXT (installed apps, browsers, paths — read before executing)" + chr(10) + system_context_md + chr(10)) if system_context_md else ""}"""

def _phase2_loop(
    task: str,
    plan: dict,
    rule_content: str,
    progress_cb: Optional[Callable] = None,
    system_context_md: str = "",
) -> str:
    import hashlib as _hashlib
    import time as _time_mod
    from core import guardrails as _gr
    from core.ws_bridge import send_agent_step_v2, send_agent_blocked, send_agent_done
    from core.toast import toast_action_blocked

    task_id = f"task_{int(_time_mod.time())}"
    log.info("Phase 2 — execution loop starting (task_id=%s)", task_id)
    steps = plan.get("steps", [])
    completed: list = []
    last_result = "Execution started"
    system = _phase2_system(task, plan, rule_content, system_context_md)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    next_context_future = executor.submit(_screenshot_and_ocr)
    loop_history: list = []  # (action_type, screenshot_hash) tuples for loop detection
    try:
        for iteration in range(1, MAX_LOOP_STEPS + 1):
            log.info(f"Loop {iteration}/{MAX_LOOP_STEPS} — {len(completed)}/{len(steps)} done")
            try:
                prefetched_img, ocr_text = next_context_future.result(timeout=5)
            except Exception as e:
                log.warning(f"Pre-fetch failed: {e} — taking fresh screenshot")
                prefetched_img, ocr_text = _screenshot_and_ocr()
            done_txt = "\n".join(f"  ✓ {s}" for s in completed) or "  (none yet)"
            todo_txt = "\n".join(f"  → {s}" for s in steps if s not in completed) or "  (all done)"
            user_msg = (
                f"Progress: {len(completed)}/{len(steps)}\n\n"
                f"Done:\n{done_txt}\n\n"
                f"Remaining:\n{todo_txt}\n\n"
                f"Screen OCR:\n{ocr_text[:1600] or '(none)'}\n\n"
                f"Last result: {last_result}\n\n"
                f"Next action (JSON only):"
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ]
            next_context_future = executor.submit(_screenshot_and_ocr)
            raw = _call_api(OMNI_MODEL, messages, TEMP_EXEC, EXEC_MAX_TOKENS)
            action = _parse_json(raw)
            if not action:
                log.error(f"No valid action: {raw[:150]}")
                break
            if action.get("type") == "done":
                message = action.get("message", "Task completed")
                if progress_cb:
                    progress_cb("done", message)
                send_agent_done(task_id, message, success=True)
                return message
            if action.get("type") == "failed":
                message = f"Task failed: {action.get('message', 'unknown')}"
                if progress_cb:
                    progress_cb("error", message)
                send_agent_done(task_id, message, success=False)
                return message

            # --- Guardrail: destructive action check ---
            action_text = str(action.get("text", "")) + " " + str(action.get("type", ""))
            is_dest, dest_reason = _gr.is_destructive_action(action_text)
            if is_dest:
                log.warning("Guardrail blocked destructive action: %s", dest_reason)
                toast_action_blocked(dest_reason)
                send_agent_blocked(task_id, dest_reason, undoable=bool(completed))
                if progress_cb:
                    progress_cb("error", f"Blocked: {dest_reason}")
                return f"Action blocked by safety guardrail: {dest_reason}"

            # --- Guardrail: coordinate bounds check ---
            if action.get("type") in ("click", "double_click", "right_click", "drag"):
                coords = action.get("coordinates") or action.get("coordinate", [])
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    x, y = int(coords[0]), int(coords[1])
                    valid, coord_reason = _gr.validate_coordinates(x, y)
                    if not valid:
                        log.warning("Guardrail blocked out-of-bounds coords: %s", coord_reason)
                        send_agent_blocked(task_id, coord_reason, undoable=False)
                        break

            # --- Loop detection ---
            img_hash = _gr.screenshot_hash(prefetched_img if isinstance(prefetched_img, bytes) else b"")
            loop_history.append((action.get("type", ""), img_hash))
            if _gr.detect_loop(loop_history):
                msg = f"Loop detected at step {iteration} — aborting"
                log.warning(msg)
                send_agent_blocked(task_id, "loop_detected", undoable=bool(completed))
                if progress_cb:
                    progress_cb("error", msg)
                return msg

            remaining = [s for s in steps if s not in completed]
            # Emit step progress to overlay
            current_step_label = remaining[0] if remaining else "finalizing"
            send_agent_step_v2(task_id, iteration, len(steps), action.get("type", ""), current_step_label)
            if progress_cb:
                progress_cb("step", f"Step {len(completed)+1}/{len(steps)}: {current_step_label}")

            last_result = _execute(action, prefetched_img=prefetched_img, progress_cb=None)
            log.info(f"Result: {last_result}")

            completed_step = action.get("completed_step")
            if isinstance(completed_step, str) and completed_step in steps and completed_step not in completed:
                completed.append(completed_step)
            elif remaining and not re.search(r"could not find|failed|unknown action", last_result, re.IGNORECASE):
                completed.append(remaining[0])

            time.sleep(0.2)
    finally:
        executor.shutdown(wait=False)
    limit_msg = f"Reached {MAX_LOOP_STEPS}-step limit — task may be incomplete"
    send_agent_done(task_id, limit_msg, success=False)
    return limit_msg

def _research_pipeline(
    task: str,
    progress_cb: Optional[Callable] = None,
) -> Optional[dict]:
    """
    Handles pure research/text tasks using Qwen (no screen required).
    Returns None so execution falls through to the standard planning pipeline,
    which handles the answer via browser/search actions.
    """
    try:
        raw = _call_api(
            OMNI_MODEL,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Answer the user's question "
                        "concisely in 1-3 sentences. No markdown."
                    ),
                },
                {"role": "user", "content": task},
            ],
            float(os.getenv("QWEN_EXECUTION_TEMP", "0.2")),
            256,
        )
        if raw:
            log.info("_research_pipeline answered: %s", raw[:120])
    except Exception as e:
        log.error("_research_pipeline failed: %s", e)
    # Return None so caller falls through to standard UI-based planning
    return None

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def run_agent_task(
    task: str,
    toast: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    """
    Entry point for agent tasks.
    Uses the new two-path architecture: UIA (primary) → Vision (fallback).
    """
    log.info(f"=== Agent task: {task!r} ===")
    if toast:
        toast("Whiztant", "Thinking…")
    if progress_cb:
        progress_cb("step", "Understanding your task...")

    # Run the two-path agent loop (preflight handled internally)
    return run_agent_loop(task, toast=toast, progress_cb=progress_cb)


def call_qwen_planner(
    task: str,
    toast: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    return run_agent_task(task, toast=toast, progress_cb=progress_cb)


_lock    = threading.Lock()
_running = False


def run_agent_task_async(
    task: str,
    toast: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
) -> None:
    global _running
    if _running:
        log.warning("Agent already running — dropping task")
        if toast:
            toast("Whiztant", "Agent busy — please wait")
        if progress_cb:
            progress_cb("error", "Agent busy — please wait")
        return
    def _worker():
        global _running
        with _lock:
            _running = True
        try:
            run_agent_task(task, toast, progress_cb)
        except Exception as e:
            log.error(f"Agent worker error: {e}", exc_info=True)
            if progress_cb:
                progress_cb("error", str(e)[:100])
            if toast:
                toast("Whiztant Error", str(e)[:80])
        finally:
            _running = False
    threading.Thread(target=_worker, daemon=True, name="whiztant-agent").start()


# ══════════════════════════════════════════════════════════════════════════════
# COMPATIBILITY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_default_browser_command() -> str:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        prog_id_lower = prog_id.lower()
        if "arc"      in prog_id_lower: return "arc"
        if "chrome"   in prog_id_lower: return "chrome"
        if "firefox"  in prog_id_lower: return "firefox"
        if "msedge"   in prog_id_lower or "edge" in prog_id_lower: return "msedge"
        if "brave"    in prog_id_lower: return "brave"
        if "opera"    in prog_id_lower: return "opera"
        if "vivaldi"  in prog_id_lower: return "vivaldi"
        return "start"
    except Exception:
        return "start"


def _pyautogui():
    return pyautogui


def _safe_pyautogui_call(fn: Callable[[], Any]) -> Optional[str]:
    try:
        fn()
        return None
    except Exception as e:
        return str(e)


def _list_monitors() -> list[dict]:
    with mss() as sct:
        return [dict(monitor) for monitor in sct.monitors[1:]]


def _coerce_display_index(display) -> int:
    monitors = _list_monitors()
    total = max(1, len(monitors))
    try:
        index = int(display)
    except Exception:
        index = 1
    return min(max(index, 1), total)


def _display_bounds(display: int) -> Tuple[int, int, int, int]:
    monitors = _list_monitors()
    if not monitors:
        width, height = pyautogui.size()
        return 0, 0, width, height
    monitor = monitors[_coerce_display_index(display) - 1]
    return int(monitor["left"]), int(monitor["top"]), int(monitor["width"]), int(monitor["height"])


def _current_cursor_display() -> int:
    try:
        x_pos, y_pos = pyautogui.position()
    except Exception:
        return 1
    for index, _monitor in enumerate(_list_monitors(), start=1):
        left, top, width, height = _display_bounds(index)
        if left <= x_pos < left + width and top <= y_pos < top + height:
            return index
    return 1


def _xy_for_display(display: int, x: float, y: float) -> Optional[Tuple[int, int]]:
    left, top, width, height = _display_bounds(display)
    if width <= 0 or height <= 0:
        return None
    x_norm = min(max(float(x), 0.0), 1.0)
    y_norm = min(max(float(y), 0.0), 1.0)
    return int(left + x_norm * width), int(top + y_norm * height)


def _run_screenshot_capture_once() -> list[str]:
    target_dir = Path(state.SCREENSHOT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    with mss() as sct:
        for index, monitor in enumerate(sct.monitors[1:], start=1):
            raw = sct.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            file_path = target_dir / state.SCREENSHOT_FILENAME_FMT.format(index=index)
            image.save(file_path)
            paths.append(str(file_path))
    state._agent_latest_screenshot_paths = paths
    return paths


def safe_click(x: int, y: int, _reason: str = "") -> bool:
    return _perform_click(x, y, reason=_reason or "safe_click")[0]


def safe_type(text: str, _reason: str = "") -> bool:
    return _safe_pyautogui_call(lambda: pyautogui.typewrite(text, interval=0.02)) is None


def safe_press(key: str, _reason: str = "") -> bool:
    return _safe_pyautogui_call(lambda: pyautogui.press(key)) is None


def _take_screenshot() -> Tuple[str, Tuple[int, int], Tuple[int, int]]:
    ctypes.windll.user32.SetProcessDPIAware()
    physical_w = ctypes.windll.user32.GetSystemMetrics(0)
    physical_h = ctypes.windll.user32.GetSystemMetrics(1)

    try:
        img = _screenshot()
    except Exception:
        img = ImageGrab.grab(all_screens=False)

    cap_w, cap_h = img.size
    max_w = 1280
    if cap_w > max_w:
        scale = max_w / float(cap_w)
        img = img.resize((max_w, int(cap_h * scale)), Image.LANCZOS)
    resized_w, resized_h = img.size

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return b64, (resized_w, resized_h), (physical_w, physical_h)


def capture_window_screenshot(*_args, **_kwargs):
    return _take_screenshot()


def execute_action_in_window_context(action: dict, *_args, **_kwargs) -> dict:
    result = _execute(action)
    success = not re.search(r"could not find|failed|unknown action", result, re.IGNORECASE)
    return {"success": success, "result": result}


async def _execute_single_step(
    step_text: str,
    screenshot_b64: str,
    physical_size: Tuple[int, int],
    speak_fn=None,
    transcribe_fn=None,
    max_actions: int = 5,
    rule_content: Optional[str] = None,
    browser_hwnd: Optional[int] = None,
) -> Dict:
    action_history: List[Dict] = []
    try:
        img_bytes = base64.b64decode(screenshot_b64)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        log.warning(f"Could not decode provided screenshot: {e} — taking fresh one")
        img = _screenshot()
    shortcut = _find_keyboard_shortcut(step_text)
    if shortcut:
        try:
            pyautogui.hotkey(*shortcut)
            time.sleep(STEP_PAUSE)
            action_history.append({"action": "hotkey", "keys": shortcut})
            return {"success": True, "actions": action_history, "error": None}
        except Exception as e:
            log.warning(f"Shortcut execution failed: {e}")
    result = _uitars(img, step_text)
    if result and result.get("action") == "click":
        clicked, message = _perform_click_from_model(result.get("x"), result.get("y"), reason=f"step:{step_text}")
        if clicked:
            action_history.append({"action": "click", "coordinate": [result.get("x"), result.get("y")]})
            log.info(f"Clicked '{result.get('element', step_text)}' using validated coordinates")
            return {"success": True, "actions": action_history, "error": None}
        return {"success": False, "actions": action_history, "error": message}

    return {
        "success": False,
        "actions": action_history,
        "error": f"UI-TARS could not locate target: {step_text}",
    }
