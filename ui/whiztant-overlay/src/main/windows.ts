import { BrowserWindow, screen, app, type Rectangle, type Display } from 'electron';
import path from 'node:path';
import { exec, execSync } from 'node:child_process';
import { VITE_DEV_SERVER_URL, RENDERER_DIST, PRELOAD_PATH } from './utils';
import { getPillBounds, getOverlayBounds, setWindowBounds, getCursorDisplay } from './positioning';
import { setLastCursorDisplayId } from './monitorState';
import type { EdgePosition } from './orbit';

// ── Linux WM compatibility helpers ──────────────────────────────
function safeSetAlwaysOnTop(win: BrowserWindow): void {
  try {
    win.setAlwaysOnTop(true, 'screen-saver');
  } catch {
    // Some Linux WMs don't support 'screen-saver' level
    try {
      win.setAlwaysOnTop(true, 'normal');
    } catch {
      win.setAlwaysOnTop(true);
    }
  }
}

// ── Window dimensions ───────────────────────────────────────────
// Pill is intentionally tiny so there is no invisible clickable area around it.
const PILL_W = 60;
const PILL_H = 18;
const OVERLAY_W = 360;
const OVERLAY_H = 480;
const SETTINGS_W = 300;
const SETTINGS_H = 420;
const TASK_PANEL_W = 340;
const TASK_PANEL_H = 420;
const TASK_PANEL_MIN_H = 320;
// Distance of pill from bottom of screen.
const PILL_BOTTOM_PAD = 14;
// Gap between the pill and panels stacked above it.
const PILL_GAP = 16;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max));
}

function centerX(windowWidth: number, screenWidth: number): number {
  return Math.round((screenWidth - windowWidth) / 2);
}

function centerXInArea(windowWidth: number, area: Rectangle): number {
  return area.x + Math.round((area.width - windowWidth) / 2);
}

function stampAutoHidden(win: BrowserWindow): void {
  (win as BrowserWindow & { lastAutoHiddenAt?: number }).lastAutoHiddenAt = Date.now();
}

function isWindowInOverlayGroup(
  candidate: BrowserWindow | null | undefined,
  overlay: BrowserWindow,
  pill?: BrowserWindow,
): boolean {
  if (!candidate || candidate.isDestroyed()) return false;
  if (candidate === overlay) return true;
  if (pill && !pill.isDestroyed() && candidate === pill) return true;
  return candidate.getParentWindow() === overlay;
}

// ── X11 window-type enforcement (Linux only) ─────────────────────
function getX11WindowId(win: BrowserWindow): string | null {
  try {
    const handle = win.getNativeWindowHandle();
    if (!handle || handle.length < 4) return null;
    return handle.readUInt32LE(0).toString(16);
  } catch {
    return null;
  }
}

function findWindowIdByTitle(title: string): string | null {
  try {
    const out = execSync(`xdotool search --name "${title}"`, { encoding: 'utf-8', timeout: 500 });
    const lines = out.trim().split('\n').filter((l) => l.length > 0);
    if (lines.length) return lines[0].trim();
  } catch { /* ignore */ }
  return null;
}

function applyX11FlagsSync(win: BrowserWindow, title: string): void {
  if (process.platform !== 'linux') return;
  let id = findWindowIdByTitle(title);
  if (!id) id = getX11WindowId(win);
  if (!id) {
    console.warn(`[LinuxFlags] Could not find X11 window ID for "${title}"`);
    return;
  }
  console.log(`[LinuxFlags] Applying flags to 0x${id} ("${title}")`);
  const cmds = [
    `xprop -id 0x${id} -f _NET_WM_WINDOW_TYPE 32a -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_DOCK`,
    `xprop -id 0x${id} -f _NET_WM_STATE 32a -set _NET_WM_STATE _NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_SKIP_PAGER`,
    `xprop -id 0x${id} -f _NET_WM_DESKTOP 32c -set _NET_WM_DESKTOP 0xFFFFFFFF`,
    `xdotool set_desktop_for_window 0x${id} -1`,
    `wmctrl -i -r 0x${id} -b add,sticky`,
    `wmctrl -i -r 0x${id} -b add,skip_taskbar`,
  ];
  for (const cmd of cmds) {
    try {
      execSync(cmd, { timeout: 500 });
      console.log(`[LinuxFlags] OK: ${cmd.split(' ').slice(0, 4).join(' ')}...`);
    } catch (e: any) {
      console.warn(`[LinuxFlags] FAILED: ${cmd.split(' ').slice(0, 4).join(' ')}... (${e.message || 'unknown'})`);
    }
  }
}

