import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, ArrowRight, Check, MousePointer, Eye, Zap } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Grainient from '../components/Grainient'
import Particles from '../components/Particles'

function AgentDemo() {
  const [step, setStep] = useState(0)
  const [isRunning, setIsRunning] = useState(false)

  const steps = [
    { action: 'Analyzing screen...', icon: Eye, progress: 20 },
    { action: 'Identifying UI elements...', icon: Eye, progress: 40 },
    { action: 'Planning click sequence...', icon: Zap, progress: 60 },
    { action: 'Executing click at (342, 518)', icon: MousePointer, progress: 80 },
    { action: 'Task complete', icon: Check, progress: 100 },
  ]

  const startAgent = () => {
    setIsRunning(true)
    setStep(0)
    let current = 0
    const interval = setInterval(() => {
      current++
      if (current >= steps.length) {
        clearInterval(interval)
        setIsRunning(false)
        return
      }
      setStep(current)
    }, 1200)
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8">
      <div className="flex items-center gap-2 mb-6">
        <Bot size={18} className="text-primary" />
        <span className="text-sm font-medium text-text-secondary">Agent Demo</span>
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-bg-dark p-4 mb-6 relative overflow-hidden" style={{ minHeight: '200px' }}>
        <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)', backgroundSize: '20px 20px' }} />

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="relative z-10"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                {steps[step] && (() => { const Icon = steps[step].icon; return <Icon size={16} className="text-primary" /> })()}
              </div>
              <span className="text-sm text-text-primary font-mono">{steps[step]?.action}</span>
            </div>

            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-primary rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${steps[step]?.progress}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </motion.div>
        </AnimatePresence>

        {step >= 3 && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute z-20"
            style={{ top: `${30 + step * 5}%`, left: `${40 + step * 8}%` }}
          >
            <div className="w-4 h-4 rounded-full bg-primary/60 animate-ping" />
            <div className="absolute inset-0 w-4 h-4 rounded-full bg-primary" />
          </motion.div>
        )}
      </div>

      <button
        onClick={startAgent}
        disabled={isRunning}
        className={`w-full rounded-xl px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-all ${
          isRunning
            ? 'bg-primary/20 text-primary/60 border border-primary/20 cursor-not-allowed'
            : 'bg-primary text-bg-dark hover:scale-[1.02]'
        }`}
      >
        <Bot size={16} />
        {isRunning ? 'Agent running...' : 'Start Agent Task'}
      </button>
    </div>
  )
}

export default function Agent() {
  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="absolute inset-0 z-[1]">
          <Grainient
            color1="#c08179"
            color2="#fecd89"
            color3="#07070f"
            timeSpeed={0.25}
            colorBalance={0.25}
            warpStrength={1.5}
            warpFrequency={3}
            warpSpeed={1.8}
            warpAmplitude={55}
            blendAngle={25}
            blendSoftness={0.1}
            rotationAmount={350}
            noiseScale={1.5}
            grainAmount={0.1}
            grainScale={2.5}
            grainAnimated={false}
            contrast={1.6}
            gamma={0.95}
            saturation={1.5}
            centerX={0.02}
            centerY={-0.02}
            zoom={0.8}
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
            <Bot size={14} className="text-primary" />
            <span className="text-xs font-medium text-primary">F9 x2</span>
          </div>
          <h1 className="font-display text-5xl font-bold leading-tight text-text-primary md:text-7xl">
            Your AI{' '}
            <span className="text-gradient-primary">does the work</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary drop-shadow-lg">
            Autonomous multi-step task automation with vision-based GUI control. Tell it what to do, watch it happen.
          </p>
        </motion.div>
      </section>

      {/* Demo */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <AnimatedSection direction="left">
            <AgentDemo />
          </AnimatedSection>

          <AnimatedSection direction="right">
            <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
              Vision-powered autonomy
            </h2>
            <p className="mt-4 text-text-secondary leading-relaxed">
              Agent sees your screen, understands the UI, and takes action. No APIs, no integrations, no setup. It works with any Windows application.
            </p>
            <ul className="mt-8 space-y-4">
              {[
                'Vision-based GUI control with UI-TARS model',
                'Three access tiers, Standard, System, and Deep',
                'Works across any Windows app without integration',
                'Multi-step task automation with natural language',
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-text-secondary">
                  <Check size={18} className="mt-0.5 shrink-0 text-primary" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link to="/download" className="btn-primary mt-8">
              Try Agent <ArrowRight size={16} />
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
            { step: '01', title: 'Describe the task', desc: 'Tell Agent what you need in plain English.' },
            { step: '02', title: 'AI analyzes', desc: 'It scans your screen and plans the actions needed.' },
            { step: '03', title: 'Watch it work', desc: 'Agent clicks, types, and navigates autonomously.' },
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
            Agent unlocks with Pro
          </h2>
          <p className="mt-3 text-text-secondary">
            50 agent tasks per month on Pro, 200 on Power.
          </p>
          <Link to="/pricing" className="btn-primary mt-8">
            View Pricing <ArrowRight size={16} />
          </Link>
        </AnimatedSection>
      </section>
    </div>
  )
}
