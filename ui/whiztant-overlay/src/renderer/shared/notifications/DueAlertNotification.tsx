import { useMemo, useState } from 'react';

interface DueAlertTask {
  id: string;
  title: string;
}

interface Props {
  tasks: DueAlertTask[];
  onReschedule: (id: string) => void | Promise<void>;
  onDismissAll: () => void | Promise<void>;
  compact?: boolean;
}

export default function DueAlertNotification({ tasks, onReschedule, onDismissAll, compact }: Props) {
  const [expanded, setExpanded] = useState(false);
  const count = tasks.length;
  const label = useMemo(() => `${count} task${count === 1 ? '' : 's'} due — not done`, [count]);

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
            gap: 6,
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
              <button
                type="button"
                onClick={() => void onReschedule(task.id)}
                style={{
                  border: 'none',
                  background: '#EF4444',
                  color: '#FAF6F1',
                  borderRadius: 999,
                  padding: '5px 10px',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                Reschedule
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
