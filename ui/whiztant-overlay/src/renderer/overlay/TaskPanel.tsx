import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import type { Task } from '../shared/ipc';
import { defaultTheme, themes } from '../shared/themes';
import type { ThemeName } from '../shared/ipc';
import { sendBridgeMessage } from '../shared/useBridge';
import CustomDropdown from '../shared/CustomDropdown';

function parseTaskFromHash(): Task | null {
  try {
    const hash = window.location.hash || '';
    const [, query = ''] = hash.split('?');
    const params = new URLSearchParams(query);
    const raw = params.get('task');
    if (!raw) return null;
    return JSON.parse(decodeURIComponent(raw)) as Task;
  } catch {
    return null;
  }
}

function to12Hour(hour24: number, minute: number): { time: string; period: 'AM' | 'PM' } {
  const period: 'AM' | 'PM' = hour24 >= 12 ? 'PM' : 'AM';
  const hour12 = hour24 % 12 || 12;
  const hh = String(hour12).padStart(2, '0');
  const mm = String(minute).padStart(2, '0');
  return { time: `${hh}:${mm}`, period };
}

function parseDue(value?: string | null) {
  if (!value) return { day: 'none', time: '', period: 'PM' as 'AM' | 'PM' };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { day: 'none', time: '', period: 'PM' as 'AM' | 'PM' };
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const { time, period } = to12Hour(date.getHours(), date.getMinutes());
  const day = date.toDateString() === now.toDateString()
    ? 'today'
    : date.toDateString() === tomorrow.toDateString()
      ? 'tomorrow'
      : 'today';
  return { day, time, period };
}

function buildDue(day: string, time: string, period: 'AM' | 'PM') {
  if (day === 'none' || !time.trim()) return null;
  const match = time.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  let hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 1 || hour > 12 || minute > 59) return null;
  if (period === 'PM' && hour !== 12) hour += 12;
  if (period === 'AM' && hour === 12) hour = 0;
  const date = new Date();
  if (day === 'tomorrow') date.setDate(date.getDate() + 1);
  date.setHours(hour, minute, 0, 0);
  return date.toISOString();
}

