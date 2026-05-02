import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, LogOut, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

export default function DownloadPage() {
  const { user, loading, signIn, signUp, signInWithOAuth, signOut } = useAuth()
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [downloaded, setDownloaded] = useState(false)

  const handleAuth = async (e) => {
    e.preventDefault()
    setError('')
    const { error: err } = mode === 'signin'
      ? await signIn(email, password)
      : await signUp(email, password)
    if (err) setError(err.message)
  }

  const handleOAuth = async (provider) => {
    setError('')
    const { error: err } = await signInWithOAuth(provider)
    if (err) setError(err.message)
  }

  const triggerDownload = () => {
    setDownloaded(true)
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div>
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <AnimatedSection className="relative z-10 max-w-xl">
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-5xl">
            Download Wiztant
          </h1>
          <p className="mx-auto mt-4 max-w-md text-text-secondary">
            {user
              ? 'Welcome back. Grab the latest build below.'
              : 'Sign up or log in to download the portable app.'}
          </p>
        </AnimatedSection>
      </section>

      <section className="mx-auto max-w-xl px-6 py-8">
        <AnimatePresence mode="wait">
          {!user ? (
            <motion.div
              key="auth"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8"
            >
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleOAuth('google')}
                  className="flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-white/10"
                >
                  Google
                </button>
                <button
                  onClick={() => handleOAuth('github')}
                  className="flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-white/10"
                >
                  GitHub
                </button>
              </div>

              <div className="my-6 flex items-center gap-4">
                <div className="h-px flex-1 bg-white/[0.06]" />
                <span className="text-xs text-text-secondary">or with email</span>
                <div className="h-px flex-1 bg-white/[0.06]" />
              </div>

              <form onSubmit={handleAuth} className="space-y-4">
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-secondary">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary focus:shadow-[0_0_12px_rgba(232,93,74,0.15)]"
                    placeholder="you@example.com"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-secondary">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary focus:shadow-[0_0_12px_rgba(232,93,74,0.15)]"
                    placeholder="••••••••"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-error/10 px-4 py-3 text-sm text-error">
                    <AlertCircle size={16} />
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-bg-dark transition-transform hover:scale-[1.02]"
                >
                  {mode === 'signin' ? 'Sign In' : 'Create Account'}
                </button>
              </form>

              <p className="mt-4 text-center text-sm text-text-secondary">
                {mode === 'signin' ? (
                  <>
                    No account?{' '}
                    <button onClick={() => { setMode('signup'); setError('') }} className="font-medium text-primary hover:underline">
                      Sign up
                    </button>
                  </>
                ) : (
                  <>
                    Already have an account?{' '}
                    <button onClick={() => { setMode('signin'); setError('') }} className="font-medium text-primary hover:underline">
                      Sign in
                    </button>
                  </>
                )}
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="download"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <CheckCircle2 size={24} className="text-primary" />
                </div>
                <p className="font-display text-lg font-semibold text-text-primary">
                  Welcome, {user.email?.split('@')[0] || 'User'}
                </p>
                <p className="mt-1 text-sm text-text-secondary">Tier: Free</p>

                <button
                  onClick={triggerDownload}
                  className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-8 py-4 text-base font-semibold text-bg-dark transition-transform hover:scale-105"
                >
                  <Download size={18} />
                  Download Wiztant v1.0.0
                </button>
                <p className="mt-3 text-xs text-text-secondary">~50 MB, Windows & Linux</p>

                <div className="mt-6 space-y-2 text-sm text-text-secondary">
                  <p>Included: Dictation, RePrompt</p>
                  <p>Trial: 3 days, 30 messages, 3 agent tasks</p>
                </div>

                <div className="mt-6 flex items-center justify-center gap-4">
                  <Link
                    to="/pricing"
                    className="text-sm font-medium text-primary transition-colors hover:underline"
                  >
                    Upgrade to Pro
                  </Link>
                  <button
                    onClick={signOut}
                    className="inline-flex items-center gap-1 text-sm text-text-secondary transition-colors hover:text-error"
                  >
                    <LogOut size={14} />
                    Log Out
                  </button>
                </div>
              </div>

              {downloaded && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6"
                >
                  <p className="font-display text-sm font-semibold text-text-primary">What is next?</p>
                  <ol className="mt-3 space-y-2 text-sm text-text-secondary">
                    <li className="flex gap-2"><span className="text-primary">1.</span> Run Wiztant-Portable.exe</li>
                    <li className="flex gap-2"><span className="text-primary">2.</span> Set your hotkeys (F9, Ctrl+Space, F10)</li>
                    <li className="flex gap-2"><span className="text-primary">3.</span> Start a dictation task</li>
                    <li className="flex gap-2"><span className="text-primary">4.</span> (Pro users) Try an agent task</li>
                  </ol>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </div>
  )
}
