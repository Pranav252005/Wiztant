import { useState } from 'react';
import TaskActionBar from './TaskActionBar';

interface DueReminderTask {
  id: string;
  title: string;
  scheduled_for: string;
}

interface Props {
  tasks: DueReminderTask[];
  onDismiss: () => void;
  onSnooze: (id: string, minutes: number) => void;
  onToggleDone: (id: string) => void;
  onEdit: (id: string, title: string) => void;
  compact?: boolean;
}

export default function DueReminderNotification({ tasks, onDismiss, onSnooze, onToggleDone, onEdit, compact }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (!tasks.length) return null;

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
        <div style={{ flex: 1, minWidth: 0, color: '#C4956A', fontSize: 11, fontWeight: 700 }}>
          {tasks.length} carried-over task{tasks.length === 1 ? '' : 's'} from yesterday {expanded ? '▴' : '▾'}
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
          title="Dismiss reminder"
        >
          ×
        </button>
      </div>
      {expanded ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            padding: '0 10px 10px',
            maxHeight: 160,
            overflowY: 'auto',
          }}
        >
          {tasks.map((task) => (
            <div
              key={task.id}
              style={{
                borderRadius: 8,
                border: '1px solid rgba(196,149,106,0.4)',
                background: 'rgba(196,149,106,0.08)',
                padding: '8px 8px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  color: '#FAF6F1',
                  fontSize: 11,
                  lineHeight: 1.4,
                  wordBreak: 'break-word',
                }}
              >
                {task.title}
              </div>
              <TaskActionBar
                onApprove={() => onToggleDone(task.id)}
                onDeny={onDismiss}
                onSnooze={(minutes) => onSnooze(task.id, minutes)}
                onEdit={() => onEdit(task.id, task.title)}
                compact
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
