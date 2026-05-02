"""
core/vlm_linux.py — Wiztant agent runtime for Linux.
Vision-only architecture with full parity to Windows agent via shared engine.
"""
from __future__ import annotations

import base64
import concurrent.futures
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from io import BytesIO
from PIL import Image

import core as state
from core import guardrails as _gr
from core import shortcuts_loader
from core.agent_engine import (
    BROWSER_APPS,
    EXECUTOR_MODEL,
    EXEC_MAX_TOKENS,
    GROUND_IMG_MAX,
    KEYBOARD_SHORTCUTS,
    KNOWN_APPS,
    MAX_LOOP_STEPS,
    MAX_RESULT_SCROLLS,
    OMNI_MODEL,
    PLAN_MAX_TOKENS,
    PLAN_SYSTEM,
    SITE_ALIASES,
    SITE_URLS,
    STEP_PAUSE,
    TEMP_EXEC,
    TEMP_PLAN,
    TEMP_TARS,
    TEMP_THINK,
    THINK_MAX_TOKENS,
    THINK_SYSTEM,
    TARS_MAX_TOKENS,
    call_api,
    canonicalize_url,
    canonical_site_label,
    entry_category,
    extract_click_target,
    extract_requested_app,
    extract_requested_url,
    find_keyboard_shortcut,
    is_research_task,
    parse_json,
    quick_preflight,
    refine_element_target,
    refine_task_text,
    to_base64,
)
from core.platform_backends import (
    click,
    cursor_position,
    ensure_app_open,
    get_foreground_app,
    hotkey,
    launch_browser,
    list_monitors,
    modifier_key,
    move,
    ocr_image,
    platform_name,
    press_key,
    raise_window,
    screenshot,
    scroll,
    screen_size,
    translate_coordinates,
    type_text,
    validate_screen_coordinates,
)

os.makedirs("data", exist_ok=True)
log = logging.getLogger("core.vlm_linux")

_RULES_DIR = Path(__file__).parent.parent / "agent_rules"

_CATEGORY_TO_FILE: Dict[str, Tuple[str, ...]] = {
    "A": ("apps_microsoft.md", "agent_navigation.md"),
    "B": ("agent_navigation.md", "apps_microsoft.md"),
    "C": ("apps_creative.md", "apps_browsers.md"),
    "D": ("browser_navigation_spec.md", "apps_browsers.md", "websites.md"),
    "E": ("apps_creative.md", "agent_navigation.md"),
    "F": ("apps_microsoft.md", "apps_creative.md"),
    "G": ("agent_universal_optimize.md", "agent_navigation.md"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _load_rule_file(category: str) -> str:
    candidates = _CATEGORY_TO_FILE.get(category.upper(), ("agent_navigation.md",))
    for filename in candidates:
        path = _RULES_DIR / filename
        if path.exists():
            content = path.read_text(encoding="utf-8")
            log.debug("Rule file: %s (%d chars)", filename, len(content))
            return content
    log.warning("Rule file not found for category %s: %s", category, candidates)
    return ""


def _screenshot_and_ocr() -> Tuple[Image.Image, str]:
    img = screenshot()
    text = ocr_image(img)
    return img, text[:1200]


# ═══════════════════════════════════════════════════════════════════════════════
# VISION MODEL CALLS
# ═══════════════════════════════════════════════════════════════════════════════

def _ask_vision(task: str, step: int, repeat_warning: str = "") -> dict:
    log.info("Step %d: Vision path", step + 1)
    img = screenshot()
    b64 = to_base64(img)
    w, h = screen_size()
    mod = modifier_key()

    system = (
        f"You are a {platform_name()} desktop automation agent. Analyze the screenshot and task. "
        "Return ONLY JSON with action:\n"
        '{"action": "click", "x": <0-1000>, "y": <0-1000>} - click at coordinates\n'
        '{"action": "type", "text": "..."} - type text\n'
        '{"action": "key", "key": "ctrl+a"} - press key combo\n'
        '{"action": "hotkey", "keys": ["ctrl","t"]} - press hotkey\n'
        '{"action": "scroll", "x": <0-1000>, "y": <0-1000>, "amount": 3} - scroll\n'
        '{"action": "open_app", "app": "..."} - launch/focus app\n'
        '{"action": "navigate", "url": "...", "app": "chrome"} - navigate URL\n'
        '{"action": "ask_uitars", "instruction": "click the ..."} - find & click visually\n'
        '{"action": "screenshot"} - capture and verify state\n'
        '{"action": "done", "result": "..."} - task complete\n'
        f"Coordinate system: 0-1000 scale. Modifier key: {mod}.\n"
        "CRITICAL: Return ONLY valid JSON. No markdown, no explanation."
    )

    user_content = f"Task: {task}\nScreen: {w}x{h}\n"
    if repeat_warning:
        user_content += f"\nWARNING: {repeat_warning}\n"
    user_content += "\nNext action (JSON only):"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": user_content},
        ]},
    ]
    raw = call_api(OMNI_MODEL, messages, TEMP_EXEC, EXEC_MAX_TOKENS)
    parsed = parse_json(raw)
    if not parsed:
        log.warning("Vision model returned invalid JSON: %s", raw[:200])
        return {"action": "done", "result": "Failed to parse model response"}
    return parsed


