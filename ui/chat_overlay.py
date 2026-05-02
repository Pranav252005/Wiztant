"""
ui/chat_overlay.py — Tune overlay window (tkinter)

Bottom-center positioned, always-on-top, borderless, semi-transparent overlay.
Supports live transcript (Tasks) and chat modes.

Keyboard shortcuts (overlay focused):
  Enter        — send message
  Escape       — hide overlay
  Ctrl+Space   — toggle overlay
  Tab          — cycle focus (entry ↔ message area)
  Shift+Tab    — reverse cycle
"""

import threading
import tkinter as tk
from tkinter import ttk


class TasksTab:
    """Tasks tab with live transcript display."""

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # Live transcript frame
        self.live_frame = tk.Frame(parent_frame, bg="#1C0A0A")
        self.live_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Live text (what user is saying)
        self.live_label = tk.Label(
            self.live_frame,
            text="🎤 Ready for voice input",
            wraplength=300,
            fg="#9B6E5C",
            bg="#1C0A0A",
            font=("DM Sans", 11),
            justify=tk.LEFT,
            anchor="w",
        )
        self.live_label.pack(fill=tk.BOTH, expand=True, pady=5)

        # Confidence bar
        self.confidence_var = tk.DoubleVar()
        self.confidence_bar = ttk.Progressbar(
            self.live_frame,
            variable=self.confidence_var,
            length=300,
            mode="determinate",
            maximum=100,
        )
        self.confidence_bar.pack(fill=tk.X, pady=5)

        # Refined text label
        self.refined_label = tk.Label(
            self.live_frame,
            text="",
            wraplength=300,
            fg="#C4956A",
            bg="#1C0A0A",
            font=("DM Sans", 10, "bold"),
            justify=tk.LEFT,
            anchor="w",
        )
        self.refined_label.pack(fill=tk.BOTH, expand=True, pady=5)

        # Changes label
        self.changes_label = tk.Label(
            self.live_frame,
            text="",
            wraplength=300,
            fg="#7B7B7B",
            bg="#1C0A0A",
            font=("DM Sans", 8, "italic"),
            justify=tk.LEFT,
            anchor="w",
        )
        self.changes_label.pack(fill=tk.BOTH, expand=True, pady=2)

    def update_live_partial(self, text: str, confidence: float):
        """Show partial transcript while user speaks."""
        self.live_label.config(text=f"✎ {text}", fg="#9B6E5C")
        self.confidence_var.set(confidence * 100)
        self.refined_label.config(text="")
        self.changes_label.config(text="")

    def update_refined(self, refined: str, changes: list):
        """Show refined transcript."""
        self.refined_label.config(text=f"✓ {refined}", fg="#C4956A")

        if changes:
            changes_text = " | ".join(str(c) for c in changes)
            self.changes_label.config(text=f"→ {changes_text}", fg="#7B7B7B")
        else:
            self.changes_label.config(text="", fg="#5B5B5B")

    def reset(self):
        """Clear displays."""
        self.live_label.config(text="🎤 Ready for voice input")
        self.refined_label.config(text="")
        self.changes_label.config(text="")
        self.confidence_var.set(0)


