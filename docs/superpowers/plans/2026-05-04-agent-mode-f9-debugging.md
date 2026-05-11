# Agent Mode F9×2 + Execution Debugging Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix F9×2 agent mode toggle (pill visual feedback + actual mode switch) and ensure agent voice/text execution works end-to-end.
**Architecture:** Electron overlay handles F9 hotkey → WS bridge → Python hotkeys.py → agent pipeline. Double-registration (Electron + Python fallback) causes race conditions. Silent failures in broadcast_sync and agent pre-flight mask root causes.
**Tech Stack:** Python 3.11, Electron 33, WebSocket bridge (port 9120), UI-TARS via OpenRouter.

---

## Background & Root Cause Analysis

### Symptoms Reported
1. F9×2 does NOT change the pill visually
2. Agent mode appears "not turning on"
3. Voice dictation in agent mode transcribes but agent does NOT execute tasks
4. Unclear if text-based agent (overlay chat panel) works

### Code Path Traced

**F9×2 Toggle Path:**
- Electron `shortcuts.ts:flushF9Taps()` → sends `f9_toggle_agent` via WS
- Python `ws_bridge.py:_handle_hotkey()` → calls `hotkeys.toggle_agent_mode()`
- `hotkeys.py:toggle_agent_mode()` → toggles `state.agent_mode`, broadcasts `agent_mode` + `wave_state` messages
- **BUT:** On both Windows and Linux, Python ALSO registers F9 via `keyboard` library / pynput fallback. So `toggle_agent_mode()` gets called **twice** (Electron WS + Python native handler).
- The debounce (`_last_toggle_time < 0.6`) is **not thread-safe**. Both calls can race past the check, toggle twice, ending up back at the original state.
- `broadcast_sync()` silently returns if `_clients` is empty or `_loop` is None. No error, no feedback.

**Agent Execution Path (after voice transcription):**
- `hotkeys.py:transcribe_and_dispatch()` → sees `state.agent_mode = True` → calls `ask_ai(text, user_already_added=True)`
- `agent.py:ask_ai()` → pre-flight checks:
  - `_endpoint_reachable()` — pings API endpoints (3.5s timeout)
  - `usage.check_usage("uitars", tier, fail_open=True)` — quota check
- If pre-flight passes → `asyncio.run(run_unified_agent(...))`
- `agent_unified.py:run_unified_agent()` → app detection imports `core.app_detector` which **was removed** (caught by except, but no nav context)
- `_call_vision_model()` → calls `call_api()` — if this hangs or errors, exception bubbles up to `ask_ai` catch block

### Known Code Defects Found
1. **Race condition in toggle_agent_mode()**: No mutex protects the toggle + broadcast sequence.
2. **Silent broadcast failure**: `broadcast_sync()` returns early with no logging when no clients connected.
3. **Missing app_detector module**: Removed in cleanup but still imported in `agent_unified.py` and `window_manager.py`.
4. **No diagnostic logging in toggle path**: Cannot tell if toggle fired, if broadcast sent, or if renderer received.

---

## Task 1: Harden toggle_agent_mode() Against Race Conditions

**Files:**
- Modify: `core/hotkeys.py:879-907`

**Steps:**
- [ ] **Step 1:** Add a `threading.Lock()` at module level for agent toggle
- [ ] **Step 2:** Wrap the toggle + broadcast sequence in the lock
- [ ] **Step 3:** Add `print()` logging at every branch so user can see what happened in terminal
- [ ] **Step 4:** Verify import test passes: `python -c "import main"`

**Code change:**
```python
_agent_toggle_lock = threading.Lock()

def toggle_agent_mode():
    global _last_toggle_time
    with _agent_toggle_lock:
        try:
            import core as state
            from core.toast import show_toast
            from core.ws_bridge import send_wave_state, broadcast_sync

            cancel_pending_f9_taps()

            now = time.time()
            if now - _last_toggle_time < 0.6:
                print(f"[Hotkeys] toggle_agent_mode debounced ({now - _last_toggle_time:.2f}s)")
                return
            _last_toggle_time = now
            prev_mode = getattr(state, "agent_mode", False)
            state.agent_mode = not prev_mode
            mode_name = "Agent" if state.agent_mode else "Dictation"
            show_toast(f"{mode_name} mode ready", "Wiztant")
            print(f"[Hotkeys] Mode toggled: {mode_name} (was {'Agent' if prev_mode else 'Dictation'})")

            broadcast_sync({"type": "agent_mode", "enabled": state.agent_mode})
            send_wave_state("agent" if state.agent_mode else "idle")
            print(f"[Hotkeys] Broadcast agent_mode={state.agent_mode} + wave_state={'agent' if state.agent_mode else 'idle'}")
        except Exception as e:
            print(f"[Hotkeys] toggle_agent_mode error: {e}")
```

