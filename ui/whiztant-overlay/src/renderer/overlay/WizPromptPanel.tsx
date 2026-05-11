import { useState, useEffect, useMemo, useRef } from 'react';
import type { Theme } from '../shared/themes';
import CustomDropdown from '../shared/CustomDropdown';
import {
  Sparkles,
  Code,
  Search,
  MessageSquare,
  Lightbulb,
  FileText,
  BookOpen,
  Mail,
  Bug,
  Terminal,
} from 'lucide-react';

const PRESET_ICONS: Record<string, React.ReactNode> = {
  general_polish: <Sparkles size={14} />,
  code_creation: <Code size={14} />,
  code_review: <Search size={14} />,
  prompt_engineer: <MessageSquare size={14} />,
  idea_refinement: <Lightbulb size={14} />,
  product_spec: <FileText size={14} />,
  technical_writing: <BookOpen size={14} />,
  communication: <Mail size={14} />,
  bug_report: <Bug size={14} />,
  cli_command: <Terminal size={14} />,
};

const PRESET_CATEGORIES: Record<string, string> = {
  code_creation: 'Creation',
  prompt_engineer: 'Creation',
  cli_command: 'Creation',
  code_review: 'Review',
  general_polish: 'Review',
  idea_refinement: 'Product',
  product_spec: 'Product',
  bug_report: 'Product',
  technical_writing: 'Communication',
  communication: 'Communication',
};

type Preset = {
  id: string;
  name: string;
  display_name?: string;
  description: string;
  recommended_for?: string;
  category: string;
  system_prompt_addendum: string;
  agent_focus: string | null;
  icon: string | null;
};

type ProcessStatus = 'idle' | 'active' | 'completed' | 'error';

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
    preset?: string | null;
    examples_used?: number;
    example_ids?: number[];
  } | null;
  pendingText?: string | null;
  onProcessChange?: (status: ProcessStatus) => void;
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
  preset: string | null;
  examples_used: number;
  example_ids: number[];
};

