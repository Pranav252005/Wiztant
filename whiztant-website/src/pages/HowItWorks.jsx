import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, Keyboard, CreditCard, Monitor, ChevronDown, ListTodo } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

const steps = [
  {
    num: '01',
    icon: Download,
    title: 'Download and Install',
    text: 'Grab the portable build for your OS, run it, done. No installer wizard, no admin rights, no registry clutter.',
    cta: { to: '/download', label: 'Go to Download' },
  },
  {
    num: '02',
    icon: Keyboard,
    title: 'Set Your Hotkeys',
    text: 'F9 for Dictation, F9 twice for Agent, Ctrl+Space for RePrompt, F10 for TaskStack. Zero configuration, just press and go.',
  },
  {
    num: '03',
    icon: CreditCard,
    title: 'Choose Your Tier',
    text: 'Start free and upgrade anytime. Pro unlocks Agent and TaskStack and raises your monthly limits. Power tier is built for heavy users.',
    cta: { to: '/pricing', label: 'Compare Tiers' },
  },
  {
    num: '04',
    icon: Monitor,
    title: 'Use It Anywhere',
    text: 'Wiztant works everywhere you type, your browser, IDE, email, documents, chat apps. Available on Windows and Linux. It sits in the background until you need it.',
  },
]

const faqs = [
  { q: 'Is my data safe?', a: 'Yes. Voice data is processed locally or via secure cloud STT. Agent screenshots are processed in-memory and never stored on disk unless you explicitly enable logging.' },
  { q: 'Can I customize hotkeys?', a: 'Absolutely. Open Settings and remap any hotkey to whatever fits your muscle memory.' },
  { q: 'Does Agent work offline?', a: 'Dictation works with a local Whisper fallback. Agent and RePrompt require an internet connection for the LLM backend.' },
  { q: 'What operating systems are supported?', a: 'Windows 10, Windows 11, and major Linux distributions. Both 64-bit.' },
  { q: 'Is it really portable?', a: 'Yes. A single .exe file. Drop it on a USB drive and run it on any compatible PC.' },
  { q: 'Can I cancel my subscription?', a: 'Anytime. You keep Free tier access forever. No prorated refunds, but no lock-in either.' },
  { q: 'How do I get support?', a: 'Reach out via Discord or email. Response times are typically under 24 hours for Pro and Power users.' },
  { q: 'Is there a Mac version?', a: 'Not yet. Windows and Linux are our focus right now to ensure the best experience.' },
]

function StepCard({ step, index }) {
  return (
    <AnimatedSection delay={index * 0.12}>
      <div className="relative flex gap-6 md:gap-8">
        <div className="flex flex-col items-center">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-primary/20 bg-primary/5 text-sm font-bold text-primary">
            {step.num}
          </div>
          {index < steps.length - 1 && (
            <div className="mt-2 h-full w-px bg-white/[0.06]" />
          )}
        </div>
        <div className="pb-12">
          <step.icon size={24} className="mb-3 text-text-secondary" />
          <h3 className="font-display text-xl font-semibold text-text-primary">{step.title}</h3>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-text-secondary">{step.text}</p>
          {step.cta && (
            <Link
              to={step.cta.to}
              className="mt-4 inline-block text-sm font-medium text-primary transition-colors hover:underline"
            >
              {step.cta.label} &rarr;
            </Link>
          )}
        </div>
      </div>
    </AnimatedSection>
  )
}

function FAQItem({ faq }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-white/[0.06]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-5 text-left"
      >
        <span className="font-medium text-text-primary">{faq.q}</span>
        <ChevronDown
          size={18}
          className={`shrink-0 text-text-secondary transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <p className="pb-5 text-sm leading-relaxed text-text-secondary">{faq.a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function HowItWorks() {
  return (
    <div>
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <AnimatedSection className="relative z-10 max-w-4xl">
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Get Wiztant running in minutes
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            From download to first dictation in under a minute. Works on Windows and Linux.
          </p>
        </AnimatedSection>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-20">
        {steps.map((s, i) => (
          <StepCard key={s.num} step={s} index={i} />
        ))}
      </section>

      <section className="mx-auto max-w-3xl px-6 py-20">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary">Frequently asked questions</h2>
        </AnimatedSection>
        <div className="mt-8">
          {faqs.map((faq) => (
            <FAQItem key={faq.q} faq={faq} />
          ))}
        </div>
      </section>
    </div>
  )
}
