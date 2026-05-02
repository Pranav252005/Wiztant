import { globalShortcut, BrowserWindow } from 'electron';
import { getPillState, setPillState } from './pillState';
import { sendBridgeMessage } from './bridge';

interface Windows {
  pill: BrowserWindow;
  overlay: BrowserWindow;
  showOverlay: () => void;
}

function sendHotkey(key: string) {
  sendBridgeMessage({ type: 'hotkey', key });
}

export function registerShortcuts({ overlay, showOverlay }: Windows): void {
  // Ctrl+Space — toggle tune overlay
  const BLUR_GRACE_MS = 250;
  const ctrlSpaceOk = globalShortcut.register('CommandOrControl+Space', () => {
    if (overlay.isDestroyed()) return;
    if (overlay.isVisible()) {
      overlay.hide();
      return;
    }
    const t = (overlay as any).lastAutoHiddenAt as number | undefined;
    if (typeof t === 'number' && Date.now() - t < BLUR_GRACE_MS) return;
    showOverlay();
  });
  if (!ctrlSpaceOk) {
    console.error('[Shortcuts] FAILED to register Ctrl+Space');
    if (process.platform === 'linux') {
      console.error('[Shortcuts] Linux: globalShortcut may fail on Wayland — Python keyboard fallback should handle Ctrl+Space');
    }
  }

  // F9 tap state for mode-toggle detection (mirrors Python _TAP_WINDOW = 0.4s).
  let f9TapCount = 0;
  let f9TapTimer: ReturnType<typeof setTimeout> | null = null;
  const F9_TAP_WINDOW_MS = 400;

  function flushF9Taps() {
    const count = f9TapCount;
    f9TapCount = 0;
    f9TapTimer = null;
    if (count === 1) {
      setPillState('recording');
      sendHotkey('f9_start');
    } else if (count >= 2) {
      // Multi-tap: toggle agent mode. Don't touch recording state.
      sendHotkey('f9_toggle_agent');
    }
  }

  // F9 — 1 tap starts dictation, 2+ taps toggle Agent mode.
  const f9Ok = globalShortcut.register('F9', () => {
    const isRecording = getPillState() === 'recording';
    if (isRecording) {
      // Always stop immediately when recording; cancel any pending tap window.
      setPillState('idle');
      sendHotkey('f9_stop');
      if (f9TapTimer) {
        clearTimeout(f9TapTimer);
        f9TapTimer = null;
      }
      f9TapCount = 0;
      return;
    }
    // Not recording: accumulate taps.
    f9TapCount += 1;
    if (f9TapTimer) clearTimeout(f9TapTimer);
    f9TapTimer = setTimeout(flushF9Taps, F9_TAP_WINDOW_MS);
  });
  if (!f9Ok) {
    console.error('[Shortcuts] FAILED to register F9 — another app may own it');
    if (process.platform === 'linux') {
      console.error('[Shortcuts] Linux: globalShortcut may fail on Wayland — Python keyboard fallback should handle F9');
    }
  }

  // F10 — task-capture hotkey.
  const f10Ok = globalShortcut.register('F10', () => {
    const isRecording = getPillState() === 'recording';
    setPillState(isRecording ? 'idle' : 'recording');
    sendHotkey(isRecording ? 'f10_stop' : 'f10_start');
  });
  if (!f10Ok) {
    console.error('[Shortcuts] FAILED to register F10 — another app may own it');
    if (process.platform === 'linux') {
      console.error('[Shortcuts] Linux: globalShortcut may fail on Wayland — Python keyboard fallback should handle F10');
    }
  }

  // Ctrl+Shift+Space — optimize clipboard prompt via WizPrompt
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    sendHotkey('ctrl_shift_space');
  });

  // Escape — dismiss panels, cancel active recording.
  globalShortcut.register('Escape', () => {
    if (!overlay.isDestroyed() && overlay.isVisible()) overlay.hide();
    if (getPillState() === 'recording') {
      setPillState('idle');
      sendHotkey('f9_stop');
    }
  });

  console.log(
    `[Shortcuts] Registered: Ctrl+Space=${ctrlSpaceOk} F9=${f9Ok} F10=${f10Ok}`
  );
}
