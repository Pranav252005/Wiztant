import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage, useBridgeMessage } from '../shared/useBridge';
import CustomDropdown from '../shared/CustomDropdown';

type ProcessStatus = 'idle' | 'active' | 'completed' | 'error';

type Props = {
  theme: Theme['panel'];
  onProcessChange?: (status: ProcessStatus) => void;
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
    id: 'anthropic/claude-sonnet-4.6',
    label: 'Claude Sonnet 4.6',
    description: 'Best overall quality for tuning tasks',
  },
  {
    id: 'anthropic/claude-haiku-4.5',
    label: 'Claude Haiku 4.5',
    description: 'Fast and cost-effective for tuning iterations',
  },
  {
    id: 'openai/gpt-5.5',
    label: 'GPT 5.5',
    description: 'Top-tier general reasoning and tuning',
  },
  {
    id: 'openai/gpt-5.4',
    label: 'GPT 5.4',
    description: 'Strong general-purpose tuning model',
  },
  {
    id: 'openai/gpt-5.5-mini',
    label: 'GPT 5.5 mini',
    description: 'Fast and reliable general-purpose tuning',
  },
  {
    id: 'openai/gpt-5.4-mini',
    label: 'GPT 5.4 mini',
    description: 'Efficient tuning for smaller tasks',
  },
  {
    id: 'x-ai/grok-4.3',
    label: 'Grok 4.3',
    description: 'Strong reasoning with tool-use capabilities',
  },
  {
    id: 'google/gemini-3.1-pro-preview',
    label: 'Gemini 3.1 Pro',
    description: 'Excellent multimodal and long-context tuning',
  },
  {
    id: 'google/gemini-3-flash-preview',
    label: 'Gemini 3 Flash',
    description: 'Fast and efficient for batch tuning tasks',
  },
  {
    id: 'qwen/qwen3.5-plus-20260420',
    label: 'Qwen 3.5 Plus',
    description: 'Strong coding and reasoning for technical tuning',
  },
  {
    id: 'moonshotai/kimi-k2.6',
    label: 'Kimi K2.6',
    description: 'Excellent long-context understanding',
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

export default function TuneHubPanel({ theme, onProcessChange }: Props) {
  const [stats, setStats] = useState<TuneStats | null>(null);
  const [tunes, setTunes] = useState<TuneItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [learnTask, setLearnTask] = useState('');

  useEffect(() => {
    onProcessChange?.(loading ? 'active' : 'idle');
  }, [loading]);
  const [learnFeature, setLearnFeature] = useState<'reprompt' | 'dictation' | 'agent'>('reprompt');
  const [learnResult, setLearnResult] = useState<{ success: boolean; message: string } | null>(null);
  const [settings, setSettings] = useState(loadSettings);

  const refresh = useCallback(() => {
    sendBridgeMessage({ type: 'tunehub/stats' });
    sendBridgeMessage({ type: 'tunehub/list' });
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
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Tune Hub</div>
      </div>

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <StatCard label="Tunes" value={stats?.total_tunes ?? 0} theme={theme} />
        <StatCard label="Active" value={stats?.active_tunes ?? 0} theme={theme} />
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
          {(['reprompt', 'dictation', 'agent'] as const).map((f) => {
            const isAgent = f === 'agent';
            const active = learnFeature === f;
            return (
              <button
                key={f}
                onClick={isAgent ? undefined : () => setLearnFeature(f)}
                disabled={isAgent}
                style={{
                  padding: '6px 12px',
                  borderRadius: 8,
                  border: `1px solid ${active && !isAgent ? theme.aiAccent : theme.border}`,
                  background: active && !isAgent ? `${theme.aiAccent}26` : 'transparent',
                  color: isAgent ? theme.textMuted : active ? theme.text : theme.textMuted,
                  fontSize: 12,
                  fontWeight: active ? 700 : 500,
                  fontFamily: 'inherit',
                  cursor: isAgent ? 'not-allowed' : 'pointer',
                  opacity: isAgent ? 0.5 : 1,
                  transition: 'all 0.14s',
                }}
              >
                {isAgent ? `${FEATURE_LABELS[f]} (Soon)` : FEATURE_LABELS[f]}
              </button>
            );
          })}
        </div>
        <textarea
          value={learnTask}
          onChange={(e) => {
            setLearnTask(e.target.value);
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(e.target.scrollHeight, 240)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleLearn();
            }
          }}
          placeholder={`Describe what you want to tune (e.g. "${
            learnFeature === 'reprompt'
              ? 'Optimize my coding prompts'
              : learnFeature === 'dictation'
              ? 'Correct my project names'
              : 'Automate my morning checklist'
          }")`}
          rows={1}
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
            resize: 'none',
            overflowY: 'auto',
            overflowWrap: 'break-word',
            whiteSpace: 'pre-wrap',
            minHeight: 36,
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

      {/* Compact model selector */}
      <CustomDropdown
        value={settings.model}
        onChange={(v) => handleModelChange(v)}
        options={TUNE_MODELS.map((m) => ({ value: m.id, label: m.label }))}
        theme={theme}
        label="Tuning Model"
      />

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
