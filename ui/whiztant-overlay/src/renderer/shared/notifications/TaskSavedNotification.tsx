import type { ReactNode } from 'react';
import type { Task } from '../ipc';

interface Props {
  task: Task;
  compact?: boolean;
  onSave: () => void;
  onDecline: () => void;
  onEdit: (task: Task) => void;
}

function formatSavedAt(value?: string | null): { day: string; time: string } {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return { day: 'Today', time: '' };
  const day = new Intl.DateTimeFormat([], { weekday: 'short' }).format(date);
  const time = new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).format(date);
  return { day, time };
}

export default function TaskSavedNotification({ task, compact, onSave, onDecline, onEdit }: Props) {
  const { day, time } = formatSavedAt(task.created_at);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? 6 : 10,
        padding: compact ? '8px 10px' : '10px 12px',
        color: '#FAF6F1',
        width: '100%',
        height: '100%',
        justifyContent: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: compact ? 12 : 13,
              fontWeight: 600,
              lineHeight: 1.3,
              wordBreak: 'break-word',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              maxWidth: 400,
            }}
          >
            {task.text}
          </div>
          <div style={{ display: 'flex', gap: 8, fontSize: 10, color: 'rgba(250,246,241,0.6)', marginTop: 3 }}>
            <span>{day}</span>
            {time ? <span>·</span> : null}
            {time ? <span>{time}</span> : null}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
        <IconButton color="#22C55E" onClick={onSave} title="Approve">
          <CheckIcon />
        </IconButton>
        <IconButton color="#EF4444" onClick={onDecline} title="Decline">
          <XIcon />
        </IconButton>
        <IconButton color="#3B82F6" onClick={() => onEdit(task)} title="Edit">
          <PencilIcon />
        </IconButton>
      </div>
    </div>
  );
}

function IconButton({
  color,
  onClick,
  title,
  children,
}: {
  color: string;
  onClick: () => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        flex: 1,
        border: 'none',
        background: color,
        color: '#FFFFFF',
        borderRadius: 8,
        padding: '6px 0',
        fontSize: 11,
        fontWeight: 700,
        cursor: 'pointer',
        letterSpacing: 0.2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
      }}
    >
      {children}
    </button>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path
        d="M3 8.5l3.5 3.5L13 4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path
        d="M4 4l8 8M12 4l-8 8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path
        d="M2 14l3-1 8-8-2-2-8 8-1 3z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
