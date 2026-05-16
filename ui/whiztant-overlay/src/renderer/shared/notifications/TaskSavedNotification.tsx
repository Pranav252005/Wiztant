import type { Task } from '../ipc';
import TaskActionBar from './TaskActionBar';

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

      <TaskActionBar
        onApprove={onSave}
        onDeny={onDecline}
        onEdit={() => onEdit(task)}
        compact={compact}
      />
    </div>
  );
}
