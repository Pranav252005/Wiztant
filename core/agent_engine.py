"""
core/agent_engine.py — Shared agent orchestration constants and utilities.
"""
from __future__ import annotations

import ast
import base64
import json
import logging
import os
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from PIL import Image

log = logging.getLogger("core.agent_engine")

OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
_client = OpenAI(
    api_key=OR_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
)

def _load_model_setting(key: str, default: str) -> str:
    try:
        import json
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return os.getenv(key, default)

OMNI_MODEL = _load_model_setting("AGENT_OMNI_MODEL", "google/gemini-3-flash-preview")
EXECUTOR_MODEL = _load_model_setting("AGENT_EXECUTOR_MODEL", "bytedance/ui-tars-1.5-7b")

TEMP_THINK = float(os.getenv("QWEN_THINK_TEMP", "0.1"))
TEMP_PLAN = float(os.getenv("QWEN_PLANNING_TEMP", "0.1"))
TEMP_EXEC = float(os.getenv("QWEN_EXECUTION_TEMP", "0.15"))
TEMP_TARS = float(os.getenv("UITARS_TEMP", "0.3"))

MAX_LOOP_STEPS = 20
STEP_PAUSE = 0.45
ACTION_SETTLE_DELAY = 0.12
BROWSER_LAUNCH_DELAY = 2.0
PAGE_LOAD_TIMEOUT = 10.0
LOAD_POLL_SECONDS = 0.5
MAX_RESULT_SCROLLS = 4
GROUND_IMG_MAX = int(os.getenv("AGENT_GROUND_IMG_MAX", "960"))
OCR_MAX_LINES = 60
THINK_MAX_TOKENS = 512
PLAN_MAX_TOKENS = 1200
EXEC_MAX_TOKENS = 220
TARS_MAX_TOKENS = 150

ACTION_SETTLE_DELAY  = 0.12
BROWSER_LAUNCH_DELAY = 2.0
PAGE_LOAD_TIMEOUT    = 10.0
LOAD_POLL_SECONDS    = 0.5
OCR_MAX_LINES        = 60


def call_api(model: str, messages: list, temperature: float, max_tokens: int, thinking: bool = False) -> str:
    try:
        kwargs: dict[str, Any] = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        if thinking is False:
            kwargs["extra_body"] = {"include_reasoning": False}
        resp = _client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("API call failed: %s", e)
        return ""


def parse_json(text: str) -> Optional[dict]:
    if not text:
        return None
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```json\s*|```\s*", "", text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(candidate)
            except Exception:
                pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except Exception:
            pass
    return None


def to_base64(img: Image.Image, max_side: int = GROUND_IMG_MAX) -> str:
    w, h = img.size
    max_s = max(w, h)
    if max_s > max_side:
        scale = max_side / max_s
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


# ── App registry (cross-platform) ───────────────────────────────────────────────
KNOWN_APPS: Dict[str, Optional[str]] = {
    "chrome": "chrome", "google chrome": "chrome", "arc": "arc", "arc browser": "arc",
    "firefox": "firefox", "edge": "msedge", "microsoft edge": "msedge",
    "brave": "brave", "opera": "opera", "vivaldi": "vivaldi", "comet": "comet",
    "manus": "manus", "manus ai": "manus", "cursor": "cursor", "windsurf": "windsurf",
    "claude": "claude", "vscode": "code", "vs code": "code", "visual studio code": "code",
    "terminal": "terminal", "windows terminal": "wt", "cmd": "cmd",
    "powershell": "powershell", "git bash": "bash", "postman": "postman",
    "docker": "docker", "notion": "notion", "obsidian": "obsidian",
    "notepad": "notepad", "notepad++": "notepad++", "word": "winword",
    "excel": "excel", "powerpoint": "powerpnt", "outlook": "outlook",
    "slack": "slack", "discord": "discord", "teams": "teams",
    "zoom": "zoom", "telegram": "telegram", "whatsapp": "whatsapp",
    "spotify": "spotify", "vlc": "vlc", "explorer": "explorer",
    "file explorer": "explorer", "files": "files", "file manager": "files",
    "task manager": None, "settings": None, "calculator": "calc",
    "paint": "mspaint", "snipping tool": "snippingtool",
    "text editor": "gedit",
}

BROWSER_APPS = {
    "chrome", "google chrome", "arc", "arc browser", "firefox",
    "edge", "microsoft edge", "brave", "opera", "vivaldi", "comet",
}

