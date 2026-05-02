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
const DISPLAY_EDGE_MARGIN = 100;

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

  if (process.platform === 'linux') {
    // setBounds on Wayland can be ignored by the compositor.
    // setPosition + setSize is more reliable for frameless windows.
    win.setPosition(bounds.x, bounds.y, animate);
    win.setSize(bounds.width, bounds.height, animate);
  } else {
    win.setBounds(bounds, animate);
  }
}

/** Move pill to a display, optionally animating. */
export function repositionPill(
  win: BrowserWindow,
  disp: Display,
  animate: boolean = false,
): void {
  setWindowBounds(win, getPillBounds(disp), animate);
}

/** Move overlay above the pill on a given display, optionally animating. */
export function repositionOverlay(
  overlay: BrowserWindow,
  pill: BrowserWindow,
  disp: Display,
  animate: boolean = false,
): void {
  if (pill.isDestroyed() || overlay.isDestroyed()) return;
  const pillBounds = pill.getBounds();
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

/** Get the Display object for the given id, or fallback to primary. */
export function getDisplayById(id: number): Display {
  const all = screen.getAllDisplays();
  return all.find((d) => d.id === id) ?? screen.getPrimaryDisplay();
}
