import type { ReactNode } from 'react';
import type { TopTabId } from './useTopTabNav';

type Props = {
  activeTab: TopTabId;
  chat: ReactNode;
  wizprompt: ReactNode;
  agent: ReactNode;
  tasks: ReactNode;
  memories: ReactNode;
};

export default function TopTabContent({ activeTab, chat, wizprompt, agent, tasks, memories }: Props) {
  const tabs: [TopTabId, ReactNode][] = [
    ['chat', chat],
    ['wizprompt', wizprompt],
    ['agent', agent],
    ['tasks', tasks],
    ['memories', memories],
  ];

  return (
    <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
      {tabs.map(([id, content]) => (
        <div
          key={id}
          style={{
            position: 'absolute',
            inset: 0,
            display: activeTab === id ? 'flex' : 'none',
            flexDirection: 'column',
            overflowY: 'auto',
          }}
        >
          {content}
        </div>
      ))}
    </div>
  );
}
