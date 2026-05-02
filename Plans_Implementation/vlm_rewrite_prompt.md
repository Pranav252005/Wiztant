# Whiztant `core/vlm.py` — Full Rewrite Specification

> **Status:** Optimized from the real existing file. Every section below reflects
> what the production file must contain. Do not simplify or omit.

---

## OVERVIEW

`core/vlm.py` is the Whiztant agent runtime. It uses a **two-phase architecture**:

- **Pre-flight** → resolve what app to open and build an execution plan (fast
  heuristic or LLM-generated)
- **Phase 2 loop** → step-by-step executor that reads the screen (OCR + UIA
  tree) and calls the model each iteration to decide the next action

The two-path **UIA primary / Vision fallback** runs *within* each Phase 2
iteration:

- PATH 1: `pywinauto` accessibility tree → text-only LLM (fast, no image)
- PATH 2: screenshot → multimodal LLM → optional UI-TARS pixel executor

---

## STEP 1 — IMPORTS

```python
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
import winreg
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pyautogui
from openai import OpenAI
from mss import mss
from PIL import Image, ImageGrab
from io import BytesIO

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.getenv(
        "TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False

import core as state
from core import shortcuts_loader
```

---

## STEP 2 — LOGGING & DPI

```python
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("data/whiztant.log",   encoding="utf-8"),
        logging.FileHandler("data/agent_debug.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("core.vlm")

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.05

# DPI awareness — try per-monitor first, fall back to system aware
_DPI_AWARENESS_SET = False
if not _DPI_AWARENESS_SET:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _DPI_AWARENESS_SET = True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            _DPI_AWARENESS_SET = True
        except Exception:
            pass
```

---

## STEP 3 — MODEL CONFIGURATION

```python
_OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
_client = OpenAI(
    api_key=_OR_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://whiztant.com",
        "X-Title": "Whiztant",
    },
)

OMNI_MODEL     = os.getenv("AGENT_OMNI_MODEL",     "xiaomi/mimo-v2-omni")
EXECUTOR_MODEL = os.getenv("AGENT_EXECUTOR_MODEL", "bytedance/ui-tars-1.5-7b")

TEMP_THINK = float(os.getenv("QWEN_THINK_TEMP",    "0.1"))
TEMP_PLAN  = float(os.getenv("QWEN_PLANNING_TEMP", "0.1"))
TEMP_EXEC  = float(os.getenv("QWEN_EXECUTION_TEMP","0.15"))
TEMP_TARS  = float(os.getenv("UITARS_TEMP",        "0.3"))

MAX_LOOP_STEPS      = int(os.getenv("AGENT_MAX_STEPS", "20"))
STEP_PAUSE          = 0.45
ACTION_SETTLE_DELAY = 0.12
BROWSER_LAUNCH_DELAY = 2.0
PAGE_LOAD_TIMEOUT   = 10.0
LOAD_POLL_SECONDS   = 0.5
MAX_RESULT_SCROLLS  = 4
GROUND_IMG_MAX      = int(os.getenv("AGENT_GROUND_IMG_MAX", "960"))
OCR_MAX_LINES       = 60
THINK_MAX_TOKENS    = 512
PLAN_MAX_TOKENS     = 1200
EXEC_MAX_TOKENS     = 220
TARS_MAX_TOKENS     = 150
```

---

## STEP 4 — LOOKUP DATA

### 4a. Known apps (`_KNOWN_APPS`)
Maps user-visible names to process/executable names. Must include every browser,
dev tool, productivity app, and system utility. Key entries:

```python
_KNOWN_APPS: dict[str, Optional[str]] = {
    # Browsers
    "chrome": "chrome", "google chrome": "chrome",
    "arc": "arc", "arc browser": "arc",
    "firefox": "firefox",
    "edge": "msedge", "microsoft edge": "msedge",
    "brave": "brave", "opera": "opera", "vivaldi": "vivaldi",
    "comet": "comet",
    # Dev tools
    "cursor": "cursor", "windsurf": "windsurf",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "terminal": "wt", "windows terminal": "wt",
    "cmd": "cmd", "powershell": "powershell", "git bash": "bash",
    "postman": "postman", "docker": "docker",
    # Productivity
    "notion": "notion", "obsidian": "obsidian",
    "notepad": "notepad", "notepad++": "notepad++",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook",
    # Communication
    "slack": "slack", "discord": "discord", "teams": "teams",
    "zoom": "zoom", "telegram": "telegram", "whatsapp": "whatsapp",
    # Media
    "spotify": "spotify", "vlc": "vlc",
    # System
    "explorer": "explorer", "file explorer": "explorer",
    "task manager": None, "settings": None,
    "calculator": "calc", "paint": "mspaint",
    "snipping tool": "snippingtool",
    # AI apps
    "claude": "claude", "manus": "manus", "manus ai": "manus",
}
```

