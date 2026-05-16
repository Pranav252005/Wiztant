import { useState, useEffect, useCallback, useRef } from 'react';
import { approveProjectAction, getProjectStatus, startProject } from '../shared/ipc';

export type LogLevel = 'info' | 'success' | 'warning' | 'error' | 'staging';

export interface ExecutionLog {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  detail?: string;
  subphaseId?: string;
  layerId?: string;
}

export interface ProjectStatus {
  project_id: string;
  state: string;
  current_layer?: string;
  current_phase?: string;
  current_subphase?: string;
  plan?: any;
  ui_score?: number;
  needs_approval?: boolean;
  approval_reason?: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

let _logId = 0;
function nextLogId(): string {
  return `log-${++_logId}`;
}

export function useProjectBuilder() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = useCallback((level: LogLevel, message: string, detail?: string, meta?: { subphaseId?: string; layerId?: string }) => {
    setLogs((prev) => [
      ...prev,
      {
        id: nextLogId(),
        timestamp: nowIso(),
        level,
        message,
        detail,
        subphaseId: meta?.subphaseId,
        layerId: meta?.layerId,
      },
    ]);
  }, []);

  const createProject = useCallback(async (projectPath: string, description: string) => {
    setLoading(true);
    addLog('info', 'Starting project build...', `Path: ${projectPath}`);
    try {
      const res = await startProject(projectPath, description);
      if (res.project_id) {
        setProjectId(res.project_id);
        setStatus(res);
        addLog('success', 'Project plan created', `ID: ${res.project_id}`);
      } else {
        addLog('error', 'Failed to create project', res.error || 'Unknown error');
      }
    } catch (e: any) {
      addLog('error', 'Failed to create project', e.message);
    } finally {
      setLoading(false);
    }
  }, [addLog]);

  const refreshStatus = useCallback(async () => {
    if (!projectId) return;
    try {
      const s = await getProjectStatus(projectId);
      setStatus(s);
    } catch (e: any) {
      addLog('warning', 'Status refresh failed', e.message);
    }
  }, [projectId, addLog]);

  const approve = useCallback(async () => {
    if (!projectId) return;
    addLog('info', 'User approved — resuming execution');
    try {
      await approveProjectAction(projectId, 'approve');
      await refreshStatus();
    } catch (e: any) {
      addLog('error', 'Approval failed', e.message);
    }
  }, [projectId, refreshStatus, addLog]);

  const pause = useCallback(async () => {
    if (!projectId) return;
    addLog('info', 'User paused execution');
    try {
      await approveProjectAction(projectId, 'pause');
      await refreshStatus();
    } catch (e: any) {
      addLog('error', 'Pause failed', e.message);
    }
  }, [projectId, refreshStatus, addLog]);

  const resume = useCallback(async () => {
    if (!projectId) return;
    addLog('info', 'User resumed execution');
    try {
      await approveProjectAction(projectId, 'resume');
      await refreshStatus();
    } catch (e: any) {
      addLog('error', 'Resume failed', e.message);
    }
  }, [projectId, refreshStatus, addLog]);

  // WebSocket for real-time agent events
  useEffect(() => {
    if (!projectId) return;

    const ws = new WebSocket('ws://localhost:9120');
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      addLog('info', 'WebSocket connected');
      // Subscribe to project events
      ws.send(JSON.stringify({ type: 'subscribe', project_id: projectId }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case 'agent.phase_start': {
            addLog('info', `Layer started: ${msg.layerName || msg.layerId}`, undefined, { layerId: msg.layerId });
            break;
          }
          case 'agent.subphase_staged': {
            addLog('staging', `Staged in ${msg.tool}: ${msg.subphaseId}`, msg.prompt?.slice(0, 200), { subphaseId: msg.subphaseId });
            break;
          }
          case 'agent.subphase_done': {
            addLog('success', `Completed: ${msg.subphaseId}`, `Verification: ${msg.verification}`, { subphaseId: msg.subphaseId });
            break;
          }
          case 'agent.subphase_failed': {
            addLog('error', `Failed: ${msg.subphaseId}`, msg.error, { subphaseId: msg.subphaseId });
            break;
          }
          case 'agent.verification_pass': {
            addLog('success', `Verification passed: ${msg.subphaseId}`, msg.output?.slice(0, 200), { subphaseId: msg.subphaseId });
            break;
          }
          case 'agent.verification_fail': {
            addLog('warning', `Verification failed: ${msg.subphaseId}`, msg.output?.slice(0, 300), { subphaseId: msg.subphaseId });
            break;
          }
          case 'agent.needs_approval': {
            addLog('info', 'Needs approval', msg.reason, { layerId: msg.layerId });
            setStatus((prev) => prev ? { ...prev, needs_approval: true, approval_reason: msg.reason } : prev);
            break;
          }
          case 'agent.ui_analysis': {
            addLog('info', `UI analysis complete — Score: ${msg.score}/100`, `${msg.issues?.length || 0} issues found`);
            setStatus((prev) => prev ? { ...prev, ui_score: msg.score } : prev);
            break;
          }
          case 'agent.limit_hit': {
            addLog('warning', 'Limit hit', msg.reason);
            break;
          }
          default:
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      addLog('warning', 'WebSocket disconnected');
    };

    ws.onerror = () => {
      setWsConnected(false);
      addLog('error', 'WebSocket error');
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [projectId, addLog]);

  // Polling fallback
  useEffect(() => {
    if (!projectId) return;
    const interval = setInterval(refreshStatus, 5000);
    return () => clearInterval(interval);
  }, [projectId, refreshStatus]);

  return {
    projectId,
    status,
    loading,
    logs,
    wsConnected,
    createProject,
    approve,
    pause,
    resume,
    refreshStatus,
    addLog,
  };
}
