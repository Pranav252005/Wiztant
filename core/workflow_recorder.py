"""
Whiztant core/workflow_recorder.py — Semantic Workflow Recorder

Records user actions, abstracts them into semantic intent steps via Qwen3-VL,
and stores them as replayable skills in data/skills/.

Three phases:
  Phase 1 — Observe: Capture screenshots at ~2fps + log keyboard/mouse events
  Phase 2 — Abstract: Send screen diffs to Qwen3-VL to classify intent
  Phase 3 — Replay: Re-ground each step to current screen and execute
"""

import os
import json
import time
import base64
import ctypes
import threading
import asyncio
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime

import numpy as np
from PIL import Image, ImageChops, ImageGrab
from openai import OpenAI

import core as state


# ── Config ────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "data" / "skills"

def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Intent step schema ────────────────────────────────────────────────────────

@dataclass
class IntentStep:
    step: int
    intent: str
    app: str
    action_type: str          # click, type_and_execute, navigate, keypress, scroll
    semantic_target: str      # what to look for on screen
    literal_input: str        # exact text typed / key pressed
    precondition: str         # what must be true before this step
    success_signal: str       # how to verify it worked
    timestamp: float = 0.0


# ── ScreenDiffEngine ──────────────────────────────────────────────────────────

class ScreenDiffEngine:
    """
    Captures screenshots at ~2fps and detects significant screen changes
    by comparing consecutive frames. Only emits events when the screen
    actually changed (new window, dialog, text appeared, etc.).
    """

    def __init__(self, fps: float = 2.0, diff_threshold: float = 0.03):
        self._interval = 1.0 / fps
        self._threshold = diff_threshold  # % of pixels that must differ
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_frame: Optional[Image.Image] = None
        self._on_change_callback = None
        self._frames: List[Tuple[float, str]] = []  # (timestamp, b64)

    def start(self, on_change=None):
        """Start capturing. on_change(before_b64, after_b64, timestamp) called on diffs."""
        self._on_change_callback = on_change
        self._stop_event.clear()
        self._running = True
        self._frames = []
        self._last_frame = None
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[Tuple[float, str]]:
        """Stop capturing. Returns all captured frames."""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        return self._frames

    def _capture_loop(self):
        import mss as _mss

        # Windows-only DPI awareness — silently skip on other platforms
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, ImportError):
            pass

        while not self._stop_event.is_set():
            try:
                with _mss.mss() as sct:
                    raw = sct.grab(sct.monitors[1])
                    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            except Exception:
                try:
                    img = ImageGrab.grab(all_screens=False)
                except Exception:
                    time.sleep(self._interval)
                    continue

            # Resize for efficiency
            max_w = 1280
            if img.width > max_w:
                scale = max_w / float(img.width)
                img = img.resize((max_w, int(img.height * scale)), Image.LANCZOS)

            ts = time.time()

            # Convert to b64
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode()
            self._frames.append((ts, b64))

            # Check for significant diff
            if self._last_frame is not None and self._on_change_callback:
                diff_pct = self._compute_diff(self._last_frame, img)
                if diff_pct > self._threshold:
                    # Convert last frame to b64 for callback
                    buf2 = BytesIO()
                    self._last_frame.save(buf2, format="JPEG", quality=80)
                    before_b64 = base64.b64encode(buf2.getvalue()).decode()
                    try:
                        self._on_change_callback(before_b64, b64, ts)
                    except Exception as e:
                        print(f"[Recorder] Change callback error: {e}")

            self._last_frame = img.copy()
            time.sleep(self._interval)

    @staticmethod
    def _compute_diff(img_a: Image.Image, img_b: Image.Image) -> float:
        """Compute fraction of pixels that differ between two images."""
        try:
            # Ensure same size
            if img_a.size != img_b.size:
                img_b = img_b.resize(img_a.size, Image.LANCZOS)

            arr_a = np.array(img_a, dtype=np.int16)
            arr_b = np.array(img_b, dtype=np.int16)
            diff = np.abs(arr_a - arr_b)
            # Pixel is "changed" if any channel differs by > 30
            changed = np.any(diff > 30, axis=2)
            return float(changed.sum()) / float(changed.size)
        except Exception:
            return 0.0


# ── InputLogger ───────────────────────────────────────────────────────────────

class InputLogger:
    """Logs keyboard and mouse events during recording."""

    def __init__(self):
        self._events: List[Dict] = []
        self._running = False
        self._kb_hook = None
        self._mouse_hook = None

    def start(self):
        self._events = []
        self._running = True
        import keyboard as kb
        import mouse

        self._kb_hook = kb.on_press(self._on_key)
        self._mouse_hook = mouse.on_click(self._on_click)

    def stop(self) -> List[Dict]:
        self._running = False
        import keyboard as kb
        import mouse

        if self._kb_hook is not None:
            kb.unhook(self._kb_hook)
            self._kb_hook = None
        if self._mouse_hook is not None:
            mouse.unhook(self._mouse_hook)
            self._mouse_hook = None
        return self._events

    def _on_key(self, event):
        if not self._running:
            return
        self._events.append({
            "type": "keypress",
            "key": event.name,
            "time": time.time(),
        })

    def _on_click(self):
        if not self._running:
            return
        import pyautogui
        x, y = pyautogui.position()
        self._events.append({
            "type": "click",
            "x": x,
            "y": y,
            "time": time.time(),
        })


