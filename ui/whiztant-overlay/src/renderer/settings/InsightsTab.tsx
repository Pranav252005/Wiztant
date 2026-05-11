import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { motion } from 'framer-motion';
import type { Theme } from '../shared/themes';
import { useBridgeMessage, sendBridgeMessage } from '../shared/useBridge';

// ─── Types ────────────────────────────────────────────────────
interface InsightsPayload {
  total_words_dictated?: number;
  total_fixes_made?: number;
  total_words_removed?: number;
  dictionary_items_used?: number;
  work_messages?: number;
  ai_prompts?: number;
  personal_messages?: number;
  documents_touched?: number;
  voice_commands?: number;
  other_tasks?: number;
  apps_used?: number;
  current_streak?: number;
  longest_streak?: number;
  today?: Record<string, number>;
}

interface DailyRow {
  date: string;
  activity_score: number;
  [key: string]: number | string;
}

// ─── useCountUp ───────────────────────────────────────────────
function useCountUp(target: number, duration = 1200) {
  const [value, setValue] = useState(0);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef(0);
  const toRef = useRef(target);

  useEffect(() => {
    fromRef.current = value;
    toRef.current = target;
    startRef.current = null;
    let raf = 0;

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const progress = Math.min((ts - startRef.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(fromRef.current + (toRef.current - fromRef.current) * eased);
      setValue(current);
      if (progress < 1) {
        raf = requestAnimationFrame(step);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}

// ─── Gauge (semi-circle SVG) ───────────────────────────────────
function Gauge({ value, max, label, sublabel, color }: {
  value: number;
  max: number;
  label: string;
  sublabel: string;
  color: string;
}) {
  const pct = Math.min(value / max, 1);
  const r = 36;
  const c = 2 * Math.PI * r;
  const dash = c * pct;
  const gap = c - dash;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <svg width="100" height="60" viewBox="0 0 100 60">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" strokeDasharray={`${c / 2} ${c}`} strokeLinecap="round" transform="rotate(180 50 50)" />
        <motion.circle
          cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${gap}`}
          strokeLinecap="round"
          transform="rotate(180 50 50)"
          initial={{ strokeDasharray: `0 ${c}` }}
          animate={{ strokeDasharray: `${dash} ${gap}` }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </svg>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{label}</div>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>{sublabel}</div>
      </div>
    </div>
  );
}

// ─── StatCard ─────────────────────────────────────────────────
function StatCard({ value, label, sublabel, theme, delay = 0 }: {
  value: number;
  label: string;
  sublabel?: string;
  theme: Theme['panel'];
  delay?: number;
}) {
  const animated = useCountUp(value);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${theme.border}`,
        borderRadius: 12,
        padding: '16px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 700, color: theme.text, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>
        {animated.toLocaleString()}
      </div>
      <div style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
        {label}
      </div>
      {sublabel && (
        <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 2 }}>{sublabel}</div>
      )}
    </motion.div>
  );
}

// ─── UsageBar ─────────────────────────────────────────────────
function UsageBar({ label, value, total, color, theme, delay = 0 }: {
  label: string;
  value: number;
  total: number;
  color: string;
  theme: Theme['panel'];
  delay?: number;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay }}
      style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: theme.textMuted }}>
        <span>{label}</span>
        <span>{value.toLocaleString()}</span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay: delay + 0.15, ease: 'easeOut' }}
          style={{ height: '100%', borderRadius: 4, background: color }}
        />
      </div>
    </motion.div>
  );
}

