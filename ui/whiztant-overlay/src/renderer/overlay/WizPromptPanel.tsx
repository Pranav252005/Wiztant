import { useState, useEffect, useMemo } from 'react';
import type { Theme } from '../shared/themes';

type Props = {
  theme: Theme['panel'];
  preloaded?: {
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
  } | null;
};

type OptimizationResult = {
  out: string;
  agents: string[];
  emotion: string | null;
  critiques: {
    structure?: string;
    semantic?: string;
    edge_case?: string;
    emotional?: string;
  };
  line_count: number;
  prompt_size: string;
  framing_directive: string | null;
  synthesis_failed: boolean;
};

function agentLabel(id: string): string {
  const map: Record<string, string> = {
    structure: 'Structural Clarity',
    semantic: 'Semantic Precision',
    edge_case: 'Edge Case & Robustness',
    emotional: 'Emotional Calibration',
  };
  return map[id] || id;
}

function sizeBadge(size: string): string {
  if (size === 'small') return 'Small';
  if (size === 'medium') return 'Medium';
  return 'Large';
}

const GREETINGS = new Set(['hello', 'hi', 'hey', 'test', 'testing', 'ok', 'okay', 'yes', 'no', 'yep', 'nope', 'lol', 'haha']);

function validateInput(text: string): string | null {
  const stripped = text.trim();
  if (!stripped) return 'Enter a prompt first.';
  if (stripped.length < 15) return "That's too short to be a real prompt. Write at least a full sentence.";
  if (/^\s*https?:\/\/\S+\s*$/i.test(stripped)) return "That's just a link. Paste the actual content you want optimized.";

  const lettersOnly = stripped.replace(/[^a-zA-Z]/g, '');
  if (lettersOnly.length < 3) return 'A prompt needs actual words, not just symbols or emojis.';

  if (stripped.length > 5) {
    const lower = stripped.toLowerCase();
    const counts = new Map<string, number>();
    for (const ch of lower) counts.set(ch, (counts.get(ch) || 0) + 1);
    const maxCount = Math.max(...counts.values());
    if (maxCount / stripped.length > 0.6) return 'Looks like accidental key mashing. Try writing a real prompt.';
  }

  const words = stripped.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length > 2 && new Set(words).size === 1) return "Repeating the same word isn't a prompt. Be more descriptive.";
  if (words.length <= 3 && words.every((w) => GREETINGS.has(w.replace(/[.,!?;:]/g, '')))) {
    return "That's a greeting, not a prompt. Tell the AI what you want it to optimize.";
  }

  return null;
}

