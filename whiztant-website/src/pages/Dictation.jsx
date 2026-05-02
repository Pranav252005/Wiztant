import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useInView, AnimatePresence } from 'framer-motion'
import { Mic, ArrowRight, Check, Pause, Copy, RotateCcw, XCircle, Settings2 } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Grainient from '../components/Grainient'
import Particles from '../components/Particles'
import { useDictation } from '../hooks/useDictation'

function WaveformVisualizer() {
  const [showSettings, setShowSettings] = useState(false)
  const [settings, setSettings] = useState({
    filterFillers: true,
    normalizeExtensions: true,
    smartPunctuation: true,
    capitalize: true,
  })

  const [state, controls] = useDictation({
    lang: 'en-US',
    continuous: true,
    interimResults: true,
    autoProcess: true,
    processOptions: settings,
  })

  const { isRecording, isSupported, transcript, interimTranscript, error, audioLevels } = state
  const { toggle, clear } = controls

  const displayText = transcript + (interimTranscript ? ` ${interimTranscript}` : '')

  const handleCopy = async () => {
    if (!transcript) return
    try {
      await navigator.clipboard.writeText(transcript)
    } catch (_) { /* noop */ }
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8">
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Mic size={18} className="text-primary" />
        <span className="text-sm font-medium text-text-secondary">Dictation Demo</span>
        <div className="ml-auto flex items-center gap-2">
          {transcript && (
            <button
              onClick={clear}
              className="p-1.5 rounded-lg text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors"
              title="Clear transcript"
            >
              <RotateCcw size={14} />
            </button>
          )}
          <button
            onClick={() => setShowSettings((s) => !s)}
            className={`p-1.5 rounded-lg transition-colors ${showSettings ? 'text-primary bg-primary/10' : 'text-text-secondary hover:text-primary hover:bg-primary/10'}`}
            title="Settings"
          >
            <Settings2 size={14} />
          </button>
          <span className={`text-xs font-mono ${isRecording ? 'text-primary' : 'text-text-secondary'}`}>
            {isRecording ? 'Recording...' : 'Idle'}
          </span>
        </div>
      </div>

      {/* Settings panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="rounded-xl border border-white/[0.06] bg-bg-dark px-4 py-3 mb-4 space-y-2">
              <p className="text-xs font-medium text-text-secondary mb-2">Post-processing</p>
              {[
                { key: 'filterFillers', label: 'Filter filler words' },
                { key: 'normalizeExtensions', label: 'Normalize file extensions' },
                { key: 'smartPunctuation', label: 'Smart punctuation' },
                { key: 'capitalize', label: 'Auto-capitalize sentences' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings[key]}
                    onChange={(e) => setSettings((s) => ({ ...s, [key]: e.target.checked }))}
                    className="accent-primary rounded"
                  />
                  {label}
                </label>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Real audio waveform */}
      <div className="flex items-end justify-center gap-[2px] h-32 mb-6">
        {audioLevels.map((h, i) => (
          <motion.div
            key={i}
            className="w-1.5 rounded-full bg-primary/60"
            animate={{ height: `${Math.max(h / 2.55, 4)}%` }}
            transition={{ duration: 0.05 }}
          />
        ))}
      </div>

      {/* Transcript display */}
      <div className="rounded-xl border border-white/[0.06] bg-bg-dark px-4 py-3 mb-4 min-h-[80px] max-h-[200px] overflow-y-auto">
        {error ? (
          <p className="text-sm text-red-400 font-mono flex items-center gap-2">
            <XCircle size={14} />
            {error}
          </p>
        ) : displayText ? (
          <p className="text-sm text-text-primary font-mono whitespace-pre-wrap">
            {transcript}
            {interimTranscript && (
              <span className="text-text-secondary italic"> {interimTranscript}</span>
            )}
          </p>
        ) : !isSupported ? (
          <p className="text-sm text-text-secondary font-mono">
            Dictation demo requires a Chromium-based browser or Safari.
          </p>
        ) : (
          <p className="text-sm text-text-secondary font-mono">
            Press the mic to start dictating
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mb-4">
        {transcript && (
          <button
            onClick={handleCopy}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2 transition-all bg-white/5 text-text-primary border border-white/10 hover:bg-white/10 hover:border-white/20"
          >
            <Copy size={14} />
            Copy Text
          </button>
        )}
      </div>

      {/* Main toggle button */}
      <button
        onClick={toggle}
        disabled={!isSupported}
        className={`w-full rounded-xl px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
          isRecording
            ? 'bg-primary/20 text-primary border border-primary/30'
            : 'bg-primary text-bg-dark'
        }`}
      >
        {isRecording ? <Pause size={16} /> : <Mic size={16} />}
        {isRecording ? 'Stop Recording' : 'Start Dictation'}
      </button>
    </div>
  )
}

export default function Dictation() {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true })

  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="absolute inset-0 z-[1]">
          <Grainient
            color1="#f6854c"
            color2="#ffc0c0"
            color3="#07070f"
            timeSpeed={0.3}
            colorBalance={-0.05}
            warpStrength={1}
            warpFrequency={10}
            warpSpeed={2.5}
            warpAmplitude={50}
            blendAngle={-10}
            blendSoftness={0.06}
            rotationAmount={550}
            noiseScale={2.2}
            grainAmount={0.06}
            grainScale={1.8}
            grainAnimated={false}
            contrast={1.4}
            gamma={1}
            saturation={1.2}
            centerX={0}
            centerY={0.05}
            zoom={0.9}
          />
        </div>
        <Particles count={20} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 mb-8">
            <Mic size={14} className="text-primary" />
            <span className="text-xs font-medium text-primary">F9</span>
          </div>
          <h1 className="font-display text-5xl font-bold leading-tight text-text-primary md:text-7xl">
            Say it,{' '}
            <span className="text-gradient-primary">do not type it</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary drop-shadow-lg">
            Speak naturally and watch your words appear anywhere. Perfect for coding, emails, documents, and chat.
          </p>
        </motion.div>
      </section>

      {/* Demo */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <AnimatedSection direction="left">
            <WaveformVisualizer />
          </AnimatedSection>

          <AnimatedSection direction="right" ref={ref}>
            <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
              Your voice, everywhere
            </h2>
            <p className="mt-4 text-text-secondary leading-relaxed">
              Dictation works in any app on Windows. Code in your IDE, compose emails, write documents, or chat. Your voice becomes text instantly.
            </p>
            <ul className="mt-8 space-y-4">
              {[
                'Works in any Windows application',
                'Persistent memory across sessions',
                'One-tap corrections without breaking flow',
                'Local Whisper fallback when offline',
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-text-secondary">
                  <Check size={18} className="mt-0.5 shrink-0 text-primary" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link to="/download" className="btn-primary mt-8">
              Try Dictation <ArrowRight size={16} />
            </Link>
          </AnimatedSection>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <AnimatedSection className="text-center mb-16">
          <h2 className="font-display text-3xl font-bold text-text-primary">How it works</h2>
        </AnimatedSection>
        <div className="grid gap-8 md:grid-cols-3">
          {[
            { step: '01', title: 'Press F9', desc: 'Hit the hotkey from anywhere. The mic activates instantly.' },
            { step: '02', title: 'Speak naturally', desc: 'Talk as you normally would. Wiztant transcribes in real time.' },
            { step: '03', title: 'Text appears', desc: 'Your words paste at the cursor position. No copy-paste needed.' },
          ].map((item, i) => (
            <AnimatedSection key={item.step} delay={i * 0.15}>
              <div className="card text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full border border-primary/20 bg-primary/5 text-primary font-display font-bold mb-4">
                  {item.step}
                </div>
                <h3 className="font-display text-lg font-semibold text-text-primary">{item.title}</h3>
                <p className="mt-2 text-sm text-text-secondary">{item.desc}</p>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 py-20 text-center">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary">
            Dictation is free for all users
          </h2>
          <p className="mt-3 text-text-secondary">
            No account needed. Download and start speaking.
          </p>
          <Link to="/download" className="btn-primary mt-8">
            Download Wiztant <ArrowRight size={16} />
          </Link>
        </AnimatedSection>
      </section>
    </div>
  )
}
