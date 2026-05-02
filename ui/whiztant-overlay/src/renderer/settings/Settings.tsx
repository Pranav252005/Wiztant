import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { themes, defaultTheme, type Theme } from '../shared/themes';
import type { ThemeName } from '../shared/ipc';
import InsightsTab from './InsightsTab';
import { useBridgeMessage, sendBridgeMessage } from '../shared/useBridge';

const THEME_NAMES = Object.keys(themes) as ThemeName[];

const SHORTCUTS: Array<{ key: string; action: string }> = [
  { key: 'Ctrl + Space', action: 'Open / close tune' },
  { key: 'F9', action: 'Voice dictation' },
  { key: 'F9 × 2', action: 'Agent mode' },
  { key: 'Esc', action: 'Dismiss overlay' },
];

type SystemAccess = 'standard' | 'system' | 'deep';
const SYSTEM_ACCESS_VALUES: SystemAccess[] = ['standard', 'system', 'deep'];

type SettingsTab = 'general' | 'dictation' | 'agent' | 'tasks';

const LS_KEYS = {
  sound: 'whiztant.sound',
  expanded: 'whiztant.expandedUI',
  systemAccess: 'whiztant.systemAccess',
  wizpromptModel: 'whiztant.wizprompt.model',
  wizpromptProvider: 'whiztant.wizprompt.provider',
  wizpromptModelName: 'whiztant.wizprompt.modelName',
  wizpromptApiKey: 'whiztant.wizprompt.apiKey',
} as const;

