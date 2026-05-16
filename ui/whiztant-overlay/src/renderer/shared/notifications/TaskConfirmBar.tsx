import { motion } from 'framer-motion';
import type { TaskConfirmPayload } from '../usePillNotifications';
import TaskActionBar from './TaskActionBar';

interface Props {
  payload: TaskConfirmPayload;
  onApprove: () => void;
  onDisapprove: () => void;
  onEdit: () => void;
  compact?: boolean;
}

function formatDue(iso?: string) {
  if (!iso) return { timeStr: '', dateStr: '' };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { timeStr: '', dateStr: '' };
  return {
    timeStr: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    dateStr: d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
  };
}

export default function TaskConfirmBar({ payload, onApprove, onDisapprove, onEdit, compact }: Props) {
  const { timeStr, dateStr } = formatDue(payload.due_datetime);
  const isCompact = compact ?? false;

  const iconSize = isCompact ? 26 : 32;
  const titleMaxWidth = isCompact ? 120 : 220;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={{ delay: 0.08, duration: 0.2 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        height: '100%',
        padding: isCompact ? '0 10px' : '0 16px',
        gap: 8,
      }}
    >
      {/* LEFT: Icon + Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: '1 1 auto' }}>
        <div
          style={{
            width: iconSize,
            height: iconSize,
            borderRadius: 999,
            background: 'rgba(192,193,255,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: isCompact ? 12 : 14 }}>📝</span>
        </div>
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <p
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: '#e2e2e2',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: titleMaxWidth,
              margin: 0,
              lineHeight: 1.3,
            }}
          >
            {payload.parsed_title}
          </p>
          <p style={{ fontSize: 11, color: '#6b7280', margin: 0, lineHeight: 1.3 }}>Store this task?</p>
        </div>
      </div>

      {/* RIGHT: Time & Date + Unified Action Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: isCompact ? 4 : 6, flexShrink: 0 }}>
        {payload.has_time && timeStr && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: isCompact ? '2px 6px' : '4px 10px',
              background: 'rgba(76,215,246,0.10)',
              border: '1px solid rgba(76,215,246,0.20)',
              color: '#4cd7f6',
              fontSize: isCompact ? 10 : 12,
              fontWeight: 600,
              borderRadius: 4,
              whiteSpace: 'nowrap',
            }}
          >
            {!isCompact && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            )}
            <span>{timeStr}</span>
          </div>
        )}
        {payload.has_date && dateStr && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: isCompact ? '2px 6px' : '4px 10px',
              background: 'rgba(208,188,255,0.10)',
              border: '1px solid rgba(208,188,255,0.20)',
              color: '#d0bcff',
              fontSize: isCompact ? 10 : 12,
              fontWeight: 600,
              borderRadius: 4,
              whiteSpace: 'nowrap',
            }}
          >
            {!isCompact && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            )}
            <span>{dateStr}</span>
          </div>
        )}

        <TaskActionBar
          onApprove={onApprove}
          onDeny={onDisapprove}
          onEdit={onEdit}
          compact={isCompact}
        />
      </div>
    </motion.div>
  );
}
