"""
core/agent_unified.py — Unified agent brain (single vision-model loop).

One shared orchestration layer for Linux and Windows. Platform-specific
I/O is handled by the runtime injected from platforms.factory.

Ports all Agent S3 features:
  • App awareness + navigation spec injection
  • Completion checklist + minimum verified actions
  • Reflection on failed / no-change steps
  • Instruction optimization (direct URLs)
  • Screenshot diff verification
  • Loop detection + guardrails
  • Overlay progress callbacks
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import time
import concurrent.futures
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image

from core.agent_engine import (
    OMNI_MODEL,
    EXEC_MAX_TOKENS,
    TEMP_EXEC,
    call_api,
    parse_json,
    to_base64,
    quick_preflight,
    refine_task_text,
    canonicalize_url,
)
from core import guardrails as _gr

log = logging.getLogger("core.agent_unified")

# Browsers that support profile selection
_PROFILE_BROWSER_ALIASES = {"chrome", "google chrome", "chromium", "chromium-browser", "edge", "microsoft-edge", "msedge"}

# ── Constants ────────────────────────────────────────────────────────────────

MAX_LOOP_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))
ACTION_SETTLE_MAX = 2.0  # seconds to wait for screen change
ACTION_SETTLE_INTERVAL = 0.1
GROUND_IMG_MAX = int(os.getenv("AGENT_GROUND_IMG_MAX", "960"))

# ── System prompt template ───────────────────────────────────────────────────

_AGENT_SYSTEM_TEMPLATE = """You are a precise desktop automation agent. You control the user's computer by analyzing screenshots and returning structured JSON actions.

## TASK
{task}

## AVAILABLE ACTIONS
Return EXACTLY one JSON object per turn:

{{"action": "click", "params": {{"x": 500, "y": 300, "button": "left"}}, "thought": "clicking the search bar", "completed_step": "Click search bar"}}
{{"action": "type", "params": {{"text": "hello world"}}, "thought": "typing the query", "completed_step": "Type query"}}
{{"action": "hotkey", "params": {{"keys": ["ctrl", "t"]}}, "thought": "opening new tab", "completed_step": "Open new tab"}}
{{"action": "press_key", "params": {{"key": "enter"}}, "thought": "submitting form", "completed_step": "Submit form"}}
{{"action": "scroll", "params": {{"x": 500, "y": 300, "amount": -3}}, "thought": "scrolling down", "completed_step": "Scroll down"}}
{{"action": "open_app", "params": {{"app": "chrome"}}, "thought": "launching chrome", "completed_step": "Open Chrome"}}
{{"action": "navigate", "params": {{"url": "https://google.com", "app": "chrome"}}, "thought": "navigating to google", "completed_step": "Navigate to Google"}}
{{"action": "screenshot", "params": {{}}, "thought": "verifying state", "completed_step": "Verify state"}}
{{"action": "done", "params": {{"result": "Task completed successfully"}}, "thought": "all requirements met"}}
{{"action": "failed", "params": {{"reason": "could not find element after 3 attempts"}}, "thought": "giving up"}}

## RULES
1. The screenshot is your ONLY source of truth. Never assume state.
2. Coordinates are in 0–1000 scale. (0,0) = top-left, (1000,1000) = bottom-right. I will convert to actual pixels.
3. Prefer keyboard shortcuts over clicking when available (Ctrl+L for URL bar, Ctrl+T for new tab, etc.).
4. Before typing, ensure the correct field is focused. If unsure, click it first.
5. Do NOT return "done" until the task is visibly complete on screen.
6. If an action fails twice in a row with no visible change, try a different approach.
7. NEVER return markdown, explanation, or extra text outside the JSON object.
8. The "completed_step" field is optional — include it when a plan step is finished.

## NAVIGATION CONTEXT
{nav_context}

## COMPLETION CHECKLIST
Do NOT return done until ALL of these are visibly true:
{checklist}

{reflection_note}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

