import { useState, useEffect, useCallback } from 'react'
import { loadStripe } from '@stripe/stripe-js'

const STRIPE_PK = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || ''
const stripePromise = STRIPE_PK ? loadStripe(STRIPE_PK) : null

export function usePayments(user) {
  const [country, setCountry] = useState(null)
  const [provider, setProvider] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Detect location
  useEffect(() => {
    let cancelled = false
    fetch('https://ipapi.co/json/')
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        const isIndia = data.country_code === 'IN'
        setCountry(data.country_code)
        setProvider(isIndia ? 'razorpay' : 'stripe')
      })
      .catch(() => {
        if (cancelled) return
        setProvider('stripe') // fallback
      })
    return () => { cancelled = true }
  }, [])

  const createCheckout = useCallback(async (tier) => {
    if (!user || !provider) return { error: new Error('Not ready') }
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/.netlify/functions/payment-create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tier,
          provider,
          user_id: user.id,
          email: user.email,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to create checkout')

      if (provider === 'stripe') {
        const stripe = await stripePromise
        if (!stripe) throw new Error('Stripe not loaded')
        window.location.href = data.url
        return { data }
      }

      if (provider === 'razorpay') {
        // Open Razorpay checkout in new tab
        window.open(data.checkout_url, '_blank')
        return { data }
      }

      return { data }
    } catch (err) {
      setError(err.message)
      return { error: err }
    } finally {
      setLoading(false)
    }
  }, [user, provider])

  return {
    country,
    provider,
    loading,
    error,
    setProvider,
    createCheckout,
  }
}
