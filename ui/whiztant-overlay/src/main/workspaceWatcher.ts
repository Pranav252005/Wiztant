import { spawn, exec } from 'node:child_process';

// ── Types ───────────────────────────────────────────────────────
export type DesktopChangeEvent = {
  desktop: number;
  previous: number;
  direction: 'left' | 'right' | 'unknown';
  totalDesktops: number;
};

// ── State ───────────────────────────────────────────────────────
let spyProcess: ReturnType<typeof spawn> | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let currentCb: ((event: DesktopChangeEvent) => void) | null = null;
let previousDesktop = -1;
let totalDesktops = 1;

// ── Helpers ─────────────────────────────────────────────────────

function parseDesktopLine(line: string): number | null {
  const match = line.match(/=\s*(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

function computeDirection(prev: number, next: number, total: number): DesktopChangeEvent['direction'] {
  if (prev === -1) return 'unknown';
  if (next === prev + 1) return 'right';
  if (next === prev - 1) return 'left';
  // wrap-around
  if (prev === total - 1 && next === 0) return 'right';
  if (prev === 0 && next === total - 1) return 'left';
  return 'unknown';
}

function runXpropRoot(prop: string): Promise<string> {
  return new Promise((resolve) => {
    exec(`xprop -root ${prop}`, (_err, stdout) => resolve(stdout || ''));
  });
}

async function fetchTotalDesktops(): Promise<number> {
  try {
    const out = await runXpropRoot('_NET_NUMBER_OF_DESKTOPS');
    const val = parseDesktopLine(out);
    if (val !== null && val > 0) return val;
  } catch { /* ignore */ }
  // Fallback: count lines from wmctrl -d
  return new Promise((resolve) => {
    exec('wmctrl -d', (err, stdout) => {
      if (err || !stdout) return resolve(1);
      const lines = stdout.trim().split('\n').filter((l) => l.length > 0);
      resolve(lines.length || 1);
    });
  });
}

async function fetchCurrentDesktop(): Promise<number | null> {
  try {
    const out = await runXpropRoot('_NET_CURRENT_DESKTOP');
    const val = parseDesktopLine(out);
    if (val !== null) return val;
  } catch { /* ignore */ }
  return fetchCurrentDesktopViaXdotool();
}

async function fetchCurrentDesktopViaXdotool(): Promise<number | null> {
  return new Promise((resolve) => {
    exec('xdotool get_desktop', (err, stdout) => {
      if (err || !stdout) {
        console.error('[WorkspaceWatcher] xdotool get_desktop failed:', err?.message || 'no output');
        return resolve(null);
      }
      const n = parseInt(stdout.trim(), 10);
      resolve(isNaN(n) ? null : n);
    });
  });
}

function notifyIfChanged(nextDesktop: number): void {
  if (nextDesktop === previousDesktop) return;
  const prev = previousDesktop;
  previousDesktop = nextDesktop;
  console.log(`[WorkspaceWatcher] Desktop changed: ${prev} → ${nextDesktop}`);
  if (!currentCb) {
    console.warn('[WorkspaceWatcher] No callback registered!');
    return;
  }
  currentCb({
    desktop: nextDesktop,
    previous: prev,
    direction: computeDirection(prev, nextDesktop, totalDesktops),
    totalDesktops,
  });
}

// ── Public API ──────────────────────────────────────────────────

export async function findWindowIdsByTitle(title: string): Promise<string[]> {
  return new Promise((resolve) => {
    // xdotool search --name does substring matching, so searching for the
    // exact title should find it even if the WM adds decorations.
    const cmd = `xdotool search --name "${title}"`;
    console.log(`[WorkspaceWatcher] Running: ${cmd}`);
    exec(cmd, (err, stdout) => {
      if (err) {
        console.error(`[WorkspaceWatcher] xdotool search failed:`, err.message);
        return resolve([]);
      }
      if (!stdout) {
        console.warn(`[WorkspaceWatcher] xdotool search returned empty for "${title}"`);
        return resolve([]);
      }
      const lines = stdout.trim().split('\n').map((l) => l.trim()).filter((l) => l.length > 0);
      console.log(`[WorkspaceWatcher] Found ${lines.length} window(s) for "${title}":`, lines);
      resolve(lines);
    });
  });
}

export async function getWindowDesktop(windowId: string): Promise<number | null> {
  return new Promise((resolve) => {
    exec(`xdotool get_desktop_for_window ${windowId}`, (err, stdout) => {
      if (err) {
        console.error(`[WorkspaceWatcher] get_desktop_for_window ${windowId} failed:`, err.message);
        return resolve(null);
      }
      if (!stdout) return resolve(null);
      const n = parseInt(stdout.trim(), 10);
      console.log(`[WorkspaceWatcher] Window ${windowId} is on desktop ${n}`);
      resolve(isNaN(n) ? null : n);
    });
  });
}

export async function moveWindowToDesktop(windowId: string, desktop: number): Promise<boolean> {
  return new Promise((resolve) => {
    // Prefer wmctrl because it's more reliable for moving to arbitrary desktops
    exec(`wmctrl -i -r ${windowId} -t ${desktop}`, (err) => {
      if (!err) {
        console.log(`[WorkspaceWatcher] wmctrl moved ${windowId} to desktop ${desktop}`);
        return resolve(true);
      }
      console.warn(`[WorkspaceWatcher] wmctrl failed for ${windowId}:`, err.message);
      // Fallback to xdotool
      exec(`xdotool set_desktop_for_window ${windowId} ${desktop}`, (err2) => {
        if (!err2) {
          console.log(`[WorkspaceWatcher] xdotool moved ${windowId} to desktop ${desktop}`);
        } else {
          console.error(`[WorkspaceWatcher] xdotool fallback failed for ${windowId}:`, err2.message);
        }
        resolve(!err2);
      });
    });
  });
}

export async function moveAllWindowsToDesktop(desktop: number): Promise<boolean> {
  // Find both pill and overlay windows by their titles.
  // Search for each separately so we can log which ones exist.
  const pillIds = await findWindowIdsByTitle('whiztant-pill');
  const overlayIds = await findWindowIdsByTitle('whiztant-overlay');

  // Also try a broader search as fallback
  let fallbackIds: string[] = [];
  if (!pillIds.length && !overlayIds.length) {
    console.warn('[WorkspaceWatcher] Exact title search found nothing, trying broad search...');
    fallbackIds = await findWindowIdsByTitle('whiztant');
  }

  const allIds = [...pillIds, ...overlayIds, ...fallbackIds];
  // Deduplicate
  const uniqueIds = [...new Set(allIds)];

  if (!uniqueIds.length) {
    console.error('[WorkspaceWatcher] No whiztant windows found, cannot move');
    return false;
  }

  console.log(`[WorkspaceWatcher] Moving ${uniqueIds.length} window(s) to desktop ${desktop}`);
  let anySuccess = false;
  for (const id of uniqueIds) {
    const ok = await moveWindowToDesktop(id, desktop);
    if (ok) anySuccess = true;
  }
  return anySuccess;
}

export function startWorkspaceWatcher(cb: (event: DesktopChangeEvent) => void): void {
  if (process.platform !== 'linux') {
    console.log('[WorkspaceWatcher] Not starting — platform is', process.platform);
    return;
  }
  console.log('[WorkspaceWatcher] Starting workspace watcher...');
  currentCb = cb;

  // Initialise totals and current desktop
  fetchTotalDesktops().then((t) => {
    totalDesktops = t;
    console.log(`[WorkspaceWatcher] Total desktops: ${t}`);
    return fetchCurrentDesktop();
  }).then((d) => {
    if (d !== null) {
      previousDesktop = d;
      console.log(`[WorkspaceWatcher] Initial desktop: ${d}`);
    } else {
      console.warn('[WorkspaceWatcher] Could not determine initial desktop');
    }
  }).catch((e) => {
    console.error('[WorkspaceWatcher] Init error:', e);
  });

  // Try real-time spy via xprop first
  try {
    console.log('[WorkspaceWatcher] Trying xprop -spy -root _NET_CURRENT_DESKTOP...');
    spyProcess = spawn('xprop', ['-spy', '-root', '_NET_CURRENT_DESKTOP'], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    spyProcess.stdout?.on('data', (data: Buffer) => {
      const line = data.toString();
      console.log('[WorkspaceWatcher] xprop stdout:', line.trim());
      const val = parseDesktopLine(line);
      if (val !== null) {
        notifyIfChanged(val);
      }
    });

    spyProcess.stderr?.on('data', (data: Buffer) => {
      console.error('[WorkspaceWatcher] xprop stderr:', data.toString().trim());
    });

    spyProcess.on('error', (err) => {
      console.error('[WorkspaceWatcher] xprop spawn error:', err.message);
      stopSpy();
      startPolling();
    });

    spyProcess.on('exit', (code) => {
      console.log(`[WorkspaceWatcher] xprop exited with code ${code}`);
      if (code !== 0) {
        stopSpy();
        startPolling();
      }
    });
  } catch (e) {
    console.error('[WorkspaceWatcher] xprop spawn threw:', e);
    startPolling();
  }
}

function startPolling(): void {
  if (pollTimer) return;
  console.log('[WorkspaceWatcher] Falling back to xdotool polling (150ms)');
  pollTimer = setInterval(() => {
    fetchCurrentDesktopViaXdotool().then((d) => {
      if (d !== null) notifyIfChanged(d);
    }).catch((e) => {
      console.error('[WorkspaceWatcher] Polling error:', e);
    });
  }, 150);
}

function stopSpy(): void {
  if (spyProcess) {
    try {
      spyProcess.kill();
    } catch { /* ignore */ }
    spyProcess = null;
  }
}

export function stopWorkspaceWatcher(): void {
  console.log('[WorkspaceWatcher] Stopping watcher');
  stopSpy();
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  currentCb = null;
  previousDesktop = -1;
}
