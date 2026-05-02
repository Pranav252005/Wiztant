import { useEffect, useState } from 'react';

type BridgeListener = (msg: Record<string, unknown>) => void;
type ConnectionListener = (connected: boolean) => void;

interface BridgeStore {
  socket: WebSocket | null;
  reconnectTimer: number | null;
  attempts: number;
  started: boolean;
  connected: boolean;
  listeners: Set<BridgeListener>;
  connectionListeners: Set<ConnectionListener>;
}

const DEFAULT_PORT = 9120;

const store: BridgeStore = {
  socket: null,
  reconnectTimer: null,
  attempts: 0,
  started: false,
  connected: false,
  listeners: new Set(),
  connectionListeners: new Set(),
};

function emitMessage(msg: Record<string, unknown>) {
  store.listeners.forEach((listener) => {
    try {
      listener(msg);
    } catch (_) {
      void 0;
    }
  });
}

function emitConnection(connected: boolean) {
  store.connected = connected;
  store.connectionListeners.forEach((listener) => {
    try {
      listener(connected);
    } catch (_) {
      void 0;
    }
  });
}

function scheduleReconnect() {
  if (store.reconnectTimer !== null) return;
  store.attempts += 1;
  const delay = Math.min(8000, 500 * 2 ** Math.min(4, store.attempts));
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

  let socket: WebSocket;
  try {
    socket = new WebSocket(`ws://127.0.0.1:${DEFAULT_PORT}`);
  } catch (_) {
    emitConnection(false);
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
    emitConnection(false);
    scheduleReconnect();
  };

  socket.addEventListener('open', () => {
    store.attempts = 0;
    emitConnection(true);
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
  const [connected, setConnected] = useState(store.connected);

  useEffect(() => {
    ensureStarted();
    store.connectionListeners.add(setConnected);
    setConnected(store.connected);
    return () => {
      store.connectionListeners.delete(setConnected);
    };
  }, []);

  return connected;
}

export function sendBridgeMessage(data: Record<string, unknown>) {
  if (store.socket?.readyState === WebSocket.OPEN) {
    store.socket.send(JSON.stringify(data));
  }
}
