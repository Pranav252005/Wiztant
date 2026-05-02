import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, ArrowRight, Check, Layers, BrainCircuit, ShieldCheck, Heart, Copy, Loader2 } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Grainient from '../components/Grainient'
import Particles from '../components/Particles'

const meta = {
  structure: { icon: Layers, label: 'Structural Clarity', cls: 'text-teal-400 border-teal-400/20 bg-teal-400/5' },
  semantic: { icon: BrainCircuit, label: 'Semantic Precision', cls: 'text-primary border-primary/20 bg-primary/5' },
  edge_case: { icon: ShieldCheck, label: 'Edge Case & Robustness', cls: 'text-warm border-warm/20 bg-warm/5' },
  emotional: { icon: Heart, label: 'Emotional Calibration', cls: 'text-rose-400 border-rose-400/20 bg-rose-400/5' },
}

const presets = {
  small: 'Write a function that sorts an array.',
  medium: 'Write a Python function that:\n1. Takes a JSON string\n2. Parses it\n3. Validates against schema\n4. Returns success/error',
  large: 'Design a system to process user feedback at scale.\n\nRequirements:\n1. Collect feedback from multiple channels\n2. Categorize automatically using ML\n3. Route to appropriate teams\n4. Track resolution time\n5. Generate weekly reports\n\nConsider: data privacy, spam filtering, multilingual support',
}

const mocks = {
  small: { agents: ['structure','semantic'], emotion: null, out: 'Write a well-documented Python function that sorts an array in ascending order using an efficient algorithm (O(n log n)).\n\n**Requirements:**\n- Handle edge cases: empty arrays, single elements, duplicate values, non-comparable types\n- Return the sorted array without mutating the original input\n- Include type hints and a docstring' },
  medium: { agents: ['structure','semantic','edge_case'], emotion: null, out: 'Write a production-ready Python function that parses and validates a JSON string against a provided schema.\n\n**Function Signature:**\n```python\ndef parse_and_validate(json_str: str, schema: dict) -> dict:\n```\n\n**Behavior:**\n- Parse using `json.loads`; validate using `jsonschema`\n- Return `{"success": True, "data": parsed}` on valid input\n- Return `{"success": False, "error": "<type>: <message>"}` on failure\n\n**Handled Errors:**\n- `SyntaxError` → parsing error\n- `TypeError` → validation error\n- `json.JSONDecodeError` → decoding error' },
  large: { agents: ['structure','semantic','edge_case','emotional'], emotion: 'calmness', out: 'Design a scalable, multi-channel user feedback processing system with methodical precision.\n\n## Core Objectives\n1. **Ingestion**: Collect feedback from email, web forms, and live chat via API adapters\n2. **Categorization**: ML auto-tagging with confidence thresholds\n3. **Routing**: Decision-tree rules with escalation paths\n4. **Tracking**: SLA tier monitoring (P0 < 4h, P1 < 24h, P2 < 72h)\n5. **Reporting**: Weekly summary dashboards with trend analysis\n\n## Guardrails\n- **Privacy**: GDPR/CCPA-compliant retention; PII redaction before ML\n- **Spam**: Bayesian pre-filter; quarantine for 24h review\n- **Multilingual**: Language detection; route unsupported to human triage\n- **Downtime**: Persistent queue during channel outages\n- **Integration**: REST + webhook APIs for ticketing sync' },
}

