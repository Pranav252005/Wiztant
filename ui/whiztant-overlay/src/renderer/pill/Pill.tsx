import { useEffect, useLayoutEffect, useMemo, useRef, useState, useCallback, MouseEvent as ReactMouseEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { themes, defaultTheme } from '../shared/themes';
import type {
  AppState,
  ThemeName,
  PillNoticePayload,
  PillNoticeKind,
  Task,
} from '../shared/ipc';
import { useBridgeMessage, sendBridgeMessage } from '../shared/useBridge';
import { usePillNotifications, type TaskConfirmPayload, type PillNotificationPayload } from '../shared/usePillNotifications';
import NotificationRenderer, { pillSizeFor } from '../shared/notifications/NotificationRenderer';
import SnoozeOptions from '../shared/notifications/SnoozeOptions';
import DictationPreviewInline from './DictationPreviewInline';

// Number of waveform bars shown while recording.
const BANDS = 5;
// Max bar height in px (stays inside the 18px pill).
const MAX_BAR_H = 12;

// Visual pill dimensions (the actual colored capsule).
const PILL_VISUAL_W = 60;
const PILL_VISUAL_H = 18;

/**
 * Live microphone level meter.
 *
 * When `enabled` flips true we open the default mic, build an AnalyserNode,
 * and on every animation frame reduce the frequency-domain buffer into
 * `bands` average values in [0, 1]. When `enabled` flips false (F9 toggle
 * off, Escape, state change) we fully tear down the stream + AudioContext
 * so the OS mic indicator clears and there is no lingering CPU.
 *
 * Falls back to Python-pushed mic levels via the WebSocket bridge when
 * browser getUserMedia fails or is unavailable (common on Linux / Wayland).
 */
function useMicLevels(enabled: boolean, bands: number): number[] {
  const [levels, setLevels] = useState<number[]>(() => new Array(bands).fill(0));
  const pythonLevelRef = useRef(0);
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  // Listen for mic_level messages from Python backend as fallback.
  // Use a stable callback so we don't re-register the bridge listener
  // on every render (which happens ~60×/s when the bars are animating).
  useBridgeMessage((msg) => {
    if (enabledRef.current && msg?.type === 'mic_level') {
      const lvl = typeof msg.level === 'number' ? msg.level : 0;
      pythonLevelRef.current = Math.max(0, Math.min(1, lvl));
    }
  });

  useEffect(() => {
    if (!enabled) {
      setLevels(new Array(bands).fill(0));
      return;
    }

    let cancelled = false;
    let stream: MediaStream | null = null;
    let ctx: AudioContext | null = null;
    let raf = 0;
    let hasBrowserMic = false;
    let fallbackTimer: number | null = null;

    navigator.mediaDevices
      .getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then(async (s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        hasBrowserMic = true;
        stream = s;
        ctx = new AudioContext();
        // Chromium may create the context in 'suspended' state on subsequent
        // recordings. Resume it explicitly before wiring the graph.
        if (ctx.state === 'suspended') {
          try {
            await ctx.resume();
          } catch {
            /* ignore */
          }
        }
        const src = ctx.createMediaStreamSource(s);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 128;
        analyser.smoothingTimeConstant = 0.75;
        src.connect(analyser);

        // Focus on vocal band (~100Hz – 4kHz). FFT size 128 at 48kHz sample rate
        // gives bins ~375Hz wide. Take bins 1..16 and split them into `bands`.
        const data = new Uint8Array(analyser.frequencyBinCount);
        const firstBin = 1;
        const lastBin = Math.min(16, analyser.frequencyBinCount);
        const binsPerBand = Math.max(1, Math.floor((lastBin - firstBin) / bands));

        const tick = () => {
          if (cancelled) return;
          // Defensive: if context got suspended mid-recording, try to resume.
          if (ctx && ctx.state === 'suspended') {
            ctx.resume().catch(() => {});
          }
          analyser.getByteFrequencyData(data);
          const next: number[] = [];
          for (let i = 0; i < bands; i++) {
            let sum = 0;
            const start = firstBin + i * binsPerBand;
            const end = start + binsPerBand;
            for (let j = start; j < end; j++) sum += data[j];
            const avg = sum / binsPerBand / 255; // 0..1
            next.push(avg);
          }
          setLevels(next);
          raf = requestAnimationFrame(tick);
        };
        tick();
      })
      .catch((err) => {
        // Permission denied or no device — fall back to Python mic levels.
        // eslint-disable-next-line no-console
        console.warn('[whiztant] mic unavailable, using Python fallback:', err);
      });

    // Fallback tick: wait briefly for getUserMedia to resolve, then drive bars
    // from Python level only if browser mic never became available.
    fallbackTimer = window.setTimeout(() => {
      if (cancelled || hasBrowserMic) return;
      const runFallback = () => {
        if (cancelled || hasBrowserMic) return;
        const base = pythonLevelRef.current;
        const next = Array.from({ length: bands }, (_, i) => {
          const phase = (i / bands) * Math.PI * 2;
          const variation = Math.sin(Date.now() / 200 + phase) * 0.08;
          return Math.max(0, Math.min(1, base + variation));
        });
        setLevels(next);
        fallbackTimer = window.setTimeout(runFallback, 60);
      };
      runFallback();
    }, 400);

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      if (fallbackTimer) clearTimeout(fallbackTimer);
      stream?.getTracks().forEach((t) => t.stop());
      ctx?.close().catch(() => {});
    };
  }, [enabled, bands]);

  return levels;
}


