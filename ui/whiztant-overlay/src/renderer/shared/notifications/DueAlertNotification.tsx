import { useState } from 'react';
import TaskActionBar from './TaskActionBar';

interface DueAlertTask {
  id: string;
  title: string;
}

interface Props {
  tasks: DueAlertTask[];
  onReschedule: (id: string) => void | Promise<void>;
  onDismissAll: () => void | Promise<void>;
  onSnooze: (id: string, minutes: number) => void;
  onToggleDone: (id: string) => void;
  onEdit: (id: string, title: string) => void;
  compact?: boolean;
}

export default function DueAlertNotification({ tasks, onReschedule, onDismissAll, onSnooze, onToggleDone, onEdit, compact }: Props) {
  const [expanded, setExpanded] = useState(false);
  const count = tasks.length;
  const label = `${count} task${count === 1 ? '' : 's'} due — not done`;

  if (!count) return null;

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
        <div style={{ flex: 1, minWidth: 0, color: '#FCA5A5', fontSize: 11, fontWeight: 700 }}>
          {label} {expanded ? '▴' : '▾'}
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            void onDismissAll();
          }}
          style={{
            border: 'none',
            background: 'transparent',
            color: '#FCA5A5',
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
            padding: 0,
            width: 18,
            height: 18,
          }}
          title="Reschedule all for tomorrow"
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
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                borderRadius: 8,
                border: '1px solid rgba(239,68,68,0.25)',
                background: 'rgba(239,68,68,0.08)',
                padding: '8px 8px',
              }}
            >
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  color: '#FCA5A5',
                  fontSize: 11,
                  lineHeight: 1.4,
                  wordBreak: 'break-word',
                }}
              >
                {task.title}
              </div>
              <TaskActionBar
                onApprove={() => onToggleDone(task.id)}
                onDeny={() => void onReschedule(task.id)}
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