def _ask_uitars_executor(instruction: str, img: Image.Image) -> Optional[dict]:
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
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{to_base64(img)}"}},
            {"type": "text", "text": instruction},
        ]},
    ]
    raw = call_api(EXECUTOR_MODEL, messages, TEMP_TARS, TARS_MAX_TOKENS)
    return parse_json(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION EXECUTOR (rich action types, same as Windows)
# ═══════════════════════════════════════════════════════════════════════════════

def _instruction_variants(instruction: str) -> List[str]:
    base = (instruction or "").strip()
    if not base:
        return []
    target = re.sub(r"^click\s+", "", base, flags=re.IGNORECASE)
    refined_target = refine_element_target(target)
    variants = [base, f"click {refined_target}"]
    if "sign in" in refined_target:
        variants.extend(["click sign in button", "click sign in", "click log in", "click login"])
    deduped: List[str] = []
    seen: set[str] = set()
    for item in variants:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return deduped


def _execute(
    action: dict,
    prefetched_img: Optional[Image.Image] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    t = action.get("type") or action.get("action", "")

    if t == "open_app":
        app_name = action.get("app", "")
        url = action.get("url", "")
        canonical = KNOWN_APPS.get(app_name.strip().lower(), app_name)
        if canonical in BROWSER_APPS or app_name.strip().lower() in BROWSER_APPS:
            if url:
                result = launch_browser(app_name, url=url)
            else:
                result = launch_browser(app_name)
        else:
            result = ensure_app_open(app_name, url=url)
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "hotkey":
        keys = action.get("keys", [])
        if isinstance(keys, str):
            keys = keys.split("+")
        success, msg = hotkey(*keys)
        time.sleep(0.2)
        result = msg if success else f"failed: {msg}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t in ("type", "typewrite"):
        text = action.get("text", "")
        success, msg = type_text(text, interval=action.get("interval", 0.01))
        time.sleep(0.2)
        result = msg if success else f"failed: {msg}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t in ("press", "key"):
        key = action.get("key") or action.get("keys", "enter")
        if isinstance(key, list):
            success, msg = hotkey(*key)
        else:
            success, msg = press_key(key)
        time.sleep(0.2)
        result = msg if success else f"failed: {msg}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "click":
        coords = action.get("coordinates") or [action.get("x"), action.get("y")]
        if coords and len(coords) >= 2:
            translated = translate_coordinates(coords[0], coords[1], reason="model_click")
            if translated:
                success, msg = click(translated[0], translated[1])
                time.sleep(0.2)
                return msg if success else f"failed: {msg}"
        return "invalid click coordinates"

    if t == "scroll":
        coords = action.get("coordinates") or [action.get("x"), action.get("y")]
        amount = action.get("amount", 3)
        if coords and len(coords) >= 2:
            translated = translate_coordinates(coords[0], coords[1], reason="scroll")
            if translated:
                success, msg = scroll(translated[0], translated[1], amount)
                time.sleep(0.2)
                return msg if success else f"failed: {msg}"
        return "invalid scroll coordinates"

    if t == "wait":
        secs = float(action.get("seconds", 1.0))
        time.sleep(secs)
        return f"waited {secs}s"

    if t == "navigate":
        url = canonicalize_url(action.get("url", ""))
        app = action.get("app", "chrome")
        ensure_app_open(app)
        # Focus URL bar and type
        hotkey("ctrl", "l")
        time.sleep(0.12)
        type_text(url, interval=0.01)
        time.sleep(0.12)
        press_key("return")
        time.sleep(0.12)
        result = f"navigated to {url}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "find_video_result":
        query = action.get("query", "")
        hint = action.get("hint", "")
        max_scrolls = int(action.get("max_scrolls", MAX_RESULT_SCROLLS))
        if query and hint:
            instruction = f"click the first youtube video thumbnail for {query} ({hint})"
        elif query:
            instruction = f"click the first youtube video thumbnail for {query}"
        else:
            instruction = "click the first youtube video thumbnail in the results"
        for scroll_index in range(max_scrolls + 1):
            img = screenshot()
            if progress_cb:
                progress_cb("step", f"Finding first video {scroll_index + 1}/{max_scrolls + 1}...")
            result_data = _ask_uitars_executor(instruction, img)
            if result_data and result_data.get("action") == "click":
                coords = translate_coordinates(result_data.get("x"), result_data.get("y"),
                                                reason=f"video_result:{instruction}")
                if coords:
                    success, _ = click(coords[0], coords[1])
                    if success:
                        return f"clicked '{result_data.get('element', instruction)}'"
            if scroll_index < max_scrolls:
                # Scroll down
                w, h = screen_size()
                scroll(int(w * 0.5), int(h * 0.6), -5)
                time.sleep(0.6)
        return f"failed: could not find requested video result{f' ({hint})' if hint else ''}"

    if t == "ask_uitars":
        instruction = action.get("instruction", "")
        shortcut = find_keyboard_shortcut(instruction)
        if shortcut:
            success, msg = hotkey(*shortcut)
            time.sleep(STEP_PAUSE)
            result = f"keyboard: {'+'.join(shortcut)} (for '{instruction}')"
            if progress_cb:
                progress_cb("step", result)
            return result

        for attempt, candidate in enumerate(_instruction_variants(instruction), start=1):
            img = prefetched_img if attempt == 1 and prefetched_img else screenshot()
            if progress_cb:
                progress_cb("step", f"Finding '{candidate}' on screen...")
            result_data = _ask_uitars_executor(candidate, img)
            if result_data and result_data.get("action") == "click":
                coords = translate_coordinates(result_data.get("x"), result_data.get("y"),
                                                reason=f"uitars:{candidate}")
                if coords:
                    success, _ = click(coords[0], coords[1])
                    if success:
                        result = f"clicked '{result_data.get('element', candidate)}'"
                        if progress_cb:
                            progress_cb("step", result)
                        return result
        result = f"could not find: {instruction}"
        if progress_cb:
            progress_cb("step", result)
        return result

    if t == "screenshot":
        img, ocr = _screenshot_and_ocr()
        short = ocr[:600] if ocr else "(no text detected)"
        return f"Screenshot captured. Visible text:\n{short}"

    if t in ("done", "failed"):
        return action.get("message", action.get("result", t))

    return f"unknown action: {t}"


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT THINK
# ═══════════════════════════════════════════════════════════════════════════════

def _preflight(task: str) -> dict:
    log.info("Pre-flight think: %r", task)
    quick = quick_preflight(task)
    if quick:
        log.info("Quick pre-flight → app=%s strategy=%s", quick.get("app_to_open"), quick.get("strategy"))
        return quick

    refined_task = refine_task_text(task)
    messages = [
        {"role": "system", "content": THINK_SYSTEM},
        {"role": "user", "content": f"Task: {refined_task}"},
    ]
    raw = call_api(OMNI_MODEL, messages, TEMP_THINK, THINK_MAX_TOKENS, thinking=False)
    result = parse_json(raw)
    if result:
        result["clean_task"] = refine_task_text(result.get("clean_task", refined_task))
        log.info("Pre-flight → app=%s research=%s", result.get("app_to_open"), result.get("needs_research"))
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


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — PLANNING
# ═══════════════════════════════════════════════════════════════════════════════

def _heuristic_plan(task: str, preflight: dict) -> Optional[dict]:
    app_name = preflight.get("app_to_open", "")
    url, site_label = extract_requested_url(task)
    click_target = extract_click_target(task)
    if not (url or click_target or app_name):
        return None
    steps: List[str] = []
    initial_action: Optional[dict] = None
    if app_name:
        steps.append(f"Open {app_name}")
        initial_action = {"type": "open_app", "app": app_name}
    elif url:
        steps.append(f"Open browser")
        initial_action = {"type": "open_app", "app": "chrome"}
    if url:
        steps.append(f"Navigate to {site_label or url}")
    if click_target:
        steps.append(f"Click {click_target}")
    return {
        "category": "D",
        "confidence": 0.95,
        "task_summary": task,
        "steps": steps,
        "initial_action": initial_action or {"type": "open_app", "app": "chrome"},
        "requires_uitars": bool(click_target),
    }


def _sanitize_plan(plan: dict) -> dict:
    steps = plan.get("steps", [])
    cleaned: List[Any] = []
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


def _phase1(task: str, preflight: dict) -> Optional[dict]:
    clean_task = preflight.get("clean_task", task)
    app_name = preflight.get("app_to_open", "")
    log.info("Phase 1 planning: %r", clean_task)
    fast_plan = _heuristic_plan(clean_task, preflight)
    if fast_plan and (extract_requested_url(clean_task)[0] or extract_click_target(clean_task)):
        log.info("Phase 1 using fast deterministic browser plan")
        return fast_plan
    category = entry_category(preflight.get("entry_point"))
    rule_hint = _load_rule_file(category)
    shortcut_hint = shortcuts_loader.load_shortcuts(category)
    sys_prompt = PLAN_SYSTEM
    if rule_hint:
        sys_prompt += f"\n\n## RULE FILE\n{rule_hint}"
    if shortcut_hint:
        sys_prompt += f"\n\n## Available shortcuts for this task:\n{shortcut_hint}"
    context = (
        f"Task: {clean_task}\n"
        f"App to open: {app_name or 'none specified'}\n"
        f"Entry point: {preflight.get('entry_point')}\n"
        f"Strategy: {preflight.get('strategy')}\n"
        f"Steps expected: {preflight.get('step_count')}\n"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": context},
    ]
    raw = call_api(OMNI_MODEL, messages, TEMP_PLAN, PLAN_MAX_TOKENS)
    plan = parse_json(raw)
    if plan:
        plan = _sanitize_plan(plan)
        log.info("Plan: %d steps", len(plan.get("steps", [])))
    return plan


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — EXECUTION LOOP (shared orchestration, vision-only on Linux)
# ═══════════════════════════════════════════════════════════════════════════════

def _phase2_system(task: str, plan: dict, rule_content: str, system_context_md: str = "") -> str:
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan.get("steps", [])))
    mod = modifier_key()
    return f"""\
You are a computer use agent executing tasks on the user's {platform_name()} desktop. You control the desktop by choosing actions: clicking, typing, pressing keys, navigating URLs, and taking screenshots to verify state.

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
2. Identify the currently focused element.
3. Verify that focused element is the intended target.
4. If it is NOT the intended target → execute FOCUS ESCAPE PROCEDURE before typing.

RULE 1 — FOCUS IDENTIFICATION
Identify the focused element from the current Screen OCR / screenshot context.
If you cannot confidently determine which element is focused, issue a screenshot action first.

RULE 2 — FOCUS ESCAPE PROCEDURE
When the focused element is NOT your intended target:
1. Do NOT type anything.
2. Identify the target application window.
3. Issue ask_uitars to click the title bar of the target window.
4. If the app is not visible, issue ask_uitars to click its taskbar/dock icon.
5. Issue a screenshot action and verify.
6. Issue ask_uitars to click the specific element that should receive input.
7. Issue another screenshot action and confirm cursor is in the correct field.
8. Only then issue type.

RULE 3 — APPLICATION SWITCHING
Never use Alt+Tab to switch applications unless you have confirmed no text field is currently focused.

RULE 4 — BROWSER NAVIGATION PROCEDURE
For any task involving browser navigation:
1. screenshot → identify if target browser is active.
2. ask_uitars to click URL/address bar.
3. type the URL → press enter.
4. screenshot → verify page loaded.
5. ask_uitars to click target in-page element.

RULE 5 — TASK EXECUTION LOOP
For every discrete action: screenshot → identify state → identify focused element → compare to target → redirect focus if needed → execute → verify outcome → proceed or retry.

RULE 6 — IDE CONFLICT HANDLING
If a code editor is open with active file and cursor focus, never type a URL or task input while this state is active. Click a blank area of the desktop first.

RULE 7 — VERIFICATION CHECKPOINTS
Before marking any subtask as complete, take a screenshot and verify expected state is visible in OCR.

ANTI-PATTERNS — NEVER DO THESE
- Do not issue type without confirming correct element has focus via screenshot.
- Do not assume the application you last clicked is still in focus.
- Do not use Alt+Tab without confirming no text field is active.
- Do not proceed to the next step after a failed verification.

## EXECUTION RULES
1. Never produce x/y coordinates — all clicks go through ask_uitars.
2. Never skip steps.
3. Prefer keyboard shortcuts before ask_uitars for known shortcuts ({mod}+L for URL bar, etc.).
4. Do not declare done until OCR confirms all steps complete.
5. Return one JSON object only.
6. If the current action completes a listed step, include "completed_step": "<exact step text>".

## AVAILABLE ACTIONS
Open app:          {{"type":"open_app","app":"chrome"}}
Keyboard shortcut: {{"type":"hotkey","keys":["ctrl","l"]}}
Type text:         {{"type":"type","text":"youtube.com"}}
Press key:         {{"type":"press","key":"enter"}}
Wait:              {{"type":"wait","seconds":2}}
Navigate URL:      {{"type":"navigate","url":"https://youtube.com","app":"chrome"}}
Find+click visual: {{"type":"ask_uitars","instruction":"click the search bar"}}
Verify focus/state:{{"type":"screenshot"}}
All steps done:    {{"type":"done","message":"Task completed"}}
Unrecoverable:     {{"type":"failed","message":"reason"}}
{(chr(10) + "## SYSTEM CONTEXT (installed apps, browsers, paths)" + chr(10) + system_context_md + chr(10)) if system_context_md else ""}"""


