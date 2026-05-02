import { useEffect, useState } from 'react';

interface ExistingTask {
  id: string;
  title: string;
  scheduled_for: string;
  hour: number;
  minute: number;
}

interface Props {
  existingTask: ExistingTask;
  newTime: string;
  onDismiss: () => void;
  compact?: boolean;
}

const AUTO_DISMISS_MS = 10_000;

function formatScheduled(scheduled: string, hour: number, minute: number): string {
  if (scheduled) {
    try {
      const dt = new Date(scheduled);
      if (!Number.isNaN(dt.getTime())) {
        const date = new Intl.DateTimeFormat([], { weekday: 'short', month: 'short', day: 'numeric' }).format(dt);
        const time = new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).format(dt);
        return `${date} at ${time}`;
      }
    } catch {
      // fall through to hour/minute fallback
    }
  }
  if (typeof hour === 'number') {
    const h12 = ((hour + 11) % 12) + 1;
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const mm = String(minute || 0).padStart(2, '0');
    return `${h12}:${mm} ${ampm}`;
  }
  return 'previously saved';
}

export default function DuplicateTaskNotification({ existingTask, newTime, onDismiss, compact }: Props) {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const t = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const scheduledLabel = formatScheduled(existingTask.scheduled_for, existingTask.hour, existingTask.minute);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: compact ? '6px 10px' : '10px 12px',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            flex: 1,
            minWidth: 0,
            color: '#C4956A',
            fontSize: 11,
            fontWeight: 700,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          Already saved — {existingTask.title} {expanded ? '▴' : '▾'}
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onDismiss();
          }}
          style={{
            border: 'none',
            background: 'transparent',
            color: '#C4956A',
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
            padding: 0,
            width: 18,
            height: 18,
          }}
          title="Dismiss"
        >
          ×
        </button>
      </div>
      {expanded ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '0 12px 10px' }}>
          <div style={{ color: '#FAF6F1', fontSize: 12, fontWeight: 600, lineHeight: 1.4, wordBreak: 'break-word' }}>
            {existingTask.title}
          </div>
          <div style={{ color: 'rgba(250,246,241,0.7)', fontSize: 10.5 }}>
            Saved for: <span style={{ color: '#C4956A' }}>{scheduledLabel}</span>
          </div>
          {newTime ? (
            <div style={{ color: 'rgba(250,246,241,0.55)', fontSize: 10.5 }}>
              You said: <span style={{ color: '#FAF6F1' }}>{newTime}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
