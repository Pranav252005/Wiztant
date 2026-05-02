import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';
import { IPC } from '../renderer/shared/ipc';
import type { AppState, ThemeName, PillNoticePayload, Task, DictationMemory } from '../renderer/shared/ipc';

const clipboardWrite = (text: string): Promise<void> => ipcRenderer.invoke(IPC.CLIPBOARD_WRITE, text);

contextBridge.exposeInMainWorld('api', {
  // ── Renderer → Main ───────────────────────────────────────
  toggleOverlay: (): void => ipcRenderer.send(IPC.OVERLAY_TOGGLE),
  toggleSettings: (): void => ipcRenderer.send(IPC.SETTINGS_TOGGLE),
  sendMessage: (text: string): void => ipcRenderer.send(IPC.SEND_MESSAGE, text),
  setTheme: (name: ThemeName): void => ipcRenderer.send(IPC.SET_THEME, name),
  quit: (): void => ipcRenderer.send(IPC.QUIT_APP),
  showPillMenu: (): void => ipcRenderer.send(IPC.SHOW_PILL_MENU),
  requestPillNotice: (payload: PillNoticePayload): void =>
    ipcRenderer.send(IPC.PILL_NOTICE, payload),
  getTasks: () => ipcRenderer.invoke(IPC.TASK_GET_ALL),
  saveTask: (task: Partial<Task>) => ipcRenderer.invoke(IPC.TASK_SAVE, task),
  updateTask: (id: string, fields: Partial<Task>) => ipcRenderer.invoke(IPC.TASK_UPDATE, id, fields),
  deleteTask: (id: string) => ipcRenderer.invoke(IPC.TASK_DELETE, id),
  markDone: (id: string) => ipcRenderer.invoke(IPC.TASK_MARK_DONE, id),
  openTaskPanel: (task: Task) => ipcRenderer.invoke(IPC.TASK_OPEN_PANEL, task),
  openMemoryPanel: (memory: DictationMemory) => ipcRenderer.invoke(IPC.MEMORY_OPEN_PANEL, memory),
  rescheduleTask: (id: string) => ipcRenderer.invoke(IPC.TASK_RESCHEDULE, id),
  undoTaskSave: (id: string) => ipcRenderer.invoke(IPC.TASK_UNDO_SAVE, id),
  openChatFromConfirm: (): void => ipcRenderer.send(IPC.CONFIRM_OPEN_CHAT),
  showOverlay: (): void => ipcRenderer.send(IPC.SHOW_OVERLAY),
  expandPill: (size: { width: number; height: number } | null): void =>
    ipcRenderer.send(IPC.PILL_EXPAND, size),
  stopRecording: (): void => ipcRenderer.send(IPC.STOP_RECORDING),
  syncState: (state: AppState): void => ipcRenderer.send(IPC.SYNC_STATE, state),
  openStreakPanel: (data: Record<string, unknown>): void =>
    ipcRenderer.send(IPC.STREAK_OPEN_PANEL, data),
  writeClipboard: clipboardWrite,
  pillDragStart: (): void => ipcRenderer.send(IPC.PILL_DRAG_START),
  pillDragMove: (screenX: number, screenY: number): void =>
    ipcRenderer.send(IPC.PILL_DRAG_MOVE, screenX, screenY),
  pillDragEnd: (): void => ipcRenderer.send(IPC.PILL_DRAG_END),
  getPillEdge: (): Promise<string> => ipcRenderer.invoke(IPC.PILL_GET_EDGE),
  onPillEdge: (cb: (edge: string) => void): void => {
    ipcRenderer.on(IPC.PILL_EDGE_CHANGED, (_e: IpcRendererEvent, edge: string) => cb(edge));
  },

  // ── Main → Renderer (subscriptions) ───────────────────────
  onSetState: (cb: (state: AppState) => void): void => {
    ipcRenderer.on(IPC.SET_STATE, (_e: IpcRendererEvent, s: AppState) => cb(s));
  },
  onAiReply: (cb: (text: string) => void): void => {
    ipcRenderer.on(IPC.AI_REPLY, (_e: IpcRendererEvent, t: string) => cb(t));
  },
  onThemeChanged: (cb: (name: ThemeName) => void): void => {
    ipcRenderer.on(IPC.THEME_CHANGED, (_e: IpcRendererEvent, n: ThemeName) => cb(n));
  },
  onOverlayShow: (cb: () => void): void => {
    ipcRenderer.on(IPC.OVERLAY_SHOW, () => cb());
  },
  onOverlayHide: (cb: () => void): void => {
    ipcRenderer.on(IPC.OVERLAY_HIDE, () => cb());
  },
  onShowSettings: (cb: () => void): void => {
    ipcRenderer.on(IPC.SHOW_SETTINGS, () => cb());
  },
  onHideSettings: (cb: () => void): void => {
    ipcRenderer.on(IPC.HIDE_SETTINGS, () => cb());
  },
  onPillNotice: (cb: (payload: PillNoticePayload) => void): void => {
    ipcRenderer.on(IPC.PILL_NOTICE, (_e: IpcRendererEvent, p: PillNoticePayload) => cb(p));
  },
});