const PREDEFINED_MODELS = [
  { value: 'default', label: 'Default (Whiztant)' },
  { value: 'openai/gpt-5.5-mini', label: 'GPT 5.5 mini (OpenAI)' },
  { value: 'anthropic/claude-sonnet-4.6', label: 'Claude Sonnet 4.6 (Anthropic)' },
  { value: 'moonshotai/kimi-k2-6', label: 'Kimi K2.6 (Moonshot)' },
  { value: 'google/gemini-3.1-pro', label: 'Gemini 3.1 Pro (Google)' },
  { value: 'custom', label: 'Custom / BYOK' },
];

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
}: {
  onBack: () => void;
  initialTheme?: ThemeName;
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
  const [expandedUI, setExpandedUI] = useState<boolean>(
    () => readLS(LS_KEYS.expanded, 'true') === 'true',
  );
  const [liveDictationPreview, setLiveDictationPreview] = useState<boolean>(false);

  // Sync live dictation preview setting with Python backend
  useBridgeMessage((msg) => {
    if (msg?.type === 'settings/update' && msg.settings) {
      const settings = msg.settings as Record<string, unknown>;
      setLiveDictationPreview(Boolean(settings.live_dictation_preview));
    }
  });

  // Request current settings on mount so we don't default to false every time
  // the settings panel is reopened.
  useEffect(() => {
    sendBridgeMessage({ type: 'settings/get' });
  }, []);

  useEffect(() => writeLS(LS_KEYS.sound, String(soundEnabled)), [soundEnabled]);
  useEffect(() => writeLS(LS_KEYS.expanded, String(expandedUI)), [expandedUI]);

  const toggleLivePreview = () => {
    const next = !liveDictationPreview;
    setLiveDictationPreview(next);
    sendBridgeMessage({ type: 'settings/set', key: 'live_dictation_preview', value: next });
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
        expandedUI={expandedUI}
        setExpandedUI={setExpandedUI}
        liveDictationPreview={liveDictationPreview}
        onToggleLivePreview={toggleLivePreview}
        onBack={onBack}
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
  expandedUI,
  setExpandedUI,
  liveDictationPreview,
  onToggleLivePreview,
  onBack,
}: {
  theme: Theme['panel'];
  activeTheme: ThemeName;
  onApplyTheme: (name: ThemeName) => void;
  soundEnabled: boolean;
  setSoundEnabled: (v: boolean) => void;
  expandedUI: boolean;
  setExpandedUI: (v: boolean) => void;
  liveDictationPreview: boolean;
  onToggleLivePreview: () => void;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<SettingsTab>('general');

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'general', label: 'General' },
    { id: 'dictation', label: 'Dictation' },
    { id: 'agent', label: 'Agent' },
    { id: 'tasks', label: 'Tasks' },
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
            expandedUI={expandedUI}
            setExpandedUI={setExpandedUI}
          />
        )}
        {tab === 'dictation' && (
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
              </div>
            </section>
            <Divider color={theme.border} />
            <InsightsTab theme={theme} />
          </div>
        )}
        {tab === 'agent' && <AgentTab theme={theme} />}
        {tab === 'tasks' && <TasksTab theme={theme} />}
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
  expandedUI,
  setExpandedUI,
}: {
  theme: Theme['panel'];
  activeTheme: ThemeName;
  onApplyTheme: (name: ThemeName) => void;
  soundEnabled: boolean;
  setSoundEnabled: (v: boolean) => void;
  expandedUI: boolean;
  setExpandedUI: (v: boolean) => void;
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
                      : '0 0 0 2px rgba(255,255,255,0.08)',
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
            label="Expanded UI"
            description="Show richer panels and badges"
            value={expandedUI}
            onChange={setExpandedUI}
          />
        </div>
      </section>

      <Divider color={theme.border} />

      <WizPromptSection theme={theme} />

      <Divider color={theme.border} />

      <SupabaseStatusSection theme={theme} />

      <Divider color={theme.border} />

      <section>
        <Label text="Shortcuts" color={theme.textMuted} />
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {SHORTCUTS.map((s) => (
            <div
              key={s.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: 12, color: theme.textMuted }}>
                {s.action}
              </span>
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
                {s.key}
              </kbd>
            </div>
          ))}
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
function AgentTab({ theme }: { theme: Theme['panel'] }) {
  const [systemAccess, setSystemAccess] = useState<SystemAccess>(
    () => (readLS(LS_KEYS.systemAccess, 'system') as SystemAccess),
  );
  useEffect(() => writeLS(LS_KEYS.systemAccess, systemAccess), [systemAccess]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <section>
        <Label text="System access" color={theme.textMuted} />
        <p
          style={{
            fontSize: 11,
            color: theme.textMuted,
            lineHeight: 1.55,
            margin: '8px 0 10px',
          }}
        >
          Controls how much of your system Whiztant can reach and which
          actions require confirmation.
        </p>
        <div style={{ display: 'flex', gap: 6 }}>
          {SYSTEM_ACCESS_VALUES.map((value) => {
            const isActive = systemAccess === value;
            return (
              <button
                key={value}
                onClick={() => setSystemAccess(value)}
                style={{
                  flex: 1,
                  padding: '6px 10px',
                  borderRadius: 7,
                  background: isActive ? `${theme.aiAccent}20` : 'transparent',
                  border: `1px solid ${isActive ? theme.aiAccent : theme.border}`,
                  color: isActive ? theme.text : theme.textMuted,
                  fontSize: 11,
                  fontWeight: isActive ? 600 : 500,
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                  transition: 'background 0.12s, color 0.12s',
                }}
              >
                {value}
              </button>
            );
          })}
        </div>
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <SystemAccessNote
            theme={theme}
            label="Standard"
            desc="Guidance and low-risk actions."
          />
          <SystemAccessNote
            theme={theme}
            label="System"
            desc="Broader task execution with confirmation."
          />
          <SystemAccessNote
            theme={theme}
            label="Deep"
            desc="Maximum reach — review expected."
          />
        </div>
      </section>
    </div>
  );
}

// ─── Tasks tab ─────────────────────────────────────────────
function TasksTab({ theme }: { theme: Theme['panel'] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <section>
        <Label text="Coming soon" color={theme.textMuted} />
        <p
          style={{
            fontSize: 12,
            color: theme.textMuted,
            marginTop: 10,
            lineHeight: 1.55,
          }}
        >
          Tasks settings will include default due times, reminder intervals, and
          carry-over preferences.
        </p>
      </section>
    </div>
  );
}

