import type { PillNotification, TaskConfirmPayload, PillNotificationPayload } from '../usePillNotifications';
import type { Task } from '../ipc';
import TaskSavedNotification from './TaskSavedNotification';
import DueAlertNotification from './DueAlertNotification';
import DueReminderNotification from './DueReminderNotification';
import DuplicateTaskNotification from './DuplicateTaskNotification';
import OverdueReminderNotification from './OverdueReminderNotification';
import TaskConfirmBar from './TaskConfirmBar';
import NotificationBar from './NotificationBar';

export interface NotificationHandlers {
  saveTask: () => void;
  declineTask: (task: Task) => void;
  editTask: (task: Task) => void;
  rescheduleTask: (id: string) => void | Promise<void>;
  dismissDueAlertAll: () => void | Promise<void>;
  dismissReminder: () => void;
  dismissOverdueReminder: () => void;
  dismissDuplicate: () => void;
  approveTaskConfirm: (payload: TaskConfirmPayload) => void;
  rejectTaskConfirm: () => void;
  editTaskConfirm: (payload: TaskConfirmPayload) => void;
  openTaskNotification: (payload: PillNotificationPayload) => void;
  snoozeTask: (id: string, minutes: number) => void;
  toggleTaskDone: (id: string) => void;
  openTaskById: (id: string, title: string) => void;
}

interface Props {
  notification: PillNotification;
  compact?: boolean;
  handlers: NotificationHandlers;
  onNotificationBodyClick?: () => void;
}

export default function NotificationRenderer({ notification, compact, handlers, onNotificationBodyClick }: Props) {
  if (notification.kind === 'task_confirm') {
    return (
      <TaskConfirmBar
        payload={notification.payload}
        onApprove={() => handlers.approveTaskConfirm(notification.payload)}
        onDisapprove={handlers.rejectTaskConfirm}
        onEdit={() => handlers.editTaskConfirm(notification.payload)}
        compact={compact}
      />
    );
  }
  if (notification.kind === 'pill_notification') {
    return (
      <NotificationBar
        payload={notification.payload}
        onToggleDone={() => handlers.toggleTaskDone(notification.payload.task_id)}
        onDismiss={() => handlers.openTaskNotification(notification.payload)}
        onSnooze={(minutes) => handlers.snoozeTask(notification.payload.task_id, minutes)}
        onEdit={() => handlers.openTaskNotification(notification.payload)}
        onBodyClick={onNotificationBodyClick ?? (() => {})}
      />
    );
  }
  if (notification.kind === 'task_saved') {
    return (
      <TaskSavedNotification
        task={notification.payload.task}
        compact={compact}
        onSave={handlers.saveTask}
        onDecline={() => handlers.declineTask(notification.payload.task)}
        onEdit={(t) => handlers.editTask(t)}
      />
    );
  }
  if (notification.kind === 'due_alert') {
    return (
      <DueAlertNotification
        tasks={notification.payload.tasks}
        compact={compact}
        onReschedule={handlers.rescheduleTask}
        onDismissAll={handlers.dismissDueAlertAll}
        onSnooze={handlers.snoozeTask}
        onToggleDone={handlers.toggleTaskDone}
        onEdit={handlers.openTaskById}
      />
    );
  }
  if (notification.kind === 'due_reminder') {
    return (
      <DueReminderNotification
        tasks={notification.payload.tasks}
        compact={compact}
        onDismiss={handlers.dismissReminder}
        onSnooze={handlers.snoozeTask}
        onToggleDone={handlers.toggleTaskDone}
        onEdit={handlers.openTaskById}
      />
    );
  }
  if (notification.kind === 'overdue_reminder') {
    return (
      <OverdueReminderNotification
        task={notification.payload.task}
        reminderCount={notification.payload.reminder_count}
        compact={compact}
        onDismiss={handlers.dismissOverdueReminder}
        onSnooze={handlers.snoozeTask}
        onToggleDone={handlers.toggleTaskDone}
        onEdit={handlers.openTaskById}
      />
    );
  }
  if (notification.kind === 'duplicate') {
    return (
      <DuplicateTaskNotification
        existingTask={notification.payload.existingTask}
        newTime={notification.payload.newTime}
        compact={compact}
        onDismiss={handlers.dismissDuplicate}
      />
    );
  }
  return null;
}

// Suggested pill window sizes per notification kind.
export function pillSizeFor(notification: PillNotification): { width: number; height: number } {
  switch (notification.kind) {
    case 'task_confirm':
      return { width: 560, height: 80 };
    case 'pill_notification':
      return { width: 400, height: 64 };
    case 'task_saved':
      return { width: 460, height: 120 };
    case 'due_alert':
      return { width: 360, height: 200 };
    case 'due_reminder':
      return { width: 340, height: 180 };
    case 'overdue_reminder':
      return { width: 340, height: 90 };
    case 'duplicate':
      return { width: 360, height: 110 };
    default:
      return { width: 360, height: 60 };
  }
}
