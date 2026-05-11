import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Download, Zap, Mic, Bot, ListTodo } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import SoftAurora from '../components/SoftAurora'
import TextType from '../components/TextType'
import Particles from '../components/Particles'
import ScrollVelocity from '../components/ScrollVelocity'
import ReviewsSection from '../components/ReviewsSection'

const features = [
  {
    icon: Zap,
    title: 'RePrompt',
    desc: 'Rewrite prompts faster with AI-powered personas.',
    to: '/features/reprompt',
    hotkey: 'Ctrl+Space',
    disabled: false,
  },
  {
    icon: Mic,
    title: 'Dictation',
    desc: 'Speak, do not type. Perfect for hands-free coding and writing.',
    to: '/features/dictation',
    hotkey: 'F9',
    disabled: false,
  },
  {
    icon: Bot,
    title: 'Agent',
    desc: 'Autonomous multi-step tasks. Click, type, control, all hands-free.',
    to: '/features/agent',
    hotkey: 'F9 x2',
    disabled: true,
  },
  {
    icon: ListTodo,
    title: 'TaskStack',
    desc: 'Dump your tasks anytime. It sorts, schedules, and reminds you.',
    to: '/features/taskstack',
    hotkey: 'F10',
    disabled: false,
  },
]

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="absolute inset-0 z-[1]">
          <SoftAurora
            speed={0.6}
            scale={1.5}
            brightness={1}
            color1="#fff6c0"
            color2="#f6a14c"
            noiseFrequency={1}
            noiseAmplitude={2}
            bandHeight={0.5}
            bandSpread={1}
            octaveDecay={0.1}
            layerOffset={0}
            colorSpeed={1}
            enableMouseInteraction={false}
            mouseInfluence={0.25}
          />
        </div>
        <Particles count={30} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">An AI that operates for you</p>
          <h1 className="font-display text-5xl font-bold leading-[1.1] tracking-tight text-text-primary md:text-7xl lg:text-7xl">
            Stop-
            <TextType
              as="span"
              text={['clicking', 'typing', 'skipping work', 'losing track', 'worrying']}
              className="text-gradient-primary"
              typingSpeed={80}
              deletingSpeed={40}
              pauseDuration={1800}
              cursorCharacter="/"
              showCursor={true}
              loop={true}
            />
            <br />
            Start thinking.
          </h1>
          <p className="mx-auto mt-8 max-w-2xl text-lg leading-relaxed text-text-secondary md:text-xl drop-shadow-lg">
            Understands your voice. Learns your patterns. Anticipates your needs. Keeps you on track.
          </p>
          <div className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link to="/download" className="btn-primary">
              <Download size={16} />
              Get Started Free
            </Link>
            <Link to="/how-it-works" className="btn-secondary">
              See How It Works
              <ArrowRight size={16} />
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Scrolling banner */}
      <div className="border-y border-white/[0.06] py-4 overflow-hidden">
        <ScrollVelocity
          text="RePrompt  •  Dictation  •  Agent  •  TaskStack  •  RePrompt  •  Dictation  •  Agent  •  TaskStack  •  "
          velocity={40}
          className="text-sm font-mono text-text-secondary tracking-widest"
        />
      </div>

      {/* Feature Grid */}
      <section className="mx-auto max-w-7xl px-6 py-28">
        <AnimatedSection className="mb-16 text-center">
          <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
            Four ways to work smarter
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            Every tool is designed to remove friction. Pick what fits your workflow.
          </p>
        </AnimatedSection>

        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {features.map((f, i) => (
            <AnimatedSection key={f.title} delay={i * 0.1}>
              {f.disabled ? (
                <div className="group card block opacity-50 grayscale cursor-not-allowed">
                  <div className="flex items-center justify-between mb-4">
                    <f.icon size={28} className="text-primary" />
                    <span className="kbd">{f.hotkey}</span>
                  </div>
                  <h3 className="font-display text-lg font-semibold text-text-primary">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">{f.desc}</p>
                  <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-text-secondary">
                    Coming Soon
                  </span>
                </div>
              ) : (
                <Link
                  to={f.to}
                  className="group card block"
                >
                  <div className="flex items-center justify-between mb-4">
                    <f.icon size={28} className="text-primary" />
                    <span className="kbd">{f.hotkey}</span>
                  </div>
                  <h3 className="font-display text-lg font-semibold text-text-primary">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">{f.desc}</p>
                  <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-text-secondary transition-colors group-hover:text-primary">
                    Learn more <ArrowRight size={14} />
                  </span>
                </Link>
              )}
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* Reviews */}
      <ReviewsSection />

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 py-28 text-center">
        <AnimatedSection>
          <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
            Ready to upgrade your workflow?
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-text-secondary">
            Download Wiztant for Windows and Linux. Free forever for Dictation and RePrompt.
          </p>
          <Link
            to="/download"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-primary px-10 py-4 text-base font-semibold text-bg-dark transition-transform hover:scale-105"
          >
            <Download size={18} />
            Download for Windows & Linux
          </Link>
          <p className="mt-3 text-xs text-text-secondary">Free. 15 chats per month. No credit card required.</p>
        </AnimatedSection>
      </section>
    </div>
  )
}