### 4b. Keyboard shortcuts (`KEYBOARD_SHORTCUTS`)
Maps plain-English descriptions → `pyautogui.hotkey` key lists.

```python
KEYBOARD_SHORTCUTS: dict[str, list[str]] = {
    "open settings":        ["win", "i"],
    "open file explorer":   ["win", "e"],
    "open run dialog":      ["win", "r"],
    "address bar":          ["ctrl", "l"],
    "focus address":        ["ctrl", "l"],
    "url bar":              ["ctrl", "l"],
    "new tab":              ["ctrl", "t"],
    "close tab":            ["ctrl", "w"],
    "refresh":              ["f5"],
    "refresh page":         ["f5"],
    "go back":              ["alt", "left"],
    "select all":           ["ctrl", "a"],
    "copy":                 ["ctrl", "c"],
    "paste":                ["ctrl", "v"],
    "undo":                 ["ctrl", "z"],
    "search bar":           ["ctrl", "f"],
    "search bar focus":     ["ctrl", "f"],
    "settings search focus":["ctrl", "f"],
    "youtube search":       ["s"],
    "youtube search focus": ["s"],
    "play pause":           ["k"],
    "play pause video":     ["k"],
    "fullscreen":           ["f"],
    "mute":                 ["m"],
    "new email":            ["ctrl", "n"],
    "send email":           ["ctrl", "enter"],
    "reply email":          ["ctrl", "r"],
    "slack switcher":       ["ctrl", "k"],
    "new folder":           ["ctrl", "shift", "n"],
    "task manager":         ["ctrl", "shift", "escape"],
    "screenshot":           ["win", "shift", "s"],
}
```

### 4c. Browser / site data

```python
_BROWSER_APPS = {
    "chrome", "google chrome", "arc", "arc browser",
    "firefox", "edge", "microsoft edge", "brave", "opera", "vivaldi", "comet",
}

_SITE_URLS: dict[str, str] = {
    "twitter": "https://x.com",  "x": "https://x.com",
    "youtube": "https://www.youtube.com",
    "gmail":   "https://mail.google.com",
    "google":  "https://www.google.com",
    "github":  "https://github.com",
    "linkedin":"https://www.linkedin.com",
    "facebook":"https://www.facebook.com",
    "instagram":"https://www.instagram.com",
    "reddit":  "https://www.reddit.com",
}

_SITE_ALIASES: dict[str, str] = {
    "twitter.com": "x.com", "www.twitter.com": "x.com", "twitter": "x.com",
}

_BROWSER_EXECUTABLES: dict[str, str] = {
    "chrome": "chrome.exe", "arc": "Arc.exe",
    "firefox": "firefox.exe", "msedge": "msedge.exe",
}

_BROWSER_PATHS: dict[str, tuple[str, ...]] = {
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
    "arc": (
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Arc", "Arc.exe"),
        r"C:\Program Files\Arc\Arc.exe",
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
```

### 4d. Category → rule files

```python
_RULES_DIR = Path(__file__).parent.parent / "agent_rules"

_CATEGORY_TO_FILE: dict[str, tuple[str, ...]] = {
    "A": ("apps_microsoft.md", "agent_navigation.md"),
    "B": ("agent_navigation.md", "apps_microsoft.md"),
    "C": ("apps_creative.md", "apps_browsers.md"),
    "D": ("browser_navigation_spec.md", "apps_browsers.md", "websites.md"),
    "E": ("apps_creative.md", "agent_navigation.md"),
    "F": ("apps_microsoft.md", "apps_creative.md"),
    "G": ("agent_universal_optimize.md", "agent_navigation.md"),
}
```

---

## STEP 5 — UTILITY FUNCTIONS

### 5a. `_canonicalize_url(url)` → str
- Redirect `twitter.com` → `x.com`
- Strip leading `www.` so canonical domains are consistent
- Prepend `https://` if missing

### 5b. `_canonical_site_label(url)` → str
Return just the domain (e.g. `youtube.com`) from any URL.

### 5c. `_refine_task_text(task)` → str
Normalise filler words (`please`, `just`, `kindly`), redirect Twitter →
`x.com`, convert `log in` → `sign in`, collapse whitespace.

### 5d. `_refine_element_target(target)` → str
Strip `the/that/this`, normalise `log in` → `sign in button`,
deduplicate `button button`.

