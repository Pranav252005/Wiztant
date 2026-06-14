import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Theme } from '../shared/themes';

export const ONBOARDED_KEY = 'whiztant.onboarded';

export function hasOnboarded(): boolean {
  return localStorage.getItem(ONBOARDED_KEY) === '1';
}

export function markOnboarded(): void {
  localStorage.setItem(ONBOARDED_KEY, '1');
}

// ─── Shared bits ──────────────────────────────────────────

function Kbd({ children, theme }: { children: string; theme: Theme['panel'] }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: 5,
        border: `1px solid ${theme.border}`,
        background: `${theme.aiAccent}14`,
        color: theme.text,
        fontSize: 10,
        fontWeight: 600,
        fontFamily: 'inherit',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

const PILL_STATES: { color: string; label: string; desc: string }[] = [
  { color: '#7B2241', label: 'Idle', desc: 'Wiztant is ready and listening for hotkeys' },
  { color: '#e2e2e2', label: 'Recording', desc: 'Mic is live — the wave reacts to your voice' },
  { color: '#C4956A', label: 'Thinking', desc: 'Processing your request' },
  { color: '#2d6e3e', label: 'Agent', desc: 'Agent mode is controlling the screen' },
];

function PillLegend({ theme }: { theme: Theme['panel'] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
      {PILL_STATES.map((s) => (
        <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: s.color,
              border: `1px solid ${theme.border}`,
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 11, fontWeight: 600, color: theme.text, width: 64, flexShrink: 0 }}>
            {s.label}
          </span>
          <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.4 }}>{s.desc}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Onboarding tour ──────────────────────────────────────

type TourStep = {
  title: string;
  body: React.ReactNode;
  /** Matches a data-tour attribute in the overlay; the element gets spotlit. */
  anchor?: string;
};

function buildSteps(theme: Theme['panel'], features: { agent: boolean; reprompt: boolean; tasks: boolean }): TourStep[] {
  const steps: TourStep[] = [
    {
      title: 'Welcome to Wiztant',
      body: (
        <>
          Wiztant lives in the background and is driven by hotkeys. This window is the overlay — press{' '}
          <Kbd theme={theme}>Ctrl</Kbd> + <Kbd theme={theme}>Space</Kbd> any time to show or hide it, or{' '}
          <Kbd theme={theme}>Esc</Kbd> to dismiss it.
        </>
      ),
    },
    {
      title: 'The pill',
      body: (
        <>
          The small wave at the bottom of your screen is the pill. It is always there and its color tells you what
          Wiztant is doing:
          <PillLegend theme={theme} />
        </>
      ),
    },
    {
      title: 'Dictation — press F9',
      body: (
        <>
          Put your cursor in any text field, press <Kbd theme={theme}>F9</Kbd>, and speak. When you stop, your words
          are transcribed and typed right where your cursor is. Everything you dictate also shows up in the Memories
          tab.
        </>
      ),
    },
    {
      title: 'Your toolkit',
      anchor: 'tabbar',
      body: (
        <>
          Each tab is one tool: <b>Tune Hub</b> teaches Wiztant your style, <b>RePrompt</b> optimizes prompts,{' '}
          <b>Agent</b> runs workflows on your screen, <b>Tasks</b> tracks to-dos with reminders, and <b>Memories</b>{' '}
          keeps your dictation history. Hover any tab for a description.
        </>
      ),
    },
  ];
  if (features.reprompt) {
    steps.push({
      title: 'RePrompt — instant prompt polish',
      body: (
        <>
          Copy any rough prompt, press <Kbd theme={theme}>Ctrl</Kbd> + <Kbd theme={theme}>Shift</Kbd> +{' '}
          <Kbd theme={theme}>Space</Kbd>, and Wiztant rewrites it into a sharper prompt — tuned to how you write —
          and puts it back on your clipboard.
        </>
      ),
    });
  }
  if (features.agent) {
    steps.push({
      title: 'Agent — double-tap F9',
      body: (
        <>
          Press <Kbd theme={theme}>F9</Kbd> twice quickly to toggle Agent mode: Wiztant looks at your screen and
          clicks, types, and navigates for you. You can also pick a ready-made workflow in the Agent tab and hit
          “Run Workflow”.
        </>
      ),
    });
  }
  steps.push({
    title: "You're set",
    anchor: 'header',
    body: (
      <>
        The gear opens Settings (themes, features, integrations), the diamond shows your credits, and the{' '}
        <b>?</b> button shows this hotkey guide again any time. Enjoy!
      </>
    ),
  });
  return steps;
}

type Rect = { top: number; left: number; width: number; height: number };

export function OnboardingTour({
  theme,
  features,
  onDone,
}: {
  theme: Theme['panel'];
  features: { agent: boolean; reprompt: boolean; tasks: boolean };
  onDone: () => void;
}) {
  const [step, setStep] = useState(0);
  const steps = buildSteps(theme, features);
  const current = steps[Math.min(step, steps.length - 1)];
  const [anchorRect, setAnchorRect] = useState<Rect | null>(null);

  // Measure the spotlit element whenever the step changes or window resizes.
  useEffect(() => {
    const measure = () => {
      if (!current.anchor) {
        setAnchorRect(null);
        return;
      }
      const el = document.querySelector(`[data-tour="${current.anchor}"]`);
      if (!el) {
        setAnchorRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setAnchorRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [step, current.anchor]);

  const finish = () => {
    markOnboarded();
    onDone();
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        finish();
      } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
        if (step >= steps.length - 1) {
          finish();
        } else {
          setStep(step + 1);
        }
      } else if (e.key === 'ArrowLeft') {
        setStep(Math.max(0, step - 1));
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, steps.length]);

  const isLast = step === steps.length - 1;

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 30 }}>
      {/* Backdrop / spotlight. The cutout is drawn with an oversized box-shadow. */}
      {anchorRect ? (
        <div
          style={{
            position: 'absolute',
            top: anchorRect.top - 4,
            left: anchorRect.left - 4,
            width: anchorRect.width + 8,
            height: anchorRect.height + 8,
            borderRadius: 10,
            border: `1px solid ${theme.aiAccent}`,
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.62)',
            pointerEvents: 'none',
            transition: 'all 0.2s ease',
          }}
        />
      ) : (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.62)' }} />
      )}

      {/* Step card — outer div owns positioning so framer-motion's transform
          animation on the inner div doesn't fight the centering transform. */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          pointerEvents: 'none',
          ...(anchorRect
            ? { top: anchorRect.top + anchorRect.height + 14 }
            : { top: 0, bottom: 0, alignItems: 'center' }),
        }}
      >
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 10, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          style={{
            pointerEvents: 'auto',
            width: 'min(340px, calc(100% - 32px))',
            borderRadius: 14,
            border: `1px solid ${theme.border}`,
            background: theme.headerBg,
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>{current.title}</span>
            <span style={{ fontSize: 10, color: theme.textMuted }}>
              {step + 1} / {steps.length}
            </span>
          </div>
          <div style={{ fontSize: 12, color: theme.textMuted, lineHeight: 1.55 }}>{current.body}</div>

          {/* Progress dots */}
          <div style={{ display: 'flex', gap: 5 }}>
            {steps.map((_, i) => (
              <span
                key={i}
                style={{
                  width: i === step ? 16 : 5,
                  height: 5,
                  borderRadius: 3,
                  background: i === step ? theme.aiAccent : theme.border,
                  transition: 'all 0.2s',
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
            <button
              onClick={finish}
              style={{
                background: 'transparent',
                border: 'none',
                color: theme.textMuted,
                fontSize: 11,
                cursor: 'pointer',
                fontFamily: 'inherit',
                padding: '6px 4px',
              }}
            >
              Skip tour
            </button>
            <div style={{ flex: 1 }} />
            {step > 0 && (
              <button
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                style={{
                  background: 'transparent',
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  color: theme.text,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  padding: '6px 12px',
                }}
              >
                Back
              </button>
            )}
            <button
              onClick={() => (isLast ? finish() : setStep((s) => s + 1))}
              style={{
                background: theme.aiAccent,
                border: 'none',
                borderRadius: 8,
                color: '#0b0b14',
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
                padding: '6px 14px',
              }}
            >
              {isLast ? 'Done' : 'Next'}
            </button>
          </div>
        </motion.div>
      </AnimatePresence>
      </div>
    </div>
  );
}

// ─── Hotkey cheat-sheet / help panel ──────────────────────

const HOTKEYS: { keys: string[]; label: string }[] = [
  { keys: ['F9'], label: 'Dictation — speak, text is typed at your cursor' },
  { keys: ['F9', 'F9'], label: 'Agent mode — Wiztant acts on your screen' },
  { keys: ['Ctrl', 'Space'], label: 'Show / hide this overlay' },
  { keys: ['Ctrl', 'Shift', 'Space'], label: 'RePrompt — optimize the prompt on your clipboard' },
  { keys: ['Esc'], label: 'Dismiss the overlay' },
  { keys: ['Ctrl', '←/→'], label: 'Switch between tabs' },
];

export function HelpSheet({
  theme,
  onClose,
  onReplayTour,
}: {
  theme: Theme['panel'];
  onClose: () => void;
  onReplayTour: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose]);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 25,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(360px, calc(100% - 32px))',
          maxHeight: 'calc(100% - 48px)',
          overflowY: 'auto',
          borderRadius: 14,
          border: `1px solid ${theme.border}`,
          background: theme.headerBg,
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          padding: '14px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: theme.text }}>Hotkeys & guide</span>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: theme.textMuted,
              fontSize: 14,
              cursor: 'pointer',
              lineHeight: 1,
              padding: 2,
              fontFamily: 'inherit',
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {HOTKEYS.map((h) => (
            <div key={h.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ display: 'flex', gap: 3, width: 118, flexShrink: 0, flexWrap: 'wrap' }}>
                {h.keys.map((k, i) => (
                  <Kbd key={i} theme={theme}>
                    {k}
                  </Kbd>
                ))}
              </span>
              <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.45 }}>{h.label}</span>
            </div>
          ))}
        </div>

        <div style={{ height: 1, background: theme.border }} />

        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: theme.text, marginBottom: 6 }}>
            Pill colors
          </div>
          <PillLegend theme={theme} />
        </div>

        <button
          onClick={onReplayTour}
          style={{
            marginTop: 2,
            background: 'transparent',
            border: `1px solid ${theme.border}`,
            borderRadius: 8,
            color: theme.text,
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
            padding: '7px 12px',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = theme.aiAccent;
            e.currentTarget.style.background = `${theme.aiAccent}12`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = theme.border;
            e.currentTarget.style.background = 'transparent';
          }}
        >
          Replay welcome tour
        </button>
      </motion.div>
    </div>
  );
}
