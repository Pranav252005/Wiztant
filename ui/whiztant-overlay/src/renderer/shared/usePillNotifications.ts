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

export type PillNotification =
  | { kind: 'task_saved'; payload: TaskSavedPayload }
  | { kind: 'due_alert'; payload: DueAlertPayload }
  | { kind: 'due_reminder'; payload: DueReminderPayload }
  | { kind: 'duplicate'; payload: DuplicatePayload };

export type PillNotificationKind = PillNotification['kind'];

// Priority (higher replaces lower; lower is queued):
const PRIORITY: Record<PillNotificationKind, number> = {
  due_alert: 4,
  task_saved: 3,
  duplicate: 2,
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
