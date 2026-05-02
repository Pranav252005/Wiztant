import { useEffect, useState, type CSSProperties } from 'react';
import { motion } from 'framer-motion';
import { themes, defaultTheme } from '../shared/themes';
import type { ThemeName } from '../shared/ipc';

interface DailyRow {
  date: string;
  activity_score: number;
  words_dictated?: number;
  fixes_made?: number;
  [key: string]: number | string | undefined;
}

function parseStreakFromHash(): { currentStreak: number; longestStreak: number; daily: DailyRow[] } | null {
  try {
    const hash = window.location.hash || '';
    const [, query = ''] = hash.split('?');
    const params = new URLSearchParams(query);
    const raw = params.get('data');
    if (!raw) return null;
    return JSON.parse(decodeURIComponent(raw)) as { currentStreak: number; longestStreak: number; daily: DailyRow[] };
  } catch {
    return null;
  }
}

export default function StreakPanel() {
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const theme = themes[themeName].panel;
  const [data, setData] = useState(() => parseStreakFromHash());

  useEffect(() => {
    if (window.api?.onThemeChanged) {
      window.api.onThemeChanged((name) => setThemeName(name));
    }
  }, []);

  if (!data) {
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: theme.bg,
          color: theme.textMuted,
          border: `1px solid ${theme.border}`,
          borderRadius: 16,
          fontFamily: 'Geist, "Segoe UI", sans-serif',
        }}
      >
        No streak data.
      </div>
    );
  }

  const { currentStreak, longestStreak, daily } = data;
  const weeks = 20;
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const maxScore = Math.max(1, ...daily.map((d) => d.activity_score || 0));
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
      const row = daily.find((r) => r.date === iso);
      grid[d][w] = row || null;
    }
  }

  const dragRegionStyle: CSSProperties & { WebkitAppRegion: 'drag' } = {
    WebkitAppRegion: 'drag',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    background: theme.headerBg,
    borderBottom: `1px solid ${theme.border}`,
    flexShrink: 0,
  };
  const noDragButtonStyle: CSSProperties & { WebkitAppRegion: 'no-drag' } = {
    WebkitAppRegion: 'no-drag',
    background: 'transparent',
    color: theme.textMuted,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '6px 10px',
    fontSize: 11,
    cursor: 'pointer',
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: theme.bg,
        color: theme.text,
        border: `1px solid ${theme.border}`,
        borderRadius: 16,
        overflow: 'hidden',
        fontFamily: 'Geist, "Segoe UI", sans-serif',
      }}
    >
      <div style={dragRegionStyle}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: theme.text }}>Streak Details</div>
          <div style={{ fontSize: 10, color: theme.textMuted }}>
            {currentStreak} day current · {longestStreak} day longest
          </div>
        </div>
        <button type="button" onClick={() => window.close()} style={noDragButtonStyle}>
          Close
        </button>
      </div>

      <div
        style={{
          flex: 1,
          padding: 14,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {/* Large heatmap */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 11, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Activity Heatmap
          </div>
          <div style={{ display: 'flex', gap: 2, paddingBottom: 4 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginRight: 4 }}>
              {days.map((d) => (
                <div key={d} style={{ fontSize: 8, color: theme.textMuted, height: 12, lineHeight: '12px', width: 24, textAlign: 'right', paddingRight: 4 }}>
                  {d.slice(0, 1)}
                </div>
              ))}
            </div>
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
                          borderRadius: 3,
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
        </div>

        {/* Stats summary */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
          }}
        >
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${theme.border}`,
              borderRadius: 12,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Current Streak</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: theme.text }}>{currentStreak} days</div>
          </div>
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${theme.border}`,
              borderRadius: 12,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div style={{ fontSize: 10, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Longest Streak</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: theme.text }}>{longestStreak} days</div>
          </div>
        </div>

        {/* Active days list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 11, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Recent Activity
          </div>
          {daily
            .filter((d) => d.activity_score > 0)
            .slice(0, 14)
            .map((row, i) => (
              <motion.div
                key={row.date}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: i * 0.04 }}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 10px',
                  borderRadius: 8,
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${theme.border}`,
                }}
              >
                <span style={{ fontSize: 11, color: theme.text }}>{row.date}</span>
                <span style={{ fontSize: 11, color: theme.textMuted }}>{row.activity_score} activity</span>
              </motion.div>
            ))}
          {daily.filter((d) => d.activity_score > 0).length === 0 && (
            <div style={{ fontSize: 11, color: theme.textMuted, textAlign: 'center', padding: 20 }}>
              No activity yet. Start using Wiztant to build your streak!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