export function setLinuxSticky(win: BrowserWindow, title: string): void {
  if (process.platform !== 'linux') return;
  const id = findWindowIdByTitle(title) || getX11WindowId(win);
  if (!id) return;
  const cmds = [
    `xprop -id 0x${id} -f _NET_WM_DESKTOP 32c -set _NET_WM_DESKTOP 0xFFFFFFFF`,
    `xdotool set_desktop_for_window 0x${id} -1`,
    `wmctrl -i -r 0x${id} -b add,sticky`,
  ];
  for (const cmd of cmds) {
    try { exec(cmd, () => {}); } catch { /* ignore */ }
  }
}

// ─── PILL ───────────────────────────────────────────────────────
export function createPillWindow(disp: Display, _pos?: EdgePosition): BrowserWindow {
  const isLinux = process.platform === 'linux';
  const bounds = getPillBounds(disp);
  const win = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    focusable: true,
    hasShadow: false,
    title: 'whiztant-pill',
    // Use 'notification' type on Linux so the pill appears as a floating HUD
    // rather than a desktop window in taskbars / alt-tab.
    ...(isLinux ? { type: 'toolbar' as const } : { type: 'toolbar' as const }),
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  safeSetAlwaysOnTop(win);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: false });

  // On Linux Wayland the compositor may ignore constructor x/y.
  // Use setPosition + setSize (more reliable than setBounds on Wayland).
  if (process.platform === 'linux') {
    win.once('ready-to-show', () => {
      if (!win.isDestroyed()) {
        setWindowBounds(win, getPillBounds(disp), false);
        applyX11FlagsSync(win, 'whiztant-pill');
      }
    });
  }

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(`${VITE_DEV_SERVER_URL}/pill/index.html`);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'pill/index.html'));
  }

  // Pill MUST never hide. No blur handler here — intentional.
  return win;
}

// ─── OVERLAY (tune panel) ───────────────────────────────────────
export function createOverlayWindow(disp: Display, pill?: BrowserWindow, _pos?: EdgePosition): BrowserWindow {
  // Use theoretical pill bounds for constructor; actual pill bounds will be
  // applied in ready-to-show once the pill has been positioned by the WM.
  const pillBounds = pill && !pill.isDestroyed() ? pill.getBounds() : getPillBounds(disp);
  const bounds = getOverlayBounds(disp, pillBounds);

  const win = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    focusable: true,
    fullscreenable: false,
    maximizable: false,
    minimizable: false,
    show: process.platform === 'linux',
    hasShadow: false,
    title: 'whiztant-overlay',
    ...(process.platform === 'linux' ? { type: 'toolbar' as const } : {}),
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  safeSetAlwaysOnTop(win);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: false });
  win.setFullScreenable(false);
  win.setSkipTaskbar(true);

  // On Linux Wayland the compositor may ignore constructor x/y.
  // Use setPosition + setSize (more reliable than setBounds on Wayland).
  if (process.platform === 'linux') {
    win.once('ready-to-show', () => {
      if (!win.isDestroyed()) {
        const actualPillBounds = pill && !pill.isDestroyed() ? pill.getBounds() : getPillBounds(disp);
        setWindowBounds(win, getOverlayBounds(disp, actualPillBounds), false);
        win.setMovable(false);
        win.setFullScreenable(false);
        win.setMaximizable(false);
        win.setMinimizable(false);
        applyX11FlagsSync(win, 'whiztant-overlay');
      }
    });
  }

  // Blur auto-hide: clicking outside the overlay group closes the overlay.
  // If the click landed on a different monitor, smoothly animate the pill +
  // overlay there before hiding so the next open is on the right display.
  win.on('blur', () => {
    setTimeout(() => {
      const focused = BrowserWindow.getFocusedWindow();
      if (isWindowInOverlayGroup(focused, win, pill)) return;

      if (pill && !pill.isDestroyed()) {
        const cursorDisp = getCursorDisplay();
        const currentDisp = screen.getDisplayMatching(pill.getBounds());
        if (cursorDisp.id !== currentDisp.id) {
          const pillBounds = pill.getBounds();
          const targetPillBounds = getPillBounds(cursorDisp, pillBounds.width, pillBounds.height);
          const targetOverlayBounds = getOverlayBounds(cursorDisp, targetPillBounds);
          setWindowBounds(pill, targetPillBounds, true);
          setWindowBounds(win, targetOverlayBounds, true);
          setLastCursorDisplayId(cursorDisp.id);
        }
      }

      if (!win.isDestroyed() && win.isVisible()) {
        stampAutoHidden(win);
        win.hide();
      }
    }, 0);
  });

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(`${VITE_DEV_SERVER_URL}/overlay/index.html`);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'overlay/index.html'));
  }

  return win;
}

