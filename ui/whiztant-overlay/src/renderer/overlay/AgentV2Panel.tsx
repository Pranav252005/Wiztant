import React, { useState, useEffect, useMemo } from 'react';
import { useAgentV2 } from './useAgentV2';
import CustomDropdown from '../shared/CustomDropdown';
import type { Theme } from '../shared/themes';
import { inkFor } from '../shared/themes';

type AgentPreset = {
  id: string;
  name: string;
  display_name: string;
  category: string;
  description: string;
  what_it_does: string;
  usage: string;
  limitations: string;
  template_id: string;
  params_schema: Array<{
    name: string;
    label: string;
    type: string;
    placeholder?: string;
  }>;
  examples: string[];
};

const PRESET_CATEGORIES: Record<string, string> = {
  Productivity: 'Productivity',
  Communication: 'Communication',
  Research: 'Research',
  General: 'General',
};

const statusColor = (state: string, accent: string): string => {
  switch (state) {
    case 'running': return '#22c55e';
    case 'paused': return '#f59e0b';
    case 'completed': return '#3b82f6';
    case 'failed': return '#ef4444';
    case 'planning': return '#a855f7';
    default: return accent;
  }
};

const stepIcon = (action: string): string => {
  switch (action) {
    case 'open_app': return '▶';
    case 'navigate_to': return '🔗';
    case 'click': return '🖱';
    case 'type': return '⌨';
    case 'scroll': return '⇅';
    case 'hotkey': return '⌨';
    case 'copy': return '📋';
    case 'paste': return '📋';
    case 'screenshot': return '📷';
    case 'read_screen': return '👁';
    case 'wait': return '⏱';
    case 'ask_human': return '❓';
    case 'return_result': return '✓';
    default: return '•';
  }
};

