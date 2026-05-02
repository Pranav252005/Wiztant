import asyncio
import hashlib
import io
import json
import logging
import os
import platform
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote_plus

import pyautogui

logger = logging.getLogger(__name__)

_agent_s3_instance = None

AGENT_S3_SYSTEM_PROMPT = """CRITICAL RULES:
1. Verify each meaningful action before moving on.
2. Never assume a click, type, or navigation worked without visible evidence on screen.
3. If the task says search for something, do not skip typing the query or triggering the search.
4. If the task mentions a website or domain, prefer entering the exact URL in the address bar when that is faster and more reliable.
5. Do not claim the task is done until the requested final result is visibly present on screen.
6. If the previous action did not visibly change the UI, reconsider and correct the next action instead of pretending it succeeded.

APP MANAGEMENT RULES (from agent_navigation.md + browser_navigation_spec.md):
7. ALWAYS check the window title bar in the screenshot to identify which app is currently active.
8. IF the task says "open [APP]", "use [APP]", "switch to [APP]", or "launch [APP]":
   a) The specified app has been opened/switched to BEFORE this step.
   b) Take a screenshot and verify the window title matches the requested app.
   c) DO NOT interact with any other app — especially do NOT type in Arc, Chrome, or any other browser when a different one was requested.
9. NEVER open or interact with Arc browser unless the user explicitly said "Arc" or "Arc browser".
10. For system tasks ("change theme", "edit registry", "open settings"):
    - These use Windows Settings, Registry Editor, etc. — NOT a browser.
    - The correct system app has been opened before this step.
11. BROWSER NAVIGATION (from browser_navigation_spec.md):
    - Focus address bar: Ctrl+L (universal for all browsers)
    - New tab: Ctrl+T
    - Navigate to URL: Ctrl+L → type URL → Enter
    - Search: Ctrl+L → type query → Enter
    - NEVER click the address bar if Ctrl+L is available.
12. You have access to navigation specifications for each app:
    - Follow the exact steps listed in the app's navigation spec.
    - Use keyboard shortcuts from the spec instead of clicking when possible.
    - The app context and navigation hints are injected below when available."""

AGENT_S3_REFLECTION_PROMPT = """When reflecting on the previous step, focus on visible verification.
If text did not appear, results did not load, or the page did not change, treat the action as unverified.
Never endorse completion without clear on-screen evidence."""


