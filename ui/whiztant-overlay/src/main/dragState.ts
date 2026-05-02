/**
 * Shared drag-latch state.
 *
 * Raised while code is programmatically repositioning windows so the
 * native 'move' listeners don't re-trigger edge-snapping.
 */
export const dragState = {
  isProgrammaticMove: false,
};
