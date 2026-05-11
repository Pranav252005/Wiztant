import { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useCredits } from '../hooks/useCredits'
import { getFeaturePreview, getTierCredits } from '../lib/credits'
import PaymentModal from '../components/PaymentModal'
import {
  Wallet,
  Zap,
  TrendingUp,
  Package,
  RefreshCw,
  Crown,
  Check,
  AlertCircle,
  Loader2,
  CreditCard,
  Calendar,
  XCircle,
} from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'

const TIER_META = {
  free: { label: 'Free', price: 0, color: 'text-text-secondary', bg: 'bg-white/5' },
  pro: { label: 'Pro', price: 20, color: 'text-primary', bg: 'bg-primary/10' },
  power: { label: 'Power', price: 50, color: 'text-warning', bg: 'bg-warning/10' },
}

const ALL_FEATURES = [
  'RePrompt — AI prompt optimization',
  'Dictation — Voice-to-text everywhere',
  'Agent — Autonomous screen control',
  'TaskStack — Smart task management',
  'TuneHub — Adaptive AI tuning',
  'Unlimited memory history',
  'Standard & deep system access',
  'Top-tier AI models',
]

export default function Settings() {
  const { user, signOut } = useAuth()
  const { credits, transactions, payments, loading, usagePercent, upgradeTier, refreshTransactions, refreshPayments } = useCredits(user)
  const [upgrading, setUpgrading] = useState(false)
  const [msg, setMsg] = useState(null)
  const [selectedTier, setSelectedTier] = useState(null)

  // Handle payment return URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('payment') === 'success') {
      setMsg({ type: 'success', text: 'Payment successful! Your credits have been updated.' })
      window.history.replaceState({}, '', window.location.pathname)
    }
    if (params.get('payment') === 'canceled') {
      setMsg({ type: 'error', text: 'Payment canceled. You can try again anytime.' })
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  useEffect(() => {
    if (user) {
      refreshTransactions()
      refreshPayments()
    }
  }, [user, refreshTransactions, refreshPayments])

  if (!user) {
    return (
      <div className="relative flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
        <Aurora />
        <h1 className="font-display text-3xl font-bold text-text-primary">Account Settings</h1>
        <p className="mt-4 text-text-secondary">Sign in to view your credits and manage your plan.</p>
      </div>
    )
  }

  const handleUpgrade = async (tier) => {
    setUpgrading(true)
    setMsg(null)
    const { error } = await upgradeTier(tier)
    if (error) setMsg({ type: 'error', text: error.message })
    else setMsg({ type: 'success', text: `Upgraded to ${TIER_META[tier].label}! Credits refreshed.` })
    setUpgrading(false)
  }

  const currentTier = credits?.tier || 'free'
  const balance = credits?.balance ?? 0
  const allocation = credits?.monthly_allocation ?? getTierCredits('free')
  const featurePreview = getFeaturePreview()
  const subscriptionStatus = credits?.subscription_status
  const subscriptionProvider = credits?.provider
  const currentPeriodEnd = credits?.current_period_end

  const isSubscribed = subscriptionStatus === 'active' && currentTier !== 'free'

  return (
    <div>
      <section className="relative flex min-h-[40vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <AnimatedSection className="relative z-10 max-w-3xl">
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-5xl">Account & Credits</h1>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            Manage your plan, monitor usage, and see exactly how your credits work.
          </p>
        </AnimatedSection>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-24">
        {/* Credit Card */}
        <AnimatedSection>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Wallet size={20} />
                  </div>
                  <div>
                    <h2 className="font-display text-lg font-semibold text-text-primary">Credit Balance</h2>
                    <p className="text-sm text-text-secondary">
                      Plan: <span className={TIER_META[currentTier].color}>{TIER_META[currentTier].label}</span>
                    </p>
                  </div>
                </div>

                <div className="mt-6">
                  <div className="flex items-baseline gap-2">
                    <span className="font-display text-5xl font-bold text-text-primary">{balance}</span>
                    <span className="text-text-secondary">/ {allocation} credits</span>
                  </div>
                  <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-700"
                      style={{ width: `${usagePercent}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-text-secondary">
                    {usagePercent}% used · {allocation - balance} credits remaining
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 md:w-64">
                <h3 className="text-sm font-semibold text-text-primary">Plan</h3>

                {/* Subscription info */}
                {isSubscribed && (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <CreditCard size={14} className="text-primary" />
                      <span className="capitalize">{subscriptionProvider}</span>
                      <span className="rounded-full bg-success/10 px-2 py-0.5 text-[10px] text-success">Active</span>
                    </div>
                    {currentPeriodEnd && (
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-text-secondary">
                        <Calendar size={12} />
                        Renews {new Date(currentPeriodEnd).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                )}

                <button
                  onClick={() => handleUpgrade('free')}
                  disabled={currentTier === 'free' || upgrading}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-all ${
                    currentTier === 'free'
                      ? 'border border-white/10 bg-white/5 text-text-secondary'
                      : 'border border-white/10 bg-white/5 text-text-primary hover:bg-white/10'
                  }`}
                >
                  <span className="flex items-center gap-2"><Package size={16} /> Free</span>
                  {currentTier === 'free' && <Check size={16} className="text-success" />}
                </button>
                <button
                  onClick={() => setSelectedTier('pro')}
                  disabled={currentTier === 'pro'}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-all ${
                    currentTier === 'pro'
                      ? 'border border-primary/30 bg-primary/10 text-primary'
                      : 'border border-white/10 bg-white/5 text-text-primary hover:bg-white/10'
                  }`}
                >
                  <span className="flex items-center gap-2"><Zap size={16} /> Pro — $20/mo</span>
                  {currentTier === 'pro' && <Check size={16} className="text-success" />}
                </button>
                <button
                  onClick={() => setSelectedTier('power')}
                  disabled={currentTier === 'power'}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-all ${
                    currentTier === 'power'
                      ? 'border border-warning/30 bg-warning/10 text-warning'
                      : 'border border-white/10 bg-white/5 text-text-primary hover:bg-white/10'
                  }`}
                >
                  <span className="flex items-center gap-2"><Crown size={16} /> Power — $50/mo</span>
                  {currentTier === 'power' && <Check size={16} className="text-success" />}
                </button>
                {upgrading && (
                  <div className="flex items-center gap-2 text-xs text-text-secondary">
                    <Loader2 size={14} className="animate-spin" /> Updating plan...
                  </div>
                )}
                {msg && (
                  <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
                    msg.type === 'error' ? 'bg-error/10 text-error' : 'bg-success/10 text-success'
                  }`}>
                    <AlertCircle size={14} />
                    {msg.text}
                  </div>
                )}
              </div>
            </div>
          </div>
        </AnimatedSection>

        {/* Feature Costs */}
        <AnimatedSection className="mt-8">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <h3 className="font-display text-lg font-semibold text-text-primary flex items-center gap-2">
              <TrendingUp size={18} className="text-primary" />
              Feature Costs
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Credits are deducted based on actual AI usage. Same cost across all plans.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {featurePreview.map((item) => (
                <div key={item.feature} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">{item.feature}</span>
                    <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold text-primary">
                      {item.credits} cr
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">{item.note}{item.model ? ` · ${item.model}` : ''}</p>
                </div>
              ))}
            </div>
          </div>
        </AnimatedSection>

        {/* What's Included */}
        <AnimatedSection className="mt-8">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <h3 className="font-display text-lg font-semibold text-text-primary flex items-center gap-2">
              <Check size={18} className="text-success" />
              Every Plan Includes
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              No feature gating. Upgrade only for more credits.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {ALL_FEATURES.map((f) => (
                <div key={f} className="flex items-center gap-3 text-sm text-text-secondary">
                  <Check size={16} className="shrink-0 text-success" />
                  {f}
                </div>
              ))}
            </div>
          </div>
        </AnimatedSection>

        {/* Payment History */}
        <AnimatedSection className="mt-8">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <h3 className="font-display text-lg font-semibold text-text-primary flex items-center gap-2">
              <CreditCard size={18} className="text-primary" />
              Payment History
            </h3>
            {payments.length === 0 ? (
              <p className="mt-4 text-sm text-text-secondary">No payments yet. Subscribe to a plan to see history.</p>
            ) : (
              <div className="mt-4 divide-y divide-white/[0.04]">
                {payments.map((p) => (
                  <div key={p.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium text-text-primary capitalize">{p.provider}</p>
                      <p className="text-xs text-text-secondary">{new Date(p.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-bold text-text-primary">
                        ${(p.amount / 100).toFixed(2)} {p.currency}
                      </span>
                      <p className="text-xs text-text-secondary capitalize">{p.status}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </AnimatedSection>

        {/* Transaction History */}
        <AnimatedSection className="mt-8">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <h3 className="font-display text-lg font-semibold text-text-primary flex items-center gap-2">
              <RefreshCw size={18} className="text-primary" />
              Recent Usage
            </h3>
            {transactions.length === 0 ? (
              <p className="mt-4 text-sm text-text-secondary">No usage yet. Start using Wiztant to see your credit history.</p>
            ) : (
              <div className="mt-4 divide-y divide-white/[0.04]">
                {transactions.map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium text-text-primary capitalize">{tx.feature.replace(/_/g, ' ')}</p>
                      {tx.model && <p className="text-xs text-text-secondary">{tx.model.split('/')[1]}</p>}
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-bold text-error">-{tx.amount}</span>
                      <p className="text-xs text-text-secondary">{tx.balance_after} left</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </AnimatedSection>

        {/* Account */}
        <AnimatedSection className="mt-8">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
            <h3 className="font-display text-lg font-semibold text-text-primary">Account</h3>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-text-primary">{user.email}</p>
                <p className="text-xs text-text-secondary">User ID: {user.id.slice(0, 8)}...</p>
              </div>
              <button
                onClick={signOut}
                className="btn-secondary"
              >
                Sign Out
              </button>
            </div>
          </div>
        </AnimatedSection>
      </section>

      {selectedTier && (
        <PaymentModal
          tier={selectedTier}
          user={user}
          onClose={() => setSelectedTier(null)}
        />
      )}
    </div>
  )
}
