import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage, useBridgeMessage } from '../shared/useBridge';

type Props = {
  theme: Theme['panel'];
};

type TuneStats = {
  total_tunes: number;
  active_tunes: number;
  features_with_tunes: string[];
};

type TuneItem = {
  tune_id: string;
  feature_name: string;
  task_signature: string;
  status: string;
  quality_score: number;
  version: number;
  created_at: string;
};

type CreditInfo = {
  available: number;
  consumed: number;
  reserved: number;
};

const FEATURE_LABELS: Record<string, string> = {
  reprompt: 'RePrompt',
  dictation: 'Dictation',
  agent: 'Agent',
};

const FEATURE_DESC: Record<string, string> = {
  reprompt: 'Learns to optimize your prompts for better AI responses',
  dictation: 'Learns your speech patterns and auto-corrects transcription',
  agent: 'Learns automation recipes for apps you use',
};

const TUNE_MODELS: { id: string; label: string; description: string }[] = [
  {
    id: 'anthropic/claude-sonnet-4-20250514',
    label: 'Claude Sonnet 4',
    description: 'Best overall quality for tuning tasks',
  },
  {
    id: 'thudm/glm-4-plus',
    label: 'GLM-4 Plus',
    description: 'Strong reasoning, efficient for iterative tuning',
  },
  {
    id: 'moonshotai/kimi-k2.5',
    label: 'Kimi K2.5',
    description: 'Excellent long-context understanding',
  },
  {
    id: 'openai/gpt-4o',
    label: 'GPT-4o',
    description: 'Fast and reliable general-purpose tuning',
  },
];

const SETTINGS_KEY = 'tunehub_settings';

function loadSettings(): { model: string } {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.model && TUNE_MODELS.some((m) => m.id === parsed.model)) {
        return { model: parsed.model };
      }
    }
  } catch {
    // ignore
  }
  return { model: TUNE_MODELS[0].id };
}

function saveSettings(settings: { model: string }) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

