"""
React Overlay Runner
Runs in a separate process to satisfy pywebview's main thread requirement.
Loads built React app from local dist/ folder — no dev server needed.
Monitors a command file for toggle/hide/show commands.
"""

import os
import time
import webview
import threading

WIN_W = 420
WIN_H = 580

# Path to the built React app
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIST_CANDIDATES = (
    os.path.join(_ROOT, "ui", os.getenv("WHIZTANT_OVERLAY_UI", "wiztant-clui"), "dist", "overlay.html"),
    os.path.join(_ROOT, "ui", os.getenv("WHIZTANT_OVERLAY_UI", "wiztant-clui"), "dist", "index.html"),
)
DIST_INDEX = next((path for path in _DIST_CANDIDATES if os.path.exists(path)), _DIST_CANDIDATES[0])

window = None
visible = False


def position_window():
    """Position window at bottom-right corner with margin."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        
        x = screen_w - WIN_W - 20
        y = screen_h - WIN_H - 60
        
        window.move(x, y)
    except Exception as e:
        print(f"[OverlayRunner] Position error: {e}")


def monitor_commands():
    """Monitor command file for toggle/hide/show commands."""
    global visible
    
    cmd_file = os.path.join(os.path.dirname(__file__), ".overlay_cmd")
    last_mtime = 0
    
    while True:
        try:
            if os.path.exists(cmd_file):
                mtime = os.path.getmtime(cmd_file)
                if mtime > last_mtime:
                    last_mtime = mtime
                    with open(cmd_file, "r") as f:
                        cmd = f.read().strip()
                    
                    if cmd == "toggle":
                        if visible:
                            window.hide()
                            visible = False
                        else:
                            position_window()
                            window.show()
                            visible = True
                    elif cmd == "hide":
                        if visible:
                            window.hide()
                            visible = False
                    elif cmd == "show":
                        if not visible:
                            position_window()
                            window.show()
                            visible = True
        except Exception as e:
            print(f"[OverlayRunner] Command monitor error: {e}")
        
        time.sleep(0.1)


if __name__ == "__main__":
    if not os.path.exists(DIST_INDEX):
        print(f"[OverlayRunner] ERROR: Built overlay not found at {DIST_INDEX}")
        print("[OverlayRunner] Run 'npm run build' in ui/wiztant-clui first.")
        exit(1)

    # Start command monitor in background thread
    monitor_thread = threading.Thread(target=monitor_commands, daemon=True)
    monitor_thread.start()
    
    # Load built React app from local file — no localhost needed
    url = f"file:///{DIST_INDEX.replace(os.sep, '/')}"
    
    window = webview.create_window(
        'Whiztant',
        url,
        width=WIN_W,
        height=WIN_H,
        resizable=False,
        frameless=True,
        on_top=True,
        hidden=True,
    )
    
    webview.start()
