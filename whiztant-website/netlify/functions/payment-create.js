import Razorpay from 'razorpay'
import Stripe from 'stripe'
import { createClient } from '@supabase/supabase-js'

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID,
  key_secret: process.env.RAZORPAY_KEY_SECRET,
})

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2024-12-18.acacia' })

const supabaseAdmin = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

const SITE_URL = process.env.URL || 'https://wiztant.netlify.app'

const TIER_CONFIG = {
  pro: { razorpay_plan: process.env.RAZORPAY_PLAN_PRO, stripe_price: process.env.STRIPE_PRICE_PRO },
  power: { razorpay_plan: process.env.RAZORPAY_PLAN_POWER, stripe_price: process.env.STRIPE_PRICE_POWER },
}

const TIER_CREDITS = {
  pro: 1000,
  power: 5000,
}

export const handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) }
  }

  let body
  try {
    body = JSON.parse(event.body)
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid JSON' }) }
  }

  const { tier, provider, user_id, email } = body
  if (!tier || !provider || !user_id || !email) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing fields' }) }
  }

  // Verify user exists
  const { data: userData, error: userError } = await supabaseAdmin.auth.admin.getUserById(user_id)
  if (userError || !userData?.user) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Invalid user' }) }
  }

  try {
    if (provider === 'razorpay') {
      const config = TIER_CONFIG[tier]
      if (!config?.razorpay_plan) {
        return { statusCode: 500, body: JSON.stringify({ error: 'Razorpay plan not configured' }) }
      }

      const subscription = await razorpay.subscriptions.create({
        plan_id: config.razorpay_plan,
        customer_notify: 1,
        total_count: 12,
        notes: { user_id, tier, credits: TIER_CREDITS[tier] },
      })

      return {
        statusCode: 200,
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({
          checkout_url: subscription.short_url,
          subscription_id: subscription.id,
        }),
      }
    }

    if (provider === 'stripe') {
      const config = TIER_CONFIG[tier]
      if (!config?.stripe_price) {
        return { statusCode: 500, body: JSON.stringify({ error: 'Stripe price not configured' }) }
      }

      const session = await stripe.checkout.sessions.create({
        mode: 'subscription',
        line_items: [{ price: config.stripe_price, quantity: 1 }],
        success_url: `${SITE_URL}/settings?payment=success&provider=stripe`,
        cancel_url: `${SITE_URL}/pricing?payment=canceled`,
        metadata: { user_id, tier, credits: String(TIER_CREDITS[tier]) },
        customer_email: email,
      })

      return {
        statusCode: 200,
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({
          session_id: session.id,
          url: session.url,
        }),
      }
    }

    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid provider' }) }
  } catch (err) {
    console.error('[payment-create]', err)
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) }
  }
}
