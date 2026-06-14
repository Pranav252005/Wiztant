# Electron Auto-Update System — Design Spec

**Date:** 2026-05-21  
**Scope:** Wiztant Electron Overlay (`ui/whiztant-overlay/`)  
**Goal:** Enable silent background auto-updates via GitHub Releases with Pill notification + Settings UI.

---

## 1. Requirements (Validated)

| # | Requirement | Decision |
|---|-------------|----------|
| 1 | Add `electron-updater` dependency | ✅ Yes |
| 2 | Configure `electron-builder` for GitHub Releases | ✅ Provider: `github`, Owner: `Pranav252005`, Repo: `Wiztant` |
| 3 | Check for updates on app startup | ✅ Silent check, no user prompt |
| 4 | Auto-download update in background | ✅ Option A — download silently |
| 5 | Show Pill notification when update ready | ✅ "Update available — restart to apply" |
| 6 | Add "Restart to Update" button in Settings | ✅ New section in General tab |
| 7 | Restart closes overlay + app + relaunches | ✅ `autoUpdater.quitAndInstall()` |
| 8 | Code signing placeholders | ✅ Commented-out macOS + Windows signing config |
| 9 | CI workflow for build + publish on tag | ✅ GitHub Actions workflow |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Main Process (Node/Electron)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ app.on(ready)│→ │ updater.ts   │→ │ electron-updater│   │
│  │              │  │              │  │                 │   │
│  │ bootstrap()  │  │ • check()    │  │ • checkForUpdates│   │
│  │              │  │ • on('update-│  │ • downloadUpdate │  │
│  │              │  │   available')│  │ • quitAndInstall │  │
│  │              │  │ • on('update-│  │                 │   │
│  │              │  │   downloaded')│  │                 │   │
│  └──────────────┘  └──────┬───────┘  └─────────────────┘   │
│                           │                                  │
│                           ↓ IPC                              │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ ipc.ts       │← │ preload      │← │ Settings.tsx    │   │
│  │              │  │ (api)        │  │ (Renderer)      │   │
│  │ • UPDATE_    │  │               │  │ • Show status   │   │
│  │   STATUS     │  │               │  │ • Restart btn   │   │
│  │ • RESTART_   │  │               │  │                 │   │
│  │   UPDATE     │  │               │  │                 │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
│                           │                                  │
│                           ↓ IPC                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ pillState.ts │← │ Pill.tsx     │                         │
│  │              │  │ (Renderer)   │                         │
│  │ showPillNotice│  │ • Show update│                         │
│  │              │  │   notice     │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

**Design principle:** All updater logic lives in a single `updater.ts` module. Main process calls it on bootstrap. It emits IPC events to renderers. Settings shows status + restart button. Pill shows a transient notice when the download completes.

---

## 3. Approaches Considered

### Approach A: Inline in `main/index.ts` (Rejected)
Put all `electron-updater` logic directly inside the bootstrap function.
- **Pros:** Fewer files touched.
- **Cons:** Clutters the main process entry point; harder to test; violates single-responsibility.

### Approach B: Dedicated `updater.ts` module (Recommended)
Create a focused updater module with a clean API: `initUpdater(pill, overlay)`.
- **Pros:** Clean separation; follows existing codebase patterns (`pillState.ts`, `bridge.ts`); easy to extend later (e.g., manual check button).
- **Cons:** One new file.

### Approach C: Full custom download progress UI (Rejected)
Show a download progress bar in the overlay with MB/s and ETA.
- **Pros:** Users see exactly what's happening.
- **Cons:** Overkill for background silent downloads; `electron-updater` already handles this with no UI needed.

**Decision:** Approach B.

---

## 4. Detailed Design

### 4.1 Dependencies & Build Config

**New dependency:** `electron-updater` (goes in `dependencies`, not `devDependencies`, because it runs in the main process at runtime).

**New file:** `ui/whiztant-overlay/electron-builder.yml`
- `publish.provider: github`
- `publish.owner: Pranav252005`
- `publish.repo: Wiztant`
- `mac.identity: null` (placeholder commented out)
- `win.certificateFile` + `certificatePassword` (placeholder commented out)
- `afterSign: notarize.js` (placeholder commented out)

### 4.2 Updater Module (`src/main/updater.ts`)

```typescript
// initUpdater(pill: BrowserWindow, overlay: BrowserWindow): void
// • Sets up electron-updater event handlers
// • Calls autoUpdater.checkForUpdatesAndNotify() on app.ready (silent)
// • Emits IPC events to renderers when state changes
// • Exposes restartToUpdate() for renderer-triggered restart
```

**Event flow:**
1. `app.whenReady()` → `initUpdater(pill, overlay)`
2. `autoUpdater.checkForUpdatesAndNotify()` — silent, no built-in dialog
3. On `update-available`: log, optionally start tracking
4. On `update-downloaded`:
   - Send `IPC.UPDATE_STATUS` to all renderers with `{ status: 'downloaded', version }`
   - Call `showPillNotice({ kind: 'updated', title: 'Update ready', summary: 'Restart to apply vX.Y.Z', duration_ms: 8000 })`
5. On `error`: log to console, send `IPC.UPDATE_STATUS` with `{ status: 'error', message }`

**Why `checkForUpdatesAndNotify()`?** It's the standard electron-updater API. Even though the name says "notify", it only shows a native OS notification if we don't override it. We'll suppress that and use our Pill notification instead.

### 4.3 IPC Channels

**New IPC constants in `src/renderer/shared/ipc.ts`:**
```typescript
UPDATE_STATUS: 'update-status',      // Main → Renderer (all windows)
CHECK_FOR_UPDATES: 'check-for-updates', // Renderer → Main (manual)
RESTART_UPDATE: 'restart-update',    // Renderer → Main
```

**Payload shapes:**
```typescript
type UpdateStatus =
  | { status: 'checking' }
  | { status: 'available'; version: string }
  | { status: 'downloaded'; version: string }
  | { status: 'error'; message: string }
  | { status: 'idle' };
```

**Preload exposure:** `window.api` gets:
- `onUpdateStatus(cb)` — subscribe to status changes
- `checkForUpdates()` — manual check trigger
- `restartToUpdate()` — trigger restart

### 4.4 Pill Notification Integration

When `update-downloaded` fires:
- Call `showPillNotice({ kind: 'updated', title: 'Update ready', summary: 'v1.1.0 is downloaded. Restart to apply.', duration_ms: 8000 })`

**Note:** `PillNoticeKind` currently doesn't have `'updated'`. We'll add it.

### 4.5 Settings UI Changes

In `Settings.tsx` → `GeneralTab`:

Add a new "Update" section above the version string:

```
Update
─────────────────────────────────────────
Current version: 1.0.0
Status: Checking for updates... / Up to date / Update downloaded (v1.1.0)
[Restart to Update]  ← only shown when status === 'downloaded'
```

**Styling:** Follows existing toggle/row patterns. Button uses the theme's `aiAccent` color.

### 4.6 CI/CD Workflow

**New file:** `.github/workflows/release.yml`

**Triggers:** `push` with tags matching `v*.*.*`

**Jobs:**
1. `build` — matrix: macOS, Windows, Ubuntu
   - Checkout
   - Setup Node.js
   - `cd ui/whiztant-overlay && npm ci`
   - `npm run build`
   - `npx electron-builder --publish always` (publishes to GitHub Releases)

**Signing placeholders:** The workflow will have commented-out env vars for:
- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`
- `WINDOWS_CERTIFICATE_PASSWORD`

**Note:** Since there's no `electron-builder` currently, we also need to add it to `devDependencies`.

### 4.7 Version Strategy

`package.json` version is currently `1.0.0`. GitHub Releases will use this version. Future releases:
1. Bump version in `package.json`
2. `git tag v1.1.0`
3. `git push origin v1.1.0`
4. CI builds and publishes.

---

## 5. Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `ui/whiztant-overlay/package.json` | Modify | Add `electron-updater` + `electron-builder` |
| `ui/whiztant-overlay/electron-builder.yml` | Create | Build + publish + signing config |
| `ui/whiztant-overlay/src/main/updater.ts` | Create | Core updater logic |
| `ui/whiztant-overlay/src/main/index.ts` | Modify | Call `initUpdater()` in bootstrap |
| `ui/whiztant-overlay/src/main/ipc.ts` | Modify | Register update IPC handlers |
| `ui/whiztant-overlay/src/renderer/shared/ipc.ts` | Modify | Add IPC constants + UpdateStatus type |
| `ui/whiztant-overlay/src/preload/index.ts` | Modify | Expose update APIs |
| `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` | Modify | Add update status + restart button |
| `.github/workflows/release.yml` | Create | CI build + publish on tag push |

---

## 6. Error Handling

| Scenario | Behavior |
|----------|----------|
| No internet on startup | Silent fail, status = 'idle', no pill notice |
| GitHub API rate limited | Log error, status = 'error', no user-facing noise |
| Download fails mid-way | electron-updater retries automatically; if final fail, status = 'error' |
| User clicks "Restart to Update" but download not ready | Button is hidden unless status === 'downloaded'; impossible state |

---

## 7. Security Considerations

- Updates are fetched from **GitHub Releases only** (provider: github).
- `electron-updater` verifies the signature on Windows and macOS automatically.
- No custom update server = smaller attack surface.
- The `updater.ts` module will be loaded **after** `app.whenReady()` so it cannot block startup.

---

## 8. Testing Plan

1. **Local dev:** `npm run build` succeeds; `npm run typecheck` passes.
2. **Mock test:** Temporarily change `package.json` version to `0.0.1`, run built app — should detect update from GitHub.
3. **CI test:** Push a `v0.0.0-test` tag, verify workflow runs (can delete release after).
4. **Manual:** Verify Pill notice appears; verify Settings shows status; verify restart works.

---

## 9. Open Questions / Future Work

- **Periodic checks:** Currently only on startup. Could add a 4-hour interval later.
- **Release notes:** Could fetch release body from GitHub API and show in Settings.
- **Forced updates:** Could add a `minimumVersion` gate that blocks usage until updated.
- **Delta updates:** `electron-updater` supports differential updates via `electron-builder` — can enable later.
