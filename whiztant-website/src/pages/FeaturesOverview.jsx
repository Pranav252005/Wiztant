import { Link } from 'react-router-dom'
import { ArrowRight, Zap, Mic, Bot, ListTodo } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

const features = [
  {
    icon: Zap,
    title: 'RePrompt',
    desc: 'Rewrite prompts faster with AI-powered personas. One tap, instant refinement.',
    to: '/features/reprompt',
    hotkey: 'Ctrl+Space',
  },
  {
    icon: Mic,
    title: 'Dictation',
    desc: 'Speak, do not type. Perfect for hands-free coding, writing, and quick notes.',
    to: '/features/dictation',
    hotkey: 'F9',
  },
  {
    icon: Bot,
    title: 'Agent',
    desc: 'Autonomous multi-step tasks. Click, type, control, all hands-free.',
    to: '/features/agent',
    hotkey: 'F9 x2',
  },
  {
    icon: ListTodo,
    title: 'TaskStack',
    desc: 'Dump your tasks anytime. It sorts, schedules, and reminds you so nothing slips.',
    to: '/features/taskstack',
    hotkey: 'F10',
  },
]

export default function FeaturesOverview() {
  return (
    <div className="pt-8">
      <section className="relative flex min-h-[60vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={25} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <AnimatedSection className="relative z-10 max-w-4xl">
          <p className="eyebrow mb-6">The AI operating assistant</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Everything Wiztant does
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            Understands your voice. Learns your patterns. Anticipates your needs. Keeps you on track.
          </p>
        </AnimatedSection>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-6 md:grid-cols-2">
          {features.map((f, i) => (
            <AnimatedSection key={f.title} delay={i * 0.1}>
              <Link
                to={f.to}
                className="group card block"
              >
                <div className="flex items-center justify-between mb-6">
                  <f.icon size={36} className="text-primary" />
                  <span className="kbd text-sm">{f.hotkey}</span>
                </div>
                <h3 className="font-display text-2xl font-bold text-text-primary">{f.title}</h3>
                <p className="mt-3 text-base leading-relaxed text-text-secondary">{f.desc}</p>
                <span className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary transition-colors">
                  Explore {f.title} <ArrowRight size={16} />
                </span>
              </Link>
            </AnimatedSection>
          ))}
        </div>
      </section>
    </div>
  )
}
