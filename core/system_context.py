"""
Wiztant core/system_context.py — System context scanning and caching.

Scans the user's machine on first run, generates a markdown file documenting
installed apps, browsers, paths, and available tools. Refreshes hourly
(lightweight) and daily (full). The agent reads this before executing tasks.

Data stored in: C:\whis\data\system_context.md
"""

import json
import logging
import os
import platform
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("wiztant.sysctx")


# ══════════════════════════════════════════════════════════════════════════════
# SCANNER
# ══════════════════════════════════════════════════════════════════════════════

class SystemContextScanner:
    """Scans the Windows machine for installed apps, browsers, paths, and tools."""

    def __init__(self, scan_type: str = 'full'):
        """
        scan_type: 'full' (comprehensive, ~5-10s) or 'lightweight' (quick, ~1s)
        """
        self.scan_type = scan_type
        self.context: dict = {}

    def scan_installed_apps(self) -> dict:
        """
        Read installed apps from Windows Registry (HKLM + HKCU Uninstall keys).
        Returns dict: {DisplayName: InstallLocation}
        """
        apps = {}
        try:
            import winreg
            keys = [
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, path in keys:
                try:
                    with winreg.OpenKey(hive, path) as reg_key:
                        count = winreg.QueryInfoKey(reg_key)[0]
                        for i in range(count):
                            try:
                                sub_name = winreg.EnumKey(reg_key, i)
                                with winreg.OpenKey(reg_key, sub_name) as sub:
                                    try:
                                        name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                        if not name or not name.strip():
                                            continue
                                        try:
                                            location = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                        except OSError:
                                            location = ""
                                        apps[name.strip()] = location.strip() if location else ""
                                    except OSError:
                                        pass
                            except OSError:
                                pass
                except OSError:
                    pass
        except Exception as e:
            log.debug(f"[SysCtx] scan_installed_apps error: {e}")
        return apps

    def scan_browsers(self) -> dict:
        """
        Detect installed browsers and their extensions.
        Returns dict: {browser_name: {path, default, extensions}}
        """
        browsers = {}
        try:
            local_app = os.environ.get("LOCALAPPDATA", "")
            program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
            user_home = str(Path.home())

            candidates = {
                "Chrome": [
                    os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
                    os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
                    os.path.join(local_app, "Google", "Chrome", "Application", "chrome.exe"),
                ],
                "Edge": [
                    os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
                    os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
                ],
                "Firefox": [
                    os.path.join(program_files, "Mozilla Firefox", "firefox.exe"),
                    os.path.join(program_files_x86, "Mozilla Firefox", "firefox.exe"),
                ],
                "Arc": [
                    os.path.join(local_app, "Arc", "app-*", "Arc.exe"),
                    os.path.join(local_app, "Arc", "Application", "arc.exe"),
                ],
                "Brave": [
                    os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                    os.path.join(local_app, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                ],
                "Opera": [
                    os.path.join(local_app, "Programs", "Opera", "opera.exe"),
                    os.path.join(user_home, "AppData", "Local", "Programs", "Opera GX", "opera.exe"),
                ],
                "Vivaldi": [
                    os.path.join(local_app, "Vivaldi", "Application", "vivaldi.exe"),
                ],
            }

            # Detect default browser from registry
            default_browser = ""
            try:
                import winreg
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
                ) as key:
                    prog_id = winreg.QueryValueEx(key, "ProgId")[0].lower()
                    if "chrome" in prog_id:
                        default_browser = "Chrome"
                    elif "edge" in prog_id:
                        default_browser = "Edge"
                    elif "firefox" in prog_id:
                        default_browser = "Firefox"
                    elif "brave" in prog_id:
                        default_browser = "Brave"
                    elif "arc" in prog_id:
                        default_browser = "Arc"
                    elif "opera" in prog_id:
                        default_browser = "Opera"
                    elif "vivaldi" in prog_id:
                        default_browser = "Vivaldi"
            except Exception:
                pass

            for name, paths in candidates.items():
                found_path = ""
                for p in paths:
                    # Handle glob-like wildcard in path
                    if "*" in p:
                        parent = Path(p).parent.parent
                        try:
                            matches = list(parent.glob(Path(p).parent.name + "/" + Path(p).name))
                            if matches:
                                found_path = str(matches[0])
                        except Exception:
                            pass
                    elif os.path.isfile(p):
                        found_path = p
                        break
                if found_path:
                    extensions = []
                    if name == "Chrome":
                        extensions = _read_chrome_extensions(local_app)
                    elif name == "Edge":
                        extensions = _read_edge_extensions(local_app)
                    browsers[name] = {
                        "path": found_path,
                        "default": (name == default_browser),
                        "extensions": extensions,
                    }
        except Exception as e:
            log.debug(f"[SysCtx] scan_browsers error: {e}")
        return browsers

    def scan_environment(self) -> dict:
        """
        Extract PATH entries and detect available CLI commands.
        Returns dict with 'paths' list and 'commands' list.
        """
        result = {"paths": [], "commands": []}
        try:
            path_str = os.environ.get("PATH", "")
            paths = [p for p in path_str.split(os.pathsep) if p.strip()]
            result["paths"] = paths

            check_commands = ["python", "python3", "node", "npm", "git", "ffmpeg",
                              "curl", "powershell", "wsl", "pip", "cargo", "go",
                              "docker", "kubectl", "code", "windsurf"]
            available = []
            for cmd in check_commands:
                try:
                    r = subprocess.run(
                        ["where", cmd],
                        capture_output=True, text=True, timeout=3
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        available.append(cmd)
                except Exception:
                    pass
            result["commands"] = available
        except Exception as e:
            log.debug(f"[SysCtx] scan_environment error: {e}")
        return result

    def scan_running_processes(self) -> list:
        """
        List unique running process names using psutil.
        Returns sorted list of .exe names.
        """
        processes = []
        try:
            import psutil
            seen = set()
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name']
                    if name and name not in seen:
                        seen.add(name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            processes = sorted(seen)
        except Exception as e:
            log.debug(f"[SysCtx] scan_running_processes error: {e}")
        return processes

    def scan_user_folders(self) -> dict:
        """
        Map key user directories and any custom top-level folders in home dir.
        Returns dict: {label: path_str}
        """
        folders = {}
        try:
            home = Path.home()
            standard = {
                "Desktop": home / "Desktop",
                "Documents": home / "Documents",
                "Downloads": home / "Downloads",
                "Music": home / "Music",
                "Pictures": home / "Pictures",
                "Videos": home / "Videos",
                "AppData (Roaming)": home / "AppData" / "Roaming",
                "AppData (Local)": home / "AppData" / "Local",
            }
            for label, path in standard.items():
                if path.exists():
                    folders[label] = str(path)

            # Custom user-created folders in home dir
            skip = {"AppData", "Desktop", "Documents", "Downloads", "Music",
                    "Pictures", "Videos", "OneDrive", "3D Objects", "Contacts",
                    "Favorites", "Links", "Searches", "Saved Games", "Intel",
                    "MicrosoftEdgeBackups", "source"}
            try:
                for item in home.iterdir():
                    if (item.is_dir()
                            and not item.name.startswith(".")
                            and item.name not in skip):
                        folders[item.name] = str(item)
            except Exception:
                pass
        except Exception as e:
            log.debug(f"[SysCtx] scan_user_folders error: {e}")
        return folders

    def scan_network(self) -> dict:
        """
        Capture hostname, IP, gateway, and DNS servers.
        Returns dict with network info.
        """
        info = {"hostname": "", "ip": "", "gateway": "", "dns": []}
        try:
            info["hostname"] = socket.gethostname()
            try:
                info["ip"] = socket.gethostbyname(info["hostname"])
            except Exception:
                pass

            # Parse ipconfig for gateway and DNS
            try:
                r = subprocess.run(
                    ["ipconfig", "/all"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8",
                    errors="replace"
                )
                lines = r.stdout.splitlines()
                dns_servers = []
                for line in lines:
                    low = line.lower()
                    if "default gateway" in low:
                        val = line.split(":", 1)[-1].strip()
                        if val and not val.startswith("."):
                            info["gateway"] = val
                    elif "dns servers" in low or ("dns" in low and "server" in low):
                        val = line.split(":", 1)[-1].strip()
                        if val and "." in val:
                            dns_servers.append(val)
                info["dns"] = list(dict.fromkeys(dns_servers))[:4]
            except Exception:
                pass
        except Exception as e:
            log.debug(f"[SysCtx] scan_network error: {e}")
        return info

    def scan_system_info(self) -> dict:
        """
        Capture OS, architecture, hostname, username, RAM, and disk info.
        Returns dict with system info.
        """
        info = {}
        try:
            info["os"] = platform.system() + " " + platform.release()
            info["os_version"] = platform.version()
            info["arch"] = platform.machine()
            info["hostname"] = os.environ.get("COMPUTERNAME", socket.gethostname())
            info["user"] = os.environ.get("USERNAME", os.environ.get("USER", "Unknown"))
            info["language"] = os.environ.get("LANG", os.environ.get("USERPROFILE", "")[-2:] or "en-US")

            try:
                import psutil
                ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
                info["ram_gb"] = ram_gb
                disk_free_gb = round(psutil.disk_usage("C:\\").free / (1024 ** 3), 1)
                disk_total_gb = round(psutil.disk_usage("C:\\").total / (1024 ** 3), 1)
                info["disk_free_gb"] = disk_free_gb
                info["disk_total_gb"] = disk_total_gb
            except Exception:
                pass
        except Exception as e:
            log.debug(f"[SysCtx] scan_system_info error: {e}")
        return info

    def run_scan(self) -> dict:
        """
        Execute scan (full or lightweight) and return the context dict.
        Each method is guarded individually — one failure won't abort the scan.
        """
        ctx: dict = {}

        ctx["system_info"] = self.scan_system_info()
        ctx["environment"] = self.scan_environment()
        ctx["running_processes"] = self.scan_running_processes()
        ctx["user_paths"] = self.scan_user_folders()

        if self.scan_type == 'full':
            ctx["installed_apps"] = self.scan_installed_apps()
            ctx["browsers"] = self.scan_browsers()
            ctx["network"] = self.scan_network()

        self.context = ctx
        return ctx


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS FOR BROWSER EXTENSION READING
# ══════════════════════════════════════════════════════════════════════════════

def _read_chrome_extensions(local_app: str) -> list:
    extensions = []
    try:
        ext_dir = Path(local_app) / "Google" / "Chrome" / "User Data" / "Default" / "Extensions"
        if not ext_dir.exists():
            return []
        for ext_folder in ext_dir.iterdir():
            if not ext_folder.is_dir():
                continue
            try:
                # Each extension has version subdirs
                for ver_dir in ext_folder.iterdir():
                    manifest = ver_dir / "manifest.json"
                    if manifest.exists():
                        with open(manifest, encoding="utf-8", errors="replace") as f:
                            data = json.load(f)
                        name = data.get("name", "").strip()
                        if name and not name.startswith("__MSG_") and len(name) < 80:
                            extensions.append(name)
                        break
            except Exception:
                pass
    except Exception:
        pass
    return sorted(set(extensions))[:20]  # cap at 20


def _read_edge_extensions(local_app: str) -> list:
    extensions = []
    try:
        ext_dir = Path(local_app) / "Microsoft" / "Edge" / "User Data" / "Default" / "Extensions"
        if not ext_dir.exists():
            return []
        for ext_folder in ext_dir.iterdir():
            if not ext_folder.is_dir():
                continue
            try:
                for ver_dir in ext_folder.iterdir():
                    manifest = ver_dir / "manifest.json"
                    if manifest.exists():
                        with open(manifest, encoding="utf-8", errors="replace") as f:
                            data = json.load(f)
                        name = data.get("name", "").strip()
                        if name and not name.startswith("__MSG_") and len(name) < 80:
                            extensions.append(name)
                        break
            except Exception:
                pass
    except Exception:
        pass
    return sorted(set(extensions))[:20]


# ══════════════════════════════════════════════════════════════════════════════
# GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class SystemContextGenerator:
    """Converts scan results dict into a well-structured markdown file."""

    def generate_markdown(self, scan_results: dict, scan_type: str = "Full Deep Scan") -> str:
        now = datetime.now()
        hostname = scan_results.get("system_info", {}).get("hostname", "Unknown")

        # Next scheduled updates
        next_hourly = now + timedelta(hours=1)
        tomorrow_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        lines = []

        # ── Header ────────────────────────────────────────────────────────────
        lines.append(f"# System Context — {hostname}")
        lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Last Updated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Scan Type: {scan_type}")
        lines.append(f"Next Hourly Update: {next_hourly.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Next Daily Full Scan: {tomorrow_midnight.strftime('%Y-%m-%d %H:%M:%S')} (midnight)")
        lines.append("")

        # ── System Information ─────────────────────────────────────────────────
        sys_info = scan_results.get("system_info", {})
        if sys_info:
            lines.append("## System Information")
            if sys_info.get("os"):
                lines.append(f"- **OS**: {sys_info['os']}")
            if sys_info.get("arch"):
                lines.append(f"- **Architecture**: {sys_info['arch']}")
            if sys_info.get("hostname"):
                lines.append(f"- **Hostname**: {sys_info['hostname']}")
            if sys_info.get("user"):
                lines.append(f"- **User**: {sys_info['user']}")
            if sys_info.get("ram_gb"):
                lines.append(f"- **RAM**: {sys_info['ram_gb']} GB")
            if sys_info.get("disk_free_gb") is not None:
                lines.append(
                    f"- **C: Drive**: {sys_info['disk_free_gb']} GB free "
                    f"/ {sys_info.get('disk_total_gb', '?')} GB total"
                )
            lines.append("")

        # ── Available Browsers ─────────────────────────────────────────────────
        browsers = scan_results.get("browsers", {})
        if browsers:
            lines.append("## Available Browsers")
            for name, info in browsers.items():
                lines.append(f"### {name}")
                path = info.get("path", "")
                if path:
                    lines.append(f"- **Path**: {path}")
                lines.append(f"- **Default Browser**: {'Yes' if info.get('default') else 'No'}")
                exts = info.get("extensions", [])
                if exts:
                    lines.append("- **Extensions**:")
                    for ext in exts:
                        lines.append(f"  - {ext}")
                else:
                    lines.append("- **Extensions**: None")
                lines.append("")

        # ── Installed Applications ─────────────────────────────────────────────
        apps = scan_results.get("installed_apps", {})
        if apps:
            lines.append("## Installed Applications")
            # Sort alphabetically, cap at 100 to keep context size reasonable
            for name in sorted(apps.keys())[:100]:
                path = apps[name]
                if path:
                    lines.append(f"- **{name}**: {path}")
                else:
                    lines.append(f"- **{name}**")
            if len(apps) > 100:
                lines.append(f"- *(and {len(apps) - 100} more)*")
            lines.append("")

        # ── Important User Paths ───────────────────────────────────────────────
        user_paths = scan_results.get("user_paths", {})
        if user_paths:
            lines.append("## Important User Paths")
            for label, path in user_paths.items():
                lines.append(f"- **{label}**: {path}")
            lines.append("")

        # ── Available Shell Commands ───────────────────────────────────────────
        env = scan_results.get("environment", {})
        commands = env.get("commands", [])
        if commands:
            lines.append("## Available Shell Commands")
            lines.append("The following commands are available via PATH:")
            for cmd in commands:
                lines.append(f"- `{cmd}`")
            lines.append("")

        # ── Environment Variables (PATH) ───────────────────────────────────────
        paths = env.get("paths", [])
        if paths:
            lines.append("## Environment Variables (PATH)")
            for p in paths[:30]:  # cap at 30 entries
                lines.append(p)
            if len(paths) > 30:
                lines.append(f"*(and {len(paths) - 30} more entries)*")
            lines.append("")

        # ── Running Processes ──────────────────────────────────────────────────
        processes = scan_results.get("running_processes", [])
        if processes:
            # Only include likely desktop-visible processes, skip system noise
            desktop_procs = [p for p in processes if not _is_system_process(p)][:40]
            if desktop_procs:
                lines.append("## Running Processes (Desktop Apps Currently Active)")
                for p in desktop_procs:
                    lines.append(f"- {p}")
                lines.append("")

        # ── Network Configuration ──────────────────────────────────────────────
        network = scan_results.get("network", {})
        if network and network.get("hostname"):
            lines.append("## Network Configuration")
            if network.get("ip"):
                lines.append(f"- **IP Address**: {network['ip']}")
            if network.get("gateway"):
                lines.append(f"- **Gateway**: {network['gateway']}")
            dns = network.get("dns", [])
            if dns:
                lines.append(f"- **DNS Servers**: {', '.join(dns)}")
            lines.append("")

        # ── Quick Navigation Tips for Agent ───────────────────────────────────
        lines.append("## Quick Navigation Tips for Agent")
        lines.append("1. **Check browsers section** before opening a browser — use the path listed above.")
        lines.append("2. **Default download location**: check Downloads path in Important User Paths.")
        lines.append("3. **Run Python scripts**: use `python` command directly if listed in Available Commands.")
        lines.append("4. **Find recent files**: check Desktop and Downloads first.")
        lines.append(
            "5. **Avoid IDE focus bug**: if Windsurf/VSCode/Cursor is in Running Processes, "
            "click desktop background before keyboard input."
        )
        lines.append("6. **Check running apps**: reference Running Processes before focusing windows.")

        # Add dynamic tip if IDE is running
        running_lower = [p.lower() for p in processes]
        ide_names = []
        if any("windsurf" in p for p in running_lower):
            ide_names.append("Windsurf")
        if any("code.exe" in p for p in running_lower):
            ide_names.append("VS Code")
        if any("cursor" in p for p in running_lower):
            ide_names.append("Cursor")
        if ide_names:
            ide_str = ", ".join(ide_names)
            lines.append(
                f"7. **ACTIVE IDEs DETECTED** ({ide_str}): These are currently running. "
                "Always click away from their windows before any keyboard shortcut or typing."
            )

        lines.append("")
        lines.append("---")
        lines.append(
            "*Note: This file is auto-generated by Wiztant. "
            "Manual edits will be overwritten on next update cycle.*"
        )

        return "\n".join(lines)


def _is_system_process(name: str) -> bool:
    """Return True for low-level system processes that clutter the list."""
    name_lower = name.lower()
    noise = {
        "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
        "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
        "conhost.exe", "ctfmon.exe", "fontdrvhost.exe", "wudfhost.exe",
        "runtimebroker.exe", "searchindexer.exe", "searchhost.exe",
        "securityhealthsystray.exe", "sihost.exe", "taskhostw.exe",
        "audiodg.exe", "spoolsv.exe", "wlanext.exe", "dashost.exe",
        "ntoskrnl.exe", "idle",
    }
    return name_lower in noise


# ══════════════════════════════════════════════════════════════════════════════
# LOADER
# ══════════════════════════════════════════════════════════════════════════════

class SystemContextLoader:
    """Loads and caches system_context.md in memory."""

    def __init__(self, data_dir: Path):
        self.context_file = data_dir / "system_context.md"
        self.context_markdown: Optional[str] = None
        self.last_loaded: Optional[datetime] = None

    def context_file_exists(self) -> bool:
        return self.context_file.exists() and self.context_file.stat().st_size > 50

    def load(self) -> bool:
        """Load from disk into memory. Returns True on success."""
        try:
            if not self.context_file_exists():
                return False
            self.context_markdown = self.context_file.read_text(encoding="utf-8")
            self.last_loaded = datetime.now()
            log.debug(f"[SysCtx] Loaded {len(self.context_markdown)} chars from {self.context_file}")
            return True
        except Exception as e:
            log.warning(f"[SysCtx] Load failed: {e}")
            return False

    def reload(self):
        """Reload from disk (called by scheduler after an update)."""
        self.load()

    def save(self, markdown: str):
        """Write markdown to disk."""
        try:
            self.context_file.parent.mkdir(parents=True, exist_ok=True)
            self.context_file.write_text(markdown, encoding="utf-8")
            log.debug(f"[SysCtx] Saved {len(markdown)} chars to {self.context_file}")
        except Exception as e:
            log.warning(f"[SysCtx] Save failed: {e}")

    def get_context(self) -> Optional[str]:
        return self.context_markdown

    def is_loaded(self) -> bool:
        return self.context_markdown is not None


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

class SystemContextScheduler:
    """Schedules hourly lightweight and daily full scans in background threads."""

    def __init__(self, data_dir: Path, loader: SystemContextLoader):
        self.data_dir = data_dir
        self.loader = loader
        self._hourly_timer: Optional[threading.Timer] = None
        self._daily_timer: Optional[threading.Timer] = None
        self.is_running = False

    def start(self):
        """Start both recurring timers."""
        self.is_running = True
        self._schedule_hourly()
        self._schedule_daily()
        log.info("[SysCtx] Scheduler started (hourly lightweight + daily full scan at midnight)")

    def stop(self):
        """Cancel both timers gracefully."""
        self.is_running = False
        if self._hourly_timer:
            self._hourly_timer.cancel()
            self._hourly_timer = None
        if self._daily_timer:
            self._daily_timer.cancel()
            self._daily_timer = None
        log.info("[SysCtx] Scheduler stopped")

    def trigger_refresh(self, scan_type: str = 'full'):
        """Manually trigger a refresh (called from tray menu)."""
        def _run():
            try:
                log.info(f"[SysCtx] Manual refresh triggered ({scan_type})")
                self._do_scan(scan_type)
            except Exception as e:
                log.warning(f"[SysCtx] Manual refresh error: {e}")
        threading.Thread(target=_run, daemon=True, name="sysctx-manual").start()

    def _schedule_hourly(self):
        if not self.is_running:
            return
        self._hourly_timer = threading.Timer(3600, self._hourly_update)
        self._hourly_timer.daemon = True
        self._hourly_timer.start()

    def _schedule_daily(self):
        if not self.is_running:
            return
        delay = self._seconds_until_midnight()
        self._daily_timer = threading.Timer(delay, self._daily_update)
        self._daily_timer.daemon = True
        self._daily_timer.start()

    def _hourly_update(self):
        """Run lightweight scan, then reschedule."""
        if not self.is_running:
            return
        try:
            log.info("[SysCtx] Hourly lightweight scan starting...")
            self._do_scan('lightweight')
        except Exception as e:
            log.warning(f"[SysCtx] Hourly scan error: {e}")
        finally:
            self._schedule_hourly()  # reschedule regardless of outcome

    def _daily_update(self):
        """Run full scan at midnight, then reschedule for next midnight."""
        if not self.is_running:
            return
        try:
            log.info("[SysCtx] Daily full scan starting...")
            self._do_scan('full')
        except Exception as e:
            log.warning(f"[SysCtx] Daily scan error: {e}")
        finally:
            self._schedule_daily()

    def _do_scan(self, scan_type: str):
        """Execute scan, generate markdown, save, and reload into memory."""
        scanner = SystemContextScanner(scan_type)
        # Run with 30-second timeout
        result_holder: list = []
        def _scan():
            result_holder.append(scanner.run_scan())
        t = threading.Thread(target=_scan, daemon=True)
        t.start()
        t.join(timeout=30)
        if not result_holder:
            log.warning("[SysCtx] Scan timed out (>30s) — keeping cached version")
            return
        results = result_holder[0]
        label = "Full Deep Scan" if scan_type == 'full' else "Lightweight Update"
        md = SystemContextGenerator().generate_markdown(results, scan_type=label)
        self.loader.save(md)
        self.loader.reload()
        log.info(f"[SysCtx] {label} complete — context updated")

    def _seconds_until_midnight(self) -> float:
        """Calculate seconds until next midnight."""
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return max((midnight - now).total_seconds(), 60)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC INIT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

_active_scheduler: SystemContextScheduler | None = None


def initialize_system_context(
    data_dir: Path,
) -> tuple:
    """
    Called on Wiztant startup. Returns (loader, scheduler).

    - First run: deep scan + generate markdown (~5-10s, runs in background thread)
    - Subsequent runs: load from disk instantly, start scheduler
    """
    global _active_scheduler

    loader = SystemContextLoader(data_dir)
    scheduler = SystemContextScheduler(data_dir, loader)

    if not loader.context_file_exists():
        # First run: do full scan in this thread (caller should be in a bg thread)
        print("[SysCtx] First run detected — scanning system (~5-10s)...")
        try:
            result_holder: list = []
            def _scan():
                scanner = SystemContextScanner('full')
                result_holder.append(scanner.run_scan())
            t = threading.Thread(target=_scan, daemon=True)
            t.start()
            t.join(timeout=30)
            if result_holder:
                md = SystemContextGenerator().generate_markdown(result_holder[0])
                loader.save(md)
                loader.load()
                print("[SysCtx] System context saved — ready for agent use.")
            else:
                print("[SysCtx] Scan timed out — will retry on next startup.")
        except Exception as e:
            print(f"[SysCtx] First-run scan failed: {e}")
    else:
        loader.load()
        print(f"[SysCtx] Loaded system context ({len(loader.context_markdown or '')} chars)")

    # Stop any previous scheduler before starting a new one so timers don't pile up.
    if _active_scheduler is not None and _active_scheduler.is_running:
        _active_scheduler.stop()
    scheduler.start()
    _active_scheduler = scheduler
    return loader, scheduler
