import {
  useEffect,
  useMemo,
  useCallback,
  useRef,
  useState,
  ChangeEvent,
  KeyboardEvent,
  CSSProperties,
  ReactNode,
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
import { sendBridgeMessage, useBridgeConnected, useBridgeMessage } from '../shared/useBridge';
import { usePillNotifications, type PillNotification } from '../shared/usePillNotifications';
import NotificationRenderer from '../shared/notifications/NotificationRenderer';
import type { Task } from '../shared/ipc';
import { useTopTabNav, type TopTabId } from './useTopTabNav';
import { readFeatureFlags, writeFeatureFlags, type FeatureFlags, type FeatureKey } from '../settings/Settings';
import { useTasks } from './useTasks';
import Settings from '../settings/Settings';

// ─── Types ──────────────────────────────────────────────────────
type Message = { role: 'user' | 'ai'; text: string; id: string };

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
};

type Chip = { id: string; label: string };

const SUGGESTIONS = [
  "When I say 'excell' I mean Excel",
  'Remember I prefer dark mode',
  'Add keyword: ticket = Jira issue',
  'I work from 9 AM to 5 PM PST',
];

let idCounter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${idCounter++}`;

const newConversation = (title = 'New tune'): Conversation => ({
  id: nextId('conv'),
  title,
  messages: [],
  updatedAt: Date.now(),
});

function mapBridgeHistory(messages: unknown): Message[] {
  if (!Array.isArray(messages)) return [];
  return messages
    .map((entry) => {
      const role = entry && typeof entry === 'object' ? (entry as Record<string, unknown>).role : '';
      const content = entry && typeof entry === 'object' ? (entry as Record<string, unknown>).content : '';
      if (role !== 'user' && role !== 'assistant') return null;
      const text = String(content ?? '').trim();
      if (!text) return null;
      return {
        role: role === 'assistant' ? 'ai' : 'user',
        text,
        id: nextId(role === 'assistant' ? 'ai' : 'u'),
      } satisfies Message;
    })
    .filter((entry): entry is Message => Boolean(entry));
}

type ReminderBanner = {
  id: string;
  title: string;
  detail: string;
  tone: 'info' | 'warning' | 'danger';
};


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
  // ── Conversations ────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>(() => [
    newConversation(),
  ]);
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id);
  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? conversations[0],
    [conversations, activeId],
  );

  // ── Composer ────────────────────────────────────────────
  const [input, setInput] = useState('');
  const [chips, setChips] = useState<Chip[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // ── Theme ───────────────────────────────────────────────
  const [themeName, setThemeName] = useState<ThemeName>(defaultTheme);
  const theme = themes[themeName].panel;
  const bridgeConnected = useBridgeConnected();
  const [activeTopTab, setActiveTopTab] = useState<TopTabId>(() => {
    const stored = localStorage.getItem('wiz-top-tab');
    return stored === 'agent' || stored === 'tasks' || stored === 'chat' || stored === 'wizprompt' || stored === 'memories' || stored === 'tunehub' ? stored : 'chat';
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
  const [features, setFeatures] = useState<FeatureFlags>(() => readFeatureFlags());
  const [memoriesFilter, setMemoriesFilter] = useState<DictationMemory['mode'] | 'all'>('all');
  const [tasksSortMode, setTasksSortMode] = useState<SortMode>('smart');
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
  } | null>(null);

  useEffect(() => {
    window.api.onShowSettings(() => setShowSettings(true));
    window.api.onHideSettings(() => setShowSettings(false));
  }, []);

  // ── Refs ────────────────────────────────────────────────
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Effects ─────────────────────────────────────────────
  const handleBridgeMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (msg.type === 'history') {
        const syncedMessages = mapBridgeHistory(msg.messages);
        // Only hydrate from core when the active conversation is empty —
        // avoid overwriting local IPC chat while the user is interacting.
        setConversations((prev) =>
          prev.map((conversation) => {
            if (conversation.id !== activeId) return conversation;
            if (conversation.messages.length > 0) return conversation;
            return {
              ...conversation,
              updatedAt: Date.now(),
              title: syncedMessages[0]?.text.slice(0, 32) || conversation.title,
              messages: syncedMessages,
            };
          }),
        );
        const lastRole = syncedMessages.at(-1)?.role;
        setIsLoading(lastRole === 'user');
      } else if (msg.type === 'wave_state') {
        const stateName = String(msg.state ?? '');
        if (stateName === 'thinking' || stateName === 'agent') {
          setIsLoading(true);
        }
      } else if (msg.type === 'tasks/update') {
        setTasks(Array.isArray(msg.payload) ? (msg.payload as TaskItem[]) : []);
        setTaskHistory(Array.isArray(msg.history) ? (msg.history as TaskHistoryItem[]) : []);
        setTaskSuggestion(typeof msg.suggestion === 'string' ? msg.suggestion : null);
      } else if (msg.type === 'task_saved') {
        const reply = typeof msg.reply === 'string' ? msg.reply : '✓ Saved as task';
        const aiMsg: Message = { role: 'ai', text: reply, id: nextId('ai') };
        setConversations((prev) =>
          prev.map((c) => (c.id === activeId ? { ...c, updatedAt: Date.now(), messages: [...c.messages, aiMsg] } : c)),
        );
        setIsLoading(false);
      } else if (msg.type === 'tasks_failed') {
        void tasksState.refresh();
      } else if (msg.type === 'wizprompt_result') {
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
        });
        setTopTab('wizprompt', setActiveTopTab);
        window.api.showOverlay();
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
    [activeId, tasksState],
  );

  useBridgeMessage(handleBridgeMessage);

  useEffect(() => {
    window.api.onThemeChanged((n) => setThemeName(n));
    inputRef.current?.focus();
  }, []);

  // Handle IPC AI replies from the Electron main process
  useEffect(() => {
    const handler = (text: string) => {
      const aiMsg: Message = { role: 'ai', text: String(text || ''), id: nextId('ai') };
      setConversations((prev) =>
        prev.map((c) => (c.id === activeId ? { ...c, updatedAt: Date.now(), messages: [...c.messages, aiMsg] } : c)),
      );
      setIsLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
    };
    window.api.onAiReply(handler);
    return () => {
      // No off() available — renderer is ephemeral; let it GC on unmount.
    };
  }, [activeId]);

  // ── Warp entrance animation (plays on every show) ───────
  // The overlay window is always mounted (we just hide/show the BrowserWindow),
  // so we replay the animation on every `focus` event — the main process calls
  // overlay.show() + overlay.focus() when Ctrl+Space is pressed or the pill is clicked.
  const warpControls = useAnimation();
  useEffect(() => {
    const play = () => {
      setShowSettings(false);
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
    } else if (activeTopTab === 'tunehub' && !features.tunehub) {
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
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [active.messages, isLoading]);

  // Auto-resize textarea (max 5 lines).
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 110)}px`;
  }, [input]);

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
  const send = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    const attachmentNote =
      chips.length > 0 ? `\n\n(attached: ${chips.map((c) => c.label).join(', ')})` : '';
    const userMsg: Message = {
      role: 'user',
      text: text + attachmentNote,
      id: nextId('u'),
    };
    setConversations((prev) =>
      prev.map((c) =>
        c.id === active.id
          ? {
              ...c,
              title:
                c.messages.length === 0
                  ? text.slice(0, 32) || c.title
                  : c.title,
              updatedAt: Date.now(),
              messages: [...c.messages, userMsg],
            }
          : c,
      ),
    );
    setInput('');
    setChips([]);
    // Detect save-session intent: route to Python via WS bridge, skip OpenAI
    const lower = text.toLowerCase();
    const shouldSaveSession =
      lower.includes('save this for tomorrow') ||
      lower.includes('save for tomorrow') ||
      lower.includes('save session');

    if (shouldSaveSession) {
      setIsLoading(true);
      // Ask Python to persist a large task from recent conversation via WS bridge
      sendBridgeMessage({ type: 'save_session' });
      return;
    }

    setIsLoading(true);
    // Otherwise go through Electron IPC to Tune
    window.api.sendMessage(text);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const addChat = () => {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    setChips([]);
    setInput('');
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const closeChat = (id: string) => {
    setConversations((prev) => {
      const remaining = prev.filter((c) => c.id !== id);
      if (remaining.length === 0) {
        const c = newConversation();
        setActiveId(c.id);
        return [c];
      }
      if (activeId === id) setActiveId(remaining[0].id);
      return remaining;
    });
  };

  const onAttach = () => fileInputRef.current?.click();

  const onFileSelected = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setChips((prev) => [
      ...prev,
      ...files.map((f) => ({ id: nextId('chip'), label: f.name })),
    ]);
    e.target.value = '';
  };

  const removeChip = (id: string) =>
    setChips((prev) => prev.filter((c) => c.id !== id));

  const onSuggestion = (text: string) => {
    setInput(text);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const onVoice = () => {
    // Toggle recording via the pill — F9 shortcut in the main process.
    // TODO: wire a dedicated IPC channel once the voice backend is ready.
    setInput((v) => (v ? v : ''));
    inputRef.current?.focus();
  };

  const canSend = input.trim().length > 0 && !isLoading;
  const shellMessages = active.messages;
  const empty = shellMessages.length === 0 && !isLoading;

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
      {showSettings ? (
        <Settings onBack={() => setShowSettings(false)} initialTheme={themeName} />
      ) : (
        <>
      <VocabCorrectModal theme={theme} />

      {/* ── Header + Tab strip ──────────────────────────── */}
      <TabStrip
        theme={theme}
        tabs={conversations}
        activeId={active.id}
        onSelect={setActiveId}
        onAdd={addChat}
        onClose={closeChat}
        isLoading={isLoading}
        onMinimize={() => window.api.toggleOverlay()}
        onSettings={() => setShowSettings(true)}
      />

      <TopTabBar
        active={activeTopTab}
        onChange={(tab) => setTopTab(tab, setActiveTopTab)}
        theme={theme}
        enabledFeatures={features}
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
        tunehub={
          <>
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              {empty ? (
                <EmptyState
                  theme={theme}
                  onSuggestion={onSuggestion}
                  connected={bridgeConnected}
                  dailyTaskSuggestion={taskSuggestion}
                />
              ) : (
                <AnimatePresence initial={false}>
                  {shellMessages.map((msg) => (
                    <MessageBubble key={msg.id} msg={msg} theme={theme} />
                  ))}
                </AnimatePresence>
              )}

              {isLoading && <TypingDots theme={theme} />}
              <div ref={bottomRef} />
            </div>

            <div
              style={{
                padding: '10px 12px',
                background: theme.headerBg,
                borderTop: `1px solid ${theme.border}`,
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {chips.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {chips.map((c) => (
                    <Chip
                      key={c.id}
                      label={c.label}
                      theme={theme}
                      onRemove={() => removeChip(c.id)}
                    />
                  ))}
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: 6,
                  background: theme.inputBg,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 10,
                  padding: '6px 6px 6px 10px',
                }}
              >
                <IconButton title="Attach file" onClick={onAttach} theme={theme}>
                  <PlusIcon />
                </IconButton>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKey}
                  placeholder={
                    isLoading ? 'Wiztant is updating…' : 'Tell Wiztant what to correct or remember…'
                  }
                  disabled={isLoading}
                  rows={1}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    resize: 'none',
                    outline: 'none',
                    color: theme.text,
                    fontSize: 13,
                    lineHeight: 1.45,
                    fontFamily: 'inherit',
                    padding: '6px 0',
                    maxHeight: 110,
                  }}
                />
                <IconButton title="Voice dictation (F9)" onClick={onVoice} theme={theme}>
                  <MicIcon />
                </IconButton>
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={send}
                  disabled={!canSend}
                  title="Send"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: canSend ? theme.accent : `${theme.accent}33`,
                    color: canSend ? sendButtonInk(theme) : theme.textMuted,
                    border: 'none',
                    cursor: canSend ? 'pointer' : 'not-allowed',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    transition: 'background 0.15s',
                  }}
                >
                  <ArrowUpIcon />
                </motion.button>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    color: theme.textMuted,
                    letterSpacing: '0.02em',
                  }}
                >
                  <kbd style={kbdStyle(theme)}>Ctrl+Space</kbd> to minimize
                </span>
                <span
                  style={{
                    fontSize: 10,
                    color: bridgeConnected ? theme.textMuted : theme.text,
                    opacity: bridgeConnected ? 0.8 : 1,
                  }}
                >
                  {bridgeConnected ? 'Core connected' : 'Waiting for core…'}
                </span>
              </div>
            </div>
          </>
        }
        wizprompt={features.reprompt ? <WizPromptPanel theme={theme} preloaded={wizPromptPreloaded} /> : null}
        agent={features.agent ? <AgentPanel theme={theme} /> : null}
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
          />
        ) : null}
        memories={<MemoriesPanel theme={theme} memories={dictationMemories} filter={memoriesFilter} onFilterChange={setMemoriesFilter} />}
        chat={features.tunehub ? <TuneHubPanel theme={theme} /> : null}
      />

      <input
        ref={fileInputRef}
        type="file"
        multiple
        hidden
        onChange={onFileSelected}
      />
        </>
      )}
    </motion.div>
  );
}

