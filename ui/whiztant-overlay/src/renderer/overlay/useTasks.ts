import { useCallback, useEffect, useState } from 'react';
import type { Task, TaskSnapshot } from '../shared/ipc';
import { sendBridgeMessage } from '../shared/useBridge';

export type TaskHistoryItem = TaskSnapshot['history'][number];

export function useTasks(sourceTasks: Task[], sourceHistory: TaskHistoryItem[]) {
  const [tasks, setTasks] = useState<Task[]>(sourceTasks);
  const [history, setHistory] = useState<TaskHistoryItem[]>(sourceHistory);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTasks(sourceTasks);
  }, [sourceTasks]);

  useEffect(() => {
    setHistory(sourceHistory);
  }, [sourceHistory]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // Prefer WS bridge refresh; fall back to direct IPC if bridge is down.
      sendBridgeMessage({ type: 'tasks/refresh' });
      const snapshot = await window.api.getTasks();
      setTasks(Array.isArray(snapshot.tasks) ? snapshot.tasks : []);
      setHistory(Array.isArray(snapshot.history) ? snapshot.history : []);
      return snapshot;
    } finally {
      setLoading(false);
    }
  }, []);

  const openPanel = useCallback(async (task: Task) => {
    await window.api.openTaskPanel(task);
  }, []);

  const rescheduleTask = useCallback(async (id: string) => {
    sendBridgeMessage({ type: 'tasks/reschedule', task_id: id });
    return true;
  }, []);

  const markDone = useCallback(async (id: string) => {
    sendBridgeMessage({ type: 'tasks/toggle_status', task_id: id });
    return undefined;
  }, []);

  const updateTask = useCallback(async (id: string, fields: Partial<Task>) => {
    sendBridgeMessage({ type: 'tasks/edit', task_id: id, fields });
    return undefined;
  }, []);

  const deleteTask = useCallback(async (id: string) => {
    sendBridgeMessage({ type: 'tasks/delete', task_id: id });
    return undefined;
  }, []);

  return {
    tasks,
    history,
    loading,
    refresh,
    openPanel,
    rescheduleTask,
    markDone,
    updateTask,
    deleteTask,
  };
}