---

## Task 2: Add Diagnostic Logging to WS Bridge Broadcast

**Files:**
- Modify: `core/ws_bridge.py:545-558`

**Steps:**
- [ ] **Step 1:** Add debug prints to `broadcast_sync()` showing `_loop`, `_clients` count, and message type
- [ ] **Step 2:** Add debug print to `send_wave_state()`
- [ ] **Step 3:** Verify import test passes

**Code change:**
```python
def broadcast_sync(data: dict):
    """Thread-safe broadcast — callable from any thread."""
    client_count = len(_clients)
    loop_ok = _loop is not None
    print(f"[WsBridge] broadcast_sync: type={data.get('type')}, loop={loop_ok}, clients={client_count}")
    if _loop is None or not _clients:
        print(f"[WsBridge] broadcast_sync SKIPPED (no loop or no clients)")
        return
    try:
        asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)
    except Exception as e:
        print(f"[WsBridge] broadcast_sync error: {e}")


def send_wave_state(state_name: str):
    """Push wave/overlay state change."""
    print(f"[WsBridge] send_wave_state: {state_name}")
    broadcast_sync({"type": "wave_state", "state": state_name})
```

---

## Task 3: Harden Pill Renderer to Always Handle Agent Mode

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/pill/Pill.tsx`

**Steps:**
- [ ] **Step 1:** Add `console.log()` inside the `agent_mode` message handler
- [ ] **Step 2:** Add `console.log()` inside the `wave_state` handler
- [ ] **Step 3:** Ensure `agentModeEnabled` state persists across reconnects by also inferring it from `wave_state: agent`
- [ ] **Step 4:** Run `npm run typecheck`
- [ ] **Step 5:** Run `npm run build`

**Code change:**
Inside `handleBridge`:
```tsx
// ── Agent mode toggle ──
if (msg?.type === 'agent_mode') {
  const enabled = Boolean(msg.enabled);
  console.log('[Pill] agent_mode message:', enabled);
  setAgentModeEnabled(enabled);
}

// ── Wave state (Python-driven state machine) ──
if (msg?.type === 'wave_state') {
  const ws = String(msg.state ?? '');
  console.log('[Pill] wave_state message:', ws);
  ...
}
```

Also, when `wave_state: agent` arrives, implicitly enable agent mode:
```tsx
if (ws === 'agent') {
  setAgentModeEnabled(true);
}
if (ws === 'idle' && agentStatusRef.current === 'idle') {
  // Only clear agent mode on idle if agent isn't actively working
  // Actually keep it simple: let explicit agent_mode message control this
}
```

---

## Task 4: Add Diagnostic Logging to Agent Execution Path

**Files:**
- Modify: `core/agent.py:1185-1293`

**Steps:**
- [ ] **Step 1:** Add `print()` logging before each pre-flight check
- [ ] **Step 2:** Add `print()` logging before `asyncio.run()`
- [ ] **Step 3:** Add `print()` logging in the except block
- [ ] **Step 4:** Verify import test passes

**Code change:**
Inside `ask_ai()`, agent mode block:
```python
print(f"[Agent] ask_ai entered agent block. agent_mode={state.agent_mode}, force_agent={force_agent}")

# Pre-flight endpoint check
endpoints = _agent_required_endpoints()
print(f"[Agent] Required endpoints: {endpoints}")
if not all(_endpoint_reachable(url) for url in endpoints):
    message = _mode_offline_message("agent")
    print(f"[Agent] BLOCKED: endpoints not reachable. Message: {message}")
    add_history_message("assistant", message)
    return

