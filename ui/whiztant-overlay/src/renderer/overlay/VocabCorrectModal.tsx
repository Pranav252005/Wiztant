import { useCallback, useEffect, useRef, useState } from 'react';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage, useBridgeMessage } from '../shared/useBridge';

type Prompt = {
  heard: string;
  context_before: string;
  context_after: string;
};

type Props = {
  theme: Theme['panel'];
};

export default function VocabCorrectModal({ theme }: Props) {
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [actual, setActual] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleMessage = useCallback((msg: Record<string, unknown>) => {
    if (msg.type === 'vocab_correct') {
      setPrompt({
        heard: String(msg.heard ?? ''),
        context_before: String(msg.context_before ?? ''),
        context_after: String(msg.context_after ?? ''),
      });
      setActual('');
    }
  }, []);

  useBridgeMessage(handleMessage);

  useEffect(() => {
    if (!prompt) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50);
    return () => window.clearTimeout(timer);
  }, [prompt]);

  const dismiss = () => setPrompt(null);

  const submit = () => {
    if (!prompt || !actual.trim()) return;
    sendBridgeMessage({ type: 'vocab_add', heard: prompt.heard, actual: actual.trim() });
    setPrompt(null);
  };

  if (!prompt) return null;

  return (
    <div
      onClick={dismiss}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'rgba(0, 0, 0, 0.34)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Correct a word"
        style={{
          width: '100%',
          maxWidth: 320,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: 16,
          borderRadius: 16,
          border: `1px solid ${theme.border}`,
          background: theme.headerBg,
          boxShadow: '0 24px 70px rgba(0, 0, 0, 0.35)',
        }}
      >
        <div style={{ color: theme.text, fontSize: 13, fontWeight: 700 }}>Correct a word</div>
        <div style={{ color: theme.textMuted, fontSize: 12, lineHeight: 1.55 }}>
          {prompt.context_before ? `${prompt.context_before} ` : ''}
          <strong style={{ color: theme.text }}>“{prompt.heard}”</strong>
          {prompt.context_after ? ` ${prompt.context_after}` : ''}
        </div>
        <input
          ref={inputRef}
          value={actual}
          onChange={(event) => setActual(event.target.value)}
          placeholder="Correct spelling…"
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit();
            if (event.key === 'Escape') dismiss();
          }}
          style={{
            width: '100%',
            padding: '10px 12px',
            borderRadius: 11,
            border: `1px solid ${theme.border}`,
            outline: 'none',
            background: theme.inputBg,
            color: theme.text,
            fontSize: 12,
            fontFamily: 'inherit',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            type="button"
            onClick={dismiss}
            style={{
              padding: '7px 11px',
              borderRadius: 9,
              border: `1px solid ${theme.border}`,
              background: 'transparent',
              color: theme.text,
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!actual.trim()}
            style={{
              padding: '7px 11px',
              borderRadius: 9,
              border: 'none',
              background: actual.trim() ? theme.accent : `${theme.accent}33`,
              color: actual.trim() ? '#0a0a0a' : theme.textMuted,
              fontSize: 11,
              fontWeight: 700,
              cursor: actual.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            Save correction
          </button>
        </div>
      </div>
    </div>
  );
}
