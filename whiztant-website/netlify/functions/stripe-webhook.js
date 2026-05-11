import Stripe from 'stripe'
import { createClient } from '@supabase/supabase-js'

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2024-12-18.acacia' })

const supabaseAdmin = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

const supabaseApp = createClient(
  process.env.APP_SUPABASE_URL,
  process.env.APP_SUPABASE_SERVICE_ROLE_KEY
)

const TIER_CREDITS = {
  pro: 1000,
  power: 5000,
}

async function activateSubscription(userId, tier, subscriptionId, currentPeriodEnd) {
  const allocation = TIER_CREDITS[tier]
  const resetAt = new Date().toISOString()

  // Update website DB
  const { error } = await supabaseAdmin
    .from('user_credits')
    .upsert({
      user_id: userId,
      tier,
      balance: allocation,
      monthly_allocation: allocation,
      provider: 'stripe',
      subscription_id: subscriptionId,
      subscription_status: 'active',
      current_period_end: currentPeriodEnd,
      reset_at: resetAt,
    })
  if (error) console.error('[stripe-webhook] upsert error:', error)

  // Sync to app DB
  try {
    await supabaseApp
      .from('credits')
      .upsert({
        user_id: userId,
        balance: allocation,
        tier,
        reset_at: resetAt,
      })
  } catch (syncErr) {
    console.error('[stripe-webhook] app sync error:', syncErr)
  }
}

async function logPayment(userId, amount, currency, status, subscriptionId, invoiceId) {
  await supabaseAdmin.from('payment_history').insert({
    user_id: userId,
    provider: 'stripe',
    amount,
    currency,
    status,
    subscription_id: subscriptionId,
    invoice_id: invoiceId,
  })
}

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: { 'Access-Control-Allow-Origin': '*' } }
  }
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' }
  }

  const sig = event.headers['stripe-signature']
  let stripeEvent

  try {
    stripeEvent = stripe.webhooks.constructEvent(
      event.body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    )
  } catch (err) {
    console.error('[stripe-webhook] signature error:', err.message)
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid signature' }) }
  }

  try {
    switch (stripeEvent.type) {
      case 'checkout.session.completed': {
        const session = stripeEvent.data.object
        const userId = session.metadata?.user_id
        const tier = session.metadata?.tier
        if (!userId || !tier) break

        const subscription = await stripe.subscriptions.retrieve(session.subscription)
        await activateSubscription(
          userId,
          tier,
          subscription.id,
          subscription.current_period_end
            ? new Date(subscription.current_period_end * 1000).toISOString()
            : null
        )
        break
      }

      case 'invoice.paid': {
        const invoice = stripeEvent.data.object
        const subscription = await stripe.subscriptions.retrieve(invoice.subscription)
        const userId = subscription.metadata?.user_id || invoice.subscription_details?.metadata?.user_id
        const tier = subscription.metadata?.tier

        if (userId && tier) {
          await activateSubscription(
            userId,
            tier,
            subscription.id,
            subscription.current_period_end
              ? new Date(subscription.current_period_end * 1000).toISOString()
              : null
          )
          await logPayment(
            userId,
            invoice.amount_paid,
            invoice.currency?.toUpperCase(),
            'paid',
            subscription.id,
            invoice.id
          )
        }
        break
      }

      case 'customer.subscription.deleted': {
        const subscription = stripeEvent.data.object
        const userId = subscription.metadata?.user_id
        if (userId) {
          await supabaseAdmin
            .from('user_credits')
            .update({ subscription_status: 'canceled' })
            .eq('user_id', userId)
          // Sync cancel to app
          try {
            await supabaseApp
              .from('credits')
              .update({ tier: 'free', balance: 50 })
              .eq('user_id', userId)
          } catch (syncErr) {
            console.error('[stripe-webhook] app sync cancel error:', syncErr)
          }
        }
        break
      }

      default:
        break
    }

    return { statusCode: 200, body: JSON.stringify({ received: true }) }
  } catch (err) {
    console.error('[stripe-webhook]', err)
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) }
  }
}
