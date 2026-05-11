/**
 * Shared state for tracking which display the cursor was last seen on.
 * Kept in a separate module so the monitor-follow loop, drag handlers,
 * and blur handlers can all keep it in sync.
 */
let lastCursorDisplayId: number | null = null;

export function getLastCursorDisplayId(): number | null {
  return lastCursorDisplayId;
}

export function setLastCursorDisplayId(id: number | null): void {
  lastCursorDisplayId = id;
}
