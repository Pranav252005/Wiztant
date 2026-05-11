"""
Whiztant core/background_agent.py — Background Agent Manager.

Orchestrates non-blocking background task execution:
  - User voices a task → queued instantly, control returns immediately
  - Task launches in a hidden/minimized browser window
  - Agent executes via VLM in isolated window context (no focus theft)
  - Result delivered via clipboard + toast notification

Architecture:
  BackgroundAgentManager
    ├─ Task queue (asyncio.Queue, FIFO)
    ├─ Process monitor (up to 3 parallel tasks)
    ├─ Input isolation (via core.agent_isolation)
    └─ Result delivery (clipboard + toast + optional overlay)
"""

import os
import json
import sys
import time
import asyncio
import base64
import subprocess
import threading
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

from core.agent_task_queue import (
    AgentTask,
    generate_task_id,
    save_task_to_log,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _cfg(key: str, default: str = "") -> str:
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


# ── Task type detection ─────────────────────────────────────────────────────

def detect_task_type(description: str) -> str:
    """
    Auto-detect task type from the user's voice description.
    Returns one of: "registry", "settings", "nvidia", "game", "system", "browser"
    """
    d = description.lower()

    # Registry tasks
    if any(w in d for w in ["registry", "regedit", "reg add", "hklm", "hkcu", "dword"]):
        return "registry"

    # NVIDIA / GPU tasks
    if any(w in d for w in ["nvidia", "dlss", "ray tracing", "gpu settings", "geforce"]):
        return "nvidia"

    # Game optimization (check before generic "settings" to avoid false match)
    if any(w in d for w in ["optimize game", "game optimization", "fps", "graphics settings"]):
        if any(w in d for w in ["game", "fps", "gaming", "optimize"]):
            return "game"

    # Windows Settings
    if any(w in d for w in [
        "settings", "gpu acceleration", "game mode", "game bar",
        "startup apps", "startup programs", "power plan", "refresh rate",
        "night light", "notifications", "bluetooth", "wifi",
    ]):
        return "settings"

    # System apps (Control Panel, Device Manager, etc.)
    if any(w in d for w in [
        "control panel", "device manager", "disk cleanup", "task manager",
        "uninstall", "driver", "temp files", "clear cache", "free space",
        "sound settings", "audio settings", "speaker", "microphone",
    ]):
        return "system"

    # Default: browser-based task
    return "browser"


# ── Browser detection ────────────────────────────────────────────────────────

_BROWSER_SEARCH_PATHS = [
    # Arc
    (r"Software\Microsoft\Windows\CurrentVersion\App Paths\arc.exe", None),
    # Chrome
    (r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe", None),
    # Edge
    (r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe", None),
    # Brave
    (r"Software\Microsoft\Windows\CurrentVersion\App Paths\brave.exe", None),
    # Firefox (no isolated profile flag, but still works)
    (r"Software\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe", None),
]


def _find_browser_path() -> str:
    """Find the first available browser executable on the system."""
    for reg_path, _ in _BROWSER_SEARCH_PATHS:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            path, _ = winreg.QueryValueEx(key, None)
            winreg.CloseKey(key)
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
            path, _ = winreg.QueryValueEx(key, None)
            winreg.CloseKey(key)
            if path and os.path.exists(path):
                return path
        except Exception:
            pass

    # Hardcoded fallbacks
    fallbacks = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for fb in fallbacks:
        if os.path.exists(fb):
            return fb

    return "chrome"  # Last resort — rely on PATH


# ── Window-specific screenshot ───────────────────────────────────────────────

def _capture_window_screenshot(hwnd: int) -> Optional[str]:
    """
    Capture a screenshot of a specific window by its handle.
    Returns base64-encoded JPEG string, or None on failure.

    Uses mss to grab the window region without activating it.
    """
    try:
        from core.agent_isolation import get_window_rect, is_window_valid
        if not is_window_valid(hwnd):
            return None

        rect = get_window_rect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if width < 50 or height < 50:
            return None

        import mss as _mss
        from PIL import Image

        with _mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        # Resize for token efficiency (max 1280px wide)
        max_w = 1280
        if img.width > max_w:
            scale = max_w / float(img.width)
            img = img.resize((max_w, int(img.height * scale)), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()

    except Exception as e:
        print(f"[bg_agent] Window screenshot error: {e}")
        return None


# ── VLM caller for background agent ─────────────────────────────────────────

_BG_AGENT_SYSTEM_PROMPT = (
    "You are a background UI automation agent for Windows. "
    "You are controlling a browser window that the user cannot see. "
    "You receive a screenshot of the browser window and a task to complete.\n\n"
    "Available actions (return ONLY valid JSON):\n"
    '{"action": "click", "x": <int>, "y": <int>}\n'
    '{"action": "type", "text": "text to type"}\n'
    '{"action": "key", "key": "enter"}\n'
    '{"action": "scroll", "x": <int>, "y": <int>, "direction": "down", "amount": 3}\n'
    '{"action": "complete", "result": "description of what was found or accomplished"}\n'
    '{"action": "error", "message": "reason the task cannot be completed"}\n'
    "\n"
    "Rules:\n"
    "- Return ONLY valid JSON. No markdown, no explanation.\n"
    "- Coordinates are relative to the browser window (not the full screen).\n"
    "- x=0,y=0 is the top-left corner of the browser window.\n"
    "- Be efficient: complete the task in as few steps as possible.\n"
    "- When the task is done, use the 'complete' action with a summary of the result.\n"
    "- If you cannot proceed, use the 'error' action.\n"
    "- Prefer keyboard shortcuts when faster: Ctrl+L for address bar, Ctrl+T for new tab, Enter to confirm."
)


async def _call_bg_vlm(
    screenshot_b64: str,
    task_description: str,
    step_number: int,
    history: List[Dict],
) -> Dict[str, Any]:
    """Call Qwen3-VL via OpenRouter for background agent decision-making."""
    from openai import OpenAI

    api_key = _cfg("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    model = _cfg("PLANNER_MODEL", "qwen/qwen3-vl-235b-a22b-instruct")

    messages: List[Dict] = [{"role": "system", "content": _BG_AGENT_SYSTEM_PROMPT}]

    # Add recent history (last 6 turns)
    for h in history[-6:]:
        messages.append({"role": "assistant", "content": json.dumps(h.get("action_json", {}))})
        messages.append({"role": "user", "content": f"Result: {h.get('result', 'ok')}"})

    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"Step {step_number}. Task: {task_description}\n\nWhat is the next action?",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
            },
        ],
    })

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=256,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def _normalized_to_client_coords(hwnd: int, x: Any, y: Any) -> Tuple[int, int]:
    from core.agent_isolation import get_window_rect
    import win32gui

    left, top, right, bottom = get_window_rect(hwnd)
    width = max(1, right - left)
    height = max(1, bottom - top)

    x_f = float(x)
    y_f = float(y)
    if 0.0 <= x_f <= 1.0 and 0.0 <= y_f <= 1.0:
        screen_x = left + int(x_f * width)
        screen_y = top + int(y_f * height)
    else:
        screen_x = left + int((x_f / 1000.0) * width)
        screen_y = top + int((y_f / 1000.0) * height)

    client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
    return max(0, client_x), max(0, client_y)


def _normalized_to_screen_coords(hwnd: int, x: Any, y: Any) -> Tuple[int, int]:
    from core.agent_isolation import get_window_rect

    left, top, right, bottom = get_window_rect(hwnd)
    width = max(1, right - left)
    height = max(1, bottom - top)

    x_f = float(x)
    y_f = float(y)
    if 0.0 <= x_f <= 1.0 and 0.0 <= y_f <= 1.0:
        screen_x = left + int(x_f * width)
        screen_y = top + int(y_f * height)
    else:
        screen_x = left + int((x_f / 1000.0) * width)
        screen_y = top + int((y_f / 1000.0) * height)

    return max(left, screen_x), max(top, screen_y)


def _activate_browser_window(hwnd: int):
    import win32con
    import win32gui

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _find_browser_window_for_process(browser_pid: int, browser_path: str) -> Optional[int]:
    from core.agent_isolation import find_windows_by_pid
    import psutil
    import win32gui

    browser_name = Path(browser_path).stem.lower()
    candidate_pids = {browser_pid}

    try:
        proc = psutil.Process(browser_pid)
        for child in proc.children(recursive=True):
            candidate_pids.add(child.pid)
    except Exception:
        pass

    try:
        now = time.time()
        for proc in psutil.process_iter(["pid", "name", "create_time"]):
            info = proc.info or {}
            name = str(info.get("name") or "").lower()
            created = float(info.get("create_time") or 0.0)
            if name == f"{browser_name}.exe" and created >= now - 20:
                candidate_pids.add(int(info["pid"]))
    except Exception:
        pass

    candidates: list[tuple[int, int]] = []
    for pid in candidate_pids:
        try:
            for hwnd in find_windows_by_pid(pid):
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    continue
                title = (win32gui.GetWindowText(hwnd) or "").strip()
                if not title:
                    continue
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                area = max(0, right - left) * max(0, bottom - top)
                if area <= 0:
                    continue
                candidates.append((area, hwnd))
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _find_visible_browser_windows(browser_path: str) -> list[int]:
    import psutil
    import win32gui
    import win32process

    browser_name = Path(browser_path).stem.lower()
    candidates: list[tuple[int, int, int]] = []
    foreground_hwnd = None

    try:
        foreground_hwnd = win32gui.GetForegroundWindow()
    except Exception:
        foreground_hwnd = None

    def _enum_callback(hwnd, _):
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title:
                return True
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            area = max(0, right - left) * max(0, bottom - top)
            if area <= 0:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name().lower()
            if proc_name != f"{browser_name}.exe":
                return True
            priority = 1 if hwnd == foreground_hwnd else 0
            candidates.append((priority, area, hwnd))
        except Exception:
            return True
        return True

    try:
        win32gui.EnumWindows(_enum_callback, None)
    except Exception:
        return []

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [hwnd for _, _, hwnd in candidates]


# ── Background Agent Manager ─────────────────────────────────────────────────

class BackgroundAgentManager:
    """
    Central controller for all background agent tasks.

    Usage:
        mgr = BackgroundAgentManager(max_parallel_tasks=3)
        mgr.start()                                       # starts queue processor thread
        task_id = mgr.queue_task("Search YouTube for X")  # non-blocking, returns immediately
        mgr.stop()                                        # graceful shutdown
    """

    def __init__(self, max_parallel_tasks: int = 3):
        self._queue: List[AgentTask] = []
        self._queue_lock = threading.Lock()
        self.active_tasks: Dict[str, AgentTask] = {}
        self.max_parallel = max_parallel_tasks
        self.task_history: List[AgentTask] = []

        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # System-level task executor (registry, settings, nvidia, game, etc.)
        self._system_executor = None

    # ── Public API ───────────────────────────────────────────────────────────

    def start(self):
        """Start the background queue processor thread."""
        if self._running:
            return
        self._running = True
        self._processor_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._processor_thread.start()
        print("[bg_agent] Background agent manager started")

    def stop(self):
        """Stop the queue processor and cancel active tasks."""
        self._running = False
        with self._queue_lock:
            for task in self._queue:
                task.status = "cancelled"
                task.completed_at = datetime.now()
                task.error = "App shutdown"
                self.task_history.append(task)
                save_task_to_log(task)
            self._queue.clear()

        for task in list(self.active_tasks.values()):
            task.status = "cancelled"
            task.completed_at = datetime.now()
            task.error = "App shutdown"
            save_task_to_log(task)
            self._cleanup_browser(task.browser_pid)
            self.task_history.append(task)
        self.active_tasks.clear()
        print("[bg_agent] Background agent manager stopped")

    def _get_system_executor(self):
        """Lazy-load the system task executor."""
        if self._system_executor is None:
            from core.system_task_executor import SystemTaskExecutor
            self._system_executor = SystemTaskExecutor()
        return self._system_executor

    def queue_task(self, description: str, task_type: Optional[str] = None) -> str:
        """
        Queue a task for background execution. Returns immediately with task_id.
        Thread-safe — can be called from any thread.

        task_type: "browser", "registry", "settings", "game", "system", "nvidia"
                   If None, auto-detected from description.
        """
        if task_type is None:
            task_type = detect_task_type(description)

        task_id = generate_task_id()
        task = AgentTask(
            task_id=task_id,
            description=description,
            status="queued",
            created_at=datetime.now(),
            task_type=task_type,
        )

        with self._queue_lock:
            self._queue.append(task)

        save_task_to_log(task)
        print(f"[bg_agent] Task queued: {task_id} — {description[:60]}")

        # Non-blocking toast
        try:
            from core.toast import show_toast
            show_toast(f"Task queued: {description[:50]}", "Wiztant Background Agent")
        except Exception:
            pass

        return task_id

    def get_status(self) -> Dict[str, Any]:
        """Return current queue and task status for UI display."""
        with self._queue_lock:
            queued_count = len(self._queue)
        return {
            "queued": queued_count,
            "active": len(self.active_tasks),
            "completed": len([t for t in self.task_history if t.status == "complete"]),
            "failed": len([t for t in self.task_history if t.status == "failed"]),
            "active_tasks": [t.to_dict() for t in self.active_tasks.values()],
            "recent_history": [t.to_dict() for t in self.task_history[-10:]],
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or active task."""
        # Check queue first
        with self._queue_lock:
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    task.status = "cancelled"
                    self._queue.pop(i)
                    self.task_history.append(task)
                    save_task_to_log(task)
                    return True

        # Check active tasks
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.status = "cancelled"
            self._cleanup_browser(task.browser_pid)
            del self.active_tasks[task_id]
            self.task_history.append(task)
            save_task_to_log(task)
            return True

        return False

    # ── Internal loop ────────────────────────────────────────────────────────

    def _run_loop(self):
        """Background thread: runs an asyncio event loop for task processing."""
        import traceback
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._process_queue())
        except Exception as e:
            print(f"[bg_agent] FATAL: processor thread died: {e}")
            traceback.print_exc()
        finally:
            print("[bg_agent] Processor thread exiting")
            try:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass

    def _on_task_future_done(self, fut):
        """Log any exception that propagated out of _execute_task coroutine."""
        import traceback
        try:
            exc = fut.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            return
        if exc is not None:
            print(f"[bg_agent] Task coroutine raised uncaught: {exc!r}")
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    async def _process_queue(self):
        """Continuously check the queue and launch tasks when slots are available."""
        import traceback
        while self._running:
            try:
                if len(self.active_tasks) < self.max_parallel:
                    task = None
                    with self._queue_lock:
                        if self._queue:
                            task = self._queue.pop(0)

                    if task is not None:
                        self.active_tasks[task.task_id] = task
                        print(f"[bg_agent] Dispatching task: {task.task_id} (type={task.task_type})")
                        fut = asyncio.ensure_future(self._execute_task(task))
                        fut.add_done_callback(self._on_task_future_done)
            except Exception as e:
                # Per-iteration failures must not kill the whole loop —
                # log and continue so the queue keeps being serviced.
                print(f"[bg_agent] process_queue iteration error: {e!r}")
                traceback.print_exc()

            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break

    async def _execute_task(self, task: AgentTask):
        """Execute a single background task, routing based on task_type."""
        try:
            task.status = "starting"
            save_task_to_log(task)
            print(f"[bg_agent] Starting task: {task.task_id} (type={task.task_type})")

            # Route to appropriate executor based on task_type
            if task.task_type == "browser":
                result = await self._execute_browser_task(task)
            elif task.task_type in ("registry", "settings", "nvidia", "game", "system"):
                result = await self._execute_system_type_task(task)
            else:
                result = await self._execute_browser_task(task)

            task.result = result
            result_status = "success"
            result_error = None
            if isinstance(result, dict):
                result_status = str(result.get("status", "success")).strip().lower()
                result_error = result.get("error")

            if result_status not in ("success", "complete", "done"):
                raise RuntimeError(str(result_error or "Task failed"))

            task.status = "complete"
            task.completed_at = datetime.now()
            task.progress_percent = 100
            save_task_to_log(task)
            print(f"[bg_agent] Task complete: {task.task_id}")

            # Deliver result
            await self._deliver_result(task)

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            save_task_to_log(task)
            print(f"[bg_agent] Task failed: {task.task_id} — {e}")
            await self._deliver_result(task)

        finally:
            if task.task_type != "browser":
                self._cleanup_browser(task.browser_pid)
            self.active_tasks.pop(task.task_id, None)
            self.task_history.append(task)

    async def _execute_browser_task(self, task: AgentTask):
        """Execute a browser-based task (web search, navigation, data extraction)."""
        from platforms.factory import get_vlm
        vlm = get_vlm()

        task.status = "executing"
        save_task_to_log(task)
        task.current_step = 1
        task.total_steps = 1
        task.progress_percent = 25
        save_task_to_log(task)

        result = await asyncio.to_thread(vlm.run_agent_loop, task.description)
        task.current_step = 1
        task.total_steps = 1
        failed = isinstance(result, str) and result.lower().startswith((
            "could not plan",
            "not confident enough",
            "task failed",
            "failed:",
            "reached ",
        ))
        task.progress_percent = 100 if not failed else max(task.progress_percent, 25)
        save_task_to_log(task)

        if failed:
            return {
                "status": "failed",
                "data": None,
                "error": str(result),
            }

        return {
            "status": "success",
            "data": str(result or task.description),
            "error": None,
        }

    async def _execute_system_type_task(self, task: AgentTask):
        """
        Execute system-level tasks (registry, settings, nvidia, game optimization).
        Delegates to SystemTaskExecutor which launches the right app,
        then passes the VLM agent loop function for driving the UI.
        """
        executor = self._get_system_executor()

        # The VLM loop function that system_task_executor will call
        # with the target window handle
        async def vlm_loop_fn(t, hwnd):
            return await self._run_agent_loop(t, hwnd)

        if task.task_type == "registry":
            return await executor.execute_registry_task(task, vlm_loop_fn)
        elif task.task_type == "settings":
            return await executor.execute_windows_settings_task(task, vlm_loop_fn)
        elif task.task_type == "nvidia":
            return await executor.execute_nvidia_task(task, vlm_loop_fn)
        elif task.task_type == "game":
            return await executor.execute_game_optimization(task, vlm_loop_fn)
        elif task.task_type == "system":
            return await executor.execute_system_task(task, vlm_loop_fn)
        else:
            return await self._execute_browser_task(task)

    # ── Browser lifecycle ────────────────────────────────────────────────────

    async def _launch_browser(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Launch a browser in a new process, minimized immediately.
        Returns (pid, window_handle).
        """
        browser_path = _find_browser_path()
        profile_id = f"WhiztantBg_{int(time.time()) % 100000}"
        existing_hwnds = set(_find_visible_browser_windows(browser_path))

        args = [browser_path]
        # Chromium-based browsers support these flags
        if "firefox" not in browser_path.lower():
            args.extend([
                "--new-window",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                f"--user-data-dir={_PROJECT_ROOT / 'data' / 'bg_profiles' / profile_id}",
                "about:blank",
            ])
        else:
            args.extend(["-new-window", "about:blank"])

        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        hwnd = None
        for _ in range(120):
            hwnd = _find_browser_window_for_process(proc.pid, browser_path)
            if not hwnd:
                visible_browser_hwnds = _find_visible_browser_windows(browser_path)
                new_hwnds = [candidate for candidate in visible_browser_hwnds if candidate not in existing_hwnds]
                if new_hwnds:
                    hwnd = new_hwnds[0]
                elif visible_browser_hwnds:
                    hwnd = visible_browser_hwnds[0]
            if hwnd:
                break
            await asyncio.sleep(0.1)

        return proc.pid, hwnd

    def _cleanup_browser(self, pid: Optional[int]):
        """Kill a browser process and clean up its profile directory."""
        if pid is None:
            return
        try:
            import psutil
            proc = psutil.Process(pid)
            for child in proc.children(recursive=True):
                try:
                    child.terminate()
                except Exception:
                    pass
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

    # ── Agent execution loop ─────────────────────────────────────────────────

    async def _run_agent_loop(
        self,
        task: AgentTask,
        target_hwnd: int,
    ) -> Dict[str, Any]:
        """
        VLM agent loop operating on a target window (browser or system app).
        Takes screenshots of just that window, sends to VLM, executes actions
        via isolated PostMessage input, never touching the user's foreground.

        Integrates ActionOptimizer for:
        - Screenshot caching (skip VLM if UI unchanged)
        - Action batching (reduce API calls)
        - Heuristic fast-path (common UI patterns)
        - Adaptive wait times
        """
        from core.agent_isolation import (
            AgentInputContext,
            is_window_valid,
            restore_window,
        )
        from core.action_optimizer import ActionOptimizer

        max_steps = int(_cfg("BG_AGENT_MAX_STEPS", "20"))
        context = AgentInputContext(target_hwnd)
        optimizer = ActionOptimizer()
        history: List[Dict[str, Any]] = []
        result_data: Dict[str, Any] = {"status": "incomplete", "data": None, "error": None}

        for step in range(1, max_steps + 1):
            if not self._running:
                result_data["error"] = "Manager stopped"
                break

            if not is_window_valid(target_hwnd):
                result_data["error"] = "Target window closed unexpectedly"
                break

            task.current_step = step
            task.total_steps = max_steps
            task.progress_percent = int((step / max_steps) * 100)

            # Temporarily restore window so mss can capture its pixels
            restore_window(target_hwnd)
            await asyncio.sleep(0.3)

            # Take window-specific screenshot
            screenshot_b64 = _capture_window_screenshot(target_hwnd)
            if not screenshot_b64:
                result_data["error"] = "Failed to capture window screenshot"
                break

            # Optimization: skip VLM if screenshot unchanged
            if optimizer.is_screenshot_unchanged(screenshot_b64) and not optimizer.should_force_refresh:
                # Try heuristic fast-path
                heuristic = ActionOptimizer.heuristic_action(
                    task.description,
                    history[-1].get("action_json") if history else None,
                )
                if heuristic:
                    action = heuristic
                else:
                    # UI hasn't changed, wait a bit longer
                    await asyncio.sleep(0.5)
                    continue
            else:
                # Call VLM
                try:
                    action = await _call_bg_vlm(
                        screenshot_b64=screenshot_b64,
                        task_description=task.description,
                        step_number=step,
                        history=history,
                    )
                    optimizer.cache_response(action)
                except json.JSONDecodeError:
                    history.append({"action_json": {}, "result": "VLM returned invalid JSON"})
                    continue
                except Exception as e:
                    result_data["error"] = f"VLM error: {e}"
                    break

            action_type = str(action.get("action", "")).strip().lower()

            # Check for completion
            if action_type == "complete":
                result_data["status"] = "success"
                result_data["data"] = action.get("result", "Task completed")
                break

            if action_type == "error":
                result_data["error"] = action.get("message", "Unknown VLM error")
                break

            # Execute action in isolated context
            exec_result = await self._execute_isolated_action(context, action, target_hwnd)
            history.append({"action_json": action, "result": exec_result})

            # Re-minimize after action
            from core.agent_isolation import minimize_window
            minimize_window(target_hwnd)

            # Adaptive wait: use optimizer's estimate instead of fixed 0.5s
            wait_time = optimizer.estimate_wait_time(action)
            await asyncio.sleep(wait_time)

        if result_data["status"] == "incomplete" and not result_data["error"]:
            result_data["error"] = f"Reached max steps ({max_steps}) without completing"

        return result_data

    async def _execute_isolated_action(
        self,
        context: "AgentInputContext",
        action: Dict[str, Any],
        browser_hwnd: int,
    ) -> str:
        """Execute a single VLM action in the isolated window context."""
        action_type = str(action.get("action", "")).strip().lower()

        try:
            if action_type == "click":
                x = int(action.get("x", 0))
                y = int(action.get("y", 0))
                await context.click_in_window(x, y)
                return f"OK: clicked ({x}, {y})"

            elif action_type == "type":
                text = str(action.get("text", ""))
                await context.type_text_in_window(text)
                return f"OK: typed '{text[:40]}'"

            elif action_type == "key":
                key = str(action.get("key", ""))
                await context.press_key_in_window(key)
                return f"OK: pressed {key}"

            elif action_type == "scroll":
                x = int(action.get("x", 400))
                y = int(action.get("y", 400))
                direction = str(action.get("direction", "down"))
                amount = int(action.get("amount", 3))
                await context.scroll_in_window(x, y, direction, amount)
                return f"OK: scrolled {direction}"

            else:
                return f"UNKNOWN: {action_type}"

        except Exception as e:
            return f"FAILED: {e}"

    async def _execute_browser_planned_action(
        self,
        action: Dict[str, Any],
        browser_hwnd: int,
    ) -> str:
        from core import vlm

        action_type = str(action.get("type", "")).strip().lower()

        try:
            if action_type == "click":
                if action.get("x") is None or action.get("y") is None:
                    return "FAILED: click action missing coordinates"
                _activate_browser_window(browser_hwnd)
                x, y = _normalized_to_screen_coords(browser_hwnd, action.get("x"), action.get("y"))
                if not vlm.safe_click(x, y, "background browser planned action"):
                    return f"FAILED: click failed at ({x}, {y})"
                return f"OK: clicked ({x}, {y})"

            if action_type == "type":
                text = str(action.get("text", ""))
                if not text:
                    return "FAILED: type action missing text"
                _activate_browser_window(browser_hwnd)
                if not vlm.safe_type(text, "background browser planned action"):
                    return "FAILED: type failed"
                return f"OK: typed '{text[:40]}'"

            if action_type == "press":
                key = str(action.get("key", ""))
                if not key:
                    return "FAILED: press action missing key"
                _activate_browser_window(browser_hwnd)
                if not vlm.safe_press(key, "background browser planned action"):
                    return f"FAILED: press failed for {key}"
                return f"OK: pressed {key}"

            if action_type == "scroll":
                direction = str(action.get("direction", "down")).strip().lower()
                amount = int(action.get("amount", 3))
                _activate_browser_window(browser_hwnd)
                import pyautogui as _pag
                # Move to optional coordinates first
                if action.get("x") is not None and action.get("y") is not None:
                    sx, sy = _normalized_to_screen_coords(browser_hwnd, action.get("x"), action.get("y"))
                    _pag.moveTo(sx, sy, duration=0.1)
                scroll_clicks = -amount if direction == "down" else amount
                _pag.scroll(scroll_clicks)
                import time as _t; _t.sleep(0.3)
                return f"OK: scrolled {direction} by {amount}"

            if action_type in {"wait", "sleep"}:
                import time as _t
                secs = float(action.get("seconds", 1.0))
                _t.sleep(min(secs, 5.0))  # cap at 5s
                return f"OK: waited {secs}s"

            return f"SKIPPED: unknown action type '{action_type}'"

        except Exception as e:
            return f"FAILED: {e}"

    # ── Result delivery ──────────────────────────────────────────────────────

    async def _deliver_result(self, task: AgentTask):
        """Deliver task result via clipboard + toast. Non-blocking."""
        if task.status == "complete":
            result_text = ""
            if isinstance(task.result, dict):
                result_text = str(task.result.get("data", ""))
            else:
                result_text = str(task.result or "")

            # Copy to clipboard
            try:
                import pyperclip
                pyperclip.copy(result_text)
            except Exception:
                pass

            # Toast
            try:
                from core.toast import show_toast
                preview = task.description[:45]
                show_toast(
                    f"{preview} — result copied to clipboard",
                    "Wiztant — Task Complete",
                )
            except Exception:
                pass

        elif task.status == "failed":
            try:
                from core.toast import show_toast
                show_toast(
                    f"Failed: {(task.error or 'unknown')[:50]}",
                    "Wiztant — Task Failed",
                )
            except Exception:
                pass


# ── Module-level singleton ───────────────────────────────────────────────────

_manager: Optional[BackgroundAgentManager] = None


def get_background_agent_manager() -> BackgroundAgentManager:
    """Get or create the singleton BackgroundAgentManager."""
    global _manager
    if _manager is None:
        max_tasks = int(_cfg("BG_AGENT_MAX_PARALLEL", "3"))
        _manager = BackgroundAgentManager(max_parallel_tasks=max_tasks)
    return _manager


def init_background_agent():
    """Initialize and start the background agent manager. Called from main.py."""
    mgr = get_background_agent_manager()
    mgr.start()
    return mgr


def stop_background_agent():
    """Graceful shutdown. Called on app exit."""
    global _manager
    if _manager is not None:
        _manager.stop()
        _manager = None