// ─── WizPrompt (model config + BYOK) section ───────────────
function WizPromptSection({ theme }: { theme: Theme['panel'] }) {
  const [model, setModel] = useState<string>(
    () => readLS(LS_KEYS.wizpromptModel, 'default'),
  );
  const [provider, setProvider] = useState<string>(
    () => readLS(LS_KEYS.wizpromptProvider, ''),
  );
  const [modelName, setModelName] = useState<string>(
    () => readLS(LS_KEYS.wizpromptModelName, ''),
  );
  const [apiKey, setApiKey] = useState<string>(
    () => readLS(LS_KEYS.wizpromptApiKey, ''),
  );
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => writeLS(LS_KEYS.wizpromptModel, model), [model]);
  useEffect(() => writeLS(LS_KEYS.wizpromptProvider, provider), [provider]);
  useEffect(() => writeLS(LS_KEYS.wizpromptModelName, modelName), [modelName]);
  useEffect(() => writeLS(LS_KEYS.wizpromptApiKey, apiKey), [apiKey]);

  const isCustom = model === 'custom';
  const canSave = isCustom
    ? provider.trim().length > 0 && modelName.trim().length > 0 && apiKey.trim().length > 0
    : true;

  const save = () => {
    setStatus('Saved');
    setTimeout(() => setStatus(''), 1500);
  };

  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <Label text="WizPrompt" color={theme.textMuted} />
          <p
            style={{
              fontSize: 11,
              color: theme.textMuted,
              lineHeight: 1.5,
              margin: '6px 0 0',
            }}
          >
            Choose the model that powers prompts and replies.
          </p>
        </div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
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
            Active model
          </div>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={selectStyle(theme)}
          >
            {PREDEFINED_MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {isCustom && (
          <>
            <div
              style={{
                padding: 10,
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                background: 'rgba(0,0,0,0.12)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  color: theme.textMuted,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                Bring Your Own Key
              </div>

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
                  Provider name
                </div>
                <TextField
                  theme={theme}
                  value={provider}
                  onChange={setProvider}
                  placeholder="e.g. openrouter, openai, anthropic"
                />
              </div>

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
                  Model name
                </div>
                <TextField
                  theme={theme}
                  value={modelName}
                  onChange={setModelName}
                  placeholder="exact model ID from the provider"
                />
              </div>

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
                  API key
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    style={{
                      flex: 1,
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
                  <button
                    onClick={() => setShowKey((v) => !v)}
                    title={showKey ? 'Hide key' : 'Show key'}
                    style={{
                      padding: '6px 10px',
                      borderRadius: 6,
                      border: `1px solid ${theme.border}`,
                      background: 'transparent',
                      color: theme.textMuted,
                      cursor: 'pointer',
                      fontSize: 11,
                      fontFamily: 'inherit',
                    }}
                  >
                    {showKey ? '🙈' : '👁'}
                  </button>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                onClick={save}
                disabled={!canSave}
                style={{
                  ...primaryBtn(theme, canSave),
                  minWidth: 88,
                }}
              >
                Save
              </button>
              {status && (
                <span style={{ fontSize: 11, color: theme.textMuted }}>{status}</span>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

// ─── Supabase status section ───────────────────────────────
function SupabaseStatusSection({ theme }: { theme: Theme['panel'] }) {
  const [status, setStatus] = useState<{ configured: boolean; url: string; key_prefix: string } | null>(null);

  useBridgeMessage((msg) => {
    if (msg?.type === 'supabase_status' && msg) {
      setStatus({
        configured: Boolean(msg.configured),
        url: String(msg.url || ''),
        key_prefix: String(msg.key_prefix || ''),
      });
    }
  });

  useEffect(() => {
    sendBridgeMessage({ type: 'request_supabase_status' });
  }, []);

  const reloadEnv = () => {
    sendBridgeMessage({ type: 'reload_env' });
    setTimeout(() => sendBridgeMessage({ type: 'request_supabase_status' }), 500);
  };

  return (
    <section>
      <Label text="Supabase connection" color={theme.textMuted} />
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {status ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: status.configured ? '#4ade80' : '#f87171',
                }}
              />
              <span style={{ fontSize: 12, color: theme.text, fontWeight: 500 }}>
                {status.configured ? 'Connected' : 'Not configured'}
              </span>
            </div>
            {status.url && (
              <div style={{ fontSize: 11, color: theme.textMuted, wordBreak: 'break-all' }}>
                URL: {status.url}
              </div>
            )}
            {status.key_prefix && (
              <div style={{ fontSize: 11, color: theme.textMuted }}>
                Key: {status.key_prefix}
              </div>
            )}
            <button
              onClick={reloadEnv}
              style={{
                marginTop: 4,
                alignSelf: 'flex-start',
                fontSize: 11,
                color: theme.text,
                background: `${theme.aiAccent}15`,
                border: `1px solid ${theme.border}`,
                borderRadius: 6,
                padding: '4px 10px',
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              Reload from .env
            </button>
          </>
        ) : (
          <span style={{ fontSize: 11, color: theme.textMuted }}>Loading…</span>
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
  return theme.accent.includes('#0') || theme.accent.includes('rgba(0')
    ? '#fff'
    : '#0a0a0a';
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
