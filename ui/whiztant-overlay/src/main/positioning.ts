import { screen, type Display, type Rectangle, BrowserWindow } from 'electron';
import {
  getEdgePosition,
  getPillBoundsFromEdge,
  getOverlayBoundsFromEdge,
} from './orbit';

// ── Window dimensions (mirror windows.ts) ───────────────────────
const PILL_W = 86;
const PILL_H = 44;
const OVERLAY_W = 360;
const OVERLAY_H = 480;
const PILL_BOTTOM_PAD = 14;
const PILL_GAP = 16;

// Hysteresis margin (px) to avoid flickering when cursor is on display edge.
const DISPLAY_EDGE_MARGIN = 60;

// ── Custom smooth animation ─────────────────────────────────────
const ACTIVE_ANIMATIONS = new Map<number, ReturnType<typeof setTimeout>>();

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Smoothly tween a BrowserWindow from its current bounds to target bounds
 * using a custom ease-out-cubic curve. Cancels any existing animation on
 * the same window so transitions never fight each other.
 */
export function animateWindowBounds(
  win: BrowserWindow,
  target: Rectangle,
  durationMs: number = 350,
): void {
  if (win.isDestroyed()) return;

  const winId = win.id;
  const existing = ACTIVE_ANIMATIONS.get(winId);
  if (existing) {
    clearTimeout(existing);
    ACTIVE_ANIMATIONS.delete(winId);
  }

  const start = win.getBounds();
  const startTime = Date.now();

  const tick = (): void => {
    if (win.isDestroyed()) {
      ACTIVE_ANIMATIONS.delete(winId);
      return;
    }

    const elapsed = Date.now() - startTime;
    const rawProgress = Math.min(elapsed / durationMs, 1);
    const progress = easeOutCubic(rawProgress);

    const next: Rectangle = {
      x: Math.round(start.x + (target.x - start.x) * progress),
      y: Math.round(start.y + (target.y - start.y) * progress),
      width: Math.round(start.width + (target.width - start.width) * progress),
      height: Math.round(start.height + (target.height - start.height) * progress),
    };

    if (process.platform === 'linux') {
      win.setPosition(next.x, next.y, false);
      win.setSize(next.width, next.height, false);
    } else {
      win.setBounds(next, false);
    }

    if (rawProgress < 1) {
      ACTIVE_ANIMATIONS.set(winId, setTimeout(tick, 16));
    } else {
      ACTIVE_ANIMATIONS.delete(winId);
    }
  };

  tick();
}

// ── Helpers ─────────────────────────────────────────────────────

export function getCursorDisplay(): Display {
  const point = screen.getCursorScreenPoint();
  return screen.getDisplayNearestPoint(point);
}

export function centerX(windowWidth: number, area: Rectangle): number {
  return area.x + Math.round((area.width - windowWidth) / 2);
}

/** Pill bounds from the current edge position. */
export function getPillBounds(
  disp: Display,
  width: number = PILL_W,
  height: number = PILL_H,
): Rectangle {
  const pos = getEdgePosition();
  // On left/right edges the idle pill stands vertically.
  // Expanded notifications keep their original orientation.
  if ((pos.edge === 'left' || pos.edge === 'right') && width === PILL_W && height === PILL_H) {
    return getPillBoundsFromEdge(disp, pos, height, width, PILL_BOTTOM_PAD);
  }
  return getPillBoundsFromEdge(disp, pos, width, height, PILL_BOTTOM_PAD);
}

/** Overlay bounds adjacent to the pill from the current edge position. */
export function getOverlayBounds(
  disp: Display,
  pillBounds: Rectangle,
  width: number = OVERLAY_W,
  height: number = OVERLAY_H,
): Rectangle {
  return getOverlayBoundsFromEdge(disp, pillBounds, getEdgePosition(), width, height, PILL_GAP);
}

/**
 * Reposition a BrowserWindow to the given bounds.
 * On Linux Wayland some compositors ignore `setBounds`; we split into
 * `setPosition` + `setSize` which is more reliable for frameless windows.
 */
