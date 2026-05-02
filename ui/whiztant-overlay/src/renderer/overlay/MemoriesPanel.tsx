import { useMemo, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import type { Theme } from '../shared/themes';
import type { DictationMemory } from '../shared/ipc';

export type { DictationMemory };

type Props = {
  theme: Theme['panel'];
  memories: DictationMemory[];
  filter?: DictationMemory['mode'] | 'all';
  onFilterChange?: (filter: DictationMemory['mode'] | 'all') => void;
};

const MODE_LABEL: Record<DictationMemory['mode'], string> = {
  dictation: 'Dictation',
  agent: 'Agent',
  task: 'Task',
  bg_agent: 'Bg Agent',
};

const MODE_COLOR: Record<DictationMemory['mode'], string> = {
  dictation: '#c0c1ff',
  agent: '#4cd7f6',
  task: '#d0bcff',
  bg_agent: '#C4956A',
};

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const timeStr = new Intl.DateTimeFormat([], {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
  if (isToday) return `Today ${timeStr}`;
  return new Intl.DateTimeFormat([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export default function MemoriesPanel({ theme, memories, filter: filterProp, onFilterChange }: Props) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const filter = filterProp ?? 'all';
  const setFilter = onFilterChange ?? (() => {});

  const filtered = useMemo(() => {
    if (filter === 'all') return memories;
    return memories.filter((m) => m.mode === filter);
  }, [memories, filter]);

  const handleCopy = async (text: string, id: string) => {
    try {
      await window.api.writeClipboard(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1200);
    } catch {
      // ignore
    }
  };

  const handleDoubleClick = useCallback((mem: DictationMemory) => {
    void window.api.openMemoryPanel(mem);
  }, []);

  const filters: Array<{ key: DictationMemory['mode'] | 'all'; label: string }> = [
    { key: 'all', label: 'All' },
    { key: 'dictation', label: 'Dictation' },
    { key: 'agent', label: 'Agent' },
    { key: 'task', label: 'Task' },
  ];

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: '12px 12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {filters.map((f) => {
          const active = filter === f.key;
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              style={{
                padding: '4px 10px',
                borderRadius: 8,
                border: `1px solid ${active ? theme.aiAccent : theme.border}`,
                background: active ? `${theme.aiAccent}22` : 'transparent',
                color: active ? theme.aiAccent : theme.textMuted,
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'all 0.14s',
              }}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {/* Memory list */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          overflowY: 'auto',
        }}
      >
        {filtered.length === 0 ? (
          <div
            style={{
              padding: 24,
              color: theme.textMuted,
              fontSize: 12,
              textAlign: 'center',
              lineHeight: 1.6,
            }}
          >
            {memories.length === 0
              ? 'No memories yet. Start dictating with F9 and your prompts will appear here.'
              : 'No memories match this filter.'}
          </div>
        ) : (
          filtered.map((mem) => (
            <motion.div
              key={mem.id}
              layout
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              onClick={() => handleCopy(mem.final_text, mem.id)}
              onDoubleClick={() => handleDoubleClick(mem)}
              title="Click to copy • Double-click to edit"
              style={{
                padding: '10px 12px',
                borderRadius: 12,
                border: `1px solid ${theme.border}`,
                background: theme.inputBg,
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                transition: 'background 0.12s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = `${theme.aiAccent}0d`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = theme.inputBg;
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    color: MODE_COLOR[mem.mode],
                  }}
                >
                  {MODE_LABEL[mem.mode]}
                </span>
                <span style={{ fontSize: 10, color: theme.textMuted }}>
                  {formatTime(mem.timestamp)}
                </span>
              </div>

              <div
                style={{
                  fontSize: 12,
                  color: theme.text,
                  lineHeight: 1.45,
                  wordBreak: 'break-word',
                }}
              >
                {mem.final_text}
              </div>

              {mem.original_text !== mem.final_text && (
                <div
                  style={{
                    fontSize: 11,
                    color: theme.textMuted,
                    lineHeight: 1.4,
                    fontStyle: 'italic',
                  }}
                >
                  Heard: "{mem.original_text}"
                </div>
              )}

              {copiedId === mem.id && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: theme.aiAccent,
                    alignSelf: 'flex-end',
                  }}
                >
                  Copied ✓
                </motion.div>
              )}
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
