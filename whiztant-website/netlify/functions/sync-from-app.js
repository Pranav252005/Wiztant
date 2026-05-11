import { createClient } from '@supabase/supabase-js'

const supabaseWebsite = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

export const handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) }
  }

  // Verify shared secret
  const authHeader = event.headers['x-sync-secret']
  if (authHeader !== process.env.SYNC_SECRET) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Unauthorized' }) }
  }

  let body
  try {
    body = JSON.parse(event.body)
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid JSON' }) }
  }

  const { user_id, balance, tier, transactions = [] } = body
  if (!user_id || balance === undefined || !tier) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing fields' }) }
  }

  try {
    // Upsert user credits on the website DB
    const allocation = tier === 'free' ? 50 : tier === 'pro' ? 1000 : tier === 'power' ? 5000 : 50
    await supabaseWebsite
      .from('user_credits')
      .upsert({
        user_id,
        balance,
        tier,
        monthly_allocation: allocation,
        updated_at: new Date().toISOString(),
      })

    // Insert transactions if provided
    if (transactions.length > 0) {
      const txs = transactions.map(tx => ({
        user_id,
        feature: tx.feature,
        model: tx.model || null,
        amount: tx.amount,
        balance_after: tx.balance_after,
        created_at: tx.created_at || new Date().toISOString(),
      }))
      await supabaseWebsite.from('credit_transactions').insert(txs)
    }

    return { statusCode: 200, body: JSON.stringify({ synced: true }) }
  } catch (err) {
    console.error('[sync-from-app]', err)
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) }
  }
}
