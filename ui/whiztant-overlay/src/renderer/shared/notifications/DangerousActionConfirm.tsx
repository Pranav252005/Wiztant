import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import type { Theme } from '../themes';

interface Props {
  actionDesc: string;
  reason: string;
  timeoutSeconds: number;
  onConfirm: () => void;
  onCancel: () => void;
  theme: Theme['panel'];
}

export default function DangerousActionConfirm({
  actionDesc,
  reason,
  timeoutSeconds,
  onConfirm,
  onCancel,
  theme,
}: Props) {
  const [remaining, setRemaining] = useState(timeoutSeconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    setRemaining(timeoutSeconds);

    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        const next = prev - 0.1;
        if (next <= 0) {
          if (!cancelledRef.current) {
            cancelledRef.current = true;
            onCancel();
          }
          return 0;
        }
        return next;
      });
    }, 100);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [timeoutSeconds, onCancel]);

  const handleConfirm = () => {
    cancelledRef.current = true;
    if (intervalRef.current) clearInterval(intervalRef.current);
    onConfirm();
  };

  const handleCancel = () => {
    cancelledRef.current = true;
    if (intervalRef.current) clearInterval(intervalRef.current);
    onCancel();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -12, scale: 0.96 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      style={{
        position: 'absolute',
        top: 12,
        left: 12,
        right: 12,
        zIndex: 20,
        padding: '14px 16px',
        borderRadius: 14,
        border: `1.5px solid #EF4444`,
        background: 'rgba(28, 10, 10, 0.97)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <span style={{ fontSize: 18, lineHeight: 1 }}>⚠️</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#FCA5A5', lineHeight: 1.3 }}>
            Dangerous Action Detected
          </span>
          <span style={{ fontSize: 12, color: theme.text, lineHeight: 1.4 }}>
            {actionDesc}
          </span>
          {reason && (
            <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.3 }}>
              Reason: {reason}
            </span>
          )}
        </div>
      </div>

      <div
        style={{
          height: 3,
          borderRadius: 2,
          background: 'rgba(255,255,255,0.08)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${(remaining / timeoutSeconds) * 100}%`,
            background: '#EF4444',
            borderRadius: 2,
            transition: 'width 0.1s linear',
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button
          onClick={handleCancel}
          style={{
            padding: '6px 12px',
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
            background: 'transparent',
            color: theme.textMuted,
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Cancel ({remaining.toFixed(1)}s)
        </button>
        <button
          onClick={handleConfirm}
          style={{
            padding: '6px 12px',
            borderRadius: 8,
            border: 'none',
            background: '#DC2626',
            color: '#fff',
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Confirm
        </button>
      </div>
    </motion.div>
  );
}
