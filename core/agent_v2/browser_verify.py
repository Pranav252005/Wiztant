"""
core/agent_v2/browser_verify.py — Browser launch, dev server detection,
and screenshot capture for the Build-Browse-Fix loop.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


def detect_dev_server_port(project_path: str) -> Optional[int]:
    """Detect the dev server port from package.json scripts."""
    pkg_path = Path(project_path) / "package.json"
    if not pkg_path.exists():
        return None
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        dev_script = scripts.get("dev", "")

        # Common port patterns
        if "3000" in dev_script:
            return 3000
        if "5173" in dev_script:
            return 5173
        if "4321" in dev_script:
            return 4321
        if "8080" in dev_script:
            return 8080
        if "--port" in dev_script:
            import re
            match = re.search(r"--port\s+(\d+)", dev_script)
            if match:
                return int(match.group(1))

        # Framework defaults
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "next" in deps:
            return 3000
        if "vite" in deps or "astro" in deps:
            return 5173
        if "@remix-run/dev" in deps:
            return 5173
        if "react-scripts" in deps:
            return 3000
    except Exception:
        pass
    return 3000  # Default fallback


def is_server_ready(port: int, host: str = "127.0.0.1") -> bool:
    """Check if localhost:PORT is responding."""
    try:
        req = urllib.request.Request(f"http://{host}:{port}", method="HEAD")
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def start_dev_server(project_path: str, port: int) -> Tuple[bool, str]:
    """Start the dev server in the background. Returns (success, message)."""
    pkg_path = Path(project_path) / "package.json"
    if not pkg_path.exists():
        return False, "package.json not found"

    try:
        # Try to start dev server via subprocess
        # We use nohup / disown pattern so it keeps running
        subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, "dev_server_started"
    except Exception as e:
        return False, f"failed_to_start_dev_server:{e}"


def wait_for_server(port: int, timeout: float = 30.0, interval: float = 2.0) -> bool:
    """Poll until the server is ready or timeout."""
    elapsed = 0.0
    while elapsed < timeout:
        if is_server_ready(port):
            return True
        time.sleep(interval)
        elapsed += interval
    return False


def capture_localhost_screenshot(port: int, runtime) -> Tuple[Optional[Image.Image], str]:
    """
    Open browser, navigate to localhost:PORT, wait for stable page,
    then capture a screenshot.
    """
    try:
        # Open browser
        runtime.open_browser("chrome", url=f"http://127.0.0.1:{port}")
        time.sleep(2.0)

        # Wait for page to stabilize (screenshot hash stable for 3s)
        prev_hash = ""
        stable_start = None
        deadline = time.time() + 15.0

        while time.time() < deadline:
            img = runtime.screenshot()
            import hashlib
            curr_hash = hashlib.md5(img.tobytes()).hexdigest()

            if curr_hash == prev_hash:
                if stable_start is None:
                    stable_start = time.time()
                elif time.time() - stable_start >= 3.0:
                    return img, "stable"
            else:
                stable_start = None

            prev_hash = curr_hash
            time.sleep(1.0)

        # Timeout — return last screenshot anyway
        img = runtime.screenshot()
        return img, "timeout"

    except Exception as e:
        return None, f"screenshot_failed:{e}"


def verify_localhost(
    project_path: str,
    runtime,
    auto_start: bool = True,
) -> Tuple[Optional[Image.Image], str]:
    """
    Full verification flow: detect port, start server if needed,
    wait, open browser, screenshot.
    """
    port = detect_dev_server_port(project_path)
    if port is None:
        port = 3000

    if not is_server_ready(port):
        if not auto_start:
            return None, f"server_not_ready_on_port_{port}"
        ok, msg = start_dev_server(project_path, port)
        if not ok:
            return None, msg
        if not wait_for_server(port):
            return None, f"server_failed_to_start_on_port_{port}"

    return capture_localhost_screenshot(port, runtime)