// ─── Subcomponents ───────────────────────────────────────

function TabStrip({
  theme,
  tabs,
  activeId,
  onSelect,
  onAdd,
  onClose,
  isLoading,
  onMinimize,
  onSettings,
}: {
  theme: Theme['panel'];
  tabs: Conversation[];
  activeId: string;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onClose: (id: string) => void;
  isLoading: boolean;
  onMinimize: () => void;
  onSettings: () => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 10px',
        background: theme.headerBg,
        borderBottom: `1px solid ${theme.border}`,
        flexShrink: 0,
        gap: 6,
        // Intentionally no drag region — only the pill is draggable.
      }}
    >
      <button
        onClick={onSettings}
        title="Settings"
        style={{
          width: 26,
          height: 26,
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          background: 'transparent',
          color: theme.textMuted,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontFamily: 'inherit',
          ...( { WebkitAppRegion: 'no-drag' } as any ),
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = theme.text;
          e.currentTarget.style.background = `${theme.aiAccent}12`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = theme.textMuted;
          e.currentTarget.style.background = 'transparent';
        }}
      >
        <GearIcon />
      </button>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          flex: 1,
          overflowX: 'hidden',
        }}
      >
        {tabs.map((tab) => {
          const isActive = tab.id === activeId;
          const isBusy = isLoading && isActive;
          return (
            <button
              key={tab.id}
              onClick={() => onSelect(tab.id)}
              title={tab.title}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 10px',
                background: isActive
                  ? `${theme.aiAccent}15`
                  : 'transparent',
                border: `1px solid ${isActive ? theme.border : 'transparent'}`,
                borderRadius: 7,
                color: isActive ? theme.text : theme.textMuted,
                fontSize: 11,
                fontWeight: isActive ? 600 : 500,
                fontFamily: 'inherit',
                cursor: 'pointer',
                maxWidth: 140,
                flexShrink: 0,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                transition: 'background 0.12s, color 0.12s',
                ...( { WebkitAppRegion: 'no-drag' } as any ),
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: isBusy ? theme.aiAccent : `${theme.aiAccent}55`,
                  flexShrink: 0,
                  animation: isBusy ? 'pulse 1.2s ease-in-out infinite' : undefined,
                }}
              />
              <span
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: 100,
                }}
              >
                {tab.title}
              </span>
              {tabs.length > 1 && (
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    onClose(tab.id);
                  }}
                  style={{
                    marginLeft: 2,
                    opacity: isActive ? 0.6 : 0,
                    transition: 'opacity 0.15s',
                    fontSize: 11,
                    lineHeight: 1,
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.opacity = isActive ? '0.6' : '0')
                  }
                >
                  ×
                </span>
              )}
            </button>
          );
        })}
      </div>

      <button
        onClick={onAdd}
        title="New tune (Ctrl+N)"
        style={{
          width: 26,
          height: 26,
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          background: 'transparent',
          color: theme.textMuted,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontFamily: 'inherit',
          fontSize: 14,
          lineHeight: 1,
          ...( { WebkitAppRegion: 'no-drag' } as any ),
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
        onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
      >
        +
      </button>
      <button
        onClick={onMinimize}
        title="Minimize to pill (Esc)"
        style={{
          width: 26,
          height: 26,
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          background: 'transparent',
          color: theme.textMuted,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontFamily: 'inherit',
          fontSize: 12,
          lineHeight: 1,
          ...( { WebkitAppRegion: 'no-drag' } as any ),
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = theme.text)}
        onMouseLeave={(e) => (e.currentTarget.style.color = theme.textMuted)}
      >
        −
      </button>
    </div>
  );
}

