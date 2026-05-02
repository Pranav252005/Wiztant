import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ArrowRight } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

const tiers = [
  {
    name: 'Free',
    monthlyPrice: 0,
    annualPrice: 0,
    description: 'For casual users who want to try Wiztant.',
    features: [
      '15 chats per month',
      'RePrompt',
      'Dictation',
      '7-day memory history',
      'Standard system access',
      'GPT-5.4 mini',
    ],
    cta: 'Get Started',
    highlight: false,
  },
  {
    name: 'Pro',
    monthlyPrice: 15,
    annualPrice: 165,
    description: 'For professionals who use Agent daily.',
    features: [
      '300 chats per month',
      '50 agent tasks per month',
      'RePrompt',
      'Dictation',
      'TaskStack',
      'Unlimited memory history',
      'Standard system access',
      'GPT-5.4 mini',
    ],
    cta: 'Start Free Trial',
    highlight: true,
    badge: 'Most Popular',
  },
  {
    name: 'Power',
    monthlyPrice: 25,
    annualPrice: 275,
    description: 'For power users and teams.',
    features: [
      '500 chats per month',
      '200 agent tasks per month',
      'RePrompt',
      'Dictation',
      'TaskStack',
      'Unlimited memory history',
      'Deep system access',
      'GPT-5.4 full',
    ],
    cta: 'Start Free Trial',
    highlight: false,
  },
]

export default function Pricing() {
  const [annual, setAnnual] = useState(false)

  return (
    <div>
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <AnimatedSection className="relative z-10 max-w-4xl">
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Simple, transparent pricing
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            Start free. Upgrade when you need more power. No hidden fees.
          </p>

          <div className="mt-10 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.03] p-1">
            <button
              onClick={() => setAnnual(false)}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                !annual ? 'bg-primary text-bg-dark' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setAnnual(true)}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                annual ? 'bg-primary text-bg-dark' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Annual
            </button>
          </div>
          {annual && (
            <p className="mt-3 text-sm text-primary">Pay annually and save 1 month.</p>
          )}
        </AnimatedSection>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid gap-6 md:grid-cols-3">
          {tiers.map((tier, i) => (
            <AnimatedSection key={tier.name} delay={i * 0.15}>
              <div
                className={`relative flex h-full flex-col rounded-2xl border p-8 transition-all duration-300 ${
                  tier.highlight
                    ? 'border-primary/40 bg-white/[0.03] glow-primary md:scale-105'
                    : 'border-white/[0.06] bg-white/[0.02] hover:border-white/20'
                }`}
              >
                {tier.badge && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-bold text-bg-dark">
                    {tier.badge}
                  </span>
                )}
                <h3 className="font-display text-xl font-bold text-text-primary">{tier.name}</h3>
                <p className="mt-2 text-sm text-text-secondary">{tier.description}</p>
                <div className="mt-6 flex items-baseline gap-1">
                  <span className="font-display text-4xl font-bold text-text-primary">
                    ${annual ? tier.annualPrice : tier.monthlyPrice}
                  </span>
                  <span className="text-sm text-text-secondary">
                    {tier.monthlyPrice === 0 ? '' : annual ? '/year' : '/mo'}
                  </span>
                </div>
                {annual && tier.monthlyPrice > 0 && (
                  <p className="mt-1 text-xs text-text-secondary line-through">
                    Was ${tier.monthlyPrice * 12}/year
                  </p>
                )}
                <ul className="mt-8 flex-1 space-y-3">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-start gap-3 text-sm text-text-secondary">
                      <Check size={16} className="mt-0.5 shrink-0 text-primary" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  to="/download"
                  className={`mt-8 inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-transform hover:scale-105 ${
                    tier.highlight
                      ? 'bg-primary text-bg-dark'
                      : 'border border-white/10 bg-white/5 text-text-primary'
                  }`}
                >
                  {tier.cta} <ArrowRight size={16} />
                </Link>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-24 text-center">
        <AnimatedSection>
          <p className="text-sm text-text-secondary">
            All plans include a 3-day trial with 30 messages and 3 agent tasks. No credit card required to start.
          </p>
        </AnimatedSection>
      </section>
    </div>
  )
}
