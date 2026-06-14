import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { themes, defaultTheme, inkFor, isLightBg, type Theme } from '../shared/themes';
import type { ThemeName, UpdateStatus } from '../shared/ipc';
import InsightsTab from './InsightsTab';
import { useBridgeMessage, sendBridgeMessage } from '../shared/useBridge';
import { useCredits, type CreditTransaction } from '../shared/useCredits';
import CustomDropdown from '../shared/CustomDropdown';

const THEME_NAMES = Object.keys(themes) as ThemeName[];

type SystemAccess = 'standard' | 'system' | 'deep';
const SYSTEM_ACCESS_VALUES: SystemAccess[] = ['standard', 'system', 'deep'];

export type SettingsTab = 'general' | 'dictation' | 'agent' | 'integrations' | 'tasks' | 'features' | 'credits';

// ─── Integration types ─────────────────────────────────────
type IntegrationAuthType = 'credential' | 'oauth';

interface PublicIntegration {
  id: string;
  app: string;
  auth_type: IntegrationAuthType;
  field_keys: string[];
  oauth_connected: boolean;
  updated_at?: number;
}

const OAUTH_PROVIDERS = ['google', 'slack', 'github'] as const;

const LS_KEYS = {
  sound: 'whiztant.sound',
  systemAccess: 'whiztant.systemAccess',
} as const;

// ─── Feature flags ─────────────────────────────────────────
export type FeatureKey = 'agent' | 'tasks' | 'reprompt' | 'tunehub';

export interface FeatureFlags {
  agent: boolean;
  tasks: boolean;
  reprompt: boolean;
  tunehub: boolean;
}

const FEATURE_KEYS: Record<FeatureKey, string> = {
  agent: 'whiztant.feature.agent',
  tasks: 'whiztant.feature.tasks',
  reprompt: 'whiztant.feature.reprompt',
  tunehub: 'whiztant.feature.tunehub',
};

export const DEFAULT_FEATURES: FeatureFlags = {
  agent: true,
  tasks: true,
  reprompt: true,
  tunehub: true,
};

export function readFeatureFlags(): FeatureFlags {
  try {
    const stored = window.localStorage.getItem('whiztant.features');
    if (stored) {
      const parsed = JSON.parse(stored) as Partial<FeatureFlags>;
      return { ...DEFAULT_FEATURES, ...parsed };
    }
  } catch {
    /* noop */
  }
  // Fallback: read individual keys
  return {
    agent: readLS(FEATURE_KEYS.agent, 'true') === 'true',
    tasks: readLS(FEATURE_KEYS.tasks, 'true') === 'true',
    reprompt: readLS(FEATURE_KEYS.reprompt, 'true') === 'true',
    tunehub: readLS(FEATURE_KEYS.tunehub, 'true') === 'true',
  };
}

export function writeFeatureFlags(features: FeatureFlags) {
  try {
    window.localStorage.setItem('whiztant.features', JSON.stringify(features));
    for (const [key, lsKey] of Object.entries(FEATURE_KEYS)) {
      window.localStorage.setItem(lsKey, String(features[key as FeatureKey]));
    }
  } catch {
    /* noop */
  }
}

function readLS(key: string, fallback: string): string {
  try {
    const v = window.localStorage.getItem(key);
    return v == null ? fallback : v;
  } catch {
    return fallback;
  }
}
function writeLS(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* noop */
  }
}

export default function Settings({
  onBack,
  initialTheme,
  initialTab,
}: {
  onBack: () => void;
  initialTheme?: ThemeName;
  initialTab?: SettingsTab;
}) {
  const [active, setActive] = useState<ThemeName>(
    () =>
      (initialTheme ?? (readLS('whiztant.theme', '') as ThemeName | '')) || defaultTheme,
  );
  const theme = themes[active].panel;

  useEffect(() => {
    const handler = (n: ThemeName) => setActive(n);
    window.api.onThemeChanged(handler);
  }, []);

  const applyTheme = (name: ThemeName) => {
    setActive(name);
    window.api.setTheme(name);
    writeLS('whiztant.theme', name);
  };

  const [soundEnabled, setSoundEnabled] = useState<boolean>(
    () => readLS(LS_KEYS.sound, 'true') === 'true',
  );
  const [pillNotificationsEnabled, setPillNotificationsEnabled] = useState<boolean>(
    () => readLS('whiztant.pillNotifications', 'true') === 'true',
  );
  const [liveDictationPreview, setLiveDictationPreview] = useState<boolean>(false);
  const [correctionCopyWait, setCorrectionCopyWait] = useState<number>(3);

  // Feature flags state
  const [features, setFeatures] = useState<FeatureFlags>(() => readFeatureFlags());
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({ status: 'idle' });

  // Sync live dictation preview setting with Python backend
  useBridgeMessage((msg) => {
    if (msg?.type === 'settings/update' && msg.settings) {
      const settings = msg.settings as Record<string, unknown>;
      setLiveDictationPreview(Boolean(settings.live_dictation_preview));
      const ccw = settings.correction_copy_wait_sec;
      if (typeof ccw === 'number') setCorrectionCopyWait(ccw);
      else if (typeof ccw === 'string') setCorrectionCopyWait(Number(ccw) || 3);
    }
    if (msg?.type === 'features/update' && msg.features) {
      const updated = (msg.features as Partial<FeatureFlags>);
      setFeatures((prev) => {
        const next = { ...prev, ...updated };
        writeFeatureFlags(next);
        return next;
      });
    }
  });

  // Request current settings on mount so we don't default to false every time
  // the settings panel is reopened.
  useEffect(() => {
    sendBridgeMessage({ type: 'settings/get' });
  }, []);

  // Subscribe to auto-updater status from main process
  useEffect(() => {
    window.api.onUpdateStatus((s) => setUpdateStatus(s));
  }, []);

  useEffect(() => writeLS(LS_KEYS.sound, String(soundEnabled)), [soundEnabled]);
  useEffect(() => writeLS('whiztant.pillNotifications', String(pillNotificationsEnabled)), [pillNotificationsEnabled]);

  const togglePillNotifications = () => {
    const next = !pillNotificationsEnabled;
    setPillNotificationsEnabled(next);
  };

  const toggleLivePreview = () => {
    const next = !liveDictationPreview;
    setLiveDictationPreview(next);
    sendBridgeMessage({ type: 'settings/set', key: 'live_dictation_preview', value: next });
  };

  const setCopyWait = (value: number) => {
    const clamped = Math.max(1, Math.min(10, value));
    setCorrectionCopyWait(clamped);
    sendBridgeMessage({ type: 'settings/set', key: 'correction_copy_wait_sec', value: clamped });
  };

  const toggleFeature = (key: FeatureKey) => {
    const next = { ...features, [key]: !features[key] };
    setFeatures(next);
    writeFeatureFlags(next);
    sendBridgeMessage({ type: 'features/update', features: next });
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: theme.bg,
        border: `1px solid ${theme.border}`,
        borderRadius: 16,
        backdropFilter: 'blur(40px)',
        WebkitBackdropFilter: 'blur(40px)',
        overflow: 'hidden',
        fontFamily: 'Geist, "Segoe UI", sans-serif',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <SettingsContent
        theme={theme}
        activeTheme={active}
        onApplyTheme={applyTheme}
        soundEnabled={soundEnabled}
        setSoundEnabled={setSoundEnabled}
        pillNotificationsEnabled={pillNotificationsEnabled}
        onTogglePillNotifications={togglePillNotifications}
        liveDictationPreview={liveDictationPreview}
        onToggleLivePreview={toggleLivePreview}
        correctionCopyWait={correctionCopyWait}
        onSetCopyWait={setCopyWait}
        features={features}
        onToggleFeature={toggleFeature}
        onBack={onBack}
        initialTab={initialTab}
        updateStatus={updateStatus}
      />
    </div>
  );
}

