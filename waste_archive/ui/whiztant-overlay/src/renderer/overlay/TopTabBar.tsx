import type { Theme } from '../shared/themes';
import type { TopTabId } from './useTopTabNav';
import type { FeatureFlags } from '../settings/Settings';

const ALL_TABS: { id: TopTabId; label: string; featureKey?: keyof FeatureFlags }[] = [
  { id: 'chat', label: 'Tune' },
  { id: 'tunehub', label: 'Chat', featureKey: 'tunehub' },
  { id: 'wizprompt', label: 'Prompt', featureKey: 'reprompt' },
  { id: 'agent', label: 'Agent', featureKey: 'agent' },
  { id: 'tasks', label: 'Today', featureKey: 'tasks' },
  { id: 'memories', label: 'Memories' },
];

// Tabs that are always visible regardless of feature flags
const ALWAYS_VISIBLE: Set<TopTabId> = new Set(['chat', 'memories']);

type Props = {
  active: TopTabId;
  onChange: (tab: TopTabId) => void;
  theme: Theme['panel'];
  enabledFeatures?: FeatureFlags;
};

export default function TopTabBar({ active, onChange, theme, enabledFeatures }: Props) {
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
