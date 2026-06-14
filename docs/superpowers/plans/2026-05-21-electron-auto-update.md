# Electron Auto-Update System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add silent background auto-updates to the Wiztant Electron overlay via GitHub Releases, with Pill notifications and a Settings "Restart to Update" button.
**Architecture:** A dedicated `updater.ts` main-process module drives `electron-updater`. It emits IPC events to renderers. Settings shows status. Pill flashes a notice when the download completes.
**Tech Stack:** Electron 33, electron-updater, electron-builder, GitHub Actions.

---

## File Map

| File | Action | Lines (approx) |
|------|--------|----------------|
| `ui/whiztant-overlay/package.json` | Modify | Add 2 deps |
| `ui/whiztant-overlay/electron-builder.yml` | Create | ~45 lines |
| `ui/whiztant-overlay/src/renderer/shared/ipc.ts` | Modify | Add 3 constants + 1 type |
| `ui/whiztant-overlay/src/main/updater.ts` | Create | ~90 lines |
| `ui/whiztant-overlay/src/main/index.ts` | Modify | Add 1 import + 1 call |
| `ui/whiztant-overlay/src/main/ipc.ts` | Modify | Add 1 handler block (~20 lines) |
| `ui/whiztant-overlay/src/preload/index.ts` | Modify | Add 3 API methods |
| `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` | Modify | Add update section (~60 lines) |
| `.github/workflows/release.yml` | Create | ~55 lines |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `ui/whiztant-overlay/package.json`

**Steps:**
- [ ] **Step 1:** Add `"electron-updater": "^6.3.9"` to `dependencies`.
- [ ] **Step 2:** Add `"electron-builder": "^25.1.7"` to `devDependencies`.
- [ ] **Step 3:** Run `cd ui/whiztant-overlay && npm install` to update `package-lock.json`.
- [ ] **Step 4:** Verify `node_modules/electron-updater` exists.

---

## Task 2: Create electron-builder Config

**Files:**
- Create: `ui/whiztant-overlay/electron-builder.yml`

**Steps:**
- [ ] **Step 1:** Write `electron-builder.yml` with:
  - `appId: com.pranav252005.wiztant`
  - `productName: Wiztant`
  - `directories.output: dist`
  - `files: [out/**/*, package.json]`
  - `publish.provider: github`, `owner: Pranav252005`, `repo: Wiztant`
  - `mac.target: [dmg, zip]` with commented-out `identity`, `hardenedRuntime`, `gatekeeperAssess`
  - `win.target: nsis` with commented-out `certificateFile`, `certificatePassword`
  - `linux.target: AppImage`
  - Commented `afterSign: scripts/notarize.js` placeholder
- [ ] **Step 2:** Verify YAML syntax is valid (`cat` the file).

---

