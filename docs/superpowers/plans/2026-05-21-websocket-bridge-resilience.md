# WebSocket Bridge Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add production-grade heartbeat, reconnection, connection-state tracking, and message queuing to the WebSocket bridge so the Electron overlay survives sleep, network hiccups, and backend restarts without silent data loss.

**Architecture:** Server-side uses `websockets` built-in `ping_interval`/`ping_timeout` to keep connections alive and prune dead clients. Client-side refactors the bridge store into a state machine with exponential backoff and an outbound message queue. The Pill UI consumes the new connection-state hook to render a non-intrusive reconnect indicator.

**Tech Stack:** Python 3.11 (`websockets` library), TypeScript/React (Electron overlay), Tailwind/inline styles (Pill).

---

### Task 1: Server-Side Heartbeat & Connection Hygiene

**Files:**
- Modify: `core/ws_bridge.py:1271-1284` (`_run_server`)
- Modify: `core/ws_bridge.py:72-547` (`_handler`)

- [ ] **Step 1: Enable built-in ping/pong in `websockets.serve`**
  Replace the plain `websockets.serve(_handler, "localhost", WS_PORT)` call with:
  ```python
  async with websockets.serve(
      _handler,
      "localhost",
      WS_PORT,
      ping_interval=30,
      ping_timeout=60,
  ):
  ```
  This instructs the library to send WebSocket ping frames every 30 s and close any connection that fails to respond with a pong within 60 s.

- [ ] **Step 2: Add per-client connection metadata**
  At the top of `_handler`, after `_clients.add(websocket)`, attach a small metadata dict to the websocket object:
  ```python
  websocket._wz_meta = {"connected_at": datetime.now().isoformat()}
  ```
  (This is a defensive tag for future debugging; no active logic depends on it.)

- [ ] **Step 3: Harden `_handler` finally block**
  Ensure the existing `finally` block at line 545-547 logs the disconnect reason and safely discards the client:
  ```python
  finally:
      _clients.discard(websocket)
      print(f"[WsBridge] Client disconnected ({len(_clients)} total)")
  ```
  No code change required here — just confirm the existing logic is intact after Step 1.

- [ ] **Step 4: Verify Python imports cleanly**
  Run:
  ```bash
  python -c "import core.ws_bridge"
  ```
  Must exit 0.

---