function EmptyState({
  theme,
  onSuggestion,
  connected,
  dailyTaskSuggestion,
}: {
  theme: Theme['panel'];
  onSuggestion: (s: string) => void;
  connected: boolean;
  dailyTaskSuggestion: string | null;
}) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 14,
        padding: 16,
      }}
    >
      <div
        style={{
          fontSize: 13,
          color: theme.text,
          fontWeight: 600,
          letterSpacing: '-0.01em',
        }}
      >
        Tune Hub
      </div>
      <p
        style={{
          color: theme.textMuted,
          fontSize: 12,
          textAlign: 'center',
          lineHeight: 1.6,
          margin: 0,
          maxWidth: 280,
        }}
      >
        Tell Wiztant what to improve, correct, or remember — or press{' '}
        <kbd style={kbdStyle(theme)}>F9</kbd> to dictate. Start with a suggestion below.
      </p>
      {dailyTaskSuggestion ? (
        <p
          style={{
            color: theme.text,
            fontSize: 11,
            textAlign: 'center',
            margin: 0,
            lineHeight: 1.6,
            maxWidth: 280,
          }}
        >
          {dailyTaskSuggestion}
        </p>
      ) : null}
      {!connected && (
        <p
          style={{
            color: theme.text,
            fontSize: 11,
            textAlign: 'center',
            margin: 0,
            opacity: 0.9,
          }}
        >
          Connecting to the local Wiztant core…
        </p>
      )}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          width: '100%',
          maxWidth: 280,
        }}
      >
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggestion(s)}
            style={{
              textAlign: 'left',
              padding: '8px 12px',
              fontSize: 12,
              color: theme.text,
              background: theme.inputBg,
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'background 0.12s, border-color 0.12s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = `${theme.aiAccent}12`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = theme.inputBg;
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg, theme }: { msg: Message; theme: Theme['panel'] }) {
  const isUser = msg.role === 'user';
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      {!isUser && (
        <div
          style={{
            width: 2,
            borderRadius: 2,
            background: theme.aiAccent,
            flexShrink: 0,
            marginRight: 8,
          }}
        />
      )}
      <div
        style={{
          maxWidth: '82%',
          padding: '8px 12px',
          borderRadius: isUser ? '12px 12px 3px 12px' : '12px 12px 12px 3px',
          background: isUser ? theme.userBubble : theme.aiBubble,
          color: isUser ? userBubbleInk(theme) : theme.text,
          fontSize: 13,
          lineHeight: 1.55,
          border: isUser ? 'none' : `1px solid ${theme.border}`,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {msg.text}
      </div>
    </motion.div>
  );
}

function TypingDots({ theme }: { theme: Theme['panel'] }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        paddingLeft: 10,
      }}
    >
      <div
        style={{
          width: 2,
          height: 18,
          borderRadius: 2,
          background: theme.aiAccent,
          marginRight: 6,
        }}
      />
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ repeat: Infinity, duration: 1, delay: i * 0.18 }}
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: theme.aiAccent,
          }}
        />
      ))}
    </motion.div>
  );
}

