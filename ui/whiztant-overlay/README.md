# Whiztant Overlay

Premium Windows desktop overlay — **Electron 33 · React 18 · TypeScript · Vite ·
Tailwind · Framer Motion**.

Three frameless, transparent surfaces:

- **Pill** — 180×52 floating capsule, bottom-right, always on top.
- **Tune** — 360×480 frosted tune panel (Ctrl+Space).
- **Settings** — 300×420 preferences pane (pill → right-click → Settings).

---

## Quick start

```powershell
cd ui\whiztant-overlay
npm install
npm run dev
```

The pill appears within ~1s at the bottom-right of your primary display.

## Global shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Space` | Toggle tune overlay |
| `F9` | Dictation (sends `recording` state to pill) |
| `Esc` | Dismiss whichever panel is open (pill stays) |

Right-click the pill for the context menu (Tune / Settings / Quit).

## Project structure

```
src/
├── main/           # Electron main process (Node context)
│   ├── index.ts      – app bootstrap, creates 3 windows
│   ├── windows.ts    – BrowserWindow factories (pill/overlay/settings)
│   ├── ipc.ts        – ipcMain handlers
│   ├── shortcuts.ts  – globalShortcut registration
│   └── utils.ts      – path + dev-url helpers
├── preload/
│   └── index.ts      – contextBridge exposes `window.api`
├── renderer/
│   ├── pill/         – floating capsule
│   ├── overlay/      – tune panel
│   ├── settings/     – preferences
│   └── shared/       – themes, IPC constants, global types
└── electron.vite.config.ts
```

## How the click-outside dismiss works

We use Electron's native `win.on('blur')` event on the overlay and settings
windows. When either window loses focus to *any* other surface (desktop,
another app, the pill, etc.) a short 80ms timeout fires and hides the panel.
The pill has **no** blur handler — it is resident by design.

## Theming

Five themes ship by default: **Midnight, Smoke, Carbon, Slate, Ghost**.
Editing a theme or adding a new one: update `src/renderer/shared/themes.ts`
and `src/renderer/shared/ipc.ts` (`ThemeName` union).

Selecting a theme from Settings broadcasts via `SET_THEME` and every window
updates live through the `THEME_CHANGED` channel.

## Wiring your backend

The echo stub lives in `src/main/ipc.ts` under the `SEND_MESSAGE` handler.
Replace the `setTimeout` block with a call into your LLM / voice backend and
push results back with `overlay.webContents.send(IPC.AI_REPLY, text)`.

Pill state is controlled purely from main:

```ts
pill.webContents.send(IPC.SET_STATE, 'thinking'); // or 'recording', 'speaking', 'agent', 'idle'
```
