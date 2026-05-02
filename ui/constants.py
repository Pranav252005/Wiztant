"""
Whiztant — shared UI design tokens.
Every tkinter surface imports from here. No hardcoded colors elsewhere.
Gaming Launcher aesthetic — dark, cinematic, minimal chrome.
"""

import ctypes
import sys

# ── Color tokens ──────────────────────────────────────────────
BG_DEEP     = "#08080d"
BG_PANEL    = "#111118"
BG_HOVER    = "#1a1a24"
BG_INPUT    = "#0d0d14"

ACCENT      = "#7c5af3"
ACCENT_DIM  = "#4a3580"
ACCENT_GLOW = "#7c5af340"

TEXT_PRI    = "#f0eeff"
TEXT_SEC    = "#888899"
TEXT_MUTED  = "#44445a"

BORDER      = "#1e1e2e"

SUCCESS     = "#22c55e"
WARNING     = "#f59e0b"
ERROR       = "#ef4444"

# ── Typography ────────────────────────────────────────────────
FONT_BODY   = ("Segoe UI", 13)
FONT_LABEL  = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 11)
FONT_TITLE  = ("Segoe UI", 14, "bold")
FONT_HERO   = ("Segoe UI", 24, "bold")

# ── Geometry / motion ─────────────────────────────────────────
RADIUS      = 12
ANIM_FAST   = 80
ANIM_SLOW   = 200


# ── Window helpers ────────────────────────────────────────────
def apply_window_style(win):
    """Frameless, dark, Windows-11 rounded corners when available."""
    try:
        win.overrideredirect(True)
    except Exception:
        pass
    try:
        win.configure(bg=BG_DEEP)
    except Exception:
        pass
    if sys.platform != "win32":
        return
    try:
        win.update_idletasks()
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(pref),
            ctypes.sizeof(pref),
        )
    except Exception:
        pass


def center_window(win, w: int, h: int) -> None:
    """Center a frameless window on the current screen."""
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        win.geometry(f"{w}x{h}")


def bind_drag(widget, window):
    """Wire button-1 + motion on `widget` to drag `window`."""
    state = {"dx": 0, "dy": 0}

    def start(ev):
        state["dx"] = ev.x_root - window.winfo_x()
        state["dy"] = ev.y_root - window.winfo_y()

    def move(ev):
        window.geometry(f"+{ev.x_root - state['dx']}+{ev.y_root - state['dy']}")

    widget.bind("<ButtonPress-1>", start)
    widget.bind("<B1-Motion>", move)


def accent_button(parent, text: str, command, width: int = 0, height: int = 36):
    """Flat violet accent button. Returns the tk.Button."""
    import tkinter as tk
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=ACCENT,
        fg=TEXT_PRI,
        activebackground="#9374f5",
        activeforeground=TEXT_PRI,
        relief="flat",
        bd=0,
        cursor="hand2",
        font=(FONT_BODY[0], FONT_BODY[1], "bold"),
    )
    if width:
        btn.configure(width=width)
    btn.configure(pady=max(0, (height - 20) // 2))
    btn.bind("<Enter>", lambda _e: btn.configure(bg="#9374f5"))
    btn.bind("<Leave>", lambda _e: btn.configure(bg=ACCENT))
    return btn


def ghost_button(parent, text: str, command, fg=TEXT_MUTED):
    """Borderless hover-brighten icon/text button."""
    import tkinter as tk
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=BG_PANEL,
        fg=fg,
        activebackground=BG_HOVER,
        activeforeground=TEXT_PRI,
        relief="flat",
        bd=0,
        cursor="hand2",
        font=FONT_LABEL,
    )
    btn.bind("<Enter>", lambda _e: btn.configure(fg=TEXT_PRI, bg=BG_HOVER))
    btn.bind("<Leave>", lambda _e: btn.configure(fg=fg, bg=BG_PANEL))
    return btn


def hline(parent, color=BORDER, pady=0):
    """1px horizontal divider frame."""
    import tkinter as tk
    f = tk.Frame(parent, bg=color, height=1)
    f.pack(fill="x", pady=pady)
    return f
