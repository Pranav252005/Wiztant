"""
Whiztant core/agent.py — tool registry, all tools, prompts, routing, ask_ai loop
Uses OpenAI API with tier-based model selection.
"""

import os
import json
import re
import subprocess
import threading
import asyncio
import urllib.parse
import pathlib
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import OpenAI
import pyperclip
import keyboard
import requests

import core as state
from core import memory as memory_mod
from core import vlm
from core import usage


def _speak_via_tts(text: str):
    """Speak via platform TTS (Kokoro). Non-blocking so agent loop isn't stalled."""
    try:
        from platforms.factory import get_tts
        get_tts().speak(text, blocking=False)
    except Exception as e:
        print(f"[TTS] Agent speak failed: {e}")

# =============================================================
#  AGENT MEMORY — persistent task history for session context
# =============================================================

class AgentMemory:
    """Persistent memory for agent tasks across executions."""

    def __init__(self, data_dir: Path = Path("data")):
        self.history_file = data_dir / "agent_task_history.json"
        self.undo_file    = data_dir / "undo_actions.json"
        self.memory       = self._load_history()

    def _load_history(self) -> dict:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "session_id": datetime.now().isoformat(),
            "tasks":       [],
            "current_chain": None,
            "undo_stack":  [],
        }

    def _save_history(self):
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"[AgentMemory] save error: {e}")

    def record_task_start(self, task_id: str, user_task: str, task_type: str) -> dict:
        record = {
            "task_id":           task_id,
            "timestamp":         datetime.now().isoformat(),
            "user_task":         user_task,
            "task_type":         task_type,
            "status":            "in_progress",
            "subtasks_completed": 0,
            "subtasks_total":    0,
        }
        self.memory["tasks"].append(record)
        self._save_history()
        return record

    def record_task_complete(
        self,
        task_id: str,
        undo_id: str,
        execution_time_seconds: float,
        details: dict = None,
    ):
        task = next((t for t in self.memory["tasks"] if t["task_id"] == task_id), None)
        if task:
            task["status"]                  = "completed"
            task["undo_id"]                 = undo_id
            task["execution_time_seconds"]  = round(execution_time_seconds, 2)
            task["reversible"]              = True
            if details:
                task.update(details)
            self.memory["undo_stack"].append(undo_id)
            self._save_history()

    def record_task_failed(self, task_id: str, error: str):
        task = next((t for t in self.memory["tasks"] if t["task_id"] == task_id), None)
        if task:
            task["status"] = "failed"
            task["error"]  = error
            self._save_history()

    def record_task_cancelled(self, task_id: str):
        task = next((t for t in self.memory["tasks"] if t["task_id"] == task_id), None)
        if task:
            task["status"] = "cancelled"
            self._save_history()

    def get_last_task(self) -> Optional[dict]:
        completed = [t for t in self.memory["tasks"] if t["status"] == "completed"]
        return completed[-1] if completed else None

    def get_task_context(self) -> str:
        if not self.memory["tasks"]:
            return "No previous tasks in this session."
        context = "Recent agent task history:\n"
        for task in self.memory["tasks"][-5:]:
            emoji = "✓" if task["status"] == "completed" else ("✗" if task["status"] == "failed" else "◌")
            context += f"\n{emoji} {task['user_task']} ({task.get('task_type', '?')})"
        return context

    def store_undo_actions(self, undo_id: str, task_id: str, actions: list):
        """Persist the undo action log for an agent task."""
        self.undo_file.parent.mkdir(parents=True, exist_ok=True)
        undo_map = {}
        if self.undo_file.exists():
            try:
                with open(self.undo_file, "r", encoding="utf-8") as f:
                    undo_map = json.load(f)
            except Exception:
                pass
        undo_map[undo_id] = {
            "task_id":   task_id,
            "timestamp": datetime.now().isoformat(),
            "actions":   actions,
        }
        with open(self.undo_file, "w", encoding="utf-8") as f:
            json.dump(undo_map, f, indent=2)

    # ------------------------------------------------------------------
    # Undo ring buffer (checkpoint model, max 16 entries)
    # ------------------------------------------------------------------

    _RING_SIZE = 16

    def push_undo(self, task_id: str, action: dict, undo_hook: str = "") -> None:
        """Record a reversible action. undo_hook is a human-readable reverse instruction."""
        ring = self.memory.setdefault("undo_ring", [])
        ring.append({
            "task_id":   task_id,
            "action":    action,
            "undo_hook": undo_hook,
            "ts":        datetime.now().isoformat(),
        })
        # Keep only the last _RING_SIZE entries
        if len(ring) > self._RING_SIZE:
            self.memory["undo_ring"] = ring[-self._RING_SIZE:]
        self._save_history()

    def rollback_to_checkpoint(self, task_id: str = "") -> list:
        """
        Undo all ring-buffer entries for task_id (or the most recent task if
        task_id is empty). Returns the list of undo_hooks that were reversed.
        Callers are responsible for actually executing the hooks.
        """
        ring = self.memory.get("undo_ring", [])
        if not ring:
            return []
        # Find target task_id — default to the last entry's task_id
        target = task_id or ring[-1]["task_id"]
        to_undo = [e for e in ring if e["task_id"] == target]
        hooks = [e["undo_hook"] for e in reversed(to_undo) if e.get("undo_hook")]
        # Remove rolled-back entries from the ring
        self.memory["undo_ring"] = [e for e in ring if e["task_id"] != target]
        self._save_history()
        return hooks


def get_agent_memory() -> "AgentMemory":
    return agent_memory


