import { useEffect, useRef, useState } from 'react';
import { sendBridgeMessage } from '../shared/useBridge';

interface Props {
  id: string;
  originalText: string;
  initialText: string;
  sessionId: string;
  onClose: () => void;
  onSave: () => void;
}

export default function DictationPreviewInline({
  id,
  originalText,
  initialText,
  sessionId,
  onClose,
  onSave,
}: Props) {
  const [text, setText] = useState(initialText);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const editTimeoutRef = useRef<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Notify Python when preview opens
  useEffect(() => {
    sendBridgeMessage({
      type: 'correction_capture/open',
      session_id: sessionId,
      original_text: originalText,
      stt_text: initialText,
    });
    return () => {
      sendBridgeMessage({ type: 'correction_capture/close', session_id: sessionId });
    };
  }, [sessionId, originalText, initialText]);

  // Capture Ctrl+Z as undo
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

  const handleChange = (newText: string) => {
    setText(newText);
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
  };

  const handleCopy = async () => {
    if (!text.trim()) return;
    try {
      await window.api.writeClipboard(text.trim());
    } catch {
      // ignore
    }
    sendBridgeMessage({ type: 'correction_capture/copy', session_id: sessionId });
  };

  const handleOptimize = () => {
    if (!text.trim() || isOptimizing) return;
    setIsOptimizing(true);
    sendBridgeMessage({
      type: 'dictation_preview/optimize',
      text: text.trim(),
      session_id: sessionId,
    });
  };

  const handleSave = () => {
    if (!text.trim()) return;
    sendBridgeMessage({
      type: 'dictation_memories/edit',
      id,
      final_text: text.trim(),
      original_text: originalText,
    });
    onSave();
  };

  const showHeard = originalText && originalText !== text;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        padding: '8px 10px',
        gap: 6,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 700, color: '#c0c1ff' }}>
          Dictation Preview
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: '#6b7280' }}>{text.length} chars</span>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              color: '#6b7280',
              cursor: 'pointer',
              fontSize: 14,
              lineHeight: 1,
              padding: 0,
              width: 18,
              height: 18,
            }}
            title="Close"
          >
            ×
          </button>
        </div>
      </div>

      {/* Heard */}
      {showHeard && (
        <div
          style={{
            fontSize: 10,
            color: '#6b7280',
            lineHeight: 1.4,
            wordBreak: 'break-word',
          }}
        >
          Heard: "{originalText}"
        </div>
      )}

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="Edit your dictation..."
        autoFocus
        style={{
          flex: 1,
          minHeight: 40,
          resize: 'none',
          background: 'rgba(255,255,255,0.05)',
          color: '#e2e2e2',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8,
          padding: '8px 10px',
          fontSize: 11,
          lineHeight: 1.5,
          outline: 'none',
          fontFamily: 'inherit',
        }}
      />

      {/* Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button
          type="button"
          onClick={() => void handleCopy()}
          style={{
            flex: 1,
            background: 'transparent',
            color: '#c0c1ff',
            border: '1px solid rgba(192,193,255,0.25)',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 10,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Copy
        </button>
        <button
          type="button"
          onClick={() => void handleOptimize()}
          disabled={!text.trim() || isOptimizing}
          style={{
            flex: 1,
            background: 'transparent',
            color: '#d0bcff',
            border: '1px solid rgba(208,188,255,0.25)',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 10,
            fontWeight: 600,
            cursor: !text.trim() || isOptimizing ? 'not-allowed' : 'pointer',
            opacity: !text.trim() || isOptimizing ? 0.6 : 1,
          }}
        >
          {isOptimizing ? '…' : '✨ Optimize'}
        </button>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={!text.trim()}
          style={{
            flex: 1,
            background: '#c0c1ff',
            color: '#0a0a0a',
            border: 'none',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 10,
            fontWeight: 700,
            cursor: !text.trim() ? 'not-allowed' : 'pointer',
            opacity: !text.trim() ? 0.6 : 1,
          }}
        >
          Save
        </button>
      </div>
    </div>
  );
}
