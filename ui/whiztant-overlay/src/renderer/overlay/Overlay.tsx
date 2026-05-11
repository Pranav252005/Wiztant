import {
  useEffect,
  useMemo,
  useCallback,
  useRef,
  useState,
  CSSProperties,
  createContext,
  useContext,
} from 'react';
import { motion, AnimatePresence, useAnimation } from 'framer-motion';
import { themes, defaultTheme, type Theme } from '../shared/themes';
import type { ThemeName } from '../shared/ipc';
import TopTabBar from './TopTabBar';
import TopTabContent from './TopTabContent';
import TasksPanel, { type TaskHistoryItem, type TaskItem, type SortMode } from './TasksPanel';
import AgentPanel from './AgentPanel';
import WizPromptPanel from './WizPromptPanel';
import MemoriesPanel, { type DictationMemory } from './MemoriesPanel';
import TuneHubPanel from './TuneHubPanel';
import VocabCorrectModal from './VocabCorrectModal';
import { ProjectBuilderPanel } from './ProjectBuilderPanel';

import { sendBridgeMessage, useBridgeConnected, useBridgeMessage } from '../shared/useBridge';
import { usePillNotifications, type PillNotification } from '../shared/usePillNotifications';
import NotificationRenderer from '../shared/notifications/NotificationRenderer';
import { useCreditToasts, CreditToastContainer } from '../shared/CreditToast';
import type { Task } from '../shared/ipc';
import { useTopTabNav, type TopTabId } from './useTopTabNav';
import { readFeatureFlags, writeFeatureFlags, type FeatureFlags, type FeatureKey } from '../settings/Settings';
import { useTasks } from './useTasks';
import Settings from '../settings/Settings';
import { useCredits } from '../shared/useCredits';
import type { SettingsTab } from '../settings/Settings';



type ReminderBanner = {
  id: string;
  title: string;
  detail: string;
  tone: 'info' | 'warning' | 'danger';
};


function CreditBadge({ theme, onClick }: { theme: Theme['panel']; onClick: () => void }) {
  const credits = useCredits();

  const tierColor =
    credits.tier === 'power'
      ? '#C4956A'
      : credits.tier === 'pro'
        ? '#c0c1ff'
        : '#6b7280';

  return (
    <button
      onClick={onClick}
      title={`${credits.balance.toLocaleString()} / ${credits.allocation.toLocaleString()} credits`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 10px',
        borderRadius: 999,
        border: `1px solid ${theme.border}`,
        background: 'transparent',
        cursor: 'pointer',
        fontFamily: 'inherit',
        flexShrink: 0,
        ...( { WebkitAppRegion: 'no-drag' } as any ),
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = tierColor;
        e.currentTarget.style.background = `${tierColor}12`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = theme.border;
        e.currentTarget.style.background = 'transparent';
      }}
    >
      <span style={{ fontSize: 12, lineHeight: 1 }}>◆</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: theme.text, lineHeight: 1 }}>
        {credits.balance.toLocaleString()}
      </span>
      <span style={{ fontSize: 10, color: theme.textMuted, lineHeight: 1 }}>
        /{credits.allocation.toLocaleString()}
      </span>
    </button>
  );
}

function setTopTab(tab: TopTabId, setTab: (tab: TopTabId) => void) {
  setTab(tab);
  localStorage.setItem('wiz-top-tab', tab);
}

function notificationBorder(n: PillNotification): string {
  if (n.kind === 'due_alert') return '#EF4444';
  if (n.kind === 'due_reminder' || n.kind === 'duplicate') return 'rgba(196,149,106,0.7)';
  return 'rgba(196,149,106,0.7)';
}

function notificationBg(n: PillNotification): string {
  if (n.kind === 'due_alert') return '#1C0A0A';
  return 'rgba(18,18,24,0.94)';
}

