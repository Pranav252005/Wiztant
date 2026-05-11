import { useEffect, useState, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import { getTierCredits } from '../lib/credits'

export function useCredits(user) {
  const [credits, setCredits] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchCredits = useCallback(async () => {
    if (!supabase || !user) {
      setCredits(null)
      setLoading(false)
      return
    }
    setLoading(true)
    const { data, error } = await supabase
      .from('user_credits')
      .select('*')
      .eq('user_id', user.id)
      .single()

    if (error && error.code !== 'PGRST116') {
      console.error('[useCredits] fetch error:', error)
    }

    if (data) {
      setCredits(data)
    } else {
      // Initialize if missing
      const allocation = getTierCredits('free')
      const { data: inserted } = await supabase
        .from('user_credits')
        .insert({
          user_id: user.id,
          balance: allocation,
          tier: 'free',
          monthly_allocation: allocation,
        })
        .select()
        .single()
      if (inserted) setCredits(inserted)
    }
    setLoading(false)
  }, [user])

  const fetchTransactions = useCallback(async (limit = 20) => {
    if (!supabase || !user) return
    const { data } = await supabase
      .from('credit_transactions')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(limit)
    if (data) setTransactions(data)
  }, [user])

  const fetchPayments = useCallback(async (limit = 20) => {
    if (!supabase || !user) return
    const { data } = await supabase
      .from('payment_history')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(limit)
    if (data) setPayments(data)
  }, [user])

  const upgradeTier = useCallback(async (tier) => {
    if (!supabase || !user) return { error: new Error('Not authenticated') }
    const allocation = getTierCredits(tier)
    const { data, error } = await supabase
      .from('user_credits')
      .upsert({
        user_id: user.id,
        tier,
        balance: allocation,
        monthly_allocation: allocation,
        reset_at: new Date().toISOString(),
      })
      .select()
      .single()
    if (!error) setCredits(data)
    return { data, error }
  }, [user])

  useEffect(() => {
    fetchCredits()
  }, [fetchCredits])

  const usagePercent = credits
    ? Math.min(100, Math.round(((credits.monthly_allocation - credits.balance) / credits.monthly_allocation) * 100))
    : 0

  return {
    credits,
    transactions,
    loading,
    usagePercent,
    refresh: fetchCredits,
    refreshTransactions: fetchTransactions,
    refreshPayments: fetchPayments,
    upgradeTier,
    payments,
  }
}