### 5e. `_entry_category(entry_point)` → str
Map entry point string to A–G category:
- `win+i` / `settings` → A
- `win+e` / `explorer` → B
- `powershell` / `regedit` / `task manager` → G
- `slack` / `outlook` / `teams` / `discord` → F
- `cursor` / `windsurf` / `code` → E
- Any browser or `browser` → D
- Default → C

### 5f. `_load_rule_file(category)` → str
Try each filename in `_CATEGORY_TO_FILE[category]` under `_RULES_DIR`.
Return first found content, else `""`.

### 5g. `_is_research_task(task)` → bool
Return True for pure knowledge queries (`search`, `find`, `what is`,
`who is`, `explain`, `calculate`, `weather`, etc.) — no UI needed.

---

## STEP 6 — JSON PARSER (`_parse_json`)

This is critical. Must handle all model output variants:

```python
def _parse_json(text: str) -> Optional[dict]:
    if not text:
        return None
    # 1. Strip <think>…</think> thinking blocks (MiMo, Qwen)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # 2. Strip markdown fences (```json … ```)
    stripped = re.sub(r"^```(?:json|python)?\s*|\s*```$", "", text.strip(),
                      flags=re.IGNORECASE | re.MULTILINE).strip()
    # 3. Extract first balanced { … } object
    braced = _extract_braced_object(stripped)
    candidates = [c for c in (braced, stripped) if c]
    for candidate in candidates:
        normalized = _normalize_json_text(candidate)
        try:
            parsed = json.loads(normalized)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        # 4. ast.literal_eval fallback (handles Python-style None/True/False)
        try:
            py_text = re.sub(r"\bnull\b", "None", normalized, flags=re.IGNORECASE)
            py_text = re.sub(r"\btrue\b",  "True",  py_text,  flags=re.IGNORECASE)
            py_text = re.sub(r"\bfalse\b", "False", py_text,  flags=re.IGNORECASE)
            parsed = ast.literal_eval(py_text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None

def _extract_braced_object(text: str) -> Optional[str]:
    """Extract the first balanced { ... } from text."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_string, escape = 0, False, False
    for i, ch in enumerate(text[start:], start=start):
        if escape:       escape = False; continue
        if ch == "\\" and in_string: escape = True; continue
        if ch == '"':    in_string = not in_string; continue
        if in_string:    continue
        if ch == "{":    depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]  # unbalanced fallback

def _normalize_json_text(text: str) -> str:
    """Fix smart quotes, trailing commas, unbalanced braces."""
    t = text.strip()
    t = t.replace("\u201c", '"').replace("\u201d", '"')  # smart double quotes
    t = t.replace("\u2018", "'").replace("\u2019", "'")  # smart single quotes
    t = re.sub(r",\s*([}\]])", r"\1", t)                 # trailing commas
    if t.count("{") > t.count("}"):                       # missing close braces
        t += "}" * (t.count("{") - t.count("}"))
    return t
```

---

## STEP 7 — API CALLER (`_call_api`)

Single function for all model calls. Supports optional thinking budget.
Hard timeout of 35 s. On error, retry once without thinking parameter if
the thinking call failed.

```python
def _call_api(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    thinking: bool = False,
) -> str:
    if not model:
        return ""
    extra = {}
    if thinking:
        extra["thinking"] = {"type": "enabled", "budget_tokens": THINK_MAX_TOKENS}
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra or None,
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
                    model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, timeout=35,
                )
                return str(resp.choices[0].message.content or "").strip()
            except Exception as e2:
                log.error("API retry error (model=%s): %s", model, e2)
    return ""
```

---

## STEP 8 — COORDINATE SYSTEM

All models return coordinates on a 0–1000 scale. Translate to real screen pixels
before clicking. Validate both model coords and translated screen coords.