def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _platform_name() -> str:
    system = platform.system().lower()
    return {
        "darwin": "darwin",
        "linux": "linux",
        "windows": "windows",
    }.get(system, "windows")


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class WhiztantAgentS3:
    def __init__(self):
        try:
            from gui_agents.s3.agents.agent_s import AgentS3
            from gui_agents.s3.agents.grounding import OSWorldACI
        except ImportError as e:
            raise RuntimeError(
                "Agent S3 is not installed. Install it with: pip install gui-agents"
            ) from e

        self._agent_cls = AgentS3
        self._grounding_cls = OSWorldACI
        self.platform = _platform_name()

        provider = _cfg("AGENT_S3_PROVIDER", "openai")
        model = _cfg("AGENT_S3_MODEL", "gpt-4o")
        base_url = _cfg("AGENT_S3_BASE_URL", "")
        api_key = _cfg("AGENT_S3_API_KEY", "")
        if not api_key:
            if provider in {"anthropic", "claude"}:
                api_key = _cfg("ANTHROPIC_API_KEY", "")
            elif provider in {"openrouter"}:
                api_key = _cfg("OPENROUTER_API_KEY", "")
            else:
                api_key = _cfg("OPENAI_API_KEY", "")

        self.engine_params: Dict[str, Any] = {
            "engine_type": provider,
            "model": model,
            "api_key": api_key,
        }
        if base_url:
            self.engine_params["base_url"] = base_url

        grounding_provider = _cfg("AGENT_S3_GROUNDING_PROVIDER", "huggingface")
        grounding_model = _cfg("AGENT_S3_GROUNDING_MODEL", "ui-tars-1.5-7b")
        grounding_url = _cfg("AGENT_S3_GROUNDING_URL", "http://localhost:8080")
        grounding_api_key = _cfg("AGENT_S3_GROUNDING_API_KEY", _cfg("HF_TOKEN", ""))
        grounding_width = int(_cfg("AGENT_S3_GROUNDING_WIDTH", "1920"))
        grounding_height = int(_cfg("AGENT_S3_GROUNDING_HEIGHT", "1080"))

        self.engine_params_for_grounding: Dict[str, Any] = {
            "engine_type": grounding_provider,
            "model": grounding_model,
            "base_url": grounding_url,
            "grounding_width": grounding_width,
            "grounding_height": grounding_height,
        }
        if grounding_api_key:
            self.engine_params_for_grounding["api_key"] = grounding_api_key

        self.max_trajectory_length = int(_cfg("AGENT_S3_MAX_TRAJECTORY", "8"))
        self.enable_reflection = _parse_bool(_cfg("AGENT_S3_ENABLE_REFLECTION", "true"), True)
        self.screen_width = int(_cfg("AGENT_S3_SCREEN_WIDTH", str(grounding_width)))
        self.screen_height = int(_cfg("AGENT_S3_SCREEN_HEIGHT", str(grounding_height)))
        self.verification_stall_limit = int(_cfg("AGENT_S3_VERIFICATION_STALL_LIMIT", "3"))
        self.ui_knowledge = self._load_ui_knowledge()
        self.ui_guidance = self._build_ui_guidance()

        self.grounding_agent = self._grounding_cls(
            env=None,
            platform=self.platform,
            engine_params_for_generation=self.engine_params,
            engine_params_for_grounding=self.engine_params_for_grounding,
            width=self.screen_width,
            height=self.screen_height,
        )
        self.agent = self._agent_cls(
            self.engine_params,
            self.grounding_agent,
            platform=self.platform,
            max_trajectory_length=self.max_trajectory_length,
            enable_reflection=self.enable_reflection,
        )
        logger.info("Agent S3 initialized")

    def reset(self):
        try:
            self.agent.reset()
            self._apply_runtime_guidance()
        except Exception:
            pass

    def _load_ui_knowledge(self) -> Dict[str, Any]:
        kb_path = Path(__file__).resolve().with_name("ui_knowledge_base.json")
        if not kb_path.exists():
            logger.warning("[Agent S3] UI knowledge base not found: %s", kb_path)
            return {}
        try:
            data = json.loads(kb_path.read_text(encoding="utf-8"))
            logger.info("[Agent S3] UI knowledge base loaded")
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning("[Agent S3] Failed to load UI knowledge base: %s", e)
            return {}

    def _build_ui_guidance(self) -> str:
        if not self.ui_knowledge:
            return ""
        guidance: list[str] = []
        for domain, metadata in (self.ui_knowledge.get("websites") or {}).items():
            if metadata.get("search_method") == "url_shortcut" and metadata.get("search_url"):
                guidance.append(f"- {domain}: use direct URL search pattern {metadata['search_url']}")
        for name, metadata in (self.ui_knowledge.get("system_ui") or {}).items():
            layout = str(metadata.get("layout") or "").strip()
            if layout:
                guidance.append(f"- {name}: layout={layout}")
        return "Known UI patterns:\n" + "\n".join(guidance) if guidance else ""

    def _apply_runtime_guidance(self):
        executor = getattr(self.agent, "executor", None)
        if executor is None:
            return

        generator_agent = getattr(executor, "generator_agent", None)
        if generator_agent is not None and hasattr(generator_agent, "system_prompt"):
            base_prompt = str(generator_agent.system_prompt or "")
            addition = AGENT_S3_SYSTEM_PROMPT
            if self.ui_guidance:
                addition = f"{addition}\n\n{self.ui_guidance}"
            if addition not in base_prompt:
                generator_agent.add_system_prompt(f"{base_prompt}\n\n{addition}")

        reflection_agent = getattr(executor, "reflection_agent", None)
        if reflection_agent is not None and hasattr(reflection_agent, "system_prompt"):
            reflection_prompt = str(reflection_agent.system_prompt or "")
            if AGENT_S3_REFLECTION_PROMPT not in reflection_prompt:
                reflection_agent.add_system_prompt(f"{reflection_prompt}\n\n{AGENT_S3_REFLECTION_PROMPT}")

    def _screenshots_different(self, before: bytes, after: bytes) -> bool:
        return hashlib.md5(before).hexdigest() != hashlib.md5(after).hexdigest()

    def _extract_explicit_url_or_domain(self, instruction: str) -> str:
        match = re.search(
            r"\b(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?",
            instruction,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        value = str(match.group(0) or "").strip().rstrip(".,;:!?")
        if value and not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value

    def _extract_generic_search_query(self, instruction: str) -> str:
        patterns = [
            r"search(?:\s+up|\s+for)?\s+(?P<query>.+)$",
            r"look(?:\s+up)?\s+(?P<query>.+)$",
            r"find\s+(?P<query>.+?)\s+online\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, instruction, flags=re.IGNORECASE)
            if not match:
                continue
            query = str(match.group("query") or "").strip(" .,:;!?\"'")
            query = re.split(
                r"\b(?:and then|and play|then play|and open|then open|and click|then click)\b",
                query,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if query:
                return query
        return ""

    def _build_completion_checklist(
        self,
        instruction: str,
        target_app: Optional[str] = None,
    ) -> list[str]:
        lower = instruction.lower()
        items: list[str] = []

        if target_app == "settings":
            items.append("Windows Settings is visibly open and active")
        elif target_app == "file_explorer":
            items.append("File Explorer is visibly open and active")
        elif target_app == "registry":
            items.append("Registry Editor is visibly open and active")
        elif target_app == "terminal":
            items.append("The terminal window is visibly open and active")
        elif target_app:
            items.append(f"The active app visibly matches {target_app}")

        explicit_url = self._extract_explicit_url_or_domain(instruction)
        if explicit_url:
            items.append(f"The browser has navigated to {explicit_url}")

        youtube_query = self._extract_site_search_query(instruction, ("youtube", "youtube.com"))
        if youtube_query:
            items.append(f"YouTube search results for '{youtube_query}' are visible")

        google_query = self._extract_site_search_query(instruction, ("google", "google.com"))
        if google_query:
            items.append(f"Google search results for '{google_query}' are visible")

        if not youtube_query and not google_query and any(token in lower for token in ("search", "look up", "find online")):
            generic_query = self._extract_generic_search_query(instruction)
            if generic_query:
                items.append(f"The requested search for '{generic_query}' is visibly executed")
            else:
                items.append("The requested search is visibly executed")

        if any(token in lower for token in ("first video", "play the first", "play first", "first result", "open the first", "click the first")):
            items.append("The requested first result is visibly open")
        elif any(token in lower for token in ("play", "open result", "open the result")):
            items.append("The requested result or content is visibly open")

        if any(token in lower for token in ("video", "song", "music", "playlist")):
            items.append("The requested media page or playback state is visible")

        if any(token in lower for token in ("theme", "light mode", "dark mode", "accent color", "wallpaper")):
            items.append("The requested appearance change is visibly applied")

        if target_app == "file_explorer" or any(token in lower for token in ("downloads", "documents", "desktop", "folder", "file")):
            items.append("The requested file or folder state is visible")

        if not items:
            items.append("The visible screen matches the user's requested final outcome")

        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _build_task_guidance(
        self,
        instruction: str,
        target_app: Optional[str],
        completion_checklist: list[str],
        nav_context: str,
    ) -> str:
        sections: list[str] = []

        if target_app == "settings":
            sections.append("Target surface: Windows Settings. Do not use a browser for this task.")
        elif target_app == "file_explorer":
            sections.append("Target surface: File Explorer. Do not use a browser for this task.")
        elif target_app == "registry":
            sections.append("Target surface: Registry Editor. Do not use a browser for this task.")
        elif target_app == "terminal":
            sections.append("Target surface: Terminal. Stay in the terminal unless the task explicitly requires switching.")
        elif target_app:
            sections.append(f"Target surface: {target_app}. Verify the active window title matches this app before interacting.")

        explicit_url = self._extract_explicit_url_or_domain(instruction)
        if explicit_url:
            sections.append(
                f"Direct navigation target: {explicit_url}. Use the address bar instead of a search engine when possible."
            )

        if completion_checklist:
            sections.append(
                "Completion checklist (every item must be visibly true before done):\n- "
                + "\n- ".join(completion_checklist)
            )

        nav_context = str(nav_context or "").strip()
        if nav_context:
            sections.append(nav_context)

        return "\n\n".join(section for section in sections if section)

    def _minimum_verified_actions(self, instruction: str, completion_checklist: list[str]) -> int:
        lower = instruction.lower()
        minimum = 1

        if len(completion_checklist) >= 4:
            minimum = 3
        elif len(completion_checklist) >= 2:
            minimum = 2

        if any(token in lower for token in ("search", "look up", "find online")):
            minimum = max(minimum, 2)

        if any(token in lower for token in ("first video", "play the first", "play first", "first result", "open the first", "click the first")):
            minimum = max(minimum, 3)

        if any(token in lower for token in ("theme", "light mode", "dark mode", "wallpaper")):
            minimum = max(minimum, 2)

        return minimum

    def _instruction_requires_interaction(self, instruction: str) -> bool:
        text = instruction.lower()
        return any(token in text for token in (
            "search",
            "open",
            "navigate",
            "go to",
            "click",
            "type",
            "press",
            "play",
        ))

    def _extract_site_search_query(self, instruction: str, site_tokens: Tuple[str, ...]) -> str:
        text = instruction.strip()
        lower = text.lower()
        if not any(token in lower for token in site_tokens):
            return ""

        patterns = [
            rf"search(?:\s+up|\s+for)?\s+(?P<query>.+?)\s+on\s+(?:{'|'.join(re.escape(token) for token in site_tokens)})\b",
            rf"search(?:ing)?\s+(?P<query>.+?)\s+on\s+(?:{'|'.join(re.escape(token) for token in site_tokens)})\b",
            rf"(?:on|in)\s+(?:{'|'.join(re.escape(token) for token in site_tokens)})\b.+?search(?:\s+for)?\s+(?P<query>.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            query = str(match.group("query") or "").strip(" .,:;!?\"'")
            query = re.split(r"\b(?:and then|and play|then play|then open|and open)\b", query, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if query:
                return query
        return ""

    def _optimize_instruction(self, instruction: str) -> str:
        websites = self.ui_knowledge.get("websites") or {}
        lowered = instruction.lower()

        youtube_query = self._extract_site_search_query(instruction, ("youtube", "youtube.com"))
        youtube_meta = websites.get("youtube.com") or {}
        youtube_template = str(youtube_meta.get("search_url") or "").strip()
        if youtube_query and youtube_template:
            target_url = youtube_template.format(query=quote_plus(youtube_query))
            return (
                f"Open the browser and navigate directly to {target_url}. "
                f"After the results page loads, continue the rest of the task: {instruction}"
            )

        google_query = self._extract_site_search_query(instruction, ("google", "google.com"))
        google_meta = websites.get("google.com") or {}
        google_template = str(google_meta.get("search_url") or "").strip()
        if google_query and google_template:
            target_url = google_template.format(query=quote_plus(google_query))
            return (
                f"Open the browser and navigate directly to {target_url}. "
                f"After the results page loads, continue the rest of the task: {instruction}"
            )

        domain_match = re.search(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?:/[^\s]*)?", lowered, flags=re.IGNORECASE)
        if domain_match:
            domain = str(domain_match.group(0) or "").strip()
            if domain and not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"
            return f"Open the browser and enter this exact URL in the address bar first: {domain}. Then continue the task: {instruction}"

        return instruction

    def _capture_observation(self) -> Dict[str, bytes]:
        screenshot = pyautogui.screenshot()
        if screenshot.size != (self.screen_width, self.screen_height):
            screenshot = screenshot.resize((self.screen_width, self.screen_height))
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        return {"screenshot": buffered.getvalue()}

    async def execute_task(
        self,
        instruction: str,
        speak_fn=None,
        set_wave_state_fn=None,
        append_chat_fn=None,
        stop_event=None,
        max_steps: int = 0,
        target_app: Optional[str] = None,
        guidance_block: str = "",
        completion_checklist: Optional[list[str]] = None,
        starting_verified_actions: int = 0,
    ) -> Dict[str, Any]:
        speak_fn = speak_fn or (lambda *_args, **_kwargs: None)
        set_wave_state_fn = set_wave_state_fn or (lambda *_args, **_kwargs: None)
        append_chat_fn = append_chat_fn or (lambda *_args, **_kwargs: None)
        if max_steps <= 0:
            max_steps = int(_cfg("AGENT_MAX_STEPS", "15"))

        async def _speak(text: str):
            result = speak_fn(text)
            if asyncio.iscoroutine(result):
                await result

        completion_checklist = completion_checklist or self._build_completion_checklist(
            instruction,
            target_app=target_app,
        )
        guidance_block = str(guidance_block or "").strip()
        if not guidance_block and completion_checklist:
            guidance_block = self._build_task_guidance(
                instruction,
                target_app,
                completion_checklist,
                "",
            )
        optimized_instruction = self._optimize_instruction(instruction)
        base_instruction = optimized_instruction
        if guidance_block:
            base_instruction = f"{base_instruction}\n\n{guidance_block}"
        minimum_verified_actions = self._minimum_verified_actions(
            instruction,
            completion_checklist,
        )
        self.reset()
        append_chat_fn("assistant", f"[Agent S3] Starting task: {instruction}")
        if optimized_instruction != instruction:
            append_chat_fn("assistant", f"[Agent S3] Optimized navigation: {optimized_instruction[:300]}")
            logger.info("[Agent S3] Optimized instruction: %s", optimized_instruction)
        logger.info(f"[Agent S3] Task start: {instruction}")

        last_info: Dict[str, Any] = {}
        last_action = ""
        verified_actions = max(0, int(starting_verified_actions or 0))
        unchanged_steps = 0
        verification_note = ""

        for step in range(1, max_steps + 1):
            if stop_event and stop_event.is_set():
                return {
                    "status": "failed",
                    "message": "Stopped by user",
                    "step": step,
                    "info": last_info,
                    "action": last_action,
                }

            set_wave_state_fn("thinking")
            obs = self._capture_observation()
            instruction_for_step = base_instruction
            if verification_note:
                instruction_for_step = f"{instruction_for_step}\n\n{verification_note}"
            info, actions = self.agent.predict(instruction=instruction_for_step, observation=obs)
            last_info = info or {}
            last_action = actions[0] if actions else ""
            plan_text = str((info or {}).get("plan") or "").strip()

            if plan_text:
                append_chat_fn("assistant", f"[Agent S3] Step {step}: {plan_text[:300]}")
            logger.info(f"[Agent S3] Step {step} plan: {plan_text}")
            logger.info(f"[Agent S3] Step {step} action: {last_action}")

            normalized_action = last_action.strip().lower()
            if not last_action:
                return {
                    "status": "failed",
                    "message": "Agent S3 returned no action",
                    "step": step,
                    "info": last_info,
                    "action": last_action,
                }

            if "done" in normalized_action:
                if self._instruction_requires_interaction(instruction) and verified_actions < minimum_verified_actions:
                    checklist_text = ""
                    if completion_checklist:
                        checklist_text = "\n".join(f"- {item}" for item in completion_checklist[:6])
                    verification_note = (
                        f"Do not return done yet. Verified progress is too low for this task "
                        f"({verified_actions}/{minimum_verified_actions}). "
                        "The completion checklist must be visibly true before done."
                    )
                    if checklist_text:
                        verification_note = f"{verification_note}\n{checklist_text}"
                    append_chat_fn("assistant", "[Agent S3] Completion rejected: verification requirements not met yet")
                    logger.warning(
                        "[Agent S3] Rejected completion with %s verified changes; need %s",
                        verified_actions,
                        minimum_verified_actions,
                    )
                    await asyncio.sleep(0.2)
                    continue
                message = str((info or {}).get("plan") or "Task completed")
                append_chat_fn("assistant", f"[Agent S3] Complete: {message}")
                return {
                    "status": "done",
                    "message": message,
                    "step": step,
                    "info": last_info,
                    "action": last_action,
                }

            if "fail" in normalized_action:
                message = str((info or {}).get("plan") or last_action)
                append_chat_fn("assistant", f"[Agent S3] Failed: {message}")
                return {
                    "status": "failed",
                    "message": message,
                    "step": step,
                    "info": last_info,
                    "action": last_action,
                }

            if "next" in normalized_action:
                await asyncio.sleep(0.4)
                continue

            if "wait" in normalized_action:
                await asyncio.sleep(1.5)
                continue

            set_wave_state_fn("agent")
            try:
                before_screenshot = obs["screenshot"]
                exec(last_action, {"__builtins__": __builtins__}, {})
            except Exception as e:
                logger.error(f"[Agent S3] Execution failed: {e}", exc_info=True)
                append_chat_fn("assistant", f"[Agent S3] Execution failed: {e}")
                return {
                    "status": "failed",
                    "message": f"Execution failed: {e}",
                    "step": step,
                    "info": last_info,
                    "action": last_action,
                }

            append_chat_fn("assistant", f"[Agent S3] Executed step {step}")
            await asyncio.sleep(0.8)

            after_obs = self._capture_observation()
            if self._screenshots_different(before_screenshot, after_obs["screenshot"]):
                verified_actions += 1
                unchanged_steps = 0
                verification_note = ""
                append_chat_fn("assistant", f"[Agent S3] Verified visible change after step {step}")
                logger.info("[Agent S3] Step %s verified by screenshot change", step)
            else:
                unchanged_steps += 1
                verification_note = (
                    "The previous action did not create a visible screen change. "
                    "Do not assume it worked. Re-check whether text appeared, results loaded, or focus changed before proceeding."
                )
                append_chat_fn("assistant", f"[Agent S3] Warning: no visible change detected after step {step}")
                logger.warning("[Agent S3] No visible change detected after step %s", step)
                if unchanged_steps >= self.verification_stall_limit:
                    message = "Agent S3 could not verify progress on screen"
                    return {
                        "status": "failed",
                        "message": message,
                        "step": step,
                        "info": last_info,
                        "action": last_action,
                    }

        message = f"Reached max steps ({max_steps}) without completing"
        await _speak(message)
        return {
            "status": "failed",
            "message": message,
            "step": max_steps,
            "info": last_info,
            "action": last_action,
        }

    async def execute_task_with_app_awareness(
        self,
        instruction: str,
        speak_fn=None,
        set_wave_state_fn=None,
        append_chat_fn=None,
        stop_event=None,
        max_steps: int = 0,
    ) -> Dict[str, Any]:
        """Thin wrapper — delegates to execute_task_spec_aware."""
        return await self.execute_task_spec_aware(
            instruction=instruction,
            speak_fn=speak_fn,
            set_wave_state_fn=set_wave_state_fn,
            append_chat_fn=append_chat_fn,
            stop_event=stop_event,
            max_steps=max_steps,
        )

    async def execute_task_spec_aware(
        self,
        instruction: str,
        speak_fn=None,
        set_wave_state_fn=None,
        append_chat_fn=None,
        stop_event=None,
        max_steps: int = 0,
    ) -> Dict[str, Any]:
        """
        Spec-driven task execution:
          1. detect_app_from_request() — matches instruction to correct app using
             keywords from browser_navigation_spec.md + agent_navigation.md.
             NEVER opens Arc unless explicitly requested.
          2. open_app() — opens/switches to the correct app via window_manager.
          3. Injects app navigation spec into the agent system prompt.
          4. Runs the standard agent loop with app context.
        """
        from core.app_detector import (
            detect_app_from_request,
            build_nav_context_for_prompt,
            get_app_info,
            get_window_title_hints,
            is_browser,
        )
        from core.navigation_brain import get_navigation_brain
        from core.window_manager import get_window_manager

        speak_fn = speak_fn or (lambda *_a, **_k: None)
        append_chat_fn = append_chat_fn or (lambda *_a, **_k: None)

        wm = get_window_manager()
        current_title = wm.get_foreground_app_title()
        logger.info(f"[Agent S3] Foreground before task: '{current_title}'")
        append_chat_fn("assistant", f"[Agent S3] Current window: {current_title}")
        starting_verified_actions = 0

        target_app = detect_app_from_request(instruction)
        logger.info(f"[Agent S3] Detected target app: {target_app!r}")

        nav_context = ""
        if target_app:
            app_info = get_app_info(target_app)
            app_type = "browser" if is_browser(target_app) else "system app"
            append_chat_fn(
                "assistant",
                f"[Agent S3] Spec match → {target_app} ({app_type}) | "
                f"process: {(app_info or {}).get('process', '?')}"
            )

            logger.info(f"[Agent S3] Opening '{target_app}' before agent loop...")
            success = wm.open_app(target_app)
            if not success:
                msg = f"Could not open '{target_app}' — check app_config.json path"
                logger.error(f"[Agent S3] {msg}")
                append_chat_fn("assistant", f"[Agent S3] ✗ {msg}")
                return {"status": "failed", "message": msg}

            new_title = wm.get_foreground_app_title()
            logger.info(f"[Agent S3] Active window after switch: '{new_title}'")
            append_chat_fn("assistant", f"[Agent S3] ✓ Active: {new_title}")
            title_hints = [hint.lower() for hint in get_window_title_hints(target_app)]
            if any(hint and hint in new_title.lower() for hint in title_hints):
                starting_verified_actions = 1
                append_chat_fn("assistant", f"[Agent S3] Verified target app window: {new_title}")
            else:
                append_chat_fn("assistant", f"[Agent S3] Window title needs extra verification for: {target_app}")

            nav_context = build_nav_context_for_prompt(target_app, instruction)
            if nav_context:
                logger.info(f"[Agent S3] Nav context injected for '{target_app}'")
                append_chat_fn("assistant", f"[Agent S3] Using spec navigation for: {target_app}")

        brain_context = get_navigation_brain(instruction)
        combined_nav_context = "\n\n".join(
            section for section in (nav_context, brain_context) if str(section or "").strip()
        )
        completion_checklist = self._build_completion_checklist(
            instruction,
            target_app=target_app,
        )
        guidance_block = self._build_task_guidance(
            instruction,
            target_app,
            completion_checklist,
            combined_nav_context,
        )

        saved_prompt = None
        if combined_nav_context:
            try:
                executor = getattr(self.agent, "executor", None)
                if executor:
                    gen_agent = getattr(executor, "generator_agent", None)
                    if gen_agent and hasattr(gen_agent, "system_prompt"):
                        saved_prompt = str(gen_agent.system_prompt or "")
                        patched = f"{saved_prompt}\n\n{combined_nav_context}"
                        gen_agent.add_system_prompt(patched)
            except Exception as _e:
                logger.debug(f"[Agent S3] Could not patch system prompt: {_e}")

        try:
            result = await self.execute_task(
                instruction=instruction,
                speak_fn=speak_fn,
                set_wave_state_fn=set_wave_state_fn,
                append_chat_fn=append_chat_fn,
                stop_event=stop_event,
                max_steps=max_steps,
                target_app=target_app,
                guidance_block=guidance_block,
                completion_checklist=completion_checklist,
                starting_verified_actions=starting_verified_actions,
            )
        finally:
            if saved_prompt is not None:
                try:
                    executor = getattr(self.agent, "executor", None)
                    if executor:
                        gen_agent = getattr(executor, "generator_agent", None)
                        if gen_agent and hasattr(gen_agent, "system_prompt"):
                            gen_agent.add_system_prompt(saved_prompt)
                except Exception:
                    pass

        return result


async def run_agent_s3_task(
    task: str,
    speak_fn=None,
    set_wave_state_fn=None,
    append_chat_fn=None,
    stop_event=None,
    max_steps: int = 0,
) -> str:
    result = await get_agent_s3().execute_task_with_app_awareness(
        instruction=task,
        speak_fn=speak_fn,
        set_wave_state_fn=set_wave_state_fn,
        append_chat_fn=append_chat_fn,
        stop_event=stop_event,
        max_steps=max_steps,
    )
    if result.get("status") == "done":
        return str(result.get("message") or "Task completed")
    return f"Agent failed: {result.get('message') or result.get('action') or 'Unknown error'}"


def get_agent_s3() -> WhiztantAgentS3:
    global _agent_s3_instance
    if _agent_s3_instance is None:
        _agent_s3_instance = WhiztantAgentS3()
    return _agent_s3_instance