# ── IntentAbstractor ──────────────────────────────────────────────────────────

ABSTRACTOR_PROMPT = (
    "You are analysing a user's actions on a Windows desktop. "
    "Given a before/after screenshot pair and a list of input events, "
    "describe the user's intent in structured JSON.\n\n"
    "Return ONLY valid JSON:\n"
    "{\n"
    '  "intent": "short_snake_case_name",\n'
    '  "app": "Application name visible on screen",\n'
    '  "action_type": "click | type_and_execute | navigate | keypress | scroll",\n'
    '  "semantic_target": "What to look for on screen to repeat this action",\n'
    '  "literal_input": "Exact text typed or key pressed (empty if just a click)",\n'
    '  "precondition": "What must be true before this step",\n'
    '  "success_signal": "How to verify the action succeeded"\n'
    "}\n\n"
    "Rules:\n"
    "- semantic_target must describe a visual element, not coordinates.\n"
    "- success_signal must describe a visual change, not an assumption.\n"
    "- Be specific but environment-independent (no hardcoded paths or coordinates).\n"
    "- Return ONLY the JSON object."
)


class IntentAbstractor:
    """Sends before/after screenshots + events to Qwen3-VL for intent classification."""

    def __init__(self):
        self._client = OpenAI(
            api_key=_cfg("OPENROUTER_API_KEY"),
            base_url=_cfg("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )

    def classify(
        self,
        before_b64: str,
        after_b64: str,
        events: List[Dict],
    ) -> Optional[Dict]:
        """Classify a screen change into a semantic intent step."""
        model = _cfg("PLANNER_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")

        events_text = ""
        if events:
            event_strs = []
            for e in events[:20]:  # Limit to 20 events
                if e["type"] == "keypress":
                    event_strs.append(f"Key: {e['key']}")
                elif e["type"] == "click":
                    event_strs.append(f"Click at ({e['x']}, {e['y']})")
            events_text = "Input events between screenshots:\n" + "\n".join(event_strs)

        messages = [
            {"role": "system", "content": ABSTRACTOR_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Before screenshot:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{before_b64}"}},
                    {"type": "text", "text": "After screenshot:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{after_b64}"}},
                    {"type": "text", "text": events_text or "No input events captured."},
                ],
            },
        ]

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()

            if "<think>" in raw:
                raw = raw[raw.rfind("</think>") + len("</think>"):].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()

            return json.loads(raw)
        except Exception as e:
            print(f"[Recorder] Intent classification failed: {e}")
            return None


# ── SkillStore ────────────────────────────────────────────────────────────────

class SkillStore:
    """Manages saved skills in data/skills/."""

    def __init__(self):
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, description: str, steps: List[Dict]) -> Path:
        """Save a recorded workflow as a skill."""
        skill = {
            "name": name,
            "description": description,
            "created": datetime.now().isoformat(),
            "steps": steps,
        }
        path = _SKILLS_DIR / f"{name}.json"
        path.write_text(json.dumps(skill, indent=2), encoding="utf-8")
        print(f"[SkillStore] Saved skill: {path}")
        return path

    def load(self, name: str) -> Optional[Dict]:
        """Load a skill by name."""
        path = _SKILLS_DIR / f"{name}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[SkillStore] Load error: {e}")
            return None

    def list_all(self) -> List[Dict]:
        """List all available skills."""
        skills = []
        for path in _SKILLS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                skills.append({
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "steps": len(data.get("steps", [])),
                    "created": data.get("created", ""),
                })
            except Exception:
                continue
        return skills

    def delete(self, name: str) -> bool:
        """Delete a skill."""
        path = _SKILLS_DIR / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False


# ── WorkflowRecorder (orchestrator) ──────────────────────────────────────────

