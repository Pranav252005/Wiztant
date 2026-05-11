import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { defaultTheme, themes } from '../shared/themes';
import type { ThemeName, DictationMemory, DictationMemoryMode } from '../shared/ipc';
import { sendBridgeMessage, useBridgeMessage } from '../shared/useBridge';

const MODE_LABEL: Record<DictationMemoryMode, string> = {
  dictation: 'Dictation',
  agent: 'Agent',
  task: 'Task',
  bg_agent: 'Bg Agent',
  reprompt: 'RePrompt',
};

const MODE_COLOR: Record<DictationMemoryMode, string> = {
  dictation: '#c0c1ff',
  agent: '#4cd7f6',
  task: '#d0bcff',
  bg_agent: '#C4956A',
  reprompt: '#d0bcff',
};

function parseMemoryFromHash(): DictationMemory | null {
  try {
    const hash = window.location.hash || '';
    const [, query = ''] = hash.split('?');
    const params = new URLSearchParams(query);
    const raw = params.get('memory');
    if (!raw) return null;
    return JSON.parse(decodeURIComponent(raw)) as DictationMemory;
  } catch {
    return null;
  }
}

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

export default function MemoryPanel() {
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const theme = themes[themeName].panel;
  const [memory, setMemory] = useState<DictationMemory | null>(() => parseMemoryFromHash());
  const [text, setText] = useState(memory?.final_text || '');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [sessionId] = useState(() => {
    const fromMemory = parseMemoryFromHash()?.session_id;
    return fromMemory || `preview-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  });
  const editTimeoutRef = useRef<number | null>(null);

  useBridgeMessage((msg) => {
    if (msg?.type === 'dictation_preview/optimized' && memory) {
      const optimized = String(msg.text ?? '');
      if (optimized) {
        setText(optimized);
        setIsOptimizing(false);
        // Notify correction pipeline of optimization
        sendBridgeMessage({
          type: 'correction_capture/optimize',
          session_id: sessionId,
          optimized,
        });
      }
    }
    if (msg?.type === 'dictation_memories/update' && memory) {
      const list = (msg.memories as DictationMemory[] | undefined) ?? [];
      const updated = list.find((m) => m.id === memory.id);
      if (updated) {
        setMemory(updated);
        setText(updated.final_text);
      }
    }
  });

  useEffect(() => {
    window.api.onThemeChanged((name) => setThemeName(name));
  }, []);

  useEffect(() => {
    const next = parseMemoryFromHash();
    setMemory(next);
    setText(next?.final_text || '');
  }, []);

  // ── Undo Hook: notify Python when preview opens/closes ──
  useEffect(() => {
    sendBridgeMessage({
      type: 'correction_capture/open',
      session_id: sessionId,
      original_text: memory?.original_text || '',
      stt_text: memory?.final_text || '',
    });
    return () => {
      sendBridgeMessage({ type: 'correction_capture/close', session_id: sessionId });
    };
  }, [sessionId, memory]);

  // ── Undo Hook: capture Ctrl+Z as undo ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        sendBridgeMessage({
          type: 'correction_capture/undo',
          session_id: sessionId,
          new_text: text,
        });
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [sessionId, text]);

  const save = async () => {
    if (!memory?.id || !text.trim()) return;
    setStatus('saving');
    sendBridgeMessage({
      type: 'dictation_memories/edit',
      id: memory.id,
      final_text: text.trim(),
      original_text: memory.original_text,
    });
    try {
      await window.api.writeClipboard(text.trim());
    } catch {
      // ignore
    }
    setStatus('saved');
    window.close();
  };

  const optimize = () => {
    if (!text.trim() || isOptimizing) return;
    setIsOptimizing(true);
    sendBridgeMessage({ type: 'dictation_preview/optimize', text: text.trim(), session_id: sessionId });
  };

  const copy = async () => {
    if (!text.trim()) return;
    await window.api.writeClipboard(text.trim());
    sendBridgeMessage({ type: 'correction_capture/copy', session_id: sessionId });
  };

  const del = () => {
    if (!memory?.id) return;
    sendBridgeMessage({ type: 'dictation_memories/delete', id: memory.id });
    window.close();
  };

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

  if (!memory) {
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
        No memory selected.
      </div>
    );
  }

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
          <div style={{ fontSize: 12, fontWeight: 700, color: theme.text }}>Memory Panel</div>
          <div style={{ fontSize: 10, color: theme.textMuted }}>Edit your dictation memory</div>
        </div>
        <button type="button" onClick={() => void copy()} style={noDragButtonStyle}>
          Copy
        </button>
        <button type="button" onClick={() => window.close()} style={noDragButtonStyle}>
          Close
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 12, minHeight: 0, flex: 1, overflowY: 'auto' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            padding: '10px 12px',
            borderRadius: 12,
            border: `1px solid ${theme.border}`,
            background: `${theme.aiAccent}10`,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 10,
                color: MODE_COLOR[memory.mode],
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              {MODE_LABEL[memory.mode]}
            </div>
            <div style={{ fontSize: 11, color: theme.text }}>{formatTime(memory.timestamp)}</div>
          </div>
          <div style={{ fontSize: 10, color: theme.textMuted, flexShrink: 0 }}>
            {text.length} chars
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            border: `1px solid ${theme.border}`,
            borderRadius: 12,
            background: theme.inputBg,
            overflow: 'visible',
          }}
        >
          {memory.original_text !== text && memory.original_text && (
            <div
              style={{
                padding: '10px 12px',
                borderBottom: `1px solid ${theme.border}`,
                fontSize: 10,
                color: theme.textMuted,
              }}
            >
              {`Heard: "${memory.original_text}"`}
            </div>
          )}
          <textarea
            value={text}
            onChange={(e) => {
              const newText = e.target.value;
              setText(newText);
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 320)}px`;
              if (editTimeoutRef.current) {
                window.clearTimeout(editTimeoutRef.current);
              }
              editTimeoutRef.current = window.setTimeout(() => {
                sendBridgeMessage({
                  type: 'correction_capture/edit',
                  session_id: sessionId,
                  new_text: newText,
                });
              }, 300);
            }}
            placeholder="Memory text"
            style={{
              minHeight: 80,
              resize: 'none',
              background: 'transparent',
              color: theme.text,
              border: 'none',
              padding: '12px',
              fontSize: 12,
              lineHeight: 1.6,
              outline: 'none',
              fontFamily: 'inherit',
              overflowY: 'auto',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0, marginBottom: 10, paddingTop: 2 }}>
          <button
            type="button"
            onClick={() => void optimize()}
            disabled={!text.trim() || isOptimizing}
            style={{
              background: 'transparent',
              color: theme.aiAccent,
              border: `1px solid ${theme.border}`,
              borderRadius: 10,
              padding: '8px 14px',
              fontSize: 11,
              fontWeight: 600,
              cursor: !text.trim() || isOptimizing ? 'not-allowed' : 'pointer',
              opacity: !text.trim() || isOptimizing ? 0.6 : 1,
            }}
          >
            {isOptimizing ? 'Optimizing…' : '✨ Optimize'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ fontSize: 10, color: status === 'error' ? theme.text : theme.textMuted }}>
              {status === 'saving'
                ? 'Saving…'
                : status === 'saved'
                  ? 'Saved'
                  : status === 'error'
                    ? 'Could not save'
                    : `${text.length} chars`}
            </span>
            <button
              type="button"
              onClick={() => save()}
              disabled={!text.trim() || status === 'saving'}
              style={{
                background: theme.aiAccent,
                color: '#0a0a0a',
                border: 'none',
                borderRadius: 10,
                padding: '8px 14px',
                fontSize: 11,
                fontWeight: 700,
                cursor: !text.trim() || status === 'saving' ? 'not-allowed' : 'pointer',
                opacity: !text.trim() || status === 'saving' ? 0.6 : 1,
              }}
            >
              Save
            </button>
          </div>

          <button
            type="button"
            onClick={() => del()}
            style={{
              background: 'transparent',
              color: '#F87171',
              border: '1px solid rgba(248,113,113,0.25)',
              borderRadius: 10,
              padding: '8px 14px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
