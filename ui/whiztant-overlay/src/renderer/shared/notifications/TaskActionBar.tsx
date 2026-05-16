import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface TaskActionBarProps {
  onApprove?: () => void;
  onDeny?: () => void;
  onSnooze?: (minutes: number) => void;
  onEdit?: () => void;
  compact?: boolean;
}

const PRESETS = [
  { label: '15m', minutes: 15 },
  { label: '30m', minutes: 30 },
  { label: '1h', minutes: 60 },
  { label: '1d', minutes: 1440 },
];

export default function TaskActionBar({
  onApprove,
  onDeny,
  onSnooze,
  onEdit,
  compact,
}: TaskActionBarProps) {
  const [showSnooze, setShowSnooze] = useState(false);
  const btnSize = compact ? 26 : 32;
  const iconSize = compact ? 14 : 16;

  const handleSnooze = (minutes: number) => {
    setShowSnooze(false);
    onSnooze?.(minutes);
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
      <AnimatePresence mode="wait">
        {showSnooze && onSnooze ? (
          <motion.div
            key="snooze"
            initial={{ opacity: 0, scale: 0.9, x: 10 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            exit={{ opacity: 0, scale: 0.9, x: 10 }}
            transition={{ duration: 0.18 }}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            {PRESETS.map((preset) => (
              <button
                key={preset.minutes}
                type="button"
                onClick={() => handleSnooze(preset.minutes)}
                style={{
                  padding: compact ? '3px 7px' : '4px 9px',
                  borderRadius: 6,
                  background: 'rgba(251,191,36,0.15)',
                  border: 'none',
                  color: '#fbbf24',
                  fontSize: compact ? 10 : 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(251,191,36,0.30)';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(251,191,36,0.15)';
                }}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setShowSnooze(false)}
              style={{
                padding: compact ? '3px 7px' : '4px 9px',
                borderRadius: 6,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.10)',
                color: '#6b7280',
                fontSize: compact ? 10 : 11,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="actions"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            {onApprove && (
              <ActionButton
                size={btnSize}
                iconSize={iconSize}
                color="#34d399"
                bg="rgba(52,211,153,0.15)"
                bgHover="rgba(52,211,153,0.30)"
                onClick={onApprove}
                title="Approve"
              >
                <CheckIcon size={iconSize} />
              </ActionButton>
            )}
            {onDeny && (
              <ActionButton
                size={btnSize}
                iconSize={iconSize}
                color="#f87171"
                bg="rgba(248,113,113,0.15)"
                bgHover="rgba(248,113,113,0.30)"
                onClick={onDeny}
                title="Deny"
              >
                <XIcon size={iconSize} />
              </ActionButton>
            )}
            {onSnooze && (
              <ActionButton
                size={btnSize}
                iconSize={iconSize}
                color="#fbbf24"
                bg="rgba(251,191,36,0.15)"
                bgHover="rgba(251,191,36,0.30)"
                onClick={() => setShowSnooze(true)}
                title="Snooze"
              >
                <ClockIcon size={iconSize} />
              </ActionButton>
            )}
            {onEdit && (
              <ActionButton
                size={btnSize}
                iconSize={iconSize}
                color="#c0c1ff"
                bg="rgba(192,193,255,0.15)"
                bgHover="rgba(192,193,255,0.30)"
                onClick={onEdit}
                title="Edit"
              >
                <PencilIcon size={iconSize} />
              </ActionButton>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ActionButton({
  size,
  color,
  bg,
  bgHover,
  onClick,
  title,
  children,
}: {
  size: number;
  color: string;
  bg: string;
  bgHover: string;
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        width: size,
        height: size,
        borderRadius: 6,
        background: bg,
        border: 'none',
        color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background = bgHover;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background = bg;
      }}
    >
      {children}
    </button>
  );
}

function CheckIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function ClockIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function PencilIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </svg>
  );
}