type RetrievedExample = {
  id: number;
  original: string;
  optimized: string;
  final: string;
  similarity: number;
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

export default function WizPromptPanel({ theme, preloaded, pendingText, onProcessChange }: Props) {
  const [input, setInput] = useState('');
  const [status, setStatus] = useState<'idle' | 'processing' | 'done'>('idle');

  useEffect(() => {
    const mapped: ProcessStatus = status === 'processing' ? 'active' : status === 'done' ? 'completed' : 'idle';
    onProcessChange?.(mapped);
  }, [status]);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [showCritiques, setShowCritiques] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Few-shot memory state
  const [editedOutput, setEditedOutput] = useState<string | null>(null);
  const [wasEdited, setWasEdited] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [retrievedExamples, setRetrievedExamples] = useState<RetrievedExample[]>([]);
  const [showExamples, setShowExamples] = useState(false);
  const submittedRef = useRef(false);

  // Preset state
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>(() => {
    try {
      const saved = window.localStorage.getItem('whiztant.wizprompt.preset');
      if (saved) return saved;
    } catch { /* noop */ }
    return 'general_polish';
  });

  // Model state
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    try {
      const saved = window.localStorage.getItem('whiztant.wizprompt.model');
      if (saved && saved !== 'default') return saved;
      return 'google/gemini-3-flash-preview';
    }
    catch { return 'google/gemini-3-flash-preview'; }
  });

  useEffect(() => {
    try { window.localStorage.setItem('whiztant.wizprompt.model', selectedModel); } catch { /* noop */ }
  }, [selectedModel]);

  useEffect(() => {
    try { window.localStorage.setItem('whiztant.wizprompt.preset', selectedPreset); } catch { /* noop */ }
  }, [selectedPreset]);

  // Auto-submit pending feedback on unmount (tab switch / overlay close)
  useEffect(() => {
    return () => {
      if (result && !feedbackSubmitted && !submittedRef.current) {
        submittedRef.current = true;
        const final = editedOutput ?? result.out;
        fetch('http://localhost:8765/wizprompt/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            original: input,
            optimized: result.out,
            final,
            was_edited: wasEdited,
            feedback: null,
            preset: result.preset,
            model: selectedModel,
            emotion: result.emotion,
          }),
        }).catch(() => {});
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch presets on mount
  useEffect(() => {
    fetch('http://localhost:8765/presets')
      .then((res) => res.json())
      .then((data) => {
        if (data.presets && Array.isArray(data.presets)) {
          setPresets(data.presets);
        }
      })
      .catch(() => {
        // Fallback to default presets if server is unreachable
        setPresets([
          { id: 'general_polish', name: 'General Polish', display_name: 'General Polish', description: 'Any text that needs grammar fixes, clarity, and a natural tone.', recommended_for: 'Any text that needs grammar fixes, clarity, and a natural tone.', category: 'company', system_prompt_addendum: '', agent_focus: 'clarity', icon: 'sparkles' },
          { id: 'code_creation', name: 'Code Creation', display_name: 'Code Creation', description: 'Turning natural language descriptions, pseudocode, or rough logic into production-ready code.', recommended_for: 'Turning natural language descriptions, pseudocode, or rough logic into production-ready code.', category: 'company', system_prompt_addendum: '', agent_focus: 'code', icon: 'code' },
          { id: 'code_review', name: 'Code Review', display_name: 'Code Review', description: 'Pasted code snippets that need bug detection, performance tuning, or style fixes.', recommended_for: 'Pasted code snippets that need bug detection, performance tuning, or style fixes.', category: 'company', system_prompt_addendum: '', agent_focus: 'code', icon: 'search' },
          { id: 'prompt_engineer', name: 'Prompt Engineer', display_name: 'Prompt Engineer', description: 'Optimizing AI prompts for better structure, specificity, and output quality.', recommended_for: 'Optimizing AI prompts for better structure, specificity, and output quality.', category: 'company', system_prompt_addendum: '', agent_focus: 'optimization', icon: 'message-square' },
          { id: 'idea_refinement', name: 'Idea Refinement', display_name: 'Idea Refinement', description: 'Raw thoughts, brainstorming notes, or half-baked concepts that need structure.', recommended_for: 'Raw thoughts, brainstorming notes, or half-baked concepts that need structure.', category: 'company', system_prompt_addendum: '', agent_focus: 'creativity', icon: 'lightbulb' },
          { id: 'product_spec', name: 'Product Spec', display_name: 'Product Spec', description: 'Converting rambling product thoughts into a formal PRD or feature specification.', recommended_for: 'Converting rambling product thoughts into a formal PRD or feature specification.', category: 'company', system_prompt_addendum: '', agent_focus: 'product', icon: 'file-text' },
          { id: 'technical_writing', name: 'Technical Writing', display_name: 'Technical Writing', description: 'Documentation, READMEs, API docs, or explanations that need professional polish.', recommended_for: 'Documentation, READMEs, API docs, or explanations that need professional polish.', category: 'company', system_prompt_addendum: '', agent_focus: 'documentation', icon: 'book-open' },
          { id: 'communication', name: 'Communication', display_name: 'Communication', description: 'Emails, Slack messages, DMs, or any workplace communication that needs tone adjustment.', recommended_for: 'Emails, Slack messages, DMs, or any workplace communication that needs tone adjustment.', category: 'company', system_prompt_addendum: '', agent_focus: 'communication', icon: 'mail' },
          { id: 'bug_report', name: 'Bug Report', display_name: 'Bug Report', description: 'Scattered complaints or screenshots of errors that need to become actionable bug reports.', recommended_for: 'Scattered complaints or screenshots of errors that need to become actionable bug reports.', category: 'company', system_prompt_addendum: '', agent_focus: 'technical', icon: 'bug' },
          { id: 'cli_command', name: 'CLI Command', display_name: 'CLI Command', description: 'Natural language requests that need to be converted into accurate terminal commands.', recommended_for: 'Natural language requests that need to be converted into accurate terminal commands.', category: 'company', system_prompt_addendum: '', agent_focus: 'technical', icon: 'terminal' },
        ]);
      });
  }, []);

  const liveLines = useMemo(() => {
    const count = input.split('\n').length;
    if (count <= 5) return { size: 'small', agents: 2, label: 'Small prompt — fast optimization' };
    if (count <= 15) return { size: 'medium', agents: 3, label: 'Medium prompt — fast optimization' };
    return { size: 'large', agents: 4, label: 'Large prompt — fast optimization' };
  }, [input]);

  const liveValidation = useMemo(() => validateInput(input), [input]);

  const selectedPresetData = useMemo(() => presets.find((p) => p.id === selectedPreset), [presets, selectedPreset]);

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
        preset: preloaded.preset || null,
        examples_used: preloaded.examples_used || 0,
        example_ids: preloaded.example_ids || [],
      });
      setStatus('done');
      window.api.writeClipboard(preloaded.optimized).catch(() => {});
      setCopied(true);
      const t = setTimeout(() => setCopied(false), 2000);
      return () => clearTimeout(t);
    }
  }, [preloaded]);

  useEffect(() => {
    if (pendingText) {
      setInput(pendingText);
      setStatus('processing');
      setResult(null);
      setError(null);
      setCopied(false);
      setShowCritiques(false);
      setEditedOutput(null);
      setWasEdited(false);
      setFeedback(null);
      setFeedbackSubmitted(false);
      submittedRef.current = false;
      setRetrievedExamples([]);
      setShowExamples(false);
    }
  }, [pendingText]);

  const submitFeedback = async (fb: 'up' | 'down' | null) => {
    if (!result || feedbackSubmitted) return;
    const final = editedOutput ?? result.out;
    try {
      await fetch('http://localhost:8765/wizprompt/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original: input,
          optimized: result.out,
          final,
          was_edited: wasEdited,
          feedback: fb,
          preset: result.preset,
          model: selectedModel,
          emotion: result.emotion,
        }),
      });
      setFeedbackSubmitted(true);
      if (fb) setFeedback(fb);
    } catch (e) {
      console.error('Feedback submit failed:', e);
    }
  };

  const run = async () => {
    if (!input.trim()) return;
    // Auto-submit previous result if pending
    if (result && !feedbackSubmitted && !submittedRef.current) {
      submittedRef.current = true;
      await submitFeedback(null);
    }
    setEditedOutput(null);
    setWasEdited(false);
    setFeedback(null);
    setFeedbackSubmitted(false);
    submittedRef.current = false;
    setRetrievedExamples([]);
    setShowExamples(false);
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
        body: JSON.stringify({ prompt: input, model: model || undefined, preset: selectedPreset })
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
        preset: data.preset || null,
        examples_used: data.examples_used || 0,
        example_ids: data.example_ids || [],
      });
      setStatus('done');

      // Fetch retrieved examples for display
      try {
        const exRes = await fetch(
          `http://localhost:8765/wizprompt/examples?${new URLSearchParams({
            prompt: input,
            preset: selectedPreset,
            limit: '3',
          })}`
        );
        const exData = await exRes.json();
        if (exData.ok && exData.examples) {
          setRetrievedExamples(exData.examples);
        }
      } catch (e) {
        /* ignore examples fetch errors */
      }

      if (optimized) {
        await window.api.writeClipboard(optimized);
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
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '12px', gap: 10, minHeight: 0, overflowY: 'auto' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>RePrompt</span>

        {/* Model selector */}
        <CustomDropdown
          value={selectedModel}
          onChange={(v) => setSelectedModel(v)}
          options={[
            { value: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash (Google) — Fast' },
            { value: 'anthropic/claude-haiku-4.5', label: 'Claude Haiku 4.5 (Anthropic)' },
            { value: 'openai/gpt-5.5-mini', label: 'GPT 5.5 mini (OpenAI)' },
            { value: 'openai/gpt-5.4-mini', label: 'GPT 5.4 mini (OpenAI)' },
            { value: 'anthropic/claude-sonnet-4.6', label: 'Claude Sonnet 4.6 (Anthropic)' },
            { value: 'openai/gpt-5.5', label: 'GPT 5.5 (OpenAI)' },
            { value: 'openai/gpt-5.4', label: 'GPT 5.4 (OpenAI)' },
            { value: 'x-ai/grok-4.3', label: 'Grok 4.3 (xAI)' },
            { value: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Google)' },
            { value: 'qwen/qwen3.5-plus-20260420', label: 'Qwen 3.5 Plus (Alibaba)' },
            { value: 'moonshotai/kimi-k2.6', label: 'Kimi K2.6 (Moonshot)' },
            { value: 'custom', label: 'Custom / BYOK' },
          ]}
          theme={theme}
          label="Model"
        />
        {selectedModel === 'custom' && (
          <span style={{ fontSize: 10, color: theme.textMuted }}>Configure custom model in Settings → General</span>
        )}

        {/* Preset selector */}
        <CustomDropdown
          value={selectedPreset}
          onChange={(v) => setSelectedPreset(v)}
          options={presets.map((p) => ({
            value: p.id,
            label: p.display_name ?? p.name,
            recommended_for: p.recommended_for,
            icon: PRESET_ICONS[p.id] ?? undefined,
            category: PRESET_CATEGORIES[p.id],
          }))}
          theme={theme}
          label="Optimization Preset"
          placeholder="Select a preset…"
          grouped
          showRecommendedFor
        />

        <textarea
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(e.target.scrollHeight, 240)}px`;
          }}
          placeholder="Paste your raw prompt here to optimize it..."
          style={{
            width: '100%',
            minHeight: 80,
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
            overflowY: 'auto',
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
        {status === 'processing' ? 'Optimizing...' : selectedPreset !== 'general_polish' ? `Optimize (${selectedPresetData?.display_name ?? selectedPresetData?.name ?? selectedPreset})` : 'Optimize Prompt'}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 10 }}>
          <div style={{ fontSize: 11, color: theme.textMuted, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span>{sizeBadge(result.prompt_size)} ({result.line_count} lines) • {result.agents.length} agents</span>
            {result.emotion && <span>• Emotion: <strong style={{ color: theme.aiAccent }}>{result.emotion}</strong></span>}
            {result.preset && <span>• Optimized for: <strong style={{ color: theme.aiAccent }}>{result.preset}</strong></span>}
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

          {/* Editable optimized output */}
          <textarea
            value={editedOutput ?? result.out}
            onChange={(e) => {
              setEditedOutput(e.target.value);
              setWasEdited(true);
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 600)}px`;
            }}
            placeholder="[No optimized prompt returned]"
            style={{
              width: '100%',
              minHeight: 300,
              padding: 10,
              borderRadius: 12,
              border: `1px solid ${theme.aiAccent}40`,
              background: theme.inputBg,
              color: theme.text,
              fontSize: 12,
              lineHeight: 1.6,
              resize: 'none',
              fontFamily: 'inherit',
              outline: 'none',
              overflowY: 'auto',
            }}
          />

          {/* Feedback + action buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => submitFeedback('up')}
              disabled={feedbackSubmitted}
              style={{
                padding: '6px 10px',
                borderRadius: 8,
                border: `1px solid ${feedback === 'up' ? theme.aiAccent : theme.border}`,
                background: feedback === 'up' ? `${theme.aiAccent}22` : 'transparent',
                color: feedback === 'up' ? theme.text : theme.textMuted,
                fontSize: 11,
                cursor: feedbackSubmitted ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              👍 Good
            </button>
            <button
              onClick={() => submitFeedback('down')}
              disabled={feedbackSubmitted}
              style={{
                padding: '6px 10px',
                borderRadius: 8,
                border: `1px solid ${feedback === 'down' ? '#ef4444' : theme.border}`,
                background: feedback === 'down' ? 'rgba(239,68,68,0.12)' : 'transparent',
                color: feedback === 'down' ? '#fca5a5' : theme.textMuted,
                fontSize: 11,
                cursor: feedbackSubmitted ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              👎 Bad
            </button>
            <button
              onClick={() => {
                const text = editedOutput ?? result.out;
                window.api.writeClipboard(text).catch(() => {});
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
                fontFamily: 'inherit',
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
                fontFamily: 'inherit',
              }}
            >
              {showCritiques ? 'Hide Critiques' : 'View Critiques'}
            </button>
          </div>

          {/* Retrieved examples display */}
          {retrievedExamples.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <button
                onClick={() => setShowExamples(!showExamples)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'transparent',
                  border: 'none',
                  color: theme.textMuted,
                  fontSize: 11,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  padding: 0,
                }}
              >
                <span>📚</span>
                <span>
                  Based on {retrievedExamples.length} past optimization{retrievedExamples.length > 1 ? 's' : ''} you accepted
                </span>
                <span style={{ marginLeft: 'auto' }}>{showExamples ? '▲' : '▼'}</span>
              </button>
              {showExamples && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {retrievedExamples.map((ex) => (
                    <div
                      key={ex.id}
                      style={{
                        padding: 8,
                        borderRadius: 8,
                        border: `1px solid ${theme.border}`,
                        background: 'rgba(0,0,0,0.15)',
                        fontSize: 10,
                        color: theme.textMuted,
                      }}
                    >
                      <div style={{ marginBottom: 4 }}>
                        <strong style={{ color: theme.aiAccent }}>Original:</strong>{' '}
                        {ex.original.length > 80 ? ex.original.slice(0, 80) + '…' : ex.original}
                      </div>
                      <div>
                        <strong style={{ color: theme.aiAccent }}>Optimized:</strong>{' '}
                        {ex.final.length > 80 ? ex.final.slice(0, 80) + '…' : ex.final}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

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
