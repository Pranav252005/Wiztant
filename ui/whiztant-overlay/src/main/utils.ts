import path from 'node:path';

/**
 * Resolved at runtime by electron-vite.
 * In dev:  process.env.ELECTRON_RENDERER_URL points to the Vite dev server root.
 * In prod: we fall back to the built files under out/renderer.
 */
export const VITE_DEV_SERVER_URL: string | undefined = process.env.ELECTRON_RENDERER_URL;

/** out/main at runtime */
export const MAIN_DIST = __dirname;
/** out/renderer at runtime — renderer index.html files live under subfolders (pill/, overlay/, settings/). */
export const RENDERER_DIST = path.join(__dirname, '../renderer');
/** Compiled preload script entry. */
export const PRELOAD_PATH = path.join(__dirname, '../preload/index.js');
