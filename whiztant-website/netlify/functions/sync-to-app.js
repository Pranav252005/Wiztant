import { createClient } from '@supabase/supabase-js'

const supabaseApp = createClient(
  process.env.APP_SUPABASE_URL,
  process.env.APP_SUPABASE_SERVICE_ROLE_KEY
)

export const handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) }
  }

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

  const { user_id, balance, tier, reset_at } = body
  if (!user_id || balance === undefined || !tier) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing fields' }) }
  }

  try {
    await supabaseApp
      .from('credits')
      .upsert({
        user_id,
        balance,
        tier,
        reset_at: reset_at || new Date().toISOString(),
      })

    return { statusCode: 200, body: JSON.stringify({ synced: true }) }
  } catch (err) {
    console.error('[sync-to-app]', err)
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) }
  }
}
