import { useCallback, useEffect, useRef, useState } from 'react';
import { useBridgeMessage } from './useBridge';
import type { Task } from './ipc';

// ── Types ────────────────────────────────────────────────────────
export interface TaskSavedPayload {
  task: Task;
}

export interface DueAlertTask {
  id: string;
  title: string;
}

export interface DueAlertPayload {
  tasks: DueAlertTask[];
  count: number;
}

export interface DueReminderTask {
  id: string;
  title: string;
  scheduled_for: string;
}

export interface DueReminderPayload {
  tasks: DueReminderTask[];
}

export interface OverdueReminderTask {
  id: string;
  title: string;
}

export interface OverdueReminderPayload {
  task: OverdueReminderTask;
  reminder_count: number;
}

export interface DuplicateExistingTask {
  id: string;
  title: string;
  scheduled_for: string;
  hour: number;
  minute: number;
}

export interface DuplicatePayload {
  existingTask: DuplicateExistingTask;
  newTime: string;
}

export interface TaskConfirmPayload {
  id: string;
  parsed_title: string;
  due_datetime?: string;
  has_time: boolean;
  has_date: boolean;
}

export interface PillNotificationPayload {
  task_id: string;
  title: string;
  due_datetime: string;
  notification_type: 'pre_due' | 'due_now' | 'overdue';
  minutes_remaining: number;
}

export type PillNotification =
  | { kind: 'task_confirm'; payload: TaskConfirmPayload }
  | { kind: 'pill_notification'; payload: PillNotificationPayload }
  | { kind: 'task_saved'; payload: TaskSavedPayload }
  | { kind: 'due_alert'; payload: DueAlertPayload }
  | { kind: 'due_reminder'; payload: DueReminderPayload }
  | { kind: 'overdue_reminder'; payload: OverdueReminderPayload }
  | { kind: 'duplicate'; payload: DuplicatePayload };

export type PillNotificationKind = PillNotification['kind'];

// Priority (higher replaces lower; lower is queued):
const PRIORITY: Record<PillNotificationKind, number> = {
  task_confirm: 5,
  due_alert: 4,
  task_saved: 3,
  overdue_reminder: 3,
  duplicate: 2,
  pill_notification: 2,
  due_reminder: 1,
};

interface UsePillNotificationsResult {
  active: PillNotification | null;
  dismiss: () => void;
  replace: (next: PillNotification | null) => void;
  updateActive: (updater: (current: PillNotification) => PillNotification | null) => void;
}

/**
 * Subscribes to the WS bridge and surfaces the current highest-priority
 * pill notification. Lower-priority incoming notifications are queued
 * and surfaced after the active one is dismissed.
 */
export function usePillNotifications(): UsePillNotificationsResult {
  const [active, setActive] = useState<PillNotification | null>(null);
  const queueRef = useRef<PillNotification[]>([]);

  const promoteFromQueue = useCallback(() => {
    setActive((current) => {
      if (current) return current;
      const queue = queueRef.current;
      if (!queue.length) return null;
      // Pick highest priority in queue.
      queue.sort((a, b) => PRIORITY[b.kind] - PRIORITY[a.kind]);
      const [next, ...rest] = queue;
      queueRef.current = rest;
      return next;
    });
  }, []);

  const enqueue = useCallback((incoming: PillNotification) => {
    setActive((current) => {
      if (!current) return incoming;
      if (PRIORITY[incoming.kind] > PRIORITY[current.kind]) {
        // Push the displaced one back into the queue.
        queueRef.current.push(current);
        return incoming;
      }
      queueRef.current.push(incoming);
      return current;
    });
  }, []);

  const dismiss = useCallback(() => {
    setActive(null);
    // Allow state to commit before promoting.
    setTimeout(promoteFromQueue, 0);
  }, [promoteFromQueue]);

  const replace = useCallback(
    (next: PillNotification | null) => {
      if (!next) {
        dismiss();
        return;
      }
      setActive(next);
    },
    [dismiss],
  );

  const updateActive = useCallback(
    (updater: (current: PillNotification) => PillNotification | null) => {
      setActive((current) => {
        if (!current) return current;
        const result = updater(current);
        if (result === null) {
          setTimeout(promoteFromQueue, 0);
          return null;
        }
        return result;
      });
    },
    [promoteFromQueue],
  );

  const handleMessage = useCallback(
    (msg: Record<string, unknown>) => {
      const type = String(msg?.type ?? '');
      if (type === 'task_saved' && msg.task) {
        enqueue({ kind: 'task_saved', payload: { task: msg.task as Task } });
      } else if (type === 'due_alert') {
        const tasks = Array.isArray(msg.tasks) ? (msg.tasks as DueAlertTask[]) : [];
        const count = typeof msg.count === 'number' ? msg.count : tasks.length;
        if (tasks.length) enqueue({ kind: 'due_alert', payload: { tasks, count } });
      } else if (type === 'due_reminder') {
        const tasks = Array.isArray(msg.tasks) ? (msg.tasks as DueReminderTask[]) : [];
        if (tasks.length) enqueue({ kind: 'due_reminder', payload: { tasks } });
      } else if (type === 'task_duplicate' && msg.existing_task) {
        const existing = msg.existing_task as DuplicateExistingTask;
        const newTime = typeof msg.new_time === 'string' ? msg.new_time : '';
        enqueue({ kind: 'duplicate', payload: { existingTask: existing, newTime } });
      } else if (type === 'task_confirm_request' && msg.payload) {
        enqueue({ kind: 'task_confirm', payload: msg.payload as TaskConfirmPayload });
      } else if (type === 'overdue_reminder' && msg.task) {
        const task = msg.task as OverdueReminderTask;
        const count = typeof msg.reminder_count === 'number' ? msg.reminder_count : 1;
        enqueue({ kind: 'overdue_reminder', payload: { task, reminder_count: count } });
      } else if (type === 'pill_notification' && msg.payload) {
        enqueue({ kind: 'pill_notification', payload: msg.payload as PillNotificationPayload });
      }
    },
    [enqueue],
  );

  useBridgeMessage(handleMessage);

  useEffect(() => {
    // Whenever active goes to null while queue has items, promote.
    if (!active && queueRef.current.length) promoteFromQueue();
  }, [active, promoteFromQueue]);

  return { active, dismiss, replace, updateActive };
}