def _phase2_loop(
    task: str,
    plan: dict,
    rule_content: str,
    progress_cb: Optional[Callable] = None,
    system_context_md: str = "",
) -> str:
    import hashlib as _hashlib
    from core.ws_bridge import send_agent_step_v2, send_agent_blocked, send_agent_done
    from core.toast import toast_action_blocked

    task_id = f"task_{int(time.time())}"
    log.info("Phase 2 — execution loop starting (task_id=%s)", task_id)
    steps = plan.get("steps", [])
    completed: List[str] = []
    last_result = "Execution started"
    system = _phase2_system(task, plan, rule_content, system_context_md)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    next_context_future = executor.submit(_screenshot_and_ocr)
    loop_history: List[Tuple[str, str]] = []
    try:
        for iteration in range(1, MAX_LOOP_STEPS + 1):
            log.info("Loop %d/%d — %d/%d done", iteration, MAX_LOOP_STEPS, len(completed), len(steps))
            try:
                prefetched_img, ocr_text = next_context_future.result(timeout=5)
            except Exception as e:
                log.warning("Pre-fetch failed: %s — taking fresh screenshot", e)
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
                {"role": "user", "content": user_msg},
            ]
            next_context_future = executor.submit(_screenshot_and_ocr)
            raw = call_api(OMNI_MODEL, messages, TEMP_EXEC, EXEC_MAX_TOKENS)
            action = parse_json(raw)
            if not action:
                log.error("No valid action: %s", raw[:150])
                break
            if action.get("type") == "done" or action.get("action") == "done":
                message = action.get("message", action.get("result", "Task completed"))
                if progress_cb:
                    progress_cb("done", message)
                send_agent_done(task_id, message, success=True)
                return message
            if action.get("type") == "failed" or action.get("action") == "failed":
                message = f"Task failed: {action.get('message', 'unknown')}"
                if progress_cb:
                    progress_cb("error", message)
                send_agent_done(task_id, message, success=False)
                return message

            # Guardrail: destructive action check
            action_text = str(action.get("text", "")) + " " + str(action.get("type", "") or action.get("action", ""))
            is_dest, dest_reason = _gr.is_destructive_action(action_text)
            if is_dest:
                log.warning("Guardrail blocked destructive action: %s", dest_reason)
                toast_action_blocked(dest_reason)
                send_agent_blocked(task_id, dest_reason, undoable=bool(completed))
                if progress_cb:
                    progress_cb("error", f"Blocked: {dest_reason}")
                return f"Action blocked by safety guardrail: {dest_reason}"

            # Guardrail: coordinate bounds check
            act_type = action.get("type") or action.get("action", "")
            if act_type in ("click", "double_click", "right_click", "drag"):
                coords = action.get("coordinates") or action.get("coordinate", [])
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    x, y = int(coords[0]), int(coords[1])
                    valid, coord_reason = _gr.validate_coordinates(x, y)
                    if not valid:
                        log.warning("Guardrail blocked out-of-bounds coords: %s", coord_reason)
                        send_agent_blocked(task_id, coord_reason, undoable=False)
                        break

            # Loop detection
            img_hash = _gr.screenshot_hash(prefetched_img if isinstance(prefetched_img, bytes) else b"")
            loop_history.append((act_type, img_hash))
            if _gr.detect_loop(loop_history):
                msg = f"Loop detected at step {iteration} — aborting"
                log.warning(msg)
                send_agent_blocked(task_id, "loop_detected", undoable=bool(completed))
                if progress_cb:
                    progress_cb("error", msg)
                return msg

            remaining = [s for s in steps if s not in completed]
            current_step_label = remaining[0] if remaining else "finalizing"
            send_agent_step_v2(task_id, iteration, len(steps), act_type, current_step_label)
            if progress_cb:
                progress_cb("step", f"Step {len(completed)+1}/{len(steps)}: {current_step_label}")

            last_result = _execute(action, prefetched_img=prefetched_img, progress_cb=None)
            log.info("Result: %s", last_result)

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


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def _research_pipeline(task: str, progress_cb: Optional[Callable] = None) -> Optional[dict]:
    try:
        raw = call_api(
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
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent_loop(
    task: str,
    toast: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    """
    Main agent loop for Linux.
    Uses the unified architecture: pre-flight → planning → phase 2 execution loop.
    Vision-only (no UIA), with full action parity to Windows.
    """
    log.info("=== Agent task (Linux): %r ===", task)
    if toast:
        toast("Wiztant", "Agent starting...")
    if progress_cb:
        progress_cb("step", "Initializing Linux agent...")

    # Pre-flight
    preflight = _preflight(task)
    app_to_open = preflight.get("app_to_open") or preflight.get("app", "browser")
    ensure_app_open(app_to_open)

    # Planning
    if progress_cb:
        progress_cb("step", "Planning execution...")
    plan = _phase1(task, preflight)
    category = entry_category(preflight.get("entry_point"))
    rule_content = _load_rule_file(category)

    # Phase 2 execution
    return _phase2_loop(task, plan or {}, rule_content, progress_cb=progress_cb)


def run_agent_task(
    task: str,
    toast: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
) -> str:
    """Entry point for agent tasks on Linux."""
    log.info("=== Agent task: %r ===", task)
    if toast:
        toast("Wiztant", "Thinking...")
    if progress_cb:
        progress_cb("step", "Understanding your task...")
    return run_agent_loop(task, toast=toast, progress_cb=progress_cb)


_lock = threading.Lock()
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
            toast("Wiztant", "Agent busy — please wait")
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
            log.error("Agent worker error: %s", e, exc_info=True)
            if progress_cb:
                progress_cb("error", str(e)[:100])
            if toast:
                toast("Wiztant Error", str(e)[:80])
        finally:
            _running = False
    threading.Thread(target=_worker, daemon=True, name="wiztant-agent-linux").start()


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY / COMPATIBILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _take_screenshot() -> Tuple[str, Tuple[int, int], Tuple[int, int]]:
    img = screenshot()
    w, h = img.size
    max_side = max(w, h)
    if max_side > GROUND_IMG_MAX:
        scale = GROUND_IMG_MAX / max_side
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    resized_w, resized_h = img.size
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    physical_w, physical_h = screen_size()
    return b64, (resized_w, resized_h), (physical_w, physical_h)


def capture_window_screenshot(*_args, **_kwargs):
    return _take_screenshot()


def _perform_click(x: int, y: int, reason: str = "") -> Tuple[bool, str]:
    return click(x, y)


def _perform_click_from_model(x_1000: Any, y_1000: Any, reason: str = "") -> Tuple[bool, str]:
    if isinstance(x_1000, (list, tuple)) and len(x_1000) >= 2 and y_1000 is None:
        try:
            x_1000, y_1000 = x_1000[0], x_1000[1]
        except Exception:
            pass
    translated = translate_coordinates(x_1000, y_1000, reason=reason)
    if not translated:
        return False, f"invalid translated click coordinates for {reason or 'action'}"
    return click(translated[0], translated[1])


def _type_text(text: str) -> Tuple[bool, str]:
    return type_text(text)


def _press_key(key: str) -> Tuple[bool, str]:
    return press_key(key)


def _scroll_at(x: int, y: int, amount: int) -> Tuple[bool, str]:
    return scroll(x, y, amount)


def _ensure_app_open(app_name: str) -> str:
    return ensure_app_open(app_name)


def _get_foreground_app() -> str:
    return get_foreground_app()


__all__ = [
    "capture_window_screenshot",
    "run_agent_loop",
    "run_agent_task",
    "run_agent_task_async",
    "_take_screenshot",
    "_perform_click",
    "_perform_click_from_model",
    "_type_text",
    "_press_key",
    "_scroll_at",
    "_ensure_app_open",
    "_get_foreground_app",
]
