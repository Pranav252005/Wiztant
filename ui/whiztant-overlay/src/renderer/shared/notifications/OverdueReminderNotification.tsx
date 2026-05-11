interface OverdueReminderTask {
  id: string;
  title: string;
}

interface Props {
  task: OverdueReminderTask;
  reminderCount: number;
  onDismiss: () => void;
  compact?: boolean;
}

export default function OverdueReminderNotification({ task, reminderCount, onDismiss, compact }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: compact ? '6px 10px' : '10px 12px',
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ color: '#F87171', fontSize: 11, fontWeight: 700 }}>
            Overdue #{reminderCount}
          </div>
          <div
            style={{
              color: '#FAF6F1',
              fontSize: 11,
              lineHeight: 1.4,
              wordBreak: 'break-word',
              marginTop: 2,
            }}
          >
            {task.title}
          </div>
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
            color: '#F87171',
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
            padding: 0,
            width: 18,
            height: 18,
            flexShrink: 0,
          }}
          title="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
}