# Global instance — imported by vlm.py and ui/ for memory access
agent_memory = AgentMemory()


# =============================================================
#  OPENAI CLIENT + HELICONE TRACKING + TIER-BASED MODEL SELECTION
# =============================================================

HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check for custom model endpoint (WizType BYOK mode)
_custom_model_config = None
_custom_client = None

def _get_custom_client():
    """Get or create client for custom model endpoint."""
    global _custom_model_config, _custom_client
    
    custom_model = os.getenv("MODEL_CUSTOM", "").strip()
    if not custom_model:
        return None
    
    from core.wiztype.custom_model import parse_custom_model
    config = parse_custom_model(custom_model, os.getenv("MODEL_CUSTOM_PROVIDER", "") or None)
    
    if not config.is_valid or config.is_local:
        return None
    
    # Return cached client if config matches
    if _custom_client and _custom_model_config and _custom_model_config.model_id == config.model_id:
        return _custom_client
    
    # Create new client for custom endpoint
    _custom_model_config = config
    
    if config.provider == "anthropic":
        # Anthropic uses different client
        try:
            from anthropic import Anthropic
            _custom_client = Anthropic(api_key=config.api_key)
            return _custom_client
        except Exception:
            pass
    
    # OpenAI-compatible client
    if config.api_key:
        _custom_client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        return _custom_client
    
    return None

if OPENAI_API_KEY and HELICONE_API_KEY:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url="https://oai.helicone.ai/v1",
        default_headers={
            "Helicone-Auth": f"Bearer {HELICONE_API_KEY}",
            "Helicone-Property-App": "whiztant",
            "Helicone-Property-Version": "1.0.0",
        }
    )
    print("[Helicone] OpenAI tracking enabled")
elif OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None


def _normalize_chat_model(model: str) -> str:
    # Pass through whatever the caller/.env configured. Previously this
    # silently remapped -mini / 5.1-* variants to gpt-4o, which hid tier
    # selection. If a model truly isn't available, the API will error and
    # the caller can surface it.
    model_name = (model or "").strip()
    return model_name or "gpt-4o"

def get_model(tier: str = None) -> str:
    # Check for custom model first (WizType BYOK mode)
    custom_model = os.getenv("MODEL_CUSTOM", "").strip()
    if custom_model:
        from core.wiztype.custom_model import parse_custom_model
        config = parse_custom_model(custom_model, os.getenv("MODEL_CUSTOM_PROVIDER", "") or None)
        if config.is_valid:
            return config.model_id
    
    if tier is None:
        tier = os.getenv("CURRENT_TIER", "free")
    tier = str(tier).lower()
    tier_models = {
        "free":  os.getenv("MODEL_FREE",  "gpt-4o"),
        "pro":   os.getenv("MODEL_PRO",   "gpt-4o"),
        "power": os.getenv("MODEL_POWER", "gpt-4o"),
    }
    return _normalize_chat_model(tier_models.get(tier, "gpt-4o"))


def _fallback_models(primary_model: str) -> list[str]:
    return [primary_model] if primary_model else []


def get_helicone_user_header() -> dict:
    """Returns Helicone user ID header for per-user cost tracking."""
    try:
        from core.supabase_client import get_current_user
        user = get_current_user()
        if user and user.user:
            return {"Helicone-User-Id": str(user.user.id)}
    except Exception:
        pass
    return {}


def _endpoint_reachable(url: str, timeout: float = 3.5) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False


def _agent_executor_name() -> str:
    return (os.getenv("AGENT_EXECUTOR", "agent_s3") or "agent_s3").strip().lower()


def _agent_required_endpoints() -> list[str]:
    if _agent_executor_name() != "agent_s3":
        return ["https://openrouter.ai/api/v1"]

    provider = (os.getenv("AGENT_S3_PROVIDER", "openai") or "openai").strip().lower()
    base_url = (os.getenv("AGENT_S3_BASE_URL", "") or "").strip()
    grounding_url = (os.getenv("AGENT_S3_GROUNDING_URL", "") or "").strip()

    endpoints: list[str] = []
    if base_url:
        endpoints.append(base_url)
    elif provider == "openrouter":
        endpoints.append("https://openrouter.ai/api/v1")
    elif provider in {"anthropic", "claude"}:
        endpoints.append("https://api.anthropic.com")
    elif provider in {"google", "gemini"}:
        endpoints.append("https://generativelanguage.googleapis.com")
    else:
        endpoints.append("https://api.openai.com/v1/models")

    if grounding_url.startswith("http://") or grounding_url.startswith("https://"):
        endpoints.append(grounding_url)

    return endpoints


def _mode_offline_message(mode: str) -> str:
    if mode == "agent":
        return "Agent mode needs an internet connection. Please turn on the internet and try again."
    return "Tune mode needs an internet connection. Please turn on the internet and try again."