# Pre-flight usage check
pre_allowed, pre_msg = usage.check_usage("uitars", tier, fail_open=True)
print(f"[Agent] Usage check: allowed={pre_allowed}, msg={pre_msg}")
if not pre_allowed:
    print(f"[Agent] BLOCKED: usage check failed")
    add_history_message("assistant", pre_msg)
    return

print("[Agent] Pre-flights passed. Starting run_unified_agent...")
try:
    from core.agent_unified import run_unified_agent
    from platforms.factory import get_agent_runtime
    summary = asyncio.run(run_unified_agent(...))
    print(f"[Agent] run_unified_agent returned: {summary}")
except Exception as e:
    summary = f"Agent stopped: {e}"
    print(f"[Agent] run_unified_agent EXCEPTION: {e}")
```

---

## Task 5: Fix Removed app_detector References

**Files:**
- Modify: `core/agent_unified.py:529-544`
- Modify: `core/window_manager.py` (find and guard app_detector imports)

**Steps:**
- [ ] **Step 1:** In `agent_unified.py`, change `_detect_app` and `_build_nav_context` to return `None`/`""` without importing removed module
- [ ] **Step 2:** In `window_manager.py`, guard any `app_detector` imports with try/except (if not already)
- [ ] **Step 3:** Verify import test passes

**Code change:**
```python
def _detect_app(task: str) -> Optional[str]:
    """Detect target app from the task string."""
    # app_detector module was removed in cleanup; return None for now
    return None

def _build_nav_context(target_app: str, task: str) -> str:
    """Load navigation spec for the target app."""
    # app_detector module was removed in cleanup; return empty for now
    return ""
```

---

## Task 6: Verify Text-Based Agent Path

**Files:**
- Read-only review: `core/ws_bridge.py:481-491` and overlay Agent panel code

**Steps:**
- [ ] **Step 1:** Confirm `_handle_agent_task` calls `ask_ai(text, force_agent=True)` — it does
- [ ] **Step 2:** Add debug logging to `_handle_agent_task`
- [ ] **Step 3:** Verify overlay sends `send_agent_task` message type (check overlay Agent panel)

**Code change:**
```python
def _handle_agent_task(text: str):
    """Route an agent task from the overlay to the agent pipeline (force_agent=True)."""
    print(f"[WsBridge] _handle_agent_task received: {text[:80]}")
    def _run():
        try:
            from core.agent import ask_ai
            ask_ai(text, force_agent=True)
        except Exception as e:
            print(f"[WsBridge] Agent task dispatch error: {e}")
    threading.Thread(target=_run, daemon=True).start()
```

---

## Task 7: Build and Final Verification

**Steps:**
- [ ] **Step 1:** Run `python -c "import main"` in project root
- [ ] **Step 2:** Run `cd ui/whiztant-overlay && npm run typecheck`
- [ ] **Step 3:** Run `cd ui/whiztant-overlay && npm run build`
- [ ] **Step 4:** Confirm no syntax errors, no import errors

---

## Verification Steps for Human Partner

After deploying the build:

1. **Start the app** and watch the terminal
2. **Press F9 twice** quickly — you should see in terminal:
   ```
   [Hotkeys] Mode toggled: Agent (was Dictation)
   [Hotkeys] Broadcast agent_mode=True + wave_state=agent
   [WsBridge] send_wave_state: agent
   [WsBridge] broadcast_sync: type=wave_state, loop=True, clients=1
   [WsBridge] broadcast_sync: type=agent_mode, loop=True, clients=1
   ```
3. **Pill should turn dark blue** immediately
4. **Press F9 once** and say "open chrome"
5. **Watch terminal** for:
   ```
   [Agent] ask_ai entered agent block. agent_mode=True, force_agent=False
   [Agent] Required endpoints: [...]
   [Agent] Usage check: allowed=True, msg=...
   [Agent] Pre-flights passed. Starting run_unified_agent...
   ```
6. **If agent doesn't execute**, the terminal logs will show exactly where it stopped
7. **Test text agent**: Open overlay → Agent tab → type "open youtube" → send. Terminal should show `_handle_agent_task received` and agent execution logs.

---

## Success Criteria

- [ ] F9×2 toggles agent mode with immediate dark-blue pill feedback
- [ ] Voice commands in agent mode execute (or fail with clear logged reason)
- [ ] Text commands in overlay Agent panel execute
- [ ] All builds pass (`python -c "import main"` + `npm run build`)