### Task 2: Client-Side Reconnection, State Machine & Message Queue

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/shared/useBridge.ts`
- Modify: `ui/whiztant-overlay/src/renderer/shared/ipc.ts`

- [ ] **Step 1: Add `ConnectionState` type to `ipc.ts`**
  Append to `ipc.ts`:
  ```typescript
  export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  ```

- [ ] **Step 2: Rewrite `useBridge.ts` store and connect logic**
  Replace the entire file with the following implementation. Key changes:
  - `ConnectionState` instead of boolean `connected`.
  - Exponential backoff: delays = `[1000, 2000, 4000, 8000]` then cap at `30000`.
  - `outboundQueue: Record<string, unknown>[]` — messages sent while not `connected` are queued.
  - On every `open` event: set `attempts = 0`, transition to `connected`, then flush the queue by calling `sendBridgeMessage` for each queued item.
  - `sendBridgeMessage` first tries to send; if `readyState !== OPEN` it pushes to `outboundQueue`.
  - `useBridgeConnectionState()` hook exported for consumers.

  ```typescript
  import { useEffect, useState, useCallback, useRef } from 'react';
  import type { ConnectionState } from './ipc';

  type BridgeListener = (msg: Record<string, unknown>) => void;
  type ConnectionListener = (state: ConnectionState) => void;

  interface BridgeStore {
    socket: WebSocket | null;
    reconnectTimer: number | null;
    attempts: number;
    started: boolean;
    state: ConnectionState;
    listeners: Set<BridgeListener>;
    connectionListeners: Set<ConnectionListener>;
    outboundQueue: Record<string, unknown>[];
  }

  const DEFAULT_PORT = 9120;
  const RECONNECT_DELAYS = [1000, 2000, 4000, 8000];
  const RECONNECT_CAP = 30000;

  const store: BridgeStore = {
    socket: null,
    reconnectTimer: null,
    attempts: 0,
    started: false,
    state: 'disconnected',
    listeners: new Set(),
    connectionListeners: new Set(),
    outboundQueue: [],
  };

  function getReconnectDelay(attempts: number): number {
    if (attempts <= 0) return RECONNECT_DELAYS[0];
    const index = Math.min(attempts - 1, RECONNECT_DELAYS.length - 1);
    const delay = RECONNECT_DELAYS[index];
    return Math.min(delay, RECONNECT_CAP);
  }

  function emitMessage(msg: Record<string, unknown>) {
    store.listeners.forEach((listener) => {
      try {
        listener(msg);
      } catch (_) {
        void 0;
      }
    });
  }

  function emitConnection(state: ConnectionState) {
    store.state = state;
    store.connectionListeners.forEach((listener) => {
      try {
        listener(state);
      } catch (_) {
        void 0;
      }
    });
  }

  function flushQueue() {
    if (!store.socket || store.socket.readyState !== WebSocket.OPEN) return;
    while (store.outboundQueue.length > 0) {
      const msg = store.outboundQueue.shift();
      if (msg) {
        try {
          store.socket.send(JSON.stringify(msg));
        } catch (_) {
          // If a single flush fails, stop to preserve order; next flush will retry
          store.outboundQueue.unshift(msg);
          break;
        }
      }
    }
  }

  function scheduleReconnect() {
    if (store.reconnectTimer !== null) return;
    store.attempts += 1;
    const delay = getReconnectDelay(store.attempts);
    emitConnection('reconnecting');
    store.reconnectTimer = window.setTimeout(() => {
      store.reconnectTimer = null;
      connect();
    }, delay);
  }

  function connect() {
    if (store.socket) {
      try {
        store.socket.close();
      } catch (_) {
        void 0;
      }
      store.socket = null;
    }

    emitConnection('connecting');

    let socket: WebSocket;
    try {
      socket = new WebSocket(`ws://127.0.0.1:${DEFAULT_PORT}`);
    } catch (_) {
      emitConnection('disconnected');
      scheduleReconnect();
      return;
    }

    store.socket = socket;
    let closedHere = false;

    const handleClose = () => {
      if (closedHere) return;
      closedHere = true;
      if (store.socket === socket) {
        store.socket = null;
      }
      emitConnection('disconnected');
      scheduleReconnect();
    };

    socket.addEventListener('open', () => {
      store.attempts = 0;
      emitConnection('connected');
      flushQueue();
    });

    socket.addEventListener('message', (event) => {
      if (typeof event.data !== 'string') return;
      try {
        const msg = JSON.parse(event.data) as Record<string, unknown>;
        emitMessage(msg);
      } catch (_) {
        void 0;
      }
    });

    socket.addEventListener('close', handleClose);
    socket.addEventListener('error', handleClose);
  }

  function ensureStarted() {
    if (store.started) return;
    store.started = true;
    connect();
  }

  export function useBridgeMessage(callback: BridgeListener) {
    useEffect(() => {
      ensureStarted();
      store.listeners.add(callback);
      return () => {
        store.listeners.delete(callback);
      };
    }, [callback]);
  }

  export function useBridgeConnected(): boolean {
    const [connected, setConnected] = useState(store.state === 'connected');

    useEffect(() => {
      ensureStarted();
      const listener: ConnectionListener = (state) => setConnected(state === 'connected');
      store.connectionListeners.add(listener);
      setConnected(store.state === 'connected');
      return () => {
        store.connectionListeners.delete(listener);
      };
    }, []);

    return connected;
  }

  export function useBridgeConnectionState(): ConnectionState {
    const [state, setState] = useState<ConnectionState>(store.state);

    useEffect(() => {
      ensureStarted();
      const listener: ConnectionListener = (s) => setState(s);
      store.connectionListeners.add(listener);
      setState(store.state);
      return () => {
        store.connectionListeners.delete(listener);
      };
    }, []);

    return state;
  }

  export function sendBridgeMessage(data: Record<string, unknown>) {
    if (store.socket?.readyState === WebSocket.OPEN) {
      store.socket.send(JSON.stringify(data));
    } else {
      store.outboundQueue.push(data);
      // If we haven't started yet, kick it off so the queue isn't stranded
      ensureStarted();
    }
  }

  export function getBridgeConnectionState(): ConnectionState {
    return store.state;
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles**
  Run:
  ```bash
  cd ui/whiztant-overlay && npm run typecheck
  ```
  Must exit 0 (ignore unrelated pre-existing errors if any; the new code must not introduce any).

---

### Task 3: Pill UI Reconnect Indicator

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/pill/Pill.tsx`

- [ ] **Step 1: Import the new hook**
  Near the top of `Pill.tsx`, add to the existing imports:
  ```typescript
  import { useBridgeMessage, sendBridgeMessage, useBridgeConnectionState } from '../shared/useBridge';
  ```

- [ ] **Step 2: Add connection-state local state**
  Inside the `Pill` component, after the existing `useState` declarations, add:
  ```typescript
  const connectionState = useBridgeConnectionState();
  const isReconnecting = connectionState === 'reconnecting' || connectionState === 'connecting';
  ```

- [ ] **Step 3: Render reconnect badge on the pill indicator**
  In the return JSX, inside the final fallback `<motion.div key="indicator">` (around line 899-925), wrap the `PillIndicator` container with a relative-positioned div and add a small amber pulse dot when `isReconnecting` is true:

  Replace:
  ```tsx
  <motion.div
    key="indicator"
    ...
  >
    <div style={{ transform: isVertical ? 'rotate(90deg)' : undefined, transformOrigin: 'center' }}>
      <PillIndicator ... />
    </div>
  </motion.div>
  ```

  With:
  ```tsx
  <motion.div
    key="indicator"
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    transition={{ duration: 0.15 }}
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
    }}
  >
    <div style={{ transform: isVertical ? 'rotate(90deg)' : undefined, transformOrigin: 'center' }}>
      <PillIndicator
        state={state}
        color={color}
        micLevels={levels}
        simulatedLevels={simulatedLevels}
        agentStatus={agentStatus}
      />
    </div>
    {isReconnecting && (
      <motion.div
        initial={{ opacity: 0, scale: 0.5 }}
        animate={{ opacity: [0.6, 1, 0.6], scale: [1, 1.2, 1] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute',
          top: -3,
          right: -3,
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: '#f59e0b',
          boxShadow: '0 0 4px 1px rgba(245,158,11,0.6)',
        }}
      />
    )}
  </motion.div>
  ```

  This renders a tiny amber pulse dot at the top-right of the pill whenever the bridge is trying to reconnect, without altering pill dimensions or interfering with drag/click handlers.

- [ ] **Step 4: Build overlay to verify no TS errors**
  Run:
  ```bash
  cd ui/whiztant-overlay && npm run build
  ```
  Must complete successfully.

---

### Task 4: Overlay-Level Connection State Banner (Optional but Recommended)

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx`