def call_llm(messages: list, tier: str = None, max_tokens: int = 1500,
             mode: str = "chat") -> str:
    # Check for custom model client first (WizType BYOK mode)
    custom_client = _get_custom_client()
    
    if custom_client is None and client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    
    primary_model = get_model(tier)
    if messages and messages[0].get("role") == "system":
        messages = [messages[0]] + messages[1:][-14:]
    else:
        messages = messages[-15:]

    # Use custom client if available
    if custom_client is not None:
        try:
            from core.wiztype.custom_model import parse_custom_model
            config = parse_custom_model(
                os.getenv("MODEL_CUSTOM", ""),
                os.getenv("MODEL_CUSTOM_PROVIDER", "") or None
            )
            
            if config.provider == "anthropic":
                # Anthropic API format
                system_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
                user_messages = [m for m in messages if m.get("role") != "system"]
                
                anthropic_messages = []
                for m in user_messages:
                    role = "assistant" if m.get("role") == "assistant" else "user"
                    anthropic_messages.append({"role": role, "content": m.get("content", "")})
                
                response = custom_client.messages.create(
                    model=primary_model,
                    max_tokens=max_tokens,
                    system=system_msg,
                    messages=anthropic_messages,
                )
                return response.content[0].text
            else:
                # OpenAI-compatible API
                response = custom_client.chat.completions.create(
                    model=primary_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM] Custom model error: {e}")
            # Fall back to default client if custom fails
            if client is None:
                raise
    
    # Use default client
    last_error = None
    for model in _fallback_models(primary_model):
        try:
            try:
                effective_tier = usage.get_tier()
            except Exception:
                effective_tier = os.getenv("CURRENT_TIER", "free")
            request_kwargs = {
                "model": model,
                "messages": messages,
                "extra_headers": {
                    **get_helicone_user_header(),
                    "Helicone-Property-Tier": effective_tier or "free",
                    "Helicone-Property-Mode": mode,
                },
            }

            response = None
            attempt_variants = [
                {"max_tokens": max_tokens, "temperature": 0.7},
                {"max_completion_tokens": max_tokens, "temperature": 0.7},
                {"max_completion_tokens": max_tokens},
                {"max_tokens": max_tokens},
                {},
            ]
            attempt_error = None
            for variant in attempt_variants:
                try:
                    response = client.chat.completions.create(
                        **request_kwargs,
                        **variant,
                    )
                    break
                except Exception as variant_error:
                    attempt_error = variant_error
                    error_text = str(variant_error).lower()
                    if "unsupported parameter" in error_text or "unsupported value" in error_text:
                        continue
                    raise

            if response is None:
                raise attempt_error
            if model != primary_model:
                print(f"[LLM] Falling back from {primary_model} to {model}")
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            error_text = str(e).lower()
            if "model_not_found" in error_text or "does not have access to model" in error_text:
                print(f"[LLM] Model unavailable: {model}")
                continue
            raise

    raise last_error


# =============================================================
#  SYSTEM PROMPT — loaded from agent_rules/system_prompt.md
# =============================================================

_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "agent_rules", "system_prompt.md"
)

try:
    with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as _f:
        SYSTEM_PROMPT = _f.read()
    print(f"[Agent] Loaded system prompt from {_SYSTEM_PROMPT_PATH}")
except FileNotFoundError:
    SYSTEM_PROMPT = "You are Whiztant, a personal AI operating assistant."
    print(f"[Agent] system_prompt.md not found, using default")


def _notify_overlay_history_updated():
    overlay = getattr(state, "chat_overlay", None)
    if overlay:
        try:
            overlay.on_history_updated()
        except Exception:
            pass


def _trim_conversation_history():
    global conversation_history
    if not state.conversation_history:
        state.conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        conversation_history = state.conversation_history
        return
    if len(state.conversation_history) > state.MAX_HISTORY:
        state.conversation_history = [state.conversation_history[0]] + state.conversation_history[-19:]
    conversation_history = state.conversation_history


def reset_conversation_history():
    global conversation_history
    state.conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation_history = state.conversation_history
    _notify_overlay_history_updated()


def add_history_message(role: str, content: str):
    if content is None:
        return
    text = str(content).strip()
    if not text:
        return
    if not state.conversation_history:
        reset_conversation_history()
    state.conversation_history.append({"role": role, "content": text})
    _trim_conversation_history()
    _notify_overlay_history_updated()


def add_system_message(content: str):
    add_history_message("system", content)


def process_conversation_turn(user_text: str):
    text = str(user_text).strip()
    if not text:
        return ""

    if not _endpoint_reachable("https://api.openai.com/v1/models"):
        message = _mode_offline_message("chat")
        add_history_message("assistant", message)
        return message

    # Check chat quota after confirming the online API is reachable.
    # Supabase usage can still fall back to the local counter.
    tier = usage.get_tier()
    allowed, quota_msg = usage.check_usage("chat", tier, fail_open=True)
    if not allowed:
        add_history_message("assistant", quota_msg)
        return quota_msg

    add_history_message("user", text)
    state.thinking = True
    if state.overlay:
        state.overlay.set_thinking()

    try:
        response = call_llm(state.conversation_history, mode="chat")
        add_history_message("assistant", response)
        # Increment only after a successful LLM call — errors don't burn quota.
        usage.increment_usage_count("chat", tier)
    except Exception as e:
        state.thinking = False
        if state.overlay:
            state.overlay.set_idle()
        error_text = f"Error: {e}"
        add_history_message("assistant", error_text)
        return error_text

    state.thinking = False
    if state.overlay:
        state.overlay.set_idle()
    return response


async def execute_agent_task_fixed(task: str) -> dict:
    from core.agent_s3_wrapper import get_agent_s3

    return await get_agent_s3().execute_task(
        instruction=task,
        speak_fn=lambda *_args, **_kwargs: None,
        set_wave_state_fn=lambda *_args, **_kwargs: None,
        append_chat_fn=lambda *_args, **_kwargs: None,
        stop_event=None,
        max_steps=int(os.getenv("AGENT_MAX_STEPS", "20")),
    )


if not state.conversation_history:
    reset_conversation_history()
conversation_history = state.conversation_history

# =============================================================
#  TOOL REGISTRY
# =============================================================

TOOLS = {}

