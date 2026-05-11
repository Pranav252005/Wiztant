import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import type { Task } from '../shared/ipc';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage } from '../shared/useBridge';

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

function formatSnoozeLabel(value?: string | null) {
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

  if (date.toDateString() === now.toDateString()) return `Snoozed until ${timeOnly}`;
  if (date.toDateString() === tomorrow.toDateString()) return `Snoozed until Tomorrow ${timeOnly}`;
  return `Snoozed until ${new Intl.DateTimeFormat([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date)}`;
}

const SNOOZED_UNTIL_KEY = 'whiztant.snooze_presets';

function readSnoozePresets(): number[] {
  try {
    const v = window.localStorage.getItem(SNOOZED_UNTIL_KEY);
    if (v) return JSON.parse(v) as number[];
  } catch { /* noop */ }
  return [15, 30, 60, 1440];
}

const PRESET_LABELS: Record<number, string> = {
  15: '15 min',
  30: '30 min',
  60: '1 hour',
  1440: 'Tomorrow',
};

type Props = {
  task: Task;
  theme: Theme['panel'];
  focused: boolean;
  onFocus: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onOpenPanel: () => Promise<void>;
  readOnly?: boolean;
};

export default function TaskTile({
  task,
  theme,
  focused,
  onFocus,
  onToggle,
  onDelete,
  onOpenPanel,
  readOnly = false,
}: Props) {
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const snoozeRef = useRef<HTMLDivElement>(null);

  // Close snooze dropdown on outside click
  useEffect(() => {
    if (!snoozeOpen) return;
    const handle = (e: MouseEvent) => {
      if (snoozeRef.current && !snoozeRef.current.contains(e.target as Node)) {
        setSnoozeOpen(false);
      }
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [snoozeOpen]);

  const handleSnooze = useCallback((minutes: number) => {
    sendBridgeMessage({ type: 'tasks/snooze', taskId: task.id, minutes });
    setSnoozeOpen(false);
  }, [task.id]);

  const snoozePresets = useMemo(() => readSnoozePresets(), []);

  const taskBody = useMemo(() => (task.content || task.text || '').trim(), [task.content, task.text]);
  const preview = useMemo(() => {
    if (!taskBody) return '';
    return taskBody.length > 140 ? `${taskBody.slice(0, 140).trim()}…` : taskBody;
  }, [taskBody]);
  const isLarge = task.task_type === 'large' || taskBody.length > 400;
  const isDone = task.status === 'done';
  const isInProgress = task.status === 'in_progress';
  const isFailed = Boolean(task.failed);
  const dueLabel = formatDueLabel(task.due_at);
  const isOverdue = !isDone && !isFailed && !!task.due_at && new Date(task.due_at).getTime() <= Date.now();

  // Snooze state
  const isSnoozed = !!task.snoozed_until && new Date(task.snoozed_until).getTime() > Date.now();
  const snoozeLabel = isSnoozed ? formatSnoozeLabel(task.snoozed_until) : '';
  const canSnooze = !isDone && !isFailed && !readOnly;

  return (
    <div
      draggable={!readOnly}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', task.id);
        e.dataTransfer.effectAllowed = 'move';
      }}
      tabIndex={0}
      onFocus={onFocus}
      onClick={() => {
        onFocus();
        if (!readOnly) {
          void onOpenPanel();
        }
      }}
      onKeyDown={(event) => {
        if ((event.key === 'Enter' || event.key === ' ') && !readOnly) {
          event.preventDefault();
          void onOpenPanel();
        }
      }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        width: '100%',
        padding: '12px',
        borderRadius: 14,
        border: `1px solid ${focused ? theme.aiAccent : isFailed ? 'rgba(239,68,68,0.42)' : isOverdue ? `${theme.text}55` : isSnoozed ? `${theme.aiAccent}33` : theme.border}`,
        background: isFailed ? 'rgba(127,29,29,0.18)' : focused ? `${theme.aiAccent}12` : isSnoozed ? `${theme.aiAccent}08` : theme.inputBg,
        color: isDone ? theme.textMuted : isSnoozed ? theme.textMuted : theme.text,
        opacity: isSnoozed ? 0.72 : 1,
        transition: 'background 0.12s, border-color 0.12s, opacity 0.12s',
        cursor: readOnly ? 'default' : 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        {readOnly ? (
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              border: '1px solid rgba(239,68,68,0.35)',
              background: 'rgba(239,68,68,0.12)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              fontSize: 11,
              color: '#FCA5A5',
            }}
          >
            !
          </span>
        ) : (
          <button
            type="button"
            aria-label={isDone ? `Mark ${task.text} as pending` : isInProgress ? `Mark ${task.text} as done` : `Mark ${task.text} as done`}
            onClick={(event) => {
              event.stopPropagation();
              void onToggle();
            }}
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              border: `1px solid ${isDone ? theme.aiAccent : theme.textMuted}`,
              background: isDone ? theme.aiAccent : 'transparent',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              fontSize: 12,
              color: isDone ? '#0a0a0a' : theme.textMuted,
              cursor: 'pointer',
            }}
          >
            {isDone ? '✓' : ''}
          </button>
        )}

        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: 999,
                border: `1px solid ${isInProgress ? `${theme.aiAccent}55` : theme.border}`,
                background: isInProgress ? `${theme.aiAccent}22` : `${theme.aiAccent}10`,
                color: isInProgress ? theme.aiAccent : theme.textMuted,
                fontSize: 10,
                flexShrink: 0,
              }}
            >
              {isInProgress ? 'IN PROGRESS' : isLarge ? 'LARGE' : 'SMALL'}
            </span>
            {dueLabel ? (
              <span
                style={{
                  padding: '3px 8px',
                  borderRadius: 999,
                  border: `1px solid ${isOverdue ? `${theme.text}55` : theme.border}`,
                  background: isOverdue ? `${theme.text}12` : `${theme.aiAccent}10`,
                  color: isOverdue ? theme.text : theme.textMuted,
                  fontSize: 10,
                  flexShrink: 0,
                }}
              >
                {isOverdue ? `Due ${dueLabel}` : `By ${dueLabel}`}
              </span>
            ) : null}
            {isSnoozed ? (
              <span
                style={{
                  padding: '3px 8px',
                  borderRadius: 999,
                  border: `1px solid ${theme.aiAccent}55`,
                  background: `${theme.aiAccent}18`,
                  color: theme.aiAccent,
                  fontSize: 10,
                  flexShrink: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
                title={snoozeLabel}
              >
                <span style={{ fontSize: 9 }}>🕐</span>
                {snoozeLabel}
              </span>
            ) : null}
            <span
              style={{
                padding: '3px 8px',
                borderRadius: 999,
                border: `1px solid ${theme.border}`,
                background: 'transparent',
                color: theme.textMuted,
                fontSize: 10,
                flexShrink: 0,
              }}
            >
              {task.source === 'voice' ? 'VOICE' : 'TYPED'}
            </span>
          </div>

          <div
            style={{
              fontSize: 12,
              lineHeight: 1.45,
              textDecoration: isDone ? 'line-through' : 'none',
              opacity: isDone ? 0.74 : 1,
              wordBreak: 'break-word',
              fontWeight: 600,
            }}
          >
            {task.text}
          </div>
          {isFailed ? (
            <div style={{ fontSize: 11, color: '#FCA5A5', lineHeight: 1.45 }}>
              Not completed — please review
            </div>
          ) : null}
          {preview && preview !== task.text ? (
            <div style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.45, wordBreak: 'break-word' }}>
              {preview}
            </div>
          ) : null}
          {(task.category || task.difficulty) ? (
            <div style={{ display: 'flex', gap: 4, marginTop: 2, flexWrap: 'wrap' }}>
              {task.category ? (
                <span style={{
                  padding: '2px 8px',
                  borderRadius: 10,
                  background: `${theme.aiAccent}18`,
                  color: theme.aiAccent,
                  fontSize: 10,
                  fontWeight: 600,
                }}>
                  {task.category}
                </span>
              ) : null}
              {task.difficulty ? (
                <span style={{
                  padding: '2px 8px',
                  borderRadius: 10,
                  background: task.difficulty === 'hard' ? '#ef444418' : task.difficulty === 'easy' ? '#22c55e18' : '#eab30818',
                  color: task.difficulty === 'hard' ? '#ef4444' : task.difficulty === 'easy' ? '#22c55e' : '#eab308',
                  fontSize: 10,
                  fontWeight: 600,
                }}>
                  {task.difficulty.charAt(0).toUpperCase() + task.difficulty.slice(1)}
                </span>
              ) : null}
            </div>
          ) : null}
          {!readOnly ? (
            <div style={{ fontSize: 10, color: theme.textMuted }}>
              Opens in a separate side panel for editing
            </div>
          ) : null}
        </div>

        {/* Snooze button + dropdown */}
        {canSnooze ? (
          <div ref={snoozeRef} style={{ position: 'relative', flexShrink: 0 }}>
            <button
              type="button"
              aria-label={`Snooze ${task.text}`}
              title="Snooze"
              onClick={(event) => {
                event.stopPropagation();
                setSnoozeOpen((v) => !v);
              }}
              style={{
                width: 26,
                height: 26,
                borderRadius: 8,
                border: 'none',
                background: snoozeOpen ? `${theme.aiAccent}22` : 'transparent',
                color: theme.textMuted,
                cursor: 'pointer',
                flexShrink: 0,
                padding: 0,
                fontSize: 13,
                lineHeight: 1,
              }}
            >
              ⏸
            </button>
            {snoozeOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 30,
                  right: 0,
                  zIndex: 100,
                  minWidth: 120,
                  background: theme.inputBg,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 10,
                  padding: '6px 0',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div
                  style={{
                    padding: '4px 12px',
                    fontSize: 10,
                    color: theme.textMuted,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}
                >
                  Snooze for…
                </div>
                {snoozePresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSnooze(preset);
                    }}
                    style={{
                      padding: '6px 12px',
                      fontSize: 12,
                      color: theme.text,
                      background: 'transparent',
                      border: 'none',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = `${theme.aiAccent}15`;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    {PRESET_LABELS[preset] || `${preset} min`}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : null}

        <button
          type="button"
          aria-label={`Delete ${task.text}`}
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          style={{
            width: 26,
            height: 26,
            borderRadius: 8,
            border: 'none',
            background: 'transparent',
            color: theme.textMuted,
            cursor: 'pointer',
            flexShrink: 0,
            padding: 0,
            fontSize: 18,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
    </div>
  );
}
