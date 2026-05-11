import { BrowserWindow, screen } from 'electron';
import { IPC } from '../renderer/shared/ipc';
import type { AppState, PillNoticePayload } from '../renderer/shared/ipc';
import { getCursorDisplay, getPillBounds } from './positioning';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';

// Single source of truth for pill state in the main process.
// Renderer is a pure projection — it only ever receives SET_STATE.
// This lets F9 be a reliable toggle (we know whether we're already recording).

let currentState: AppState = 'idle';
let pillWin: BrowserWindow | null = null;

// Baseline pill dimensions (match windows.ts PILL_W / PILL_H).
const BASE_W = 86;
const BASE_H = 44;
const EXPANDED_W = 360;
const EXPANDED_H = 52;
const BOTTOM_PAD = 14;
const MAX_NOTIF_W = 480;
const MAX_NOTIF_H = 260;
const PREVIEW_W = 460;
const PREVIEW_H = 200;

let restoreTimer: ReturnType<typeof setTimeout> | null = null;
let notificationSized = false;

// ─── Pill notifications toggle ─────────────────────────────
let pillNotificationsEnabled = true;

function _loadPillNotificationsSetting(): boolean {
  try {
    const settingsPath = path.join(process.cwd(), 'data', 'settings.json');
    if (!existsSync(settingsPath)) return true;
    const raw = readFileSync(settingsPath, 'utf-8');
    const data = JSON.parse(raw);
    return data.pill_notifications !== false;
  } catch {
    return true;
  }
}

pillNotificationsEnabled = _loadPillNotificationsSetting();

export function setPillNotificationsEnabled(enabled: boolean): void {
  pillNotificationsEnabled = enabled;
  // Persist to settings.json so it survives app restarts
  try {
    const settingsPath = path.join(process.cwd(), 'data', 'settings.json');
    const dir = path.dirname(settingsPath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    let data: Record<string, unknown> = {};
    if (existsSync(settingsPath)) {
      data = JSON.parse(readFileSync(settingsPath, 'utf-8'));
    }
    data.pill_notifications = enabled;
    writeFileSync(settingsPath, JSON.stringify(data, null, 2));
  } catch {
    // Non-fatal — setting just won't persist across restarts
  }
}

export function isPillNotificationsEnabled(): boolean {
  return pillNotificationsEnabled;
}

export function bindPill(win: BrowserWindow): void {
  pillWin = win;
}

export function getPillState(): AppState {
  return currentState;
}

export function setPillState(state: AppState): void {
  currentState = state;
  if (pillWin && !pillWin.isDestroyed()) {
    try {
      pillWin.webContents.send(IPC.SET_STATE, state);
    } catch {
      // Renderer frame may be disposed on Linux/Wayland — ignore.
    }
  }
}

function resizePill(width: number, height: number): void {
  if (!pillWin || pillWin.isDestroyed()) return;
  try {
    const disp = getCursorDisplay();
    const bounds = getPillBounds(disp, width, height);
    pillWin.setBounds(bounds, false);
  } catch {
    // Window may be in a bad state on Linux/Wayland.
  }
}

export function showPillNotice(payload: PillNoticePayload): void {
  if (!pillNotificationsEnabled) return;
  if (!pillWin || pillWin.isDestroyed()) return;
  try {
    // Don't clobber a persistent notification with an ephemeral notice.
    if (notificationSized) {
      pillWin.webContents.send(IPC.PILL_NOTICE, payload);
      return;
    }
  // Cancel any in-flight restore so overlapping notices don't collapse early.
  if (restoreTimer) {
    clearTimeout(restoreTimer);
    restoreTimer = null;
  }
    resizePill(EXPANDED_W, EXPANDED_H);
    pillWin.webContents.send(IPC.PILL_NOTICE, payload);

    const duration = Math.max(800, payload.duration_ms || 2600);
    restoreTimer = setTimeout(() => {
      restoreTimer = null;
      if (!notificationSized) resizePill(BASE_W, BASE_H);
    }, duration);
  } catch {
    // Renderer frame may be disposed on Linux/Wayland — ignore.
  }
}

export function restorePillSize(): void {
  if (restoreTimer) {
    clearTimeout(restoreTimer);
    restoreTimer = null;
  }
  notificationSized = false;
  resizePill(BASE_W, BASE_H);
}

/**
 * Render-driven pill resizer for persistent notifications (task_saved,
 * due_alert, etc.). Unlike `showPillNotice`, this has no auto-restore —
 * the renderer calls it with `null` to collapse back to baseline.
 */
export function setPillNotificationSize(
  size: { width: number; height: number } | null,
): void {
  if (!pillNotificationsEnabled) return;
  if (!pillWin || pillWin.isDestroyed()) return;
  try {
    if (restoreTimer) {
      clearTimeout(restoreTimer);
      restoreTimer = null;
    }
    if (!size) {
      notificationSized = false;
      resizePill(BASE_W, BASE_H);
      return;
    }
    notificationSized = true;
    const w = Math.max(BASE_W, Math.min(MAX_NOTIF_W, Math.round(size.width)));
    const h = Math.max(BASE_H, Math.min(MAX_NOTIF_H, Math.round(size.height)));
    resizePill(w, h);
  } catch {
    // Renderer frame may be disposed on Linux/Wayland — ignore.
  }
}

export function isPillNotificationSized(): boolean {
  return notificationSized;
}

/** Expand the pill to dictation preview dimensions. */
export function setDictationPreviewSize(active: boolean): void {
  if (!pillWin || pillWin.isDestroyed()) return;
  try {
    if (restoreTimer) {
      clearTimeout(restoreTimer);
      restoreTimer = null;
    }
    if (!active) {
      notificationSized = false;
      resizePill(BASE_W, BASE_H);
      return;
    }
    notificationSized = true;
    resizePill(PREVIEW_W, PREVIEW_H);
  } catch {
    // Renderer frame may be disposed on Linux/Wayland — ignore.
  }
}