// ─── Settings content with tabbed navigation ─────────────
function SettingsContent({
  theme,
  activeTheme,
  onApplyTheme,
  soundEnabled,
  setSoundEnabled,
  pillNotificationsEnabled,
  onTogglePillNotifications,
  liveDictationPreview,
  onToggleLivePreview,
  correctionCopyWait,
  onSetCopyWait,
  features,
  onToggleFeature,
  onBack,
  initialTab,
  updateStatus,
}: {
  theme: Theme['panel'];
  activeTheme: ThemeName;
  onApplyTheme: (name: ThemeName) => void;
  soundEnabled: boolean;
  setSoundEnabled: (v: boolean) => void;
  pillNotificationsEnabled: boolean;
  onTogglePillNotifications: () => void;
  liveDictationPreview: boolean;
  onToggleLivePreview: () => void;
  correctionCopyWait: number;
  onSetCopyWait: (v: number) => void;
  features: FeatureFlags;
  onToggleFeature: (key: FeatureKey) => void;
  onBack: () => void;
  initialTab?: SettingsTab;
  updateStatus: UpdateStatus;
}) {
  const [tab, setTab] = useState<SettingsTab>(initialTab ?? 'general');

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'general', label: 'General' },
    { id: 'features', label: 'Features' },
    { id: 'dictation', label: 'Dictation' },
    { id: 'agent', label: 'Agent' },
    { id: 'integrations', label: 'Integrations' },
    { id: 'tasks', label: 'Tasks' },
    { id: 'credits', label: 'Credits' },
  ];

  return (
    <>
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          background: theme.headerBg,
          borderBottom: `1px solid ${theme.border}`,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <button
          onClick={onBack}
          aria-label="Back"
          title="Back"
          style={{
            background: 'transparent',
            border: 'none',
            color: theme.textMuted,
            fontSize: 16,
            cursor: 'pointer',
            lineHeight: 1,
            padding: 2,
            marginRight: 8,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
          onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
        >
          ←
        </button>
        <span style={{ color: theme.text, fontSize: 13, fontWeight: 600 }}>
          Settings
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={onBack}
          aria-label="Close"
          style={{
            background: 'transparent',
            border: 'none',
            color: theme.textMuted,
            fontSize: 16,
            cursor: 'pointer',
            lineHeight: 1,
            padding: 2,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
          onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
        >
          ✕
        </button>
      </div>

      {/* Tab strip */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          padding: '0 16px',
          background: theme.headerBg,
          borderBottom: `1px solid ${theme.border}`,
          flexShrink: 0,
          overflowX: 'auto',
        }}
      >
        {tabs.map((t) => {
          const isActive = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: '8px 12px',
                fontSize: 12,
                fontWeight: isActive ? 600 : 500,
                color: isActive ? theme.text : theme.textMuted,
                background: isActive ? `${theme.aiAccent}15` : 'transparent',
                border: 'none',
                borderBottom: `2px solid ${isActive ? theme.aiAccent : 'transparent'}`,
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'color 0.15s, background 0.15s',
                marginBottom: -1,
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
        }}
      >
        {tab === 'general' && (
          <GeneralTab
            theme={theme}
            activeTheme={activeTheme}
            onApplyTheme={onApplyTheme}
            soundEnabled={soundEnabled}
            setSoundEnabled={setSoundEnabled}
            pillNotificationsEnabled={pillNotificationsEnabled}
            onTogglePillNotifications={onTogglePillNotifications}
            updateStatus={updateStatus}
          />
        )}
        {tab === 'features' && (
          <FeaturesTab theme={theme} features={features} onToggleFeature={onToggleFeature} />
        )}
        {tab === 'dictation' && (
          <DictationTab
            theme={theme}
            liveDictationPreview={liveDictationPreview}
            onToggleLivePreview={onToggleLivePreview}
            correctionCopyWait={correctionCopyWait}
            onSetCopyWait={onSetCopyWait}
          />
        )}
        {tab === 'agent' && <AgentTab theme={theme} />}
        {tab === 'integrations' && <IntegrationsTab theme={theme} />}
        {tab === 'tasks' && <TasksTab theme={theme} />}
        {tab === 'credits' && <CreditsTab theme={theme} />}
      </div>
    </>
  );
}

// ─── General tab ───────────────────────────────────────────
function GeneralTab({
  theme,
  activeTheme,
  onApplyTheme,
  soundEnabled,
  setSoundEnabled,
  pillNotificationsEnabled,
  onTogglePillNotifications,
  updateStatus,
}: {
  theme: Theme['panel'];
  activeTheme: ThemeName;
  onApplyTheme: (name: ThemeName) => void;
  soundEnabled: boolean;
  setSoundEnabled: (v: boolean) => void;
  pillNotificationsEnabled: boolean;
  onTogglePillNotifications: () => void;
  updateStatus: UpdateStatus;
}) {
  return (
    <>
      <section>
        <Label text="Theme" color={theme.textMuted} />
        <div
          style={{
            display: 'flex',
            gap: 10,
            flexWrap: 'wrap',
            marginTop: 10,
          }}
        >
          {THEME_NAMES.map((name) => {
            const t = themes[name];
            const isActive = name === activeTheme;
            return (
              <motion.button
                key={name}
                whileTap={{ scale: 0.9 }}
                onClick={() => onApplyTheme(name)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 6,
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 2,
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: t.pill.bg,
                    border: `1px solid ${t.pill.border}`,
                    position: 'relative',
                    boxShadow: isActive
                      ? `0 0 0 3px ${theme.bg}, 0 0 0 5px ${t.pill.idle}`
                      : `0 0 0 2px ${isLightBg(theme.bg) ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
                    transition: 'box-shadow 0.15s',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: t.pill.idle,
                    }}
                  />
                </div>
                <span
                  style={{
                    fontSize: 10,
                    color: isActive ? theme.text : theme.textMuted,
                    fontWeight: isActive ? 600 : 400,
                    letterSpacing: '0.02em',
                  }}
                >
                  {t.name}
                </span>
              </motion.button>
            );
          })}
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="Runtime" color={theme.textMuted} />
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <ToggleRow
            theme={theme}
            label="Sound effects"
            description="Play audio cues on events"
            value={soundEnabled}
            onChange={setSoundEnabled}
          />
          <ToggleRow
            theme={theme}
            label="Pill notifications"
            description="Show popup notices on the pill for tasks, alerts, and reminders"
            value={pillNotificationsEnabled}
            onChange={onTogglePillNotifications}
          />
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="Getting started" color={theme.textMuted} />
        <div style={{ marginTop: 10 }}>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('wiz-replay-tour'))}
            style={{
              padding: '7px 12px',
              borderRadius: 8,
              border: `1px solid ${theme.border}`,
              background: 'transparent',
              color: theme.text,
              fontSize: 11,
              fontWeight: 600,
              fontFamily: 'inherit',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = theme.aiAccent;
              e.currentTarget.style.background = `${theme.aiAccent}12`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = theme.border;
              e.currentTarget.style.background = 'transparent';
            }}
          >
            Replay welcome tour
          </button>
          <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 6, lineHeight: 1.4 }}>
            Walks through the hotkeys, the pill, and each tab again.
          </div>
        </div>
      </section>

      <Divider color={theme.border} />

      <ShortcutsSection theme={theme} />

      <Divider color={theme.border} />

      <section>
        <Label text="Update" color={theme.textMuted} />
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div style={{ fontSize: 12, color: theme.text }}>
            {updateStatus.status === 'checking' && 'Checking for updates…'}
            {updateStatus.status === 'available' && `Update available: v${updateStatus.version}`}
            {updateStatus.status === 'downloaded' && `v${updateStatus.version} ready to install`}
            {updateStatus.status === 'error' && 'Update check failed'}
            {updateStatus.status === 'idle' && 'Up to date'}
          </div>
          {updateStatus.status === 'downloaded' && (
            <button
              onClick={() => window.api.restartToUpdate()}
              style={{
                fontSize: 12,
                color: theme.aiAccent,
                background: `${theme.aiAccent}15`,
                border: `1px solid ${theme.aiAccent}40`,
                borderRadius: 6,
                padding: '6px 14px',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontWeight: 600,
                alignSelf: 'flex-start',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = `${theme.aiAccent}25`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = `${theme.aiAccent}15`;
              }}
            >
              Restart to Update
            </button>
          )}
        </div>
      </section>

      <Divider color={theme.border} />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 11, color: theme.textMuted }}>
          Whiztant v1.0.0
        </span>
        <button
          onClick={() => window.api.quit()}
          style={{
            fontSize: 12,
            color: '#F87171',
            background: 'transparent',
            border: '1px solid rgba(248,113,113,0.2)',
            borderRadius: 6,
            padding: '4px 10px',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = 'rgba(248,113,113,0.08)')
          }
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          Quit
        </button>
      </div>
    </>
  );
}

// ─── Agent tab ─────────────────────────────────────────────
function ModelSelectRow({
  theme,
  label,
  description,
  value,
  onChange,
  models,
}: {
  theme: Theme['panel'];
  label: string;
  description: string;
  value: string;
  onChange: (v: string) => void;
  models: Array<{ value: string; label: string }>;
}) {
  return (
    <div>
      <div style={{ fontSize: 12, color: theme.text, fontWeight: 500, marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 11, color: theme.textMuted, marginBottom: 6 }}>
        {description}
      </div>
      <CustomDropdown
        value={value}
        onChange={onChange}
        options={models}
        theme={theme}
      />
    </div>
  );
}

function DictationTab({
  theme,
  liveDictationPreview,
  onToggleLivePreview,
  correctionCopyWait,
  onSetCopyWait,
}: {
  theme: Theme['panel'];
  liveDictationPreview: boolean;
  onToggleLivePreview: () => void;
  correctionCopyWait: number;
  onSetCopyWait: (v: number) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <section>
        <Label text="Dictation behavior" color={theme.textMuted} />
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ToggleRow
            theme={theme}
            label="Dictation preview"
            description="Show an editable preview above the pill before pasting. You can edit, optimize, and copy the text."
            value={liveDictationPreview}
            onChange={onToggleLivePreview}
          />
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 12, color: theme.text, marginBottom: 6 }}>
              Correction finalize wait: <strong>{correctionCopyWait}s</strong>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={correctionCopyWait}
              onChange={(e) => onSetCopyWait(Number(e.target.value))}
              style={{ width: '100%', accentColor: theme.aiAccent }}
            />
            <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 4 }}>
              Seconds to wait after copying before finalizing the learned correction.
            </div>
          </div>
        </div>
      </section>
      <Divider color={theme.border} />
      <DictionarySection theme={theme} />
      <Divider color={theme.border} />
      <InsightsTab theme={theme} />
    </div>
  );
}

// ─── My Dictionary (user vocabulary for dictation) ─────────
function DictionarySection({ theme }: { theme: Theme['panel'] }) {
  const [words, setWords] = useState<string[]>([]);
  const [corrections, setCorrections] = useState<{ heard: string; actual: string }[]>([]);
  const [newWord, setNewWord] = useState('');
  const [pairHeard, setPairHeard] = useState('');
  const [pairActual, setPairActual] = useState('');

  useBridgeMessage((msg: any) => {
    if (msg?.type === 'vocab/update') {
      setWords(Array.isArray(msg.words) ? msg.words.filter(Boolean) : []);
      setCorrections(Array.isArray(msg.corrections) ? msg.corrections : []);
    }
  });

  useEffect(() => {
    sendBridgeMessage({ type: 'vocab/list' });
  }, []);

  const addWord = () => {
    const w = newWord.trim();
    if (!w) return;
    sendBridgeMessage({ type: 'vocab/add_word', word: w });
    setNewWord('');
  };

  const addPair = () => {
    const heard = pairHeard.trim();
    const actual = pairActual.trim();
    if (!heard || !actual) return;
    sendBridgeMessage({ type: 'vocab/add_pair', heard, actual });
    setPairHeard('');
    setPairActual('');
  };

  const inputStyle: CSSProperties = {
    background: theme.inputBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '7px 10px',
    fontSize: 12,
    color: theme.text,
    outline: 'none',
    flex: 1,
    minWidth: 0,
  };
  const addBtnStyle: CSSProperties = {
    background: theme.aiAccent,
    color: '#07070f',
    border: 'none',
    borderRadius: 8,
    padding: '7px 14px',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  };
  const chipStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    background: theme.inputBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 999,
    padding: '4px 10px',
    fontSize: 12,
    color: theme.text,
  };
  const removeBtnStyle: CSSProperties = {
    background: 'transparent',
    border: 'none',
    color: theme.textMuted,
    cursor: 'pointer',
    fontSize: 12,
    padding: 0,
    lineHeight: 1,
  };

  return (
    <section>
      <Label text="My Dictionary" color={theme.textMuted} />
      <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 6, lineHeight: 1.5 }}>
        Add names, brands, and jargon you actually say. When dictation mishears one of them,
        only that word is corrected — the rest of your sentence is never touched.
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <input
          type="text"
          placeholder="Add a word (e.g. Wiztant)"
          value={newWord}
          onChange={(e) => setNewWord(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addWord()}
          style={inputStyle}
        />
        <button onClick={addWord} style={addBtnStyle}>Add</button>
      </div>

      {words.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
          {words.map((w) => (
            <span key={w} style={chipStyle}>
              {w}
              <button
                onClick={() => sendBridgeMessage({ type: 'vocab/delete_word', word: w })}
                style={removeBtnStyle}
                title="Remove word"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 16 }}>
        Exact replacements (optional): map a specific mis-hearing to the correct word.
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input
          type="text"
          placeholder="Heard as (e.g. whiz tent)"
          value={pairHeard}
          onChange={(e) => setPairHeard(e.target.value)}
          style={inputStyle}
        />
        <input
          type="text"
          placeholder="Correct word"
          value={pairActual}
          onChange={(e) => setPairActual(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addPair()}
          style={inputStyle}
        />
        <button onClick={addPair} style={addBtnStyle}>Add</button>
      </div>

      {corrections.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10 }}>
          {corrections.map((c) => (
            <div
              key={c.heard}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: 12,
                color: theme.text,
                background: theme.inputBg,
                border: `1px solid ${theme.border}`,
                borderRadius: 8,
                padding: '5px 10px',
              }}
            >
              <span>
                <span style={{ color: theme.textMuted }}>{c.heard}</span>
                {' → '}
                {c.actual}
              </span>
              <button
                onClick={() => sendBridgeMessage({ type: 'vocab/delete_correction', heard: c.heard })}
                style={removeBtnStyle}
                title="Remove replacement"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

type AgentSettings = {
  agent_max_steps: number;
  AGENT_PLANNER_MODEL: string;
  AGENT_OMNI_MODEL: string;
};

function AgentTab({ theme }: { theme: Theme['panel'] }) {
  const [settings, setSettings] = useState<AgentSettings>({
    agent_max_steps: 100,
    AGENT_PLANNER_MODEL: '',
    AGENT_OMNI_MODEL: '',
  });
  const [statusMsg, setStatusMsg] = useState<string>('');

  useBridgeMessage((msg: any) => {
    if (msg?.type === 'settings/agent/update' && msg.settings) {
      setSettings({
        agent_max_steps: Number(msg.settings.agent_max_steps) || 100,
        AGENT_PLANNER_MODEL: msg.settings.AGENT_PLANNER_MODEL ?? '',
        AGENT_OMNI_MODEL: msg.settings.AGENT_OMNI_MODEL ?? '',
      });
      setStatusMsg('Saved.');
    }
  });

  useEffect(() => {
    sendBridgeMessage({ type: 'settings/agent/get' });
  }, []);

  const save = () => {
    setStatusMsg('');
    sendBridgeMessage({ type: 'settings/agent/save', ...settings });
  };

  const labelStyle: CSSProperties = { fontSize: 11, color: theme.textMuted, letterSpacing: '0.02em' };
  const inputStyle: CSSProperties = {
    background: theme.inputBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '8px 10px',
    fontSize: 12,
    color: theme.text,
    outline: 'none',
    width: '100%',
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0, overflowY: 'auto', padding: '4px 2px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: theme.text }}>Agent Settings</span>
        <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.5 }}>
          Limits and model overrides for the screen agent. Changes apply to the next agent run.
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={labelStyle}>Max steps per task</span>
        <input
          type="number"
          min={1}
          max={500}
          value={settings.agent_max_steps}
          onChange={(e) => setSettings({ ...settings, agent_max_steps: Number(e.target.value) })}
          style={inputStyle}
        />
        <span style={{ fontSize: 10, color: theme.textMuted }}>
          Safety ceiling on actions the agent may take in one task (default 100).
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={labelStyle}>Planner model</span>
        <input
          type="text"
          placeholder="qwen/qwen3-vl-235b-a22b-instruct"
          value={settings.AGENT_PLANNER_MODEL}
          onChange={(e) => setSettings({ ...settings, AGENT_PLANNER_MODEL: e.target.value })}
          style={inputStyle}
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={labelStyle}>Vision model</span>
        <input
          type="text"
          placeholder="google/gemini-3-flash-preview"
          value={settings.AGENT_OMNI_MODEL}
          onChange={(e) => setSettings({ ...settings, AGENT_OMNI_MODEL: e.target.value })}
          style={inputStyle}
        />
        <span style={{ fontSize: 10, color: theme.textMuted }}>
          OpenRouter model ids. Leave blank to use the built-in defaults. Model changes apply after restart.
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          onClick={save}
          style={{
            background: theme.aiAccent,
            color: '#07070f',
            border: 'none',
            borderRadius: 8,
            padding: '8px 18px',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Save
        </button>
        {statusMsg && <span style={{ fontSize: 11, color: theme.textMuted }}>{statusMsg}</span>}
      </div>
    </div>
  );
}

// ─── Integrations tab ──────────────────────────────────────
// Lets the user authorize apps so the agent can log into them automatically.
// OAuth for apps that support it; a local encrypted credential vault otherwise.
// Nothing is sent to any Wiztant cloud DB — all secrets stay encrypted on the
// user's machine (handled by core/integrations.py).
function IntegrationsTab({ theme }: { theme: Theme['panel'] }) {
  const [items, setItems] = useState<PublicIntegration[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [oauthBusy, setOauthBusy] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string>('');

  useBridgeMessage((msg: any) => {
    if (msg?.type === 'integrations/update' && Array.isArray(msg.integrations)) {
      setItems(msg.integrations as PublicIntegration[]);
    } else if (msg?.type === 'integrations/error') {
      setStatusMsg(`Error: ${msg.error}`);
    } else if (msg?.type === 'integrations/oauth/result') {
      setOauthBusy(null);
      setStatusMsg(msg.ok ? `${msg.app}: connected.` : `${msg.app}: ${msg.error}`);
    }
  });

  useEffect(() => {
    sendBridgeMessage({ type: 'integrations/list' });
  }, []);

  const remove = (id: string) => sendBridgeMessage({ type: 'integrations/delete', id });

  const labelStyle: CSSProperties = { fontSize: 11, color: theme.textMuted, letterSpacing: '0.02em' };
  const cardStyle: CSSProperties = {
    background: theme.inputBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    padding: 12,
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0, overflowY: 'auto', padding: '4px 2px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: theme.text }}>App Integrations</span>
        <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.5 }}>
          Authorize apps once so the agent can sign in automatically. Credentials are
          encrypted and stored only on this device — never uploaded.
        </span>
      </div>

      {statusMsg && (
        <div style={{ ...cardStyle, fontSize: 11, color: theme.text }}>{statusMsg}</div>
      )}

      {items.length === 0 && !showForm && (
        <span style={{ fontSize: 12, color: theme.textMuted, padding: '8px 0' }}>No integrations yet.</span>
      )}

      {items.map((it) => (
        <div key={it.id} style={{ ...cardStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>{it.app}</span>
            <span style={{ ...labelStyle }}>
              {it.auth_type === 'oauth'
                ? it.oauth_connected ? 'OAuth · connected' : 'OAuth · not connected'
                : `Vault · ${it.field_keys.join(', ') || 'no fields'}`}
            </span>
          </div>
          <button
            onClick={() => remove(it.id)}
            style={{ background: 'transparent', border: `1px solid ${theme.border}`, color: theme.textMuted, borderRadius: 8, padding: '4px 10px', fontSize: 11, cursor: 'pointer' }}
          >
            Remove
          </button>
        </div>
      ))}

      {showForm ? (
        <IntegrationForm
          theme={theme}
          onClose={() => setShowForm(false)}
          oauthBusy={oauthBusy}
          onConnectOauth={(app, provider, clientId, clientSecret) => {
            setOauthBusy(app);
            setStatusMsg(`${app}: opening browser…`);
            sendBridgeMessage({ type: 'integrations/oauth/start', app, provider, client_id: clientId, client_secret: clientSecret });
          }}
        />
      ) : (
        <button
          onClick={() => { setShowForm(true); setStatusMsg(''); }}
          style={{ background: theme.accent, color: isLightBg(theme.bg) ? '#000' : '#000', border: 'none', borderRadius: 10, padding: '10px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
        >
          + Add integration
        </button>
      )}
    </div>
  );
}

function IntegrationForm({
  theme,
  onClose,
  oauthBusy,
  onConnectOauth,
}: {
  theme: Theme['panel'];
  onClose: () => void;
  oauthBusy: string | null;
  onConnectOauth: (app: string, provider: string, clientId: string, clientSecret: string) => void;
}) {
  const [app, setApp] = useState('');
  const [authType, setAuthType] = useState<IntegrationAuthType>('credential');
  // Credential fields as editable key/value rows.
  const [fields, setFields] = useState<{ key: string; value: string }[]>([
    { key: 'email', value: '' },
    { key: 'password', value: '' },
  ]);
  // OAuth provider config.
  const [provider, setProvider] = useState<string>('google');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  const inputStyle: CSSProperties = {
    background: theme.bg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    color: theme.text,
    padding: '7px 9px',
    fontSize: 12,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  };
  const labelStyle: CSSProperties = { fontSize: 11, color: theme.textMuted, marginBottom: 4, display: 'block' };

  const setField = (i: number, patch: Partial<{ key: string; value: string }>) =>
    setFields((f) => f.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const addField = () => setFields((f) => [...f, { key: '', value: '' }]);
  const removeField = (i: number) => setFields((f) => f.filter((_, idx) => idx !== i));

  const saveCredential = () => {
    if (!app.trim()) return;
    const fieldObj: Record<string, string> = {};
    fields.forEach(({ key, value }) => {
      if (key.trim() && value.trim()) fieldObj[key.trim()] = value;
    });
    sendBridgeMessage({
      type: 'integrations/save',
      integration: { app: app.trim(), auth_type: 'credential', fields: fieldObj },
    });
    onClose();
  };

  const connectOauth = () => {
    if (!app.trim() || !clientId.trim()) return;
    onConnectOauth(app.trim(), provider, clientId.trim(), clientSecret.trim());
  };

  return (
    <div style={{ background: theme.inputBg, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div>
        <label style={labelStyle}>App name</label>
        <input style={inputStyle} placeholder="e.g. Slack" value={app} onChange={(e) => setApp(e.target.value)} />
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        {(['credential', 'oauth'] as IntegrationAuthType[]).map((t) => (
          <button
            key={t}
            onClick={() => setAuthType(t)}
            style={{
              flex: 1,
              background: authType === t ? theme.accent : 'transparent',
              color: authType === t ? '#000' : theme.textMuted,
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              padding: '6px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {t === 'credential' ? 'Credential vault' : 'OAuth'}
          </button>
        ))}
      </div>

      {authType === 'credential' ? (
        <>
          <span style={{ fontSize: 10, color: theme.textMuted, lineHeight: 1.5 }}>
            Stored encrypted on this device. The agent types these into the app's
            login screen and pauses to ask you for any OTP / 2FA code.
          </span>
          {fields.map((row, i) => (
            <div key={i} style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputStyle, flex: 1 }} placeholder="field (email)" value={row.key} onChange={(e) => setField(i, { key: e.target.value })} />
              <input style={{ ...inputStyle, flex: 1.4 }} placeholder="value" value={row.value} onChange={(e) => setField(i, { value: e.target.value })} />
              <button onClick={() => removeField(i)} style={{ background: 'transparent', border: `1px solid ${theme.border}`, color: theme.textMuted, borderRadius: 8, padding: '0 9px', fontSize: 14, cursor: 'pointer' }}>×</button>
            </div>
          ))}
          <button onClick={addField} style={{ background: 'transparent', border: `1px dashed ${theme.border}`, color: theme.textMuted, borderRadius: 8, padding: '6px', fontSize: 11, cursor: 'pointer' }}>+ Add field</button>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={onClose} style={{ flex: 1, background: 'transparent', border: `1px solid ${theme.border}`, color: theme.textMuted, borderRadius: 8, padding: '8px', fontSize: 12, cursor: 'pointer' }}>Cancel</button>
            <button onClick={saveCredential} style={{ flex: 1, background: theme.accent, color: '#000', border: 'none', borderRadius: 8, padding: '8px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>Save</button>
          </div>
        </>
      ) : (
        <>
          <span style={{ fontSize: 10, color: theme.textMuted, lineHeight: 1.5 }}>
            Real OAuth sign-in. Provide your OAuth client ID (and secret if
            required). A browser window opens to authorize; the token is stored
            encrypted on this device.
          </span>
          <div>
            <label style={labelStyle}>Provider</label>
            <select style={inputStyle} value={provider} onChange={(e) => setProvider(e.target.value)}>
              {OAUTH_PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Client ID</label>
            <input style={inputStyle} value={clientId} onChange={(e) => setClientId(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>Client secret (optional)</label>
            <input style={inputStyle} type="password" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={onClose} style={{ flex: 1, background: 'transparent', border: `1px solid ${theme.border}`, color: theme.textMuted, borderRadius: 8, padding: '8px', fontSize: 12, cursor: 'pointer' }}>Cancel</button>
            <button
              onClick={connectOauth}
              disabled={!!oauthBusy}
              style={{ flex: 1, background: theme.accent, color: '#000', border: 'none', borderRadius: 8, padding: '8px', fontSize: 12, fontWeight: 600, cursor: oauthBusy ? 'default' : 'pointer', opacity: oauthBusy ? 0.6 : 1 }}
            >
              {oauthBusy ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Tasks tab ─────────────────────────────────────────────
const TASKS_LS_KEYS = {
  reminderInterval: 'whiztant.tasks.reminderInterval',
  defaultDueTime: 'whiztant.tasks.defaultDueTime',
  snoozePresets: 'whiztant.tasks.snoozePresets',
  preDueWarning: 'whiztant.tasks.preDueWarning',
  carryOver: 'whiztant.tasks.carryOver',
  taskCreationMode: 'whiztant.tasks.creationMode',
} as const;

const INTERVAL_OPTIONS = [
  { value: 5, label: '5 minutes' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
];

const ALL_SNOOZE_PRESETS = [
  { value: null, label: 'Undefined' },
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 60, label: '1 hour' },
  { value: 1440, label: 'Tomorrow' },
];

function readSingleSnoozePreset(): number | null {
  try {
    const v = window.localStorage.getItem(TASKS_LS_KEYS.snoozePresets);
    if (v) {
      const parsed = JSON.parse(v) as number[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed[0];
    }
  } catch { /* noop */ }
  return null;
}

function TasksTab({ theme }: { theme: Theme['panel'] }) {
  const [reminderInterval, setReminderInterval] = useState<number>(() => {
    try {
      const v = window.localStorage.getItem(TASKS_LS_KEYS.reminderInterval);
      return v ? parseInt(v, 10) : 15;
    } catch { return 15; }
  });
  const [defaultDueTime, setDefaultDueTime] = useState<string>(() => {
    return window.localStorage.getItem(TASKS_LS_KEYS.defaultDueTime) || '17:00';
  });
  const [snoozePreset, setSnoozePreset] = useState<number | null>(readSingleSnoozePreset);
  const [preDueWarning, setPreDueWarning] = useState<boolean>(() => {
    return window.localStorage.getItem(TASKS_LS_KEYS.preDueWarning) !== 'false';
  });
  const [carryOver, setCarryOver] = useState<boolean>(() => {
    return window.localStorage.getItem(TASKS_LS_KEYS.carryOver) !== 'false';
  });
  const [taskCreationMode, setTaskCreationMode] = useState<'hotkey' | 'smart'>(() => {
    const stored = window.localStorage.getItem(TASKS_LS_KEYS.taskCreationMode);
    return stored === 'hotkey' ? 'hotkey' : 'smart';
  });
  const [taskAiEnabled, setTaskAiEnabled] = useState<boolean>(() => {
    return window.localStorage.getItem('whiztant.task_ai_enabled') !== 'false';
  });

  // Persist to localStorage and sync to backend
  const syncTasksSettings = useCallback((patch?: Record<string, unknown>) => {
    const settings: Record<string, unknown> = {
      reminder_interval_min: reminderInterval,
      default_due_time: defaultDueTime,
      snooze_presets: snoozePreset !== null ? [snoozePreset] : [],
      pre_due_warning: preDueWarning,
      carry_over: carryOver,
      ...patch,
    };
    sendBridgeMessage({ type: 'tasks/settings/set', ...settings });
  }, [reminderInterval, defaultDueTime, snoozePreset, preDueWarning, carryOver]);

  useEffect(() => {
    // Request current settings on mount
    sendBridgeMessage({ type: 'tasks/settings/get' });
  }, []);

  // Listen for backend settings updates
  useBridgeMessage((msg) => {
    if (msg?.type === 'tasks/settings/update' && msg.settings) {
      const s = msg.settings as Record<string, unknown>;
      if (typeof s.reminder_interval_min === 'number') {
        setReminderInterval(s.reminder_interval_min);
        window.localStorage.setItem(TASKS_LS_KEYS.reminderInterval, String(s.reminder_interval_min));
      }
      if (typeof s.default_due_time === 'string') {
        setDefaultDueTime(s.default_due_time);
        window.localStorage.setItem(TASKS_LS_KEYS.defaultDueTime, s.default_due_time);
      }
      if (Array.isArray(s.snooze_presets)) {
        const first = (s.snooze_presets as number[])[0] ?? null;
        setSnoozePreset(first);
        window.localStorage.setItem(TASKS_LS_KEYS.snoozePresets, JSON.stringify(s.snooze_presets));
      }
      if (typeof s.pre_due_warning === 'boolean') {
        setPreDueWarning(s.pre_due_warning);
        window.localStorage.setItem(TASKS_LS_KEYS.preDueWarning, String(s.pre_due_warning));
      }
      if (typeof s.carry_over === 'boolean') {
        setCarryOver(s.carry_over);
        window.localStorage.setItem(TASKS_LS_KEYS.carryOver, String(s.carry_over));
      }
      if (typeof s.task_creation_mode === 'string') {
        const mode = s.task_creation_mode === 'hotkey' ? 'hotkey' : 'smart';
        setTaskCreationMode(mode);
        window.localStorage.setItem(TASKS_LS_KEYS.taskCreationMode, mode);
      }
    }
  });

  const updateReminderInterval = (v: number) => {
    setReminderInterval(v);
    window.localStorage.setItem(TASKS_LS_KEYS.reminderInterval, String(v));
    syncTasksSettings({ reminder_interval_min: v });
  };
  const updateDefaultDueTime = (v: string) => {
    setDefaultDueTime(v);
    window.localStorage.setItem(TASKS_LS_KEYS.defaultDueTime, v);
    syncTasksSettings({ default_due_time: v });
  };
  const updateSnoozePreset = (v: number | null) => {
    setSnoozePreset(v);
    const asArray = v !== null ? [v] : [];
    window.localStorage.setItem(TASKS_LS_KEYS.snoozePresets, JSON.stringify(asArray));
    // Also update the overlay's local copy so TaskTile sees the change
    window.localStorage.setItem('whiztant.snooze_presets', JSON.stringify(asArray));
    syncTasksSettings({ snooze_presets: asArray });
  };
  const updatePreDueWarning = (v: boolean) => {
    setPreDueWarning(v);
    window.localStorage.setItem(TASKS_LS_KEYS.preDueWarning, String(v));
    syncTasksSettings({ pre_due_warning: v });
  };
  const updateCarryOver = (v: boolean) => {
    setCarryOver(v);
    window.localStorage.setItem(TASKS_LS_KEYS.carryOver, String(v));
    syncTasksSettings({ carry_over: v });
  };
  const updateTaskCreationMode = (v: 'hotkey' | 'smart') => {
    setTaskCreationMode(v);
    window.localStorage.setItem(TASKS_LS_KEYS.taskCreationMode, v);
    syncTasksSettings({ task_creation_mode: v });
  };
  const updateTaskAiEnabled = (v: boolean) => {
    setTaskAiEnabled(v);
    window.localStorage.setItem('whiztant.task_ai_enabled', String(v));
    fetch('http://localhost:8765/settings/task_ai_enabled', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: v }),
    }).catch(() => {});
  };

  useEffect(() => {
    fetch('http://localhost:8765/settings/task_ai_enabled')
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) {
          setTaskAiEnabled(d.enabled);
          window.localStorage.setItem('whiztant.task_ai_enabled', String(d.enabled));
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <section>
        <Label text="Reminders" color={theme.textMuted} />
        <p
          style={{
            fontSize: 11,
            color: theme.textMuted,
            lineHeight: 1.55,
            margin: '8px 0 10px',
          }}
        >
          Control how often Whiztant checks for due tasks and when you receive warnings.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 10 }}>
          {/* Reminder interval */}
          <div>
            <div style={{ fontSize: 10, color: theme.textMuted, marginBottom: 4, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Reminder check interval
            </div>
            <CustomDropdown
              value={String(reminderInterval)}
              onChange={(v) => updateReminderInterval(parseInt(v, 10))}
              options={INTERVAL_OPTIONS.map((o) => ({ value: String(o.value), label: o.label }))}
              theme={theme}
            />
          </div>

          {/* Default due time */}
          <div>
            <div style={{ fontSize: 10, color: theme.textMuted, marginBottom: 4, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Default due time
            </div>
            <input
              type="time"
              value={defaultDueTime}
              onChange={(e) => updateDefaultDueTime(e.target.value)}
              style={{
                ...selectStyle(theme),
                width: 'auto',
                minWidth: 120,
              }}
            />
          </div>
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="Snooze" color={theme.textMuted} />
        <p
          style={{
            fontSize: 11,
            color: theme.textMuted,
            lineHeight: 1.55,
            margin: '8px 0 10px',
          }}
        >
          Choose which snooze options appear on task tiles.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          {ALL_SNOOZE_PRESETS.map((preset) => {
            const active = snoozePreset === preset.value;
            return (
              <button
                key={preset.label}
                onClick={() => {
                  updateSnoozePreset(active ? null : preset.value);
                }}
                style={{
                  padding: '5px 12px',
                  borderRadius: 999,
                  border: `1px solid ${active ? theme.aiAccent : theme.border}`,
                  background: active ? `${theme.aiAccent}22` : 'transparent',
                  color: active ? theme.text : theme.textMuted,
                  fontSize: 11,
                  fontWeight: active ? 600 : 500,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  transition: 'background 0.12s, color 0.12s',
                }}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="Behavior" color={theme.textMuted} />
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ToggleRow
            theme={theme}
            label="Pre-due warning"
            description="Warn me 30 minutes before a task is due"
            value={preDueWarning}
            onChange={updatePreDueWarning}
          />
          <ToggleRow
            theme={theme}
            label="Carry over tasks"
            description="Automatically carry over unfinished tasks to the next day"
            value={carryOver}
            onChange={updateCarryOver}
          />
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="Task creation" color={theme.textMuted} />
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <RadioRow
            theme={theme}
            label="Smart detection in dictation"
            description="Say phrases like 'this is a task' or 'add that as a task' during F9 dictation. No extra hotkey needed."
            selected={taskCreationMode === 'smart'}
            onSelect={() => updateTaskCreationMode('smart')}
          />
          <RadioRow
            theme={theme}
            label="F10 hotkey"
            description="Press F10 to start a dedicated voice recording that saves directly as a task."
            selected={taskCreationMode === 'hotkey'}
            onSelect={() => updateTaskCreationMode('hotkey')}
          />
        </div>
      </section>

      <Divider color={theme.border} />

      <section>
        <Label text="AI Refinement" color={theme.textMuted} />
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ToggleRow
            theme={theme}
            label="Use AI for TaskStack"
            description={taskAiEnabled
              ? 'AI will refine and improve task text before saving.'
              : 'Tasks will be saved exactly as typed or spoken.'}
            value={taskAiEnabled}
            onChange={updateTaskAiEnabled}
          />
        </div>
      </section>
    </div>
  );
}

// ─── Credits tab ───────────────────────────────────────────
function CreditsTab({ theme }: { theme: Theme['panel'] }) {
  const credits = useCredits();

  const tierColor =
    credits.tier === 'power'
      ? '#C4956A'
      : credits.tier === 'pro'
        ? '#c0c1ff'
        : '#6b7280';

  const tierLabel = credits.tier === 'power' ? 'Power' : credits.tier === 'pro' ? 'Pro' : 'Free';

  const featureLabel = (f: string) => {
    const map: Record<string, string> = {
      dictation: 'Dictation',
      reprompt: 'RePrompt',
      reprompt_fast: 'RePrompt',
      reprompt_deep_agent: 'RePrompt (Deep)',
      reprompt_deep_synth: 'RePrompt (Synthesis)',
      reprompt_agent: 'RePrompt (Agent)',
      tunehub: 'TuneHub',
    };
    return map[f] || f.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const shortModel = (m?: string) => {
    if (!m) return '';
    const parts = m.split('/');
    const name = parts[parts.length - 1] || m;
    return name.replace('-preview', '').replace('-20260420', '');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Balance Card */}
      <section
        style={{
          padding: 20,
          borderRadius: 12,
          border: `1px solid ${theme.border}`,
          background: `${theme.headerBg}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Current Plan
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: tierColor,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              background: `${tierColor}15`,
              padding: '3px 10px',
              borderRadius: 999,
            }}
          >
            {tierLabel}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 36, fontWeight: 700, color: theme.text, lineHeight: 1 }}>
            {credits.balance.toLocaleString()}
          </span>
          <span style={{ fontSize: 13, color: theme.textMuted }}>
            / {credits.allocation.toLocaleString()} credits
          </span>
        </div>

        <div style={{ fontSize: 12, color: theme.textMuted, marginBottom: 14 }}>
          {credits.remainingPercent.toFixed(0)}% remaining this period
        </div>

        {/* Progress bar */}
        <div
          style={{
            width: '100%',
            height: 6,
            borderRadius: 3,
            background: theme.border,
            overflow: 'hidden',
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${credits.usagePercent}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
            style={{
              height: '100%',
              borderRadius: 3,
              background:
                credits.usagePercent > 90
                  ? '#EF4444'
                  : credits.usagePercent > 70
                    ? '#F59E0B'
                    : tierColor,
            }}
          />
        </div>

        {/* Zero-credits warning */}
        {credits.balance === 0 && !credits.loading && (
          <div
            style={{
              marginTop: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.3)',
              color: theme.text,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <strong>⚠️ 0 credits remaining</strong>
            <br />
            You have used all your credits for this period. Upgrade your plan to continue using AI features.
          </div>
        )}
      </section>

      {/* Per-Feature Usage Summary */}
      {credits.summary.length > 0 && (
        <section>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Label text="Usage by Feature" color={theme.textMuted} />
            <button
              onClick={() => credits.refreshSummary()}
              style={{
                fontSize: 11,
                color: theme.textMuted,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
              onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
            >
              Refresh
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {credits.summary.map((item) => (
              <div
                key={item.feature}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: 6,
                  background: theme.inputBg,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 500, color: theme.text }}>
                  {featureLabel(item.feature)}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#EF4444' }}>
                    −{item.total}
                  </div>
                  <div style={{ fontSize: 10, color: theme.textMuted }}>
                    {item.count} use{item.count === 1 ? '' : 's'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Plan Comparison */}
      <section>
        <Label text="Plans" color={theme.textMuted} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
          {[
            { tier: 'free', label: 'Free', credits: 50, price: '$0' },
            { tier: 'pro', label: 'Pro', credits: 1000, price: '$20/mo' },
            { tier: 'power', label: 'Power', credits: 5000, price: '$50/mo' },
          ].map((p) => {
            const isCurrent = credits.tier === p.tier;
            return (
              <div
                key={p.tier}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: `1px solid ${isCurrent ? tierColor : theme.border}`,
                  background: isCurrent ? `${tierColor}08` : 'transparent',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: isCurrent ? tierColor : theme.border,
                    }}
                  />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>
                      {p.label}
                    </div>
                    <div style={{ fontSize: 11, color: theme.textMuted }}>
                      {p.credits.toLocaleString()} credits / month
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: isCurrent ? tierColor : theme.textMuted }}>
                  {isCurrent ? 'Current' : p.price}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Upgrade CTA */}
      <section>
        <button
          onClick={() => window.api.openExternal('https://wiztant.com/pricing')}
          style={{
            width: '100%',
            padding: '10px 16px',
            borderRadius: 10,
            border: 'none',
            background: tierColor,
            color: '#07070f',
            fontSize: 13,
            fontWeight: 700,
            fontFamily: 'inherit',
            cursor: 'pointer',
            textAlign: 'center',
            transition: 'opacity 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.85'; }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
        >
          Upgrade Plan →
        </button>
      </section>

      {/* Recent Usage */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <Label text="Recent Usage" color={theme.textMuted} />
          <button
            onClick={() => credits.refreshHistory(20)}
            style={{
              fontSize: 11,
              color: theme.textMuted,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
            onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
          >
            Refresh
          </button>
        </div>

        {credits.transactions.length === 0 ? (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: theme.textMuted,
              fontSize: 12,
              border: `1px dashed ${theme.border}`,
              borderRadius: 8,
            }}
          >
            No usage yet. Start using features to see your credit history.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {credits.transactions.map((tx: CreditTransaction, i: number) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: 6,
                  background: theme.inputBg,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: theme.text }}>
                    {featureLabel(tx.feature)}
                  </div>
                  {tx.model && tx.feature !== 'dictation' && (
                    <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 1 }}>
                      {shortModel(tx.model)}
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#EF4444' }}>
                    −{tx.amount}
                  </div>
                  <div style={{ fontSize: 10, color: theme.textMuted }}>
                    {tx.balance_after.toLocaleString()} left
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ─── Features tab ──────────────────────────────────────────
function FeaturesTab({
  theme,
  features,
  onToggleFeature,
}: {
  theme: Theme['panel'];
  features: FeatureFlags;
  onToggleFeature: (key: FeatureKey) => void;
}) {
  const FEATURE_DEFS: { key: FeatureKey; label: string; description: string }[] = [
    {
      key: 'agent',
      label: 'Enable Agent',
      description: 'F9 double-tap to toggle agent mode for autonomous task execution',
    },
    {
      key: 'tasks',
      label: 'Enable Tasks',
      description: 'Task management with voice capture and reminders',
    },
    {
      key: 'reprompt',
      label: 'Enable RePrompt',
      description: 'Ctrl+Shift+Space to optimize prompts with AI agents',
    },
    {
      key: 'tunehub',
      label: 'Enable TuneHub',
      description: 'Adaptive tuning for dictation, tasks, and prompts',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <section>
        <Label text="Feature toggles" color={theme.textMuted} />
        <p
          style={{
            fontSize: 11,
            color: theme.textMuted,
            lineHeight: 1.55,
            margin: '8px 0 10px',
          }}
        >
          Enable or disable individual features. Changes take effect immediately and persist across sessions.
        </p>
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {FEATURE_DEFS.map((f) => (
            <ToggleRow
              key={f.key}
              theme={theme}
              label={f.label}
              description={f.description}
              value={features[f.key]}
              onChange={() => onToggleFeature(f.key)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

// ─── Shortcuts section ─────────────────────────────────────
type ShortcutAction = 'overlay_toggle' | 'dictation' | 'agent_toggle' | 'wizprompt' | 'task_voice' | 'dismiss';

const ACTION_LABELS: Record<ShortcutAction, string> = {
  overlay_toggle: 'Open / close tune',
  dictation: 'Voice dictation',
  agent_toggle: 'Agent mode',
  wizprompt: 'WizPrompt',
  task_voice: 'Add task (voice)',
  dismiss: 'Dismiss overlay',
};

const DEFAULT_SHORTCUTS: Record<ShortcutAction, string> = {
  overlay_toggle: 'Ctrl + Space',
  dictation: 'F9',
  agent_toggle: 'F9',
  wizprompt: 'Ctrl + Shift + Space',
  task_voice: 'F10',
  dismiss: 'Esc',
};

const LS_PREFIX = 'whiztant.shortcuts.';

function readShortcut(action: ShortcutAction): string {
  try {
    const v = window.localStorage.getItem(LS_PREFIX + action);
    return v || DEFAULT_SHORTCUTS[action];
  } catch {
    return DEFAULT_SHORTCUTS[action];
  }
}

function writeShortcut(action: ShortcutAction, value: string) {
  try {
    window.localStorage.setItem(LS_PREFIX + action, value);
  } catch { /* ignore */ }
}

function formatKeysForDisplay(keys: string[]): string {
  const modMap: Record<string, string> = {
    commandorcontrol: 'Ctrl',
    ctrl: 'Ctrl',
    shift: 'Shift',
    alt: 'Alt',
    command: 'Command',
    meta: 'Command',
  };
  const keyMap: Record<string, string> = {
    space: 'Space',
    escape: 'Esc',
    esc: 'Esc',
    arrowup: 'Up',
    arrowdown: 'Down',
    arrowleft: 'Left',
    arrowright: 'Right',
  };
  return keys
    .map((k) => {
      const lower = k.trim().toLowerCase();
      return modMap[lower] || keyMap[lower] || k.trim();
    })
    .join(' + ');
}

function formatKeysForElectron(keys: string[]): string {
  const modMap: Record<string, string> = {
    ctrl: 'CommandOrControl',
    commandorcontrol: 'CommandOrControl',
    command: 'CommandOrControl',
    shift: 'Shift',
    alt: 'Alt',
    meta: 'CommandOrControl',
  };
  const keyMap: Record<string, string> = {
    space: 'Space',
    escape: 'Escape',
    esc: 'Escape',
    arrowup: 'Up',
    arrowdown: 'Down',
    arrowleft: 'Left',
    arrowright: 'Right',
  };
  return keys
    .map((k) => {
      const lower = k.trim().toLowerCase();
      return modMap[lower] || keyMap[lower] || k.trim();
    })
    .join('+');
}

function captureKeyToParts(e: KeyboardEvent): string[] | null {
  const modifiers: string[] = [];
  if (e.ctrlKey) modifiers.push('Ctrl');
  if (e.altKey) modifiers.push('Alt');
  if (e.shiftKey) modifiers.push('Shift');
  if (e.metaKey) modifiers.push('Command');

  const key = e.key;
  // Ignore pure modifier presses
  if (['Control', 'Alt', 'Shift', 'Meta'].includes(key)) return null;

  // Prevent browser defaults for most captured keys
  if (key !== 'F5' && key !== 'F12') {
    e.preventDefault();
    e.stopPropagation();
  }

  const keyLabel = key === ' ' ? 'Space' : key;
  return [...modifiers, keyLabel];
}

function ShortcutsSection({ theme }: { theme: Theme['panel'] }) {
  const [shortcuts, setShortcuts] = useState<Record<ShortcutAction, string>>(() => ({
    overlay_toggle: readShortcut('overlay_toggle'),
    dictation: readShortcut('dictation'),
    agent_toggle: readShortcut('agent_toggle'),
    wizprompt: readShortcut('wizprompt'),
    task_voice: readShortcut('task_voice'),
    dismiss: readShortcut('dismiss'),
  }));

  const [selectedAction, setSelectedAction] = useState<ShortcutAction | ''>('');
  const [recording, setRecording] = useState(false);
  const [pendingValue, setPendingValue] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState('');

  const hasChanges = selectedAction !== '' && pendingValue !== null && pendingValue !== shortcuts[selectedAction];

  // Key capture effect
  useEffect(() => {
    if (!recording) return;

    const handler = (e: KeyboardEvent) => {
      const parts = captureKeyToParts(e);
      if (!parts) return;
      setPendingValue(formatKeysForDisplay(parts));
      setRecording(false);
    };

    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [recording]);

  const handleSave = () => {
    if (!selectedAction || pendingValue === null) return;
    const next = { ...shortcuts, [selectedAction]: pendingValue };
    setShortcuts(next);
    writeShortcut(selectedAction, pendingValue);

    // Build electron-formatted config and send to main
    const electronConfig: Record<string, string> = {};
    for (const [action, display] of Object.entries(next)) {
      const parts = display.split(/\s*\+\s*/).map((p) => p.trim());
      electronConfig[action] = formatKeysForElectron(parts);
    }
    window.api.reloadShortcuts(electronConfig);

    setSaveStatus('Saved');
    setTimeout(() => setSaveStatus(''), 1500);
  };

  const handleReset = () => {
    if (!selectedAction) return;
    const defaultValue = DEFAULT_SHORTCUTS[selectedAction];
    setPendingValue(defaultValue);
  };

  const shortcutList: { action: ShortcutAction; label: string }[] = [
    { action: 'overlay_toggle', label: 'Open / close tune' },
    { action: 'dictation', label: 'Voice dictation' },
    { action: 'agent_toggle', label: 'Agent mode' },
    { action: 'wizprompt', label: 'WizPrompt' },
    { action: 'task_voice', label: 'Add task (voice)' },
    { action: 'dismiss', label: 'Dismiss overlay' },
  ];

  return (
    <section>
      <Label text="Shortcuts" color={theme.textMuted} />
      <p
        style={{
          fontSize: 11,
          color: theme.textMuted,
          lineHeight: 1.55,
          margin: '8px 0 10px',
        }}
      >
        Customize your keyboard shortcuts. Select a feature, press a new key
        combination, then save.
      </p>

      {/* Current shortcuts reference */}
      <div
        style={{
          marginTop: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {shortcutList.map((s) => {
          const val = shortcuts[s.action];
          const isAgent = s.action === 'agent_toggle';
          const agentSharesKey = isAgent && val === shortcuts.dictation;
          const displayVal = agentSharesKey ? `${val} × 2` : val;
          return (
            <div
              key={s.action}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: 12, color: theme.textMuted }}>{s.label}</span>
              <kbd
                style={{
                  fontSize: 11,
                  color: theme.text,
                  background: `${theme.aiAccent}15`,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 5,
                  padding: '2px 8px',
                  fontFamily: 'Geist Mono, Consolas, monospace',
                }}
              >
                {displayVal}
              </kbd>
            </div>
          );
        })}
      </div>

      <Divider color={theme.border} />

      {/* Customize area */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 12, color: theme.text, fontWeight: 500 }}>
          Change shortcut
        </div>

        {/* Feature dropdown */}
        <div>
          <div
            style={{
              fontSize: 10,
              color: theme.textMuted,
              marginBottom: 4,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Feature
          </div>
          <select
            value={selectedAction}
            onChange={(e) => {
              setSelectedAction(e.target.value as ShortcutAction | '');
              setPendingValue(null);
              setSaveStatus('');
            }}
            style={selectStyle(theme)}
          >
            <option value="">Select a feature…</option>
            {shortcutList.map((s) => (
              <option key={s.action} value={s.action}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {selectedAction && (
          <>
            {/* Current value */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: theme.textMuted }}>Current:</span>
              <kbd
                style={{
                  fontSize: 11,
                  color: theme.text,
                  background: `${theme.aiAccent}15`,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 5,
                  padding: '2px 8px',
                  fontFamily: 'Geist Mono, Consolas, monospace',
                }}
              >
                {shortcuts[selectedAction]}
              </kbd>
            </div>

            {/* Record button */}
            <div>
              <div
                style={{
                  fontSize: 10,
                  color: theme.textMuted,
                  marginBottom: 4,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                New shortcut
              </div>
              <button
                onClick={() => {
                  setPendingValue(null);
                  setRecording(true);
                }}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: 7,
                  border: `1px solid ${recording ? theme.aiAccent : theme.border}`,
                  background: recording ? `${theme.aiAccent}15` : theme.inputBg,
                  color: recording ? theme.aiAccent : theme.text,
                  fontSize: 12,
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                {recording
                  ? 'Press a key combination…'
                  : pendingValue || 'Click to record a new shortcut'}
              </button>
              {recording && (
                <p style={{ fontSize: 10, color: theme.textMuted, margin: '4px 0 0' }}>
                  Press the key or combination you want to use (e.g. F10, Ctrl+Shift+T)
                </p>
              )}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                onClick={handleSave}
                disabled={!hasChanges}
                style={primaryBtn(theme, !!hasChanges)}
              >
                Save
              </button>
              <button
                onClick={handleReset}
                style={{
                  padding: '6px 12px',
                  borderRadius: 7,
                  background: 'transparent',
                  color: theme.textMuted,
                  border: `1px solid ${theme.border}`,
                  fontSize: 11,
                  fontWeight: 600,
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                }}
              >
                Reset to default
              </button>
              {saveStatus && (
                <span style={{ fontSize: 11, color: theme.textMuted }}>{saveStatus}</span>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

// ─── Reusable primitives ───────────────────────────────────
function Label({ text, color }: { text: string; color: string }) {
  return (
    <p
      style={{
        fontSize: 10,
        color,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        margin: 0,
        fontWeight: 600,
      }}
    >
      {text}
    </p>
  );
}

function Divider({ color }: { color: string }) {
  return <div style={{ height: 1, background: color }} />;
}

function ToggleRow({
  theme,
  label,
  description,
  value,
  onChange,
}: {
  theme: Theme['panel'];
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: theme.text, fontWeight: 500 }}>
          {label}
        </div>
        <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 2 }}>
          {description}
        </div>
      </div>
      <button
        onClick={() => onChange(!value)}
        role="switch"
        aria-checked={value}
        style={{
          position: 'relative',
          width: 34,
          height: 18,
          borderRadius: 999,
          border: `1px solid ${theme.border}`,
          background: value ? theme.aiAccent : 'transparent',
          cursor: 'pointer',
          padding: 0,
          flexShrink: 0,
          transition: 'background 0.18s',
        }}
      >
        <motion.span
          animate={{ x: value ? 16 : 0 }}
          transition={{ type: 'spring', stiffness: 420, damping: 32 }}
          style={{
            position: 'absolute',
            top: 1,
            left: 1,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: value ? theme.bg : theme.textMuted,
          }}
        />
      </button>
    </div>
  );
}

function RadioRow({
  theme,
  label,
  description,
  selected,
  onSelect,
}: {
  theme: Theme['panel'];
  label: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        padding: 0,
        textAlign: 'left',
        fontFamily: 'inherit',
      }}
    >
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: '50%',
          border: `2px solid ${selected ? theme.aiAccent : theme.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {selected && (
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: theme.aiAccent,
            }}
          />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: theme.text, fontWeight: 500 }}>
          {label}
        </div>
        <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 2 }}>
          {description}
        </div>
      </div>
    </button>
  );
}

function SystemAccessNote({
  theme,
  label,
  desc,
}: {
  theme: Theme['panel'];
  label: string;
  desc: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        fontSize: 11,
      }}
    >
      <span
        style={{
          color: theme.text,
          fontWeight: 600,
          minWidth: 52,
          textTransform: 'capitalize',
        }}
      >
        {label}
      </span>
      <span style={{ color: theme.textMuted, lineHeight: 1.5 }}>{desc}</span>
    </div>
  );
}

function miniPill(theme: Theme['panel'], active: boolean): CSSProperties {
  return {
    padding: '4px 12px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 600,
    border: `1px solid ${active ? theme.aiAccent : theme.border}`,
    background: active ? `${theme.aiAccent}22` : 'transparent',
    color: active ? theme.text : theme.textMuted,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'background 0.15s, color 0.15s',
  };
}

function selectStyle(theme: Theme['panel']): CSSProperties {
  return {
    width: '100%',
    padding: '6px 8px',
    borderRadius: 7,
    background: theme.inputBg,
    border: `1px solid ${theme.border}`,
    color: theme.text,
    fontSize: 12,
    outline: 'none',
    fontFamily: 'inherit',
  };
}

function primaryBtn(theme: Theme['panel'], enabled: boolean): CSSProperties {
  return {
    padding: '6px 12px',
    borderRadius: 7,
    background: enabled ? theme.aiAccent : `${theme.aiAccent}30`,
    color: enabled ? primaryBtnInk(theme) : theme.textMuted,
    border: 'none',
    fontSize: 11,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: enabled ? 'pointer' : 'not-allowed',
    transition: 'background 0.15s',
  };
}

function primaryBtnInk(theme: Theme['panel']): string {
  return inkFor(theme.aiAccent);
}

function TextField({
  theme,
  value,
  onChange,
  placeholder,
}: {
  theme: Theme['panel'];
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%',
        padding: '7px 10px',
        borderRadius: 8,
        background: theme.inputBg,
        border: `1px solid ${theme.border}`,
        color: theme.text,
        fontSize: 12,
        outline: 'none',
        fontFamily: 'inherit',
      }}
    />
  );
}

// Silence unused imports that TS can't see through JSX destructuring.
export type { ReactNode };
