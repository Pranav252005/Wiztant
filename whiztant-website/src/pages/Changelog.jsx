import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { GitCommit, ArrowRight, Zap, Bug, Sparkles, Shield, Download } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

const releases = [
  {
    version: '2.1.0',
    date: 'April 2026',
    status: 'latest',
    changes: [
      { type: 'feature', text: 'RePrompt multi-agent optimization now supports custom agent templates' },
      { type: 'feature', text: 'Dictation voice commands expanded: "select all", "copy", "paste"' },
      { type: 'improvement', text: 'Agent task success rate improved by 18% with UI-TARS v2' },
      { type: 'fix', text: 'Fixed memory leak in long-running Dictation sessions' },
      { type: 'fix', text: 'Resolved hotkey conflict with AutoHotkey scripts' },
    ]
  },
  {
    version: '2.0.0',
    date: 'March 2026',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'Introduced RePrompt multi-agent optimization' },
      { type: 'feature', text: 'New TaskStack smart scheduling with calendar integration' },
      { type: 'feature', text: 'Linux Wayland support for Dictation and Agent' },
      { type: 'improvement', text: 'Reduced startup time by 40%' },
      { type: 'improvement', text: 'Settings UI completely redesigned' },
      { type: 'security', text: 'API keys now stored in OS keychain instead of plain text' },
    ]
  },
  {
    version: '1.4.2',
    date: 'February 2026',
    status: 'stable',
    changes: [
      { type: 'fix', text: 'Agent coordinate mapping fixed for 4K displays with 200% scaling' },
      { type: 'fix', text: 'TaskStack duplicate reminder bug resolved' },
      { type: 'improvement', text: 'RePrompt latency reduced by 25%' },
    ]
  },
  {
    version: '1.4.0',
    date: 'January 2026',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'Agent Deep Access tier for Power subscribers' },
      { type: 'feature', text: 'Offline Whisper model auto-download' },
      { type: 'improvement', text: 'Added 12 new RePrompt personas' },
      { type: 'fix', text: 'Fixed crash when minimizing during Agent execution' },
    ]
  },
  {
    version: '1.3.0',
    date: 'December 2025',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'TaskStack released — smart task management with AI prioritization' },
      { type: 'feature', text: 'RePrompt now works in any text field system-wide' },
      { type: 'improvement', text: 'Dictation accuracy improved in noisy environments' },
    ]
  },
  {
    version: '1.2.0',
    date: 'November 2025',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'Agent mode with vision-based GUI control' },
      { type: 'feature', text: 'Custom hotkey mapping in Settings' },
      { type: 'improvement', text: 'Better error messages for network failures' },
    ]
  },
  {
    version: '1.1.0',
    date: 'October 2025',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'RePrompt with 6 built-in personas' },
      { type: 'feature', text: 'Persistent memory across sessions' },
      { type: 'fix', text: 'Fixed audio crackling on certain headsets' },
    ]
  },
  {
    version: '1.0.0',
    date: 'September 2025',
    status: 'stable',
    changes: [
      { type: 'feature', text: 'Initial release — Dictation and basic AI chat' },
      { type: 'feature', text: 'Global hotkey system' },
      { type: 'feature', text: 'Portable executable, no install required' },
    ]
  },
]

const typeConfig = {
  feature: { icon: Sparkles, label: 'New', color: 'text-primary bg-primary/10 border-primary/20' },
  improvement: { icon: Zap, label: 'Improved', color: 'text-warm bg-warm/10 border-warm/20' },
  fix: { icon: Bug, label: 'Fixed', color: 'text-success bg-success/10 border-success/20' },
  security: { icon: Shield, label: 'Security', color: 'text-error bg-error/10 border-error/20' },
}

export default function Changelog() {
  return (
    <div>
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">Updates</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Changelog
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            A history of improvements, fixes, and new features. Wiztant gets better every week.
          </p>
        </motion.div>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-20">
        <div className="relative">
          <div className="absolute left-6 top-0 bottom-0 w-px bg-white/[0.06]" />
          
          <div className="space-y-12">
            {releases.map((release, i) => (
              <AnimatedSection key={release.version} delay={i * 0.08}>
                <div className="relative flex gap-6">
                  <div className="flex flex-col items-center">
                    <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border text-sm font-bold ${
                      release.status === 'latest'
                        ? 'border-primary/30 bg-primary/10 text-primary'
                        : 'border-white/[0.06] bg-bg-dark text-text-secondary'
                    }`}>
                      <GitCommit size={18} />
                    </div>
                    {i < releases.length - 1 && (
                      <div className="mt-2 h-full w-px bg-white/[0.06]" />
                    )}
                  </div>

                  <div className="flex-1 pb-4">
                    <div className="flex flex-wrap items-center gap-3 mb-4">
                      <h3 className="font-display text-xl font-bold text-text-primary">
                        v{release.version}
                      </h3>
                      {release.status === 'latest' && (
                        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary border border-primary/20">
                          Latest
                        </span>
                      )}
                      <span className="text-xs text-text-secondary font-mono">{release.date}</span>
                    </div>

                    <div className="space-y-2">
                      {release.changes.map((change, ci) => {
                        const config = typeConfig[change.type]
                        const Icon = config.icon
                        return (
                          <div
                            key={ci}
                            className="flex items-start gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-4 py-3"
                          >
                            <span className={`flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${config.color}`}>
                              <Icon size={10} />
                              {config.label}
                            </span>
                            <p className="text-sm text-text-secondary pt-0.5">{change.text}</p>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20 text-center">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary">
            Stay up to date
          </h2>
          <p className="mt-3 text-text-secondary max-w-md mx-auto">
            Follow us on Twitter or join Discord for real-time updates and beta access.
          </p>
          <Link to="/download" className="btn-primary mt-8">
            <Download size={16} />
            Download Latest
          </Link>
        </AnimatedSection>
      </section>
    </div>
  )
}