function formatDueLabel(value?: string | null) {
  if (!value) return 'No due time';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No due time';
  return new Intl.DateTimeFormat([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export default function TaskPanel() {
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const theme = themes[themeName].panel;
  const [task, setTask] = useState<Task | null>(() => parseTaskFromHash());
  const [title, setTitle] = useState(task?.text || '');
  const initialDue = useMemo(() => parseDue(task?.due_at), [task?.due_at]);
  const [dueDay, setDueDay] = useState(initialDue.day);
  const [dueTime, setDueTime] = useState(initialDue.time);
  const [duePeriod, setDuePeriod] = useState<'AM' | 'PM'>(initialDue.period);
  const [category, setCategory] = useState(task?.category || '');
  const [difficulty, setDifficulty] = useState(task?.difficulty || 'medium');
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const contentLength = title.trim().length;

  const dragRegionStyle: CSSProperties & { WebkitAppRegion: 'drag' } = {
    WebkitAppRegion: 'drag',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    background: theme.headerBg,
    borderBottom: `1px solid ${theme.border}`,
    flexShrink: 0,
  };
  const noDragButtonStyle: CSSProperties & { WebkitAppRegion: 'no-drag' } = {
    WebkitAppRegion: 'no-drag',
    background: 'transparent',
    color: theme.textMuted,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '6px 10px',
    fontSize: 11,
    cursor: 'pointer',
  };

  useEffect(() => {
    window.api.onThemeChanged((name) => setThemeName(name));
  }, []);

  useEffect(() => {
    const nextTask = parseTaskFromHash();
    setTask(nextTask);
    setTitle(nextTask?.text || '');
    const nextDue = parseDue(nextTask?.due_at);
    setDueDay(nextDue.day);
    setDueTime(nextDue.time);
    setDuePeriod(nextDue.period);
    setCategory(nextTask?.category || '');
    setDifficulty(nextTask?.difficulty || 'medium');
  }, []);

  const save = async () => {
    if (!task?.id || !title.trim()) return;
    setStatus('saving');
    try {
      const updated = await window.api.updateTask(task.id, {
        text: title.trim(),
        content: null,
        due_at: buildDue(dueDay, dueTime, duePeriod),
        task_type: 'small',
        category: category.trim() || null,
        difficulty: difficulty as Task['difficulty'],
      });
      if (!updated) {
        setStatus('error');
        return;
      }
      setTask(updated);
      setStatus('saved');
      window.setTimeout(() => setStatus((current) => (current === 'saved' ? 'idle' : current)), 1400);

      // Auto-learn spelling corrections when the user edited the title
      const originalText = task.text || '';
      const correctedText = title.trim();
      if (originalText && correctedText && originalText !== correctedText) {
        sendBridgeMessage({
          type: 'learn_from_edit',
          original: originalText,
          corrected: correctedText,
        });
      }
    } catch {
      setStatus('error');
    }
  };

  const copyContent = async () => {
    const value = title.trim();
    if (!value) return;
    await window.api.writeClipboard(value);
  };

  if (!task) {
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: theme.bg,
          color: theme.textMuted,
          border: `1px solid ${theme.border}`,
          borderRadius: 16,
          fontFamily: 'Geist, "Segoe UI", sans-serif',
        }}
      >
        No task selected.
      </div>
    );
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: theme.bg,
        color: theme.text,
        border: `1px solid ${theme.border}`,
        borderRadius: 16,
        overflow: 'hidden',
        fontFamily: 'Geist, "Segoe UI", sans-serif',
      }}
    >
      <div style={dragRegionStyle}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: theme.text }}>Task Panel</div>
          <div style={{ fontSize: 10, color: theme.textMuted }}>All task editing happens here in the side panel</div>
        </div>
        <button
          type="button"
          onClick={() => void copyContent()}
          style={noDragButtonStyle}
        >
          Copy
        </button>
        <button
          type="button"
          onClick={() => window.close()}
          style={noDragButtonStyle}
        >
          Close
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 12, minHeight: 0, flex: 1, overflowY: 'auto' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            padding: '10px 12px',
            borderRadius: 12,
            border: `1px solid ${theme.border}`,
            background: `${theme.aiAccent}10`,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Small task
            </div>
            <div style={{ fontSize: 11, color: theme.text }}>{formatDueLabel(task.due_at)}</div>
          </div>
          <div style={{ fontSize: 10, color: theme.textMuted, flexShrink: 0 }}>{contentLength} chars</div>
        </div>

        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Task title"
          style={{
            background: theme.inputBg,
            color: theme.text,
            border: `1px solid ${theme.border}`,
            borderRadius: 10,
            padding: '10px 12px',
            fontSize: 12,
            outline: 'none',
          }}
        />

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="Category"
            style={{
              background: theme.inputBg,
              color: theme.text,
              border: `1px solid ${theme.border}`,
              borderRadius: 10,
              padding: '8px 10px',
              fontSize: 11,
              outline: 'none',
              width: 140,
            }}
          />
          <CustomDropdown
            value={difficulty}
            onChange={(v) => setDifficulty(v as 'easy' | 'medium' | 'hard')}
            options={[
              { value: 'easy', label: 'Easy' },
              { value: 'medium', label: 'Medium' },
              { value: 'hard', label: 'Hard' },
            ]}
            theme={theme}
            style={{ width: 100 }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            flexShrink: 0,
            marginBottom: 10,
            paddingTop: 2,
          }}
        >
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <CustomDropdown
              value={dueDay}
              onChange={(v) => setDueDay(v)}
              options={[
                { value: 'none', label: 'No due time' },
                { value: 'today', label: 'Today' },
                { value: 'tomorrow', label: 'Tomorrow' },
              ]}
              theme={theme}
              style={{ width: 120 }}
            />
            <input
              type="text"
              value={dueTime}
              onChange={(event) => setDueTime(event.target.value)}
              placeholder="hh:mm"
              disabled={dueDay === 'none'}
              style={{
                background: theme.inputBg,
                color: theme.text,
                border: `1px solid ${theme.border}`,
                borderRadius: 10,
                padding: '8px 10px',
                fontSize: 11,
                outline: 'none',
                opacity: dueDay === 'none' ? 0.5 : 1,
                width: 64,
              }}
            />
            <button
              type="button"
              onClick={() => setDuePeriod((p) => (p === 'AM' ? 'PM' : 'AM'))}
              disabled={dueDay === 'none'}
              style={{
                background: theme.inputBg,
                color: theme.text,
                border: `1px solid ${theme.border}`,
                borderRadius: 10,
                padding: '8px 10px',
                fontSize: 11,
                fontWeight: 700,
                cursor: dueDay === 'none' ? 'not-allowed' : 'pointer',
                opacity: dueDay === 'none' ? 0.5 : 1,
                minWidth: 44,
              }}
            >
              {duePeriod}
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ fontSize: 10, color: status === 'error' ? theme.text : theme.textMuted }}>
              {status === 'saving'
                ? 'Saving…'
                : status === 'saved'
                  ? 'Saved'
                  : status === 'error'
                    ? 'Could not save task'
                    : 'Small task'}
            </span>
            <button
              type="button"
              onClick={() => void save()}
              disabled={!title.trim() || status === 'saving'}
              style={{
                background: theme.aiAccent,
                color: '#0a0a0a',
                border: 'none',
                borderRadius: 10,
                padding: '8px 14px',
                fontSize: 11,
                fontWeight: 700,
                cursor: !title.trim() || status === 'saving' ? 'not-allowed' : 'pointer',
                opacity: !title.trim() || status === 'saving' ? 0.6 : 1,
              }}
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
