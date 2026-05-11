import { screen, type Display, type Rectangle, app } from 'electron';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';

export type OrbitalEdge = 'top' | 'bottom' | 'left' | 'right';

export interface EdgePosition {
  edge: OrbitalEdge;
  offset: number;
}

let currentPosition: EdgePosition = { edge: 'bottom', offset: 0.5 };

const POSITION_FILE = (() => {
  try {
    const projectRoot = path.resolve(app.getAppPath(), '..', '..');
    return path.join(projectRoot, 'memory', 'overlay_position.json');
  } catch {
    return path.join(app.getPath('userData'), 'overlay_position.json');
  }
})();

export function getEdgePosition(): EdgePosition {
  return currentPosition;
}

export function setEdgePosition(pos: EdgePosition): void {
  currentPosition = pos;
}

/** Distance from a point to each edge of the work area. */
function edgeDistances(
  work: Rectangle,
  cx: number,
  cy: number,
): Record<OrbitalEdge, number> {
  return {
    top: cy - work.y,
    bottom: work.y + work.height - cy,
    left: cx - work.x,
    right: work.x + work.width - cx,
  };
}

/**
 * Given a window position, determine which screen edge it is closest to
 * and compute the offset along that edge (clamped by padding).
 */
export function latchToNearestEdge(
  disp: Display,
  winX: number,
  winY: number,
  winW: number,
  winH: number,
  pad: number,
): EdgePosition {
  const work = disp.workArea;
  const cx = winX + winW / 2;
  const cy = winY + winH / 2;

  const dists = edgeDistances(work, cx, cy);
  let nearestEdge: OrbitalEdge = 'bottom';
  let minDist = dists.bottom;

  if (dists.top < minDist) { minDist = dists.top; nearestEdge = 'top'; }
  if (dists.left < minDist) { minDist = dists.left; nearestEdge = 'left'; }
  if (dists.right < minDist) { minDist = dists.right; nearestEdge = 'right'; }

  let offset: number;
  if (nearestEdge === 'top' || nearestEdge === 'bottom') {
    offset = (cx - work.x) / work.width;
  } else {
    offset = (cy - work.y) / work.height;
  }

  return { edge: nearestEdge, offset: Math.max(0, Math.min(1, offset)) };
}

/** Compute pill bounds from an edge position. */
export function getPillBoundsFromEdge(
  disp: Display,
  pos: EdgePosition,
  width: number,
  height: number,
  pad: number,
): Rectangle {
  const work = disp.workArea;
  const bounds = disp.bounds;
  switch (pos.edge) {
    case 'bottom':
      return {
        x: work.x + Math.round(pos.offset * work.width) - Math.round(width / 2),
        y: work.y + work.height - height - pad,
        width,
        height,
      };
    case 'top':
      return {
        x: work.x + Math.round(pos.offset * work.width) - Math.round(width / 2),
        y: work.y + pad,
        width,
        height,
      };
    case 'left':
      return {
        x: work.x + pad,
        y: work.y + Math.round(pos.offset * work.height) - Math.round(height / 2),
        width,
        height,
      };
    case 'right':
      return {
        x: work.x + work.width - width - pad,
        y: work.y + Math.round(pos.offset * work.height) - Math.round(height / 2),
        width,
        height,
      };
  }
}

/** Compute overlay bounds adjacent to the pill, opening inward. */
export function getOverlayBoundsFromEdge(
  disp: Display,
  pillBounds: Rectangle,
  pos: EdgePosition,
  width: number,
  height: number,
  gap: number,
): Rectangle {
  const work = disp.workArea;
  const pillCx = pillBounds.x + Math.round(pillBounds.width / 2);
  const pillCy = pillBounds.y + Math.round(pillBounds.height / 2);

  let x: number;
  let y: number;

  switch (pos.edge) {
    case 'bottom':
      x = pillCx - Math.round(width / 2);
      y = pillBounds.y - height - gap;
      break;
    case 'top':
      x = pillCx - Math.round(width / 2);
      y = pillBounds.y + pillBounds.height + gap;
      break;
    case 'left':
      x = pillBounds.x + pillBounds.width + gap;
      y = pillCy - Math.round(height / 2);
      break;
    case 'right':
      x = pillBounds.x - width - gap;
      y = pillCy - Math.round(height / 2);
      break;
  }

  // Clamp to work area so overlay never opens off-screen
  x = Math.max(work.x, Math.min(x, work.x + work.width - width));
  y = Math.max(work.y, Math.min(y, work.y + work.height - height));

  return { x, y, width, height };
}

function ensurePositionDir(): void {
  const dir = path.dirname(POSITION_FILE);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

export function loadSavedPosition(): EdgePosition {
  try {
    if (!existsSync(POSITION_FILE)) {
      return { edge: 'bottom', offset: 0.5 };
    }
    const data = JSON.parse(readFileSync(POSITION_FILE, 'utf8'));
    const edge = data?.edge;
    let offset = Number(data?.offset);
    const validEdges: OrbitalEdge[] = ['top', 'bottom', 'left', 'right'];
    if (!validEdges.includes(edge)) {
      return { edge: 'bottom', offset: 0.5 };
    }
    if (!Number.isFinite(offset)) {
      return { edge: 'bottom', offset: 0.5 };
    }
    // Backward-compat: old format stored offset in absolute pixels (>1).
    // Reset to center (0.5) so the user can re-drag if needed.
    if (offset > 1) {
      offset = 0.5;
    }
    return { edge, offset: Math.max(0, Math.min(1, offset)) };
  } catch {
    return { edge: 'bottom', offset: 0.5 };
  }
}

export function savePosition(pos: EdgePosition): void {
  try {
    ensurePositionDir();
    writeFileSync(POSITION_FILE, JSON.stringify(pos, null, 2));
  } catch {
    // Non-fatal — position just won't persist this session.
  }
}
