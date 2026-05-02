"""
Whiztant — tkinter in-app toast notifications.
Lightweight slide-in from bottom-right. Stacks upward. Auto-dismiss.
Replaces winotify-based notifications for in-process UI feedback.
"""

import threading
import tkinter as tk

from ui.constants import (
    BG_PANEL, BORDER, TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    ACCENT, SUCCESS, WARNING, ERROR,
    FONT_LABEL, FONT_SMALL, apply_window_style,
)

_TOAST_W = 300
_TOAST_H = 56
_MARGIN  = 20
_GAP     = 8
_LIFETIME_MS = 3500
_FADE_MS = 300

_active: list["Toast"] = []
_lock = threading.Lock()


class Toast:
    def __init__(self, msg: str, kind: str = "info"):
        self.msg = msg
        self.kind = kind
        self.color = {
            "success": SUCCESS,
            "error":   ERROR,
            "warning": WARNING,
            "info":    ACCENT,
        }.get(kind, ACCENT)
        self.root: tk.Toplevel | None = None
        self._alive = True

    # ── public ─────────────────────────────────────────────────
    def show(self):
        try:
            self.root = tk.Toplevel()
        except Exception:
            # No Tk root yet — fall back to print
            print(f"[Toast:{self.kind}] {self.msg}")
            return
        apply_window_style(self.root)
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-alpha", 0.0)
        except Exception:
            pass

        self._build()
        self._place()

        # fade in
        self._animate_alpha(0.0, 0.97, 180)
        # auto dismiss
        self.root.after(_LIFETIME_MS, self.dismiss)

        with _lock:
            _active.append(self)
        _restack()

    def dismiss(self):
        if not self._alive:
            return
        self._alive = False
        if self.root is None:
            return
        self._animate_alpha(0.97, 0.0, _FADE_MS, on_done=self._destroy)

    # ── internal ───────────────────────────────────────────────
    def _build(self):
        r = self.root
        r.configure(bg=BG_PANEL)

        outer = tk.Frame(r, bg=BORDER)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=BG_PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        bar = tk.Frame(inner, bg=self.color, width=4)
        bar.pack(side="left", fill="y")

        body = tk.Frame(inner, bg=BG_PANEL)
        body.pack(side="left", fill="both", expand=True, padx=12, pady=8)

        # Canvas-drawn glyph badge (circle + kind-specific mark)
        badge = tk.Canvas(body, width=22, height=22, bg=BG_PANEL,
                          highlightthickness=0, bd=0)
        badge.pack(side="left", padx=(0, 10))
        badge.create_oval(1, 1, 21, 21, fill=self.color, outline="")
        badge.create_oval(3, 3, 19, 19, fill=BG_PANEL, outline="")
        mark = {"success": "\u2713", "error": "\u2715",
                "warning": "!", "info": "i"}.get(self.kind, "i")
        badge.create_text(11, 11, text=mark, fill=self.color,
                          font=(FONT_LABEL[0], 10, "bold"))

        lbl = tk.Label(
            body, text=self.msg[:140],
            bg=BG_PANEL, fg=TEXT_PRI,
            font=FONT_LABEL, justify="left", anchor="w",
            wraplength=_TOAST_W - 60,
        )
        lbl.pack(side="left", fill="x", expand=True)

        close = tk.Label(body, text="×", bg=BG_PANEL, fg=TEXT_MUTED, font=(FONT_LABEL[0], 12))
        close.pack(side="right", padx=(4, 0))
        close.bind("<Enter>", lambda _e: close.configure(fg=TEXT_PRI))
        close.bind("<Leave>", lambda _e: close.configure(fg=TEXT_MUTED))
        close.bind("<Button-1>", lambda _e: self.dismiss())

    def _place(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - _TOAST_W - _MARGIN
        y = sh - _TOAST_H - _MARGIN
        self.root.geometry(f"{_TOAST_W}x{_TOAST_H}+{x}+{y}")

    def _animate_alpha(self, start: float, end: float, duration_ms: int, on_done=None):
        steps = max(1, duration_ms // 20)
        delta = (end - start) / steps

        def step(i: int, alpha: float):
            if self.root is None or not self.root.winfo_exists():
                return
            try:
                self.root.wm_attributes("-alpha", max(0.0, min(1.0, alpha)))
            except Exception:
                pass
            if i + 1 < steps:
                self.root.after(20, lambda: step(i + 1, alpha + delta))
            else:
                try:
                    self.root.wm_attributes("-alpha", end)
                except Exception:
                    pass
                if on_done:
                    on_done()

        step(0, start)

    def _destroy(self):
        try:
            if self.root:
                self.root.destroy()
        except Exception:
            pass
        with _lock:
            if self in _active:
                _active.remove(self)
        _restack()


def _restack():
    """Re-position all active toasts stacked from bottom-right upward."""
    with _lock:
        stack = list(_active)
    for idx, t in enumerate(stack):
        if t.root is None:
            continue
        try:
            sw = t.root.winfo_screenwidth()
            sh = t.root.winfo_screenheight()
            x = sw - _TOAST_W - _MARGIN
            y = sh - _TOAST_H - _MARGIN - (idx * (_TOAST_H + _GAP))
            t.root.geometry(f"{_TOAST_W}x{_TOAST_H}+{x}+{y}")
        except Exception:
            pass


# ── public API ────────────────────────────────────────────────
def show_info(msg: str):     Toast(msg, "info").show()
def show_success(msg: str):  Toast(msg, "success").show()
def show_warning(msg: str):  Toast(msg, "warning").show()
def show_error(msg: str):    Toast(msg, "error").show()
