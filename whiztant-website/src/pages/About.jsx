import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Target, Eye, Heart, Users, Zap, Globe, Shield, Sparkles } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

const values = [
  {
    icon: Zap,
    title: 'Speed First',
    desc: 'Every millisecond matters. Wiztant is designed to feel instant, from hotkey to result.',
  },
  {
    icon: Shield,
    title: 'Privacy by Design',
    desc: 'Your voice, screen, and data stay yours. Local processing where possible, encryption everywhere else.',
  },
  {
    icon: Users,
    title: 'Built for Humans',
    desc: 'No corporate jargon. No confusing settings. Just powerful tools that feel obvious to use.',
  },
  {
    icon: Globe,
    title: 'Accessible to All',
    desc: 'Free tier that actually works. No paywalls on core features. AI assistance should not be a luxury.',
  },
]

const milestones = [
  { year: '2024', title: 'The Spark', desc: 'Wiztant started as a weekend project to dictation faster without cloud dependencies.' },
  { year: '2025', title: 'First Release', desc: 'Launched with Dictation and RePrompt. 10,000 downloads in the first month.' },
  { year: '2025', title: 'Agent Arrives', desc: 'Added vision-based task automation. Wiztant became more than a voice tool.' },
  { year: '2026', title: 'Growing Ecosystem', desc: 'TaskStack and advanced RePrompt joined the suite. 100,000+ active users worldwide.' },
]

export default function About() {
  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-[60vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={20} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">Our Story</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Built by builders,<br />
            <span className="text-gradient-primary">for builders</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            We believe AI should work for you, not the other way around. Wiztant exists to remove the friction between thought and action.
          </p>
        </motion.div>
      </section>

      {/* Mission */}
      <section className="mx-auto max-w-7xl px-6 py-24">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <AnimatedSection direction="left">
            <div className="space-y-8">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5">
                  <Target size={22} className="text-primary" />
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-text-primary">Mission</h3>
                  <p className="mt-2 text-text-secondary leading-relaxed">
                    To make AI assistance as natural as breathing. No interfaces to learn, no apps to open. Just think, speak, and let Wiztant handle the rest.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5">
                  <Eye size={22} className="text-primary" />
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-text-primary">Vision</h3>
                  <p className="mt-2 text-text-secondary leading-relaxed">
                    A world where technology adapts to humans, not the reverse. Where your computer anticipates your needs before you articulate them.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5">
                  <Heart size={22} className="text-primary" />
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-text-primary">Values</h3>
                  <p className="mt-2 text-text-secondary leading-relaxed">
                    Transparency, user sovereignty, and relentless optimization. We ship fast, listen harder, and never lock you in.
                  </p>
                </div>
              </div>
            </div>
          </AnimatedSection>

          <AnimatedSection direction="right">
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center">
                  <p className="font-display text-3xl font-bold text-primary">100K+</p>
                  <p className="mt-1 text-sm text-text-secondary">Active Users</p>
                </div>
                <div className="text-center">
                  <p className="font-display text-3xl font-bold text-primary">5M+</p>
                  <p className="mt-1 text-sm text-text-secondary">Tasks Automated</p>
                </div>
                <div className="text-center">
                  <p className="font-display text-3xl font-bold text-primary">50+</p>
                  <p className="mt-1 text-sm text-text-secondary">Countries</p>
                </div>
                <div className="text-center">
                  <p className="font-display text-3xl font-bold text-primary">99.9%</p>
                  <p className="mt-1 text-sm text-text-secondary">Uptime</p>
                </div>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Values */}
      <section className="mx-auto max-w-7xl px-6 py-24">
        <AnimatedSection className="mb-16 text-center">
          <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">What drives us</h2>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            These principles shape every decision we make, from code to customer support.
          </p>
        </AnimatedSection>

        <div className="grid gap-6 md:grid-cols-2">
          {values.map((v, i) => (
            <AnimatedSection key={v.title} delay={i * 0.1}>
              <div className="card flex items-start gap-5">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5">
                  <v.icon size={22} className="text-primary" />
                </div>
                <div>
                  <h3 className="font-display text-lg font-semibold text-text-primary">{v.title}</h3>
                  <p className="mt-2 text-sm text-text-secondary leading-relaxed">{v.desc}</p>
                </div>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* Timeline */}
      <section className="mx-auto max-w-4xl px-6 py-24">
        <AnimatedSection className="mb-16 text-center">
          <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">Our journey</h2>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            From a weekend hack to a productivity suite used worldwide.
          </p>
        </AnimatedSection>

        <div className="relative">
          <div className="absolute left-6 top-0 bottom-0 w-px bg-white/[0.06] hidden md:block" />
          <div className="space-y-12">
            {milestones.map((m, i) => (
              <AnimatedSection key={m.year} delay={i * 0.1}>
                <div className="relative flex flex-col md:flex-row md:items-start gap-4 md:gap-8">
                  <div className="flex items-center gap-4 md:block">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-primary/20 bg-primary/5 font-display font-bold text-primary md:mb-0">
                      {m.year.slice(2)}
                    </div>
                  </div>
                  <div className="md:pt-2">
                    <span className="text-xs font-mono text-primary">{m.year}</span>
                    <h3 className="font-display text-lg font-semibold text-text-primary mt-1">{m.title}</h3>
                    <p className="mt-2 text-sm text-text-secondary leading-relaxed">{m.desc}</p>
                  </div>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 py-24 text-center">
        <AnimatedSection>
          <Sparkles size={32} className="mx-auto mb-6 text-primary" />
          <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
            Join the movement
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-text-secondary">
            Be part of a community that believes AI should amplify human potential, not replace it.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link to="/download" className="btn-primary">
              Download Wiztant
            </Link>
            <Link to="/contact" className="btn-secondary">
              Get in Touch
            </Link>
          </div>
        </AnimatedSection>
      </section>
    </div>
  )
}
