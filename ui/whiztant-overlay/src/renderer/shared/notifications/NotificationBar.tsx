import { motion } from 'framer-motion';
import type { PillNotificationPayload } from '../usePillNotifications';
import TaskActionBar from './TaskActionBar';

interface Props {
  payload: PillNotificationPayload;
  onToggleDone: () => void;
  onDismiss: () => void;
  onSnooze: (minutes: number) => void;
  onEdit: () => void;
  onBodyClick: () => void;
}

export default function NotificationBar({ payload, onToggleDone, onDismiss, onSnooze, onEdit, onBodyClick }: Props) {
  const urgencyColor =
    payload.notification_type === 'overdue'
      ? '#f87171'
      : payload.notification_type === 'due_now'
        ? '#fbbf24'
        : '#c0c1ff';

  const urgencyBg =
    payload.notification_type === 'overdue'
      ? 'rgba(248,113,113,0.15)'
      : 'rgba(192,193,255,0.15)';

  const subtitle =
    payload.notification_type === 'pre_due'
      ? `Due in ${payload.minutes_remaining} min`
      : payload.notification_type === 'due_now'
        ? 'Due now'
        : 'Overdue';

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
        height: '100%',
        padding: '0 16px',
        gap: 12,
      }}
    >
      {/* Icon + Title */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1, cursor: 'pointer' }}
        onClick={onBodyClick}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 999,
            background: urgencyBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={urgencyColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
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
              maxWidth: 240,
              margin: 0,
            }}
          >
            {payload.title}
          </p>
          <p
            style={{
              fontSize: 11,
              color: '#6b7280',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            {subtitle}
          </p>
        </div>
      </div>

      {/* Unified Action Bar */}
      <TaskActionBar
        onApprove={onToggleDone}
        onDeny={onDismiss}
        onSnooze={onSnooze}
        onEdit={onEdit}
      />
    </motion.div>
  );
}