// ─── TASK PANEL ─────────────────────────────────────────────────
export function createTaskPanelWindow(taskId: string, taskJson: string, overlay: BrowserWindow): BrowserWindow {
  let taskTextLength = 0;
  try {
    const task = JSON.parse(taskJson) as { text?: string; content?: string | null };
    taskTextLength = `${task.content || task.text || ''}`.trim().length;
  } catch {
    taskTextLength = 0;
  }
  const overlayBounds = overlay.getBounds();
  const display = screen.getDisplayMatching(overlayBounds);
  const workArea = display.workArea;
  const gap = 24;
  const panelWidth = Math.min(overlayBounds.width, TASK_PANEL_W);
  const maxPanelHeight = Math.min(overlayBounds.height, TASK_PANEL_H);
  const estimatedHeight = clamp(TASK_PANEL_MIN_H + Math.ceil(taskTextLength / 6), TASK_PANEL_MIN_H, maxPanelHeight);
  const preferredX = overlayBounds.x + overlayBounds.width + gap;
  // Always open to the right of the overlay; clamp to screen right edge if needed.
  const x = Math.min(preferredX, workArea.x + workArea.width - panelWidth);
  const y = Math.max(
    workArea.y,
    Math.min(overlayBounds.y, workArea.y + workArea.height - estimatedHeight),
  );
  const route = `#/task-panel?task=${encodeURIComponent(taskJson)}`;

  const win = new BrowserWindow({
    width: panelWidth,
    height: estimatedHeight,
    minWidth: panelWidth,
    maxWidth: panelWidth,
    minHeight: TASK_PANEL_MIN_H,
    maxHeight: maxPanelHeight,
    x,
    y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    hasShadow: false,
    title: `task-panel-${taskId}`,
    parent: overlay,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  safeSetAlwaysOnTop(win);
  win.on('ready-to-show', () => {
    if (!win.isDestroyed()) {
      if (!overlay.isDestroyed()) overlay.show();
      win.show();
      win.focus();
    }
  });
  win.on('blur', () => {
    setTimeout(() => {
      const focused = BrowserWindow.getFocusedWindow();
      if (isWindowInOverlayGroup(focused, overlay)) return;
      if (!win.isDestroyed()) {
        win.close();
      }
      if (!overlay.isDestroyed() && overlay.isVisible()) {
        stampAutoHidden(overlay);
        overlay.hide();
      }
    }, 0);
  });
  win.on('closed', () => {
    if (!overlay.isDestroyed() && overlay.isVisible()) {
      stampAutoHidden(overlay);
      overlay.hide();
    }
  });

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(`${VITE_DEV_SERVER_URL}/overlay/index.html${route}`);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'overlay/index.html'), { hash: route.slice(1) });
  }

  return win;
}

// ─── STREAK PANEL ───────────────────────────────────────────────
const STREAK_PANEL_W = 340;
const STREAK_PANEL_H = 480;
const STREAK_PANEL_MIN_H = 320;