class WorkflowRecorder:
    """
    Main recording orchestrator.
    Usage:
        recorder = WorkflowRecorder()
        recorder.start_recording()
        # ... user performs actions ...
        skill = recorder.stop_recording("deploy_vercel", "Deploy project to Vercel")
    """

    def __init__(self):
        self._diff_engine = ScreenDiffEngine(fps=2.0, diff_threshold=0.03)
        self._input_logger = InputLogger()
        self._abstractor = IntentAbstractor()
        self._store = SkillStore()
        self._recording = False
        self._change_buffer: List[Dict] = []  # Pending screen changes
        self._classified_steps: List[Dict] = []
        self._step_counter = 0

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self):
        """Enter recording mode. Starts capturing screenshots + input."""
        if self._recording:
            return
        self._recording = True
        self._change_buffer = []
        self._classified_steps = []
        self._step_counter = 0

        self._diff_engine.start(on_change=self._on_screen_change)
        self._input_logger.start()
        print("[Recorder] Recording started")

    def stop_recording(self, skill_name: str = "", description: str = "") -> Optional[Dict]:
        """
        Stop recording, classify buffered changes, and save as skill.
        Returns the skill dict or None if no steps were captured.
        """
        if not self._recording:
            return None
        self._recording = False

        frames = self._diff_engine.stop()
        events = self._input_logger.stop()
        print(f"[Recorder] Recording stopped. {len(frames)} frames, "
              f"{len(events)} events, {len(self._change_buffer)} changes")

        # Classify any remaining buffered changes
        self._classify_pending_changes(events)

        if not self._classified_steps:
            print("[Recorder] No steps captured")
            return None

        # Generate name if not provided
        if not skill_name:
            skill_name = f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not description:
            description = f"Recorded {len(self._classified_steps)} steps"

        # Save
        path = self._store.save(skill_name, description, self._classified_steps)

        skill_data = {
            "name": skill_name,
            "description": description,
            "steps": self._classified_steps,
            "path": str(path),
        }
        print(f"[Recorder] Skill saved: {skill_name} ({len(self._classified_steps)} steps)")
        return skill_data

    def _on_screen_change(self, before_b64: str, after_b64: str, timestamp: float):
        """Called by ScreenDiffEngine when a significant change is detected."""
        self._change_buffer.append({
            "before_b64": before_b64,
            "after_b64": after_b64,
            "timestamp": timestamp,
        })

        # Classify in batches to avoid spamming the VLM
        if len(self._change_buffer) >= 3:
            events = self._input_logger._events  # Peek at current events
            self._classify_pending_changes(events)

    def _classify_pending_changes(self, all_events: List[Dict]):
        """Classify all buffered screen changes into intent steps."""
        if not self._change_buffer:
            return

        for change in self._change_buffer:
            ts = change["timestamp"]

            # Find events near this change (within 2 seconds before)
            relevant_events = [
                e for e in all_events
                if ts - 2.0 <= e.get("time", 0) <= ts + 0.5
            ]

            result = self._abstractor.classify(
                change["before_b64"],
                change["after_b64"],
                relevant_events,
            )

            if result:
                self._step_counter += 1
                result["step"] = self._step_counter
                result["timestamp"] = ts
                self._classified_steps.append(result)
                print(f"[Recorder] Step {self._step_counter}: "
                      f"{result.get('intent', '?')} in {result.get('app', '?')}")

        self._change_buffer.clear()


# ── Replay ────────────────────────────────────────────────────────────────────

async def replay_skill(
    skill_data: Dict,
    speak_fn,
    transcribe_fn,
    set_wave_state_fn,
    append_chat_fn,
    stop_event: Optional[threading.Event] = None,
) -> str:
    """
    Replay a recorded skill by re-grounding each step to the current screen.
    Uses Qwen3-VL to find semantic targets and UI-TARS to execute actions.
    """
    from platforms.windows._vlm_impl import _take_screenshot, _execute_single_step

    steps = skill_data.get("steps", [])
    if not steps:
        return "FAILED: Skill has no steps"

    name = skill_data.get("name", "skill")
    total = len(steps)

    def _speak_sync(text: str):
        result = speak_fn(text)
        if asyncio.iscoroutine(result):
            asyncio.run(result)

    def _transcribe_sync() -> str:
        result = transcribe_fn()
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result or ""

    append_chat_fn("assistant", f"[Skill] Replaying '{name}' — {total} steps")

    for i, step in enumerate(steps):
        if stop_event and stop_event.is_set():
            return f"Stopped at step {i+1}/{total}"

        intent = step.get("intent", "unknown")
        target = step.get("semantic_target", step.get("action", ""))
        literal = step.get("literal_input", "")
        precondition = step.get("precondition", "")

        # Build a task description for the executor
        task = target
        if literal:
            task = f"{target} — type: {literal}"

        set_wave_state_fn("agent")
        append_chat_fn("assistant", f"[Skill] Step {i+1}/{total}: {intent}")

        screenshot_b64, _, physical_size = _take_screenshot()

        try:
            result = await _execute_single_step(
                task,
                screenshot_b64,
                physical_size,
                _speak_sync,
                _transcribe_sync,
                max_actions=5,
            )

            if result.get("success"):
                append_chat_fn("assistant", f"[Skill] ✓ Step {i+1} done")
            else:
                error = result.get("error", "Unknown")
                append_chat_fn("assistant", f"[Skill] ✗ Step {i+1} failed: {error}")
                # Continue anyway — don't abort entire skill

        except Exception as e:
            append_chat_fn("assistant", f"[Skill] ✗ Step {i+1} error: {e}")

        time.sleep(0.5)

    return f"OK: Replayed {name} ({total} steps)"


# ── Module-level singleton ────────────────────────────────────────────────────

_recorder: Optional[WorkflowRecorder] = None


def get_recorder() -> WorkflowRecorder:
    """Get or create the global WorkflowRecorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = WorkflowRecorder()
    return _recorder
