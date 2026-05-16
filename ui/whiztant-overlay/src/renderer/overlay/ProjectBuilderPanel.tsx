import React, { useState, useRef, useEffect } from 'react';
import { useProjectBuilder, type ExecutionLog, type LogLevel } from './useProjectBuilder';
import { PhaseTimeline } from './PhaseTimeline';
import type { Theme } from '../shared/themes';

const logLevelColor = (level: LogLevel, accent: string): string => {
  switch (level) {
    case 'success': return '#22c55e';
    case 'error': return '#ef4444';
    case 'warning': return '#f59e0b';
    case 'staging': return '#3b82f6';
    default: return accent;
  }
};

const logLevelIcon = (level: LogLevel): string => {
  switch (level) {
    case 'success': return '✓';
    case 'error': return '✗';
    case 'warning': return '⚠';
    case 'staging': return '⏳';
    default: return '›';
  }
};

export const ProjectBuilderPanel: React.FC<{ theme?: Theme['panel'] }> = ({ theme }) => {
  const {
    status,
    loading,
    logs,
    wsConnected,
    createProject,
    approve,
    pause,
    resume,
  } = useProjectBuilder();

  const [path, setPath] = useState('');
  const [description, setDescription] = useState('');
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs'>('timeline');
  const logsEndRef = useRef<HTMLDivElement>(null);

  const t = theme;

  // Auto-scroll logs
  useEffect(() => {
    if (activeTab === 'logs' && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, activeTab]);

  const renderStatusBadge = (state?: string) => {
    if (!state) return null;
    const colors: Record<string, string> = {
      running: '#22c55e',
      paused: '#f59e0b',
      completed: '#3b82f6',
      cancelled: '#ef4444',
      failed: '#ef4444',
    };
    const color = colors[state] || (t?.textMuted ?? '#6b7280');
    return (
      <span style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 4,
        background: `${color}22`,
        color,
        textTransform: 'uppercase',
        letterSpacing: 0.5,
      }}>
        {state}
      </span>
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
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Project Builder</h2>
        {wsConnected && (
          <span style={{
            fontSize: 10,
            color: '#22c55e',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <span style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: '#22c55e',
              display: 'inline-block',
            }} />
            Live
          </span>
        )}
      </div>

      {!status ? (
        /* ── Create Form ── */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input
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
            }}
            placeholder="Project path (e.g. /home/user/my-app)"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
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
            placeholder="Describe what you want to build..."
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            style={{
              borderRadius: 8,
              background: t?.aiAccent ?? '#c0c1ff',
              color: '#07070f',
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              opacity: loading || !path || !description ? 0.5 : 1,
              transition: 'filter 0.15s ease',
            }}
            onClick={() => createProject(path, description)}
            disabled={loading || !path || !description}
            onMouseEnter={(e) => {
              if (!loading && path && description) {
                e.currentTarget.style.filter = 'brightness(1.15)';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.filter = 'none';
            }}
          >
            {loading ? 'Planning...' : 'Start Build'}
          </button>
        </div>
      ) : (
        /* ── Running Project ── */
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          gap: 10,
          overflow: 'hidden',
        }}>
          {/* Status bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 10px',
            borderRadius: 8,
            background: t?.headerBg ?? 'rgba(10,10,11,0.98)',
            border: `1px solid ${t?.border ?? '#27273a'}`,
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {renderStatusBadge(status.state)}
              {status.ui_score !== undefined && (
                <span style={{
                  fontSize: 10,
                  color: status.ui_score >= 80 ? '#22c55e' : '#f59e0b',
                  fontWeight: 500,
                }}>
                  UI: {status.ui_score}/100
                </span>
              )}
              {status.needs_approval && (
                <span style={{
                  fontSize: 10,
                  color: '#f59e0b',
                  fontWeight: 600,
                  animation: 'pulse 2s infinite',
                }}>
                  Needs Approval
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {status.state === 'PAUSED' || status.needs_approval ? (
                <button
                  style={{
                    borderRadius: 6,
                    background: '#0d9488',
                    color: '#fff',
                    padding: '4px 12px',
                    fontSize: 12,
                    border: 'none',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                  onClick={resume}
                >
                  Resume
                </button>
              ) : (
                <button
                  style={{
                    borderRadius: 6,
                    background: t?.aiAccent ?? '#c0c1ff',
                    color: '#07070f',
                    padding: '4px 12px',
                    fontSize: 12,
                    border: 'none',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                  onClick={approve}
                >
                  Approve Next
                </button>
              )}
              <button
                style={{
                  borderRadius: 6,
                  background: '#d97706',
                  color: '#fff',
                  padding: '4px 12px',
                  fontSize: 12,
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
                onClick={pause}
              >
                Pause
              </button>
            </div>
          </div>

          {/* Approval banner */}
          {status.needs_approval && status.approval_reason && (
            <div style={{
              padding: '10px 12px',
              borderRadius: 8,
              background: `${t?.aiAccent ?? '#c0c1ff'}10`,
              border: `1px solid ${t?.aiAccent ?? '#c0c1ff'}44`,
              fontSize: 12,
              color: t?.text ?? '#e2e2e2',
              flexShrink: 0,
            }}>
              <span style={{ fontWeight: 600 }}>Approval Required:</span>{' '}
              {status.approval_reason}
            </div>
          )}

          {/* Tab switcher */}
          <div style={{
            display: 'flex',
            gap: 4,
            flexShrink: 0,
          }}>
            {(['timeline', 'logs'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  flex: 1,
                  padding: '6px 0',
                  fontSize: 12,
                  fontWeight: 600,
                  borderRadius: 6,
                  border: 'none',
                  cursor: 'pointer',
                  background: activeTab === tab
                    ? `${t?.aiAccent ?? '#c0c1ff'}22`
                    : 'transparent',
                  color: activeTab === tab
                    ? (t?.aiAccent ?? '#c0c1ff')
                    : (t?.textMuted ?? '#6b7280'),
                  borderBottom: activeTab === tab
                    ? `2px solid ${t?.aiAccent ?? '#c0c1ff'}`
                    : '2px solid transparent',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab === 'timeline' ? 'Timeline' : `Logs (${logs.length})`}
              </button>
            ))}
          </div>

          {/* Content area */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            minHeight: 0,
          }}>
            {activeTab === 'timeline' ? (
              <PhaseTimeline
                plan={status.plan}
                currentLayerId={status.current_layer}
                currentPhaseId={status.current_phase}
                currentSubphaseId={status.current_subphase}
                theme={theme}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {logs.length === 0 && (
                  <div style={{
                    textAlign: 'center',
                    padding: '20px 0',
                    color: t?.textMuted ?? '#6b7280',
                    fontSize: 12,
                  }}>
                    No logs yet...
                  </div>
                )}
                {logs.map((log) => {
                  const color = logLevelColor(log.level, t?.aiAccent ?? '#c0c1ff');
                  return (
                    <div
                      key={log.id}
                      style={{
                        display: 'flex',
                        gap: 8,
                        alignItems: 'flex-start',
                        padding: '6px 8px',
                        borderRadius: 6,
                        background: `${color}08`,
                        borderLeft: `2px solid ${color}`,
                      }}
                    >
                      <span style={{
                        fontSize: 11,
                        color,
                        fontWeight: 700,
                        flexShrink: 0,
                        marginTop: 1,
                      }}>
                        {logLevelIcon(log.level)}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 11,
                          color: t?.text ?? '#e2e2e2',
                          lineHeight: 1.4,
                        }}>
                          {log.message}
                        </div>
                        {log.detail && (
                          <div style={{
                            fontSize: 10,
                            color: t?.textMuted ?? '#6b7280',
                            marginTop: 2,
                            lineHeight: 1.4,
                            wordBreak: 'break-word',
                          }}>
                            {log.detail}
                          </div>
                        )}
                        <div style={{
                          fontSize: 9,
                          color: t?.textMuted ?? '#6b7280',
                          marginTop: 2,
                          opacity: 0.6,
                        }}>
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
