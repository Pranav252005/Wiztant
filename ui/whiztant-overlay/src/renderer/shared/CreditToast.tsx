import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useBridgeMessage } from './useBridge';

type CreditToast = {
  id: string;
  feature: string;
  amount: number;
  balanceAfter: number;
};

const FEATURE_LABELS: Record<string, string> = {
  taskstack: 'TaskStack',
  reprompt: 'RePrompt',
  tunehub: 'Tune Hub',
  agent: 'Agent',
  chat: 'Chat',
};

export function useCreditToasts() {
  const [toasts, setToasts] = useState<CreditToast[]>([]);

  useBridgeMessage((msg) => {
    if (msg?.type === 'credits/consumed') {
      const feature = String(msg.feature ?? '');
      // Dictation is explicitly excluded from tracking visibility
      if (feature === 'dictation') return;
      const toast: CreditToast = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        feature,
        amount: Number(msg.amount ?? 0),
        balanceAfter: Number(msg.balance_after ?? 0),
      };
      setToasts((prev) => [...prev.slice(-2), toast]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id));
      }, 3000);
    }
  });

  return toasts;
}

export function CreditToastContainer({ toasts }: { toasts: CreditToast[] }) {
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 80,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        pointerEvents: 'none',
      }}
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 12, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              background: 'rgba(15,15,26,0.95)',
              border: '1px solid rgba(192,193,255,0.25)',
              color: '#e2e2e2',
              fontSize: 12,
              fontWeight: 500,
              backdropFilter: 'blur(8px)',
              whiteSpace: 'nowrap',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            }}
          >
            <span style={{ color: '#c0c1ff' }}>
              {FEATURE_LABELS[t.feature] || t.feature}
            </span>
            {' — '}
            <span style={{ color: '#F59E0B' }}>
              −{t.amount} credit{t.amount !== 1 ? 's' : ''}
            </span>
            {' · '}
            <span style={{ color: '#6b7280' }}>{t.balanceAfter} left</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
