import { useEffect, useState } from 'react';
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