class ChatTab:
    """Chat tab with scrollable message history and input field."""

    _MSG_WRAP = 270

    def __init__(self, parent_frame, on_send=None):
        self.parent = parent_frame
        self.on_send = on_send

        self.msg_container = tk.Frame(parent_frame, bg="#1C0A0A")
        self.msg_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        self.msg_canvas = tk.Canvas(self.msg_container, bg="#1C0A0A", highlightthickness=0)
        self.msg_scrollbar = tk.Scrollbar(self.msg_container, orient="vertical", command=self.msg_canvas.yview)
        self.msg_scrollable = tk.Frame(self.msg_canvas, bg="#1C0A0A")

        self.msg_scrollable.bind("<Configure>", lambda _e: self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox("all")))
        self.msg_canvas_window = self.msg_canvas.create_window((0, 0), window=self.msg_scrollable, anchor="nw", tags="inner_frame")
        self.msg_canvas.bind("<Configure>", self._on_canvas_configure)
        self.msg_canvas.configure(yscrollcommand=self.msg_scrollbar.set)
        self.msg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.msg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.msg_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.msg_scrollable.bind("<MouseWheel>", self._on_mousewheel)

        self.input_frame = tk.Frame(parent_frame, bg="#1C0A0A", padx=8, pady=(4, 8))
        self.input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.entry = tk.Entry(
            self.input_frame,
            bg="#2B1010",
            fg="#FAF6F1",
            insertbackground="#C4956A",
            font=("DM Sans", 11),
            relief=tk.FLAT,
            highlightbackground="#1C0A0A",
            highlightcolor="#C4956A",
            highlightthickness=1,
        )
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.entry.bind("<Return>", self._on_send)

        self.send_btn = tk.Label(
            self.input_frame,
            text="➤",
            fg="#C4956A",
            bg="#1C0A0A",
            font=("DM Sans", 12),
            cursor="hand2",
        )
        self.send_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self.send_btn.bind("<Button-1>", self._on_send)

    def _on_canvas_configure(self, event):
        self.msg_canvas.itemconfig(self.msg_canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.msg_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_send(self, _event=None):
        text = self.entry.get().strip()
        if text and self.on_send:
            self._flash_send_btn()
            self.on_send(text)
            self.entry.delete(0, tk.END)

    def _flash_send_btn(self):
        orig_bg = self.send_btn.cget("bg")
        self.send_btn.config(bg="#2B1010")
        self.parent.after(120, lambda: self.send_btn.config(bg=orig_bg))

    def _animate_message_in(self, bubble_frame):
        # Entrance flash: briefly brighten border color then settle
        bubble_frame.config(bg="#3B2020")
        self.parent.after(80, lambda: bubble_frame.config(bg="#2B1010"))

    def add_message(self, role, text):
        is_user = role == "user"
        is_ai = role == "assistant"
        outer = tk.Frame(self.msg_scrollable, bg="#1C0A0A")
        outer.pack(fill=tk.X, pady=4, padx=4)
        if is_user:
            outer.pack_configure(anchor="e")
        bubble_bg = "#2B1010"
        bubble = tk.Frame(outer, bg=bubble_bg, padx=8, pady=6)
        if is_user:
            bubble.pack(side=tk.RIGHT)
        elif is_ai:
            border = tk.Frame(outer, bg="#C4956A", width=2)
            border.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
            bubble.pack(side=tk.LEFT)
        else:
            bubble.pack(side=tk.LEFT)
        label = tk.Label(
            bubble,
            text=text,
            wraplength=self._MSG_WRAP,
            fg="#FAF6F1",
            bg=bubble_bg,
            font=("DM Sans", 10),
            justify=tk.LEFT,
            anchor="w",
        )
        label.pack(fill=tk.BOTH)
        self._animate_message_in(bubble)
        self.msg_canvas.update_idletasks()
        self.msg_canvas.yview_moveto(1.0)

    def show_typing_dots(self):
        if getattr(self, "_typing_dots_frame", None) and self._typing_dots_frame.winfo_exists():
            return
        self._typing_dots_frame = tk.Frame(self.msg_scrollable, bg="#1C0A0A")
        self._typing_dots_frame.pack(fill=tk.X, pady=4, padx=4, anchor="w")
        border = tk.Frame(self._typing_dots_frame, bg="#C4956A", width=2)
        border.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        dots_box = tk.Frame(self._typing_dots_frame, bg="#2B1010", padx=8, pady=6)
        dots_box.pack(side=tk.LEFT)
        self._typing_dots = []
        for i in range(3):
            d = tk.Label(dots_box, text="●", fg="#C4956A", bg="#2B1010", font=("DM Sans", 6))
            d.pack(side=tk.LEFT, padx=2)
            self._typing_dots.append(d)
        self._typing_dots_idx = 0
        self._animate_typing_dots()
        self.msg_canvas.update_idletasks()
        self.msg_canvas.yview_moveto(1.0)

    def _animate_typing_dots(self):
        if not getattr(self, "_typing_dots_frame", None) or not self._typing_dots_frame.winfo_exists():
            return
        for i, d in enumerate(self._typing_dots):
            if i == self._typing_dots_idx:
                d.config(fg="#FAF6F1")
            else:
                d.config(fg="#7B7B7B")
        self._typing_dots_idx = (self._typing_dots_idx + 1) % 3
        self.parent.after(350, self._animate_typing_dots)

    def hide_typing_dots(self):
        if getattr(self, "_typing_dots_frame", None) and self._typing_dots_frame.winfo_exists():
            self._typing_dots_frame.destroy()
            self._typing_dots_frame = None
            self._typing_dots = []

    def clear_messages(self):
        for w in self.msg_scrollable.winfo_children():
            w.destroy()

    def focus_entry(self):
        self.entry.focus_set()


class ChatOverlay:
    """Standalone tkinter overlay window."""

    OVERLAY_W = 340
    OVERLAY_H = 420
    BG = "#1C0A0A"

    def __init__(self, on_send=None):
        try:
            existing = tk._default_root
            if existing and existing.winfo_exists():
                self.root = tk.Toplevel(existing)
            else:
                self.root = tk.Tk()
        except Exception:
            self.root = tk.Tk()

        self.root.withdraw()
        self.root.title("Wiztant Tune")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.88)
        try:
            self.root.attributes("-skip-taskbar", True)
        except tk.TclError:
            pass

        self._position_bottom_center()
        self.root.configure(bg=self.BG)

        self._visible = False
        self._on_send = on_send
        self._build_ui()

        self.root.bind("<Escape>", lambda _e: self.hide())
        self.root.bind("<Control-space>", lambda _e: self.toggle())
        self.root.bind("<Tab>", self._on_tab)
        self.root.bind("<Shift-Tab>", self._on_shift_tab)

    def _position_bottom_center(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - self.OVERLAY_W) // 2
        y = sh - self.OVERLAY_H - 50
        self.root.geometry(f"{self.OVERLAY_W}x{self.OVERLAY_H}+{x}+{y}")

    def _build_ui(self):
        self.tab_bar = tk.Frame(self.root, bg=self.BG, height=32)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP)
        self.tab_bar.pack_propagate(False)

        self._tabs = {}
        self._add_tab_btn("Tune", self._show_chat)
        self._add_tab_btn("Tasks", self._show_tasks)

        self.content = tk.Frame(self.root, bg=self.BG)
        self.content.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = tk.Frame(self.content, bg=self.BG)
        self.chat_tab = ChatTab(self.chat_frame, on_send=self._on_send)

        self.tasks_frame = tk.Frame(self.content, bg=self.BG)
        self.tasks_tab = TasksTab(self.tasks_frame)

        self.status_frame = tk.Frame(self.root, bg=self.BG, height=20)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_frame,
            text="",
            fg="#7B7B7B",
            bg=self.BG,
            font=("DM Sans", 8),
        )
        self.status_label.pack(side=tk.LEFT, padx=8)

        self._show_chat()

    def _add_tab_btn(self, name, command):
        btn = tk.Label(
            self.tab_bar,
            text=name,
            fg="#9B6E5C",
            bg=self.BG,
            font=("DM Sans", 10, "bold"),
            cursor="hand2",
            padx=12,
            pady=4,
        )
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda _e: command())
        self._tabs[name] = btn

    def _show_chat(self):
        self.tasks_frame.pack_forget()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        self._set_active_tab("Tune")

    def _show_tasks(self):
        self.chat_frame.pack_forget()
        self.tasks_frame.pack(fill=tk.BOTH, expand=True)
        self._set_active_tab("Tasks")

    def _set_active_tab(self, name):
        for n, btn in self._tabs.items():
            if n == name:
                btn.config(fg="#FAF6F1", bg="#2B1010")
            else:
                btn.config(fg="#9B6E5C", bg=self.BG)

    def _on_tab(self, _event):
        focused = self.root.focus_get()
        target = self.chat_tab.msg_canvas if focused == self.chat_tab.entry else self.chat_tab.entry
        target.focus_set()
        return "break"

    def _on_shift_tab(self, _event):
        focused = self.root.focus_get()
        target = self.chat_tab.msg_canvas if focused == self.chat_tab.entry else self.chat_tab.entry
        target.focus_set()
        return "break"

    def _safe(self, fn, *args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            fn(*args, **kwargs)
        else:
            self.root.after(0, lambda: fn(*args, **kwargs))

    def show(self):
        self._safe(self._do_show)

    def _do_show(self):
        if not self._visible:
            self._position_bottom_center()
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self._visible = True
            self._animate_show()
            self.chat_tab.focus_entry()

    def _animate_show(self, step=0):
        # Fade-in: 0 -> 0.88 over ~240ms (12 steps × 20ms)
        if step == 0:
            self.root.attributes("-alpha", 0.0)
        alpha = min(0.88, step * 0.88 / 10)
        self.root.attributes("-alpha", alpha)
        if alpha < 0.88:
            self.root.after(20, lambda: self._animate_show(step + 1))

    def hide(self):
        self._safe(self._do_hide)

    def _do_hide(self):
        if self._visible:
            self.root.withdraw()
            self._visible = False

    def toggle(self):
        self._safe(self._do_toggle)

    def _do_toggle(self):
        if self._visible:
            self._do_hide()
        else:
            self._do_show()

    def is_visible(self):
        return self._visible

    def add_message(self, role, text):
        self._safe(self.chat_tab.add_message, role, text)

    def clear_messages(self):
        self._safe(self.chat_tab.clear_messages)

    def set_listening(self):
        self._safe(self._set_status, "● Listening", "#9B6E5C")

    def set_thinking(self):
        self._safe(self._set_status, "◐ Thinking", "#C4956A")
        self._safe(self.chat_tab.show_typing_dots)

    def set_idle(self):
        self._safe(self._set_status, "", "#7B7B7B")
        self._safe(self.chat_tab.hide_typing_dots)

    def _set_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def update_live_partial(self, text, confidence):
        self._safe(self.tasks_tab.update_live_partial, text, confidence)

    def update_refined(self, refined, changes):
        self._safe(self.tasks_tab.update_refined, refined, changes)

    def reset(self):
        self._safe(self.tasks_tab.reset)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    overlay = ChatOverlay(on_send=lambda t: print(f"Send: {t}"))
    overlay.show()
    overlay.run()
