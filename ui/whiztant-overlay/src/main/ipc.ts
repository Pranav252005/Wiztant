import { ipcMain, app, BrowserWindow, Menu, clipboard } from 'electron';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { IPC } from '../renderer/shared/ipc';
import type { PillNoticePayload, ThemeName, Task, TaskSnapshot, AppState } from '../renderer/shared/ipc';
import { getPillState, setPillState, showPillNotice, setPillNotificationSize } from './pillState';
import { screen, type Display } from 'electron';
import {
  setEdgePosition,
  getEdgePosition,
  savePosition,
  latchToNearestEdge,
  getOverlayBoundsFromEdge,
} from './orbit';
import { setWindowBounds, getPillBounds } from './positioning';
import { sendBridgeMessage } from './bridge';
import { dragState } from './dragState';
import { createTaskPanelWindow, createStreakPanelWindow, createMemoryPanelWindow } from './windows';

// Theme persistence — stored next to the Python app in C:\whis\memory\theme.json
// so the same file can be inspected or edited by the desktop side if needed.
const THEME_FILE = (() => {
  // Project root is three levels up from out/main at runtime (out/main/index.js).
  // Fall back to userData if the project memory dir is unavailable.
  try {
    const projectRoot = path.resolve(app.getAppPath(), '..', '..');
    return path.join(projectRoot, 'memory', 'theme.json');
  } catch {
    return path.join(app.getPath('userData'), 'theme.json');
  }
})();

const VALID_THEMES: ThemeName[] = ['onyx', 'graphite', 'porcelain', 'midnight', 'ember'];

const TASKS_FILE = (() => {
  try {
    const projectRoot = path.resolve(app.getAppPath(), '..', '..');
    return path.join(projectRoot, 'memory', 'tasks.json');
  } catch {
    return path.join(app.getPath('userData'), 'tasks.json');
  }
})();

const taskPanels = new Map<string, BrowserWindow>();
let streakPanel: BrowserWindow | null = null;
let memoryPanel: BrowserWindow | null = null;

