import React from 'react';
import ReactDOM from 'react-dom/client';
import Overlay from './Overlay';
import TaskPanel from './TaskPanel';
import MemoryPanel from './MemoryPanel';
import StreakPanel from './StreakPanel';
import '../shared/types';

const isTaskPanelRoute = window.location.hash.startsWith('#/task-panel');
const isMemoryPanelRoute = window.location.hash.startsWith('#/memory-panel');
const isStreakPanelRoute = window.location.hash.startsWith('#/streak-panel');

function Route() {
  if (isTaskPanelRoute) return <TaskPanel />;
  if (isMemoryPanelRoute) return <MemoryPanel />;
  if (isStreakPanelRoute) return <StreakPanel />;
  return <Overlay />;
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Route />
  </React.StrictMode>,
);
