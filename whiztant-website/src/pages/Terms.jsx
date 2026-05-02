import { motion } from 'framer-motion'
import { FileText, Scale, Ban, CreditCard, Gavel } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'
import Particles from '../components/Particles'

export default function Terms() {
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
            Terms of Service
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
              <FileText size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Acceptance of Terms</h2>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  By downloading, installing, or using Wiztant, you agree to these Terms of Service. If you do not agree, do not use the software. These terms constitute a legally binding agreement between you and Wiztant Technologies.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Scale size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">License</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>Wiztant grants you a limited, non-exclusive, non-transferable license to use the software subject to these terms:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>You may use Wiztant on devices you own or control.</li>
                    <li>You may not reverse engineer, decompile, or disassemble the software.</li>
                    <li>You may not rent, lease, lend, sell, redistribute, or sublicense Wiztant.</li>
                    <li>You may not use Wiztant for any illegal or unauthorized purpose.</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <CreditCard size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Subscriptions & Payments</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>Pro and Power tiers are billed on a recurring basis. By subscribing, you authorize us to charge your payment method.</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Subscriptions automatically renew unless cancelled at least 24 hours before the renewal date.</li>
                    <li>You may cancel anytime from your account dashboard.</li>
                    <li>No refunds for partial months. Free trials convert to paid subscriptions unless cancelled.</li>
                    <li>We reserve the right to change pricing with 30 days notice.</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Ban size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Prohibited Uses</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>You agree not to use Wiztant to:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Violate any applicable laws or regulations</li>
                    <li>Infringe intellectual property rights</li>
                    <li>Distribute malware or engage in unauthorized access to systems</li>
                    <li>Automate actions that violate third-party terms of service</li>
                    <li>Harvest data from others without consent</li>
                    <li>Interfere with the operation of Wiztant or its servers</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Gavel size={22} className="text-primary shrink-0 mt-1" />
              <div>
                <h2 className="font-display text-xl font-bold text-text-primary">Disclaimer & Limitation of Liability</h2>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary space-y-2">
                  <p>Wiztant is provided "as is" without warranties of any kind. We do not guarantee that the software will be error-free or uninterrupted.</p>
                  <p>Agent automation involves controlling your mouse and keyboard. You are solely responsible for reviewing and approving Agent actions. We are not liable for any unintended consequences of Agent execution.</p>
                  <p>To the maximum extent permitted by law, Wiztant Technologies shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of the software.</p>
                </div>
              </div>
            </div>

            <div>
              <h2 className="font-display text-xl font-bold text-text-primary">Changes to These Terms</h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                We may update these terms from time to time. We will notify you of significant changes via email or in-app notification. Continued use after changes constitutes acceptance.
              </p>
            </div>

            <div>
              <h2 className="font-display text-xl font-bold text-text-primary">Contact</h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Questions about these terms? Contact us at <a href="mailto:legal@wiztant.ai" className="text-primary hover:underline">legal@wiztant.ai</a>.
              </p>
            </div>
          </div>
        </AnimatedSection>
      </section>
    </div>
  )
}
