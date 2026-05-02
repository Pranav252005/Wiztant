import { Link } from 'react-router-dom'
import { MessageCircle, Mail } from 'lucide-react'

const footerLinks = {
  product: [
    { label: 'RePrompt', to: '/features/reprompt' },
    { label: 'Dictation', to: '/features/dictation' },
    { label: 'Agent', to: '/features/agent' },
    { label: 'TaskStack', to: '/features/taskstack' },
    { label: 'How It Works', to: '/how-it-works' },
    { label: 'Pricing', to: '/pricing' },
  ],
  company: [
    { label: 'About', to: '/about' },
    { label: 'Contact', to: '/contact' },
    { label: 'Changelog', to: '/changelog' },
    { label: 'Docs', to: '/docs' },
  ],
  legal: [
    { label: 'Privacy Policy', to: '/privacy' },
    { label: 'Terms of Service', to: '/terms' },
  ],
}

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06]">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid gap-12 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Link to="/" className="inline-block transition-opacity hover:opacity-80">
              <img src="/wiztantW.png" alt="Wiztant" className="h-14 w-auto" />
            </Link>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary max-w-sm">
              The AI operating assistant for Windows and Linux. RePrompt, Dictation, Agent, and TaskStack — all in one portable app.
            </p>
            <div className="mt-6 flex gap-3">
              <a href="#" className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              </a>
              <a href="#" className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 2.22 1.15.645-.18 1.335-.27 2.025-.27.69 0 1.38.09 2.025.27 1.215-1.472 2.22-1.15 2.22-1.15.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
              </a>
              <a href="#" className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                <MessageCircle size={16} />
              </a>
              <a href="mailto:hello@wiztant.ai" className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:text-primary hover:border-primary/30 transition-all">
                <Mail size={16} />
              </a>
            </div>
          </div>

          <div>
            <h4 className="font-display text-sm font-semibold uppercase tracking-wider text-text-primary">
              Product
            </h4>
            <ul className="mt-4 space-y-3 text-sm">
              {footerLinks.product.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="text-text-secondary transition-colors hover:text-primary">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-display text-sm font-semibold uppercase tracking-wider text-text-primary">
              Company
            </h4>
            <ul className="mt-4 space-y-3 text-sm">
              {footerLinks.company.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="text-text-secondary transition-colors hover:text-primary">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-display text-sm font-semibold uppercase tracking-wider text-text-primary">
              Legal
            </h4>
            <ul className="mt-4 space-y-3 text-sm">
              {footerLinks.legal.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="text-text-secondary transition-colors hover:text-primary">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/[0.06] pt-8 sm:flex-row">
          <p className="text-xs text-text-secondary">
            &copy; 2026 Wiztant. All rights reserved.
          </p>
          <p className="text-xs text-text-secondary">
            Made with care for humans who type too much.
          </p>
        </div>
      </div>
    </footer>
  )
}