def tool(name: str, desc: str):
    def decorator(fn):
        TOOLS[name] = {"fn": fn, "desc": desc}
        return fn
    return decorator

# =============================================================
#  CORE TOOLS
# =============================================================

@tool("get_datetime",
      "Returns the current date and time.")
def tool_get_datetime(**_):
    return datetime.now().strftime("%A %d %B %Y, %H:%M:%S")


@tool("clipboard_read",
      "Reads whatever is currently in the clipboard.")
def tool_clipboard_read(**_):
    content = pyperclip.paste()
    return content if content else "(clipboard is empty)"


@tool("clipboard_write",
      "Writes text to the clipboard. Args: text (str)")
def tool_clipboard_write(text="", **_):
    pyperclip.copy(str(text))
    return "Clipboard updated."


@tool("paste_text",
      "Types/pastes text into whatever app is currently focused. Args: text (str)")
def tool_paste_text(text="", **_):
    import time
    def _do():
        pyperclip.copy(str(text))
        time.sleep(0.25)
        keyboard.press_and_release("ctrl+v")
    threading.Thread(target=_do, daemon=True).start()
    return "Pasted."


@tool("run_command",
      "Runs a Windows shell command and returns its output. Args: cmd (str).")
def tool_run_command(cmd="", **_):
    if not cmd:
        return "No command given."
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=20
        )
        output = (result.stdout or result.stderr or "").strip()
        return output[:800] if output else "(command ran, no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 20s."
    except Exception as e:
        return f"Error: {e}"


@tool("open_app",
      "Opens an application, file, or URL. Args: target (str).")
def tool_open_app(target="", **_):
    if not target:
        return "No target specified."
    try:
        if target.startswith("http://") or target.startswith("https://"):
            import webbrowser
            webbrowser.open(target)
            return f"Opened in browser: {target}"
        os.startfile(target)
        return f"Opened: {target}"
    except Exception:
        try:
            subprocess.Popen(f'start "" "{target}"', shell=True)
            return f"Launched: {target}"
        except Exception as e:
            return f"Could not open '{target}': {e}"


@tool("read_file",
      "Reads and returns the contents of a file. Args: path (str). Returns first 2000 characters.")
def tool_read_file(path="", **_):
    if not path:
        return "No file path given."
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(2000)
    except Exception as e:
        return f"Could not read file: {e}"


@tool("write_file",
      "Creates or overwrites a file with given content. Args: path (str), content (str).")
def tool_write_file(path="", content="", **_):
    if not path:
        return "No file path given."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(content))
        return f"Written to {path} ({len(content)} chars)."
    except Exception as e:
        return f"Could not write file: {e}"


@tool("web_search",
      "Searches the web via DuckDuckGo. Returns a short answer or summary. Args: query (str).")
def tool_web_search(query="", **_):
    if not query:
        return "No query given."
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        abstract = data.get("AbstractText", "").strip()
        if abstract:
            return abstract[:600]
        topics = data.get("RelatedTopics", [])
        snippets = []
        for t in topics[:4]:
            if isinstance(t, dict) and "Text" in t:
                snippets.append(t["Text"])
        if snippets:
            return "\n\n".join(snippets)[:600]
        return f"No quick answer found for: {query}. Try a more specific query."
    except Exception as e:
        return f"Search failed: {e}"


# =============================================================
#  BROWSER TOOLS
# =============================================================

def _chrome_open(url: str, profile_num: int = 0, side_window: bool = True):
    """Open a URL in the default browser. Cross-platform via webbrowser module."""
    import webbrowser
    try:
        webbrowser.open(url, new=1 if side_window else 0)
    except Exception:
        pass
        return None


@tool("browser_open",
      "Opens a URL in a side window. Args: url (str), profile (int, optional)")
def tool_browser_open(url="", profile=0, **_):
    if not url:
        return "No URL given."
    try:
        _chrome_open(url, profile_num=int(profile))
        return f"Opened {url}"
    except Exception as e:
        return f"Error: {e}"


@tool("youtube_search",
      "Searches YouTube in a side window. Args: query (str), profile (int, optional)")
def tool_youtube_search(query="", profile=0, **_):
    if not query:
        return "No query given."
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    return tool_browser_open(url=url, profile=profile)


@tool("youtube_play_feed",
      "Opens YouTube homepage in a side window. Args: profile (int, optional)")
def tool_youtube_play_feed(profile=0, **_):
    return tool_browser_open(url="https://www.youtube.com", profile=profile)


@tool("google_search",
      "Searches Google in a side window. Args: query (str), profile (int, optional)")
def tool_google_search(query="", profile=0, **_):
    if not query:
        return "No query given."
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    return tool_browser_open(url=url, profile=profile)


@tool("google_drive_open",
      "Opens Google Drive. Args: search (str, optional), profile (int, optional)")
def tool_google_drive_open(search="", profile=0, **_):
    if search:
        url = f"https://drive.google.com/drive/search?q={urllib.parse.quote(search)}"
    else:
        url = "https://drive.google.com"
    return tool_browser_open(url=url, profile=profile)


@tool("browser_type",
      "Types text into the currently focused browser window. Args: text (str), press_enter (bool, default true)")
def tool_browser_type(text="", press_enter=True, **_):
    if not text:
        return "No text given."
    try:
        import pyautogui
        import time
        time.sleep(0.4)
        pyautogui.typewrite(text, interval=0.04)
        if press_enter:
            pyautogui.press("enter")
        return f"Typed: {text}"
    except ImportError:
        return "pyautogui not installed. Run: pip install pyautogui"
    except Exception as e:
        return f"Type error: {e}"