```python
def _coerce_int(value: Any) -> Optional[int]:
    """Safely convert any numeric-looking value to int."""
    if isinstance(value, bool): return None
    if isinstance(value, int):  return value
    if isinstance(value, float): return int(value) if value.is_integer() else None
    if isinstance(value, str):
        c = value.strip()
        if re.fullmatch(r"-?\d+",    c): return int(c)
        if re.fullmatch(r"-?\d+\.0+", c): return int(float(c))
    return None

def _virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """(left, top, width, height) of the full virtual desktop."""
    try:
        with mss() as sct:
            m = sct.monitors[0]
            return int(m["left"]), int(m["top"]), int(m["width"]), int(m["height"])
    except Exception:
        pass
    w, h = pyautogui.size()
    return 0, 0, int(w), int(h)

def _validate_model_coordinates(x_1000, y_1000, reason="") -> Optional[Tuple[int, int]]:
    x, y = _coerce_int(x_1000), _coerce_int(y_1000)
    if x is None or y is None:
        log.warning("Blocked click %s: non-int coords x=%r y=%r", reason, x_1000, y_1000)
        return None
    if not (0 <= x <= 1000 and 0 <= y <= 1000):
        log.warning("Blocked click %s: out-of-range x=%r y=%r", reason, x, y)
        return None
    return x, y

def _translate(x_1000, y_1000, reason="") -> Optional[Tuple[int, int]]:
    pair = _validate_model_coordinates(x_1000, y_1000, reason=reason)
    if not pair: return None
    w, h = pyautogui.size()
    sx, sy = int(pair[0] / 1000 * w), int(pair[1] / 1000 * h)
    left, top, width, height = _virtual_screen_bounds()
    if not (left <= sx < left + width and top <= sy < top + height):
        log.warning("Blocked click %s: translated coords (%d,%d) out of screen", reason, sx, sy)
        return None
    return sx, sy

def _perform_click(x, y, reason="") -> tuple[bool, str]:
    try:
        pyautogui.moveTo(x, y, duration=0.15)
        time.sleep(ACTION_SETTLE_DELAY)
        pyautogui.click(x, y)
        time.sleep(STEP_PAUSE)
        return True, f"clicked at ({x}, {y})"
    except Exception as e:
        return False, f"click failed: {e}"

def _perform_click_from_model(x_1000, y_1000, reason="") -> tuple[bool, str]:
    # Handle model packing both coords into x as a list
    if isinstance(x_1000, (list, tuple)) and len(x_1000) >= 2 and y_1000 is None:
        x_1000, y_1000 = x_1000[0], x_1000[1]
    translated = _translate(x_1000, y_1000, reason=reason)
    if not translated:
        return False, f"invalid translated coords for {reason}"
    return _perform_click(translated[0], translated[1], reason=reason)
```

---

## STEP 9 — SCREENSHOT & OCR

```python
def _screenshot() -> Image.Image:
    with mss() as sct:
        m = sct.monitors[1]   # primary monitor (index 1, not 0)
        raw = sct.grab(m)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

def _to_base64(img: Image.Image) -> str:
    """Downscale to GROUND_IMG_MAX longest side, encode as JPEG for API."""
    scaled = img
    try:
        max_side = max(img.size)
        if max_side > GROUND_IMG_MAX:
            ratio = GROUND_IMG_MAX / float(max_side)
            scaled = img.resize(
                (int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS
            )
        if scaled.mode != "RGB":
            scaled = scaled.convert("RGB")
    except Exception:
        scaled = img
    buf = BytesIO()
    try:
        scaled.save(buf, format="JPEG", quality=80, optimize=True)
    except Exception:
        buf = BytesIO(); scaled.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def _ocr(img: Image.Image) -> str:
    if not TESSERACT_OK: return ""
    try:
        lines = [ln.strip() for ln in pytesseract.image_to_string(img).splitlines() if ln.strip()]
        return "\n".join(lines[:OCR_MAX_LINES])
    except Exception as e:
        log.warning("OCR error: %s", e)
        return ""

def _screenshot_and_ocr() -> tuple[Image.Image, str]:
    img = _screenshot()
    return img, _ocr(img)
```

---

## STEP 10 — EXTRACTION HELPERS

These are pure regex/heuristic — no LLM calls:

- `_extract_requested_app(task)` → match against `_KNOWN_APPS` keys (longest first)
- `_extract_requested_url(task)` → regex for `https://…`, then `domain.tld`, then `_SITE_URLS`
- `_extract_click_target(task)` → regex for `click [the] <target>` or `press [the] <target>`
- `_extract_search_query(task)` → regex for `search for`, `look up`, `find`
- `_extract_video_recency_hint(task)` → regex for `latest`, `this week`, `N days ago`

---

## STEP 11 — YOUTUBE FILTER CODES

`_youtube_filter_code(hint, task)` → `sp=` URL parameter for direct filtered search.

| Pattern | Code |
|---|---|
| `last hour` / `past hour` | `EgIIAQ%3D%3D` |
| `today` / `past 24 hours` | `EgIIAg%3D%3D` |
| `this week` / `last week` | `EgIIAw%3D%3D` |
| `this month` / `last month` | `EgIIBA%3D%3D` |
| `this year` / `last year` | `EgIIBQ%3D%3D` |
| `most viewed` / `popular` | `CAM%3D` |
| `highest rated` | `CAE%3D` |
| `latest` / `most recent` / `newest` | `CAI%3D` |

