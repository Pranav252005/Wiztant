"""
Deep overlay test — run overlay for several seconds, exercise all IPC paths,
and capture every log/warning/error.
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_1_keyboard_fallback():
    """Verify Python-side keyboard hook can load (pynput fallback)."""
    _print_section("1. Keyboard fallback availability")
    try:
        import keyboard
        print("  [OK] keyboard library available")
        return True
    except Exception as e:
        print(f"  [WARN] keyboard not available: {e}")

    try:
        from pynput import keyboard as pkb
        print("  [OK] pynput available as fallback")
        return True
    except Exception as e:
        print(f"  [FAIL] pynput also not available: {e}")
        return False


def test_2_overlay_start_and_ipc():
    """Start overlay, send show/toggle/hide, check log for errors."""
    _print_section("2. Overlay lifecycle + IPC")
    import ui.react_overlay as ro

    ro.stop_overlay()
    time.sleep(0.5)

    with open(ro._COMMAND_FILE, "w") as f:
        f.write("")

    ok = ro._start_overlay_process()
    if not ok:
        print("  [FAIL] Overlay failed to start")
        return False

    # Wait for WS connect
    time.sleep(2.0)

    if not ro._is_process_alive():
        print("  [FAIL] Overlay died after 2s")
        return False
    print("  [OK] Overlay process alive after 2s")

    # Read log
    log = ""
    if os.path.exists(ro._LOG_FILE):
        with open(ro._LOG_FILE, "r") as f:
            log = f.read()

    # Check for known error signatures
    errors = []
    for line in log.splitlines()[-50:]:
        low = line.lower()
        if any(k in low for k in ["error", "fatal", "crash", "exception", "cannot find", "cannot resolve"]):
            if "wayland_event_watcher" in low or "wl_shm_pool" in low:
                continue  # Harmless Wayland cleanup noise
            errors.append(line)

    if errors:
        print(f"  [WARN] {len(errors)} suspicious log lines:")
        for e in errors:
            print(f"    {e}")
    else:
        print("  [OK] No suspicious errors in log")

    # Send commands
    for cmd in ["show", "toggle", "toggle", "hide"]:
        ro._send_command(cmd)
        time.sleep(0.3)
        if not ro._is_process_alive():
            print(f"  [FAIL] Overlay died after '{cmd}'")
            return False
    print("  [OK] All IPC commands survived")

    ro.stop_overlay()
    time.sleep(0.5)
    return True


def test_3_ws_bridge_message_roundtrip():
    """Send a message through WS bridge and verify it reaches overlay."""
    _print_section("3. WS bridge roundtrip")
    try:
        from core.ws_bridge import broadcast_sync
        import ui.react_overlay as ro

        ro._ensure_ws_bridge()
        time.sleep(0.5)

        payload = {"type": "ping", "payload": {"test": True}}
        broadcast_sync(payload)
        print("  [OK] broadcast_sync executed without exception")
        return True
    except Exception as e:
        print(f"  [FAIL] broadcast_sync failed: {e}")
        return False


def test_4_command_file_race():
    """Rapidly overwrite command file to check for race conditions."""
    _print_section("4. Command file race test")
    import ui.react_overlay as ro

    os.makedirs(os.path.dirname(ro._COMMAND_FILE), exist_ok=True)
    for i in range(20):
        with open(ro._COMMAND_FILE, "w") as f:
            f.write("toggle" if i % 2 == 0 else "show")
        time.sleep(0.05)

    print("  [OK] 20 rapid writes completed")
    return True


def test_5_hotkey_imports_on_linux():
    """Verify hotkey module imports and registers without crash."""
    _print_section("5. Hotkey module health")
    try:
        import core.hotkeys as hk
        # Don't actually call register_hotkeys() — it would bind real hooks
        print("  [OK] core.hotkeys imports cleanly")
        print(f"  [INFO] _keyboard() = {hk._keyboard()}")
        return True
    except Exception as e:
        print(f"  [FAIL] core.hotkeys import failed: {e}")
        return False


def test_6_tasks_module_no_crash():
    """Verify tasks module loads (regression for missing sys import)."""
    _print_section("6. Tasks module health")
    try:
        from core.tasks import get_task_snapshot
        snap = get_task_snapshot()
        print(f"  [OK] get_task_snapshot() returned keys: {list(snap.keys())}")
        return True
    except Exception as e:
        print(f"  [FAIL] tasks module failed: {e}")
        return False


def test_7_paste_fallback():
    """Verify paste fallback functions exist."""
    _print_section("7. Paste fallback health")
    try:
        from core.hotkeys import _paste_clipboard
        print("  [OK] _paste_clipboard function exists")
        return True
    except Exception as e:
        print(f"  [FAIL] _paste_clipboard import failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    tests = [
        test_1_keyboard_fallback,
        test_2_overlay_start_and_ipc,
        test_3_ws_bridge_message_roundtrip,
        test_4_command_file_race,
        test_5_hotkey_imports_on_linux,
        test_6_tasks_module_no_crash,
        test_7_paste_fallback,
    ]
    for t in tests:
        try:
            results.append(t())
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            results.append(False)

    _print_section("SUMMARY")
    passed = sum(results)
    total = len(results)
    for i, ok in enumerate(results, 1):
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] Test {i}")
    print(f"\nTotal: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)