// ─── Heatmap ──────────────────────────────────────────────────
function Heatmap({ data, theme }: { data: DailyRow[]; theme: Theme['panel'] }) {
  // Build a 7×20 grid (≈ 5 months) sized to fit without horizontal scroll
  const weeks = 20;
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  // Normalize activity_score to 0..4 for color intensity
  const maxScore = Math.max(1, ...data.map((d) => d.activity_score || 0));
  const colorScale = [
    'rgba(255,255,255,0.04)',
    'rgba(255,255,255,0.12)',
    'rgba(255,255,255,0.28)',
    'rgba(255,255,255,0.50)',
    theme.aiAccent,
  ];

  const grid: (DailyRow | null)[][] = Array.from({ length: 7 }, () => Array(weeks).fill(null));
  const today = new Date();
  for (let w = weeks - 1; w >= 0; w--) {
    for (let d = 6; d >= 0; d--) {
      const offset = (weeks - 1 - w) * 7 + (6 - d);
      const date = new Date(today);
      date.setDate(date.getDate() - offset);
      const iso = date.toISOString().slice(0, 10);
      const row = data.find((r) => r.date === iso);
      grid[d][w] = row || null;
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <div style={{ display: 'flex', gap: 2, paddingBottom: 4 }}>
        {/* Day labels */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginRight: 4 }}>
          {days.map((d) => (
            <div key={d} style={{ fontSize: 8, color: theme.textMuted, height: 10, lineHeight: '10px', width: 20, textAlign: 'right', paddingRight: 4 }}>
              {d.slice(0, 1)}
            </div>
          ))}
        </div>
        {/* Grid */}
        <div style={{ display: 'flex', gap: 2 }}>
          {Array.from({ length: weeks }, (_, w) => (
            <div key={w} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {Array.from({ length: 7 }, (_, d) => {
                const row = grid[d][w];
                const score = row?.activity_score || 0;
                const level = Math.min(4, Math.floor((score / maxScore) * 4));
                return (
                  <motion.div
                    key={d}
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.25, delay: (w * 7 + d) * 0.003 }}
                    title={row ? `${row.date}: ${score} activity` : ''}
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: colorScale[level],
                      cursor: row ? 'pointer' : 'default',
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, justifyContent: 'flex-end' }}>
        <span style={{ fontSize: 9, color: theme.textMuted }}>Less</span>
        {colorScale.map((c, i) => (
          <div key={i} style={{ width: 10, height: 10, borderRadius: 2, background: c }} />
        ))}
        <span style={{ fontSize: 9, color: theme.textMuted }}>More</span>
      </div>
    </motion.div>
  );
}

// ─── InsightsTab ──────────────────────────────────────────────
export default function InsightsTab({ theme }: { theme: Theme['panel'] }) {
  const [insights, setInsights] = useState<InsightsPayload>({});
  const [subTab] = useState<'usage'>('usage');
  const [daily, setDaily] = useState<DailyRow[]>([]);

  // Listen for WebSocket insights updates
  useBridgeMessage((msg) => {
    if (msg?.type === 'insights_update' && msg.payload) {
      setInsights(msg.payload as InsightsPayload);
    }
  });

  // Load initial data from localStorage fallback + request fresh data
  useEffect(() => {
    try {
      const raw = localStorage.getItem('whiztant.insights');
      if (raw) setInsights(JSON.parse(raw));
    } catch {
      /* noop */
    }
    // Request current insights from Python on mount
    sendBridgeMessage({ type: 'request_insights' });
  }, []);

  // Periodic polling fallback (every 3s) to ensure real-time sync
  useEffect(() => {
    const interval = window.setInterval(() => {
      sendBridgeMessage({ type: 'request_insights' });
    }, 3000);
    return () => window.clearInterval(interval);
  }, []);

  // Persist to localStorage for quick reloads
  useEffect(() => {
    try {
      localStorage.setItem('whiztant.insights', JSON.stringify(insights));
    } catch {
      /* noop */
    }
  }, [insights]);

  // Build demo daily data if none (all zeros / empty heatmap)
  useEffect(() => {
    if (daily.length === 0) {
      const rows: DailyRow[] = [];
      const today = new Date();
      for (let i = 0; i < 180; i++) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        rows.push({
          date: d.toISOString().slice(0, 10),
          activity_score: 0,
          words_dictated: 0,
          fixes_made: 0,
        });
      }
      setDaily(rows);
    }
  }, [daily.length]);

  const totalWords = insights.total_words_dictated || 0;
  const totalFixes = insights.total_fixes_made || 0;
  const wordsRemoved = insights.total_words_removed || 0;
  const currentStreak = insights.current_streak || 0;
  const longestStreak = insights.longest_streak || 0;

  // Desktop usage breakdown
  const usageItems = [
    { label: 'Work messages', value: insights.work_messages || 0, color: '#4A9B8E' },
    { label: 'AI prompts', value: insights.ai_prompts || 0, color: '#4A9B8E' },
    { label: 'Personal messages', value: insights.personal_messages || 0, color: '#4A9B8E' },
    { label: 'Documents', value: insights.documents_touched || 0, color: '#6BB3A8' },
    { label: 'Voice commands', value: insights.voice_commands || 0, color: '#8ECDC4' },
    { label: 'Other tasks', value: insights.other_tasks || 0, color: '#8ECDC4' },
  ];
  const usageTotal = usageItems.reduce((s, i) => s + i.value, 0) || 1;

  const accent = theme.aiAccent;

  const openStreakPanel = () => {
    try {
      if (window.api?.openStreakPanel) {
        window.api.openStreakPanel({
          currentStreak,
          longestStreak,
          daily,
        });
      }
    } catch {
      /* noop */
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, overflowY: 'auto', minHeight: 0 }}>
      {subTab === 'usage' && (
        <>
          {/* Top stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <StatCard
              value={totalWords > 0 ? Math.round(totalWords / Math.max(1, (insights.today?.words_dictated || 1))) : 0}
              label="Words / min"
              sublabel="Rolling average"
              theme={theme}
              delay={0}
            />
            <StatCard
              value={totalFixes}
              label="Fixes made"
              sublabel={`${wordsRemoved.toLocaleString()} words removed`}
              theme={theme}
              delay={0.08}
            />
            <StatCard
              value={totalWords}
              label="Total words dictated"
              sublabel={currentStreak > 0 ? `${currentStreak} day streak` : 'Start dictating to build your streak'}
              theme={theme}
              delay={0.16}
            />
          </div>

          {/* Desktop usage + Streak */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10 }}>
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.24 }}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${theme.border}`,
                borderRadius: 12,
                padding: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Desktop usage</span>
                <span style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Total apps used | {(insights.apps_used || 0).toLocaleString()}
                </span>
              </div>
              {usageItems.map((item, i) => (
                <UsageBar
                  key={item.label}
                  label={item.label}
                  value={item.value}
                  total={usageTotal}
                  color={item.color}
                  theme={theme}
                  delay={0.3 + i * 0.06}
                />
              ))}
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.32 }}
              onClick={openStreakPanel}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${theme.border}`,
                borderRadius: 12,
                padding: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                cursor: 'pointer',
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = theme.aiAccent;
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = theme.border;
                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>
                  {currentStreak > 0 ? `${currentStreak} day streak` : 'Start your streak'}
                </span>
                <span style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Longest streak | {longestStreak} days
                </span>
              </div>
              <Heatmap data={daily} theme={theme} />
            </motion.div>
          </div>

          {/* Percentile badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.5 }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '10px 14px',
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${theme.border}`,
              borderRadius: 10,
            }}
          >
            <Gauge
              value={totalWords > 0 ? Math.min(100, Math.round(totalWords / 100)) : 0}
              max={100}
              label={totalWords > 0 ? `Top ${Math.max(1, Math.min(99, 100 - Math.round(totalWords / 100)))}%` : 'Top —%'}
              sublabel="of Wiztant users"
              color={accent}
            />
          </motion.div>
        </>
      )}


    </div>
  );
}
