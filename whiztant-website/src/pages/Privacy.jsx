import { motion } from 'framer-motion'
import { Shield, Lock, Eye, Server, Trash2, Mail } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

export default function Privacy() {
  return (
    <div>
      <section className="relative flex min-h-[40vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">Legal</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-5xl">
            Privacy Policy
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            Last updated: May 1, 2026
          </p>
        </motion.div>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-20">
        <AnimatedSection>
          <div className="prose-dark space-y-8">
            <div className="flex items-start gap-4">
              <Shield size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Our Commitment</h2>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  Wiztant is built on the principle that your data belongs to you. We minimize data collection, process sensitive information locally whenever possible, and never sell your data to third parties. This policy explains what we collect, how we use it, and your rights.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Eye size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">What We Collect</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p><strong className="text-text-primary">Account Information:</strong> When you create an account, we store your email address and authentication credentials. Passwords are hashed and never stored in plain text.</p>
                  <p><strong className="text-text-primary">Usage Analytics:</strong> We collect anonymous usage statistics such as feature activation counts, error logs, and performance metrics. This data cannot be used to identify you.</p>
                  <p><strong className="text-text-primary">Billing Information:</strong> For paid subscribers, payment details are handled by our payment processor (Stripe). We do not store credit card numbers on our servers.</p>
                  <p><strong className="text-text-primary">Voice Data:</strong> Dictation audio is processed either locally (if offline mode is enabled) or sent to our secure STT provider. Audio is not retained after transcription unless you explicitly enable voice history.</p>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Lock size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">How We Protect Your Data</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>All data transmission between Wiztant and our servers uses TLS 1.3 encryption. API keys are stored in your operating system's native keychain (Windows Credential Manager or Linux keyring) rather than in plain text files.</p>
                  <p>Agent screenshots are processed entirely in-memory and are never written to disk unless you explicitly enable debug logging. We have no ability to view your screen.</p>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Server size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Third-Party Services</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>We use the following third-party services to operate Wiztant:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li><strong className="text-text-primary">Supabase</strong> — Authentication and database hosting</li>
                    <li><strong className="text-text-primary">Stripe</strong> — Payment processing</li>
                    <li><strong className="text-text-primary">OpenAI / Anthropic</strong> — LLM inference for RePrompt, Agent, and TaskStack</li>
                  </ul>
                  <p>Each of these providers maintains their own privacy policies and security certifications.</p>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Trash2 size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Your Rights</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>You have the right to:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Access all data we hold about you</li>
                    <li>Request correction of inaccurate data</li>
                    <li>Request deletion of your account and associated data</li>
                    <li>Export your data in a portable format</li>
                    <li>Opt out of analytics collection in Settings → Privacy</li>
                  </ul>
                  <p>Account deletion requests are processed within 30 days. Some data may be retained longer if required by law.</p>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Mail size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Contact Us</h2>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  If you have questions about this privacy policy or want to exercise your data rights, email us at <a href="mailto:privacy@wiztant.ai" className="text-primary hover:underline">privacy@wiztant.ai</a>.
                </p>
              </div>
            </div>
          </div>
        </AnimatedSection>
      </section>
    </div>
  )
}
