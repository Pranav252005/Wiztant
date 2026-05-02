import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Theme } from '../shared/themes';
import { sendBridgeMessage, useBridgeMessage } from '../shared/useBridge';

type AgentMsg = {
  id: string;
  role: 'user' | 'agent';
  text: string;
  options?: string[];
  questionId?: string;
};

type AgentState = 'idle' | 'running' | 'done';

let idCounter = 0;
const nextId = () => `a-${Date.now()}-${idCounter++}`;

function mapHistoryToAgentMsgs(messages: unknown): AgentMsg[] {
  if (!Array.isArray(messages)) return [];
  return messages
    .map((entry) => {
      const role =
        entry && typeof entry === 'object'
          ? (entry as Record<string, unknown>).role
          : '';
      const content =
        entry && typeof entry === 'object'
          ? (entry as Record<string, unknown>).content
          : '';
      if (role !== 'user' && role !== 'assistant') return null;
      const text = String(content ?? '').trim();
      if (!text) return null;
      return {
        role: role === 'assistant' ? 'agent' : 'user',
        text,
        id: nextId(),
      } satisfies AgentMsg;
    })
    .filter((entry): entry is AgentMsg => Boolean(entry));
}

type Props = {
  theme: Theme['panel'];
};

export default function AgentPanel({ theme }: Props) {
  const [messages, setMessages] = useState<AgentMsg[]>([]);
  const [input, setInput] = useState('');
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleMessage = useCallback((msg: Record<string, unknown>) => {
    if (msg.type === 'history') {
      const incoming = mapHistoryToAgentMsgs(msg.messages);
      setMessages(incoming);
      const lastRole = incoming.at(-1)?.role;
      if (lastRole === 'agent') {
        setAgentState((prev) => (prev === 'done' ? 'done' : 'running'));
      }
    } else if (msg.type === 'agent/done') {
      setAgentState('done');
    } else if (msg.type === 'agent/step') {
      setAgentState('running');
    } else if (msg.type === 'agent/blocked') {
      setAgentState('idle');
    } else if (msg.type === 'agent/question') {
      const text = String(msg.text ?? '');
      const options = Array.isArray(msg.options) ? msg.options : [];
      const questionId = String(msg.question_id ?? '');
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'agent',
          text,
          options,
          questionId,
        },
      ]);
      setAgentState('idle'); // waiting for user choice
    }
  }, []);

  useBridgeMessage(handleMessage);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentState]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 110)}px`;
  }, [input]);

  const send = () => {
    const text = input.trim();
    if (!text || agentState === 'running') return;
    setInput('');
    setAgentState('running');
    sendBridgeMessage({ type: 'send_agent_task', text });
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const sendOptionResponse = useCallback(
    (questionId: string, option: string) => {
      sendBridgeMessage({
        type: 'agent/answer',
        question_id: questionId,
        choice: option,
      });
      // Render the choice as a user message locally
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'user', text: option },
      ]);
      setAgentState('running');
    },
    []
  );

  const isLoading = agentState === 'running';
  const empty = messages.length === 0 && !isLoading;

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Messages area */}
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
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: theme.textMuted,
              fontSize: 12,
              textAlign: 'center',
            }}
          >
            Tell the agent what to do on your computer.
            <br />
            Example: "Open Chrome and search for Python docs"
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '10px 14px',
                  borderRadius: 12,
                  background: msg.role === 'user' ? theme.userBubble : theme.aiBubble,
                  color: msg.role === 'user' ? userBubbleInk(theme) : theme.text,
                  fontSize: 13,
                  lineHeight: 1.5,
                  border:
                    msg.role === 'user' ? 'none' : `1px solid ${theme.border}`,
                }}
              >
                <div>{msg.text}</div>
                {msg.options && msg.options.length > 0 && msg.questionId && (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                      marginTop: 10,
                    }}
                  >
                    {msg.options.map((opt) => (
                      <button
                        key={opt}
                        onClick={() =>
                          sendOptionResponse(msg.questionId!, opt)
                        }
                        disabled={agentState === 'running'}
                        style={{
                          padding: '6px 10px',
                          borderRadius: 8,
                          border: `1px solid ${theme.border}`,
                          background: theme.inputBg,
                          color: theme.text,
                          fontSize: 12,
                          cursor:
                            agentState === 'running'
                              ? 'not-allowed'
                              : 'pointer',
                          textAlign: 'left',
                          fontFamily: 'inherit',
                          opacity: agentState === 'running' ? 0.6 : 1,
                          transition: 'background 0.12s, border-color 0.12s',
                        }}
                        onMouseEnter={(e) => {
                          if (agentState !== 'running') {
                            e.currentTarget.style.background = `${theme.accent}22`;
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = theme.inputBg;
                        }}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        )}

        {isLoading && <TypingDots theme={theme} />}

        {agentState === 'done' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25 }}
            style={{
              alignSelf: 'center',
              padding: '8px 16px',
              borderRadius: 999,
              border: '1.5px solid #22c55e',
              color: '#22c55e',
              fontSize: 12,
              fontWeight: 600,
              marginTop: 4,
            }}
          >
            Your task was done
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
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
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder={
              isLoading ? 'Agent is working…' : 'Tell the agent what to do…'
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
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={send}
            disabled={!input.trim() || isLoading}
            title="Send"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background:
                input.trim() && !isLoading
                  ? theme.accent
                  : `${theme.accent}33`,
              color: input.trim() && !isLoading ? '#fff' : theme.textMuted,
              border: 'none',
              cursor:
                input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'background 0.15s',
            }}
          >
            ↑
          </motion.button>
        </div>
      </div>
    </div>
  );
}

/** Pick ink color for the user bubble based on its filled background. */
function userBubbleInk(theme: Theme['panel']): string {
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

function TypingDots({ theme }: { theme: Theme['panel'] }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{
        alignSelf: 'flex-start',
        padding: '10px 14px',
        borderRadius: 12,
        background: theme.inputBg,
        border: `1px solid ${theme.border}`,
        color: theme.textMuted,
        fontSize: 13,
      }}
    >
      <span
        style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}
      >
        <motion.span
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: 0 }}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: theme.textMuted,
          }}
        />
        <motion.span
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: 0.3 }}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: theme.textMuted,
          }}
        />
        <motion.span
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: 0.6 }}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: theme.textMuted,
          }}
        />
      </span>
    </motion.div>
  );
}
