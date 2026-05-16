import { app, BrowserWindow, globalShortcut, screen, session, type Display } from 'electron';
import { createPillWindow, createOverlayWindow, setLinuxSticky } from './windows';
import { registerIpcHandlers } from './ipc';
import { registerShortcuts } from './shortcuts';
import { bindPill } from './pillState';
import {
  getCursorDisplay,
  hasCursorChangedDisplay,
  getDisplayById,
  repositionPill,
  repositionOverlay,
  getPillBounds,
  getOverlayBounds,
  animateSlideIn,
} from './positioning';
import {
  loadSavedPosition,
  setEdgePosition,
  getEdgePosition,
} from './orbit';
import { readFileSync, existsSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { sendBridgeMessage, closeBridge } from './bridge';
import { dragState } from './dragState';
import { IPC } from '../renderer/shared/ipc';
import {
  getLastCursorDisplayId,
  setLastCursorDisplayId,
} from './monitorState';
import {
  startWorkspaceWatcher,
  stopWorkspaceWatcher,
  getWindowDesktop,
  moveAllWindowsToDesktop,
  findWindowIdsByTitle,
} from './workspaceWatcher';

let pill: BrowserWindow;
let overlay: BrowserWindow;
let topReassertTimer: ReturnType<typeof setInterval> | null = null;
let cmdWatchTimer: ReturnType<typeof setInterval> | null = null;
let wsHeartbeatTimer: ReturnType<typeof setInterval> | null = null;
let monitorFollowTimer: ReturnType<typeof setInterval> | null = null;





/** Reposition both pill and overlay to the display under the cursor. */
function moveToDisplay(disp: Display, animate: boolean = false): void {
  if (!pill.isDestroyed()) {
    repositionPill(pill, disp, animate);
  }
  if (!overlay.isDestroyed()) {
    repositionOverlay(overlay, pill, disp, animate);
  }
}

/** Ensure overlay is on the right display and next to the pill before showing. */
function showOverlay(): void {
  if (overlay.isDestroyed()) return;
  const disp = getCursorDisplay();
  if (disp.id !== getLastCursorDisplayId()) {
    setLastCursorDisplayId(disp.id);
    moveToDisplay(disp, false); // snap, don't animate on show
  } else if (!pill.isDestroyed()) {
    // Pill may have moved on the same display — keep overlay adjacent
    repositionOverlay(overlay, pill, screen.getDisplayMatching(pill.getBounds()), false);
  }
  overlay.show();
  overlay.focus();
}

// File-based IPC with Python backend
const COMMAND_FILE = (() => {
  // Allow Python launcher to pass absolute path via env var
  const envPath = process.env.WHIZTANT_OVERLAY_CMD;
  if (envPath && existsSync(envPath)) return envPath;
  try {
    // out/main/index.js -> whiztant-overlay -> ui -> project root
    const projectRoot = path.resolve(app.getAppPath(), '..', '..', '..');
    const candidate = path.join(projectRoot, 'ui', '.overlay_cmd');
    if (existsSync(candidate)) return candidate;
    // Fallback: if app is packaged, userData may be the only writable place
    return path.join(app.getPath('userData'), '.overlay_cmd');
  } catch {
    return path.join(app.getPath('userData'), '.overlay_cmd');
  }
})();

function handleCommandFile(): void {
  if (!existsSync(COMMAND_FILE)) return;
  try {
    const cmd = readFileSync(COMMAND_FILE, 'utf8').trim();
    if (!cmd) return;

    // Clear immediately so the command is not re-executed on the next poll.
    // Use best-effort: if the file is locked by Python, ignore the error.
    try {
      writeFileSync(COMMAND_FILE, '', 'utf8');
    } catch {
      // ignore
    }

    if (cmd === 'show') {
      showOverlay();
    } else if (cmd === 'toggle') {
      if (overlay.isDestroyed()) return;
      if (overlay.isVisible()) {
        // On Linux the overlay is a persistent HUD — never hide, just refocus
        if (process.platform === 'linux') {
          overlay.focus();
        } else {
          overlay.hide();
        }
      } else {
        showOverlay();
      }
    } else if (cmd === 'collapse' || cmd === 'hide') {
      // On Linux the overlay stays visible; hide commands are ignored
      if (process.platform !== 'linux' && !overlay.isDestroyed() && overlay.isVisible()) {
        overlay.hide();
      }
    }
  } catch {
    // Ignore read errors
  }
}

function startBridgeHeartbeat(): void {
  wsHeartbeatTimer = setInterval(() => {
    sendBridgeMessage({ type: 'ping' });
  }, 5000);
}

function bootstrap(): void {
  // Auto-grant microphone access to our renderers so the pill's waveform
  // can read live voice levels without a visible permission dialog.
  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    if (permission === 'media' || permission === 'mediaKeySystem') {
      callback(true);
    } else {
      callback(false);
    }
  });

  console.log('[Overlay] COMMAND_FILE resolved to:', COMMAND_FILE);

  // Start on the display the cursor is currently on (not hardcoded primary).
  const initialDisp = getCursorDisplay();
  setLastCursorDisplayId(initialDisp.id);

  const savedPos = loadSavedPosition();
  setEdgePosition(savedPos);

  pill = createPillWindow(initialDisp);
  overlay = createOverlayWindow(initialDisp, pill);

  bindPill(pill);
  registerIpcHandlers({ pill, overlay, showOverlay, setLastCursorDisplayId });
  registerShortcuts({ pill, overlay, showOverlay });

  // Send initial edge to pill renderer once it loads
  pill.webContents.on('did-finish-load', () => {
    try {
      pill.webContents.send(IPC.PILL_EDGE_CHANGED, getEdgePosition().edge);
    } catch { /* renderer may not be ready yet */ }
  });



  // Poll command file for IPC from Python backend
  cmdWatchTimer = setInterval(handleCommandFile, 100);

  // Re-assert always-on-top every 2s so the pill and overlay remain above newly-launched
  // apps or system panes that temporarily take priority. This does NOT create
  // extra windows — it only re-applies a flag on the existing windows.
  topReassertTimer = setInterval(() => {
    if (!pill.isDestroyed()) {
      pill.setAlwaysOnTop(true, 'screen-saver');
      pill.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: false });
      setLinuxSticky(pill, 'whiztant-pill');
    }
    if (!overlay.isDestroyed()) {
      overlay.setAlwaysOnTop(true, 'screen-saver');
      overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: false });
      setLinuxSticky(overlay, 'whiztant-overlay');
    }
  }, 2000);

  // Follow the cursor across monitors: smoothly animate pill + overlay to the
  // display the cursor is on. Poll every 250 ms for responsive transitions.
  monitorFollowTimer = setInterval(() => {
    const nextId = hasCursorChangedDisplay(getLastCursorDisplayId());
    if (nextId !== null && nextId !== getLastCursorDisplayId()) {
      setLastCursorDisplayId(nextId);
      const disp = getDisplayById(nextId);
      moveToDisplay(disp, true); // animate for smooth multi-monitor transition
    }
  }, 250);

  // Watch virtual-desktop changes on Linux and move pill + overlay to the
  // active desktop with a slide-in animation when they get left behind.
  console.log('[Main] Platform:', process.platform);
  if (process.platform === 'linux') {
    console.log('[Main] Starting workspace watcher on Linux...');
    startWorkspaceWatcher(async (event) => {
      console.log('[Main] Workspace event:', event);
      if (pill.isDestroyed()) {
        console.warn('[Main] Pill is destroyed, skipping');
        return;
      }

      // Search by window title — more reliable than PID because Chromium
      // creates X11 windows from child processes, not the main process.
      const pillIds = await findWindowIdsByTitle('whiztant-pill');
      console.log(`[Main] Pill window IDs:`, pillIds);
      if (!pillIds.length) {
        console.warn('[Main] No pill window found. Is Electron running on native Wayland?');
        console.warn('[Main] Try running with: ELECTRON_OZONE_PLATFORM_HINT=x11');
        return;
      }

      const pillDesktop = await getWindowDesktop(pillIds[0]);
      console.log(`[Main] Pill window ${pillIds[0]} desktop: ${pillDesktop}, target: ${event.desktop}`);
      if (pillDesktop === null) {
        console.warn('[Main] Could not determine pill desktop');
        return;
      }

      if (pillDesktop === event.desktop) {
        console.log('[Main] Already on correct desktop, no move needed');
        return;
      }

      console.log(`[Main] Moving windows from desktop ${pillDesktop} to ${event.desktop}`);

      // Fade out to avoid flash during the move
      pill.setOpacity(0);
      if (!overlay.isDestroyed() && overlay.isVisible()) {
        overlay.setOpacity(0);
      }

      // Move all whiztant windows to the new desktop
      const moved = await moveAllWindowsToDesktop(event.desktop);
      console.log('[Main] Move result:', moved);

      // Compute target bounds on the current display
      const disp = getCursorDisplay();
      const pb = getPillBounds(disp, pill.getBounds().width, pill.getBounds().height);
      const ob = !overlay.isDestroyed() && overlay.isVisible()
        ? getOverlayBounds(disp, pb)
        : null;

      // Slide in from the direction the user swiped FROM.
      // Swiped right (desktop index increased) → enter from left.
      const slideDir = event.direction === 'right' ? 'from-left' : 'from-right';
      console.log(`[Main] Animating slide-in from ${slideDir}`);
      animateSlideIn(pill, pb, slideDir, 280);
      if (ob) animateSlideIn(overlay, ob, slideDir, 280);

      // Restore opacity after the off-screen snap has been applied
      setTimeout(() => {
        if (!pill.isDestroyed()) pill.setOpacity(1);
        if (!overlay.isDestroyed() && overlay.isVisible()) overlay.setOpacity(1);
        console.log('[Main] Opacity restored');
      }, 60);
    });
  } else {
    console.log('[Main] Not Linux, skipping workspace watcher');
  }

  // Heartbeat to Python bridge so launcher knows we are alive
  startBridgeHeartbeat();
}

app.whenReady().then(bootstrap);

// Don't quit when all windows close — the pill is resident.
// Quit is only allowed via IPC (tray / context menu / settings).
app.on('window-all-closed', () => {
  // intentionally empty on all platforms
});

app.on('will-quit', () => {
  if (topReassertTimer) clearInterval(topReassertTimer);
  if (cmdWatchTimer) clearInterval(cmdWatchTimer);
  if (wsHeartbeatTimer) clearInterval(wsHeartbeatTimer);
  if (monitorFollowTimer) clearInterval(monitorFollowTimer);
  stopWorkspaceWatcher();
  closeBridge();
  globalShortcut.unregisterAll();
});
