import React from 'react';

interface PhaseTimelineProps {
  plan: any;
  currentLayerId?: string;
  currentPhaseId?: string;
  currentSubphaseId?: string;
}

export const PhaseTimeline: React.FC<PhaseTimelineProps> = ({ plan, currentLayerId, currentPhaseId, currentSubphaseId }) => {
  if (!plan || !plan.layers) return null;
  return (
    <div className="space-y-4">
      {plan.layers.map((layer: any) => (
        <div key={layer.id} className={`rounded-lg border p-3 ${layer.id === currentLayerId ? 'border-indigo-400 bg-indigo-950/30' : 'border-gray-700'}`}>
          <div className="font-semibold text-sm text-indigo-200">{layer.id}: {layer.name}</div>
          <div className="mt-2 space-y-2">
            {layer.phases.map((phase: any) => (
              <div key={phase.id} className={`rounded border p-2 ${phase.id === currentPhaseId ? 'border-purple-400 bg-purple-950/20' : 'border-gray-800'}`}>
                <div className="text-xs text-gray-300">{phase.id}: {phase.name}</div>
                <div className="mt-1 space-y-1">
                  {phase.subphases.map((sub: any) => (
                    <div key={sub.id} className={`flex items-center justify-between rounded px-2 py-1 text-xs ${sub.id === currentSubphaseId ? 'bg-teal-900/40 text-teal-200' : 'text-gray-400'}`}>
                      <span>{sub.id} — {sub.description}</span>
                      <span className="capitalize">{sub.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
