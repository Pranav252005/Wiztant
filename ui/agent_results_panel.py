"""
Whiztant ui/agent_results_panel.py — Non-blocking results display for background agent tasks.

Shows completed/failed background tasks in a lightweight Tkinter panel.
The panel is NOT topmost — the user's window stays on top.
"""

import json
import threading
from datetime import datetime
from typing import Optional, List

_panel_instance: Optional["AgentResultsPanel"] = None
_panel_lock = threading.Lock()


class AgentResultsPanel:
    """
    Lightweight panel to display completed background agent tasks.
    Uses Tkinter so it works without additional dependencies.
    NOT topmost — user's foreground window stays active.
    """

    def __init__(self):
        import tkinter as tk
        from tkinter import scrolledtext

        self._root = tk.Toplevel() if tk._default_root else tk.Tk()
        self._root.title("Wiztant — Background Tasks")
        self._root.geometry("520x420")
        self._root.configure(bg="#13171B")
        self._root.attributes("-topmost", False)
        self._root.protocol("WM_DELETE_WINDOW", self.hide)

        # Header
        header = tk.Frame(self._root, bg="#1E2328")
        header.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(
            header,
            text="Background Agent Tasks",
            font=("Segoe UI", 11, "bold"),
            bg="#1E2328",
            fg="#E6E1DC",
            padx=12,
            pady=8,
        ).pack(side=tk.LEFT)

        self._status_label = tk.Label(
            header,
            text="0 active, 0 queued",
            font=("Segoe UI", 9),
            bg="#1E2328",
            fg="#7A828E",
            padx=12,
            pady=8,
        )
        self._status_label.pack(side=tk.RIGHT)

        # Task log
        self._text = scrolledtext.ScrolledText(
            self._root,
            height=18,
            width=62,
            bg="#0F1215",
            fg="#E6E1DC",
            font=("Consolas", 9),
            insertbackground="#E6E1DC",
            selectbackground="#262C33",
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 4))

        # Bottom bar
        bottom = tk.Frame(self._root, bg="#1E2328")
        bottom.pack(fill=tk.X, padx=0, pady=0)

        tk.Button(
            bottom,
            text="Copy Last Result",
            command=self._copy_last,
            bg="#262C33",
            fg="#E6E1DC",
            activebackground="#333A42",
            activeforeground="#E6E1DC",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=8, pady=6)

        tk.Button(
            bottom,
            text="Clear",
            command=self._clear,
            bg="#262C33",
            fg="#7A828E",
            activebackground="#333A42",
            activeforeground="#E6E1DC",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=0, pady=6)

        self._tasks: List[dict] = []
        self._root.withdraw()  # Start hidden

    def show(self):
        """Show the panel."""
        try:
            self._root.deiconify()
            self._root.lift()
        except Exception:
            pass

    def hide(self):
        """Hide the panel (don't destroy)."""
        try:
            self._root.withdraw()
        except Exception:
            pass

    @property
    def visible(self) -> bool:
        try:
            return self._root.winfo_viewable()
        except Exception:
            return False

    def update_status(self, active: int, queued: int):
        """Update the header status label."""
        try:
            self._status_label.config(text=f"{active} active, {queued} queued")
        except Exception:
            pass

    def add_task_result(self, task_dict: dict):
        """Append a completed/failed task to the display."""
        import tkinter as tk

        self._tasks.append(task_dict)

        status = task_dict.get("status", "unknown").upper()
        desc = task_dict.get("description", "")
        task_id = task_dict.get("task_id", "?")
        completed = task_dict.get("completed_at", "")
        result = task_dict.get("result")
        error = task_dict.get("error")

        marker = "[OK]" if status == "COMPLETE" else "[FAIL]"
        result_text = ""
        if result:
            if isinstance(result, dict):
                result_text = str(result.get("data", result))
            else:
                result_text = str(result)
        if error:
            result_text = f"Error: {error}"

        entry = (
            f"\n{'=' * 56}\n"
            f"  {marker} {task_id}\n"
            f"  Task: {desc}\n"
            f"  Status: {status}  |  {completed or ''}\n"
        )
        if result_text:
            entry += f"  Result: {result_text[:300]}\n"
        entry += f"{'=' * 56}\n"

        try:
            self._text.config(state=tk.NORMAL)
            self._text.insert(tk.END, entry)
            self._text.see(tk.END)
            self._text.config(state=tk.DISABLED)
        except Exception:
            pass

    def _copy_last(self):
        """Copy the last task result to clipboard."""
        if not self._tasks:
            return
        last = self._tasks[-1]
        result = last.get("result")
        if isinstance(result, dict):
            text = str(result.get("data", json.dumps(result, indent=2)))
        else:
            text = str(result or last.get("error", ""))
        try:
            import pyperclip
            pyperclip.copy(text)
            from core.toast import show_toast
            show_toast("Result copied to clipboard", "Wiztant")
        except Exception:
            pass

    def _clear(self):
        """Clear the task log display."""
        import tkinter as tk
        self._tasks.clear()
        try:
            self._text.config(state=tk.NORMAL)
            self._text.delete("1.0", tk.END)
            self._text.config(state=tk.DISABLED)
        except Exception:
            pass


# ── Module-level helpers ─────────────────────────────────────────────────────

def get_results_panel() -> Optional[AgentResultsPanel]:
    """Get the singleton results panel (creates it on first call from main thread)."""
    global _panel_instance
    with _panel_lock:
        if _panel_instance is None:
            try:
                _panel_instance = AgentResultsPanel()
            except Exception as e:
                print(f"[agent_results_panel] Could not create panel: {e}")
                return None
        return _panel_instance


def show_results_panel():
    """Show the results panel."""
    panel = get_results_panel()
    if panel:
        panel.show()


def hide_results_panel():
    """Hide the results panel."""
    panel = get_results_panel()
    if panel:
        panel.hide()


def add_result_to_panel(task_dict: dict):
    """Add a task result to the panel (thread-safe: schedules on Tk main loop)."""
    panel = get_results_panel()
    if panel:
        try:
            panel._root.after(0, lambda: panel.add_task_result(task_dict))
        except Exception:
            pass
