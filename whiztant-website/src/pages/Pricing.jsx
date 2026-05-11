import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ArrowRight, Zap, Mic, Bot, ListTodo, Sparkles, Sliders, Crown, Wallet, MapPin, CreditCard } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'
import { getFeaturePreview } from '../lib/credits'
import { useAuth } from '../hooks/useAuth'
import PaymentModal from '../components/PaymentModal'

const tiers = [
  {
    name: 'Free',
    tier: 'free',
    monthlyPrice: 0,
    annualPrice: 0,
    credits: 50,
    description: 'Try everything. One-time credits to evaluate Wiztant.',
    cta: 'Get Started',
    highlight: false,
  },
  {
    name: 'Pro',
    tier: 'pro',
    monthlyPrice: 20,
    annualPrice: 220,
    credits: 1000,
    description: 'For professionals who use AI daily. Best value.',
    cta: 'Choose Pro',
    highlight: true,
    badge: 'Most Popular',
  },
  {
    name: 'Power',
    tier: 'power',
    monthlyPrice: 50,
    annualPrice: 550,
    credits: 5000,
    description: 'For power users and teams who need serious volume.',
    cta: 'Choose Power',
    highlight: false,
  },
]

const allFeatures = [
  { icon: Zap, label: 'RePrompt' },
  { icon: Mic, label: 'Dictation' },
  { icon: Bot, label: 'Agent' },
  { icon: ListTodo, label: 'TaskStack' },
  { icon: Sliders, label: 'TuneHub' },
  { icon: Sparkles, label: 'All AI Models' },
  { icon: Wallet, label: 'Unlimited Memory' },
  { icon: Crown, label: 'Deep System Access' },
]

export default function Pricing() {
  const [annual, setAnnual] = useState(false)
  const [selectedTier, setSelectedTier] = useState(null)
  const { user } = useAuth()
  const featurePreview = getFeaturePreview()

  return (
    <div>
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <AnimatedSection className="relative z-10 max-w-4xl">
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            Transparent credit pricing
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            Every feature is included in every plan. You only pay for how much you use. Pick a plan for your monthly credit budget.
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

      {/* Tiers */}
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

                <div className="mt-5 flex items-center gap-2 rounded-xl bg-primary/5 px-4 py-3">
                  <Wallet size={18} className="text-primary" />
                  <div>
                    <span className="text-lg font-bold text-primary">{tier.credits.toLocaleString()}</span>
                    <span className="ml-1 text-xs text-text-secondary">credits / month</span>
                  </div>
                </div>

                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">All Features</p>
                  <div className="grid grid-cols-2 gap-2">
                    {allFeatures.map((f) => (
                      <div key={f.label} className="flex items-center gap-2 text-xs text-text-secondary">
                        <f.icon size={13} className="shrink-0 text-primary/70" />
                        {f.label}
                      </div>
                    ))}
                  </div>
                </div>

                {tier.tier === 'free' ? (
                  <Link
                    to={user ? '/settings' : '/download'}
                    className={`mt-8 inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-transform hover:scale-105 ${
                      tier.highlight
                        ? 'bg-primary text-bg-dark'
                        : 'border border-white/10 bg-white/5 text-text-primary'
                    }`}
                  >
                    {tier.cta} <ArrowRight size={16} />
                  </Link>
                ) : (
                  <button
                    onClick={() => setSelectedTier(tier.tier)}
                    className={`mt-8 inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-transform hover:scale-105 w-full ${
                      tier.highlight
                        ? 'bg-primary text-bg-dark'
                        : 'border border-white/10 bg-white/5 text-text-primary'
                    }`}
                  >
                    {user ? tier.cta : 'Sign In to Subscribe'} <ArrowRight size={16} />
                  </button>
                )}
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* Feature Costs */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <AnimatedSection>
          <div className="text-center mb-10">
            <h2 className="font-display text-2xl font-bold text-text-primary">What credits buy you</h2>
            <p className="mt-2 text-text-secondary">
              Costs are identical across all plans. Pick a cheaper model, spend fewer credits.
            </p>
          </div>
        </AnimatedSection>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {featurePreview.map((item, i) => (
            <AnimatedSection key={item.feature} delay={i * 0.05}>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 transition-all hover:border-primary/20">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">{item.feature}</span>
                  <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold text-primary">
                    {item.credits} cr
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-secondary">{item.note}{item.model ? ` · ${item.model}` : ''}</p>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* Models teaser */}
      <section className="mx-auto max-w-3xl px-6 pb-16 text-center">
        <AnimatedSection>
          <p className="text-sm text-text-secondary">
            Featuring top-tier models including GPT-5.5, Claude Sonnet 4.6, Gemini 3.1 Pro, and more.
            Switch models anytime based on your quality and speed needs.
          </p>
        </AnimatedSection>
      </section>

      {selectedTier && user && (
        <PaymentModal
          tier={selectedTier}
          user={user}
          onClose={() => setSelectedTier(null)}
        />
      )}

      {/* FAQ */}
      <section className="mx-auto max-w-3xl px-6 pb-24">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary text-center mb-8">FAQ</h2>
          <div className="space-y-4">
            {[
              {
                q: 'Do credits roll over?',
                a: 'No. Credits reset monthly on your billing date. Use them or lose them.',
              },
              {
                q: 'Are all features really included in Free?',
                a: 'Yes. Free gets 50 credits to try everything — RePrompt, Dictation, Agent, TaskStack, TuneHub. No feature gates.',
              },
              {
                q: 'Can I change my plan anytime?',
                a: 'Absolutely. Upgrade or downgrade from your Settings page. Changes apply immediately.',
              },
              {
                q: 'How is credit cost calculated?',
                a: 'credits = ceil(API cost × 5 / cost_per_credit). You pay for actual tokens used, not estimates.',
              },
            ].map((faq) => (
              <div key={faq.q} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                <p className="text-sm font-semibold text-text-primary">{faq.q}</p>
                <p className="mt-1 text-sm text-text-secondary">{faq.a}</p>
              </div>
            ))}
          </div>
        </AnimatedSection>
      </section>
    </div>
  )
}
