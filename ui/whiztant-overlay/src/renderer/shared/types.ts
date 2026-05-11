import type { AppState, ThemeName, PillNoticePayload, Task, TaskSnapshot, DictationMemory } from './ipc';

/** Shape of the contextBridge-exposed API available inside renderer processes. */
export interface WhiztantApi {
  toggleOverlay: () => void;
  toggleSettings: () => void;
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
  onThemeChanged: (cb: (name: ThemeName) => void) => void;
  onOverlayShow: (cb: () => void) => void;
  onOverlayHide: (cb: () => void) => void;
  onShowSettings: (cb: () => void) => void;
  onHideSettings: (cb: () => void) => void;
  onPillNotice: (cb: (payload: PillNoticePayload) => void) => void;
  openExternal: (url: string) => void;
  openOverlayToTasksEdit: (data: Record<string, unknown>) => void;
  onNavigateToTasksEdit: (cb: (data: Record<string, unknown>) => void) => void;
}

declare global {
  interface Window {
    api: WhiztantApi;
  }
}

export interface AgentV2PhaseStartEvent {
  type: 'agent.phase_start';
  project_id: string;
  layer?: string;
  phase?: string;
  subphase?: string;
  status?: string;
}

export interface AgentV2StepCompleteEvent {
  type: 'agent.step_complete';
  project_id: string;
  subphase_id: string;
}

export interface AgentV2NeedsApprovalEvent {
  type: 'agent.needs_approval';
  project_id: string;
  message: string;
}

export interface AgentV2LimitHitEvent {
  type: 'agent.limit_hit';
  project_id: string;
  reason: string;
}

export type AgentV2Event = AgentV2PhaseStartEvent | AgentV2StepCompleteEvent | AgentV2NeedsApprovalEvent | AgentV2LimitHitEvent;

export {};
