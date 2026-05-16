import TaskActionBar from './TaskActionBar';

interface OverdueReminderTask {
  id: string;
  title: string;
}

interface Props {
  task: OverdueReminderTask;
  reminderCount: number;
  onDismiss: () => void;
  onSnooze: (id: string, minutes: number) => void;
  onToggleDone: (id: string) => void;
  onEdit: (id: string, title: string) => void;
  compact?: boolean;
}

export default function OverdueReminderNotification({ task, reminderCount, onDismiss, onSnooze, onToggleDone, onEdit, compact }: Props) {
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
        <TaskActionBar
          onApprove={() => onToggleDone(task.id)}
          onDeny={onDismiss}
          onSnooze={(minutes) => onSnooze(task.id, minutes)}
          onEdit={() => onEdit(task.id, task.title)}
          compact={compact}
        />
      </div>
    </div>
  );
}
