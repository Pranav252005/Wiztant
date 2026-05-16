import React from 'react';
import type { Theme } from '../shared/themes';

interface PhaseTimelineProps {
  plan: any;
  currentLayerId?: string;
  currentPhaseId?: string;
  currentSubphaseId?: string;
  theme?: Theme['panel'];
}

const statusColor = (status: string, accent: string): string => {
  switch (status) {
    case 'done': return '#22c55e';
    case 'failed': return '#ef4444';
    case 'staging': return '#f59e0b';
    case 'verifying': return '#3b82f6';
    case 'running': return accent;
    default: return '#6b7280';
  }
};

export const PhaseTimeline: React.FC<PhaseTimelineProps> = ({
  plan,
  currentLayerId,
  currentPhaseId,
  currentSubphaseId,
  theme,
}) => {
  const t = theme;
  if (!plan || !plan.layers) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {plan.layers.map((layer: any) => {
        const isActiveLayer = layer.id === currentLayerId;
        return (
          <div
            key={layer.id}
            style={{
              borderRadius: 10,
              border: `1px solid ${isActiveLayer ? (t?.accent ?? '#c0c1ff') : (t?.border ?? '#27273a')}`,
              padding: 12,
              background: isActiveLayer
                ? `${t?.accent ?? '#c0c1ff'}08`
                : 'transparent',
            }}
          >
            <div style={{
              fontWeight: 600,
              fontSize: 13,
              color: isActiveLayer ? (t?.accent ?? '#c0c1ff') : (t?.text ?? '#e2e2e2'),
              marginBottom: 8,
            }}>
              {layer.id}: {layer.name}
              {layer.status && (
                <span style={{
                  marginLeft: 8,
                  fontSize: 10,
                  fontWeight: 500,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: `${statusColor(layer.status, t?.accent ?? '#c0c1ff')}22`,
                  color: statusColor(layer.status, t?.accent ?? '#c0c1ff'),
                }}>
                  {layer.status}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {layer.phases.map((phase: any) => {
                const isActivePhase = phase.id === currentPhaseId;
                return (
                  <div
                    key={phase.id}
                    style={{
                      borderRadius: 8,
                      border: `1px solid ${isActivePhase ? `${t?.accent ?? '#c0c1ff'}66` : (t?.border ?? '#27273a')}`,
                      padding: 10,
                      background: isActivePhase
                        ? `${t?.accent ?? '#c0c1ff'}06`
                        : 'transparent',
                    }}
                  >
                    <div style={{
                      fontSize: 12,
                      color: isActivePhase ? (t?.text ?? '#e2e2e2') : (t?.textMuted ?? '#6b7280'),
                      marginBottom: 6,
                    }}>
                      {phase.id}: {phase.name}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {phase.subphases.map((sub: any) => {
                        const isActiveSub = sub.id === currentSubphaseId;
                        const subStatusColor = statusColor(sub.status, t?.accent ?? '#c0c1ff');
                        return (
                          <div
                            key={sub.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              borderRadius: 6,
                              padding: '4px 8px',
                              fontSize: 11,
                              color: isActiveSub ? (t?.text ?? '#e2e2e2') : (t?.textMuted ?? '#6b7280'),
                              background: isActiveSub
                                ? `${subStatusColor}15`
                                : 'transparent',
                              borderLeft: isActiveSub
                                ? `2px solid ${subStatusColor}`
                                : '2px solid transparent',
                            }}
                          >
                            <span style={{
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              flex: 1,
                            }}>
                              {sub.id} — {sub.description}
                            </span>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 500,
                              textTransform: 'capitalize',
                              color: subStatusColor,
                              flexShrink: 0,
                              marginLeft: 8,
                            }}>
                              {sub.status}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
};
