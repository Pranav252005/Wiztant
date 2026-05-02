import type { CSSProperties } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { Task } from '../shared/ipc';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage } from '../shared/useBridge';
import TaskTile from './TaskTile';

export type TaskItem = Task;

export type TaskHistoryItem = {
  task_id: string;
  text: string;
  source: 'voice' | 'typed';
  created_at?: string | null;
  completed_at?: string | null;
};

type Props = {
  theme: Theme['panel'];
  active: boolean;
  tasks: TaskItem[];
  history: TaskHistoryItem[];
  suggestion: string | null;
  loading?: boolean;
  onOpenPanel: (task: Task) => Promise<void>;
  onMarkDone: (id: string) => Promise<void>;
  onDeleteTask: (id: string) => Promise<void>;
  onTaskAdded?: () => void;
  sortMode?: SortMode;
  onSortChange?: (mode: SortMode) => void;
};

function formatDueLabel(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const timeOnly = new Intl.DateTimeFormat([], {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);

  if (date.toDateString() === now.toDateString()) return `Today ${timeOnly}`;
  if (date.toDateString() === tomorrow.toDateString()) return `Tomorrow ${timeOnly}`;
  return new Intl.DateTimeFormat([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatHistoryLabel(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return `Today · ${new Intl.DateTimeFormat([], {
      hour: 'numeric',
      minute: '2-digit',
    }).format(date)}`;
  }
  return new Intl.DateTimeFormat([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function buildDueAtISO(day: 'none' | 'today' | 'tomorrow', time: string, meridiem: '24' | 'am' | 'pm'): string | null {
  if (day === 'none' || !time) return null;
  const [hStr, mStr] = time.split(':');
  let hour = Number.parseInt(hStr || '', 10);
  const minute = Number.parseInt(mStr || '0', 10);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
  if (meridiem === 'pm' && hour < 12) hour += 12;
  if (meridiem === 'am' && hour === 12) hour = 0;
  const now = new Date();
  const date = new Date(now);
  if (day === 'tomorrow') date.setDate(date.getDate() + 1);
  date.setHours(hour, minute, 0, 0);
  if (day === 'today' && date.getTime() <= now.getTime()) {
    date.setDate(date.getDate() + 1);
  }
  return date.toISOString();
}

export type SortMode = 'smart' | 'due_asc' | 'due_desc' | 'alpha_asc' | 'alpha_desc';

const SORT_LABELS: Record<SortMode, string> = {
  smart: 'Smart',
  due_asc: 'Due: Soonest',
  due_desc: 'Due: Latest',
  alpha_asc: 'A → Z',
  alpha_desc: 'Z → A',
};

export default function TasksPanel({
  theme,
  active,
  tasks,
  history,
  suggestion,
  loading = false,
  onOpenPanel,
  onMarkDone,
  onDeleteTask,
  onTaskAdded,
  sortMode: sortModeProp,
  onSortChange,
}: Props) {
  const [focusIdx, setFocusIdx] = useState(0);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState('');
  const [draftDay, setDraftDay] = useState<'none' | 'today' | 'tomorrow'>('none');
  const [draftTime, setDraftTime] = useState('');
  const [draftMeridiem, setDraftMeridiem] = useState<'24' | 'am' | 'pm'>('pm');
  const sortMode = sortModeProp ?? 'smart';
  const setSortMode = onSortChange ?? (() => {});

  const nowMs = Date.now();

  const sortedTasks = useMemo(() => {
    const list = [...tasks];
    if (sortMode === 'smart') {
      return list.sort((a, b) => {
        // 1. Status: pending / in_progress before done
        if (a.status !== b.status) {
          const order = { pending: 0, in_progress: 1, done: 2 };
          return (order[a.status as keyof typeof order] ?? 0) - (order[b.status as keyof typeof order] ?? 0);
        }

        // 2. Failed tasks at the bottom of pending
        const aFailed = Boolean(a.failed);
        const bFailed = Boolean(b.failed);
        if (aFailed !== bFailed) return aFailed ? 1 : -1;

        // 3. For active tasks (pending / in_progress): overdue first, then soonest due
        if ((a.status === 'pending' || a.status === 'in_progress') && !aFailed && !bFailed) {
          const aDue = a.due_at ? new Date(a.due_at).getTime() : 0;
          const bDue = b.due_at ? new Date(b.due_at).getTime() : 0;
          const aOverdue = aDue > 0 && aDue < nowMs;
          const bOverdue = bDue > 0 && bDue < nowMs;
          if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
          if (aDue !== bDue) {
            // Tasks with due dates before those without; sooner due first
            if (aDue === 0) return 1;
            if (bDue === 0) return -1;
            return aDue - bDue;
          }
        }

        // 4. Fallback: newest created first
        return (b.created_at || '').localeCompare(a.created_at || '');
      });
    }
    if (sortMode === 'due_asc') {
      return list.sort((a, b) => {
        const aDue = a.due_at ? new Date(a.due_at).getTime() : Number.MAX_SAFE_INTEGER;
        const bDue = b.due_at ? new Date(b.due_at).getTime() : Number.MAX_SAFE_INTEGER;
        if (aDue !== bDue) return aDue - bDue;
        return (a.text || '').localeCompare(b.text || '');
      });
    }
    if (sortMode === 'due_desc') {
      return list.sort((a, b) => {
        const aDue = a.due_at ? new Date(a.due_at).getTime() : 0;
        const bDue = b.due_at ? new Date(b.due_at).getTime() : 0;
        if (aDue !== bDue) return bDue - aDue;
        return (b.text || '').localeCompare(a.text || '');
      });
    }
    if (sortMode === 'alpha_asc') {
      return list.sort((a, b) => (a.text || '').localeCompare(b.text || ''));
    }
    if (sortMode === 'alpha_desc') {
      return list.sort((a, b) => (b.text || '').localeCompare(a.text || ''));
    }
    return list;
  }, [tasks, nowMs, sortMode]);
  const activeTasks = useMemo(() => sortedTasks.filter((task) => !task.failed), [sortedTasks]);
  const failedTasks = useMemo(() => sortedTasks.filter((task) => task.failed), [sortedTasks]);

  useEffect(() => {
    if (focusIdx > activeTasks.length - 1) {
      setFocusIdx(Math.max(0, activeTasks.length - 1));
    }
  }, [activeTasks, focusIdx]);

  useEffect(() => {
    if (pendingDeleteId && !tasks.some((task) => task.id === pendingDeleteId)) {
      setPendingDeleteId(null);
    }
  }, [pendingDeleteId, tasks]);

  useEffect(() => {
    if (!active) return;

    const handler = (event: KeyboardEvent) => {
      if (activeTasks.length === 0) return;

      const element = document.activeElement;
      if (
        element &&
        (element.tagName === 'INPUT' ||
          element.tagName === 'TEXTAREA' ||
          (element as HTMLElement).isContentEditable)
      ) {
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setFocusIdx((index) => Math.min(index + 1, activeTasks.length - 1));
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        setFocusIdx((index) => Math.max(index - 1, 0));
      } else if (event.key === ' ') {
        const task = activeTasks[focusIdx];
        if (!task) return;
        event.preventDefault();
        void handleToggle(task.id);
      } else if (event.key === 'Delete') {
        const task = activeTasks[focusIdx];
        if (!task) return;
        event.preventDefault();
        setPendingDeleteId(task.id);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [active, activeTasks, focusIdx, pendingDeleteId]);

  const recentHistory = useMemo(() => history.slice(0, 8), [history]);

  const completedTodayCount = useMemo(() => {
    const today = new Date().toDateString();
    return history.filter((item) => {
      const completed = item.completed_at ? new Date(item.completed_at) : null;
      return completed && !Number.isNaN(completed.getTime()) && completed.toDateString() === today;
    }).length;
  }, [history]);

  const handleToggle = async (taskId: string) => {
    setPendingDeleteId((current) => (current === taskId ? null : current));
    await onMarkDone(taskId);
  };

  const handleDeleteClick = (taskId: string) => {
    // Open the confirmation modal instead of deleting inline.
    setPendingDeleteId(taskId);
  };

  const confirmDelete = async () => {
    if (!pendingDeleteId) return;
    await onDeleteTask(pendingDeleteId);
    setPendingDeleteId(null);
  };

  const cancelDelete = () => setPendingDeleteId(null);

  const submitDraft = () => {
    const text = draftText.trim();
    if (!text) return;
    const due_at = buildDueAtISO(draftDay, draftTime, draftMeridiem);
    sendBridgeMessage({ type: 'tasks/add', text, source: 'typed', due_at });
    setDraftText('');
    setDraftDay('none');
    setDraftTime('');
    setDraftMeridiem('pm');
    onTaskAdded?.();
  };

  const pendingDeleteTask = pendingDeleteId ? tasks.find((t) => t.id === pendingDeleteId) : null;

  const inputBaseStyle: CSSProperties = {
    background: theme.inputBg,
    color: theme.text,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    padding: '8px 10px',
    fontSize: 12,
    outline: 'none',
  };

  const formSection = (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        marginBottom: 12,
        padding: '12px',
        borderRadius: 14,
        border: `1px solid ${theme.border}`,
        background: theme.inputBg,
      }}
    >
      <input
        type="text"
        value={draftText}
        placeholder="Add a task…"
        onChange={(e) => setDraftText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            submitDraft();
          }
        }}
        style={{ ...inputBaseStyle, width: '100%' }}
      />
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          value={draftDay}
          onChange={(e) => setDraftDay(e.target.value as 'none' | 'today' | 'tomorrow')}
          style={{ ...inputBaseStyle, padding: '6px 8px' }}
        >
          <option value="none">No due time</option>
          <option value="today">Today</option>
          <option value="tomorrow">Tomorrow</option>
        </select>
        <input
          type="text"
          placeholder="hh:mm"
          value={draftTime}
          disabled={draftDay === 'none'}
          onChange={(e) => setDraftTime(e.target.value)}
          style={{ ...inputBaseStyle, padding: '6px 8px', opacity: draftDay === 'none' ? 0.5 : 1 }}
        />
        <select
          value={draftMeridiem}
          disabled={draftDay === 'none'}
          onChange={(e) => setDraftMeridiem(e.target.value as '24' | 'am' | 'pm')}
          style={{ ...inputBaseStyle, padding: '6px 8px', opacity: draftDay === 'none' ? 0.5 : 1 }}
        >
          <option value="pm">PM</option>
          <option value="am">AM</option>
          <option value="24">24h</option>
        </select>
        <button
          type="button"
          onClick={submitDraft}
          disabled={!draftText.trim()}
          style={{
            marginLeft: 'auto',
            background: theme.aiAccent,
            color: '#0a0a0a',
            border: 'none',
            borderRadius: 10,
            padding: '7px 14px',
            fontSize: 12,
            fontWeight: 600,
            cursor: draftText.trim() ? 'pointer' : 'not-allowed',
            opacity: draftText.trim() ? 1 : 0.5,
          }}
        >
          Add
        </button>
      </div>
    </div>
  );

  const deleteModal = pendingDeleteTask ? (
    <div
      onClick={cancelDelete}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          cancelDelete();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          confirmDelete();
        }
      }}
      tabIndex={-1}
      ref={(node) => {
        // Auto-focus so Enter/Escape are captured immediately.
        if (node) node.focus();
      }}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        outline: 'none',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 280,
          padding: 16,
          borderRadius: 14,
          border: `1px solid ${theme.border}`,
          background: theme.bg || theme.inputBg,
          color: theme.text,
          boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700 }}>Delete this task?</div>
        <div style={{ fontSize: 11, color: theme.textMuted, wordBreak: 'break-word' }}>
          “{pendingDeleteTask.text}”
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 4, justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={cancelDelete}
            style={{
              background: 'transparent',
              color: theme.text,
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirmDelete}
            style={{
              background: '#e5484d',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '6px 14px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  ) : null;

  const isEmpty = activeTasks.length === 0 && failedTasks.length === 0 && recentHistory.length === 0;

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '12px 12px 14px', position: 'relative' }}>
      {formSection}
      {isEmpty ? (
        <div
          style={{
            padding: 18,
            color: theme.textMuted,
            fontSize: 12,
            textAlign: 'center',
            lineHeight: 1.6,
          }}
        >
          {suggestion ? `${suggestion} ` : ''}No tasks yet. Say “add task review PR by 5 pm” or type above.
        </div>
      ) : null}
      {suggestion && !isEmpty ? (
        <div
          style={{
            marginBottom: 12,
            padding: '10px 12px',
            borderRadius: 12,
            border: `1px solid ${theme.border}`,
            background: `${theme.aiAccent}10`,
            color: theme.textMuted,
            fontSize: 11,
            lineHeight: 1.5,
          }}
        >
          {suggestion}
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 10,
          padding: '0 4px',
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Today</div>
          <div style={{ fontSize: 11, color: theme.textMuted }}>
            {activeTasks.filter((task) => task.status !== 'done').length} active tasks · {completedTodayCount} done today{loading ? ' · syncing…' : ''}
          </div>
        </div>
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          style={{
            background: theme.inputBg,
            color: theme.text,
            border: `1px solid ${theme.border}`,
            borderRadius: 8,
            padding: '4px 8px',
            fontSize: 11,
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {(Object.keys(SORT_LABELS) as SortMode[]).map((mode) => (
            <option key={mode} value={mode}>
              {SORT_LABELS[mode]}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <AnimatePresence initial={false}>
        {activeTasks.map((task, index) => (
          <motion.div
            key={task.id}
            layout
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.96, transition: { duration: 0.18 } }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <TaskTile
              task={task}
              theme={theme}
              focused={index === focusIdx}
              onFocus={() => setFocusIdx(index)}
              onToggle={() => handleToggle(task.id)}
              onDelete={() => handleDeleteClick(task.id)}
              onOpenPanel={async () => {
                await onOpenPanel(task);
              }}
            />
          </motion.div>
        ))}
        </AnimatePresence>
      </div>

      {failedTasks.length > 0 ? (
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ padding: '0 4px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: theme.text }}>Undone</div>
            <div style={{ fontSize: 11, color: theme.textMuted }}>
              Missed tasks that rolled over and were not completed
            </div>
          </div>
          {failedTasks.map((task) => (
            <TaskTile
              key={task.id}
              task={task}
              theme={theme}
              focused={false}
              onFocus={() => undefined}
              onToggle={() => Promise.resolve()}
              onDelete={() => handleDeleteClick(task.id)}
              onOpenPanel={() => Promise.resolve()}
              readOnly
            />
          ))}
        </div>
      ) : null}

      {recentHistory.length > 0 ? (
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ padding: '0 4px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: theme.text }}>Recent history</div>
            <div style={{ fontSize: 11, color: theme.textMuted }}>
              Completed tasks from today and previous days
            </div>
          </div>
          {recentHistory.map((item) => (
            <div
              key={`${item.task_id}-${item.completed_at}`}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 12,
                border: `1px solid ${theme.border}`,
                background: `${theme.inputBg}`,
              }}
            >
              <span
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: `${theme.aiAccent}18`,
                  color: theme.aiAccent,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  flexShrink: 0,
                }}
              >
                ✓
              </span>
              <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ fontSize: 12, color: theme.text, lineHeight: 1.45, wordBreak: 'break-word' }}>
                  {item.text}
                </div>
                <div style={{ fontSize: 10, color: theme.textMuted }}>
                  {formatHistoryLabel(item.completed_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {deleteModal}
    </div>
  );
}
