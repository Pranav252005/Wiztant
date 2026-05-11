import { useState, useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X, Download, ChevronDown, Zap, Mic, Bot, ListTodo, Sparkles, Wallet, Settings, LogOut, User } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useCredits } from '../hooks/useCredits'
import AuthModal from './AuthModal'

const featureLinks = [
  { to: '/features/reprompt', label: 'RePrompt', icon: Zap, desc: 'AI-powered prompt rewriting' },
  { to: '/features/dictation', label: 'Dictation', icon: Mic, desc: 'Voice-to-text everywhere' },
  { to: '/features/agent', label: 'Agent', icon: Bot, desc: 'Autonomous screen control' },
  { to: '/features/taskstack', label: 'TaskStack', icon: ListTodo, desc: 'Smart task management' },
]

const navLinks = [
  { to: '/how-it-works', label: 'How It Works' },
  { to: '/pricing', label: 'Pricing' },
  { to: '/docs', label: 'Docs' },
  { to: '/about', label: 'About' },
]

function getAvatarUrl(user) {
  if (!user) return null
  return user.user_metadata?.avatar_url || user.user_metadata?.picture || null
}

function getInitials(email) {
  if (!email) return '?'
  return email.charAt(0).toUpperCase()
}

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const [featuresOpen, setFeaturesOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const { user, signOut } = useAuth()
  const { credits } = useCredits(user)
  const location = useLocation()
  const userMenuRef = useRef(null)

  useEffect(() => {
    setOpen(false)
    setFeaturesOpen(false)
    setUserMenuOpen(false)
  }, [location.pathname])

  // Close user menu on outside click
  useEffect(() => {
    function handleClick(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const avatarUrl = getAvatarUrl(user)

  return (
    <header className="fixed top-0 left-0 right-0 z-50 px-4 pt-3">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 rounded-2xl border border-white/[0.08] bg-bg-dark/80 backdrop-blur-xl shadow-lg shadow-black/20">
        <Link to="/" className="flex items-center transition-opacity hover:opacity-80">
          <img src="/wiztantW.png" alt="Wiztant" className="h-14 w-auto" />
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <div
            className="relative"
            onMouseEnter={() => setFeaturesOpen(true)}
            onMouseLeave={() => setFeaturesOpen(false)}
          >
            <button className="flex items-center gap-1 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
              Features
              <ChevronDown size={14} className={`transition-transform duration-200 ${featuresOpen ? 'rotate-180' : ''}`} />
            </button>
            <AnimatePresence>
              {featuresOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.2 }}
                  className="absolute top-full left-0 mt-2 w-72 rounded-xl border border-white/[0.08] bg-bg-dark/95 backdrop-blur-xl p-3 shadow-2xl"
                >
                  {featureLinks.map((link) => (
                    <Link
                      key={link.to}
                      to={link.to}
                      className="flex items-start gap-3 rounded-lg px-3 py-3 transition-colors hover:bg-white/[0.05]"
                    >
                      <link.icon size={18} className="mt-0.5 shrink-0 text-primary" />
                      <div>
                        <div className="text-sm font-medium text-text-primary">{link.label}</div>
                        <div className="text-xs text-text-secondary">{link.desc}</div>
                      </div>
                    </Link>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`text-sm font-medium transition-colors ${
                location.pathname === link.to
                  ? 'text-primary'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {link.label}
            </Link>
          ))}

          {user ? (
            <>
              <Link
                to="/settings"
                className={`text-sm font-medium transition-colors ${
                  location.pathname === '/settings' ? 'text-primary' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                Settings
              </Link>

              {/* Credit badge */}
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-text-primary hover:bg-white/10 transition-colors"
                >
                  <Wallet size={14} className="text-primary" />
                  {credits ? credits.balance : '—'}
                </button>
              </div>

              {/* Avatar dropdown */}
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 overflow-hidden transition-all hover:border-primary/40 hover:ring-2 hover:ring-primary/20"
                >
                  {avatarUrl ? (
                    <img src={avatarUrl} alt="Profile" className="h-full w-full object-cover" />
                  ) : (
                    <span className="text-sm font-bold text-text-primary">{getInitials(user?.email)}</span>
                  )}
                </button>

                <AnimatePresence>
                  {userMenuOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                      className="absolute top-full right-0 mt-2 w-56 rounded-xl border border-white/[0.08] bg-bg-dark/95 backdrop-blur-xl p-2 shadow-2xl"
                    >
                      <div className="px-3 py-2 border-b border-white/[0.06] mb-1">
                        <p className="text-sm font-medium text-text-primary truncate">{user.email}</p>
                        <p className="text-xs text-text-secondary capitalize">{credits?.tier || 'free'} Plan</p>
                      </div>
                      <Link
                        to="/settings"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-white/[0.05] hover:text-text-primary transition-colors"
                      >
                        <Settings size={16} /> Settings
                      </Link>
                      <button
                        onClick={() => { signOut(); setUserMenuOpen(false) }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-white/[0.05] hover:text-error transition-colors text-left"
                      >
                        <LogOut size={16} /> Sign Out
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </>
          ) : (
            <button
              onClick={() => setAuthOpen(true)}
              className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-text-primary hover:bg-white/10 transition-colors"
            >
              <User size={15} /> Sign In
            </button>
          )}

          <Link to="/download" className="btn-primary">
            <Download size={15} />
            Download
          </Link>
        </div>

        <button
          className="md:hidden text-text-primary"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="border-t border-white/[0.06] bg-bg-dark/95 backdrop-blur-xl md:hidden overflow-hidden"
          >
            <div className="flex flex-col gap-1 px-6 py-6">
              <div className="mb-2">
                <p className="text-xs font-medium uppercase tracking-wider text-text-secondary mb-2">Features</p>
                {featureLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-2 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
                  >
                    <link.icon size={14} className="text-primary" />
                    {link.label}
                  </Link>
                ))}
              </div>
              <div className="h-px bg-white/[0.06] my-2" />
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setOpen(false)}
                  className="text-base font-medium py-3 transition-colors text-text-secondary hover:text-text-primary"
                >
                  {link.label}
                </Link>
              ))}

              {user ? (
                <>
                  <div className="flex items-center gap-3 py-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 overflow-hidden">
                      {avatarUrl ? (
                        <img src={avatarUrl} alt="Profile" className="h-full w-full object-cover" />
                      ) : (
                        <span className="text-sm font-bold text-text-primary">{getInitials(user?.email)}</span>
                      )}
                    </div>
                    <div>
                      <p className="text-sm text-text-primary">{user.email}</p>
                      <p className="text-xs text-text-secondary capitalize">{credits?.tier || 'free'} Plan</p>
                    </div>
                  </div>
                  <Link
                    to="/settings"
                    onClick={() => setOpen(false)}
                    className="text-base font-medium py-3 text-text-secondary hover:text-text-primary flex items-center gap-2"
                  >
                    <Settings size={16} /> Settings
                  </Link>
                  <button
                    onClick={() => { signOut(); setOpen(false) }}
                    className="text-base font-medium py-3 text-text-secondary hover:text-error flex items-center gap-2 text-left"
                  >
                    <LogOut size={16} /> Sign Out
                  </button>
                </>
              ) : (
                <button
                  onClick={() => { setAuthOpen(true); setOpen(false) }}
                  className="mt-2 flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-text-primary hover:bg-white/10 transition-colors w-fit"
                >
                  <User size={16} /> Sign In / Sign Up
                </button>
              )}

              <Link
                to="/download"
                onClick={() => setOpen(false)}
                className="mt-4 flex items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-bg-dark"
              >
                <Download size={15} />
                Download
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} />}
    </header>
  )
}