function ensureTaskDir(): void {
  const dir = path.dirname(TASKS_FILE);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function readTaskSnapshot(): TaskSnapshot {
  try {
    if (!existsSync(TASKS_FILE)) return { tasks: [], history: [] };
    const data = JSON.parse(readFileSync(TASKS_FILE, 'utf8'));
    return {
      tasks: Array.isArray(data?.tasks) ? data.tasks : [],
      history: Array.isArray(data?.history) ? data.history : [],
    };
  } catch {
    return { tasks: [], history: [] };
  }
}

function writeTaskSnapshot(snapshot: TaskSnapshot): void {
  ensureTaskDir();
  writeFileSync(TASKS_FILE, JSON.stringify(snapshot, null, 2));
}

function buildTask(task: Partial<Task>): Task {
  const now = new Date().toISOString();
  const content = typeof task.content === 'string' ? task.content : null;
  const taskType = task.task_type ?? (content && content.length > 400 ? 'large' : 'small');
  return {
    id: task.id || `task_${Date.now()}_${randomUUID().slice(0, 6)}`,
    text: String(task.text || '').trim(),
    status: (task.status === 'done' || task.status === 'in_progress') ? task.status : 'pending',
    source: task.source === 'voice' ? 'voice' : 'typed',
    created_at: task.created_at || now,
    due_at: task.due_at ?? null,
    completed_at: task.completed_at ?? null,
    parent_id: task.parent_id ?? null,
    content,
    task_type: taskType,
    carried_over: Boolean(task.carried_over),
    failed: Boolean(task.failed),
  };
}

function syncTaskPanels(task: Task): void {
  const win = taskPanels.get(task.id);
  if (!win || win.isDestroyed()) {
    taskPanels.delete(task.id);
    return;
  }
  if (!win.webContents.isLoading()) {
    win.webContents.send(IPC.THEME_CHANGED, loadStoredTheme() || 'graphite');
    return;
  }
  win.webContents.once('did-finish-load', () => {
    if (!win.isDestroyed()) {
      win.webContents.send(IPC.THEME_CHANGED, loadStoredTheme() || 'graphite');
    }
  });
}

function closeTaskPanels(): void {
  for (const [taskId, win] of taskPanels) {
    if (!win.isDestroyed()) {
      win.close();
    }
    taskPanels.delete(taskId);
  }
}

export function loadStoredTheme(): ThemeName | null {
  try {
    if (!existsSync(THEME_FILE)) return null;
    const data = JSON.parse(readFileSync(THEME_FILE, 'utf8'));
    const name = data?.theme;
    return VALID_THEMES.includes(name) ? (name as ThemeName) : null;
  } catch {
    return null;
  }
}

function saveStoredTheme(name: string): void {
  try {
    const dir = path.dirname(THEME_FILE);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(THEME_FILE, JSON.stringify({ theme: name }, null, 2));
  } catch {
    // Non-fatal — theme just won't persist this session.
  }
}

interface Windows {
  pill: BrowserWindow;
  overlay: BrowserWindow;
  showOverlay: () => void;
}

export function registerIpcHandlers({ pill, overlay, showOverlay }: Windows): void {
  for (const [taskId, win] of taskPanels) {
    if (win.isDestroyed()) taskPanels.delete(taskId);
  }

  const getAllThemeWindows = () => {
    return [
      pill,
      overlay,
      ...taskPanels.values(),
      ...(streakPanel && !streakPanel.isDestroyed() ? [streakPanel] : []),
      ...(memoryPanel && !memoryPanel.isDestroyed() ? [memoryPanel] : []),
    ];
  };
  const closeAuxiliaryWindows = () => {
    closeTaskPanels();
    if (streakPanel && !streakPanel.isDestroyed()) {
      streakPanel.close();
      streakPanel = null;
    }
  };

  // ─── Overlay toggle ─────────────────────────────────────────
  // Grace window (ms): if the overlay was auto-hidden by blur very
  // recently (e.g. user clicked the pill while overlay was focused),
  // the incoming click IPC is the *same* click that closed it —
  // treat as "close complete" instead of reopening.
  const BLUR_GRACE_MS = 250;
  const wasJustAutoHidden = (w: BrowserWindow): boolean => {
    const t = (w as any).lastAutoHiddenAt as number | undefined;
    return typeof t === 'number' && Date.now() - t < BLUR_GRACE_MS;
  };

  ipcMain.on(IPC.OVERLAY_TOGGLE, () => {
    if (overlay.isDestroyed()) return;
    if (overlay.isVisible()) {
      closeAuxiliaryWindows();
      overlay.hide();
    } else if (wasJustAutoHidden(overlay)) {
      // Click that closed it just arrived here — do nothing.
    } else {
      showOverlay();
    }
  });

  // ─── Settings toggle ────────────────────────────────────────
  // Settings is now rendered inline inside the overlay window (not a separate
  // BrowserWindow). We send IPC to the overlay renderer to show/hide it.
  ipcMain.on(IPC.SETTINGS_TOGGLE, () => {
    if (overlay.isDestroyed()) return;
    overlay.webContents.send(IPC.SHOW_SETTINGS);
    showOverlay();
  });

  // ─── Message from overlay → call OpenAI → reply ──────────────
  ipcMain.on(IPC.SEND_MESSAGE, async (_event, text: string) => {
    setPillState('thinking');

    const readEnv = (): Record<string, string> => {
      try {
        const projectRoot = path.resolve(app.getAppPath(), '..', '..');
        const envPath = path.join(projectRoot, '.env');
        const raw = existsSync(envPath) ? readFileSync(envPath, 'utf8') : '';
        const map: Record<string, string> = {};
        for (const line of raw.split(/\r?\n/)) {
          const m = line.match(/^\s*([A-Za-z0-9_]+)\s*=\s*(.*)\s*$/);
          if (m) {
            let v = m[2];
            if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
            if (v.startsWith('\'') && v.endsWith('\'')) v = v.slice(1, -1);
            map[m[1]] = v;
          }
        }
        return map;
      } catch {
        return {};
      }
    };

    const env = readEnv();
    const apiKey = process.env.OPENAI_API_KEY || env.OPENAI_API_KEY || '';
    const tier = (env.CURRENT_TIER || 'free').toLowerCase();
    const modelMap: Record<string, string> = {
      free: env.MODEL_FREE || 'gpt-4o',
      pro: env.MODEL_PRO || 'gpt-4o',
      power: env.MODEL_POWER || 'gpt-4o',
    };
    const model = modelMap[tier] || 'gpt-4o';

    const messages = [
      { role: 'system', content: 'You are Wiztant, a helpful assistant.' },
      { role: 'user', content: String(text || '') },
    ];

    async function callTune(): Promise<string> {
      try {
        const res = await fetch('http://localhost:8765/tune', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ content: String(text || '') }),
        });
        if (!res.ok) {
          return `Tune server error: ${res.status} ${res.statusText}`;
        }
        const data: any = await res.json();
        if (data && data.reply) {
          const applied = data.applied && data.applied.length ? `\n✓ ${data.applied.join(', ')}` : '';
          const errs = data.errors && data.errors.length ? `\n⚠ ${data.errors.join(', ')}` : '';
          return `${data.reply}${applied}${errs}`;
        }
        return JSON.stringify(data);
      } catch (e: any) {
        return `Network error: ${String(e?.message || e)}`;
      }
    }

    // Fallback legacy chat handler (kept for compatibility)
    async function callOpenAI(): Promise<string> {
      if (!apiKey) return 'Error: OPENAI_API_KEY is not configured.';
      try {
        const res = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify({ model, messages, temperature: 0.7, max_tokens: 800 }),
        });
        if (!res.ok) {
          const err = await res.text();
          return `Error from OpenAI: ${res.status} ${res.statusText} — ${err}`;
        }
        const data: any = await res.json();
        return data?.choices?.[0]?.message?.content || '';
      } catch (e: any) {
        return `Network error: ${String(e?.message || e)}`;
      }
    }

    const reply = await callTune();
    if (!overlay.isDestroyed()) {
      overlay.webContents.send(IPC.AI_REPLY, reply || '(no response)');
    }
    setPillState('idle');
  });

  // ─── Theme change → broadcast to all surfaces + persist ─────
  ipcMain.on(IPC.SET_THEME, (_event, themeName: string) => {
    saveStoredTheme(themeName);
    for (const win of getAllThemeWindows()) {
      if (!win.isDestroyed()) {
        win.webContents.send(IPC.THEME_CHANGED, themeName);
      }
    }
  });

  // On each window finishing load, push the stored theme so the active tab
  // indicator and surface colors are correct on first paint.
  const stored = loadStoredTheme();
  if (stored) {
    for (const win of getAllThemeWindows()) {
      win.webContents.once('did-finish-load', () => {
        if (!win.isDestroyed()) {
          win.webContents.send(IPC.THEME_CHANGED, stored);
        }
      });
    }
  }

  // ─── Native context menu (pill is too small to contain one) ─
  ipcMain.on(IPC.SHOW_PILL_MENU, () => {
    const menu = Menu.buildFromTemplate([
      {
        label: 'Tune',
        accelerator: 'CommandOrControl+Space',
        click: () => {
          if (overlay.isDestroyed()) return;
          showOverlay();
        },
      },
      {
        label: 'Settings',
        click: () => {
          if (overlay.isDestroyed()) return;
          overlay.webContents.send(IPC.SHOW_SETTINGS);
          showOverlay();
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Whiztant',
        click: () => app.quit(),
      },
    ]);
    menu.popup({ window: pill });
  });

  // ─── Pill notice (from pill renderer, relayed from WS bridge) ──
  ipcMain.on(IPC.PILL_NOTICE, (_event, payload: PillNoticePayload) => {
    if (!payload || typeof payload !== 'object') return;
    showPillNotice({
      kind: payload.kind ?? 'added',
      title: String(payload.title ?? ''),
      summary: String(payload.summary ?? ''),
      duration_ms: Number(payload.duration_ms ?? 2600),
    });
  });

  ipcMain.handle(IPC.TASK_GET_ALL, () => {
    return readTaskSnapshot();
  });

  ipcMain.handle(IPC.TASK_SAVE, (_event, task: Partial<Task>) => {
    const snapshot = readTaskSnapshot();
    const nextTask = buildTask(task);
    snapshot.tasks.push(nextTask);
    writeTaskSnapshot(snapshot);
    syncTaskPanels(nextTask);
    return nextTask;
  });

  ipcMain.handle(IPC.TASK_UPDATE, (_event, id: string, fields: Partial<Task>) => {
    const snapshot = readTaskSnapshot();
    const index = snapshot.tasks.findIndex((task) => task.id === id);
    if (index === -1) return null;
    const current = snapshot.tasks[index];
    const merged = buildTask({
      ...current,
      ...fields,
      id: current.id,
      created_at: current.created_at,
      source: current.source,
    });
    snapshot.tasks[index] = merged;
    if (merged.status === 'done' && merged.completed_at) {
      snapshot.history = [
        ...snapshot.history.filter((item) => item.task_id !== merged.id),
        {
          task_id: merged.id,
          text: merged.text,
          source: merged.source,
          created_at: merged.created_at,
          completed_at: merged.completed_at,
        },
      ].sort((a, b) => String(b.completed_at || '').localeCompare(String(a.completed_at || '')));
    } else {
      snapshot.history = snapshot.history.filter((item) => item.task_id !== merged.id);
    }
    writeTaskSnapshot(snapshot);
    syncTaskPanels(merged);
    return merged;
  });

  ipcMain.handle(IPC.TASK_DELETE, (_event, id: string) => {
    const snapshot = readTaskSnapshot();
    const index = snapshot.tasks.findIndex((task) => task.id === id);
    if (index === -1) return null;
    const [removed] = snapshot.tasks.splice(index, 1);
    snapshot.history = snapshot.history.filter((item) => item.task_id !== id);
    writeTaskSnapshot(snapshot);
    const panel = taskPanels.get(id);
    if (panel && !panel.isDestroyed()) panel.close();
    taskPanels.delete(id);
    return removed;
  });

  ipcMain.handle(IPC.TASK_MARK_DONE, (_event, id: string) => {
    const snapshot = readTaskSnapshot();
    const index = snapshot.tasks.findIndex((task) => task.id === id);
    if (index === -1) return null;
    const current = snapshot.tasks[index];
    const nextCompletedAt = current.status === 'done' ? null : new Date().toISOString();
    const next = buildTask({
      ...current,
      status: current.status === 'done' ? 'pending' : 'done',
      completed_at: nextCompletedAt,
      id: current.id,
      created_at: current.created_at,
      source: current.source,
    });
    snapshot.tasks[index] = next;
    if (next.status === 'done' && next.completed_at) {
      snapshot.history = [
        ...snapshot.history.filter((item) => item.task_id !== next.id),
        {
          task_id: next.id,
          text: next.text,
          source: next.source,
          created_at: next.created_at,
          completed_at: next.completed_at,
        },
      ].sort((a, b) => String(b.completed_at || '').localeCompare(String(a.completed_at || '')));
    } else {
      snapshot.history = snapshot.history.filter((item) => item.task_id !== next.id);
    }
    writeTaskSnapshot(snapshot);
    syncTaskPanels(next);
    return next;
  });

  ipcMain.handle(IPC.TASK_OPEN_PANEL, (_event, task: Task) => {
    if (!task?.id) return false;
    const existing = taskPanels.get(task.id);
    if (existing && !existing.isDestroyed()) {
      if (!overlay.isDestroyed()) showOverlay();
      existing.show();
      existing.focus();
      return true;
    }
    const panel = createTaskPanelWindow(task.id, JSON.stringify(task), overlay);
    taskPanels.set(task.id, panel);
    panel.webContents.once('did-finish-load', () => {
      if (!panel.isDestroyed()) {
        panel.webContents.send(IPC.THEME_CHANGED, loadStoredTheme() || 'graphite');
      }
    });
    panel.on('closed', () => {
      taskPanels.delete(task.id);
    });
    return true;
  });

  ipcMain.handle(IPC.MEMORY_OPEN_PANEL, (_event, memory: Record<string, unknown>) => {
    if (!memory?.id) return false;
    if (memoryPanel && !memoryPanel.isDestroyed()) {
      if (!overlay.isDestroyed()) showOverlay();
      memoryPanel.show();
      memoryPanel.focus();
      return true;
    }
    memoryPanel = createMemoryPanelWindow(JSON.stringify(memory), overlay);
    memoryPanel.webContents.once('did-finish-load', () => {
      if (memoryPanel && !memoryPanel.isDestroyed()) {
        memoryPanel.webContents.send(IPC.THEME_CHANGED, loadStoredTheme() || 'graphite');
      }
    });
    memoryPanel.on('closed', () => {
      memoryPanel = null;
    });
    return true;
  });

  ipcMain.on(IPC.STREAK_OPEN_PANEL, (_event, data: Record<string, unknown>) => {
    if (streakPanel && !streakPanel.isDestroyed()) {
      if (!overlay.isDestroyed()) showOverlay();
      streakPanel.show();
      streakPanel.focus();
      return;
    }
    streakPanel = createStreakPanelWindow(JSON.stringify(data), overlay);
    streakPanel.webContents.once('did-finish-load', () => {
      if (streakPanel && !streakPanel.isDestroyed()) {
        streakPanel.webContents.send(IPC.THEME_CHANGED, loadStoredTheme() || 'graphite');
      }
    });
    streakPanel.on('closed', () => {
      streakPanel = null;
    });
  });

  ipcMain.handle(IPC.TASK_RESCHEDULE, (_event, id: string) => {
    const snapshot = readTaskSnapshot();
    const index = snapshot.tasks.findIndex((task) => task.id === id);
    if (index === -1) return false;
    const current = snapshot.tasks[index];
    const dueBase = current.due_at ? new Date(current.due_at) : new Date();
    const next = new Date();
    next.setDate(next.getDate() + 1);
    next.setHours(dueBase.getHours(), dueBase.getMinutes(), 0, 0);
    snapshot.tasks[index] = buildTask({
      ...current,
      due_at: next.toISOString(),
      carried_over: true,
      failed: false,
      id: current.id,
      created_at: current.created_at,
      source: current.source,
    });
    writeTaskSnapshot(snapshot);
    syncTaskPanels(snapshot.tasks[index]);
    return true;
  });

  ipcMain.on(IPC.CONFIRM_OPEN_CHAT, () => {
    if (!overlay.isDestroyed()) {
      showOverlay();
    }
  });

  ipcMain.on(IPC.SHOW_OVERLAY, () => {
    if (!overlay.isDestroyed()) {
      showOverlay();
    }
  });

  ipcMain.on(IPC.PILL_EXPAND, (_event, size: { width: number; height: number } | null) => {
    setPillNotificationSize(size && typeof size === 'object' ? size : null);
  });

  ipcMain.handle(IPC.CLIPBOARD_WRITE, (_event, text: string) => {
    clipboard.writeText(String(text ?? ''));
  });

  ipcMain.handle(IPC.TASK_UNDO_SAVE, (_event, id: string) => {
    const snapshot = readTaskSnapshot();
    const index = snapshot.tasks.findIndex((task) => task.id === id);
    if (index === -1) return false;
    const [removed] = snapshot.tasks.splice(index, 1);
    snapshot.history = snapshot.history.filter((item) => item.task_id !== id);
    writeTaskSnapshot(snapshot);
    const panel = taskPanels.get(id);
    if (panel && !panel.isDestroyed()) panel.close();
    taskPanels.delete(id);
    return Boolean(removed);
  });

  // ─── Stop recording / stop agent (pill button) ──────────────
  ipcMain.on(IPC.STOP_RECORDING, () => {
    const current = getPillState();
    if (current === 'recording') {
      setPillState('idle');
      sendBridgeMessage({ type: 'hotkey', key: 'f9_stop' });
    } else if (current === 'agent') {
      sendBridgeMessage({ type: 'stop_agent' });
    }
  });

  // ─── Sync state from renderer (Python-driven state) ─────────
  ipcMain.on(IPC.SYNC_STATE, (_e, s: AppState) => {
    if (['idle', 'recording', 'thinking', 'speaking', 'agent'].includes(s)) {
      setPillState(s);
    }
  });

  // ─── Pill drag (renderer-driven, works for mouse + touch) ───
  let lastDragDisplay: Display | null = null;

  ipcMain.on(IPC.PILL_DRAG_START, () => {
    if (pill.isDestroyed()) return;
    pill.setOpacity(0.8);
  });

  ipcMain.on(IPC.PILL_DRAG_MOVE, (_e, screenX: number, screenY: number) => {
    if (pill.isDestroyed()) return;
    const bounds = pill.getBounds();
    const newX = screenX - Math.round(bounds.width / 2);
    const newY = screenY - Math.round(bounds.height / 2);
    pill.setPosition(newX, newY);
    lastDragDisplay = screen.getDisplayNearestPoint({ x: screenX, y: screenY });
  });

  ipcMain.on(IPC.PILL_DRAG_END, () => {
    if (pill.isDestroyed()) return;
    pill.setOpacity(1.0);

    const bounds = pill.getBounds();
    const disp = lastDragDisplay ?? screen.getDisplayMatching(bounds);
    lastDragDisplay = null;

    const newPos = latchToNearestEdge(disp, bounds.x, bounds.y, bounds.width, bounds.height, 14);
    setEdgePosition(newPos);
    savePosition(newPos);

    dragState.isProgrammaticMove = true;
    const pb = getPillBounds(disp);
    setWindowBounds(pill, pb, true);
    if (!overlay.isDestroyed()) {
      const ob = getOverlayBoundsFromEdge(disp, pb, newPos, overlay.getBounds().width, overlay.getBounds().height, 16);
      setWindowBounds(overlay, ob, true);
    }
    setTimeout(() => {
      dragState.isProgrammaticMove = false;
    }, 100);

    // Notify renderer of new edge so it can update orientation immediately
    if (!pill.isDestroyed()) {
      try {
        pill.webContents.send(IPC.PILL_EDGE_CHANGED, newPos.edge);
      } catch { /* ignore */ }
    }
  });

  ipcMain.handle(IPC.PILL_GET_EDGE, () => {
    return getEdgePosition().edge;
  });

  // ─── Quit ───────────────────────────────────────────────────
  ipcMain.on(IPC.QUIT_APP, () => {
    app.quit();
  });
}