/**
 * Simulated waveform bars for agent mode when no mic input is available.
 * Creates a gentle flowing wave pattern so the pill feels "alive".
 */
function useSimulatedBars(enabled: boolean, bands: number): number[] {
  const [levels, setLevels] = useState<number[]>(() => new Array(bands).fill(0));

  useEffect(() => {
    if (!enabled) {
      setLevels(new Array(bands).fill(0));
      return;
    }
    let timer: number | null = null;
    let t = 0;
    const tick = () => {
      t += 0.18;
      setLevels(
        Array.from({ length: bands }, (_, i) => {
          const phase = (i / bands) * Math.PI * 2;
          const v = Math.sin(t + phase) * 0.35 + 0.5;
          const noise = (Math.random() - 0.5) * 0.15;
          return Math.max(0.1, Math.min(0.85, v + noise));
        })
      );
      timer = window.setTimeout(tick, 90);
    };
    tick();
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [enabled, bands]);

  return levels;
}

const GREEN = 'rgba(52, 211, 153, 0.95)';
const AMBER = 'rgba(251, 191, 36, 0.95)';
const RED = 'rgba(248, 113, 113, 0.95)';
const AGENT_BLUE = 'rgba(96, 165, 250, 0.95)';

function noticeAccent(kind: PillNoticeKind): string {
  if (kind === 'duplicate' || kind === 'subtask') return AMBER;
  if (kind === 'error') return RED;
  return GREEN;
}

function noticeBg(kind: PillNoticeKind): string {
  if (kind === 'duplicate' || kind === 'subtask') {
    return 'linear-gradient(90deg, rgba(251,191,36,0.18) 0%, rgba(18,18,24,0.92) 55%)';
  }
  if (kind === 'error') {
    return 'linear-gradient(90deg, rgba(248,113,113,0.22) 0%, rgba(18,18,24,0.92) 55%)';
  }
  return 'linear-gradient(90deg, rgba(52,211,153,0.22) 0%, rgba(18,18,24,0.92) 55%)';
}

export default function Pill() {
  const [state, setState] = useState<AppState>('idle');
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const [notice, setNotice] = useState<PillNoticePayload | null>(null);
  const [glowActive, setGlowActive] = useState(false);
  const [flashState, setFlashState] = useState<'success' | 'error' | null>(null);

  // Agent status tracking: idle | active (blue) | working (green) | error (red)
  const [agentStatus, setAgentStatus] = useState<'idle' | 'active' | 'working' | 'error'>('idle');
  const agentStatusRef = useRef(agentStatus);
  agentStatusRef.current = agentStatus;
  const agentTimeoutRef = useRef<number | null>(null);

  // Agent mode toggle tracking (F9×2) — drives dark-blue pill theme
  const [agentModeEnabled, setAgentModeEnabled] = useState(false);
  const agentModeRef = useRef(agentModeEnabled);
  agentModeRef.current = agentModeEnabled;

  // Snooze view state: when user clicks a notification body, show snooze options
  const [snoozePayload, setSnoozePayload] = useState<PillNotificationPayload | null>(null);

  // Inline dictation preview state
  const [dictationPreview, setDictationPreview] = useState<{
    id: string;
    text: string;
    originalText: string;
    sessionId: string;
  } | null>(null);

  const pillNotifications = usePillNotifications();
  const activeNotification = pillNotifications.active;
  const dismissNotification = pillNotifications.dismiss;
  const updateActiveNotification = pillNotifications.updateActive;
  const prevStateRef = useRef<AppState>(state);

  const theme = themes[themeName];
  const isAgentVisual = agentModeEnabled && (state === 'recording' || state === 'thinking' || state === 'agent');
  const color = isAgentVisual ? theme.pill.recording : theme.pill[state];
  const glow = theme.pill.glow;
  const capsuleBg = isAgentVisual ? 'rgba(26, 58, 107, 0.96)' : theme.pill.bg;
  const capsuleBorder = isAgentVisual ? 'rgba(96, 165, 250, 0.35)' : theme.pill.border;

  const levels = useMicLevels(state === 'recording', BANDS);
  const simulatedLevels = useSimulatedBars(state === 'agent', BANDS);

  useEffect(() => {
    window.api.onSetState(setState);
    window.api.onThemeChanged((n) => setThemeName(n));
    window.api.onPillNotice((payload) => {
      setNotice(payload);
      const duration = Math.max(800, payload.duration_ms || 2600);
      window.setTimeout(() => {
        setNotice((current) => (current === payload ? null : current));
      }, duration);
    });
  }, []);

  const clearAgentTimeout = useCallback(() => {
    if (agentTimeoutRef.current) {
      clearTimeout(agentTimeoutRef.current);
      agentTimeoutRef.current = null;
    }
  }, []);

  // Relay bridge messages into local state / main process.
  const handleBridge = useCallback((msg: Record<string, unknown>) => {
    if (msg?.type === 'pill/notice') {
      const payload: PillNoticePayload = {
        kind: (msg.kind as PillNoticeKind) || 'added',
        title: String(msg.title ?? ''),
        summary: String(msg.summary ?? ''),
        duration_ms: Number(msg.duration_ms ?? 2600),
      };
      window.api.requestPillNotice(payload);
    }

    // ── Agent mode toggle ──
    if (msg?.type === 'agent_mode') {
      const enabled = Boolean(msg.enabled);
      console.log('[Pill] agent_mode message:', enabled);
      setAgentModeEnabled(enabled);
    }

    // ── Wave state (Python-driven state machine) ──
    if (msg?.type === 'wave_state') {
      const ws = String(msg.state ?? '');
      console.log('[Pill] wave_state message:', ws);
      if (['idle', 'recording', 'thinking', 'speaking', 'agent'].includes(ws)) {
        setState(ws as AppState);
        window.api.syncState(ws as AppState);
        // Also infer agent mode from wave_state so we never miss the toggle
        if (ws === 'agent') {
          setAgentModeEnabled(true);
        }
        // Reset agent status when leaving agent mode
        if (ws !== 'agent' && agentStatusRef.current !== 'idle') {
          setAgentStatus('idle');
          clearAgentTimeout();
        }
      }
    }

    // ── Agent step (legacy v1) ──
    if (msg?.type === 'agent_step') {
      setAgentStatus('working');
      clearAgentTimeout();
      agentTimeoutRef.current = window.setTimeout(() => {
        if (agentStatusRef.current === 'working') {
          setAgentStatus('active');
        }
      }, 2500);
    }

    // ── Agent step v2 ──
    if (msg?.type === 'agent/step') {
      setAgentStatus('working');
      clearAgentTimeout();
      agentTimeoutRef.current = window.setTimeout(() => {
        if (agentStatusRef.current === 'working') {
          setAgentStatus('active');
        }
      }, 2500);
    }

    // ── Agent done ──
    if (msg?.type === 'agent/done') {
      const success = Boolean(msg.success ?? true);
      if (success) {
        setAgentStatus('idle');
      } else {
        setAgentStatus('error');
        setFlashState('error');
      }
      clearAgentTimeout();
    }

    // ── Agent blocked ──
    if (msg?.type === 'agent/blocked') {
      setAgentStatus('error');
      setFlashState('error');
      clearAgentTimeout();
    }

    // ── Voice state (dictation lifecycle) ──
    if (msg?.type === 'voice_state') {
      const vs = String(msg.state ?? '');
      if (vs === 'listening') {
        setState('recording');
        window.api.syncState('recording');
      } else if (vs === 'processing') {
        setState('thinking');
        window.api.syncState('thinking');
      } else if (vs === 'pasted') {
        setFlashState('success');
        setState('idle');
        window.api.syncState('idle');
      } else if (vs === 'error') {
        setFlashState('error');
        setState('idle');
        window.api.syncState('idle');
      } else if (vs === 'idle') {
        // Explicit idle reset — ensures we never get stuck in thinking/recording
        // if a delayed message arrives after the session already ended.
        setState('idle');
        window.api.syncState('idle');
      }
    }

    // ── Dictation preview — open MemoryPanel AND show inline preview in pill ──
    if (msg?.type === 'dictation_preview') {
      const previewText = String(msg.text ?? '');
      const originalText = String(msg.original_text ?? '');
      const previewSessionId = String(msg.session_id ?? '');
      const previewId = String(msg.id ?? `preview-${Date.now()}`);
      if (previewText) {
        setDictationPreview({
          id: previewId,
          text: previewText,
          originalText,
          sessionId: previewSessionId,
        });
        const syntheticMemory = {
          id: previewId,
          timestamp: new Date().toISOString(),
          mode: 'dictation' as const,
          original_text: originalText,
          final_text: previewText,
          session_id: previewSessionId,
        };
        void window.api.openMemoryPanel(syntheticMemory);
      }
    }

    // ── Dictation preview optimized — update inline preview text ──
    if (msg?.type === 'dictation_preview/optimized' && dictationPreview) {
      const optimized = String(msg.text ?? '');
      if (optimized) {
        setDictationPreview((prev) =>
          prev ? { ...prev, text: optimized } : null
        );
        sendBridgeMessage({
          type: 'correction_capture/optimize',
          session_id: dictationPreview.sessionId,
          optimized,
        });
      }
    }
  }, [clearAgentTimeout, dictationPreview]);

  useBridgeMessage(handleBridge);

  // Resize the pill window whenever a persistent notification mounts/unmounts.
  useEffect(() => {
    if (dictationPreview) {
      window.api.expandPill({ width: 460, height: 220 });
    } else if (activeNotification) {
      window.api.expandPill(pillSizeFor(activeNotification));
    } else {
      window.api.expandPill(null);
    }
  }, [activeNotification, dictationPreview]);

  // F9 auto-dismiss + glow on state transitions.
  useEffect(() => {
    const prev = prevStateRef.current;
    prevStateRef.current = state;

    // Dismiss notifications when entering recording or agent.
    if (prev !== 'recording' && state === 'recording' && activeNotification) {
      dismissNotification();
    }
    if (prev !== 'agent' && state === 'agent' && activeNotification) {
      dismissNotification();
    }

    // Trigger glow when leaving recording; cancel it if we re-enter.
    if (prev === 'recording' && state !== 'recording') {
      setGlowActive(true);
    } else if (state === 'recording') {
      setGlowActive(false);
    }
  }, [state, activeNotification, dismissNotification]);

  // Auto-clear the glow after 1.2 s.
  useEffect(() => {
    if (!glowActive) return;
    const t = window.setTimeout(() => setGlowActive(false), 1200);
    return () => clearTimeout(t);
  }, [glowActive]);

  // Auto-clear flash after 1.5s.
  useEffect(() => {
    if (!flashState) return;
    const t = window.setTimeout(() => setFlashState(null), 1500);
    return () => clearTimeout(t);
  }, [flashState]);

  // Cancel flash if user starts recording or agent again.
  useEffect(() => {
    if ((state === 'recording' || state === 'agent') && flashState) {
      setFlashState(null);
    }
  }, [state, flashState]);

  // Auto-clear agent error status after 3s.
  useEffect(() => {
    if (agentStatus !== 'error') return;
    const t = window.setTimeout(() => {
      setAgentStatus('idle');
    }, 3000);
    return () => clearTimeout(t);
  }, [agentStatus]);

  // Auto-dismiss pill notifications after 10s.
  // Skip auto-dismiss for kinds that require explicit user action.
  useEffect(() => {
    if (!activeNotification) {
      setSnoozePayload(null);
      return;
    }
    const skipAutoDismiss: PillNotificationKind[] = ['task_confirm', 'due_alert'];
    if (skipAutoDismiss.includes(activeNotification.kind)) {
      return;
    }
    const timer = setTimeout(() => {
      dismissNotification();
      setSnoozePayload(null);
    }, 10000);
    return () => clearTimeout(timer);
  }, [activeNotification, dismissNotification]);

  const isNotificationActive = Boolean(activeNotification);
  const isNoticeExpanded = Boolean(notice) && !isNotificationActive;
  const isDictationPreviewActive = Boolean(dictationPreview);
  const isExpanded = isNotificationActive || isNoticeExpanded || isDictationPreviewActive;
  const isFlashing = Boolean(flashState) && !isExpanded;

  const flashColor = flashState === 'success' ? GREEN : RED;
  const flashGlow = flashState === 'success' ? 'rgba(52,211,153,0.45)' : 'rgba(248,113,113,0.45)';
  const flashBg = flashState === 'success'
    ? 'linear-gradient(90deg, rgba(52,211,153,0.25) 0%, rgba(18,18,24,0.92) 55%)'
    : 'linear-gradient(90deg, rgba(248,113,113,0.25) 0%, rgba(18,18,24,0.92) 55%)';

  const handleContextMenu = (e: ReactMouseEvent) => {
    e.preventDefault();
    window.api.showPillMenu();
  };

  // ── Click / double-click drag handling ─────────────────────────
  const pillRef = useRef<HTMLDivElement>(null);
  const lastMouseDownRef = useRef(0);
  const isDraggingRef = useRef(false);
  const clickTimerRef = useRef<number | null>(null);
  const expandedRef = useRef(isExpanded);
  expandedRef.current = isExpanded;
  const DOUBLE_CLICK_MS = 400;
  const CLICK_DELAY_MS = 180;
  const DRAG_THRESHOLD_PX = 4;

  // Track single-click-and-hold-to-drag state
  const pointerDownRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // RAF-throttle drag IPC so fast mouse motion doesn't flood the main process
  const pendingDragRef = useRef<{ x: number; y: number } | null>(null);
  const rafRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    if (typeof window.api?.pillDragStart !== 'function') {
      console.error('[Pill] pillDragStart not available in preload');
      return;
    }

    const el = pillRef.current;
    if (!el) return;

    const flushDrag = () => {
      rafRef.current = null;
      if (pendingDragRef.current && isDraggingRef.current) {
        window.api.pillDragMove(pendingDragRef.current.x, pendingDragRef.current.y);
        pendingDragRef.current = null;
      }
    };

    const scheduleDragMove = (screenX: number, screenY: number) => {
      pendingDragRef.current = { x: screenX, y: screenY };
      if (!rafRef.current) {
        rafRef.current = requestAnimationFrame(flushDrag);
      }
    };

    const startDrag = (e: PointerEvent) => {
      isDraggingRef.current = true;
      if (clickTimerRef.current) {
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      el.setPointerCapture(e.pointerId);
      e.preventDefault();
      window.api.pillDragStart();
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      if ((e.target as HTMLElement).closest('button')) return;

      const now = Date.now();
      pointerDownRef.current = true;
      dragStartRef.current = { x: e.screenX, y: e.screenY };

      if (now - lastMouseDownRef.current < DOUBLE_CLICK_MS && !isDraggingRef.current) {
        // Double-click / double-tap detected — start drag immediately
        startDrag(e);
      }
      lastMouseDownRef.current = now;
    };

    const onPointerMove = (e: PointerEvent) => {
      if (isDraggingRef.current) {
        e.preventDefault();
        scheduleDragMove(e.screenX, e.screenY);
        return;
      }

      // If pointer is down and we've moved past the threshold, start dragging
      // (supports single-click-and-hold to drag)
      if (pointerDownRef.current && !isDraggingRef.current) {
        const dx = Math.abs(e.screenX - dragStartRef.current.x);
        const dy = Math.abs(e.screenY - dragStartRef.current.y);
        if (dx > DRAG_THRESHOLD_PX || dy > DRAG_THRESHOLD_PX) {
          startDrag(e);
          scheduleDragMove(e.screenX, e.screenY);
        }
      }
    };

    const onPointerUp = (e: PointerEvent) => {
      if (e.button !== 0) return;
      pointerDownRef.current = false;

      // Flush any pending drag coordinate before ending so the pill doesn't snap back
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      if (pendingDragRef.current && isDraggingRef.current) {
        window.api.pillDragMove(pendingDragRef.current.x, pendingDragRef.current.y);
        pendingDragRef.current = null;
      }

      if (!isDraggingRef.current) {
        // Queue a single-click toggle (only if we didn't start dragging)
        if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
        clickTimerRef.current = window.setTimeout(() => {
          if (!expandedRef.current) window.api.toggleOverlay();
        }, CLICK_DELAY_MS);
        return;
      }
      isDraggingRef.current = false;
      window.api.pillDragEnd();
    };

    el.addEventListener('pointerdown', onPointerDown);
    el.addEventListener('pointermove', onPointerMove);
    el.addEventListener('pointerup', onPointerUp);

    return () => {
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', onPointerMove);
      el.removeEventListener('pointerup', onPointerUp);
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // Track which edge the pill is on so we can orient vertically on left/right.
  // The edge is sent from main (reliable) instead of inferring from window size
  // (which Linux WMs often don't report correctly for toolbar windows).
  const [pillEdge, setPillEdge] = useState<'top' | 'bottom' | 'left' | 'right'>('bottom');
  useEffect(() => {
    // Subscribe to edge updates from main
    if (typeof window.api?.onPillEdge === 'function') {
      const handler = (edge: string) => {
        if (['top', 'bottom', 'left', 'right'].includes(edge)) {
          setPillEdge(edge as 'top' | 'bottom' | 'left' | 'right');
        }
      };
      window.api.onPillEdge(handler);
    }
    // Query initial edge on mount
    if (typeof window.api?.getPillEdge === 'function') {
      window.api.getPillEdge().then((edge) => {
        if (['top', 'bottom', 'left', 'right'].includes(edge)) {
          setPillEdge(edge as 'top' | 'bottom' | 'left' | 'right');
        }
      }).catch(() => { /* ignore */ });
    }
  }, []);
  const isVertical = !isExpanded && (pillEdge === 'left' || pillEdge === 'right');
  // Horizontal: 60×18  |  Vertical (left/right): 18×60
  const pillW = isExpanded ? '100%' : (isVertical ? PILL_VISUAL_H : PILL_VISUAL_W);
  const pillH = isExpanded ? '100%' : (isVertical ? PILL_VISUAL_W : PILL_VISUAL_H);

  const handlers = useMemo(
    () => ({
      saveTask: () => {
        setFlashState('success');
        dismissNotification();
      },
      declineTask: async (task: Task) => {
        try {
          await window.api.undoTaskSave(task.id);
        } finally {
          setFlashState('error');
          dismissNotification();
        }
      },
      editTask: async (task: Task) => {
        try {
          await window.api.openTaskPanel(task);
        } finally {
          dismissNotification();
        }
      },
      rescheduleTask: async (id: string) => {
        await window.api.rescheduleTask(id);
        // Remove from active due_alert list; dismiss when empty.
        updateActiveNotification((current) => {
          if (current.kind !== 'due_alert') return current;
          const remaining = current.payload.tasks.filter((t) => t.id !== id);
          if (!remaining.length) return null;
          return {
            kind: 'due_alert',
            payload: { tasks: remaining, count: remaining.length },
          };
        });
      },
      dismissDueAlertAll: async () => {
        const current = activeNotification;
        if (current?.kind === 'due_alert') {
          await Promise.all(
            current.payload.tasks.map((t) => window.api.rescheduleTask(t.id)),
          );
        }
        dismissNotification();
      },
      dismissReminder: () => dismissNotification(),
      dismissOverdueReminder: () => dismissNotification(),
      dismissDuplicate: () => dismissNotification(),
      approveTaskConfirm: (payload: TaskConfirmPayload) => {
        sendBridgeMessage({
          type: 'task_confirm_approve',
          confirm_id: payload.id,
        });
        setFlashState('success');
        dismissNotification();
      },
      rejectTaskConfirm: () => {
        dismissNotification();
      },
      editTaskConfirm: (payload: TaskConfirmPayload) => {
        dismissNotification();
        window.api.openOverlayToTasksEdit({
          prefillTitle: payload.parsed_title,
          prefillDue: payload.due_datetime,
          tempId: payload.id,
        });
      },
      openTaskNotification: (payload: PillNotificationPayload) => {
        dismissNotification();
        window.api.showOverlay();
        window.api.openOverlayToTasksEdit({
          prefillTitle: payload.title,
          taskId: payload.task_id,
          scrollToTask: true,
        });
      },
      snoozeTask: (id: string, minutes: number) => {
        sendBridgeMessage({ type: 'tasks/snooze', task_id: id, minutes });
        setFlashState('success');
        dismissNotification();
      },
      toggleTaskDone: (id: string) => {
        sendBridgeMessage({ type: 'tasks/toggle_status', task_id: id });
        setFlashState('success');
        dismissNotification();
      },
      openTaskById: (id: string, title: string) => {
        dismissNotification();
        window.api.showOverlay();
        window.api.openOverlayToTasksEdit({
          prefillTitle: title,
          taskId: id,
          scrollToTask: true,
        });
      },
    }),
    [activeNotification, dismissNotification, updateActiveNotification],
  );

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
        userSelect: 'none',
        pointerEvents: 'none',
      }}
    >
      <motion.div
        ref={pillRef}
        onContextMenu={handleContextMenu}
        animate={{
          scale: isFlashing ? 1.08 : (glowActive && !isExpanded ? 1.06 : 1),
          boxShadow: isFlashing
            ? `0 0 8px 4px ${flashGlow}`
            : (glowActive && !isExpanded
              ? `0 0 8px 3px ${glow}`
              : 'none'),
          background: isDictationPreviewActive || isNotificationActive
            ? 'rgba(18,18,24,0.96)'
            : isNoticeExpanded
              ? noticeBg(notice!.kind)
              : isFlashing
                ? flashBg
                : capsuleBg,
        }}
        transition={
          isFlashing
            ? { type: 'spring', stiffness: 400, damping: 15 }
            : glowActive && !isExpanded
              ? { duration: 1.2, ease: 'easeInOut' }
              : { type: 'tween', duration: 0.28 }
        }
        style={{
          width: pillW,
          height: pillH,
          borderRadius: isExpanded ? 14 : 999,
          border: `1px solid ${
            isNotificationActive
              ? 'rgba(196,149,106,0.6)'
              : isNoticeExpanded
                ? noticeAccent(notice!.kind)
                : isFlashing
                  ? flashColor
                  : capsuleBorder
          }`,
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          display: 'flex',
          alignItems: isDictationPreviewActive || isNotificationActive ? 'stretch' : 'center',
          justifyContent: isExpanded ? 'flex-start' : 'center',
          cursor: isExpanded ? 'default' : 'pointer',
          overflow: isVertical ? 'visible' : 'hidden',
          padding: isDictationPreviewActive || isNotificationActive ? 0 : isNoticeExpanded ? '6px 12px' : 0,
          pointerEvents: 'auto',
          touchAction: 'none',
        }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isDictationPreviewActive ? (
            <motion.div
              key="dictation-preview"
              initial={{ opacity: 0, scale: 0.92, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              transition={{ type: 'spring', stiffness: 350, damping: 25 }}
              onClick={(event) => event.stopPropagation()}
              style={{ width: '100%', height: '100%', display: 'flex' }}
            >
              <DictationPreviewInline
                id={dictationPreview!.id}
                originalText={dictationPreview!.originalText}
                initialText={dictationPreview!.text}
                sessionId={dictationPreview!.sessionId}
                onClose={() => setDictationPreview(null)}
                onSave={() => setDictationPreview(null)}
              />
            </motion.div>
          ) : isNotificationActive ? (
            <motion.div
              key="pill-notification"
              initial={{ opacity: 0, scale: 0.92, x: -10 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.96, x: 10 }}
              transition={{ type: 'spring', stiffness: 350, damping: 25 }}
              onClick={(event) => event.stopPropagation()}
              style={{ width: '100%', height: '100%', display: 'flex' }}
            >
              {snoozePayload ? (
                <SnoozeOptions
                  onSnooze={(minutes) => {
                    sendBridgeMessage({ type: 'tasks/snooze', task_id: snoozePayload.task_id, minutes });
                    dismissNotification();
                    setSnoozePayload(null);
                  }}
                  onCancel={() => setSnoozePayload(null)}
                />
              ) : (
                <NotificationRenderer
                  notification={activeNotification!}
                  compact
                  handlers={handlers}
                  onNotificationBodyClick={() => {
                    if (activeNotification?.kind === 'pill_notification') {
                      setSnoozePayload(activeNotification.payload);
                    }
                  }}
                />
              )}
            </motion.div>
          ) : isNoticeExpanded ? (
            <motion.div
              key="notice"
              initial={{ opacity: 0, x: -12, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 8, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 400, damping: 28 }}
            >
              <PillNotice payload={notice!} />
            </motion.div>
          ) : (
            <motion.div
              key="indicator"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <div
                style={{
                  transform: isVertical ? 'rotate(90deg)' : undefined,
                  transformOrigin: 'center',
                }}
              >
                <PillIndicator
                  state={state}
                  color={color}
                  micLevels={levels}
                  simulatedLevels={simulatedLevels}
                  agentStatus={agentStatus}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

function PillNotice({ payload }: { payload: PillNoticePayload }) {
  const accent = noticeAccent(payload.kind);
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 8 }}
      transition={{ duration: 0.22 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        width: '100%',
        height: '100%',
      }}
    >
      <motion.div
        animate={{ scale: [0.8, 1.15, 1], opacity: [0.6, 1, 1] }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        style={{
          flex: '0 0 auto',
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: accent,
          boxShadow: `0 0 8px ${accent}`,
        }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
        <div
          style={{
            color: 'rgba(255,255,255,0.95)',
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 1.2,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontFamily:
              'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          }}
        >
          {payload.title || ''}
        </div>
        {payload.summary ? (
          <div
            style={{
              color: 'rgba(255,255,255,0.55)',
              fontSize: 10.5,
              fontWeight: 400,
              lineHeight: 1.25,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              marginTop: 2,
              fontFamily:
                'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
            }}
          >
            {payload.summary}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

function AgentStatusBlob({ status }: { status: 'idle' | 'active' | 'working' | 'error' }) {
  if (status === 'idle') return null;

  const colors = {
    active: AGENT_BLUE,
    working: GREEN,
    error: RED,
  };

  const c = colors[status];

  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{
        scale: [1, 1.35, 1],
        opacity: [0.7, 1, 0.7],
      }}
      transition={{
        scale: { repeat: Infinity, duration: 1.2, ease: 'easeInOut' },
        opacity: { repeat: Infinity, duration: 1.2, ease: 'easeInOut' },
      }}
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: c,
        boxShadow: `0 0 6px 2px ${c.replace('0.95', '0.45')}`,
        marginRight: 2,
      }}
    />
  );
}

function StopButton({ onClick }: { onClick: (e: ReactMouseEvent<HTMLButtonElement>) => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title="Stop"
      style={{
        width: 14,
        height: 14,
        borderRadius: 3,
        background: '#EF4444',
        border: '1px solid rgba(255,255,255,0.35)',
        cursor: 'pointer',
        padding: 0,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'auto',
        position: 'relative',
        zIndex: 2,
      }}
    >
      <div
        style={{
          width: 6,
          height: 6,
          borderRadius: 1,
          background: 'rgba(255,255,255,0.95)',
        }}
      />
    </button>
  );
}

function PillIndicator({
  state,
  color,
  micLevels,
  simulatedLevels,
  agentStatus,
}: {
  state: AppState;
  color: string;
  micLevels: number[];
  simulatedLevels: number[];
  agentStatus: 'idle' | 'active' | 'working' | 'error';
}) {
  if (state === 'idle') {
    return (
      <motion.div
        animate={{ scale: [1, 1.25, 1], opacity: [0.75, 1, 0.75] }}
        transition={{ repeat: Infinity, duration: 2.2, ease: 'easeInOut' }}
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: color,
        }}
      />
    );
  }

  if (state === 'recording') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        <Bars values={micLevels} color={color} maxH={MAX_BAR_H} />
        <StopButton
          onClick={(e) => {
            e.stopPropagation();
            window.api.stopRecording();
          }}
        />
      </div>
    );
  }

  if (state === 'thinking') {
    return (
      <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.15, 0.8] }}
            transition={{ repeat: Infinity, duration: 1.05, delay: i * 0.22 }}
            style={{ width: 4, height: 4, borderRadius: '50%', background: color }}
          />
        ))}
      </div>
    );
  }

  if (state === 'speaking') {
    return (
      <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        {[0, 1, 2, 3].map((i) => (
          <motion.div
            key={i}
            animate={{ scaleY: [0.35, 1, 0.35] }}
            transition={{
              repeat: Infinity,
              duration: 0.55,
              delay: i * 0.09,
              ease: 'easeInOut',
            }}
            style={{
              width: 2.5,
              height: MAX_BAR_H,
              borderRadius: 2,
              background: color,
              transformOrigin: 'center',
            }}
          />
        ))}
      </div>
    );
  }

  if (state === 'agent') {
    // Use real mic levels if available (agent might be recording user voice),
    // otherwise fall back to simulated bars so the pill stays animated.
    const values = micLevels.some((v) => v > 0.05) ? micLevels : simulatedLevels;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        <AgentStatusBlob status={agentStatus} />
        <Bars values={values} color={color} maxH={MAX_BAR_H} />
        <StopButton
          onClick={(e) => {
            e.stopPropagation();
            window.api.stopRecording();
          }}
        />
      </div>
    );
  }

  return null;
}

/**
 * Voice-reactive bar group. `values` are 0..1 from `useMicLevels`.
 * We apply a gentle floor (so bars are never invisible) and a ceiling
 * so a loud spike doesn't clip outside the pill.
 */
function Bars({
  values,
  color,
  maxH,
}: {
  values: number[];
  color: string;
  maxH: number;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 2,
        alignItems: 'center',
        justifyContent: 'center',
        height: maxH,
      }}
    >
      {values.map((v, i) => {
        // Shape the curve: sqrt makes quiet speech visible without letting
        // loud peaks dominate. Multiplied by 2 so normal speech comfortably
        // fills the bar range before clamping.
        const shaped = Math.sqrt(Math.min(1, v * 2));
        const h = Math.max(2, Math.min(maxH, shaped * maxH));
        return (
          <motion.div
            key={i}
            animate={{ height: h }}
            transition={{ duration: 0.06, ease: 'linear' }}
            style={{
              width: 2.5,
              borderRadius: 2,
              background: color,
            }}
          />
        );
      })}
    </div>
  );
}
