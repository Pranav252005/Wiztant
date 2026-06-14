"""
core/agent_v2_clipboard.py — Clipboard monitoring and error detection for the Bridge Agent.

Watches the clipboard for error patterns (stack traces, module not found,
permission denied) and surfaces them to the agent for automatic handling.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

log = logging.getLogger("core.agent_v2_clipboard")


# =============================================================
#  ERROR PATTERNS
# =============================================================

ERROR_PATTERNS: List[tuple[str, re.Pattern]] = [
    ("stack_trace", re.compile(r'Traceback\s+\(most\s+recent\s+call\s+last\)', re.IGNORECASE)),
    ("python_error", re.compile(r'\w+Error:\s+', re.IGNORECASE)),
    ("module_not_found", re.compile(r"Module not found|Can't resolve|Cannot find module", re.IGNORECASE)),
    ("permission_denied", re.compile(r'Permission denied|Access denied|EACCES', re.IGNORECASE)),
    ("syntax_error", re.compile(r'SyntaxError|Unexpected token|ParseError', re.IGNORECASE)),
    ("type_error", re.compile(r'TypeError|Type mismatch', re.IGNORECASE)),
    ("null_reference", re.compile(r'NullPointerException|Cannot read propert.*?of null|Cannot read propert.*?of undefined', re.IGNORECASE)),
    ("build_error", re.compile(r'Build failed|Compilation failed|Failed to compile', re.IGNORECASE)),
    ("test_failure", re.compile(r'Tests?\s+failed|AssertionError|expect\(.*?\)\.to', re.IGNORECASE)),
    ("git_error", re.compile(r'fatal:|error:.*git|rejected|conflict', re.IGNORECASE)),
    ("npm_error", re.compile(r'npm ERR!|pnpm ERR!|yarn error', re.IGNORECASE)),
    ("docker_error", re.compile(r'docker.*error|container.*failed|image.*not found', re.IGNORECASE)),
    ("network_error", re.compile(r'ECONNREFUSED|ETIMEDOUT|Network Error|fetch failed', re.IGNORECASE)),
    ("lint_error", re.compile(r'eslint|prettier|lint.*error', re.IGNORECASE)),
]


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class DetectedError:
    """An error detected in the clipboard."""

    text: str
    error_type: str
    timestamp: float = field(default_factory=time.time)
    file_paths: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary of the error."""
        first_line = self.text.strip().split("\n")[0][:120]
        return f"[{self.error_type}] {first_line}"


# =============================================================
#  CLIPBOARD MONITOR
# =============================================================

class ClipboardMonitor:
    """
    Monitors the system clipboard for error patterns.

    Runs in a background thread and calls registered callbacks when
    an error pattern is detected.
    """

    def __init__(self, poll_interval: float = 1.5) -> None:
        self.poll_interval = poll_interval
        self._last_text: str = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[DetectedError], None]] = []
        self._last_error: Optional[DetectedError] = None
        self._lock = threading.Lock()

    def start_monitoring(self) -> None:
        """Start the clipboard monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        log.info("Clipboard monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the clipboard monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        log.info("Clipboard monitoring stopped")

    def on_error_detected(self, callback: Callable[[DetectedError], None]) -> None:
        """Register a callback to be called when an error is detected."""
        self._callbacks.append(callback)

    def get_last_error(self) -> Optional[DetectedError]:
        """Get the most recently detected error."""
        with self._lock:
            return self._last_error

    def clear_last_error(self) -> None:
        """Clear the last detected error."""
        with self._lock:
            self._last_error = None

    def _get_clipboard_text(self) -> str:
        """Read the system clipboard as text."""
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            # Fallback: try platform-specific methods
            try:
                import subprocess
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception:
                pass
        return ""

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                self._check_clipboard()
            except Exception as e:
                log.warning("Clipboard poll error: %s", e)
            time.sleep(self.poll_interval)

    def _check_clipboard(self) -> None:
        """Check clipboard content for error patterns."""
        text = self._get_clipboard_text()
        if not text or text == self._last_text:
            return

        self._last_text = text

        # Check if text matches any error pattern
        detected_type = self._classify_error(text)
        if detected_type:
            file_paths = self._extract_file_paths(text)
            error = DetectedError(
                text=text,
                error_type=detected_type,
                file_paths=file_paths,
            )
            with self._lock:
                self._last_error = error

            log.info("Clipboard error detected: %s", error.summary())
            for cb in self._callbacks:
                try:
                    cb(error)
                except Exception as e:
                    log.warning("Error callback failed: %s", e)

    def _classify_error(self, text: str) -> Optional[str]:
        """Classify text as an error type if it matches any pattern."""
        for error_type, pattern in ERROR_PATTERNS:
            if pattern.search(text):
                return error_type
        return None

    def _extract_file_paths(self, text: str) -> List[str]:
        """Extract file paths mentioned in error text."""
        paths = []
        # Match File "path", line N
        for match in re.finditer(r'File\s+["\']([^"\']+)["\']', text):
            paths.append(match.group(1))
        # Match import paths
        for match in re.finditer(r'from\s+["\']([^"\']+)["\']|import\s+["\']([^"\']+)["\']', text):
            p = match.group(1) or match.group(2)
            if p:
                paths.append(p)
        return list(set(paths))


# =============================================================
#  ONE-SHOT CLIPBOARD READERS
# =============================================================

def read_clipboard_text() -> str:
    """Read the current clipboard text."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return ""


def detect_error_in_text(text: str) -> Optional[DetectedError]:
    """Classify a text string as an error without monitoring."""
    monitor = ClipboardMonitor()
    error_type = monitor._classify_error(text)
    if error_type:
        return DetectedError(
            text=text,
            error_type=error_type,
            file_paths=monitor._extract_file_paths(text),
        )
    return None
