import React, { useState } from 'react';
import { useProjectBuilder } from './useProjectBuilder';
import { PhaseTimeline } from './PhaseTimeline';

export const ProjectBuilderPanel: React.FC = () => {
  const { status, loading, createProject, approve, pause, resume } = useProjectBuilder();
  const [path, setPath] = useState('');
  const [description, setDescription] = useState('');

  return (
    <div className="flex flex-col h-full p-4 text-gray-200">
      <h2 className="text-lg font-bold mb-4">Project Builder</h2>
      {!status ? (
        <div className="space-y-3">
          <input
            className="w-full rounded bg-gray-900 border border-gray-700 px-3 py-2 text-sm"
            placeholder="Project path (e.g. /home/user/my-app)"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <textarea
            className="w-full rounded bg-gray-900 border border-gray-700 px-3 py-2 text-sm"
            placeholder="Describe what you want to build..."
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
            onClick={() => createProject(path, description)}
            disabled={loading || !path || !description}
          >
            {loading ? 'Planning...' : 'Start Build'}
          </button>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-gray-400">State: <span className="text-white font-mono">{status.state}</span></div>
            <div className="space-x-2">
              {status.state === 'PAUSED' ? (
                <button className="rounded bg-teal-600 px-3 py-1 text-xs hover:bg-teal-500" onClick={resume}>Resume</button>
              ) : (
                <button className="rounded bg-indigo-600 px-3 py-1 text-xs hover:bg-indigo-500" onClick={approve}>Approve Next</button>
              )}
              <button className="rounded bg-amber-600 px-3 py-1 text-xs hover:bg-amber-500" onClick={pause}>Pause</button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            <PhaseTimeline
              plan={status.plan}
              currentLayerId={status.current_layer}
              currentPhaseId={status.current_phase}
              currentSubphaseId={status.current_subphase}
            />
          </div>
        </div>
      )}
    </div>
  );
};