export function setWindowBounds(
  win: BrowserWindow,
  bounds: Rectangle,
  animate: boolean = false,
): void {
  if (win.isDestroyed()) return;

  if (animate) {
    animateWindowBounds(win, bounds, 350);
    return;
  }

  if (process.platform === 'linux') {
    // setBounds on Wayland can be ignored by the compositor.
    // setPosition + setSize is more reliable for frameless windows.
    win.setPosition(bounds.x, bounds.y, false);
    win.setSize(bounds.width, bounds.height, false);
  } else {
    win.setBounds(bounds, false);
  }
}

/** Move pill to a display, optionally animating. */
export function repositionPill(
  win: BrowserWindow,
  disp: Display,
  animate: boolean = false,
): void {
  const currentBounds = win.getBounds();
  setWindowBounds(win, getPillBounds(disp, currentBounds.width, currentBounds.height), animate);
}

/** Move overlay above the pill on a given display, optionally animating. */
export function repositionOverlay(
  overlay: BrowserWindow,
  pill: BrowserWindow,
  disp: Display,
  animate: boolean = false,
): void {
  if (pill.isDestroyed() || overlay.isDestroyed()) return;
  const currentBounds = pill.getBounds();
  // When animating to a new display, compute the target pill bounds at its
  // current size so the overlay animates to the correct final position.
  const pillBounds = animate
    ? getPillBounds(disp, currentBounds.width, currentBounds.height)
    : currentBounds;
  setWindowBounds(overlay, getOverlayBounds(disp, pillBounds), animate);
}

/** Detect whether the cursor has moved to a *different* display with hysteresis. */
export function hasCursorChangedDisplay(prevId: number | null): number | null {
  const point = screen.getCursorScreenPoint();
  const disp = screen.getDisplayNearestPoint(point);

  // Hysteresis: ignore if cursor is very close to the edge of the new display.
  const work = disp.workArea;
  const nearEdgeX =
    point.x < work.x + DISPLAY_EDGE_MARGIN ||
    point.x > work.x + work.width - DISPLAY_EDGE_MARGIN;
  const nearEdgeY =
    point.y < work.y + DISPLAY_EDGE_MARGIN ||
    point.y > work.y + work.height - DISPLAY_EDGE_MARGIN;

  if (nearEdgeX || nearEdgeY) {
    // Cursor is on the edge; only switch if we were already on this display.
    if (prevId === disp.id) return disp.id;
    return prevId; // stay on previous to avoid flicker
  }

  return disp.id !== prevId ? disp.id : prevId;
}

/**
 * Animate a window sliding in from off-screen in a given direction.
 * The window is first snapped to an off-screen start position, then
 * eased to the target bounds using the existing tween engine.
 */
export function animateSlideIn(
  win: BrowserWindow,
  target: Rectangle,
  direction: 'from-left' | 'from-right' | 'from-top' | 'from-bottom',
  durationMs: number = 300,
): void {
  if (win.isDestroyed()) return;

  const start: Rectangle = { ...target };
  const pad = 20;

  switch (direction) {
    case 'from-left':
      start.x = target.x - target.width - pad;
      break;
    case 'from-right': {
      const disp = screen.getDisplayMatching(target);
      start.x = disp.workArea.x + disp.workArea.width + pad;
      break;
    }
    case 'from-top':
      start.y = target.y - target.height - pad;
      break;
    case 'from-bottom': {
      const disp = screen.getDisplayMatching(target);
      start.y = disp.workArea.y + disp.workArea.height + pad;
      break;
    }
  }

  // Snap to off-screen start (no animation)
  setWindowBounds(win, start, false);
  // Tween to final position
  animateWindowBounds(win, target, durationMs);
}

/** Get the Display object for the given id, or fallback to primary. */
export function getDisplayById(id: number): Display {
  const all = screen.getAllDisplays();
  return all.find((d) => d.id === id) ?? screen.getPrimaryDisplay();
}
