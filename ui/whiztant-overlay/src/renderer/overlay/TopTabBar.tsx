import type { Theme } from '../shared/themes';
import type { TopTabId } from './useTopTabNav';
import type { FeatureFlags } from '../settings/Settings';

const ALL_TABS: { id: TopTabId; label: string; featureKey?: keyof FeatureFlags }[] = [
  { id: 'chat', label: 'Tune' },
  { id: 'wizprompt', label: 'RePrompt', featureKey: 'reprompt' },
  { id: 'agent', label: 'Builder', featureKey: 'agent' },
  { id: 'tasks', label: 'TaskStack', featureKey: 'tasks' },
  { id: 'memories', label: 'Memories' },
];

// Tabs that are always visible regardless of feature flags
const ALWAYS_VISIBLE: Set<TopTabId> = new Set(['chat', 'memories']);

type ProcessStatus = 'idle' | 'active' | 'completed' | 'error';

type Props = {
  active: TopTabId;
  onChange: (tab: TopTabId) => void;
  theme: Theme['panel'];
  enabledFeatures?: FeatureFlags;
  processes?: Record<string, ProcessStatus>;
};

export default function TopTabBar({ active, onChange, theme, enabledFeatures, processes }: Props) {
  const visibleTabs = ALL_TABS.filter((tab) => {
    if (ALWAYS_VISIBLE.has(tab.id)) return true;
    if (!tab.featureKey) return true;
    // If no feature flags provided, show all tabs (backward compatible)
    if (!enabledFeatures) return true;
    return enabledFeatures[tab.featureKey];
  });

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
      {visibleTabs.map((tab) => {
        const isActive = tab.id === active;
        const proc = processes?.[tab.id];
        const procColor = proc === 'active' ? theme.aiAccent : proc === 'completed' ? '#22c55e' : proc === 'error' ? '#ef4444' : undefined;
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
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            {tab.label}
            {procColor && (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: procColor,
                  display: 'inline-block',
                  flexShrink: 0,
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
