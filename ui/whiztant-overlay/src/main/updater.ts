import { BrowserWindow } from 'electron';
import { autoUpdater, UpdateInfo } from 'electron-updater';
import { IPC } from '../renderer/shared/ipc';
import type { UpdateStatus } from '../renderer/shared/ipc';
import { showPillNotice } from './pillState';

let pillWindow: BrowserWindow | null = null;
let overlayWindow: BrowserWindow | null = null;

function broadcastUpdateStatus(status: UpdateStatus): void {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    try {
      overlayWindow.webContents.send(IPC.UPDATE_STATUS, status);
    } catch {
      // Renderer may not be ready
    }
  }
  // Also broadcast to pill in case it ever needs update awareness
  if (pillWindow && !pillWindow.isDestroyed()) {
    try {
      pillWindow.webContents.send(IPC.UPDATE_STATUS, status);
    } catch {
      // Renderer may not be ready
    }
  }
}

/**
 * Initialize the auto-updater.
 *
 * Checks for updates silently on startup. When an update is downloaded,
 * broadcasts the status to renderers and shows a pill notification.
 */
export function initUpdater(pill: BrowserWindow, overlay: BrowserWindow): void {
  pillWindow = pill;
  overlayWindow = overlay;

  // Disable the built-in native notification dialog from
  // checkForUpdatesAndNotify — we use our own Pill UI instead.
  autoUpdater.autoDownload = true;

  autoUpdater.on('checking-for-update', () => {
    console.log('[Updater] Checking for updates...');
    broadcastUpdateStatus({ status: 'checking' });
  });

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    console.log(`[Updater] Update available: v${info.version}`);
    broadcastUpdateStatus({ status: 'available', version: info.version });
  });

  autoUpdater.on('update-not-available', () => {
    console.log('[Updater] No updates available.');
    broadcastUpdateStatus({ status: 'idle' });
  });

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    console.log(`[Updater] Update downloaded: v${info.version}`);
    broadcastUpdateStatus({ status: 'downloaded', version: info.version });
    showPillNotice({
      kind: 'update_ready',
      title: 'Update ready',
      summary: `v${info.version} downloaded. Restart to apply.`,
      duration_ms: 8000,
    });
  });

  autoUpdater.on('error', (err: Error) => {
    console.error('[Updater] Error:', err.message);
    broadcastUpdateStatus({ status: 'error', message: err.message });
  });

  // Delay the check so it doesn't block cold-start responsiveness.
  setTimeout(() => {
    autoUpdater
      .checkForUpdatesAndNotify()
      .catch((err: Error) => {
        console.error('[Updater] checkForUpdates failed:', err.message);
      });
  }, 3000);
}

/** Trigger a manual update check. */
export function checkForUpdates(): void {
  autoUpdater
    .checkForUpdatesAndNotify()
    .catch((err: Error) => {
      console.error('[Updater] Manual check failed:', err.message);
    });
}

/** Quit the app and install the downloaded update, then relaunch. */
export function restartToUpdate(): void {
  // isSilent=true  → no user prompt
  // forceRunAfter=true → ensures the new version starts after quit
  autoUpdater.quitAndInstall(true, true);
}