- [ ] **Step 1: Import the new hook**
  Add to existing imports:
  ```typescript
  import { sendBridgeMessage, useBridgeMessage, useBridgeConnected, useBridgeConnectionState } from '../shared/useBridge';
  ```

- [ ] **Step 2: Add reconnecting banner state**
  Inside the `Overlay` component, after existing state hooks:
  ```typescript
  const connectionState = useBridgeConnectionState();
  const showReconnectBanner = connectionState === 'reconnecting' || connectionState === 'connecting';
  ```

- [ ] **Step 3: Render a thin top banner when reconnecting**
  In the top-level returned JSX, as the first child inside the main overlay container, add:
  ```tsx
  {showReconnectBanner && (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        background: 'linear-gradient(90deg, transparent, #f59e0b, transparent)',
        opacity: 0.9,
        zIndex: 100,
        animation: 'wz-pulse-opacity 1.5s ease-in-out infinite',
      }}
    />
  )}
  ```
  And ensure the overlay's `<style>` block or CSS includes:
  ```css
  @keyframes wz-pulse-opacity {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }
  ```
  (If the overlay uses a global CSS file, add the keyframe there; otherwise inline the animation via a `<style>` tag inside the component.)

- [ ] **Step 4: Build overlay**
  Run:
  ```bash
  cd ui/whiztant-overlay && npm run build
  ```
  Must complete successfully.

---

### Task 5: End-to-End Verification

- [ ] **Step 1: Python import test**
  ```bash
  python -c "import core.ws_bridge; print('OK')"
  ```

- [ ] **Step 2: TypeScript typecheck**
  ```bash
  cd ui/whiztant-overlay && npm run typecheck
  ```

- [ ] **Step 3: Production build**
  ```bash
  cd ui/whiztant-overlay && npm run build
  ```

- [ ] **Step 4: Manual check — simulate disconnect**
  Start the Python backend (`python main.py`), open the overlay, then:
  1. Kill the backend process. Overlay should transition to `reconnecting` and show amber dot on pill + overlay banner.
  2. Restart the backend. Overlay should reconnect, amber indicators disappear, and queued messages (if any) flush.

---

## Summary of Changes

| File | Action | Lines |
|---|---|---|
| `core/ws_bridge.py` | Add `ping_interval=30`, `ping_timeout=60` to `websockets.serve` | ~1278 |
| `core/ws_bridge.py` | Attach `_wz_meta` to websocket on connect | ~75 |
| `ui/whiztant-overlay/src/renderer/shared/ipc.ts` | Add `ConnectionState` type | +1 line |
| `ui/whiztant-overlay/src/renderer/shared/useBridge.ts` | Full rewrite with state machine, exponential backoff, message queue | ~170 lines |
| `ui/whiztant-overlay/src/renderer/pill/Pill.tsx` | Import hook, add `isReconnecting`, render amber pulse badge | ~25 lines changed |
| `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx` | Import hook, add reconnect banner | ~15 lines changed |