CATEGORY_TO_FILE: Dict[str, Tuple[str, ...]] = {
    "A": ("apps_microsoft.md", "agent_navigation.md"),
    "B": ("agent_navigation.md", "apps_microsoft.md"),
    "C": ("apps_creative.md", "apps_browsers.md"),
    "D": ("browser_navigation_spec.md", "apps_browsers.md", "websites.md"),
    "E": ("apps_creative.md", "agent_navigation.md"),
    "F": ("apps_microsoft.md", "apps_creative.md"),
    "G": ("agent_universal_optimize.md", "agent_navigation.md"),
}

SITE_URLS: Dict[str, str] = {
    "twitter": "https://x.com", "x": "https://x.com",
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "google": "https://www.google.com", "github": "https://github.com",
    "linkedin": "https://www.linkedin.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "reddit": "https://www.reddit.com",
}

SITE_ALIASES: Dict[str, str] = {
    "twitter.com": "x.com", "www.twitter.com": "x.com", "twitter": "x.com",
}

# ── Text utilities ────────────────────────────────────────────────────────────
def canonicalize_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    # Handle twitter/x canonicalization for both with and without protocol
    cleaned = re.sub(r"^(?:https?://)?(?:www\.)?twitter\.com", "https://x.com", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^https?://www\.", "https://", cleaned, flags=re.IGNORECASE)
    if not re.match(r"^https?://", cleaned, flags=re.IGNORECASE):
        cleaned = f"https://{cleaned.lstrip('/')}"
    return cleaned


def canonical_site_label(url: str) -> str:
    canonical = canonicalize_url(url)
    return re.sub(r"^https?://", "", canonical, flags=re.IGNORECASE).split("/")[0]


def refine_element_target(target: str) -> str:
    cleaned = (target or "").strip().lower()
    cleaned = re.sub(r"\b(?:the|that|this)\b", "", cleaned)
    cleaned = re.sub(r"\blog\s*in\b", "sign in", cleaned)
    cleaned = re.sub(r"\bsign\s*in\s*(?:option|link|cta|page)\b", "sign in button", cleaned)
    cleaned = re.sub(r"\bsign\s*in\b", "sign in button", cleaned)
    cleaned = re.sub(r"\bbutton\s+button\b", "button", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def refine_task_text(task: str) -> str:
    refined = (task or "").strip()
    refined = re.sub(r"\b(?:please|kindly|just|for me|you know)\b", "", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\b(?:(?:go|navigate|browse|visit)\s+to|open)\s+twitter(?:\.com)?\b", lambda m: m.group(0).replace("twitter.com", "x.com").replace("Twitter", "x.com").replace("twitter", "x.com"), refined, flags=re.IGNORECASE)
    refined = re.sub(r"\b(?:www\.)?twitter\.com\b", "x.com", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\bclick on\b", "click", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\bsign\s*in\s*(?:option|link|cta)\b", "sign in button", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\blog\s*in\b", "sign in", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\s+", " ", refined).strip(" .")
    return refined


def is_research_task(task: str) -> bool:
    keywords = [
        "search", "find", "look up", "what is", "who is", "how does",
        "explain", "summarise", "summarize", "tell me about", "research",
        "calculate", "convert", "translate", "define", "weather",
    ]
    return any(kw in task.lower().strip() for kw in keywords)


# ── Keyboard shortcuts ──────────────────────────────────────────────────────────
KEYBOARD_SHORTCUTS: Dict[str, List[str]] = {
    "open settings": ["win", "i"],
    "open file explorer": ["win", "e"],
    "open run dialog": ["win", "r"],
    "address bar": ["ctrl", "l"],
    "focus address": ["ctrl", "l"],
    "url bar": ["ctrl", "l"],
    "new tab": ["ctrl", "t"],
    "close tab": ["ctrl", "w"],
    "refresh": ["f5"],
    "refresh page": ["f5"],
    "go back": ["alt", "left"],
    "select all": ["ctrl", "a"],
    "copy": ["ctrl", "c"],
    "paste": ["ctrl", "v"],
    "undo": ["ctrl", "z"],
    "search bar": ["ctrl", "f"],
    "search bar focus": ["ctrl", "f"],
    "settings search focus": ["ctrl", "f"],
    "youtube search": ["s"],
    "youtube search focus": ["s"],
    "play pause": ["k"],
    "play pause video": ["k"],
    "fullscreen": ["f"],
    "mute": ["m"],
    "new email": ["ctrl", "n"],
    "send email": ["ctrl", "enter"],
    "reply email": ["ctrl", "r"],
    "slack switcher": ["ctrl", "k"],
    "slack quick switcher": ["ctrl", "k"],
    "new folder": ["ctrl", "shift", "n"],
    "task manager": ["ctrl", "shift", "escape"],
    "screenshot": ["win", "shift", "s"],
}


def find_keyboard_shortcut(instruction: str) -> Optional[List[str]]:
    lowered = (instruction or "").strip().lower()
    return KEYBOARD_SHORTCUTS.get(lowered)


# ── Pre-flight / Planning helpers ─────────────────────────────────────────────
def extract_requested_app(task: str) -> Optional[str]:
    t = (task or "").lower()
    for name in sorted(KNOWN_APPS.keys(), key=len, reverse=True):
        if name in t:
            return name
    return None


def extract_requested_url(task: str) -> Tuple[Optional[str], str]:
    t = (task or "").lower()
    for label, url in sorted(SITE_URLS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if label in t:
            return url, label
    # Raw URL pattern
    m = re.search(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?", task)
    if m:
        raw = m.group(0)
        return canonicalize_url(raw), canonical_site_label(raw)
    return None, ""


def extract_click_target(task: str) -> Optional[str]:
    m = re.search(r"\bclick\b.+?(?:on\s+)?(.+)", task, re.IGNORECASE)
    if m:
        return m.group(1).strip(" .")
    return None


def quick_preflight(task: str) -> Optional[dict]:
    refined = refine_task_text(task)
    lowered = refined.lower()
    if is_research_task(refined):
        return None
    app_name = extract_requested_app(refined)
    url, site_label = extract_requested_url(refined)
    click_target = extract_click_target(refined)
    browser_like = bool(url or click_target) or any(
        word in lowered for word in (
            "navigate", "go to", "visit", "open chrome", "open edge",
            "open firefox", "open arc", "open browser",
        )
    )
    if not browser_like:
        return None
    step_count = len([item for item in (app_name, url, click_target) if item]) or 1
    parts = []
    if app_name:
        parts.append(f"open {app_name}")
    if site_label:
        parts.append(f"navigate to {site_label}")
    if click_target:
        parts.append(f"click {click_target}")
    strategy = "; ".join(parts) if parts else "browser automation"
    return {
        "clean_task": refined,
        "app_to_open": app_name,
        "step_count": step_count,
        "entry_point": app_name or "browser",
        "needs_research": False,
        "research_query": None,
        "keyboard_only": bool(url and not click_target),
        "strategy": strategy,
    }


def entry_category(entry_point: Optional[str]) -> str:
    value = (entry_point or "").strip().lower()
    if value in {"win+i", "settings"}:
        return "A"
    if value in {"win+e", "explorer", "file explorer", "files", "file manager"}:
        return "B"
    if value in {"powershell", "regedit", "registry", "task manager", "terminal"}:
        return "G"
    if value in {"slack", "outlook", "teams", "discord", "telegram", "whatsapp", "zoom"}:
        return "F"
    if value in {"cursor", "windsurf", "code", "vscode", "vs code", "visual studio code"}:
        return "E"
    if value in BROWSER_APPS or value in {"browser", "web browser"}:
        return "D"
    return "C"


# ── System prompts ────────────────────────────────────────────────────────────
THINK_SYSTEM = """\
You are the reasoning core of Wiztant, a cross-platform AI assistant.

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
- Settings/theme/display tasks should use Win+I on Windows, settings app on Linux.
- Research tasks should set needs_research to true.
- Refine repeated user wording to the shortest actionable target while preserving the intended control.
- Preserve the final actionable UI target, such as "sign in button".

Return ONLY valid JSON:
{
  "clean_task": "<rewritten task>",
  "app_to_open": "<exact app name user said, or null>",
  "step_count": <int>,
  "entry_point": "<ctrl+alt+t / win+e / chrome / arc / settings / files etc>",
  "needs_research": <true|false>,
  "research_query": "<search query or null>",
  "keyboard_only": <true|false>,
  "strategy": "<one sentence>"
}
"""

PLAN_SYSTEM = """\
You are the planning brain of Wiztant, a cross-platform AI assistant.

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