async def run_unified_agent(
    task: str,
    runtime,
    speak_fn: Callable | None = None,
    set_wave_state_fn: Callable | None = None,
    append_chat_fn: Callable | None = None,
    stop_event=None,
    max_steps: int = 0,
    credit_check_fn: Callable | None = None,
    steps_taken_ref: list | None = None,
) -> str:
    """Run the unified agent loop. Returns a status message."""
    speak_fn = speak_fn or (lambda *_a, **_k: None)
    set_wave_state_fn = set_wave_state_fn or (lambda *_a, **_k: None)
    append_chat_fn = append_chat_fn or (lambda *_a, **_k: None)
    credit_check_fn = credit_check_fn or (lambda *_a, **_k: True)
    if max_steps <= 0:
        max_steps = MAX_LOOP_STEPS

    log.info("=== Unified Agent task: %r ===", task)
    append_chat_fn("assistant", f"[Agent] Starting: {task}")
    set_wave_state_fn("agent")

    # ── App awareness + pre-flight ──────────────────────────────────────────
    target_app = _detect_app(task)
    nav_context = ""
    starting_verified = 0
    chosen_profile: Optional[str] = None
    if target_app:
        nav_context = _build_nav_context(target_app, task)
        append_chat_fn("assistant", f"[Agent] Detected app: {target_app}")
        log.info("App awareness → %s", target_app)

        # ── Chrome profile picker: ask user if multiple profiles ─────────────
        if target_app.lower().strip() in _PROFILE_BROWSER_ALIASES:
            try:
                profiles = runtime.get_browser_profiles(target_app)
                if len(profiles) > 1:
                    log.info("Multiple Chrome profiles detected: %s", profiles)
                    question_id = f"profile-{int(time.time()*1000)}"
                    question_text = (
                        "Multiple Chrome profiles found. "
                        "Which profile should I access Chrome from?"
                    )
                    from core.ws_bridge import send_agent_question, wait_for_agent_answer
                    send_agent_question(question_id, question_text, profiles)
                    append_chat_fn(
                        "assistant",
                        f"[Agent] {question_text}\nOptions: {', '.join(profiles)}"
                    )
                    answer = wait_for_agent_answer(question_id, timeout=60.0)
                    if answer and answer in profiles:
                        chosen_profile = answer
                        append_chat_fn("assistant", f"[Agent] Using profile: {chosen_profile}")
                        log.info("User chose Chrome profile: %s", chosen_profile)
                    else:
                        chosen_profile = profiles[0] if profiles else "Default"
                        append_chat_fn(
                            "assistant",
                            f"[Agent] No response — defaulting to profile: {chosen_profile}"
                        )
                        log.info("No profile answer received, defaulting to: %s", chosen_profile)
                elif len(profiles) == 1:
                    chosen_profile = profiles[0]
                    log.info("Single Chrome profile found: %s", chosen_profile)
            except Exception as e:
                log.warning("Profile detection failed: %s", e)

        result = runtime.ensure_app_open(target_app, profile=chosen_profile)
        append_chat_fn("assistant", f"[Agent] {result}")
        time.sleep(0.5)
        # Verify window title
        title = runtime.get_foreground_app()
        if target_app.lower() in title.lower():
            starting_verified = 1
            append_chat_fn("assistant", f"[Agent] Verified window: {title}")
        else:
            append_chat_fn("assistant", f"[Agent] Window title: {title} (needs verification)")

    # ── Instruction optimization ────────────────────────────────────────────
    optimized_task = _optimize_instruction(task)
    if optimized_task != task:
        append_chat_fn("assistant", f"[Agent] Optimized: {optimized_task[:200]}")
        log.info("Optimized instruction: %s", optimized_task)

    # ── Completion checklist ────────────────────────────────────────────────
    checklist = _build_completion_checklist(optimized_task, target_app)
    if checklist:
        append_chat_fn("assistant", f"[Agent] Checklist: {len(checklist)} items")

    # ── Fast-path: keyboard-only tasks ──────────────────────────────────────
    fast_result = _try_fast_path(optimized_task, runtime, target_app)
    if fast_result:
        append_chat_fn("assistant", f"[Agent] Fast-path: {fast_result}")
        set_wave_state_fn("idle")
        return fast_result

    # ── Main vision loop ────────────────────────────────────────────────────
    loop_history: List[Tuple[str, str]] = []
    verified_actions = starting_verified
    unchanged_steps = 0
    reflection_note = ""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    try:
        # Prefetch first screenshot
        next_img_future = executor.submit(runtime.screenshot)

        for step in range(1, max_steps + 1):
            if stop_event and stop_event.is_set():
                return "Stopped by user"

            # Mid-flight credit exhaustion check (skip on first step — pre-paid)
            if step > 1 and not credit_check_fn(step):
                msg = "Agent stopped: credits exhausted. Upgrade at whiztant.app/pricing"
                append_chat_fn("assistant", f"[Agent] {msg}")
                set_wave_state_fn("idle")
                _send_done(msg, success=False)
                if steps_taken_ref is not None:
                    steps_taken_ref.append(step - 1)
                return msg

            set_wave_state_fn("thinking")

            try:
                img = next_img_future.result(timeout=5)
            except Exception as e:
                log.warning("Screenshot prefetch failed: %s", e)
                img = runtime.screenshot()

            # Build prompt
            system = _build_system_prompt(
                task=optimized_task,
                nav_context=nav_context,
                checklist=checklist,
                reflection_note=reflection_note,
            )
            history_text = _build_step_history(loop_history, verified_actions)
            user_text = (
                f"Step {step}/{max_steps}\n"
                f"Verified actions so far: {verified_actions}\n"
                f"{history_text}\n"
                f"Next action (JSON only):"
            )

            # Prefetch next screenshot while model thinks
            next_img_future = executor.submit(runtime.screenshot)

            # Call vision model
            b64 = to_base64(img, max_side=GROUND_IMG_MAX)
            raw = _call_vision_model(system, user_text, b64)
            action = parse_json(raw)

            if not action:
                log.error("Model returned invalid JSON: %s", raw[:200])
                append_chat_fn("assistant", f"[Agent] Step {step}: Invalid model response")
                break

            action_type = action.get("action") or action.get("type", "")
            params = action.get("params") or action.get("arguments") or {}
            thought = action.get("thought", "")
            completed_step = action.get("completed_step", "")

            log.info("Step %d: %s | %s", step, action_type, thought)
            if thought:
                append_chat_fn("assistant", f"[Agent] Step {step}: {thought[:200]}")

            # ── Done / Failed ───────────────────────────────────────────────
            if action_type == "done":
                min_required = _minimum_verified_actions(optimized_task, checklist)
                if verified_actions < min_required:
                    reflection_note = (
                        f"Do not return done yet. Verified progress is too low "
                        f"({verified_actions}/{min_required}). The completion checklist must be visibly true before done."
                    )
                    append_chat_fn("assistant", f"[Agent] Completion rejected: need {min_required} verified changes")
                    continue
                result = params.get("result", "Task completed")
                append_chat_fn("assistant", f"[Agent] Complete: {result}")
                set_wave_state_fn("idle")
                _send_done(result, success=True)
                if steps_taken_ref is not None:
                    steps_taken_ref.append(step)
                return result

            if action_type == "failed":
                reason = params.get("reason", "Unknown failure")
                append_chat_fn("assistant", f"[Agent] Failed: {reason}")
                set_wave_state_fn("idle")
                _send_done(reason, success=False)
                if steps_taken_ref is not None:
                    steps_taken_ref.append(step)
                return f"Agent failed: {reason}"

            # ── Guardrails ──────────────────────────────────────────────────
            action_text = f"{action_type} {params}"
            is_dest, dest_reason = _gr.is_destructive_action(action_text)
            if is_dest:
                log.warning("Guardrail blocked: %s", dest_reason)
                append_chat_fn("assistant", f"[Agent] Blocked: {dest_reason}")
                _send_blocked(dest_reason)
                return f"Blocked by safety guardrail: {dest_reason}"

            if action_type in ("click", "scroll"):
                coords = _extract_coords(params)
                if coords:
                    x, y = coords
                    valid, coord_reason = _gr.validate_coordinates(x, y)
                    if not valid:
                        log.warning("Guardrail blocked coords: %s", coord_reason)
                        _send_blocked(coord_reason)
                        break

            # ── Loop detection ──────────────────────────────────────────────
            img_hash = _screenshot_hash(img)
            loop_history.append((action_type, img_hash))
            if _gr.detect_loop(loop_history):
                msg = f"Loop detected at step {step} — aborting"
                log.warning(msg)
                _send_blocked("loop_detected")
                return msg

            # ── Progress ────────────────────────────────────────────────────
            _send_step(step, max_steps, action_type, completed_step or action_type)

            # ── Execute ─────────────────────────────────────────────────────
            set_wave_state_fn("agent")
            before_hash = img_hash
            _execute_action(action_type, params, runtime)

            # ── Verify ──────────────────────────────────────────────────────
            after_img = runtime.screenshot()
            after_hash = _screenshot_hash(after_img)
            if after_hash != before_hash:
                verified_actions += 1
                unchanged_steps = 0
                reflection_note = ""
                append_chat_fn("assistant", f"[Agent] Verified change after step {step}")
            else:
                unchanged_steps += 1
                reflection_note = (
                    "The previous action did not create a visible screen change. "
                    "Do not assume it worked. Re-check and try a different approach if needed."
                )
                append_chat_fn("assistant", f"[Agent] Warning: no visible change after step {step}")
                if unchanged_steps >= 3:
                    return f"Agent could not verify progress on screen (step {step})"

            # Adaptive settle: wait up to ACTION_SETTLE_MAX for change
            if after_hash == before_hash:
                _adaptive_settle(runtime, before_hash)

    finally:
        executor.shutdown(wait=False)
        set_wave_state_fn("idle")

    limit_msg = f"Reached {max_steps}-step limit — task may be incomplete"
    _send_done(limit_msg, success=False)
    if steps_taken_ref is not None:
        steps_taken_ref.append(max_steps)
    return limit_msg


