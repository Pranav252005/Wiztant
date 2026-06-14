# Windows Smoke Checklist (pre-ship manual verification)

Run on a real Windows machine before shipping. Last code-level parity audit: 2026-06-12
(agent loop unified — Windows and Linux now share `core/agent_loop.py`; the legacy
`platforms/windows/_vlm_impl.py` loop is only reachable with `WIZTANT_LEGACY_AGENT=1`).

## Startup
- [ ] `python main.py` starts clean: uvicorn on 127.0.0.1:8765, WS bridge on 9120, tray icon appears.
- [ ] No import errors in console (PAL must not load any Linux module).

## Hotkeys
- [ ] F9 ×1 — dictation: speak, transcription pastes at cursor (test in Notepad; include a non-ASCII word to exercise the clipboard type fallback).
- [ ] F9 ×2 — agent mode toggles on (pill turns green) and off.
- [ ] Ctrl+Space — overlay shows/hides instantly (opacity toggle; no DWM repaint lag, no flicker).
- [ ] Ctrl+Shift+Space — RePrompt: copy text, trigger, optimized text written back to clipboard.
- [ ] Esc closes the overlay.
- [ ] F10 — task voice capture creates a task.

## Agent (unified loop)
- [ ] Run a trivial agent task from the overlay ("open notepad and type hello"). Verify steps stream to AgentPanel, agent completes, `agent/done` shows.
- [ ] Focus save/restore works after agent run (win32 branch in core/hotkeys.py).
- [ ] Settings → Agent tab: change Max steps, Save, re-run task — limit respected.

## Tasks & reminders
- [ ] Create a task due in ~5 min; pre-due warning and due alert fire; snooze works.
- [ ] `memory/tasks.json` updated by both overlay edits and backend.

## Integrations vault
- [ ] Add a credential integration in Settings; verify `%USERPROFILE%\.wiztant\integrations.enc` created and key stored in Windows Credential Manager (keyring), not `vault.key`.

## Tray
- [ ] Tray icon menu opens; Quit shuts down all threads/processes cleanly.

## Escape hatch
- [ ] If the unified agent loop misbehaves on Windows, set `WIZTANT_LEGACY_AGENT=1` to fall back to the legacy loop, and report the failure.
