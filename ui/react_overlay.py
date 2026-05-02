"""
Whiztant React Overlay Manager
Displays the React overlay as an Electron desktop app (frameless, always-on-top).
Falls back to pywebview if Electron/npm is not available.
Also starts the WebSocket bridge for real-time Python ↔ Overlay IPC.
"""

import subprocess
import sys
import os
import shutil
import time
import urllib.request
import urllib.error
import threading

_overlay_process = None
_ws_bridge_started = False
_ws_bridge_lock = threading.Lock()
_dev_server_available = None
_OVERLAY_POST_START_DELAY = 1.0  # Electron needs ~0.5-1s; stale-cmd fix makes this a soft target

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OVERLAY_NAME = os.getenv("WHIZTANT_OVERLAY_UI", "whiztant-overlay")
_OVERLAY_DIR = os.path.join(_ROOT, "ui", _OVERLAY_NAME)

# Detect build system: electron-vite (whiztant-overlay) produces `out/`,
# plain vite (wiztant-clui) produces `dist/`. Everything downstream branches
# on this one boolean so the launcher works for either layout.
_IS_ELECTRON_VITE = os.path.exists(
    os.path.join(_OVERLAY_DIR, "electron.vite.config.ts")
) or os.path.exists(
    os.path.join(_OVERLAY_DIR, "electron.vite.config.js")
)

_DEV_SERVER_URL = "http://127.0.0.1:5173/" if _IS_ELECTRON_VITE else "http://127.0.0.1:5174/"

_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".overlay_pid")
_COMMAND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".overlay_cmd")
_LOG_FILE = os.path.join(_ROOT, "data", "overlay.log")

# Ensure data dir exists for logs
os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)


