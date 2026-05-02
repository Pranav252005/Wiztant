import { useState } from 'react'
import { motion } from 'framer-motion'
import { Mail, MessageSquare, Send, CheckCircle2, AlertCircle, MapPin, Clock } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' })
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    if (!form.name || !form.email || !form.message) {
      setError('Please fill in all required fields.')
      return
    }
    // Simulate submission
    setSubmitted(true)
  }

  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-[50vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">Get in Touch</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-6xl">
            We are here to <span className="text-gradient-primary">help</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            Questions, feedback, or just want to say hi? Reach out. We read every message.
          </p>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-3">
          {/* Contact Info */}
          <AnimatedSection direction="left" className="space-y-8">
            <div>
              <h3 className="font-display text-xl font-bold text-text-primary">Contact Information</h3>
              <p className="mt-2 text-sm text-text-secondary">
                Our team typically responds within 24 hours on weekdays.
              </p>
            </div>

            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5">
                  <Mail size={18} className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">Email</p>
                  <a href="mailto:hello@wiztant.ai" className="text-sm text-text-secondary hover:text-primary transition-colors">
                    hello@wiztant.ai
                  </a>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5">
                  <MessageSquare size={18} className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">Discord Community</p>
                  <a href="#" className="text-sm text-text-secondary hover:text-primary transition-colors">
                    discord.gg/wiztant
                  </a>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5">
                  <Clock size={18} className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">Response Time</p>
                  <p className="text-sm text-text-secondary">Usually under 24 hours</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5">
                  <MapPin size={18} className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">Based in</p>
                  <p className="text-sm text-text-secondary">Remote-first, worldwide</p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
              <p className="text-sm font-medium text-text-primary mb-4">Follow us</p>
              <div className="flex gap-3">
                <a href="#" className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                </a>
                <a href="#" className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 2.22 1.15.645-.18 1.335-.27 2.025-.27.69 0 1.38.09 2.025.27 1.215-1.472 2.22-1.15 2.22-1.15.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                </a>
              </div>
            </div>
          </AnimatedSection>

          {/* Form */}
          <AnimatedSection direction="right" className="lg:col-span-2">
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
              {!submitted ? (
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid gap-6 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-text-primary">Name *</label>
                      <input
                        type="text"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary"
                        placeholder="Your name"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-text-primary">Email *</label>
                      <input
                        type="email"
                        value={form.email}
                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                        className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary"
                        placeholder="you@example.com"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-text-primary">Subject</label>
                    <select
                      value={form.subject}
                      onChange={(e) => setForm({ ...form, subject: e.target.value })}
                      className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary"
                    >
                      <option value="">Select a topic</option>
                      <option value="general">General Inquiry</option>
                      <option value="support">Technical Support</option>
                      <option value="billing">Billing & Pricing</option>
                      <option value="feature">Feature Request</option>
                      <option value="bug">Bug Report</option>
                      <option value="partnership">Partnership</option>
                    </select>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-text-primary">Message *</label>
                    <textarea
                      value={form.message}
                      onChange={(e) => setForm({ ...form, message: e.target.value })}
                      rows={5}
                      className="w-full rounded-xl border border-white/10 bg-bg-dark px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-primary resize-none"
                      placeholder="Tell us what's on your mind..."
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
                    className="btn-primary w-full md:w-auto"
                  >
                    <Send size={16} />
                    Send Message
                  </button>
                </form>
              ) : (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col items-center justify-center py-12 text-center"
                >
                  <CheckCircle2 size={48} className="text-success mb-4" />
                  <h3 className="font-display text-xl font-bold text-text-primary">Message sent!</h3>
                  <p className="mt-2 text-text-secondary max-w-md">
                    Thanks for reaching out. We will get back to you as soon as possible.
                  </p>
                  <button
                    onClick={() => { setSubmitted(false); setForm({ name: '', email: '', subject: '', message: '' }) }}
                    className="btn-secondary mt-6"
                  >
                    Send another message
                  </button>
                </motion.div>
              )}
            </div>
          </AnimatedSection>
        </div>
      </section>
    </div>
  )
}
