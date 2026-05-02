import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function useAuth() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }

    const getSession = async () => {
      const { data } = await supabase.auth.getSession()
      setUser(data.session?.user || null)
      setLoading(false)
    }

    getSession()

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null)
    })

    return () => {
      listener.subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email, password) => {
    if (!supabase) return { data: null, error: new Error('Supabase not configured') }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    return { data, error }
  }

  const signUp = async (email, password) => {
    if (!supabase) return { data: null, error: new Error('Supabase not configured') }
    const { data, error } = await supabase.auth.signUp({ email, password })
    return { data, error }
  }

  const signInWithOAuth = async (provider) => {
    if (!supabase) return { data: null, error: new Error('Supabase not configured') }
    const { data, error } = await supabase.auth.signInWithOAuth({ provider })
    return { data, error }
  }

  const signOut = async () => {
    if (!supabase) return
    await supabase.auth.signOut()
  }

  return { user, loading, signIn, signUp, signInWithOAuth, signOut }
}