function formatTaskDue(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function getTaskProgress(task: TaskItem, nowMs: number) {
  if (!task.due_at || task.status === 'done') return null;
  const createdMs = new Date(task.created_at).getTime();
  const dueMs = new Date(task.due_at).getTime();
  if (Number.isNaN(createdMs) || Number.isNaN(dueMs) || dueMs <= createdMs) return null;
  return { halfwayMs: createdMs + (dueMs - createdMs) / 2, dueMs, nowMs };
}

export default function Overlay() {
  // ── Theme ───────────────────────────────────────────────
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const theme = themes[themeName].panel;
  const bridgeConnected = useBridgeConnected();
  const [activeTopTab, setActiveTopTab] = useState<TopTabId>(() => {
    const stored = localStorage.getItem('wiz-top-tab');
    return stored === 'agent' || stored === 'builder' || stored === 'tasks' || stored === 'chat' || stored === 'wizprompt' || stored === 'memories' ? stored : 'chat';
  });
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [taskHistory, setTaskHistory] = useState<TaskHistoryItem[]>([]);
  const [taskSuggestion, setTaskSuggestion] = useState<string | null>(null);
  const [taskBanner, setTaskBanner] = useState<ReminderBanner | null>(null);
  const [dictationMemories, setDictationMemories] = useState<DictationMemory[]>([]);
  const pillNotifications = usePillNotifications();
  const activeNotification = pillNotifications.active;
  const dismissNotification = pillNotifications.dismiss;
  const updateActiveNotification = pillNotifications.updateActive;
  const announcedRemindersRef = useRef<Set<string>>(new Set());
  const previousTasksRef = useRef<TaskItem[]>([]);
  const tasksState = useTasks(tasks, taskHistory);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<SettingsTab | undefined>(undefined);
  const creditToasts = useCreditToasts();

  // ── Process tracking for tab indicators ───────────────────
  type ProcessStatus = 'idle' | 'active' | 'completed' | 'error';
  const [processes, setProcesses] = useState<Record<string, ProcessStatus>>({
    wizprompt: 'idle',
    tunehub: 'idle',
    agent: 'idle',
  });
  const updateProcess = useCallback((id: string, status: ProcessStatus) => {
    setProcesses((prev) => ({ ...prev, [id]: status }));
  }, []);
  const [features, setFeatures] = useState<FeatureFlags>(() => readFeatureFlags());
  const [memoriesFilter, setMemoriesFilter] = useState<DictationMemory['mode'] | 'all'>('all');
  const [tasksSortMode, setTasksSortMode] = useState<SortMode>('smart');
  const [taskCategories, setTaskCategories] = useState<string[]>([]);
  const [wizPromptPreloaded, setWizPromptPreloaded] = useState<{
    original: string;
    optimized: string;
    agent_count: number;
    emotion: string | null;
    critiques: {
      structure?: string;
      semantic?: string;
      edge_case?: string;
      emotional?: string;
    };
    line_count?: number;
    prompt_size?: string;
    framing_directive?: string | null;
    synthesis_failed?: boolean;
    examples_used?: number;
    example_ids?: number[];
  } | null>(null);
  const [taskPrefill, setTaskPrefill] = useState<Record<string, unknown> | null>(null);
  const [repromptPendingText, setRepromptPendingText] = useState<string | null>(null);

  useEffect(() => {
    window.api.onShowSettings(() => setShowSettings(true));
    window.api.onHideSettings(() => setShowSettings(false));
  }, []);

  // Listen for navigate-to-tasks-edit from main process (pill edit flow)
  useEffect(() => {
    const handler = (data: Record<string, unknown>) => {
      setTopTab('tasks', setActiveTopTab);
      setShowSettings(false);
      setTaskPrefill(data);
    };
    window.api.onNavigateToTasksEdit(handler);
    return () => window.api.onNavigateToTasksEdit(handler);
  }, []);

  // ── Effects ─────────────────────────────────────────────
  const handleBridgeMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (msg.type === 'tasks/update') {
        setTasks(Array.isArray(msg.payload) ? (msg.payload as TaskItem[]) : []);
        setTaskHistory(Array.isArray(msg.history) ? (msg.history as TaskHistoryItem[]) : []);
        setTaskSuggestion(typeof msg.suggestion === 'string' ? msg.suggestion : null);
        if (Array.isArray(msg.categories)) {
          setTaskCategories(msg.categories as string[]);
        }
      } else if (msg.type === 'tasks_failed') {
        void tasksState.refresh();
      } else if (msg.type === 'wizprompt_result') {
        setRepromptPendingText(null);
        setWizPromptPreloaded({
          original: String(msg.original ?? ''),
          optimized: String(msg.optimized ?? ''),
          agent_count: Number(msg.agent_count ?? 0),
          emotion: msg.emotion ? String(msg.emotion) : null,
          critiques: msg.critiques && typeof msg.critiques === 'object' ? (msg.critiques as any) : {},
          line_count: Number(msg.line_count ?? 0),
          prompt_size: String(msg.prompt_size ?? 'unknown'),
          framing_directive: msg.framing_directive ? String(msg.framing_directive) : null,
          synthesis_failed: Boolean(msg.synthesis_failed),
          examples_used: Number(msg.examples_used ?? 0),
          example_ids: Array.isArray(msg.example_ids) ? (msg.example_ids as number[]) : [],
        });
        setTopTab('wizprompt', setActiveTopTab);
        window.api.showOverlay();
      } else if (msg.type === 'reprompt_init') {
        const capturedText = String(msg.text ?? '');
        setWizPromptPreloaded(null);
        setRepromptPendingText(capturedText);
        setTopTab('wizprompt', setActiveTopTab);
        window.api.showOverlay();
        // Notify backend that the Reprompt tab is open and visible
        setTimeout(() => {
          sendBridgeMessage({ type: 'reprompt_ready' });
        }, 150);
      } else if (msg.type === 'dictation_memories/update') {
        const incoming = Array.isArray(msg.memories) ? (msg.memories as DictationMemory[]) : [];
        setDictationMemories((prev) => {
          const map = new Map(prev.map((m) => [m.id, m]));
          for (const m of incoming) {
            map.set(m.id, m);
          }
          return Array.from(map.values()).sort(
            (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
          );
        });
      } else if (msg.type === 'features/update') {
        const updated = msg.features as Partial<FeatureFlags> | undefined;
        if (updated) {
          setFeatures((prev) => {
            const next = { ...prev, ...updated };
            writeFeatureFlags(next);
            return next;
          });
        }
      }
      // due_alert / due_reminder / task_duplicate / task_saved (as pill
      // notification) are all handled by `usePillNotifications` and rendered
      // via the shared NotificationRenderer at the top of the overlay.
    },
    [tasksState],
  );

  useBridgeMessage(handleBridgeMessage);

  useEffect(() => {
    window.api.onThemeChanged((n) => setThemeName(n));
  }, []);

  // ── Warp entrance animation (plays on every show) ───────
  // The overlay window is always mounted (we just hide/show the BrowserWindow),
  // so we replay the animation on every `focus` event — the main process calls
  // overlay.show() + overlay.focus() when Ctrl+Space is pressed or the pill is clicked.
  const warpControls = useAnimation();
  useEffect(() => {
    const play = () => {
      warpControls.set({ scale: 0.82, opacity: 0 });
      warpControls.start({
        scale: 1,
        opacity: 1,
        transition: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
      });
    };
    play();
    window.addEventListener('focus', play);
    return () => window.removeEventListener('focus', play);
  }, [warpControls]);

  useTopTabNav(activeTopTab, (tab) => {
    setTopTab(tab, setActiveTopTab);
  });

  // Redirect to a valid tab if the active tab's feature was disabled
  useEffect(() => {
    if (activeTopTab === 'agent' && !features.agent) {
      setTopTab('chat', setActiveTopTab);
    } else if (activeTopTab === 'tasks' && !features.tasks) {
      setTopTab('chat', setActiveTopTab);
    } else if (activeTopTab === 'wizprompt' && !features.reprompt) {
      setTopTab('chat', setActiveTopTab);
    }
  }, [activeTopTab, features]);

  // Request dictation memories on mount and whenever the bridge reconnects
  useEffect(() => {
    if (bridgeConnected) {
      sendBridgeMessage({ type: 'dictation_memories/get', limit: 50 });
      sendBridgeMessage({ type: 'features/get' });
    }
  }, [bridgeConnected]);


  useEffect(() => {
    if (previousTasksRef.current.length === 0 && tasksState.tasks.length > 0) {
      previousTasksRef.current = tasksState.tasks;
      return;
    }
    const previousById = new Map(previousTasksRef.current.map((task) => [task.id, task]));
    const addedVoiceTask = tasksState.tasks.find((task) => !previousById.has(task.id) && task.source === 'voice');
    if (addedVoiceTask) {
      setTopTab('tasks', setActiveTopTab);
      setTaskBanner({
        id: `added-${addedVoiceTask.id}`,
        title: 'Added to Today',
        detail: addedVoiceTask.due_at
          ? `${addedVoiceTask.text} · due ${formatTaskDue(addedVoiceTask.due_at)}`
          : addedVoiceTask.text,
        tone: 'info',
      });
    }
    previousTasksRef.current = tasksState.tasks;
  }, [tasksState.tasks]);

  useEffect(() => {
    const scanTasks = () => {
      const nowMs = Date.now();
      for (const task of tasksState.tasks) {
        const progress = getTaskProgress(task, nowMs);
        if (!progress) continue;

        const overdueKey = `${task.id}:due`;
        if (nowMs >= progress.dueMs && !announcedRemindersRef.current.has(overdueKey)) {
          announcedRemindersRef.current.add(overdueKey);
          setTaskBanner({
            id: overdueKey,
            title: 'Task due now',
            detail: `${task.text} · due ${formatTaskDue(task.due_at)}`,
            tone: 'danger',
          });
          return;
        }

        const halfwayKey = `${task.id}:half`;
        if (nowMs >= progress.halfwayMs && !announcedRemindersRef.current.has(halfwayKey)) {
          announcedRemindersRef.current.add(halfwayKey);
          setTaskBanner({
            id: halfwayKey,
            title: 'Halfway reminder',
            detail: `${task.text} · due ${formatTaskDue(task.due_at)}`,
            tone: 'warning',
          });
          return;
        }
      }
    };

    scanTasks();
    const interval = window.setInterval(scanTasks, 15000);

    return () => window.clearInterval(interval);
  }, [tasks]);

  useEffect(() => {
    if (!taskBanner) return;
    const timer = window.setTimeout(() => setTaskBanner((current) => (
      current?.id === taskBanner.id ? null : current
    )), 4500);
    return () => window.clearTimeout(timer);
  }, [taskBanner]);

  // ── Actions ─────────────────────────────────────────────


  // ── Render ──────────────────────────────────────────────
  return (
    <motion.div
      animate={warpControls}
      initial={{ scale: 0.82, opacity: 0 }}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: theme.bg,
        border: `1px solid ${theme.border}`,
        borderRadius: 16,
        backdropFilter: 'blur(40px)',
        WebkitBackdropFilter: 'blur(40px)',
        overflow: 'hidden',
        fontFamily: 'Geist, "Segoe UI", sans-serif',
        color: theme.text,
        // Warp origin: bottom-center so the overlay grows up out of the pill.
        transformOrigin: '50% 100%',
      }}
    >
      {/* Overlay content — always mounted, hidden via CSS when Settings open */}
      <div style={{ display: showSettings ? 'none' : 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
        <VocabCorrectModal theme={theme} />

        {/* ── Header + Tab strip ──────────────────────────── */}
        {/* ── Header ──────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 10px",
            background: theme.headerBg,
            borderBottom: `1px solid ${theme.border}`,
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => { setSettingsInitialTab(undefined); setShowSettings(true); }}
            title="Settings"
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              border: `1px solid ${theme.border}`,
              background: "transparent",
              color: theme.textMuted,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              fontFamily: "inherit",
              ...( { WebkitAppRegion: "no-drag" } as any ),
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = theme.text;
              e.currentTarget.style.background = `${theme.aiAccent}12`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = theme.textMuted;
              e.currentTarget.style.background = "transparent";
            }}
          >
            <GearIcon />
          </button>

          <CreditBadge theme={theme} onClick={() => { setSettingsInitialTab('credits'); setShowSettings(true); }} />

          <button
            onClick={() => window.api.toggleOverlay()}
            title="Minimize to pill (Esc)"
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              border: `1px solid ${theme.border}`,
              background: "transparent",
              color: theme.textMuted,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              fontFamily: "inherit",
              fontSize: 12,
              lineHeight: 1,
              ...( { WebkitAppRegion: "no-drag" } as any ),
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
            onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
          >
            −
          </button>
        </div>

        <TopTabBar
          active={activeTopTab}
          onChange={(tab) => setTopTab(tab, setActiveTopTab)}
          theme={theme}
          enabledFeatures={features}
          processes={processes}
        />

        {activeNotification ? (
          <div
            style={{
              margin: '8px 12px 0',
              borderRadius: 12,
              border: `1px solid ${notificationBorder(activeNotification)}`,
              background: notificationBg(activeNotification),
              overflow: 'hidden',
              flexShrink: 0,
            }}
          >
            <NotificationRenderer
              notification={activeNotification}
              handlers={{
                saveTask: () => dismissNotification(),
                declineTask: async (task: Task) => {
                  try {
                    await window.api.undoTaskSave(task.id);
                  } finally {
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
                  await tasksState.rescheduleTask(id);
                  updateActiveNotification((current) => {
                    if (current.kind !== 'due_alert') return current;
                    const remaining = current.payload.tasks.filter((t) => t.id !== id);
                    if (!remaining.length) return null;
                    return { kind: 'due_alert', payload: { tasks: remaining, count: remaining.length } };
                  });
                },
                dismissDueAlertAll: async () => {
                  if (activeNotification?.kind === 'due_alert') {
                    await Promise.all(
                      activeNotification.payload.tasks.map((t) => tasksState.rescheduleTask(t.id)),
                    );
                  }
                  dismissNotification();
                },
                dismissReminder: () => dismissNotification(),
                dismissDuplicate: () => dismissNotification(),
                approveTaskConfirm: () => dismissNotification(),
                rejectTaskConfirm: () => dismissNotification(),
                editTaskConfirm: () => dismissNotification(),
                openTaskNotification: () => dismissNotification(),
              }}
            />
          </div>
        ) : null}

        <AnimatePresence initial={false}>
          {taskBanner ? (
            <motion.div
              key={taskBanner.id}
              initial={{ opacity: 0, y: -18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -18 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              style={{
                margin: '8px 12px 0',
                padding: '10px 12px',
                borderRadius: 12,
                border: `1px solid ${
                  taskBanner.tone === 'danger'
                    ? `${theme.text}55`
                    : taskBanner.tone === 'warning'
                      ? `${theme.aiAccent}66`
                      : theme.border
                }`,
                background: theme.headerBg,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                flexShrink: 0,
              }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: theme.text }}>
                {taskBanner.title}
              </span>
              <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.5 }}>
                {taskBanner.detail}
              </span>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <TopTabContent
          activeTab={activeTopTab}
          wizprompt={features.reprompt ? <WizPromptPanel theme={theme} preloaded={wizPromptPreloaded} pendingText={repromptPendingText} onProcessChange={(s) => updateProcess('wizprompt', s)} /> : null}
          agent={features.agent ? <AgentPanel theme={theme} onProcessChange={(s) => updateProcess('agent', s)} /> : null}
          tasks={features.tasks ? (
            <TasksPanel
              theme={theme}
              active={activeTopTab === 'tasks'}
              tasks={tasksState.tasks}
              history={tasksState.history}
              suggestion={taskSuggestion}
              loading={tasksState.loading}
              onOpenPanel={tasksState.openPanel}
              onMarkDone={async (id) => {
                await tasksState.markDone(id);
              }}
              onDeleteTask={async (id) => {
                await tasksState.deleteTask(id);
              }}
              onTaskAdded={() => setTopTab('tasks', setActiveTopTab)}
              sortMode={tasksSortMode}
              onSortChange={setTasksSortMode}
              prefill={taskPrefill}
              onPrefillConsumed={() => setTaskPrefill(null)}
              categories={taskCategories}
              onAddCategory={(name) => sendBridgeMessage({ type: 'tasks/add_category', name })}
              onDropTask={(taskId, category) => sendBridgeMessage({ type: 'tasks/edit', task_id: taskId, fields: { category } })}
            />
          ) : null}
          memories={<MemoriesPanel theme={theme} memories={dictationMemories} filter={memoriesFilter} onFilterChange={setMemoriesFilter} />}
          chat={<TuneHubPanel theme={theme} onProcessChange={(s) => updateProcess('tunehub', s)} />}
          builder={<ProjectBuilderPanel />}
        />
      </div>

      {/* Settings overlay — renders on top without unmounting underlying content */}
      {showSettings && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 10, display: 'flex', flexDirection: 'column' }}>
          <Settings onBack={() => setShowSettings(false)} initialTheme={themeName} initialTab={settingsInitialTab} />
        </div>
      )}

      {/* Credit consumption toasts */}
      <CreditToastContainer toasts={creditToasts} />
    </motion.div>
  );
}

// ─── Icons ────────────────────────────────────────────────
// Inline SVGs keep the bundle tiny and avoid adding an icon-pack dependency.

function GearIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8 3.4 3.4"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}


