import type { AppState, ThemeName, PillNoticePayload, Task, TaskSnapshot, DictationMemory } from './ipc';

/** Shape of the contextBridge-exposed API available inside renderer processes. */
export interface WhiztantApi {
  toggleOverlay: () => void;
  toggleSettings: () => void;
  sendMessage: (text: string) => void;
  setTheme: (name: ThemeName) => void;
  quit: () => void;
  showPillMenu: () => void;
  requestPillNotice: (payload: PillNoticePayload) => void;
  getTasks: () => Promise<TaskSnapshot>;
  saveTask: (task: Partial<Task>) => Promise<Task>;
  updateTask: (id: string, fields: Partial<Task>) => Promise<Task | null>;
  deleteTask: (id: string) => Promise<Task | null>;
  markDone: (id: string) => Promise<Task | null>;
  openTaskPanel: (task: Task) => Promise<boolean>;
  openMemoryPanel: (memory: DictationMemory) => Promise<boolean>;
  rescheduleTask: (id: string) => Promise<boolean>;
  undoTaskSave: (id: string) => Promise<boolean>;
  openChatFromConfirm: () => void;
  showOverlay: () => void;
  expandPill: (size: { width: number; height: number } | null) => void;
  stopRecording: () => void;
  syncState: (state: AppState) => void;
  openStreakPanel: (data: Record<string, unknown>) => void;
  writeClipboard: (text: string) => Promise<void>;
  pillDragStart: () => void;
  pillDragMove: (screenX: number, screenY: number) => void;
  pillDragEnd: () => void;
  getPillEdge: () => Promise<string>;
  onPillEdge: (cb: (edge: string) => void) => void;

  onSetState: (cb: (state: AppState) => void) => void;
  onAiReply: (cb: (text: string) => void) => void;
  onThemeChanged: (cb: (name: ThemeName) => void) => void;
  onOverlayShow: (cb: () => void) => void;
  onOverlayHide: (cb: () => void) => void;
  onShowSettings: (cb: () => void) => void;
  onHideSettings: (cb: () => void) => void;
  onPillNotice: (cb: (payload: PillNoticePayload) => void) => void;
}

declare global {
  interface Window {
    api: WhiztantApi;
  }
}

export {};
