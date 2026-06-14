import type { Theme } from '../shared/themes';
import type { TopTabId } from './useTopTabNav';
import type { FeatureFlags } from '../settings/Settings';

const ALL_TABS: { id: TopTabId; label: string; tooltip: string; featureKey?: keyof FeatureFlags }[] = [
  { id: 'chat', label: 'Tune Hub', tooltip: 'Teach Wiztant your style — tune dictation and RePrompt to how you work' },
  { id: 'wizprompt', label: 'RePrompt', tooltip: 'Optimize any prompt — copy text, press Ctrl+Shift+Space', featureKey: 'reprompt' },
  { id: 'agent', label: 'Agent', tooltip: 'Run workflows on your screen — toggle with a double-tap of F9', featureKey: 'agent' },
  { id: 'tasks', label: 'Tasks', tooltip: 'Track to-dos with due times, reminders and snooze', featureKey: 'tasks' },
  { id: 'memories', label: 'Memories', tooltip: 'Everything you dictated with F9, searchable' },
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
  // The agent tab stays visible when its feature is disabled, shown as "Coming Soon".
  const isComingSoon = (tab: (typeof ALL_TABS)[number]) =>
    tab.id === 'agent' && !!enabledFeatures && !enabledFeatures.agent;

  const visibleTabs = ALL_TABS.filter((tab) => {
    if (ALWAYS_VISIBLE.has(tab.id)) return true;
    if (!tab.featureKey) return true;
    // If no feature flags provided, show all tabs (backward compatible)
    if (!enabledFeatures) return true;
    return enabledFeatures[tab.featureKey] || isComingSoon(tab);
  });

  return (
    <div
      role="tablist"
      aria-label="Overlay sections"
      data-tour="tabbar"
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
        const comingSoon = isComingSoon(tab);
        const isActive = tab.id === active && !comingSoon;
        const proc = processes?.[tab.id];
        const procColor = proc === 'active' ? theme.aiAccent : proc === 'completed' ? '#22c55e' : proc === 'error' ? '#ef4444' : undefined;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            title={comingSoon ? 'Agent mode is coming soon' : tab.tooltip}
            onClick={() => { if (!comingSoon) onChange(tab.id); }}
            disabled={comingSoon}
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
              cursor: comingSoon ? 'default' : 'pointer',
              opacity: comingSoon ? 0.55 : 1,
              transition: 'background 0.14s, color 0.14s, border-color 0.14s',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            {tab.label}
            {comingSoon && (
              <span
                style={{
                  fontSize: 8,
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  padding: '1px 5px',
                  borderRadius: 6,
                  border: `1px solid ${theme.border}`,
                  color: theme.textMuted,
                  flexShrink: 0,
                }}
              >
                Soon
              </span>
            )}
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
