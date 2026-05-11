interface Props {
  onSnooze: (minutes: number) => void;
  onCancel: () => void;
}

const PRESETS = [
  { label: '15m', minutes: 15 },
  { label: '30m', minutes: 30 },
  { label: '1h', minutes: 60 },
  { label: '1d', minutes: 1440 },
];

export default function SnoozeOptions({ onSnooze, onCancel }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
        height: '100%',
        padding: '0 16px',
        gap: 10,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e2e2', whiteSpace: 'nowrap' }}>
        Snooze for
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {PRESETS.map((preset) => (
          <button
            key={preset.minutes}
            type="button"
            onClick={() => onSnooze(preset.minutes)}
            style={{
              padding: '5px 10px',
              borderRadius: 6,
              background: 'rgba(192,193,255,0.15)',
              border: 'none',
              color: '#c0c1ff',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(192,193,255,0.30)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(192,193,255,0.15)';
            }}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: '5px 10px',
            borderRadius: 6,
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.10)',
            color: '#6b7280',
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
            marginLeft: 4,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
