import { useState, useEffect, useCallback } from 'react';
import { approveProjectAction, getProjectStatus, startProject } from '../shared/ipc';
import type { AgentV2Event } from '../shared/types';

export interface ProjectStatus {
  project_id: string;
  state: string;
  current_layer?: string;
  current_phase?: string;
  current_subphase?: string;
  plan?: any;
}

export function useProjectBuilder() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const createProject = useCallback(async (projectPath: string, description: string) => {
    setLoading(true);
    try {
      const res = await startProject(projectPath, description);
      if (res.project_id) {
        setProjectId(res.project_id);
        setStatus(res);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    if (!projectId) return;
    const s = await getProjectStatus(projectId);
    setStatus(s);
  }, [projectId]);

  const approve = useCallback(async () => {
    if (!projectId) return;
    await approveProjectAction(projectId, 'approve');
    await refreshStatus();
  }, [projectId, refreshStatus]);

  const pause = useCallback(async () => {
    if (!projectId) return;
    await approveProjectAction(projectId, 'pause');
    await refreshStatus();
  }, [projectId, refreshStatus]);

  const resume = useCallback(async () => {
    if (!projectId) return;
    await approveProjectAction(projectId, 'resume');
    await refreshStatus();
  }, [projectId, refreshStatus]);

  useEffect(() => {
    if (!projectId) return;
    const interval = setInterval(refreshStatus, 3000);
    return () => clearInterval(interval);
  }, [projectId, refreshStatus]);

  return { projectId, status, loading, createProject, approve, pause, resume, refreshStatus };
}
