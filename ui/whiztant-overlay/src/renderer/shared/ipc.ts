// Shared IPC channel constants used by main + preload + renderers.
// Keeping these in a single const-object gives us type-safe string literals.

export const IPC = {
  // Main → Renderer (pill)
  SET_STATE: 'set-state',
  PILL_NOTICE: 'pill-notice',
  // Main → Renderer (overlay)
  OVERLAY_SHOW: 'overlay-show',
  OVERLAY_HIDE: 'overlay-hide',
  SHOW_SETTINGS: 'show-settings',
  HIDE_SETTINGS: 'hide-settings',
  AI_REPLY: 'ai-reply',
  // Renderer → Main
  OVERLAY_TOGGLE: 'overlay-toggle',
  SETTINGS_TOGGLE: 'settings-toggle',
  SEND_MESSAGE: 'send-message',
  SET_THEME: 'set-theme',
  QUIT_APP: 'quit-app',
  SHOW_PILL_MENU: 'show-pill-menu',
  PILL_RESIZE: 'pill-resize',
  TASK_GET_ALL: 'task:getAll',
  TASK_SAVE: 'task:save',
  TASK_UPDATE: 'task:update',
  TASK_DELETE: 'task:delete',
  TASK_MARK_DONE: 'task:markDone',
  TASK_OPEN_PANEL: 'task:openPanel',
  MEMORY_OPEN_PANEL: 'memory:openPanel',
  STREAK_OPEN_PANEL: 'streak:openPanel',
  TASK_RESCHEDULE: 'task:reschedule',
  TASK_UNDO_SAVE: 'task:undoSave',
  CLIPBOARD_WRITE: 'clipboard:write',
  SHOW_OVERLAY: 'show-overlay',
  PILL_EXPAND: 'pill:expand',
  STOP_RECORDING: 'stop-recording',
  SYNC_STATE: 'sync-state',
  // Pill drag (renderer → main)
  PILL_DRAG_START: 'pill-drag-start',
  PILL_DRAG_MOVE: 'pill-drag-move',
  PILL_DRAG_END: 'pill-drag-end',
  PILL_GET_EDGE: 'pill:get-edge',
  PILL_EDGE_CHANGED: 'pill-edge-changed',
  // Renderer → Main (shortcuts)
  RELOAD_SHORTCUTS: 'reload-shortcuts',
  PILL_NOTIFICATIONS: 'pill-notifications',
  // Main → Renderer (all)
  THEME_CHANGED: 'theme-changed',
  OPEN_OVERLAY_TO_TASKS_EDIT: 'open-overlay-to-tasks-edit',
  NAVIGATE_TO_TASKS_EDIT: 'navigate-to-tasks-edit',
  OPEN_EXTERNAL: 'open-external',
} as const;

export type AppState = 'idle' | 'recording' | 'thinking' | 'speaking' | 'agent';
export type ThemeName = 'onyx' | 'graphite' | 'porcelain' | 'midnight' | 'ember';

export type TaskStatus = 'pending' | 'in_progress' | 'done';
export type TaskSource = 'voice' | 'typed';
export type TaskType = 'large' | 'small' | null;
export type TaskDifficulty = 'easy' | 'medium' | 'hard' | null;

export interface Task {
  id: string;
  text: string;
  status: TaskStatus;
  source: TaskSource;
  created_at: string;
  due_at?: string | null;
  completed_at?: string | null;
  parent_id?: string | null;
  content?: string | null;
  task_type?: TaskType;
  carried_over?: boolean;
  failed?: boolean;
  snoozed_until?: string | null;
  category?: string | null;
  difficulty?: TaskDifficulty;
}

export interface TaskSnapshot {
  tasks: Task[];
  history: Array<{
    task_id: string;
    text: string;
    source: TaskSource;
    created_at?: string | null;
    completed_at?: string | null;
  }>;
}

export type DictationMemoryMode = 'dictation' | 'agent' | 'task' | 'bg_agent' | 'reprompt';

export interface DictationMemory {
  id: string;
  timestamp: string;
  mode: DictationMemoryMode;
  original_text: string;
  final_text: string;
  session_id?: string;
}

export type PillNoticeKind =
  | 'added'
  | 'updated'
  | 'duplicate'
  | 'subtask'
  | 'memory_added'
  | 'memory_updated'
  | 'error';

export interface PillNoticePayload {
  kind: PillNoticeKind;
  title: string;
  summary: string;
  duration_ms: number;
}

export async function startProject(projectPath: string, description: string, stack: string[] = [], approvalMode = 'step-by-step') {
  const res = await fetch('http://localhost:8765/agent/project/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: projectPath, description, stack, approval_mode: approvalMode }),
  });
  return res.json();
}

export async function getProjectStatus(projectId: string) {
  const res = await fetch(`http://localhost:8765/agent/project/${projectId}/status`);
  return res.json();
}

export async function approveProjectAction(projectId: string, action: 'approve' | 'pause' | 'resume') {
  const res = await fetch(`http://localhost:8765/agent/project/${projectId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  return res.json();
}