## Task 3: Add IPC Channels and Update Types

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/shared/ipc.ts`

**Steps:**
- [ ] **Step 1:** Add to `IPC` constant object:
  - `UPDATE_STATUS: 'update-status'`
  - `CHECK_FOR_UPDATES: 'check-for-updates'`
  - `RESTART_UPDATE: 'restart-update'`
- [ ] **Step 2:** Add `UpdateStatus` TypeScript union type below existing types:
  ```typescript
  export type UpdateStatus =
    | { status: 'checking' }
    | { status: 'available'; version: string }
    | { status: 'downloaded'; version: string }
    | { status: 'error'; message: string }
    | { status: 'idle' };
  ```
- [ ] **Step 3:** Add `'updated'` to `PillNoticeKind` union.

---

## Task 4: Create Core Updater Module

**Files:**
- Create: `ui/whiztant-overlay/src/main/updater.ts`

**Steps:**
- [ ] **Step 1:** Import `{ app, BrowserWindow }` from `electron`, `{ autoUpdater }` from `electron-updater`.
- [ ] **Step 2:** Import `IPC` and `sendBridgeMessage` (from `./bridge`) for renderer communication.
- [ ] **Step 3:** Import `showPillNotice` from `./pillState`.
- [ ] **Step 4:** Write `initUpdater(pill: BrowserWindow, overlay: BrowserWindow): void` that:
  - Logs `[Updater] Initializing...`.
  - Registers `autoUpdater.on('checking-for-update')` → broadcast `UPDATE_STATUS` with `{ status: 'checking' }` to all renderers.
  - Registers `autoUpdater.on('update-available')` → broadcast `{ status: 'available', version: info.version }`.
  - Registers `autoUpdater.on('update-downloaded')` → broadcast `{ status: 'downloaded', version: info.version }` + call `showPillNotice({ kind: 'updated', title: 'Update ready', summary: \`v\${info.version} downloaded. Restart to apply.\`, duration_ms: 8000 })`.
  - Registers `autoUpdater.on('error')` → broadcast `{ status: 'error', message: err.message }`.
  - After a 3-second delay (so app startup isn't blocked), calls `autoUpdater.checkForUpdatesAndNotify().catch(() => {})`.
- [ ] **Step 5:** Export a `restartToUpdate(): void` function that calls `autoUpdater.quitAndInstall(true, true)` (isSilent=true, forceRunAfter=true).
- [ ] **Step 6:** Export a `checkForUpdates(): void` function that calls `autoUpdater.checkForUpdatesAndNotify().catch(() => {})`.

---

## Task 5: Wire Updater into Main Bootstrap

**Files:**
- Modify: `ui/whiztant-overlay/src/main/index.ts`

**Steps:**
- [ ] **Step 1:** Add `import { initUpdater } from './updater';` near the top.
- [ ] **Step 2:** In `bootstrap()`, after `startBridgeHeartbeat()`, call `initUpdater(pill, overlay);`.

---

## Task 6: Register Update IPC Handlers

**Files:**
- Modify: `ui/whiztant-overlay/src/main/ipc.ts`

**Steps:**
- [ ] **Step 1:** Import `initUpdater, restartToUpdate, checkForUpdates` from `./updater`.
- [ ] **Step 2:** In `registerIpcHandlers`, add:
  - `ipcMain.on(IPC.CHECK_FOR_UPDATES, () => checkForUpdates())`
  - `ipcMain.on(IPC.RESTART_UPDATE, () => restartToUpdate())`
- [ ] **Step 3:** Ensure the `getAllThemeWindows` helper also includes any settings-related windows if they exist (overlay already covers it since Settings is inline in overlay).

---

## Task 7: Expose Update APIs in Preload

**Files:**
- Modify: `ui/whiztant-overlay/src/preload/index.ts`

**Steps:**
- [ ] **Step 1:** Add `UpdateStatus` to the type import from `../renderer/shared/ipc`.
- [ ] **Step 2:** In `contextBridge.exposeInMainWorld('api', { ... })`, add:
  - `checkForUpdates: (): void => ipcRenderer.send(IPC.CHECK_FOR_UPDATES)`
  - `restartToUpdate: (): void => ipcRenderer.send(IPC.RESTART_UPDATE)`
  - `onUpdateStatus: (cb: (status: UpdateStatus) => void): void => { ipcRenderer.on(IPC.UPDATE_STATUS, (_e, s) => cb(s)); }`

---

## Task 8: Add Update UI to Settings

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/settings/Settings.tsx`

**Steps:**
- [ ] **Step 1:** Import `UpdateStatus` from `../shared/ipc`.
- [ ] **Step 2:** In `GeneralTab` component props, add `updateStatus` and `onRestartUpdate`.
- [ ] **Step 3:** In the `GeneralTab` body, add an "Update" section above the version footer:
  - Label: "Update"
  - Status text: shows current state (`checking` → "Checking for updates...", `downloaded` → "vX.Y.Z ready to install", `idle` → "Up to date", `error` → "Check failed")
  - Button: "Restart to Update" — only rendered when `updateStatus.status === 'downloaded'`
  - Button style: uses `theme.aiAccent`, padding `6px 14px`, borderRadius `6px`, fontSize `12px`
  - Button `onClick`: calls `window.api.restartToUpdate()`
- [ ] **Step 4:** In the main `Settings` component, add state:
  ```typescript
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({ status: 'idle' });
  ```
- [ ] **Step 5:** In `Settings` `useEffect` (mount), subscribe:
  ```typescript
  window.api.onUpdateStatus((s) => setUpdateStatus(s));
  ```
- [ ] **Step 6:** Pass `updateStatus` and `() => window.api.restartToUpdate()` down to `GeneralTab`.

---

## Task 9: Create GitHub Actions Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`

**Steps:**
- [ ] **Step 1:** Create `.github/workflows/release.yml` with:
  - Trigger: `on.push.tags: ['v*.*.*']`
  - Job `release` running on `ubuntu-latest`
  - Steps: checkout, setup Node 20, `cd ui/whiztant-overlay`, `npm ci`, `npm run build`, `npx electron-builder --publish always`
  - Environment block with commented-out placeholders for `GH_TOKEN`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`, `WINDOWS_CERTIFICATE_PASSWORD`, `CSC_LINK`
  - Comment explaining each placeholder
- [ ] **Step 2:** Verify YAML is valid by reading it back.

---

## Task 10: Build Verification

**Files:**
- All of the above

**Steps:**
- [ ] **Step 1:** Run `cd ui/whiztant-overlay && npm run typecheck` — confirm 0 errors.
- [ ] **Step 2:** Run `cd ui/whiztant-overlay && npm run build` — confirm exit 0.
- [ ] **Step 3:** If either fails, read error, fix, re-run.

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every requirement from the design doc maps to a task above.
- [ ] **Placeholder scan:** No "TBD", "TODO", or "implement later" strings in the plan.
- [ ] **Type consistency:** `UpdateStatus` type is used identically in `ipc.ts`, `updater.ts`, `preload.ts`, and `Settings.tsx`.