export const AgentV2Panel: React.FC<{ theme?: Theme['panel'] }> = ({ theme }) => {
  const {
    status,
    workflowState,
    steps,
    decisionGate,
    error,
    summary,
    workflowResult,
    learning,
    initiate,
    initiatePreset,
    pause,
    resume,
    abort,
    submitDecision,
    submitWorkflowDecision,
    approveLearned,
    rejectLearned,
  } = useAgentV2();

  const [presets, setPresets] = useState<AgentPreset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>(() => {
    try {
      const saved = window.localStorage.getItem('whiztant.agent.preset');
      if (saved) return saved;
    } catch { /* noop */ }
    return 'morning_standup';
  });
  const [params, setParams] = useState<Record<string, string>>({});
  const [freeformText, setFreeformText] = useState('');
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [gateEditValue, setGateEditValue] = useState('');
  const [showGateEdit, setShowGateEdit] = useState(false);

  const t = theme;
  const accent = t?.aiAccent ?? '#c0c1ff';

  const isIdle = workflowState === 'idle';
  const isRunning = workflowState === 'running';
  const isPaused = workflowState === 'paused';
  const isCompleted = workflowState === 'completed';
  const isFailed = workflowState === 'failed';

  // Fetch presets on mount
  useEffect(() => {
    fetch('http://localhost:8765/agent_presets')
      .then((res) => res.json())
      .then((data) => {
        if (data.presets && Array.isArray(data.presets)) {
          setPresets(data.presets);
        }
      })
      .catch(() => {
        setPresets([
          {
            id: 'info_gather',
            name: 'Info Gather',
            display_name: 'Info Gather',
            category: 'General',
            description: 'Describe what information you need and the agent searches across apps to find it.',
            what_it_does: 'This is the freeform mode. You describe what information you need in plain English, and the agent dynamically plans a workflow to find it.',
            usage: 'Use this for ad-hoc questions that do not fit a specific preset.',
            limitations: 'Because the agent plans dynamically, complex multi-app searches may take longer.',
            template_id: 'freeform',
            params_schema: [{ name: 'query', label: 'What do you need to know?', type: 'text', placeholder: 'e.g. What is the deadline for the Q3 roadmap?' }],
            examples: ['Find the Q3 roadmap deadline', 'What did Sarah say about the API changes in Slack?'],
          },
        ]);
      });
  }, []);

  useEffect(() => {
    try { window.localStorage.setItem('whiztant.agent.preset', selectedPreset); } catch { /* noop */ }
  }, [selectedPreset]);

  const selectedPresetData = useMemo(
    () => presets.find((p) => p.id === selectedPreset),
    [presets, selectedPreset]
  );

  // Rotating placeholder
  useEffect(() => {
    if (!selectedPresetData || isTyping || freeformText.trim()) return;
    const examples = selectedPresetData.examples;
    if (!examples || examples.length === 0) return;

    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % examples.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [selectedPresetData, isTyping, freeformText]);

  useEffect(() => {
    setPlaceholderIndex(0);
  }, [selectedPreset]);

  // Reset gate edit when gate appears/disappears
  useEffect(() => {
    if (!decisionGate) {
      setShowGateEdit(false);
      setGateEditValue('');
    }
  }, [decisionGate]);

  const currentPlaceholder = selectedPresetData?.examples?.[placeholderIndex] ?? 'Describe what you want the agent to do...';

  const progressPct = status && status.total_steps > 0
    ? Math.round((status.current_step / status.total_steps) * 100)
    : 0;

  const renderProgressBar = (pct: number, color: string) => (
    <div style={{
      width: '100%',
      height: 6,
      borderRadius: 3,
      background: `${accent}15`,
      overflow: 'hidden',
    }}>
      <div style={{
        width: `${Math.min(pct, 100)}%`,
        height: '100%',
        borderRadius: 3,
        background: color,
        transition: 'width 0.3s ease',
      }} />
    </div>
  );

  const handleRun = () => {
    if (!selectedPresetData) return;
    const intent = freeformText.trim();
    if (selectedPresetData.template_id === 'freeform' && !intent) return;
    initiatePreset(selectedPresetData.id, intent, params);
  };

  const handleRunAnother = () => {
    abort();
    setFreeformText('');
    setParams({});
  };

  const handleCopyResult = () => {
    if (workflowResult) {
      navigator.clipboard.writeText(workflowResult).catch(() => {});
    }
  };

  const renderParamInput = (schema: AgentPreset['params_schema'][number]) => {
    const commonStyle: React.CSSProperties = {
      width: '100%',
      borderRadius: 8,
      background: t?.inputBg ?? '#0f0f1a',
      border: `1px solid ${t?.border ?? '#27273a'}`,
      padding: '8px 12px',
      fontSize: 13,
      color: t?.text ?? '#e2e2e2',
      fontFamily: 'inherit',
      outline: 'none',
    };

    if (schema.type === 'textarea') {
      return (
        <textarea
          key={schema.name}
          style={{ ...commonStyle, resize: 'vertical' }}
          placeholder={schema.placeholder}
          rows={3}
          value={params[schema.name] || ''}
          onChange={(e) => setParams((p) => ({ ...p, [schema.name]: e.target.value }))}
        />
      );
    }

    return (
      <input
        key={schema.name}
        style={commonStyle}
        placeholder={schema.placeholder}
        value={params[schema.name] || ''}
        onChange={(e) => setParams((p) => ({ ...p, [schema.name]: e.target.value }))}
      />
    );
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      padding: 16,
      color: t?.text ?? '#e2e2e2',
      gap: 12,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Workflow Copilot</h2>
        {!isIdle && (
          <span style={{
            fontSize: 10,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 4,
            background: `${statusColor(workflowState, accent)}22`,
            color: statusColor(workflowState, accent),
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}>
            {workflowState}
          </span>
        )}
      </div>

      {/* TuneHub Learning UI */}
      {learning.active && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: '10px 12px',
          borderRadius: 8,
          background: `${accent}10`,
          border: `1px solid ${accent}44`,
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600 }}>
            TuneHub Learning: {learning.workflow_name}
          </div>
          {renderProgressBar(learning.percent, accent)}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t?.textMuted ?? '#6b7280' }}>
            <span>{learning.current_source}</span>
            <span>{learning.steps_found} steps found</span>
          </div>
        </div>
      )}

      {learning.result && !learning.active && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: '10px 12px',
          borderRadius: 8,
          background: '#22c55e10',
          border: '1px solid #22c55e44',
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e' }}>
            Learning Complete
          </div>
          <div style={{ fontSize: 10, color: t?.textMuted ?? '#6b7280' }}>
            New workflow learned with {(learning.result.confidence as number) || 0}% confidence
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              style={{
                flex: 1,
                borderRadius: 6,
                background: '#22c55e',
                color: '#fff',
                padding: '5px 0',
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
              }}
              onClick={() => {
                const template = learning.result?.template as Record<string, string> | undefined;
                if (template?.template_id) {
                  approveLearned(template.template_id);
                  initiate(template.template_id, {});
                }
              }}
            >
              Run Now
            </button>
            <button
              style={{
                flex: 1,
                borderRadius: 6,
                background: t?.inputBg ?? '#0f0f1a',
                color: t?.text ?? '#e2e2e2',
                padding: '5px 0',
                fontSize: 11,
                fontWeight: 600,
                border: `1px solid ${t?.border ?? '#27273a'}`,
                cursor: 'pointer',
              }}
              onClick={() => {
                const template = learning.result?.template as Record<string, string> | undefined;
                if (template?.template_id) {
                  approveLearned(template.template_id);
                }
              }}
            >
              Save Only
            </button>
            <button
              style={{
                flex: 1,
                borderRadius: 6,
                background: '#ef4444',
                color: '#fff',
                padding: '5px 0',
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
              }}
              onClick={() => {
                const template = learning.result?.template as Record<string, string> | undefined;
                if (template?.template_id) {
                  rejectLearned(template.template_id, 'user_rejected');
                }
              }}
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {learning.failed_reason && !learning.active && (
        <div style={{
          padding: '8px 10px',
          borderRadius: 8,
          background: '#ef444410',
          border: '1px solid #ef444444',
          fontSize: 11,
          color: '#ef4444',
          flexShrink: 0,
        }}>
          Learning failed: {learning.failed_reason}
        </div>
      )}

      {isIdle ? (
        /* ── Preset Selection ── */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          <div style={{ fontSize: 12, color: t?.textMuted ?? '#6b7280' }}>
            Choose a workflow that makes your day easier:
          </div>

          {/* Preset dropdown */}
          {presets.length > 0 && (
            <CustomDropdown
              value={selectedPreset}
              onChange={(v) => {
                setSelectedPreset(v);
                setParams({});
                setFreeformText('');
              }}
              options={presets.map((p) => ({
                value: p.id,
                label: p.display_name ?? p.name,
                recommended_for: p.description,
                category: PRESET_CATEGORIES[p.category] ?? p.category,
              }))}
              theme={t!}
              label="Workflow"
              placeholder="Select a workflow..."
              grouped
              showRecommendedFor
            />
          )}

          {/* Preset info card */}
          {selectedPresetData && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              padding: '10px 12px',
              borderRadius: 8,
              background: `${accent}08`,
              border: `1px solid ${accent}30`,
              fontSize: 11,
              lineHeight: 1.5,
            }}>
              <div>
                <span style={{ fontWeight: 600, color: accent }}>What it does: </span>
                <span style={{ color: t?.text ?? '#e2e2e2' }}>{selectedPresetData.what_it_does}</span>
              </div>
              <div>
                <span style={{ fontWeight: 600, color: accent }}>Useful for: </span>
                <span style={{ color: t?.text ?? '#e2e2e2' }}>{selectedPresetData.usage}</span>
              </div>
              <div>
                <span style={{ fontWeight: 600, color: '#f59e0b' }}>Limitations: </span>
                <span style={{ color: t?.textMuted ?? '#6b7280' }}>{selectedPresetData.limitations}</span>
              </div>
            </div>
          )}

          {/* Dynamic params */}
          {selectedPresetData && selectedPresetData.params_schema.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {selectedPresetData.params_schema.map((schema) => (
                <div key={schema.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 10, color: t?.textMuted ?? '#6b7280', fontWeight: 500 }}>
                    {schema.label}
                  </label>
                  {renderParamInput(schema)}
                </div>
              ))}
            </div>
          )}

          {/* Freeform input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11, color: t?.textMuted ?? '#6b7280' }}>
              {selectedPresetData?.template_id === 'freeform'
                ? 'Describe your task:'
                : 'Or add extra instructions (optional):'}
            </div>
            <textarea
              style={{
                width: '100%',
                borderRadius: 8,
                background: t?.inputBg ?? '#0f0f1a',
                border: `1px solid ${t?.border ?? '#27273a'}`,
                padding: '8px 12px',
                fontSize: 13,
                color: t?.text ?? '#e2e2e2',
                fontFamily: 'inherit',
                outline: 'none',
                resize: 'vertical',
              }}
              placeholder={currentPlaceholder}
              rows={2}
              value={freeformText}
              onChange={(e) => {
                setFreeformText(e.target.value);
                setIsTyping(e.target.value.length > 0);
              }}
              onBlur={() => setIsTyping(false)}
              onFocus={() => setIsTyping(true)}
            />
            <button
              style={{
                borderRadius: 8,
                background: accent,
                color: inkFor(accent),
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                transition: 'filter 0.15s ease',
              }}
              onClick={handleRun}
              onMouseEnter={(e) => { e.currentTarget.style.filter = 'brightness(1.15)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.filter = 'none'; }}
            >
              Run Workflow
            </button>
          </div>
        </div>
      ) : (
        /* ── Active Workflow ── */
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          gap: 10,
          overflow: 'hidden',
        }}>
          {/* Progress & Status */}
          {(isRunning || isPaused) && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              padding: '10px 12px',
              borderRadius: 8,
              background: t?.headerBg ?? 'rgba(10,10,11,0.98)',
              border: `1px solid ${t?.border ?? '#27273a'}`,
              flexShrink: 0,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, fontWeight: 600 }}>
                <span>{status?.workflow_name ?? 'Workflow'}</span>
                {isRunning && (
                  <span style={{
                    fontSize: 9,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: '#0d948822',
                    color: '#2dd4bf',
                    fontWeight: 600,
                  }}>
                    Working...
                  </span>
                )}
              </div>
              {status && status.total_steps > 0 && (
                <>
                  {renderProgressBar(progressPct, accent)}
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t?.textMuted ?? '#6b7280' }}>
                    <span>Step {status.current_step} / {status.total_steps}</span>
                    <span>App: {status.current_app}</span>
                  </div>
                </>
              )}

              {/* Apps chain */}
              {status && status.apps_chain.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 2 }}>
                  {status.apps_chain.map((app, i) => (
                    <span key={`${app}-${i}`} style={{
                      fontSize: 9,
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: `${accent}15`,
                      color: accent,
                      fontWeight: 600,
                      textTransform: 'capitalize',
                    }}>
                      {app}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div style={{
              padding: '8px 10px',
              borderRadius: 8,
              background: '#ef444410',
              border: '1px solid #ef444444',
              fontSize: 11,
              color: '#ef4444',
              flexShrink: 0,
            }}>
              {error}
            </div>
          )}

          {/* Decision gate */}
          {decisionGate && (
            <div style={{
              padding: '10px 12px',
              borderRadius: 8,
              background: `${accent}10`,
              border: `1px solid ${accent}44`,
              flexShrink: 0,
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8 }}>
                Decision Required
              </div>
              <div style={{ fontSize: 11, color: t?.text ?? '#e2e2e2', marginBottom: 10 }}>
                {decisionGate.description}
              </div>

              {showGateEdit && (
                <input
                  autoFocus
                  style={{
                    width: '100%',
                    borderRadius: 6,
                    background: t?.inputBg ?? '#0f0f1a',
                    border: `1px solid ${t?.border ?? '#27273a'}`,
                    padding: '6px 10px',
                    fontSize: 12,
                    color: t?.text ?? '#e2e2e2',
                    fontFamily: 'inherit',
                    outline: 'none',
                    marginBottom: 8,
                  }}
                  placeholder="Type your response..."
                  value={gateEditValue}
                  onChange={(e) => setGateEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && gateEditValue.trim()) {
                      submitWorkflowDecision(decisionGate.gate_id ?? decisionGate.step_id.toString(), gateEditValue.trim());
                    }
                  }}
                />
              )}

              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  style={{
                    flex: 1,
                    borderRadius: 6,
                    background: '#22c55e',
                    color: '#fff',
                    padding: '6px 0',
                    fontSize: 12,
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onClick={() => submitWorkflowDecision(decisionGate.gate_id ?? decisionGate.step_id.toString(), 'yes')}
                >
                  Yes
                </button>
                <button
                  style={{
                    flex: 1,
                    borderRadius: 6,
                    background: '#ef4444',
                    color: '#fff',
                    padding: '6px 0',
                    fontSize: 12,
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onClick={() => submitWorkflowDecision(decisionGate.gate_id ?? decisionGate.step_id.toString(), 'no')}
                >
                  No
                </button>
                <button
                  style={{
                    flex: 1,
                    borderRadius: 6,
                    background: t?.inputBg ?? '#0f0f1a',
                    color: t?.text ?? '#e2e2e2',
                    padding: '6px 0',
                    fontSize: 12,
                    fontWeight: 600,
                    border: `1px solid ${t?.border ?? '#27273a'}`,
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    if (showGateEdit && gateEditValue.trim()) {
                      submitWorkflowDecision(decisionGate.gate_id ?? decisionGate.step_id.toString(), gateEditValue.trim());
                    } else {
                      setShowGateEdit(true);
                    }
                  }}
                >
                  {showGateEdit ? 'Send' : 'Edit'}
                </button>
              </div>
            </div>
          )}

          {/* Step timeline */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            minHeight: 0,
          }}>
            {steps.length === 0 && !isCompleted && (
              <div style={{
                textAlign: 'center',
                padding: '20px 0',
                color: t?.textMuted ?? '#6b7280',
                fontSize: 12,
              }}>
                Starting workflow...
              </div>
            )}

            {steps.map((step, idx) => {
              const isLast = idx === steps.length - 1;
              const color = isLast && isRunning ? accent : isLast && isCompleted ? '#22c55e' : t?.textMuted ?? '#6b7280';
              return (
                <div
                  key={`${step.id}-${idx}`}
                  style={{
                    display: 'flex',
                    gap: 8,
                    alignItems: 'flex-start',
                    padding: '6px 8px',
                    borderRadius: 6,
                    background: isLast ? `${color}08` : 'transparent',
                    borderLeft: `2px solid ${isLast ? color : 'transparent'}`,
                  }}
                >
                  <span style={{
                    fontSize: 12,
                    flexShrink: 0,
                    marginTop: 1,
                    minWidth: 18,
                    textAlign: 'center',
                  }}>
                    {stepIcon(step.action)}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 11,
                      color: isLast ? (t?.text ?? '#e2e2e2') : (t?.textMuted ?? '#6b7280'),
                      lineHeight: 1.4,
                      fontWeight: isLast ? 500 : 400,
                    }}>
                      {step.description || step.action}
                    </div>
                    <div style={{
                      fontSize: 9,
                      color: t?.textMuted ?? '#6b7280',
                      marginTop: 2,
                      textTransform: 'capitalize',
                    }}>
                      {step.app}
                    </div>
                    {step.output && (
                      <div style={{
                        fontSize: 9,
                        color: t?.textMuted ?? '#6b7280',
                        marginTop: 2,
                        lineHeight: 1.4,
                        wordBreak: 'break-word',
                        opacity: 0.8,
                      }}>
                        {step.output}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Result Card */}
          {(isCompleted || workflowResult) && (
            <div style={{
              padding: '12px 14px',
              borderRadius: 8,
              background: '#22c55e10',
              border: '1px solid #22c55e44',
              flexShrink: 0,
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e', marginBottom: 6 }}>
                Workflow Complete
              </div>
              <div style={{
                fontSize: 12,
                color: t?.text ?? '#e2e2e2',
                lineHeight: 1.5,
                marginBottom: 10,
                wordBreak: 'break-word',
              }}>
                {workflowResult ?? (summary?.message as string) ?? 'Done'}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  style={{
                    flex: 1,
                    borderRadius: 6,
                    background: '#22c55e',
                    color: '#fff',
                    padding: '6px 0',
                    fontSize: 11,
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onClick={handleCopyResult}
                >
                  Copy to Clipboard
                </button>
                <button
                  style={{
                    flex: 1,
                    borderRadius: 6,
                    background: t?.inputBg ?? '#0f0f1a',
                    color: t?.text ?? '#e2e2e2',
                    padding: '6px 0',
                    fontSize: 11,
                    fontWeight: 600,
                    border: `1px solid ${t?.border ?? '#27273a'}`,
                    cursor: 'pointer',
                  }}
                  onClick={handleRunAnother}
                >
                  Run Another
                </button>
              </div>
            </div>
          )}

          {/* Controls */}
          <div style={{
            display: 'flex',
            gap: 6,
            flexShrink: 0,
            paddingTop: 4,
          }}>
            {isPaused && !decisionGate ? (
              <button
                style={{
                  flex: 1,
                  borderRadius: 6,
                  background: '#0d9488',
                  color: '#fff',
                  padding: '6px 0',
                  fontSize: 12,
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={resume}
              >
                Resume
              </button>
            ) : isRunning ? (
              <button
                style={{
                  flex: 1,
                  borderRadius: 6,
                  background: '#d97706',
                  color: '#fff',
                  padding: '6px 0',
                  fontSize: 12,
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={pause}
              >
                Pause
              </button>
            ) : null}
            <button
              style={{
                flex: 1,
                borderRadius: 6,
                background: '#ef4444',
                color: '#fff',
                padding: '6px 0',
                fontSize: 12,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
              }}
              onClick={abort}
            >
              Stop
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