export default function TuneHubPanel({ theme }: Props) {
  const [stats, setStats] = useState<TuneStats | null>(null);
  const [tunes, setTunes] = useState<TuneItem[]>([]);
  const [credits, setCredits] = useState<CreditInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [learnTask, setLearnTask] = useState('');
  const [learnFeature, setLearnFeature] = useState<'reprompt' | 'dictation' | 'agent'>('reprompt');
  const [learnResult, setLearnResult] = useState<{ success: boolean; message: string } | null>(null);
  const [settings, setSettings] = useState(loadSettings);
  const [showSettings, setShowSettings] = useState(false);

  const refresh = useCallback(() => {
    sendBridgeMessage({ type: 'tunehub/stats' });
    sendBridgeMessage({ type: 'tunehub/list' });
    sendBridgeMessage({ type: 'tunehub/credits' });
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    sendBridgeMessage({ type: 'tunehub/get_settings' });
  }, []);

  useBridgeMessage((msg) => {
    if (msg.type === 'tunehub/stats') {
      setStats((msg.stats as TuneStats) ?? null);
    }
    if (msg.type === 'tunehub/list') {
      setTunes((msg.tunes as TuneItem[]) ?? []);
    }
    if (msg.type === 'tunehub/credits') {
      setCredits((msg.credits as CreditInfo) ?? null);
    }
    if (msg.type === 'tunehub/learn_result') {
      setLoading(false);
      setLearnResult({
        success: Boolean(msg.success),
        message: String(msg.message ?? ''),
      });
      if (msg.success) {
        refresh();
      }
    }
    if (msg.type === 'tunehub/settings') {
      const incoming = msg.settings as { model?: string } | undefined;
      if (incoming?.model && TUNE_MODELS.some((m) => m.id === incoming.model)) {
        setSettings({ model: incoming.model });
        saveSettings({ model: incoming.model });
      }
    }
  });

  const handleLearn = () => {
    if (!learnTask.trim()) return;
    setLoading(true);
    setLearnResult(null);
    sendBridgeMessage({
      type: 'tunehub/learn',
      feature_name: learnFeature,
      task: learnTask.trim(),
    });
  };

  const handleModelChange = (modelId: string) => {
    const next = { model: modelId };
    setSettings(next);
    saveSettings(next);
    sendBridgeMessage({ type: 'tunehub/set_settings', settings: next });
  };

  const selectedModel = TUNE_MODELS.find((m) => m.id === settings.model) ?? TUNE_MODELS[0];

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 12px',
    borderRadius: 8,
    border: `1px solid ${active ? theme.aiAccent : theme.border}`,
    background: active ? `${theme.aiAccent}26` : 'transparent',
    color: active ? theme.text : theme.textMuted,
    fontSize: 12,
    fontWeight: active ? 700 : 500,
    fontFamily: 'inherit',
    cursor: 'pointer',
    transition: 'all 0.14s',
  });

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: '12px 12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Tune Hub</div>
        <button
          onClick={() => setShowSettings((s) => !s)}
          style={{
            padding: '4px 10px',
            borderRadius: 6,
            border: `1px solid ${theme.border}`,
            background: 'transparent',
            color: theme.textMuted,
            fontSize: 11,
            fontFamily: 'inherit',
            cursor: 'pointer',
          }}
        >
          {showSettings ? 'Close' : 'Settings'}
        </button>
      </div>

      {/* Settings panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              border: `1px solid ${theme.border}`,
              borderRadius: 12,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              overflow: 'hidden',
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>Tuning Model</div>
            <div style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.4 }}>
              Select the AI model used for quality scoring and optimization during tuning.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {TUNE_MODELS.map((m) => {
                const active = m.id === settings.model;
                return (
                  <button
                    key={m.id}
                    onClick={() => handleModelChange(m.id)}
                    style={{
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: 8,
                      border: `1px solid ${active ? theme.aiAccent : theme.border}`,
                      background: active ? `${theme.aiAccent}15` : 'transparent',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 600, color: active ? theme.aiAccent : theme.text }}>
                      {m.label}
                    </div>
                    <div style={{ fontSize: 10, color: theme.textMuted, marginTop: 2 }}>
                      {m.description}
                    </div>
                  </button>
                );
              })}
            </div>
            <div
              style={{
                fontSize: 10,
                color: theme.textMuted,
                padding: '6px 8px',
                borderRadius: 6,
                background: `${theme.aiAccent}08`,
              }}
            >
              Active: <strong style={{ color: theme.aiAccent }}>{selectedModel.label}</strong>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <StatCard label="Tunes" value={stats?.total_tunes ?? 0} theme={theme} />
        <StatCard label="Active" value={stats?.active_tunes ?? 0} theme={theme} />
        <StatCard label="Credits" value={credits?.available ?? 0} theme={theme} />
      </div>

      {/* Learn section */}
      <div
        style={{
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Learn a Tune</div>
        <div style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.4 }}>
          {FEATURE_DESC[learnFeature]}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['reprompt', 'dictation', 'agent'] as const).map((f) => (
            <button key={f} onClick={() => setLearnFeature(f)} style={btnStyle(learnFeature === f)}>
              {FEATURE_LABELS[f]}
            </button>
          ))}
        </div>
        <input
          value={learnTask}
          onChange={(e) => setLearnTask(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleLearn();
          }}
          placeholder={`Describe what you want to tune (e.g. "${
            learnFeature === 'reprompt'
              ? 'Optimize my coding prompts'
              : learnFeature === 'dictation'
              ? 'Correct my project names'
              : 'Automate my morning checklist'
          }")`}
          style={{
            width: '100%',
            padding: '8px 10px',
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
            background: theme.inputBg,
            color: theme.text,
            fontSize: 12,
            fontFamily: 'inherit',
            outline: 'none',
          }}
        />
        <button
          onClick={handleLearn}
          disabled={loading || !learnTask.trim()}
          style={{
            width: '100%',
            padding: '8px 0',
            borderRadius: 8,
            border: 'none',
            background: loading ? theme.border : theme.aiAccent,
            color: '#07070f',
            fontSize: 12,
            fontWeight: 700,
            fontFamily: 'inherit',
            cursor: loading || !learnTask.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !learnTask.trim() ? 0.6 : 1,
          }}
        >
          {loading ? 'Learning…' : 'Start Learning'}
        </button>
        {learnResult && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              fontSize: 11,
              color: learnResult.success ? '#4ade80' : '#f87171',
              padding: '6px 8px',
              borderRadius: 6,
              background: learnResult.success ? 'rgba(74,222,128,0.08)' : 'rgba(248,113,113,0.08)',
            }}
          >
            {learnResult.message}
          </motion.div>
        )}
      </div>

      {/* Active tunes list */}
      {tunes.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Your Tunes</div>
          {tunes.map((tune) => (
            <div
              key={tune.tune_id}
              style={{
                border: `1px solid ${theme.border}`,
                borderRadius: 10,
                padding: 10,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>
                  {FEATURE_LABELS[tune.feature_name] ?? tune.feature_name}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: tune.status === 'deployed' ? 'rgba(74,222,128,0.15)' : 'rgba(196,149,106,0.15)',
                    color: tune.status === 'deployed' ? '#4ade80' : '#C4956A',
                    textTransform: 'uppercase',
                  }}
                >
                  {tune.status}
                </span>
              </div>
              <div style={{ fontSize: 11, color: theme.textMuted, wordBreak: 'break-all' }}>
                {tune.task_signature}
              </div>
              <div style={{ fontSize: 10, color: theme.textMuted, display: 'flex', gap: 12 }}>
                <span>Quality: {Math.round((tune.quality_score ?? 0) * 100)}%</span>
                <span>v{tune.version}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  theme,
}: {
  label: string;
  value: number | string;
  theme: Theme['panel'];
}) {
  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        borderRadius: 10,
        padding: '10px 8px',
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ fontSize: 18, fontWeight: 800, color: theme.aiAccent }}>{value}</div>
      <div style={{ fontSize: 10, fontWeight: 600, color: theme.textMuted, textTransform: 'uppercase' }}>
        {label}
      </div>
    </div>
  );
}