function Chip({
  label,
  theme,
  onRemove,
}: {
  label: string;
  theme: Theme['panel'];
  onRemove: () => void;
}) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 8px',
        background: `${theme.aiAccent}15`,
        border: `1px solid ${theme.border}`,
        borderRadius: 999,
        fontSize: 11,
        color: theme.text,
        maxWidth: 200,
      }}
    >
      <span
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: 160,
        }}
      >
        {label}
      </span>
      <button
        onClick={onRemove}
        aria-label="Remove attachment"
        style={{
          background: 'transparent',
          border: 'none',
          color: theme.textMuted,
          cursor: 'pointer',
          fontSize: 11,
          lineHeight: 1,
          padding: 0,
        }}
      >
        ×
      </button>
    </motion.span>
  );
}

function IconButton({
  children,
  onClick,
  title,
  theme,
}: {
  children: ReactNode;
  onClick: () => void;
  title: string;
  theme: Theme['panel'];
}) {
  return (
    <motion.button
      whileTap={{ scale: 0.9 }}
      onClick={onClick}
      title={title}
      style={{
        width: 28,
        height: 28,
        borderRadius: 7,
        background: 'transparent',
        border: 'none',
        color: theme.textMuted,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        transition: 'background 0.12s, color 0.12s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = `${theme.aiAccent}15`;
        e.currentTarget.style.color = theme.text;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
        e.currentTarget.style.color = theme.textMuted;
      }}
    >
      {children}
    </motion.button>
  );
}