Fast-path URL: `https://www.youtube.com/results?search_query={q}&sp={code}`

---

## STEP 12 — BROWSER LAUNCHING

### `_get_default_browser_command()` → str
Read Windows registry
`HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice`
to find the user's default browser. Return `arc`, `chrome`, `firefox`,
`msedge`, `brave`, `opera`, `vivaldi`, or `start` as fallback.

### `_lookup_registry_app_path(executable_name)` → Optional[str]
Check `App Paths\{exe}` in both HKCU and HKLM, return the verified path.

### `_resolve_browser_path(app)` → Optional[str]
Try static `_BROWSER_PATHS` first, then registry fallback.

### `_launch_browser(app, url=None)` → str
Launch the resolved browser binary. Pass `url` as argument if provided so
Chrome opens directly at that URL (avoids Ctrl+L race with non-browser focus).
Wait `BROWSER_LAUNCH_DELAY` seconds after launch.

### `_foreground_browser_window(app)` → bool
Find a visible browser window by title hint and bring it to the foreground.
Use `win32gui.SetForegroundWindow` with an ALT nudge to bypass Windows
foreground lock. Fall back to ctypes-only if pywin32 unavailable.

---

## STEP 13 — PRE-FLIGHT

### `_quick_preflight(task)` → Optional[dict]
Fast path — no LLM call. Returns a preflight dict if the task is obviously
a browser/navigation task. Detects app name, URL, click target, and builds
a short strategy string. Returns `None` for non-browser or ambiguous tasks.

### `_THINK_SYSTEM` prompt
LLM pre-flight prompt that returns:
```json
{
  "clean_task": "<rewritten task, normalised>",
  "app_to_open": "<exact app name or null>",
  "step_count": 3,
  "entry_point": "<Win+I / chrome / arc / etc>",
  "needs_research": false,
  "research_query": null,
  "keyboard_only": false,
  "strategy": "<one sentence>"
}
```

Rules baked into the system prompt:
- Always use the exact app the user named — never substitute browsers
- Canonicalize `twitter` → `x.com`
- `Win+I` for Settings tasks
- Preserve final UI target (e.g. `sign in button`)

### `_preflight(task)` → dict
1. Try `_quick_preflight` — return immediately if it matches
2. Refine task text
3. Call `_call_api(OMNI_MODEL, …, TEMP_THINK, 600)` with `_THINK_SYSTEM`
4. Parse and refine result; log app and research flags
5. Return safe defaults if parse fails

---

## STEP 14 — PHASE 1: PLANNING

### `_heuristic_plan(task, preflight)` → Optional[dict]
Deterministic planner — no LLM. Builds a plan for browser tasks:

1. Extract app, URL, click target, search query, recency hint
2. YouTube search → build `first_url` with filter code, pass to `open_app`
   so Chrome opens directly at the results page (no Ctrl+L race)
3. For non-YouTube URLs: add `navigate` action
4. For search queries: add `ask_uitars` (click search bar) + `type` + `press enter`
   + `wait_for_page`
5. For `_wants_first_video`: add `find_video_result` + `wait_for_page`
6. For click targets: add `ask_uitars`