# =============================================================
#  VLM / CURSOR / SCREENSHOT TOOLS
# =============================================================

@tool("cursor_move",
      "Moves mouse cursor to normalized (0..1) position on a display. "
      "Args: x (float), y (float), display (int, optional), pixels (bool, default false)")
def tool_cursor_move(x: float = 0.5, y: float = 0.5, display=None, pixels: bool = False, **_):
    display = vlm._coerce_display_index(display) if display else vlm._current_cursor_display()
    if pixels:
        left, top, w, h = vlm._display_bounds(display)
        if w <= 0 or h <= 0:
            return f"Invalid display {display}."
        pos = vlm._xy_for_display(display, x / max(1.0, float(w)), y / max(1.0, float(h)))
    else:
        pos = vlm._xy_for_display(display, x, y)
    if pos is None:
        return "Could not resolve position."
    x_pos, y_pos = pos
    err = vlm._safe_pyautogui_call(lambda: vlm._pyautogui().moveTo(x_pos, y_pos))
    if err:
        return err
    return f"Moved cursor to x={x_pos}, y={y_pos} on display {display}."


@tool("cursor_click",
      "Clicks mouse button. Args: button='left'|'right'|'middle', clicks=1, interval=0.0, x=None, y=None, display=None")
def tool_cursor_click(button="left", clicks=1, interval=0.0, x=None, y=None, display=None, **_):
    pg = vlm._pyautogui()
    if pg is None:
        return "pyautogui not installed. Run: pip install pyautogui"
    if x is not None and y is not None:
        display = vlm._coerce_display_index(display) if display else vlm._current_cursor_display()
        pos = vlm._xy_for_display(display, x, y)
        if pos is None:
            return "Could not resolve position."
        err = vlm._safe_pyautogui_call(lambda: pg.moveTo(pos[0], pos[1], duration=0.0))
        if err:
            return err
    try:
        pg.click(button=button, clicks=int(clicks), interval=float(interval))
    except Exception as e:
        return f"Click error: {e}"
    return f"Clicked {button} {clicks} time(s)."


@tool("mouse_wheel",
      "Scroll mouse wheel. Args: amount (int, negative=down), x=None, y=None, display=None")
def tool_mouse_wheel(amount=0, x=None, y=None, display=None, **_):
    pg = vlm._pyautogui()
    if pg is None:
        return "pyautogui not installed. Run: pip install pyautogui"
    if x is not None and y is not None:
        display = vlm._coerce_display_index(display) if display else vlm._current_cursor_display()
        pos = vlm._xy_for_display(display, x, y)
        if pos is None:
            return "Could not resolve position."
        pg.moveTo(pos[0], pos[1], duration=0.0)
    try:
        pg.scroll(int(amount))
    except Exception as e:
        return f"Scroll error: {e}"
    return f"Scrolled by {amount}."


@tool("keyboard_tap",
      "Presses one key, shortcut, or list of keys. Args: key (str), keys (list[str], optional)")
def tool_keyboard_tap(key=None, keys=None, **_):
    pg = vlm._pyautogui()
    if pg is None:
        return "pyautogui not installed. Run: pip install pyautogui"
    if keys is not None:
        if isinstance(keys, str):
            key_seq = [k.strip() for k in keys.split(",") if k.strip()]
        else:
            key_seq = [str(k).strip() for k in keys if str(k).strip()]
        try:
            pg.hotkey(*key_seq)
            return f"Pressed hotkey: {', '.join(key_seq)}."
        except Exception as e:
            return f"Hotkey error: {e}"
    if not key:
        return "No key provided."
    try:
        pg.press(str(key))
        return f"Pressed key: {key}."
    except Exception as e:
        return f"Key press error: {e}"


@tool("agent_screenshot_now",
      "Capture one fresh screenshot per display immediately. Returns list of paths.")
def tool_agent_screenshot_now(**_):
    try:
        return vlm._run_screenshot_capture_once()
    except Exception as e:
        return f"Screenshot error: {e}"


@tool("agent_screenshot_paths",
      "Return last captured screenshot file paths for every active display.")
def tool_agent_screenshot_paths(**_):
    with state._agent_screenshot_lock:
        return list(state._agent_latest_screenshot_paths)


@tool("undo_last",
      "Undo the most recent system change (registry write, power plan, startup entry). "
      "Call this when the user says 'undo', 'undo that', 'undo last', or 'reverse that'.")
def tool_undo_last(**_):
    import core.system_access as _sa
    return _sa.undo_last()


@tool("start_recording",
      "Start recording the user's workflow. Captures screenshots and input events. "
      "Call this when the user says 'watch what I do', 'record this', 'learn this workflow'.")
def tool_start_recording(**_):
    from core.workflow_recorder import get_recorder
    recorder = get_recorder()
    if recorder.is_recording:
        return "Already recording."
    recorder.start_recording()
    state.workflow_recording = True
    return "Recording started. I'm watching — perform your workflow, then say 'stop recording'."


@tool("stop_recording",
      "Stop recording and save the workflow as a replayable skill. "
      "Args: name (str, optional), description (str, optional). "
      "Call this when the user says 'stop recording', 'save that', 'done recording'.")
def tool_stop_recording(name="", description="", **_):
    from core.workflow_recorder import get_recorder
    recorder = get_recorder()
    if not recorder.is_recording:
        return "Not currently recording."
    skill = recorder.stop_recording(skill_name=name, description=description)
    state.workflow_recording = False
    if skill:
        return f"Saved skill '{skill['name']}' with {len(skill['steps'])} steps."
    return "Recording stopped but no steps were captured."