# ═══════════════════════════════════════════════════════════════════════════════
# Action execution
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_action(action_type: str, params: dict, runtime) -> None:
    """Dispatch a parsed action to the runtime."""
    try:
        if action_type == "click":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            button = params.get("button", "left")
            px, py = _translate_coords(runtime, x, y)
            runtime.click(px, py, button=button)
            time.sleep(0.12)

        elif action_type == "type":
            text = str(params.get("text", ""))
            runtime.type_text(text)
            time.sleep(0.12)

        elif action_type == "hotkey":
            keys = params.get("keys", [])
            if isinstance(keys, str):
                keys = keys.replace("+", ",").split(",")
            keys = [k.strip() for k in keys if k.strip()]
            if keys:
                runtime.hotkey(*keys)
            time.sleep(0.12)

        elif action_type == "press_key":
            key = str(params.get("key", ""))
            if key:
                runtime.press_key(key)
            time.sleep(0.12)

        elif action_type == "scroll":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            amount = int(params.get("amount", 3))
            px, py = _translate_coords(runtime, x, y)
            runtime.scroll(px, py, amount)
            time.sleep(0.12)

        elif action_type == "open_app":
            app = str(params.get("app", ""))
            if app:
                runtime.ensure_app_open(app)
            time.sleep(1.0)

        elif action_type == "navigate":
            url = canonicalize_url(str(params.get("url", "")))
            app = str(params.get("app", "chrome"))
            if url:
                runtime.ensure_app_open(app)
                time.sleep(0.5)
                runtime.hotkey("ctrl", "l")
                time.sleep(0.1)
                runtime.type_text(url)
                time.sleep(0.1)
                runtime.press_key("return")
                time.sleep(0.5)

        elif action_type == "screenshot":
            # No-op — next iteration will capture anyway
            time.sleep(0.2)

        else:
            log.warning("Unknown action type: %s", action_type)

    except Exception as e:
        log.error("Action execution failed: %s", e, exc_info=True)


