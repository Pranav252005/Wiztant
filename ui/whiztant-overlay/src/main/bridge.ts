import WebSocket from 'ws';

let ws: WebSocket | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;
const pendingQueue: string[] = [];

function ensureConnected() {
  if (ws?.readyState === WebSocket.OPEN) return;
  try {
    const socket = new WebSocket('ws://127.0.0.1:9120');
    ws = socket;

    socket.on('open', () => {
      console.log('[Overlay] WS connected to Python bridge');
      socket.send(JSON.stringify({ type: 'overlay_ready' }));
      while (pendingQueue.length > 0) {
        socket.send(pendingQueue.shift()!);
      }
    });

    socket.on('error', (err) => {
      console.warn('[Overlay] WS connect error:', err.message);
    });

    socket.on('close', () => {
      // Only clear the global ref if this socket is still the current one.
      // If ensureConnected() was called again and replaced ws, leave the
      // newer socket alone.
      if (ws === socket) {
        ws = null;
      }
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          ensureConnected();
        }, 1000);
      }
    });
  } catch {
    // ws module may not be bundled in some configs
  }
}

ensureConnected();

export function sendBridgeMessage(data: Record<string, unknown>): void {
  const payload = JSON.stringify(data);
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(payload);
  } else {
    if (pendingQueue.length < 5) pendingQueue.push(payload);
    ensureConnected();
  }
}

export function closeBridge(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    try { ws.close(); } catch { /* ignore */ }
    ws = null;
  }
}