export default function WizPromptPanel({ theme, preloaded }: Props) {
  const [input, setInput] = useState('');
  const [status, setStatus] = useState<'idle' | 'processing' | 'done'>('idle');
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [showCritiques, setShowCritiques] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const liveLines = useMemo(() => {
    const count = input.split('\n').length;
    if (count <= 5) return { size: 'small', agents: 2, label: 'Small prompt — will use 2 agents' };
    if (count <= 15) return { size: 'medium', agents: 3, label: 'Medium prompt — will use 3 agents' };
    return { size: 'large', agents: 4, label: 'Large prompt — will use 4 agents' };
  }, [input]);

  const liveValidation = useMemo(() => validateInput(input), [input]);

  useEffect(() => {
    if (preloaded) {
      setInput(preloaded.original);
      const agents = ['structure', 'semantic'];
      if (preloaded.agent_count >= 3) agents.push('edge_case');
      if (preloaded.agent_count >= 4) agents.push('emotional');
      setResult({
        out: preloaded.optimized,
        agents,
        emotion: preloaded.emotion,
        critiques: preloaded.critiques || {},
        line_count: preloaded.line_count || preloaded.original.split('\n').length,
        prompt_size: preloaded.prompt_size || 'unknown',
        framing_directive: preloaded.framing_directive || null,
        synthesis_failed: preloaded.synthesis_failed || false,
      });
      setStatus('done');
      navigator.clipboard.writeText(preloaded.optimized);
      setCopied(true);
      const t = setTimeout(() => setCopied(false), 2000);
      return () => clearTimeout(t);
    }
  }, [preloaded]);

  const run = async () => {
    if (!input.trim()) return;
    setResult(null);
    setShowCritiques(false);
    setCopied(false);
    setError(null);

    const validationError = validateInput(input);
    if (validationError) {
      setError(validationError);
      setStatus('idle');
      return;
    }

    setStatus('processing');

    // Read model config from Settings localStorage keys
    let model = '';
    try {
      const storedModel = window.localStorage.getItem('whiztant.wizprompt.model');
      if (storedModel && storedModel !== 'default' && storedModel !== 'custom') {
        model = storedModel;
      } else if (storedModel === 'custom') {
        const customName = window.localStorage.getItem('whiztant.wizprompt.modelName');
        if (customName) model = customName;
      }
    } catch {
      /* ignore localStorage errors */
    }

    try {
      const res = await fetch('http://localhost:8765/wizprompt/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: input, model: model || undefined })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.detail || data.message || `Server error ${res.status}`);
      }

      const agents = ['structure', 'semantic'];
      if (data.agent_count >= 3) agents.push('edge_case');
      if (data.agent_count >= 4) agents.push('emotional');

      const optimized = data.optimized_prompt || '';
      setResult({
        out: optimized,
        agents,
        emotion: data.emotional_state,
        critiques: data.critiques || {},
        line_count: data.line_count || input.split('\n').length,
        prompt_size: data.prompt_size || 'unknown',
        framing_directive: data.framing_directive || null,
        synthesis_failed: data.synthesis_failed || false,
      });
      setStatus('done');

      if (optimized) {
        await navigator.clipboard.writeText(optimized);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (e: any) {
      console.error(e);
      setError(e?.message || 'Optimization failed. Make sure the core server is running.');
      setStatus('idle');
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '12px', gap: 10, minHeight: 0 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>WizPrompt</span>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste your raw prompt here to optimize it..."
          style={{
            width: '100%',
            height: 100,
            padding: 10,
            borderRadius: 12,
            border: `1px solid ${theme.border}`,
            background: theme.inputBg,
            color: theme.text,
            fontSize: 12,
            resize: 'none',
            fontFamily: 'inherit',
            outline: 'none',
            flexShrink: 0,
          }}
        />
        {input.trim() && (
          <span style={{ fontSize: 10, color: liveValidation ? '#fca5a5' : theme.textMuted }}>
            {liveValidation || `${input.split('\n').length} lines • ${liveLines.label}`}
          </span>
        )}
      </div>

      <button
        onClick={run}
        disabled={status === 'processing' || !input.trim() || !!liveValidation}
        style={{
          padding: '8px 12px',
          borderRadius: 12,
          border: 'none',
          background: status === 'processing' ? `${theme.aiAccent}80` : theme.aiAccent,
          color: '#07070f',
          fontSize: 12,
          fontWeight: 600,
          cursor: status === 'processing' || !input.trim() || !!liveValidation ? 'not-allowed' : 'pointer',
          flexShrink: 0,
        }}
      >
        {status === 'processing' ? 'Optimizing with Agents...' : 'Optimize Prompt'}
      </button>

      {status === 'processing' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {liveLines.agents >= 2 && (
            <AgentStep label={agentLabel('structure')} theme={theme} />
          )}
          {liveLines.agents >= 2 && (
            <AgentStep label={agentLabel('semantic')} theme={theme} />
          )}
          {liveLines.agents >= 3 && (
            <AgentStep label={agentLabel('edge_case')} theme={theme} />
          )}
          {liveLines.agents >= 4 && (
            <AgentStep label={agentLabel('emotional')} theme={theme} />
          )}
          <span style={{ fontSize: 10, color: theme.textMuted, marginTop: 4 }}>
            Synthesizing critiques…
          </span>
        </div>
      )}

      {error && (
        <div style={{ padding: 10, borderRadius: 12, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', fontSize: 11 }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0, overflowY: 'auto', paddingBottom: 10 }}>
          <div style={{ fontSize: 11, color: theme.textMuted, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span>{sizeBadge(result.prompt_size)} ({result.line_count} lines) • {result.agents.length} agents</span>
            {result.emotion && <span>• Emotion: <strong style={{ color: theme.aiAccent }}>{result.emotion}</strong></span>}
            {copied && <span style={{ color: '#4ade80' }}>• Copied</span>}
          </div>

          {result.synthesis_failed && (
            <div style={{ padding: 8, borderRadius: 8, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', fontSize: 11 }}>
              Synthesis failed — showing raw critiques below.
            </div>
          )}

          {result.framing_directive && (
            <div style={{ padding: 10, borderRadius: 12, border: `1px solid ${theme.border}`, background: `${theme.aiAccent}10`, fontSize: 11, color: theme.textMuted }}>
              <strong style={{ color: theme.aiAccent }}>Framing Directive</strong>{' '}
              {result.framing_directive}
            </div>
          )}

          <div
            style={{
              padding: 10,
              borderRadius: 12,
              border: `1px solid ${theme.border}`,
              background: theme.inputBg,
              color: theme.text,
              fontSize: 12,
              whiteSpace: 'pre-wrap',
            }}
          >
            {result.out || '[No optimized prompt returned]'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => {
                navigator.clipboard.writeText(result.out);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              style={{
                flex: 1,
                padding: '6px',
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                background: 'transparent',
                color: theme.text,
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button
              onClick={() => setShowCritiques(!showCritiques)}
              style={{
                flex: 1,
                padding: '6px',
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                background: 'transparent',
                color: theme.text,
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              {showCritiques ? 'Hide Critiques' : 'View Critiques'}
            </button>
          </div>

          {showCritiques && (
            <div style={{ padding: 10, borderRadius: 12, border: `1px solid ${theme.border}`, background: 'rgba(0,0,0,0.2)', fontSize: 11, color: theme.textMuted, whiteSpace: 'pre-wrap' }}>
              <strong style={{color: theme.aiAccent}}>STRUCTURAL</strong>{'\n'}{result.critiques.structure || 'N/A'}{'\n\n'}
              <strong style={{color: theme.aiAccent}}>SEMANTIC</strong>{'\n'}{result.critiques.semantic || 'N/A'}
              {result.critiques.edge_case && <>{'\n\n'}<strong style={{color: theme.aiAccent}}>EDGE CASE</strong>{'\n'}{result.critiques.edge_case}</>}
              {result.critiques.emotional && <>{'\n\n'}<strong style={{color: theme.aiAccent}}>EMOTIONAL</strong>{'\n'}{result.critiques.emotional}</>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentStep({ label, theme }: { label: string; theme: Theme['panel'] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: theme.textMuted }}>
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: '50%',
          border: `2px solid ${theme.aiAccent}`,
          borderTopColor: 'transparent',
          animation: 'spin 0.8s linear infinite',
          display: 'inline-block',
        }}
      />
      <span>Analyzing {label}…</span>
    </div>
  );
}