@tool("list_skills",
      "List all recorded workflow skills available for replay.")
def tool_list_skills(**_):
    from core.workflow_recorder import SkillStore
    store = SkillStore()
    skills = store.list_all()
    if not skills:
        return "No saved skills yet. Say 'watch what I do' to record one."
    lines = [f"- {s['name']}: {s['description']} ({s['steps']} steps)" for s in skills]
    return "Available skills:\n" + "\n".join(lines)


@tool("replay_skill",
      "Replay a previously recorded workflow skill. Args: name (str) — the skill name to replay.")
def tool_replay_skill(name="", **_):
    if not name:
        return "No skill name given. Use list_skills to see available skills."
    from core.workflow_recorder import SkillStore
    store = SkillStore()
    skill = store.load(name)
    if not skill:
        return f"Skill '{name}' not found. Use list_skills to see available skills."
    return f"REPLAY_SKILL:{name}"


# =============================================================
#  ROUTING
# =============================================================

_THINK_WORDS = [
    "think about", "think through", "reason", "analyze", "analyse",
    "plan", "figure out", "step by step", "deep dive", "explain in detail",
    "how does", "why does", "break down",
]
_SEARCH_WORDS = [
    "search", "look up", "find out", "latest", "news about",
    "what's happening", "current", "today", "right now", "recent",
    "who is", "what is the", "tell me about",
]


def route(text: str) -> tuple[bool, bool]:
    """Returns (use_tools, do_search)."""
    low = text.lower()
    
    # Fast-path for undo commands
    if low in ["undo", "undo last"]:
        return False, False
    if low == "undo all":
        return False, False
        
    wants_think  = any(kw in low for kw in _THINK_WORDS)
    wants_search = any(kw in low for kw in _SEARCH_WORDS)
    if wants_think:
        return True, wants_search
    if wants_search:
        return False, True
    return False, False


# =============================================================
#  PROMPTS
# =============================================================

def build_fast_prompt() -> str:
    mem = memory_mod.as_text()
    return (
        "You are Whiztant, a sharp, fast voice assistant. "
        "Reply in 1-3 short sentences. No lists. No markdown. "
        "Speak naturally as if in a conversation. "
        "If given a [SEARCH RESULT], summarize the key point in plain speech.\n\n"
        f"WHAT YOU KNOW ABOUT THE USER:\n{mem}"
    )


def build_smart_prompt() -> str:
    tool_lines = "\n".join(
        f"  {name}: {info['desc']}"
        for name, info in TOOLS.items()
    )
    mem = memory_mod.as_text()
    return f"""{SYSTEM_PROMPT}

WHAT YOU KNOW ABOUT THE USER:
{mem}

AVAILABLE TOOLS:
{tool_lines}

TWO RESPONSE MODES ONLY:

MODE 1 — plain text
For conversation, questions, summaries. Just reply.

MODE 2 — tool call
For any system action. Output ONLY this JSON:
{{"tool": "tool_name", "args": {{"arg_name": "value"}}, "say": "under 8 words spoken aloud"}}

RULES:
- Use a tool when action is needed. Never describe what you would do — do it.
- After a TOOL RESULT, summarize in 1-2 sentences max.
- One tool per turn. Continue from the result if more steps needed.
"""


# =============================================================
#  RESPONSE PARSER
# =============================================================