function Demo() {
  const [size, setSize] = useState('small')
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [input, setInput] = useState(presets.small)
  const [showCritiques, setShowCritiques] = useState(false)

  const run = async () => { 
    setStatus('processing'); 
    setResult(null); 
    setShowCritiques(false);
    try {
      const res = await fetch('http://localhost:8765/reprompt/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: input })
      });
      if (!res.ok) throw new Error('Backend not available');
      const data = await res.json();
      
      const agents = ['structure', 'semantic'];
      if (data.agent_count >= 3) agents.push('edge_case');
      if (data.agent_count >= 4) agents.push('emotional');
      
      setResult({
        out: data.optimized_prompt,
        agents: agents,
        emotion: data.emotional_state,
        critiques: data.critiques
      });
      setStatus('done');
    } catch (e) {
      console.log('Falling back to mocks...', e);
      setTimeout(()=>{ setResult(mocks[size]); setStatus('done') }, 1500);
    }
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8">
      <div className="flex items-center gap-2 mb-6">
        <Sparkles size={18} className="text-primary" />
        <span className="text-sm font-medium text-text-secondary">RePrompt Demo</span>
      </div>
      <div className="flex gap-2 mb-4">
        {['small','medium','large'].map(s => (
          <button key={s} onClick={()=>{setSize(s);setInput(presets[s]);setStatus('idle');setResult(null);setShowCritiques(false)}}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${size===s?'bg-primary text-bg-dark':'border border-white/10 text-text-secondary hover:text-text-primary'}`}>
            {s[0].toUpperCase()+s.slice(1)}
          </button>
        ))}
      </div>
      <div className="mb-4">
        <p className="text-xs text-text-secondary mb-2">Original prompt ({input.split('\n').length} lines)</p>
        <textarea value={input} onChange={e=>setInput(e.target.value)}
          rows={Math.min(6,input.split('\n').length+1)}
          className="w-full rounded-xl border border-white/[0.06] bg-bg-dark px-4 py-3 text-sm text-text-secondary font-mono resize-none outline-none focus:border-primary/40" />
      </div>
      <button onClick={run} disabled={status==='processing'}
        className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-medium text-bg-dark transition-opacity hover:opacity-90 flex items-center justify-center gap-2 disabled:opacity-50">
        {status==='processing'?<Loader2 size={16} className="animate-spin" />:<Sparkles size={16} />}
        {status==='processing'?'Optimizing...':'Optimize with Agents'}
      </button>
      <AnimatePresence>
        {result && (
          <motion.div initial={{opacity:0,height:0}} animate={{opacity:1,height:'auto'}} exit={{opacity:0,height:0}} className="mt-6 space-y-4 overflow-hidden">
            <div className="flex items-center gap-2">
              <Check size={14} className="text-teal-400" />
              <span className="text-xs text-text-secondary">Optimized with {result.agents.length} agents {result.emotion?`· Emotion: ${result.emotion}`:''}</span>
            </div>
            <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-text-primary font-mono leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">{result.out}</div>
            <div className="flex gap-2 flex-wrap">
              {result.agents.map(a=>{ const m=meta[a],I=m.icon; return <span key={a} className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${m.cls}`}><I size={12}/> {m.label}</span> })}
            </div>
            <div className="flex gap-2">
              <button onClick={()=>navigator.clipboard.writeText(result.out)}
                className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-text-secondary transition-all hover:bg-white/10 flex items-center justify-center gap-2">
                <Copy size={12}/> Copy
              </button>
              {result.critiques && (
                <button onClick={()=>setShowCritiques(!showCritiques)}
                  className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-text-secondary transition-all hover:bg-white/10 flex items-center justify-center gap-2">
                  <Layers size={12}/> {showCritiques ? 'Hide Critiques' : 'Show Critiques'}
                </button>
              )}
            </div>
            
            {showCritiques && result.critiques && (
              <motion.div initial={{opacity:0}} animate={{opacity:1}} className="mt-4 p-4 rounded-xl border border-white/10 bg-black/20 text-xs text-text-secondary font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                <h4 className="text-primary font-bold mb-2">STRUCTURAL CRITIQUE</h4>
                <div>{result.critiques.structure || 'N/A'}</div>
                <h4 className="text-primary font-bold mt-4 mb-2">SEMANTIC CRITIQUE</h4>
                <div>{result.critiques.semantic || 'N/A'}</div>
                {result.critiques.edge_case && (
                  <>
                    <h4 className="text-primary font-bold mt-4 mb-2">EDGE CASE CRITIQUE</h4>
                    <div>{result.critiques.edge_case}</div>
                  </>
                )}
                {result.critiques.emotional && (
                  <>
                    <h4 className="text-primary font-bold mt-4 mb-2">EMOTIONAL CALIBRATION</h4>
                    <div>{result.critiques.emotional}</div>
                  </>
                )}
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function RePrompt() {
  return (
    <div>
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="absolute inset-0 z-[1]">
          <Grainient color1="#c0c1ff" color2="#d0bcff" color3="#07070f" timeSpeed={0.15} warpStrength={0.8} blendAngle={5} contrast={1.2} gamma={1.15} />
        </div>
        <Particles count={20} />
        <div className="absolute inset-0" style={{backgroundImage:'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize:'60px 60px'}} />
        <motion.div initial={{opacity:0,y:40}} animate={{opacity:1,y:0}} transition={{duration:1}} className="relative z-10 max-w-4xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 mb-8">
            <Sparkles size={14} className="text-primary" />
            <span className="text-xs font-medium text-primary">Ctrl+Shift+P</span>
          </div>
          <h1 className="font-display text-5xl font-bold leading-tight text-text-primary md:text-7xl">
            Prompts that perform{' '}
            <span className="text-gradient-primary">at their best</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary drop-shadow-lg">
            RePrompt deploys 2-4 specialized AI agents to restructure, sharpen, and emotionally calibrate your prompts.
          </p>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <AnimatedSection direction="left"><Demo /></AnimatedSection>
          <AnimatedSection direction="right">
            <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">Multi-agent, size-aware optimization</h2>
            <p className="mt-4 text-text-secondary leading-relaxed">
              RePrompt reads your prompt length and automatically assembles the right agent team. Small prompts get structure + semantics. Large prompts get emotional calibration too.
            </p>
            <ul className="mt-8 space-y-4">
              {['Dynamic agent selection based on prompt size','Structural clarity + semantic precision on every run','Edge-case stress testing for medium and large prompts','Emotional calibration unlocks peak LLM performance'].map((item) => (
                <li key={item} className="flex items-start gap-3 text-text-secondary">
                  <Check size={18} className="mt-0.5 shrink-0 text-primary" /><span>{item}</span>
                </li>
              ))}
            </ul>
            <Link to="/download" className="btn-primary mt-8">Try RePrompt <ArrowRight size={16} /></Link>
          </AnimatedSection>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <AnimatedSection className="text-center mb-16">
          <h2 className="font-display text-3xl font-bold text-text-primary">How it works</h2>
        </AnimatedSection>
        <div className="grid gap-8 md:grid-cols-3">
          {[
            { step:'01', title:'Paste your prompt', desc:'Any length — a one-liner or a full system spec. RePrompt measures and decides.' },
            { step:'02', title:'Agent team deploys', desc:'2-4 specialized agents critique structure, semantics, edge cases, and emotional framing in parallel.' },
            { step:'03', title:'Get the refined prompt', desc:'Synthesis merges all critiques into one cohesive, production-ready prompt you can copy and use.' },
          ].map((item,i) => (
            <AnimatedSection key={item.step} delay={i*0.15}>
              <div className="card text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full border border-primary/20 bg-primary/5 text-primary font-display font-bold mb-4">{item.step}</div>
                <h3 className="font-display text-lg font-semibold text-text-primary">{item.title}</h3>
                <p className="mt-2 text-sm text-text-secondary">{item.desc}</p>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20 text-center">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary">RePrompt is included with Pro</h2>
          <p className="mt-3 text-text-secondary">Start your free trial today.</p>
          <Link to="/pricing" className="btn-primary mt-8">View Pricing <ArrowRight size={16} /></Link>
        </AnimatedSection>
      </section>
    </div>
  )
}