def _translate_coords(runtime, x_1000: int, y_1000: int) -> Tuple[int, int]:
    """Convert 0–1000 scale to actual screen pixels."""
    w, h = runtime.screen_size()
    return int(x_1000 / 1000 * w), int(y_1000 / 1000 * h)


def _extract_coords(params: dict) -> Optional[Tuple[int, int]]:
    """Try to extract x,y from action params."""
    x = params.get("x")
    y = params.get("y")
    if x is not None and y is not None:
        try:
            return int(x), int(y)
        except (TypeError, ValueError):
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Fast path
# ═══════════════════════════════════════════════════════════════════════════════

def _try_fast_path(task: str, runtime, target_app: Optional[str]) -> Optional[str]:
    """If the task is a simple keyboard shortcut or app launch, skip the vision model."""
    lowered = task.lower().strip()

    # Simple app open
    if lowered.startswith("open ") and len(lowered.split()) <= 3:
        app = lowered.replace("open ", "").strip()
        result = runtime.ensure_app_open(app)
        return f"Opened {app}. {result}"

    # Known keyboard shortcuts
    shortcuts = {
        "new tab": (["ctrl", "t"], "Opened new tab"),
        "close tab": (["ctrl", "w"], "Closed tab"),
        "refresh": (["f5"], "Refreshed page"),
        "reload": (["f5"], "Reloaded page"),
        "fullscreen": (["f11"], "Toggled fullscreen"),
        "address bar": (["ctrl", "l"], "Focused address bar"),
        "url bar": (["ctrl", "l"], "Focused address bar"),
        "copy": (["ctrl", "c"], "Copied"),
        "paste": (["ctrl", "v"], "Pasted"),
        "undo": (["ctrl", "z"], "Undid"),
        "select all": (["ctrl", "a"], "Selected all"),
    }
    for phrase, (keys, msg) in shortcuts.items():
        if phrase in lowered:
            if target_app:
                runtime.ensure_app_open(target_app)
                time.sleep(0.3)
            runtime.hotkey(*keys)
            return msg

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Vision model call
# ═══════════════════════════════════════════════════════════════════════════════

