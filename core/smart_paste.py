"""
core/smart_paste.py — Intelligent paste engine

Format text intelligently for tasks.
Clipboard management (clear -> copy -> paste).
Cross-window paste via platform_backends.type_text() with clipboard fallback.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Optional, Tuple

import pyperclip

logger = logging.getLogger(__name__)


class SmartPasteEngine:
    """Format & paste text safely."""

    def __init__(self):
        self.last_paste_time = 0.0
        self.last_paste_text = ""
        self.paste_stats = {
            "total_pastes": 0,
            "successful": 0,
            "failed": 0,
            "avg_latency_ms": 0.0,
        }

    def format_for_task(self, text: str) -> str:
        """
        Format as task title.
        - Trim whitespace
        - Capitalize first letter
        - Remove filler words (um, uh, like)
        - Remove trailing period (too formal)

        Examples:
        "  call john about the deadline  " -> "Call john about the deadline"
        "create task for um the project" -> "Create task for the project"
        """
        text = text.strip()
        if not text:
            return ""

        # Remove common filler words anywhere in text
        fillers = [
            r"\bum\b",
            r"\buh\b",
            r"\blike\b",
            r"\byeah\b",
            r"\bokay\b",
            r"\bso\b",
            r"\bright\b",
            r"\bcorrect\b",
        ]
        for pattern in fillers:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        # Collapse extra spaces left by removal
        text = re.sub(r"\s{2,}", " ", text).strip()

        # Remove trailing period/punctuation
        text = text.rstrip(".,!?;:")

        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]

        return text

    def format_for_description(self, text: str) -> str:
        """Format as multi-sentence description."""
        text = text.strip()
        if not text:
            return ""

        # Split sentences
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Capitalize each sentence
        formatted = ". ".join(
            s[0].upper() + s[1:] if s else "" for s in sentences
        )

        if formatted and not formatted.endswith("."):
            formatted += "."

        return formatted

    def _linux_clipboard_copy(self, text: str) -> bool:
        """Linux fallback using xclip, xsel, or wl-copy directly."""
        import shutil, subprocess
        enc = text.encode("utf-8")
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard", "-in"],
            ["xsel", "-b", "-i"],
        ):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=enc, timeout=3, check=True)
                    return True
                except Exception:
                    pass
        return False

    def clear_clipboard(self) -> bool:
        """Clear system clipboard."""
        try:
            pyperclip.copy("")
            return True
        except Exception as e:
            logger.warning(f"Clear clipboard failed: {e}")
            return self._linux_clipboard_copy("")

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard."""
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            logger.error(f"Copy to clipboard error: {e}")
            return self._linux_clipboard_copy(text)

    def paste_via_hotkey(self) -> bool:
        """Paste via Ctrl+V simulation."""
        # Try keyboard library first (works on Windows and some Linux setups)
        try:
            import keyboard as _kb
            _kb.press_and_release("ctrl+v")
            return True
        except Exception:
            pass

        # Detect Wayland so we paste from the same clipboard backend we copied to.
        _is_wayland = (
            os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY"))
        )

        # Fallback: display-server-native tools first to avoid pynput
        # permission dialogs that silently fail on Wayland / some X11.
        # Only try a tool if it is actually installed (shutil.which).

        if _is_wayland:
            # Wayland: wtype first (reads Wayland clipboard), then xdotool fallback
            if shutil.which("wtype"):
                try:
                    subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], timeout=2, check=True)
                    print("[Paste] wtype ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] wtype failed: {e}")

            if shutil.which("ydotool"):
                try:
                    subprocess.run(["ydotool", "key", "ctrl+v"], timeout=2, check=True)
                    print("[Paste] ydotool ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] ydotool failed: {e}")

            # xdotool fallback via XWayland (reads X11 clipboard — may be stale)
            if shutil.which("xdotool"):
                try:
                    subprocess.run(["xdotool", "key", "ctrl+v"], timeout=2, check=True)
                    print("[Paste] xdotool ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] xdotool failed: {e}")
        else:
            # X11: xdotool first, then Wayland fallbacks
            if shutil.which("xdotool"):
                try:
                    subprocess.run(["xdotool", "key", "ctrl+v"], timeout=2, check=True)
                    print("[Paste] xdotool ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] xdotool failed: {e}")

            if shutil.which("wtype"):
                try:
                    subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], timeout=2, check=True)
                    print("[Paste] wtype ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] wtype failed: {e}")

            if shutil.which("ydotool"):
                try:
                    subprocess.run(["ydotool", "key", "ctrl+v"], timeout=2, check=True)
                    print("[Paste] ydotool ctrl+v succeeded")
                    return True
                except Exception as e:
                    print(f"[Paste] ydotool failed: {e}")

        # pynput fallback — may trigger an accessibility approval dialog
        try:
            from pynput.keyboard import Controller, Key

            c = Controller()
            c.press(Key.ctrl)
            c.press("v")
            c.release("v")
            c.release(Key.ctrl)
            print("[Paste] pynput ctrl+v attempted")
            return True
        except Exception as e:
            print(f"[Paste] pynput failed: {e}")

        print("[Paste] No input backend available for Ctrl+V")
        return False

    def paste_text(self, text: str, format_type: str = "task") -> Tuple[bool, str]:
        """
        Complete paste flow: format -> clear -> copy -> paste.

        Returns:
            (success: bool, message: str)
        """
        start_time = time.time()

        try:
            # Format
            if format_type == "task":
                formatted = self.format_for_task(text)
            elif format_type == "description":
                formatted = self.format_for_description(text)
            else:
                formatted = text

            if not formatted:
                return False, "Formatted text is empty"

            # Copy to clipboard (skip clear — it can leave clipboard empty if copy fails)
            if not self.copy_to_clipboard(formatted):
                return False, "Failed to copy to clipboard"

            # Linux needs longer for clipboard to propagate; verify it landed.
            clipboard_delay = 0.5 if sys.platform != "win32" else 0.2
            time.sleep(clipboard_delay)
            try:
                if pyperclip.paste() != formatted:
                    # pyperclip read mismatch — try Linux fallback again
                    self._linux_clipboard_copy(formatted)
                    time.sleep(0.3)
            except Exception:
                pass

            if sys.platform == "win32":
                # Windows: type_text (pyautogui) is rock-solid — try first
                try:
                    from core.platform_backends import type_text

                    ok, msg = type_text(formatted)
                    if ok:
                        latency = (time.time() - start_time) * 1000
                        self._track_success(latency)
                        logger.info(
                            f"Pasted (type_text, {latency:.0f}ms): {formatted[:50]}..."
                        )
                        return True, f"Pasted: {formatted[:60]}"
                except Exception as e:
                    logger.debug(f"Direct type failed: {e}")

                # Fallback: clipboard + Ctrl+V
                if self.paste_via_hotkey():
                    latency = (time.time() - start_time) * 1000
                    self._track_success(latency)
                    logger.info(
                        f"Pasted (clipboard, {latency:.0f}ms): {formatted[:50]}..."
                    )
                    return True, f"Pasted: {formatted[:60]}"
            else:
                # Linux: clipboard + Ctrl+V first (xdotool/wtype are more reliable
                # than pynput which may silently fail on Wayland).
                # Retry up to 3 times so user can approve any OS accessibility dialog.
                pasted = False
                for attempt in range(3):
                    if self.paste_via_hotkey():
                        pasted = True
                        break
                    logger.info(f"Paste attempt {attempt + 1}/3 failed; retrying...")
                    time.sleep(0.5)

                if pasted:
                    latency = (time.time() - start_time) * 1000
                    self._track_success(latency)
                    logger.info(
                        f"Pasted (clipboard, {latency:.0f}ms): {formatted[:50]}..."
                    )
                    return True, f"Pasted: {formatted[:60]}"

                # Final fallback: direct type injection
                try:
                    from core.platform_backends import type_text

                    ok, msg = type_text(formatted, interval=0.005)
                    if ok:
                        latency = (time.time() - start_time) * 1000
                        self._track_success(latency)
                        logger.info(
                            f"Pasted (type_text fallback, {latency:.0f}ms): {formatted[:50]}..."
                        )
                        return True, f"Pasted: {formatted[:60]}"
                except Exception as e:
                    logger.debug(f"Direct type fallback failed: {e}")

            return False, "Paste hotkey failed"

        except Exception as e:
            self.paste_stats["total_pastes"] += 1
            self.paste_stats["failed"] += 1
            logger.error(f"Paste failed: {e}")
            return False, f"Paste error: {str(e)}"

    def _track_success(self, latency_ms: float):
        self.paste_stats["total_pastes"] += 1
        self.paste_stats["successful"] += 1
        n = self.paste_stats["successful"]
        self.paste_stats["avg_latency_ms"] = (
            self.paste_stats["avg_latency_ms"] * (n - 1) + latency_ms
        ) / n
        self.last_paste_time = time.time()

    def get_last_paste(self) -> Optional[str]:
        """Get last pasted text."""
        return self.last_paste_text or None

    def get_paste_stats(self) -> dict:
        """Get paste statistics."""
        return self.paste_stats.copy()

    def reset_paste_stats(self):
        """Reset statistics."""
        self.paste_stats = {
            "total_pastes": 0,
            "successful": 0,
            "failed": 0,
            "avg_latency_ms": 0.0,
        }


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    engine = SmartPasteEngine()

    tests = [
        ("  create a task for um the Q4 report  ", "task"),
        ("call john smith about the deadline", "task"),
        (
            "this is a description. it has multiple sentences. and lots of thoughts",
            "description",
        ),
    ]

    for text, fmt in tests:
        if fmt == "task":
            result = engine.format_for_task(text)
        else:
            result = engine.format_for_description(text)

        print(f"{fmt:12} | {text[:50]:50} -> {result}")
