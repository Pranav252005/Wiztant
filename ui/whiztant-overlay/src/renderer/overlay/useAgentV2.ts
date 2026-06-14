import { useState, useEffect, useCallback, useRef } from 'react';
import { useBridgeMessage, sendBridgeMessage } from '../shared/useBridge';

export type WorkflowStatus = 'idle' | 'planning' | 'running' | 'paused' | 'completed' | 'failed';

export interface V2Step {
  id: number;
  action: string;
  app: string;
  description?: string;
  success?: boolean;
  output?: string;
}

export interface V2Status {
  workflow_name: string;
  current_step: number;
  total_steps: number;
  current_app: string;
  current_action: string;
  steps_used: number;
  steps_budget: number;
  apps_chain: string[];
}

export interface V2Template {
  id: string;
  name: string;
  description: string;
  apps_required: string[];
  estimated_steps: number;
  estimated_budget: number;
}

export interface V2DecisionGate {
  step_id: number;
  gate_id?: string;
  description: string;
  app: string;
}

export interface LearningState {
  active: boolean;
  workflow_name: string;
  query: string;
  percent: number;
  current_source: string;
  steps_found: number;
  estimated_time: number;
  result: Record<string, unknown> | null;
  failed_reason: string | null;
}

export function useAgentV2() {
  const [status, setStatus] = useState<V2Status | null>(null);
  const [workflowState, setWorkflowState] = useState<WorkflowStatus>('idle');
  const [steps, setSteps] = useState<V2Step[]>([]);
  const [templates, setTemplates] = useState<V2Template[]>([]);
  const [decisionGate, setDecisionGate] = useState<V2DecisionGate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [learning, setLearning] = useState<LearningState>({
    active: false,
    workflow_name: '',
    query: '',
    percent: 0,
    current_source: '',
    steps_found: 0,
    estimated_time: 45,
    result: null,
    failed_reason: null,
  });
  const [workflowResult, setWorkflowResult] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const handleMessage = useCallback((msg: Record<string, unknown>) => {
    const type = msg.type as string;
    if (!type) return;

    // Workflow events (new orchestrator)
    if (type.startsWith('workflow/')) {
      switch (type) {
        case 'workflow/started': {
          setWorkflowState('running');
          setSteps([]);
          setWorkflowResult(null);
          break;
        }
        case 'workflow/step': {
          const step: V2Step = {
            id: (msg.step_index as number) ?? 0,
            action: (msg.action as string) ?? '',
            app: (msg.app as string) ?? '',
            description: (msg.description as string) ?? '',
          };
          setSteps((prev) => [...prev, step]);
          break;
        }
        case 'workflow/gate': {
          const gate = {
            step_id: 0,
            gate_id: (msg.gate_id as string) ?? '',
            description: (msg.question as string) ?? 'Decision needed',
            app: 'system',
          };
          setDecisionGate(gate);
          setWorkflowState('paused');
          break;
        }
        case 'workflow/paused': {
          setWorkflowState('paused');
          break;
        }
        case 'workflow/resumed': {
          setWorkflowState('running');
          setDecisionGate(null);
          break;
        }
        case 'workflow/completed': {
          setWorkflowState('completed');
          setDecisionGate(null);
          break;
        }
        case 'workflow/result': {
          setWorkflowResult((msg.summary as string) ?? '');
          break;
        }
        case 'workflow/error': {
          setError((msg.error as string) ?? 'Unknown error');
          setWorkflowState('failed');
          break;
        }
      }
      return;
    }

    // Agent V2 events (legacy bridge)
    if (type.startsWith('agent_v2/')) {
      switch (type) {
        case 'agent_v2/template_list': {
          const tpls = msg.templates as V2Template[] | undefined;
          if (tpls) setTemplates(tpls);
          break;
        }
        case 'agent_v2/plan_ready': {
          setWorkflowState('planning');
          break;
        }
        case 'agent_v2/status_update': {
          const s = msg as unknown as V2Status;
          setStatus(s);
          setWorkflowState('running');
          break;
        }
        case 'agent_v2/step_complete': {
          const step = msg.step as V2Step | undefined;
          const requiresDecision = msg.requires_decision as boolean;
          if (step) {
            setSteps((prev) => {
              const existing = prev.findIndex((p) => p.id === step.id);
              if (existing >= 0) {
                const next = [...prev];
                next[existing] = { ...next[existing], ...step };
                return next;
              }
              return [...prev, step];
            });
          }
          if (!requiresDecision) {
            setDecisionGate(null);
          }
          break;
        }
        case 'agent_v2/paused': {
          setWorkflowState('paused');
          break;
        }
        case 'agent_v2/completed': {
          setWorkflowState('completed');
          setSummary(msg.summary as Record<string, unknown>);
          setDecisionGate(null);
          break;
        }
        case 'agent_v2/error': {
          const msgText = msg.message as string;
          const recoverable = msg.recoverable as boolean;
          setError(msgText);
          if (!recoverable) {
            setWorkflowState('failed');
          }
          break;
        }
        case 'agent_v2/decision_gate': {
          const gate = {
            step_id: msg.step_id as number,
            description: msg.description as string,
            app: msg.app as string,
          };
          setDecisionGate(gate);
          setWorkflowState('paused');
          break;
        }
      }
      return;
    }

    // TuneHub learning events
    if (type.startsWith('tunehub:')) {
      switch (type) {
        case 'tunehub:learning_started': {
          setLearning({
            active: true,
            workflow_name: (msg.workflow_name as string) || '',
            query: (msg.query as string) || '',
            percent: 0,
            current_source: 'Searching...',
            steps_found: 0,
            estimated_time: (msg.estimated_time as number) || 45,
            result: null,
            failed_reason: null,
          });
          break;
        }
        case 'tunehub:learning_progress': {
          setLearning((prev) => ({
            ...prev,
            percent: msg.percent as number,
            current_source: (msg.current_source as string) || prev.current_source,
            steps_found: msg.steps_found as number,
          }));
          break;
        }
        case 'tunehub:learning_complete': {
          setLearning((prev) => ({
            ...prev,
            active: false,
            percent: 100,
            result: {
              template: msg.template,
              confidence: msg.confidence,
              sources: msg.sources,
              requires_review: msg.requires_review,
            } as Record<string, unknown>,
          }));
          break;
        }
        case 'tunehub:learning_failed': {
          setLearning((prev) => ({
            ...prev,
            active: false,
            failed_reason: (msg.reason as string) || 'Unknown error',
          }));
          break;
        }
      }
      return;
    }
  }, []);

  useBridgeMessage(handleMessage);

  const initiate = useCallback((templateId: string, params: Record<string, unknown>) => {
    setSteps([]);
    setError(null);
    setSummary(null);
    setDecisionGate(null);
    setLearning((prev) => ({ ...prev, active: false, result: null, failed_reason: null }));
    setWorkflowState('planning');
    sendBridgeMessage({
      type: 'agent_v2:select_template',
      template_id: templateId,
      params,
    });
  }, []);

  const initiateFreeform = useCallback((intent: string) => {
    setSteps([]);
    setError(null);
    setSummary(null);
    setDecisionGate(null);
    setLearning((prev) => ({ ...prev, active: false, result: null, failed_reason: null }));
    setWorkflowState('planning');
    sendBridgeMessage({
      type: 'tunehub:trigger_learning',
      intent,
      params: {},
    });
  }, []);

  const initiatePreset = useCallback((presetId: string, intent: string, params: Record<string, unknown>) => {
    setSteps([]);
    setError(null);
    setSummary(null);
    setDecisionGate(null);
    setLearning((prev) => ({ ...prev, active: false, result: null, failed_reason: null }));
    setWorkflowState('planning');
    sendBridgeMessage({
      type: 'agent_v2:run_preset',
      preset_id: presetId,
      intent,
      params,
    });
  }, []);

  const pause = useCallback(() => {
    sendBridgeMessage({ type: 'agent_v2:pause', reason: 'user_request' });
  }, []);

  const resume = useCallback(() => {
    sendBridgeMessage({ type: 'agent_v2:resume' });
  }, []);

  const abort = useCallback(() => {
    sendBridgeMessage({ type: 'agent_v2:abort' });
    setWorkflowState('idle');
    setStatus(null);
    setSteps([]);
    setDecisionGate(null);
  }, []);

  const submitDecision = useCallback((decision: 'accept' | 'deny' | 'retry') => {
    sendBridgeMessage({ type: 'agent_v2:decision', decision });
    setDecisionGate(null);
    if (decision !== 'deny') {
      setWorkflowState('running');
    }
  }, []);

  const submitWorkflowDecision = useCallback((gateId: string, choice: string) => {
    sendBridgeMessage({ type: 'workflow:decision', gate_id: gateId, choice });
    setDecisionGate(null);
    setWorkflowState('running');
  }, []);

  const approveLearned = useCallback((templateId: string) => {
    sendBridgeMessage({ type: 'tunehub:approve_learned', template_id: templateId });
    setLearning((prev) => ({ ...prev, active: false, result: null }));
  }, []);

  const rejectLearned = useCallback((templateId: string, reason: string) => {
    sendBridgeMessage({ type: 'tunehub:reject_learned', template_id: templateId, reason });
    setLearning((prev) => ({ ...prev, active: false, result: null }));
  }, []);

  return {
    status,
    workflowState,
    steps,
    templates,
    decisionGate,
    error,
    summary,
    workflowResult,
    learning,
    logsEndRef,
    initiate,
    initiateFreeform,
    initiatePreset,
    pause,
    resume,
    abort,
    submitDecision,
    submitWorkflowDecision,
    approveLearned,
    rejectLearned,
  };
}