def _call_vision_model(system: str, user_text: str, b64_img: str) -> str:
    """Call the vision model with a screenshot."""
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                {"type": "text", "text": user_text},
            ],
        },
    ]
    return call_api(OMNI_MODEL, messages, TEMP_EXEC, EXEC_MAX_TOKENS, thinking=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt construction
# ═══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt(
    task: str,
    nav_context: str = "",
    checklist: List[str] | None = None,
    reflection_note: str = "",
) -> str:
    checklist_text = "\n".join(f"- {item}" for item in (checklist or [])) or "(none defined)"
    return _AGENT_SYSTEM_TEMPLATE.format(
        task=task,
        nav_context=nav_context or "(none)",
        checklist=checklist_text,
        reflection_note=reflection_note or "",
    )


def _build_step_history(loop_history: List[Tuple[str, str]], verified: int) -> str:
    if not loop_history:
        return "No previous actions."
    lines = [f"Previous actions ({len(loop_history)} total, {verified} verified):"]
    for i, (action, _hash) in enumerate(loop_history[-6:], start=1):
        lines.append(f"  {i}. {action}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# App awareness (ported from S3)
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_app(task: str) -> Optional[str]:
    """Detect target app from the task string."""
    # app_detector module was removed in cleanup; return None for now
    return None


def _build_nav_context(target_app: str, task: str) -> str:
    """Load navigation spec for the target app and build a context string."""
    # app_detector module was removed in cleanup; return empty for now
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Completion checklist (ported from S3)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_completion_checklist(task: str, target_app: Optional[str]) -> List[str]:
    lower = task.lower()
    items: List[str] = []

    if target_app == "settings":
        items.append("Settings is visibly open and active")
    elif target_app == "file_explorer":
        items.append("File Explorer is visibly open and active")
    elif target_app == "terminal":
        items.append("The terminal window is visibly open and active")
    elif target_app:
        items.append(f"The active app visibly matches {target_app}")

    explicit_url = _extract_url(task)
    if explicit_url:
        items.append(f"The browser has navigated to {explicit_url}")

    if any(kw in lower for kw in ("search", "look up", "find online")):
        items.append("The requested search is visibly executed")

    if any(kw in lower for kw in ("first video", "play the first", "play first", "first result", "open the first")):
        items.append("The requested first result is visibly open")
    elif any(kw in lower for kw in ("play", "open result", "open the result")):
        items.append("The requested result or content is visibly open")

    if any(kw in lower for kw in ("video", "song", "music", "playlist")):
        items.append("The requested media page or playback state is visible")

    if any(kw in lower for kw in ("theme", "light mode", "dark mode", "accent color", "wallpaper")):
        items.append("The requested appearance change is visibly applied")

    if not items:
        items.append("The visible screen matches the user's requested final outcome")

    return _dedupe(items)


def _minimum_verified_actions(task: str, checklist: List[str]) -> int:
    lower = task.lower()
    minimum = 1
    if len(checklist) >= 4:
        minimum = 3
    elif len(checklist) >= 2:
        minimum = 2
    if any(kw in lower for kw in ("search", "look up", "find online")):
        minimum = max(minimum, 2)
    if any(kw in lower for kw in ("first video", "play the first", "play first", "first result", "open the first")):
        minimum = max(minimum, 3)
    if any(kw in lower for kw in ("theme", "light mode", "dark mode", "wallpaper")):
        minimum = max(minimum, 2)
    return minimum


# ═══════════════════════════════════════════════════════════════════════════════
# Instruction optimization (ported from S3)
# ═══════════════════════════════════════════════════════════════════════════════

def _optimize_instruction(task: str) -> str:
    """Rewrite tasks with direct URLs when possible."""
    lower = task.lower()

    # YouTube search optimization
    m = re.search(r"search\s+(?:youtube|youtube\.com)\s+for\s+(.+?)(?:\s+(?:and|then)\s+|$)", lower)
    if m:
        query = m.group(1).strip(" .,;:!?")
        from urllib.parse import quote_plus
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        return f"Open Chrome and navigate to {url}. Then continue: {task}"

    # Google search optimization
    m = re.search(r"search\s+(?:google|google\.com)\s+for\s+(.+?)(?:\s+(?:and|then)\s+|$)", lower)
    if m:
        query = m.group(1).strip(" .,;:!?")
        from urllib.parse import quote_plus
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        return f"Open Chrome and navigate to {url}. Then continue: {task}"

    # Raw domain match
    dm = re.search(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?:/[^\s]*)?", lower)
    if dm:
        domain = dm.group(0).strip()
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        return f"Open Chrome and enter this exact URL in the address bar first: {domain}. Then continue: {task}"

    return task


def _extract_url(text: str) -> str:
    m = re.search(
        r"\b(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return ""
    url = m.group(0).strip().rstrip(".,;:!?")
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _screenshot_hash(img: Image.Image) -> str:
    """Fast perceptual hash of a PIL image."""
    try:
        # Resize to tiny thumbnail for fast hashing
        thumb = img.resize((32, 32), Image.Resampling.LANCZOS).convert("L")
        return hashlib.md5(thumb.tobytes()).hexdigest()
    except Exception:
        return hashlib.md5(b"").hexdigest()


def _adaptive_settle(runtime, before_hash: str) -> None:
    """Wait up to ACTION_SETTLE_MAX for the screen to change."""
    deadline = time.time() + ACTION_SETTLE_MAX
    while time.time() < deadline:
        time.sleep(ACTION_SETTLE_INTERVAL)
        try:
            img = runtime.screenshot()
            if _screenshot_hash(img) != before_hash:
                break
        except Exception:
            break


def _dedupe(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Overlay bridge helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _send_step(step: int, total: int, action: str, target: str = ""):
    try:
        from core.ws_bridge import send_agent_step_v2
        send_agent_step_v2("agent-task", step, total, action, target)
    except Exception:
        pass


def _send_done(result: str, success: bool = True):
    try:
        from core.ws_bridge import send_agent_done
        send_agent_done("agent-task", result, success=success)
    except Exception:
        pass


def _send_blocked(reason: str):
    try:
        from core.ws_bridge import send_agent_blocked
        send_agent_blocked("agent-task", reason, undoable=False)
    except Exception:
        pass
