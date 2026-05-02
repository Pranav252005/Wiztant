import type { Theme } from '../shared/themes';
import type { TopTabId } from './useTopTabNav';

const TABS: { id: TopTabId; label: string }[] = [
  { id: 'chat', label: 'Tune' },
  { id: 'wizprompt', label: 'Prompt' },
  { id: 'agent', label: 'Agent' },
  { id: 'tasks', label: 'Today' },
  { id: 'memories', label: 'Memories' },
  { id: 'tunehub', label: 'Chat' },
];

type Props = {
  active: TopTabId;
  onChange: (tab: TopTabId) => void;
  theme: Theme['panel'];
};

export default function TopTabBar({ active, onChange, theme }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Overlay sections"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '8px 10px 0',
        flexShrink: 0,
        overflowX: 'auto',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      }}
    >
      <style>{`
        div[role="tablist"]::-webkit-scrollbar {
          display: none;
        }
      `}</style>
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            style={{
              height: 28,
              padding: '0 10px',
              borderRadius: '8px 8px 0 0',
              border: `1px solid ${isActive ? theme.border : 'transparent'}`,
              borderBottom: `2px solid ${isActive ? theme.aiAccent : 'transparent'}`,
              background: isActive ? `${theme.aiAccent}26` : 'transparent',
              color: isActive ? theme.text : theme.textMuted,
              fontSize: 11,
              fontWeight: isActive ? 700 : 500,
              fontFamily: 'inherit',
              cursor: 'pointer',
              transition: 'background 0.14s, color 0.14s, border-color 0.14s',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