def _log(msg: str):
    """Append a timestamped line to overlay.log and print to stdout."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _overlay_dist_candidates():
    if _IS_ELECTRON_VITE:
        # electron-vite compiles main/preload to out/. The first existing path
        # is treated as the "build is present" marker.
        return (
            os.path.join(_OVERLAY_DIR, "out", "main", "index.js"),
            os.path.join(_OVERLAY_DIR, "out", "main", "index.cjs"),
        )
    return (
        os.path.join(_OVERLAY_DIR, "dist", "overlay.html"),
        os.path.join(_OVERLAY_DIR, "dist", "index.html"),
    )


def _latest_mtime(paths):
    latest = 0.0
    for target in paths:
        if not os.path.exists(target):
            continue
        if os.path.isfile(target):
            latest = max(latest, os.path.getmtime(target))
            continue
        for root, dirs, files in os.walk(target):
            dirs[:] = [name for name in dirs if name not in {"node_modules", "dist", ".git"}]
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    latest = max(latest, os.path.getmtime(file_path))
                except OSError:
                    pass
    return latest


def _is_npm_install_needed() -> bool:
    """Check if .bin/ symlinks are missing or broken (common after cross-platform copy)."""
    bin_dir = os.path.join(_OVERLAY_DIR, "node_modules", ".bin")
    if not os.path.isdir(bin_dir):
        return True
    # Check a few key binaries
    for name in ("electron", "electron-vite"):
        path = os.path.join(bin_dir, name)
        if os.name == "nt":
            path += ".cmd"
        if not os.path.exists(path):
            return True
    return False


def _run_npm_install():
    """Run npm install to fix broken symlinks. Blocking."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        _log("[ReactOverlay] npm not found, cannot install dependencies")
        return False
    _log("[ReactOverlay] Running npm install...")
    try:
        result = subprocess.run(
            [npm, "install"],
            cwd=_OVERLAY_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            _log(f"[ReactOverlay] npm install failed (exit {result.returncode}):")
            for line in (result.stdout or "").splitlines()[-20:]:
                _log(f"  {line}")
            return False
        _log("[ReactOverlay] npm install succeeded")
        return True
    except Exception as e:
        _log(f"[ReactOverlay] npm install exception: {e}")
        return False


def _ensure_overlay_build_current(npx, force: bool = False):
    """Ensure dist/ exists. mtime staleness is only a reason to rebuild when
    explicitly ``force``-ed (e.g. background refresh) — otherwise a present
    dist/ is treated as good enough, so app startup stays under a second.
    """
    dist_candidates = _overlay_dist_candidates()
    dist_files = [path for path in dist_candidates if os.path.exists(path)]

    if dist_files and not force:
        return True

    if not force:
        # dist missing → we must build (blocking) before launching Electron.
        source_mtime = 0.0
        dist_mtime = 0.0
    else:
        source_paths = [
            os.path.join(_OVERLAY_DIR, "src"),
            os.path.join(_OVERLAY_DIR, "electron"),
            os.path.join(_OVERLAY_DIR, "index.html"),
            os.path.join(_OVERLAY_DIR, "overlay.html"),
            os.path.join(_OVERLAY_DIR, "package.json"),
            os.path.join(_OVERLAY_DIR, "tsconfig.app.json"),
            os.path.join(_OVERLAY_DIR, "vite.config.ts"),
            os.path.join(_OVERLAY_DIR, "vite.config.js"),
            os.path.join(_OVERLAY_DIR, "electron.vite.config.ts"),
            os.path.join(_OVERLAY_DIR, "electron.vite.config.js"),
            os.path.join(_OVERLAY_DIR, "tsconfig.json"),
            os.path.join(_OVERLAY_DIR, "tsconfig.node.json"),
            os.path.join(_OVERLAY_DIR, "tsconfig.web.json"),
        ]
        source_mtime = _latest_mtime(source_paths)
        dist_mtime = max((os.path.getmtime(path) for path in dist_files), default=0.0)
        if dist_mtime >= source_mtime and dist_files:
            return True

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        return False

    # Fix broken node_modules first
    if _is_npm_install_needed():
        if not _run_npm_install():
            return False

    _log("[ReactOverlay] Building overlay...")
    try:
        result = subprocess.run(
            [npm, "run", "build"],
            cwd=_OVERLAY_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            _log(f"[ReactOverlay] Overlay build failed (exit {result.returncode}):")
            for line in (result.stdout or "").splitlines()[-30:]:
                _log(f"  {line}")
            return False
        _log("[ReactOverlay] Overlay build succeeded")
    except Exception as e:
        _log(f"[ReactOverlay] Overlay build exception: {e}")
        return False

    return any(os.path.exists(path) for path in dist_candidates)


def _has_overlay_dev_server():
    global _dev_server_available
    if _dev_server_available is None:
        _dev_server_available = _wait_for_overlay_url(_DEV_SERVER_URL, timeout=0.35)
    return _dev_server_available


def _overlay_electron_entry():
    """
    Pick the Electron entry file.
    - electron-vite layout (whiztant-overlay): package.json `main` points at
      `./out/main/index.js`, so we pass "." and let Electron resolve it.
    - Legacy (wiztant-clui): a hand-written `electron/overlay.cjs` is present.
    """
    if _IS_ELECTRON_VITE:
        return "."
    overlay_entry = os.path.join(_OVERLAY_DIR, "electron", "overlay.cjs")
    return overlay_entry if os.path.exists(overlay_entry) else "."


def _wait_for_overlay_url(url, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(0.25)
        except Exception:
            time.sleep(0.25)
    return False


def _ensure_ws_bridge():
    """Start the WebSocket bridge if not already running."""
    global _ws_bridge_started
    if _ws_bridge_started:
        return
    with _ws_bridge_lock:
        if _ws_bridge_started:
            return
        try:
            from core.ws_bridge import start_ws_bridge
            start_ws_bridge()
            _ws_bridge_started = True
        except Exception as e:
            print(f"[ReactOverlay] WebSocket bridge failed: {e}")


def _electron_flags_linux() -> list:
    """Return Electron CLI flags needed for reliable Linux startup."""
    flags = ["--no-sandbox", "--disable-setuid-sandbox"]
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        # Native Wayland with frameless always-on-top overlay windows can spin at
        # 100% CPU on some compositors (Electron 33 + KDE Plasma). XWayland (X11)
        # is stable and well-tested for this use-case, so we prefer it.
        flags.append("--ozone-platform=x11")
    elif session == "x11":
        flags.append("--ozone-platform=x11")
    else:
        # Unknown or unset — let Electron auto-detect, but disable GPU
        # sandbox issues that are common on headless / VM setups.
        flags.append("--disable-gpu-sandbox")
    return flags


def _start_electron():
    """Try to start the Electron overlay."""
    global _overlay_process

    if _overlay_process is not None and _overlay_process.poll() is None:
        return True  # Already running

    # Platform-specific Electron binary paths
    if os.name == "nt":
        electron_exe = os.path.join(_OVERLAY_DIR, "node_modules", "electron", "dist", "electron.exe")
        electron_cmd = os.path.join(_OVERLAY_DIR, "node_modules", ".bin", "electron.cmd")
    else:
        electron_exe = os.path.join(_OVERLAY_DIR, "node_modules", "electron", "dist", "electron")
        electron_cmd = os.path.join(_OVERLAY_DIR, "node_modules", ".bin", "electron")

    if os.path.exists(electron_exe):
        launcher = [electron_exe]
    elif os.path.exists(electron_cmd):
        launcher = [electron_cmd]
    else:
        npx = shutil.which("npx")
        if not npx:
            _log("[ReactOverlay] No electron binary or npx found")
            return False
        launcher = [npx, "electron"]

    overlay_entry = _overlay_electron_entry()
    using_dev = _has_overlay_dev_server()

    if not using_dev:
        dist_files = [p for p in _overlay_dist_candidates() if os.path.exists(p)]
        if not dist_files:
            # No build at all — must block and build before we can launch.
            npx = shutil.which("npx")
            if not npx or not _ensure_overlay_build_current(npx):
                _log("[ReactOverlay] Build missing and build failed — overlay cannot start")
                return False
            dist_files = [p for p in _overlay_dist_candidates() if os.path.exists(p)]
            if not dist_files:
                _log("[ReactOverlay] Build still missing after rebuild attempt")
                return False
        else:
            # Build exists — launch immediately and rebuild stale assets in the background
            # so the next restart picks up the latest code without blocking the hot path.
            npx = shutil.which("npx")
            if npx:
                threading.Thread(
                    target=_ensure_overlay_build_current,
                    args=(npx,),
                    kwargs={"force": True},
                    daemon=True,
                ).start()

    if (
        overlay_entry == "."
        and not using_dev
        and not any(os.path.exists(p) for p in _overlay_dist_candidates())
    ):
        return False

    try:
        env = os.environ.copy()
        # Pass the absolute COMMAND_FILE path so Electron can find it
        # regardless of how it resolves its own CWD / appPath.
        env.setdefault("WHIZTANT_OVERLAY_CMD", _COMMAND_FILE)
        if using_dev:
            env.setdefault("VITE_DEV_SERVER", "1")
            env.setdefault("WHIZTANT_CLUI_OVERLAY_URL", _DEV_SERVER_URL)
            env.setdefault("WHIZTANT_OVERLAY_URL", _DEV_SERVER_URL)
            # electron-vite reads ELECTRON_RENDERER_URL to know the Vite dev
            # server address. Required for our utils.ts to load from the dev
            # server instead of the prod out/renderer files.
            env.setdefault("ELECTRON_RENDERER_URL", _DEV_SERVER_URL.rstrip("/"))

        cmd = launcher.copy()
        if os.name != "nt":
            cmd.extend(_electron_flags_linux())
        cmd.append(overlay_entry)

        # Open log file for Electron stderr/stdout so we can diagnose crashes
        log_fp = open(_LOG_FILE, "a", encoding="utf-8")
        _overlay_process = subprocess.Popen(
            cmd,
            cwd=_OVERLAY_DIR,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            env=env,
        )
        _write_pid_file(_overlay_process)
        _log(f"[ReactOverlay] Electron overlay started (PID {_overlay_process.pid})")

        # Quick health check: if process dies within 3s, log the tail of overlay.log
        time.sleep(0.5)
        if _overlay_process.poll() is not None:
            _log(f"[ReactOverlay] Electron exited immediately (code {_overlay_process.poll()})")
            try:
                with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    _log("[ReactOverlay] Last Electron log lines:")
                    for line in lines[-15:]:
                        _log(f"  {line.rstrip()}")
            except Exception:
                pass
            return False
        return True
    except Exception as e:
        _log(f"[ReactOverlay] Electron start failed: {e}")
        return False


def _start_pywebview_fallback():
    """Fallback: start the overlay via pywebview in a separate process."""
    global _overlay_process

    if _overlay_process is not None and _overlay_process.poll() is None:
        return

    script_path = os.path.join(os.path.dirname(__file__), "react_overlay_runner.py")

    try:
        _overlay_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[ReactOverlay] Pywebview overlay started (fallback)")
    except Exception as e:
        print(f"[ReactOverlay] Pywebview fallback failed: {e}")


def _is_process_alive():
    if _overlay_process is not None and _overlay_process.poll() is None:
        return True
    tracked_pid = _tracked_overlay_pid()
    return _pid_is_alive(tracked_pid)


def _kill_stale_overlay():
    """Kill any previously tracked Electron overlay process (safe — verifies PID before kill)."""
    if not os.path.exists(_PID_FILE):
        return
    try:
        with open(_PID_FILE) as f:
            pid = f.read().strip()
        if not pid:
            return

        if os.name == "nt":
            # Windows: Use fast tasklist /FI instead of slow wmic to verify the PID.
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=2,
            )
            out = result.stdout.lower()
            if "electron" in out:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                _log(f"[ReactOverlay] Killed stale overlay process (PID {pid})")
                time.sleep(0.15)
        else:
            # Linux/macOS: Use ps to check and kill the process and any children
            try:
                # Check if it's a zombie first
                is_zombie = False
                try:
                    with open(f"/proc/{pid}/stat") as f:
                        stat = f.read().strip()
                        rparen = stat.rfind(')')
                        if rparen != -1 and rparen + 2 < len(stat):
                            is_zombie = stat[rparen + 2] == 'Z'
                except (FileNotFoundError, PermissionError):
                    pass  # Process already gone

                if is_zombie:
                    _log(f"[ReactOverlay] Reaping zombie overlay (PID {pid})")
                    try:
                        os.waitpid(int(pid), os.WNOHANG)
                    except (ChildProcessError, OSError):
                        pass
                    return

                result = subprocess.run(
                    ["ps", "-p", pid, "-o", "comm="],
                    capture_output=True, text=True, timeout=2,
                )
                out = result.stdout.lower()
                if "electron" in out or "electron" in result.stderr.lower():
                    # Try SIGTERM first, then SIGKILL after a short grace
                    os.kill(int(pid), 15)
                    _log(f"[ReactOverlay] Killed stale overlay process (PID {pid})")
                    time.sleep(0.3)
                    try:
                        os.kill(int(pid), 0)
                        # Still alive — force kill
                        os.kill(int(pid), 9)
                        _log(f"[ReactOverlay] Force-killed stale overlay (PID {pid})")
                    except (ProcessLookupError, OSError):
                        pass
            except (ProcessLookupError, ValueError):
                pass  # Process already gone
    except Exception as e:
        _log(f"[ReactOverlay] Could not kill stale overlay: {e}")
    finally:
        try:
            os.unlink(_PID_FILE)
        except Exception:
            pass


def _write_pid_file(proc):
    try:
        with open(_PID_FILE, "w") as f:
            f.write(str(proc.pid))
    except Exception:
        pass


def _electron_is_available():
    """True if the local electron binary or npx is present on this machine."""
    if os.name == "nt":
        electron_exe = os.path.join(_OVERLAY_DIR, "node_modules", "electron", "dist", "electron.exe")
        electron_cmd = os.path.join(_OVERLAY_DIR, "node_modules", ".bin", "electron.cmd")
    else:
        electron_exe = os.path.join(_OVERLAY_DIR, "node_modules", "electron", "dist", "electron")
        electron_cmd = os.path.join(_OVERLAY_DIR, "node_modules", ".bin", "electron")
    return os.path.exists(electron_exe) or os.path.exists(electron_cmd) or shutil.which("npx") is not None


def _tracked_overlay_pid():
    try:
        if not os.path.exists(_PID_FILE):
            return None
        with open(_PID_FILE) as f:
            pid = f.read().strip()
        return pid or None
    except Exception:
        return None


def _pid_is_alive(pid):
    if not pid:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            output = result.stdout.strip().lower()
            return bool(output) and "no tasks are running" not in output
        # On Linux/macOS: check /proc/{pid}/stat for zombie state
        try:
            with open(f"/proc/{pid}/stat") as f:
                stat = f.read().strip()
                # stat format: pid (comm) state ... state is the char after the last ')'
                rparen = stat.rfind(')')
                if rparen != -1 and rparen + 2 < len(stat):
                    state = stat[rparen + 2]
                    if state == 'Z':
                        return False  # Zombie — dead but not reaped
        except (FileNotFoundError, PermissionError):
            return False  # /proc entry gone = process dead
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True   # Process exists, we just can't signal it
    except (ProcessLookupError, OSError):
        return False  # Process genuinely gone
    except Exception:
        return False


def _kill_all_overlay_electrons():
    """Kill every Electron process that belongs to this overlay app (Linux/macOS)."""
    if os.name == "nt":
        return
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"electron.*{_OVERLAY_DIR.replace(os.path.expanduser('~'), '~')}"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            # Try a broader pattern if the specific one fails
            result = subprocess.run(
                ["pgrep", "-f", "whiztant-overlay.*electron"],
                capture_output=True, text=True, timeout=3,
            )
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line or not line.isdigit():
                continue
            try:
                pid = int(line)
                # Don't kill ourselves if we're somehow matched
                if pid == os.getpid():
                    continue
                os.kill(pid, 15)
                _log(f"[ReactOverlay] SIGTERM stale Electron (PID {pid})")
            except (ProcessLookupError, OSError, ValueError):
                pass
        time.sleep(0.3)
        # Second pass: SIGKILL any survivors
        result2 = subprocess.run(
            ["pgrep", "-f", f"electron.*{_OVERLAY_DIR.replace(os.path.expanduser('~'), '~')}"],
            capture_output=True, text=True, timeout=3,
        )
        if result2.returncode != 0:
            result2 = subprocess.run(
                ["pgrep", "-f", "whiztant-overlay.*electron"],
                capture_output=True, text=True, timeout=3,
            )
        for line in result2.stdout.strip().splitlines():
            line = line.strip()
            if not line or not line.isdigit():
                continue
            try:
                pid = int(line)
                if pid == os.getpid():
                    continue
                os.kill(pid, 9)
                _log(f"[ReactOverlay] SIGKILL stale Electron (PID {pid})")
            except (ProcessLookupError, OSError, ValueError):
                pass
    except Exception as e:
        _log(f"[ReactOverlay] Process cleanup warning: {e}")


def _start_overlay_process():
    """Start the overlay — Electron first, pywebview fallback only if Electron is absent."""
    _ensure_ws_bridge()

    if _is_process_alive():
        return False  # Already running, didn't just start

    if _electron_is_available():
        # Kill any previous overlay from a prior Python session before starting fresh.
        _kill_stale_overlay()
        _kill_all_overlay_electrons()
        ok = _start_electron()
        if not ok:
            _log("[ReactOverlay] Electron failed to start, trying pywebview fallback")
            _start_pywebview_fallback()
    else:
        _log("[ReactOverlay] Electron not available, using pywebview fallback")
        if not _start_electron():
            _start_pywebview_fallback()

    return True  # Just started


def ensure_react_overlay_running():
    if not _is_process_alive():
        _clear_command_file()
    _start_overlay_process()


def _send_command(cmd):
    """Write a command to the IPC file."""
    try:
        with open(_COMMAND_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        print(f"[ReactOverlay] Command error: {e}")


def _clear_command_file():
    try:
        if os.path.exists(_COMMAND_FILE):
            os.unlink(_COMMAND_FILE)
    except Exception:
        pass


def show_react_overlay():
    """Show the overlay and start its process if needed."""
    just_started = _start_overlay_process()

    if just_started:
        # Wait for overlay to be ready (WS connect or max 3s)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if _is_process_alive():
                time.sleep(0.2)
                break
            time.sleep(0.1)
    _send_command("show")


def toggle_react_overlay():
    """Show the overlay if hidden, hide it if visible."""
    just_started = _start_overlay_process()

    if just_started:
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if _is_process_alive():
                time.sleep(0.2)
                break
            time.sleep(0.1)
    _send_command("toggle")


def hide_react_overlay_if_visible():
    """Hide the overlay if it is currently visible."""
    if _is_process_alive():
        _send_command("collapse")


def stop_overlay():
    """Stop the overlay process."""
    global _overlay_process
    tracked_pid = _tracked_overlay_pid()
    try:
        if _overlay_process is not None and _overlay_process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(_overlay_process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                _overlay_process.terminate()
        elif _pid_is_alive(tracked_pid):
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(tracked_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                os.kill(int(tracked_pid), 15)
    except Exception:
        pass
    _overlay_process = None
    _clear_command_file()
    try:
        if os.path.exists(_PID_FILE):
            os.unlink(_PID_FILE)
    except Exception:
        pass