def parse_response(raw: str):
    raw = raw.strip()
    match = re.search(r'\{[^{}]*"tool"[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if "tool" in data and data["tool"] in TOOLS:
                return ("tool", data)
        except (json.JSONDecodeError, KeyError):
            pass
    return ("text", raw)


# =============================================================
#  ASK AI — all LLM calls go through call_llm() via OpenAI API
# =============================================================

def _agent_step_callback(step_num: int, response_text: str, total_steps: int = None):
    """
    Called by agent loop on each step for live progress.
    
    Args:
        step_num: Current step number (1-indexed)
        response_text: Step description or action text
        total_steps: Total number of steps in plan (optional, for "X of Y" display)
    """
    if total_steps:
        print(f"[Agent] Step {step_num}/{total_steps} complete")
        step_label = f"Step {step_num}/{total_steps}"
    else:
        print(f"[Agent] Step {step_num} complete")
        step_label = f"Step {step_num}"
    
    step_text = " ".join(str(response_text).split())
    if step_text:
        add_system_message(f"{step_label}: {step_text[:220]}")

    # Extract the Action line for a compact display description (case-insensitive)
    action_match = re.search(r"(?i)action:\s*(.+?)(?:\n|$)", response_text)
    action_desc = action_match.group(1).strip()[:90] if action_match else step_text[:90] if step_text else "working..."

    # Push to overlay agent log (thread-safe via signal)
    overlay = getattr(state, "chat_overlay", None)
    if overlay is not None:
        try:
            overlay._sig_log.emit(step_label, action_desc, "active")
        except Exception:
            pass

    # Push to any page-level step callback registered in state
    page_cb = getattr(state, "_agent_step_page_cb", None)
    if page_cb is not None:
        try:
            page_cb(step_label, action_desc, "active")
        except Exception:
            pass


def _set_agent_wave_state(name: str):
    # Notify the Electron overlay via the WS bridge
    try:
        from core.ws_bridge import send_wave_state
        wave_map = {
            "recording": "recording",
            "listening": "recording",
            "thinking": "thinking",
            "speaking": "speaking",
            "agent": "agent",
            "idle": "idle",
        }
        if name in wave_map:
            send_wave_state(wave_map[name])
    except Exception:
        pass

    # Legacy Python overlay
    overlay = getattr(state, "overlay", None)
    if overlay is None:
        return
    try:
        if name in ("recording", "listening") and hasattr(overlay, "set_listening"):
            overlay.set_listening()
        elif name == "thinking" and hasattr(overlay, "set_thinking"):
            overlay.set_thinking()
        elif name == "speaking" and hasattr(overlay, "set_speaking"):
            overlay.set_speaking()
        elif name in ("idle", "agent") and hasattr(overlay, "set_idle"):
            overlay.set_idle()
    except Exception:
        pass


_COMPILER_KEYWORDS = [
    "prepare", "set up", "setup", "configure", "build", "deploy",
    "install and configure", "create a", "make a", "design a",
    "optimize my", "clean up", "migrate", "automate", "organize",
    "update all", "fix all", "check all", "audit", "benchmark",
    "for my application", "for my portfolio", "for my project",
    "multiple steps", "several things", "a few things",
]


def _should_use_compiler(text: str) -> bool:
    """
    Detect whether a task is complex enough to use the Intent Compiler
    (dependency graph with parallel steps, checkpoints, re-planning)
    vs the simpler sequential Planner + UI-TARS pipeline.
    
    Heuristic: use compiler for multi-step goals with dependencies.
    Use regular pipeline for simple direct actions.
    """
    low = text.lower().strip()
    
    # Short commands are usually simple actions → regular pipeline
    if len(low.split()) <= 4:
        return False
    
    # Check for compiler-triggering keywords
    if any(kw in low for kw in _COMPILER_KEYWORDS):
        return True
    
    # Check for "and" connecting multiple distinct goals
    if " and " in low and len(low.split()) > 8:
        return True
    
    # Explicit user trigger
    if "compile" in low or "plan this" in low or "break this down" in low:
        return True
    
    return False


def _append_agent_chat(role: str, text: str):
    add_history_message(role, text)


def _transcribe_once_for_agent() -> str:
    from core.voice import record_audio, transcribe
    audio_bytes = record_audio()
    if not audio_bytes:
        return ""
    return transcribe(audio_bytes) or ""


def ask_ai(user_text: str, user_already_added: bool = False, force_agent: bool = False):
    import core.system_access as sys_access
    
    # Handle undo commands directly
    low = user_text.lower().strip()
    if low in ["undo", "undo last"]:
        res = sys_access.undo_last_action()
        add_history_message("assistant", res)
        return
    elif low == "undo all":
        res = sys_access.undo_all_actions()
        add_history_message("assistant", res)
        return
        
    tier = usage.get_tier()
    model = get_model(tier)

    # ── F9×3 Agent mode → UI-TARS via OpenRouter ────────────────
    if state.agent_mode or force_agent:
        if not user_already_added:
            add_history_message("user", user_text)
        if not all(_endpoint_reachable(url) for url in _agent_required_endpoints()):
            message = _mode_offline_message("agent")
            print(f"[Agent] Pre-flight blocked: {message}")
            add_history_message("assistant", message)
            return
        add_system_message(f"Agent task: {user_text}")

        # Pre-flight check so we don't announce "Starting agent task" and then immediately
        # block. The @requires_usage("uitars") decorator on run_agent_task is the real gate
        # (check + increment-on-success); this check avoids the false announcement.
        # Internet is required for agent mode; usage can still fall back to the local counter.
        pre_allowed, pre_msg = usage.check_usage("uitars", tier, fail_open=True)
        if not pre_allowed:
            print(f"[Agent] Pre-flight blocked: {pre_msg}")
            add_history_message("assistant", pre_msg)
            return

        executor_name = _agent_executor_name()

        # Decide: Intent Compiler (complex multi-step goals) vs regular agent pipeline
        use_compiler = executor_name != "agent_s3" and _should_use_compiler(user_text)

        if use_compiler:
            print(f"\n[Router] AGENT mode → Intent Compiler")
        elif executor_name == "agent_s3":
            print(f"\n[Router] AGENT mode → Agent S3")
        else:
            print(f"\n[Router] AGENT mode → Planner + UI-TARS grounding")

        stop_event = threading.Event()
        state._agent_stop_event = stop_event
        state._agent_running = True

        try:
            if use_compiler:
                from core.intent_compiler import run_compiled_task
                summary = asyncio.run(run_compiled_task(
                    goal=user_text,
                    speak_fn=_speak_via_tts,
                    transcribe_fn=_transcribe_once_for_agent,
                    set_wave_state_fn=_set_agent_wave_state,
                    append_chat_fn=_append_agent_chat,
                    stop_event=stop_event,
                ))
            elif executor_name == "agent_s3":
                from core.agent_s3_wrapper import run_agent_s3_task

                summary = asyncio.run(run_agent_s3_task(
                    task=user_text,
                    speak_fn=_speak_via_tts,
                    set_wave_state_fn=_set_agent_wave_state,
                    append_chat_fn=_append_agent_chat,
                    stop_event=stop_event,
                    max_steps=int(os.getenv("AGENT_MAX_STEPS", "20")),
                ))
            else:
                from core.toast import show_toast

                overlay = getattr(state, "chat_overlay", None)
                if overlay:
                    overlay.show_progress(user_text)

                def _progress_cb(event_type: str, message: str) -> None:
                    if overlay:
                        overlay.update_progress(event_type, message)

                summary = vlm.run_agent_task(
                    task=user_text,
                    toast=lambda title, body: show_toast(body, title),
                    progress_cb=_progress_cb,
                )
        except Exception as e:
            summary = f"Agent stopped: {e}"
        finally:
            state._agent_running = False
            state._agent_stop_event = None
            _set_agent_wave_state("idle")

        if summary is None:
            # Blocked by @requires_usage on run_agent_task; message already spoken.
            return

        print(f"[Agent] {summary}")
        add_history_message("assistant", summary)
        if state.MEMORY_ENABLED and summary:
            memory_mod.update_from_exchange(user_text, summary)
        # Save agent summary to dictation memories so it appears in the Memories tab
        if summary:
            try:
                from core.dictation_memory import add_memory
                add_memory(original_text=user_text, final_text=summary, mode="agent")
            except Exception:
                pass
        return

    # ── Chat routing (overlay text input) ───────────────────────
    if not _endpoint_reachable("https://api.openai.com/v1/models"):
        message = _mode_offline_message("chat")
        print(f"[Tune] Blocked: {message}")
        if not user_already_added:
            add_history_message("user", user_text)
        add_history_message("assistant", message)
        return

    use_tools, do_search = route(user_text)
    print(f"\n[Router] model={model}  tools={use_tools}  search={do_search}")

    # Optional web search
    search_context = ""
    if do_search:
        print("[Search] Fetching...")
        search_context = tool_web_search(query=user_text)
        print(f"[Search] {search_context[:120]}...")

    augmented = (
        f"{user_text}\n\n[SEARCH RESULT]:\n{search_context}"
        if search_context else user_text
    )

    if not user_already_added:
        add_history_message("user", user_text)

    conversation_messages = list(state.conversation_history[1:])
    if conversation_messages and conversation_messages[-1].get("role") == "user":
        conversation_messages = conversation_messages[:-1] + [{"role": "user", "content": augmented}]
    elif augmented:
        conversation_messages.append({"role": "user", "content": augmented})

    # Smart: tool-calling loop via call_llm
    if use_tools:
        # Agent tools: fail CLOSED when Supabase is offline (don't risk runaway tool use).
        allowed, msg = usage.check_usage("agent", tier, fail_open=False)
        if not allowed:
            print(f"[Agent] Blocked: {msg}")
            add_history_message("assistant", msg)
            return
        print(f"[Agent] {msg}")

        system_prompt = build_smart_prompt()
        replied = False
        for turn in range(state.MAX_TOOL_TURNS + 1):
            try:
                print(f"[Smart turn {turn + 1}]")
                messages = [{"role": "system", "content": system_prompt}] + conversation_messages[-14:]
                reply = call_llm(messages)
                print(reply)
            except Exception as e:
                print(f"\n[Smart] Error: {e}")
                return  # no increment — API call failed

            response_type, data = parse_response(reply)

            if response_type == "text":
                add_history_message("assistant", reply)
                # Increment only after we got a final text reply — success.
                usage.increment_usage_count("agent", tier)
                if state.MEMORY_ENABLED:
                    memory_mod.update_from_exchange(user_text, reply)
                return

            tool_name = data.get("tool", "")
            args      = data.get("args", {})
            say       = data.get("say", f"Running {tool_name}.")
            print(f"\n[Tool] → {tool_name}  {args}")
            try:
                result = TOOLS[tool_name]["fn"](**args)
            except Exception as e:
                result = f"Tool error: {e}"
            
            # Handle REPLAY_SKILL special result — route to skill replay
            if isinstance(result, str) and result.startswith("REPLAY_SKILL:"):
                skill_name = result[len("REPLAY_SKILL:"):].strip()
                add_history_message("assistant", f"Replaying skill: {skill_name}")
                try:
                    from core.workflow_recorder import SkillStore, replay_skill
                    skill_data = SkillStore().load(skill_name)
                    if skill_data:
                        stop_event = threading.Event()
                        state._agent_stop_event = stop_event
                        state._agent_running = True
                        try:
                            replay_result = asyncio.run(replay_skill(
                                skill_data,
                                speak_fn=_speak_via_tts,
                                transcribe_fn=_transcribe_once_for_agent,
                                set_wave_state_fn=_set_agent_wave_state,
                                append_chat_fn=_append_agent_chat,
                                stop_event=stop_event,
                            ))
                            result = replay_result
                        finally:
                            state._agent_running = False
                            state._agent_stop_event = None
                            _set_agent_wave_state("idle")
                    else:
                        result = f"Skill '{skill_name}' not found."
                except Exception as e:
                    result = f"Skill replay failed: {e}"
            
            print(f"[Result] {str(result)[:200]}")
            add_history_message("assistant", reply)
            add_history_message("user", f"[TOOL RESULT — {tool_name}]:\n{result}")
            conversation_messages = list(state.conversation_history[1:])

        add_history_message("assistant", "Could not complete.")

    # Conversation: single-shot, no tools
    else:
        # Internet was already verified above; Supabase usage can still fall back locally.
        allowed, msg = usage.check_usage("chat", tier, fail_open=True)
        if not allowed:
            print(f"[Tune] Blocked: {msg}")
            add_history_message("assistant", msg)
            return
        print(f"[Tune] {msg}")

        try:
            print("[Tune]")
            system_prompt = build_fast_prompt()
            messages = [{"role": "system", "content": system_prompt}] + conversation_messages[-14:]
            reply = call_llm(messages)
            print(reply)
        except Exception as e:
            print(f"\n[Tune] Error: {e}")
            return  # no increment — API call failed

        # Increment only after a successful LLM response — errors don't burn quota.
        usage.increment_usage_count("chat", tier)
        add_history_message("assistant", reply)
        if state.MEMORY_ENABLED:
            memory_mod.update_from_exchange(user_text, reply)
