import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { X, Mail, Lock, User, Loader2, AlertCircle } from 'lucide-react'

export default function AuthModal({ onClose }) {
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { signIn, signUp, signInWithOAuth } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    if (mode === 'signin') {
      const { error } = await signIn(email, password)
      if (error) setError(error.message)
      else onClose()
    } else {
      const { error } = await signUp(email, password)
      if (error) setError(error.message)
      else {
        setError(null)
        setMode('signin')
        setError('Account created! Please sign in.')
      }
    }
    setLoading(false)
  }

  const handleGoogle = async () => {
    setLoading(true)
    setError(null)
    const { error } = await signInWithOAuth('google')
    if (error) {
      setError(error.message)
      setLoading(false)
    }
    // OAuth redirects, so we don't close the modal here
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="relative w-full max-w-sm rounded-2xl border border-white/[0.06] bg-bg-dark p-6 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-secondary hover:text-text-primary transition-colors"
        >
          <X size={20} />
        </button>

        <h2 className="font-display text-xl font-bold text-text-primary text-center">
          {mode === 'signin' ? 'Welcome back' : 'Create account'}
        </h2>
        <p className="mt-1 text-sm text-text-secondary text-center">
          {mode === 'signin' ? 'Sign in to manage your credits' : 'Get 50 free credits to start'}
        </p>

        {/* Google */}
        <button
          onClick={handleGoogle}
          disabled={loading}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-text-primary transition-all hover:bg-white/10"
        >
          <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24">
            <path fill="#EA4335" d="M12 5.04c1.67 0 3.17.58 4.35 1.71l3.24-3.24C17.48 1.17 14.9 0 12 0 7.39 0 3.38 2.6 1.48 6.38l3.75 2.91C6.38 6.22 8.95 5.04 12 5.04z"/>
            <path fill="#4285F4" d="M23.5 12.23c0-.83-.07-1.63-.2-2.4H12v4.54h6.45c-.28 1.48-1.1 2.73-2.34 3.57l3.78 2.93c2.2-2.03 3.61-5.02 3.61-8.64z"/>
            <path fill="#FBBC05" d="M5.23 9.29l-3.75-2.91C-.7 8.5 0 11.2 0 12c0 .81.07 1.6.2 2.37l3.76-2.91c-.1-.47-.16-.97-.16-1.47 0-.5.06-1 .16-1.47l-.53.67z"/>
            <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.78-2.93c-1.01.67-2.31 1.07-4.17 1.07-3.05 0-5.62-1.18-7.23-3.02l-3.76 2.91C3.38 21.4 7.39 24 12 24z"/>
          </svg>
          Continue with Google
        </button>

        <div className="mt-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-white/[0.06]" />
          <span className="text-xs text-text-secondary">or</span>
          <div className="h-px flex-1 bg-white/[0.06]" />
        </div>

        {/* Email form */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <div className="relative">
            <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] py-2.5 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-secondary focus:border-primary/40 focus:outline-none"
            />
          </div>
          <div className="relative">
            <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] py-2.5 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-secondary focus:border-primary/40 focus:outline-none"
            />
          </div>

          {error && (
            <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
              error.includes('created') || error.includes('Please sign in')
                ? 'bg-success/10 text-success'
                : 'bg-error/10 text-error'
            }`}>
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                {mode === 'signin' ? 'Signing in...' : 'Creating account...'}
              </>
            ) : (
              <>
                <User size={16} />
                {mode === 'signin' ? 'Sign In' : 'Sign Up'}
              </>
            )}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-text-secondary">
          {mode === 'signin' ? (
            <>
              No account?{' '}
              <button onClick={() => { setMode('signup'); setError(null) }} className="text-primary hover:underline">
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button onClick={() => { setMode('signin'); setError(null) }} className="text-primary hover:underline">
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