export function createStreakPanelWindow(streakJson: string, overlay: BrowserWindow): BrowserWindow {
  const overlayBounds = overlay.getBounds();
  const display = screen.getDisplayMatching(overlayBounds);
  const workArea = display.workArea;
  const gap = 24;
  const panelWidth = Math.min(overlayBounds.width, STREAK_PANEL_W);
  const maxPanelHeight = Math.min(overlayBounds.height, STREAK_PANEL_H);
  const estimatedHeight = STREAK_PANEL_MIN_H;
  const preferredX = overlayBounds.x + overlayBounds.width + gap;
  // Always open to the right of the overlay; clamp to screen right edge if needed.
  const x = Math.min(preferredX, workArea.x + workArea.width - panelWidth);
  const y = Math.max(
    workArea.y,
    Math.min(overlayBounds.y, workArea.y + workArea.height - estimatedHeight),
  );
  const route = `#/streak-panel?data=${encodeURIComponent(streakJson)}`;

  const win = new BrowserWindow({
    width: panelWidth,
    height: estimatedHeight,
    minWidth: panelWidth,
    maxWidth: panelWidth,
    minHeight: STREAK_PANEL_MIN_H,
    maxHeight: maxPanelHeight,
    x,
    y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    hasShadow: false,
    title: 'streak-panel',
    parent: overlay,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  safeSetAlwaysOnTop(win);
  win.on('ready-to-show', () => {
    if (!win.isDestroyed()) {
      if (!overlay.isDestroyed()) overlay.show();
      win.show();
      win.focus();
    }
  });
  win.on('blur', () => {
    setTimeout(() => {
      const focused = BrowserWindow.getFocusedWindow();
      if (isWindowInOverlayGroup(focused, overlay)) return;
      if (!win.isDestroyed()) {
        win.close();
      }
      if (!overlay.isDestroyed() && overlay.isVisible()) {
        stampAutoHidden(overlay);
        overlay.hide();
      }
    }, 0);
  });
  win.on('closed', () => {
    if (!overlay.isDestroyed() && overlay.isVisible()) {
      stampAutoHidden(overlay);
      overlay.hide();
    }
  });

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(`${VITE_DEV_SERVER_URL}/overlay/index.html${route}`);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'overlay/index.html'), { hash: route.slice(1) });
  }

  return win;
}

// ─── MEMORY PANEL ───────────────────────────────────────────────
const MEMORY_PANEL_W = 340;
const MEMORY_PANEL_H = 480;
const MEMORY_PANEL_MIN_H = 320;

export function createMemoryPanelWindow(memoryJson: string, overlay: BrowserWindow): BrowserWindow {
  let memoryTextLength = 0;
  try {
    const memory = JSON.parse(memoryJson) as { final_text?: string };
    memoryTextLength = String(memory.final_text || '').trim().length;
  } catch {
    memoryTextLength = 0;
  }
  const overlayBounds = overlay.getBounds();
  const display = screen.getDisplayMatching(overlayBounds);
  const workArea = display.workArea;
  const gap = 24;
  const panelWidth = Math.min(overlayBounds.width, MEMORY_PANEL_W);
  const maxPanelHeight = Math.min(overlayBounds.height, MEMORY_PANEL_H);
  const estimatedHeight = clamp(MEMORY_PANEL_MIN_H + Math.ceil(memoryTextLength / 5), MEMORY_PANEL_MIN_H, maxPanelHeight);
  const preferredX = overlayBounds.x + overlayBounds.width + gap;
  // Always open to the right of the overlay; clamp to screen right edge if needed.
  const x = Math.min(preferredX, workArea.x + workArea.width - panelWidth);
  const y = Math.max(
    workArea.y,
    Math.min(overlayBounds.y, workArea.y + workArea.height - estimatedHeight),
  );
  const route = `#/memory-panel?memory=${encodeURIComponent(memoryJson)}`;

  const win = new BrowserWindow({
    width: panelWidth,
    height: estimatedHeight,
    minWidth: panelWidth,
    maxWidth: panelWidth,
    minHeight: MEMORY_PANEL_MIN_H,
    maxHeight: maxPanelHeight,
    x,
    y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    hasShadow: false,
    title: 'memory-panel',
    parent: overlay,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  safeSetAlwaysOnTop(win);
  win.on('ready-to-show', () => {
    if (!win.isDestroyed()) {
      if (!overlay.isDestroyed()) overlay.show();
      win.show();
      win.focus();
    }
  });
  win.on('blur', () => {
    setTimeout(() => {
      if (!win.isDestroyed()) {
        win.close();
      }
      const focused = BrowserWindow.getFocusedWindow();
      if (!isWindowInOverlayGroup(focused, overlay)) {
        if (!overlay.isDestroyed() && overlay.isVisible()) {
          stampAutoHidden(overlay);
          overlay.hide();
        }
      }
    }, 50);
  });
  win.on('closed', () => {
    if (!overlay.isDestroyed() && overlay.isVisible()) {
      stampAutoHidden(overlay);
      overlay.hide();
    }
  });

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(`${VITE_DEV_SERVER_URL}/overlay/index.html${route}`);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'overlay/index.html'), { hash: route.slice(1) });
  }

  return win;
}

// ─── SETTINGS (merged into overlay renderer; no separate window) ─