// ─── Icons ────────────────────────────────────────────────
// Inline SVGs keep the bundle tiny and avoid adding an icon-pack dependency.

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 3v10M3 8h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <rect x="6" y="2" width="4" height="8" rx="2" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4 8a4 4 0 0 0 8 0M8 12v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function ArrowUpIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 12V4M4 8l4-4 4 4"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

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

// ─── Utilities ───────────────────────────────────────────

/** Pick text color on the send button based on theme luminance. */
function sendButtonInk(theme: Theme['panel']): string {
  // Onyx + dark themes use near-white accent → ink should be black.
  // Porcelain uses near-black accent → ink should be white.
  return theme.accent.includes('#0') || theme.accent.includes('rgba(0') ? '#fff' : '#0a0a0a';
}

/** Pick ink color for the user bubble based on its filled background. */
function userBubbleInk(theme: Theme['panel']): string {
  // User bubble is "inverse" — light tint in dark themes, dark in light ones.
  // Keep a dark ink on light bubbles, light ink on dark bubbles.
  const bubble = theme.userBubble;
  const isLight =
    bubble.includes('255,255') ||
    bubble.includes('242,242') ||
    bubble.includes('232,236') ||
    bubble.includes('245,225') ||
    bubble.includes('220,230') ||
    bubble.includes('#fff') ||
    bubble.includes('#F');
  return isLight ? '#0a0a0a' : theme.text;
}

function kbdStyle(t: Theme['panel']): CSSProperties {
  return {
    fontSize: 10,
    color: t.text,
    background: `${t.aiAccent}15`,
    border: `1px solid ${t.border}`,
    borderRadius: 4,
    padding: '1px 6px',
    fontFamily: 'Geist Mono, Consolas, monospace',
    margin: '0 2px',
  };
}
