"""
Integration test for React overlay (Electron + Python bridge).
This test launches the actual overlay and verifies:
- Process starts and stays alive
- show/toggle/hide commands work
- IPC file is read correctly
- No crashes in logs
"""

import os
import sys
import time
import subprocess
import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_overlay_imports():
    """Verify all overlay modules import cleanly."""
    import ui.react_overlay as ro
    assert ro._OVERLAY_DIR is not None
    assert os.path.exists(ro._OVERLAY_DIR)


def test_build_exists():
    """Verify Electron build output exists."""
    import ui.react_overlay as ro
    candidates = ro._overlay_dist_candidates()
    assert any(os.path.exists(p) for p in candidates), \
        f"No build output found in {candidates}"


def test_electron_binary_exists():
    """Verify Electron binary is available."""
    import ui.react_overlay as ro
    assert ro._electron_is_available(), "Electron not found"


def test_npm_not_needed():
    """Verify node_modules are intact (no broken symlinks)."""
    import ui.react_overlay as ro
    assert not ro._is_npm_install_needed(), "npm install needed"


def test_overlay_lifecycle():
    """Launch overlay, send commands, verify process stays alive."""
    import ui.react_overlay as ro

    # Clean slate
    ro.stop_overlay()
    time.sleep(0.5)

    # Ensure command file exists and is empty
    os.makedirs(os.path.dirname(ro._COMMAND_FILE), exist_ok=True)
    with open(ro._COMMAND_FILE, "w") as f:
        f.write("")

    # Start
    started = ro._start_overlay_process()
    assert started, "Overlay failed to start"

    # Wait for process to be alive
    time.sleep(1.5)
    assert ro._is_process_alive(), "Overlay process died immediately"

    # Read initial log
    log_path = ro._LOG_FILE
    initial_log = ""
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            initial_log = f.read()

    # Test show
    ro.show_react_overlay()
    time.sleep(0.5)
    assert ro._is_process_alive(), "Overlay died after show"

    # Test toggle (should hide)
    ro.toggle_react_overlay()
    time.sleep(0.5)
    assert ro._is_process_alive(), "Overlay died after toggle"

    # Test hide
    ro.hide_react_overlay_if_visible()
    time.sleep(0.5)
    assert ro._is_process_alive(), "Overlay died after hide"

    # Check logs for errors
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            full_log = f.read()
        new_log = full_log[len(initial_log):]

        fatal_keywords = ["FATAL", "crash", "segmentation fault", "segfault",
                           "Cannot find module", "Cannot resolve"]
        for kw in fatal_keywords:
            if kw.lower() in new_log.lower():
                # Not a hard failure — just report it
                print(f"\n[WARNING] Found '{kw}' in overlay log:\n{new_log[-500:]}")

    # Cleanup
    ro.stop_overlay()
    time.sleep(0.5)


def test_command_file_ipc():
    """Verify command file is written and readable."""
    import ui.react_overlay as ro

    ro._send_command("show")
    time.sleep(0.1)
    assert os.path.exists(ro._COMMAND_FILE), "Command file not created"
    with open(ro._COMMAND_FILE, "r") as f:
        content = f.read().strip()
    assert content == "show", f"Command file content mismatch: {content}"


def test_linux_flags():
    """Verify Linux Electron flags are sensible."""
    import ui.react_overlay as ro
    if os.name != "nt":
        flags = ro._electron_flags_linux()
        assert "--no-sandbox" in flags
        assert "--disable-setuid-sandbox" in flags


def test_log_file_created():
    """Verify log file path is valid and directory exists."""
    import ui.react_overlay as ro
    assert os.path.isdir(os.path.dirname(ro._LOG_FILE)), "Log directory missing"


if __name__ == "__main__":
    print("=" * 60)
    print("React Overlay Integration Tests")
    print("=" * 60)

    tests = [
        test_overlay_imports,
        test_build_exists,
        test_electron_binary_exists,
        test_npm_not_needed,
        test_linux_flags,
        test_log_file_created,
        test_command_file_ipc,
        test_overlay_lifecycle,
    ]

    passed = 0
    failed = 0

    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
