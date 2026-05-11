import { globalShortcut, BrowserWindow } from 'electron';
import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { getPillState, setPillState } from './pillState';
import { sendBridgeMessage } from './bridge';

interface Windows {
  pill: BrowserWindow;
  overlay: BrowserWindow;
  showOverlay: () => void;
}

let _windows: Windows | null = null;

function sendHotkey(key: string) {
  sendBridgeMessage({ type: 'hotkey', key });
}

const SETTINGS_PATH = path.join(process.cwd(), 'data', 'settings.json');

function ensureSettingsDir() {
  try {
    const dir = path.dirname(SETTINGS_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  } catch { /* ignore */ }
}

export interface ShortcutConfig {
  overlay_toggle: string;
  dictation: string;
  agent_toggle: string;
  wizprompt: string;
  task_voice: string;
  dismiss: string;
}

const DEFAULT_SHORTCUTS: ShortcutConfig = {
  overlay_toggle: 'CommandOrControl+Space',
  dictation: 'F9',
  agent_toggle: 'F9',
  wizprompt: 'CommandOrControl+Shift+Space',
  task_voice: 'F10',
  dismiss: 'Escape',
};

function _loadShortcutConfig(): ShortcutConfig {
  try {
    if (!existsSync(SETTINGS_PATH)) return { ...DEFAULT_SHORTCUTS };
    const raw = readFileSync(SETTINGS_PATH, 'utf-8');
    const data = JSON.parse(raw);
    const shortcuts = data.shortcuts;
    if (shortcuts && typeof shortcuts === 'object') {
      return {
        overlay_toggle: String(shortcuts.overlay_toggle || DEFAULT_SHORTCUTS.overlay_toggle),
        dictation: String(shortcuts.dictation || DEFAULT_SHORTCUTS.dictation),
        agent_toggle: String(shortcuts.agent_toggle || DEFAULT_SHORTCUTS.agent_toggle),
        wizprompt: String(shortcuts.wizprompt || DEFAULT_SHORTCUTS.wizprompt),
        task_voice: String(shortcuts.task_voice || DEFAULT_SHORTCUTS.task_voice),
        dismiss: String(shortcuts.dismiss || DEFAULT_SHORTCUTS.dismiss),
      };
    }
  } catch {
    /* ignore */
  }
  return { ...DEFAULT_SHORTCUTS };
}

export function saveShortcutConfig(config: Partial<ShortcutConfig>) {
  ensureSettingsDir();
  try {
    let data: Record<string, unknown> = {};
    if (existsSync(SETTINGS_PATH)) {
      data = JSON.parse(readFileSync(SETTINGS_PATH, 'utf-8'));
    }
    data.shortcuts = { ..._loadShortcutConfig(), ...config };
    writeFileSync(SETTINGS_PATH, JSON.stringify(data, null, 2));
  } catch (e) {
    console.error('[Shortcuts] Failed to save config:', e);
  }
}

function _normalizeAccelerator(key: string): string {
  const parts = key.split(/\s*\+\s*/).map((p) => {
    const lower = p.trim().toLowerCase();
    if (lower.length <= 1) return lower;
    const special: Record<string, string> = {
      ctrl: 'CommandOrControl',
      cmd: 'CommandOrControl',
      command: 'CommandOrControl',
      alt: 'Alt',
      shift: 'Shift',
      f1: 'F1', f2: 'F2', f3: 'F3', f4: 'F4', f5: 'F5',
      f6: 'F6', f7: 'F7', f8: 'F8', f9: 'F9', f10: 'F10',
      f11: 'F11', f12: 'F12',
      space: 'Space',
      tab: 'Tab',
      escape: 'Escape',
      esc: 'Esc',
      enter: 'Enter',
      return: 'Return',
      backspace: 'Backspace',
      delete: 'Delete',
      del: 'Delete',
      insert: 'Insert',
      home: 'Home',
      end: 'End',
      pageup: 'PageUp',
      pagedown: 'PageDown',
      up: 'Up',
      down: 'Down',
      left: 'Left',
      right: 'Right',
    };
    return special[lower] || p.trim();
  });
  return parts.join('+');
}

const TAP_WINDOW_MS = 400;

function _isSingleKey(accel: string): boolean {
  return !accel.includes('+');
}

function registerTapShortcut(
  accel: string,
  tapsRequired: number,
  onTrigger: () => void,
  onRecordingStop?: () => void,
): boolean {
  let tapCount = 0;
  let tapTimer: ReturnType<typeof setTimeout> | null = null;

  function flushTaps() {
    const count = tapCount;
    tapCount = 0;
    tapTimer = null;
    if (count >= tapsRequired) {
      onTrigger();
    }
  }

  return globalShortcut.register(accel, () => {
    const isRecording = getPillState() === 'recording';
    if (isRecording && onRecordingStop) {
      setPillState('idle');
      onRecordingStop();
      if (tapTimer) {
        clearTimeout(tapTimer);
        tapTimer = null;
      }
      tapCount = 0;
      return;
    }
    tapCount += 1;
    if (tapTimer) clearTimeout(tapTimer);
    tapTimer = setTimeout(flushTaps, TAP_WINDOW_MS);
  });
}

export function registerShortcuts(windows: Windows): void {
  _windows = windows;
  const { overlay, showOverlay } = windows;
  const cfg = _loadShortcutConfig();
  const results: string[] = [];

  // Overlay toggle
  const overlayAccel = _normalizeAccelerator(cfg.overlay_toggle);
  const BLUR_GRACE_MS = 250;
  const overlayOk = globalShortcut.register(overlayAccel, () => {
    if (overlay.isDestroyed()) return;
    if (overlay.isVisible()) {
      overlay.hide();
      return;
    }
    const t = (overlay as any).lastAutoHiddenAt as number | undefined;
    if (typeof t === 'number' && Date.now() - t < BLUR_GRACE_MS) return;
    showOverlay();
  });
  results.push(`Overlay=${overlayOk}(${overlayAccel})`);
  if (!overlayOk) {
    console.error(`[Shortcuts] FAILED to register overlay toggle ${overlayAccel}`);
  }

  // Dictation + Agent toggle (shared key with tap counting)
  const dictAccel = _normalizeAccelerator(cfg.dictation);
  const agentAccel = _normalizeAccelerator(cfg.agent_toggle);
  const sharedKey = dictAccel === agentAccel;

  if (sharedKey) {
    // F9-style tap counting: 1 tap = dictation, 2 taps = agent
    let f9TapCount = 0;
    let f9TapTimer: ReturnType<typeof setTimeout> | null = null;

    function flushF9Taps() {
      const count = f9TapCount;
      f9TapCount = 0;
      f9TapTimer = null;
      if (count === 1) {
        setPillState('recording');
        sendHotkey('f9_start');
      } else if (count >= 2) {
        sendHotkey('f9_toggle_agent');
      }
    }

    const dictOk = globalShortcut.register(dictAccel, () => {
      const isRecording = getPillState() === 'recording';
      if (isRecording) {
        setPillState('idle');
        sendHotkey('f9_stop');
        if (f9TapTimer) {
          clearTimeout(f9TapTimer);
          f9TapTimer = null;
        }
        f9TapCount = 0;
        return;
      }
      f9TapCount += 1;
      if (f9TapTimer) clearTimeout(f9TapTimer);
      f9TapTimer = setTimeout(flushF9Taps, TAP_WINDOW_MS);
    });
    results.push(`Dictation+Agent=${dictOk}(${dictAccel})`);
    if (!dictOk) console.error(`[Shortcuts] FAILED to register dictation ${dictAccel}`);
  } else {
    // Separate keys — no tap counting
    const dictOk = globalShortcut.register(dictAccel, () => {
      const isRecording = getPillState() === 'recording';
      if (isRecording) {
        setPillState('idle');
        sendHotkey('f9_stop');
        return;
      }
      setPillState('recording');
      sendHotkey('f9_start');
    });
    results.push(`Dictation=${dictOk}(${dictAccel})`);
    if (!dictOk) console.error(`[Shortcuts] FAILED to register dictation ${dictAccel}`);

    const agentOk = globalShortcut.register(agentAccel, () => {
      sendHotkey('f9_toggle_agent');
    });
    results.push(`Agent=${agentOk}(${agentAccel})`);
    if (!agentOk) console.error(`[Shortcuts] FAILED to register agent ${agentAccel}`);
  }

  // Task hotkey
  const taskAccel = _normalizeAccelerator(cfg.task_voice);
  const taskOk = globalShortcut.register(taskAccel, () => {
    const isRecording = getPillState() === 'recording';
    setPillState(isRecording ? 'idle' : 'recording');
    sendHotkey(isRecording ? 'f10_stop' : 'f10_start');
  });
  results.push(`Task=${taskOk}(${taskAccel})`);
  if (!taskOk) console.error(`[Shortcuts] FAILED to register task hotkey ${taskAccel}`);

  // WizPrompt
  const wizAccel = _normalizeAccelerator(cfg.wizprompt);
  const wizOk = globalShortcut.register(wizAccel, () => {
    sendHotkey('ctrl_shift_space');
  });
  results.push(`WizPrompt=${wizOk}(${wizAccel})`);
  if (!wizOk) console.error(`[Shortcuts] FAILED to register wizprompt ${wizAccel}`);

  // Dismiss
  const dismissAccel = _normalizeAccelerator(cfg.dismiss);
  const dismissOk = globalShortcut.register(dismissAccel, () => {
    if (!overlay.isDestroyed() && overlay.isVisible()) overlay.hide();
    if (getPillState() === 'recording') {
      setPillState('idle');
      sendHotkey('f9_stop');
    }
  });
  results.push(`Dismiss=${dismissOk}(${dismissAccel})`);
  if (!dismissOk) console.error(`[Shortcuts] FAILED to register dismiss ${dismissAccel}`);

  console.log(`[Shortcuts] Registered: ${results.join(' ')}`);
}

export function reloadShortcuts(config?: Partial<ShortcutConfig>): void {
  if (config) {
    saveShortcutConfig(config);
  }
  globalShortcut.unregisterAll();
  if (_windows) {
    registerShortcuts(_windows);
  }
}
