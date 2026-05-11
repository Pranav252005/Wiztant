import { useState } from 'react'
import { usePayments } from '../hooks/usePayments'
import { X, Loader2, CreditCard, Wallet, Globe, MapPin } from 'lucide-react'

const TIER_META = {
  pro: { label: 'Pro', price: 20, credits: 1000 },
  power: { label: 'Power', price: 50, credits: 5000 },
}

export default function PaymentModal({ tier, onClose, user }) {
  const { country, provider, loading, error, setProvider, createCheckout } = usePayments(user)
  const [started, setStarted] = useState(false)

  const meta = TIER_META[tier]
  if (!meta) return null

  const handlePay = async () => {
    setStarted(true)
    await createCheckout(tier)
    // For Stripe: page redirects, so we never get here
    // For Razorpay: opens new tab, stays on page
    setStarted(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="relative w-full max-w-md rounded-2xl border border-white/[0.06] bg-bg-dark p-6 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-secondary hover:text-text-primary transition-colors"
        >
          <X size={20} />
        </button>

        <h3 className="font-display text-xl font-bold text-text-primary">
          Upgrade to {meta.label}
        </h3>
        <p className="mt-1 text-sm text-text-secondary">
          ${meta.price}/month · {meta.credits.toLocaleString()} credits
        </p>

        <div className="mt-6 space-y-3">
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <MapPin size={14} />
            {country ? `Detected: ${country}` : 'Detecting location...'}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setProvider('razorpay')}
              className={`flex flex-col items-center gap-2 rounded-xl border px-4 py-3 text-sm transition-all ${
                provider === 'razorpay'
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-white/[0.06] bg-white/[0.02] text-text-secondary hover:border-white/20'
              }`}
            >
              <Wallet size={20} />
              <span className="font-medium">UPI / Cards</span>
              <span className="text-[10px] opacity-70">Razorpay · India</span>
            </button>
            <button
              onClick={() => setProvider('stripe')}
              className={`flex flex-col items-center gap-2 rounded-xl border px-4 py-3 text-sm transition-all ${
                provider === 'stripe'
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-white/[0.06] bg-white/[0.02] text-text-secondary hover:border-white/20'
              }`}
            >
              <CreditCard size={20} />
              <span className="font-medium">Card / Global</span>
              <span className="text-[10px] opacity-70">Stripe · Worldwide</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg bg-error/10 px-3 py-2 text-xs text-error">
            {error}
          </div>
        )}

        <button
          onClick={handlePay}
          disabled={loading || started || !provider}
          className="btn-primary mt-6 w-full"
        >
          {loading || started ? (
            <>
              <Loader2 size={16} className="animate-spin" /> Processing...
            </>
          ) : provider === 'razorpay' ? (
            <>
              <Wallet size={16} /> Pay with Razorpay
            </>
          ) : (
            <>
              <Globe size={16} /> Pay with Stripe
            </>
          )}
        </button>

        <p className="mt-3 text-center text-[11px] text-text-secondary">
          You can switch providers anytime before paying.
        </p>
      </div>
    </div>
  )
}
