import crypto from 'crypto'
import { createClient } from '@supabase/supabase-js'

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

function verifySignature(body, signature, secret) {
  const expected = crypto.createHmac('sha256', secret).update(body).digest('hex')
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))
}

async function activateSubscription(userId, tier, subscriptionId, currentPeriodEnd) {
  const allocation = TIER_CREDITS[tier]
  const resetAt = new Date().toISOString()
  const periodEnd = currentPeriodEnd ? new Date(currentPeriodEnd * 1000).toISOString() : null

  // Update website DB
  const { error } = await supabaseAdmin
    .from('user_credits')
    .upsert({
      user_id: userId,
      tier,
      balance: allocation,
      monthly_allocation: allocation,
      provider: 'razorpay',
      subscription_id: subscriptionId,
      subscription_status: 'active',
      current_period_end: periodEnd,
      reset_at: resetAt,
    })
  if (error) console.error('[razorpay-webhook] upsert error:', error)

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
    console.error('[razorpay-webhook] app sync error:', syncErr)
  }
}

async function logPayment(userId, amount, currency, status, subscriptionId, invoiceId) {
  await supabaseAdmin.from('payment_history').insert({
    user_id: userId,
    provider: 'razorpay',
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

  const signature = event.headers['x-razorpay-signature']
  if (!signature || !verifySignature(event.body, signature, process.env.RAZORPAY_WEBHOOK_SECRET)) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid signature' }) }
  }

  const payload = JSON.parse(event.body)
  const eventType = payload.event
  const entity = payload.payload?.subscription?.entity || payload.payload?.payment?.entity

  if (!entity) {
    return { statusCode: 200, body: JSON.stringify({ received: true }) }
  }

  const userId = entity.notes?.user_id
  const tier = entity.notes?.tier

  if (!userId || !tier) {
    return { statusCode: 200, body: JSON.stringify({ received: true, note: 'No user mapping' }) }
  }

  try {
    switch (eventType) {
      case 'subscription.activated':
      case 'subscription.charged': {
        await activateSubscription(
          userId,
          tier,
          entity.id,
          entity.current_end
        )
        await logPayment(userId, 0, 'INR', 'paid', entity.id, entity.id)
        break
      }
      case 'subscription.cancelled': {
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
          console.error('[razorpay-webhook] app sync cancel error:', syncErr)
        }
        break
      }
      default:
        break
    }

    return { statusCode: 200, body: JSON.stringify({ received: true }) }
  } catch (err) {
    console.error('[razorpay-webhook]', err)
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) }
  }
}