### `_PLAN_SYSTEM` prompt
LLM planner prompt (used when heuristic plan doesn't apply). Returns:
```json
{
  "category": "D",
  "confidence": 0.97,
  "task_summary": "<one line>",
  "steps": ["<step 1>", "<step 2>"],
  "initial_action": {"type": "open_app", "app": "chrome"},
  "requires_uitars": true
}
```
**Absolute rule:** never return coordinates — all clicks must use `ask_uitars`.

### `_phase1(task, preflight)` → Optional[dict]
1. Try `_heuristic_plan` first
2. Load rule file and shortcut hints for the category
3. Call `_call_api(OMNI_MODEL, …, TEMP_PLAN, PLAN_MAX_TOKENS)`
4. Sanitise plan (convert any coordinate-click steps to `ask_uitars`)

---

## STEP 15 — PHASE 2: EXECUTION LOOP SYSTEM PROMPT

`_phase2_system(task, plan, rule_content, system_context_md)` builds the
system prompt injected at every Phase 2 iteration. It must contain:

### Task + Steps section
All planned steps listed. The agent must complete every single one.

### Focus Verification Rules (non-negotiable)

**RULE 0 — SCREENSHOT-FIRST PROTOCOL**
Before any keyboard input: take a screenshot, identify the focused element,
verify it is the intended target. If not → execute FOCUS ESCAPE PROCEDURE.

**RULE 1 — FOCUS IDENTIFICATION**
- Text cursor in a text area → that element has focus
- IDE (Windsurf, VSCode, Cursor) foregrounded with file open → editor has focus
- Browser address bar: thin field at top with URL or "Search or type a URL"
- In-page inputs: search bars, form fields

**RULE 2 — FOCUS ESCAPE PROCEDURE**
When focused element is NOT your intended target:
1. Do NOT type anything
2. Use `ask_uitars` to click the title bar of the target window
3. Take a screenshot and verify
4. Use `ask_uitars` to click the specific element that should receive input
5. Take another screenshot to confirm cursor position
6. Only then issue `type`

**RULE 3 — APPLICATION SWITCHING**
Never use Alt+Tab unless confirmed no text field is focused.
Safe method: click the app icon in the taskbar via `ask_uitars`.

**RULE 4 — BROWSER NAVIGATION PROCEDURE**
1. screenshot → is target browser the active foreground window?
   - If not → `ask_uitars` to click browser icon in taskbar
   - screenshot → verify browser is active
2. `ask_uitars` to click URL/address bar
   - screenshot → verify cursor in URL bar
3. `type` the URL → `press enter`
   - screenshot → verify loading
4. screenshot → verify page fully loaded
5. `ask_uitars` to click target in-page element
6. `type` → `press enter` → screenshot → verify result
Use `navigate` action as shortcut only when browser already has focus.

**RULE 5 — TASK EXECUTION LOOP**
For every discrete action:
screenshot → identify state → identify focus → compare to target →
redirect focus if needed → execute → verify via next OCR → proceed or retry.
If outcome doesn't match: do NOT continue. Analyze and re-execute from last
verified correct state.

**RULE 6 — IDE CONFLICT HANDLING**
If Windsurf, VSCode, Cursor, or any IDE is foregrounded with active file:
- Never type a URL or task input while this state is active
- Remediation: `ask_uitars` click blank desktop area → screenshot → confirm
  no text field focused → proceed with target app

**RULE 7 — VERIFICATION CHECKPOINTS**
Before marking any subtask complete: screenshot → verify expected state visible in OCR.
If verification fails → retry the subtask from scratch.

### Anti-patterns section
- Do not issue `type` without confirming correct element has focus
- Do not assume last-clicked app is still in focus
- Do not use Alt+Tab without confirming no text field is active
- Do not infer focus from context — always confirm with screenshot
- Do not proceed after failed verification — always retry

### Available actions section
```
Open app:          {"type":"open_app","app":"chrome"}
Open app at URL:   {"type":"open_app","app":"chrome","url":"https://youtube.com"}
Keyboard shortcut: {"type":"hotkey","keys":["ctrl","l"]}
Type text:         {"type":"type","text":"youtube.com"}
Press key:         {"type":"press","key":"enter"}
Wait:              {"type":"wait","seconds":2}
Navigate URL:      {"type":"navigate","url":"https://youtube.com"}
Find+click visual: {"type":"ask_uitars","instruction":"click the search bar"}
Find first video:  {"type":"find_video_result","query":"lo-fi","hint":"this week"}
Wait for page:     {"type":"wait_for_page","target":"youtube_results","query":"lo-fi"}
Take screenshot:   {"type":"screenshot"}
All steps done:    {"type":"done","message":"Video is playing"}
Unrecoverable:     {"type":"failed","message":"reason"}
```

---

## STEP 16 — ACTION EXECUTOR (`_execute`)

Handles all action types from Phase 2. Key implementations:

**`open_app`**: if browser + URL → `_launch_browser(app, url)`, else `_launch_app(app)`.
After browser launch, call `_foreground_browser_window(app)`.

**`navigate`**: First call `_foreground_browser_window(app)` to ensure browser
has focus. Then `Ctrl+L` to focus URL bar, `typewrite(url, interval=0.01)`,
`press enter`. This is the reliable keyboard-only path.

**`hotkey`**: `pyautogui.hotkey(*keys)`. Block dangerous keys (`cmd+q`,
`cmd+w`, `cmd+tab`, `alt+f4`). Remap `cmd+` → `ctrl+` automatically.

**`type`**: `pyautogui.typewrite(text, interval=0.04)`. If URL-like text
(starts with `http` or `www`), press enter after.

**`press`**: `pyautogui.press(key)`.

**`scroll`**: translate 0–1000 coords, `pyautogui.scroll(amount * direction)`.

**`wait_for_page`**: polling loop up to `PAGE_LOAD_TIMEOUT` seconds; OCR the
screen every `LOAD_POLL_SECONDS`; check for loading markers and target-specific
content (YouTube home/results/video).

**`find_video_result`**: up to `max_scrolls` attempts; call `_uitars` to locate
the first video thumbnail; if not found, `pyautogui.scroll(-500)` and retry.

**`ask_uitars`**: First check `_find_keyboard_shortcut(instruction)` — if a
keyboard shortcut matches, use it instead of a visual search. Otherwise call
`_uitars` with up to 3 instruction variants (e.g. `click sign in` → also try
`click sign in button`, `click log in`).

**`screenshot`**: `_screenshot_and_ocr()` and return OCR text (first 600 chars).

**`done` / `failed`**: return the message directly.

---

## STEP 17 — UIA + VISION (per-iteration fallback paths)

These are used inside `run_agent_loop` (the simpler two-path loop) and also
as the visual grounding backbone in Phase 2 via `ask_uitars`:

**`_get_uia_tree()`**: `pywinauto Desktop(backend="uia")` on the foreground
window, capture `print_control_identifiers(depth=4)` to a StringIO buffer,
return if > 50 chars.

**`_ask_omni_uia(task, tree, step, repeat_warning)`**:
```
System: You are a Windows desktop agent. Given the UI accessibility tree,
return ONE JSON action:
{"action": "click_element", "title": "…"}
{"action": "type", "text": "…"}
{"action": "key", "key": "ctrl+l"}
{"action": "done", "result": "…"}
{"action": "fallback", "reason": "UIA insufficient, need vision"}
Return ONLY valid JSON. No markdown.
```
If same action repeated 3 times, inject a warning: "Previous action failed or
had no effect. Do NOT repeat it. Try a completely different approach."

**`_ask_omni_vision(task, step, repeat_warning)`**:
```
System: You are a Windows desktop agent controlling a real screen.
Return ONE JSON action. Available actions:
{"action": "click", "coordinate": [x, y]}  ← 0-1000 scale
{"action": "type", "text": "…"}
{"action": "key", "key": "ctrl+l"}
{"action": "scroll", "coordinate": [x, y], "direction": "down", "amount": 3}
{"action": "done", "result": "…"}
{"action": "uitars", "reason": "need sub-pixel precision"}
CRITICAL: This is Windows. Use ctrl/shift/alt/win — never cmd/super/meta.
Never output alt+tab or alt+f4.
```
If `action == "uitars"`, route to `_ask_uitars_executor`.

**`_uitars(img, instruction)`**: Call `EXECUTOR_MODEL` with image + instruction.
Returns `{"action":"click","x":…,"y":…,"element":"…"}` or `{"action":"not_found"}`.

---

## STEP 18 — MAIN AGENT LOOP (`run_agent_loop`)

```python
def run_agent_loop(task, toast=None, progress_cb=None) -> str:
    log.info("=== Agent task (two-path): %r ===", task)
    # Pre-flight
    preflight = _preflight(task)
    app_to_open = preflight.get("app_to_open") or preflight.get("app", "chrome")
    _ensure_app_open(app_to_open)

    action_history: list[str] = []
    repeat_warning = ""

    for step in range(MAX_LOOP_STEPS):
        tree = _get_uia_tree()
        if tree:
            action = _ask_omni_uia(task, tree, step, repeat_warning)
            if action.get("action") == "fallback":
                action = _ask_omni_vision(task, step, repeat_warning)
        else:
            action = _ask_omni_vision(task, step, repeat_warning)

        if not action:
            continue

        success, result = _execute_two_path(action, step, task)

        # Repeat detection
        action_str = json.dumps(action, sort_keys=True)
        action_history.append(action_str)
        if len(action_history) > 3:
            action_history.pop(0)
        if len(action_history) == 3 and len(set(action_history)) == 1:
            repeat_warning = "Previous action failed or had no effect. Do NOT repeat it. Try a completely different approach."
        else:
            repeat_warning = ""

        if action.get("action") == "done":
            return result
        time.sleep(0.3)

    return f"Reached {MAX_LOOP_STEPS}-step limit — task may be incomplete"
```

`_execute_two_path` handles UIA `click_element`, vision `click` (coordinate),
`type`, `key`, `scroll`, `done`, `fallback` (recurse to vision), `not_found`.

---

## STEP 19 — PUBLIC API

```python
def run_agent_task(task, toast=None, progress_cb=None) -> str:
    """Public entry point. Uses two-path architecture."""
    log.info("=== Agent task: %r ===", task)
    if toast: toast("Whiztant", "Thinking…")
    if progress_cb: progress_cb("step", "Understanding your task...")
    return run_agent_loop(task, toast=toast, progress_cb=progress_cb)

def call_qwen_planner(task, toast=None, progress_cb=None) -> str:
    return run_agent_task(task, toast=toast, progress_cb=progress_cb)

_lock    = threading.Lock()
_running = False

def run_agent_task_async(task, toast=None, progress_cb=None) -> None:
    global _running
    if _running:
        if toast: toast("Whiztant", "Agent busy — please wait")
        return
    def _worker():
        global _running
        with _lock: _running = True
        try:
            run_agent_task(task, toast, progress_cb)
        except Exception as e:
            log.error("Agent worker error: %s", e, exc_info=True)
            if progress_cb: progress_cb("error", str(e)[:100])
        finally:
            _running = False
    threading.Thread(target=_worker, daemon=True, name="whiztant-agent").start()
```

---

## STEP 20 — COMPATIBILITY HELPERS

**`_get_default_browser_command()`**: Read Windows registry
`HKCU\…\UrlAssociations\https\UserChoice` → `ProgId` to find default browser.
Return `arc`/`chrome`/`firefox`/`msedge`/`brave`/`opera`/`vivaldi`/`start`.

**`_ensure_app_open(app_name)`**: 
1. Check `win32gui.GetForegroundWindow()` title — if app already focused, return
2. `EnumWindows` to find the window — restore and `SetForegroundWindow`, return
3. Launch via `subprocess.Popen` and wait 2.5 s

---

## STEP 21 — SELF-TESTS

After writing the file, run from `C:\whis`:

```python
python -c "
import sys
sys.path.insert(0, r'C:\whis')
from core.vlm import _parse_json, _preflight, _get_uia_tree, _ensure_app_open, KEYBOARD_SHORTCUTS, _KNOWN_APPS

# Test 1: JSON with <think> block
t1 = _parse_json('<think>let me think</think>{\"action\": \"click_element\", \"title\": \"Search\"}')
assert t1 == {'action': 'click_element', 'title': 'Search'}, f'FAIL test1: {t1}'
print('PASS: <think> block stripped + JSON parsed')

# Test 2: JSON with markdown fence
t2 = _parse_json('\`\`\`json\n{\"action\": \"key\", \"key\": \"win\"}\n\`\`\`')
assert t2 == {'action': 'key', 'key': 'win'}, f'FAIL test2: {t2}'
print('PASS: markdown fence stripped + JSON parsed')

# Test 3: Pre-flight Chrome detection
pf = _preflight('open chrome and go to youtube')
assert pf.get('app_to_open') == 'chrome' or pf.get('app') == 'chrome', f'FAIL test3: {pf}'
print('PASS: pre-flight Chrome detection')

# Test 4: UIA tree (should not crash)
tree = _get_uia_tree()
print(f'PASS: UIA tree returned {len(tree) if tree else 0} chars')

# Test 5: Keyboard shortcuts dict is populated
assert 'url bar' in KEYBOARD_SHORTCUTS, 'FAIL test5: url bar missing'
assert 'open settings' in KEYBOARD_SHORTCUTS, 'FAIL test5: open settings missing'
print('PASS: KEYBOARD_SHORTCUTS populated')

# Test 6: Known apps dict
assert 'chrome' in _KNOWN_APPS, 'FAIL test6: chrome missing'
assert 'arc' in _KNOWN_APPS, 'FAIL test6: arc missing'
print('PASS: _KNOWN_APPS populated')

print('ALL TESTS PASSED')
"
```

Fix any failure and re-run until all 6 pass.

---

## LOOP APPROACH: SIMPLE RETRY ✓

Use a simple write → test → fix → re-test loop for this task.
**Do NOT use `superpowers:executing-plans`** — that skill is designed for
multi-file implementation plans with sequenced dependencies. This is a single-file
rewrite with 6 deterministic tests. The loop is:

```
1. Write core/vlm.py
2. Run the 6 tests
3. If any fail → fix the specific function → re-run
4. Repeat until all 6 pass
5. Do NOT change any other file (guardrails, ws_bridge, tts, etc.)
```

---

## DO NOT CHANGE

- Any file outside `core/vlm.py`
- Tier enforcement / usage guard (handled by `core/usage.py` or caller)
- `core/guardrails.py` integration calls (import and call as-is)
- `core/ws_bridge.py` calls (`send_agent_step_v2`, `send_agent_blocked`, `send_agent_done`)
- `core/toast.py` calls (`toast_action_blocked`)
- `requirements.txt`
