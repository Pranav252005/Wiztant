# Wiztant Website — Feature Specification

## Purpose
The Wiztant marketing website is the primary conversion funnel for the Windows AI operating assistant. It must communicate value in under 5 seconds, establish trust, and drive downloads or sign-ups. The site currently operates as a single landing page but is architected to expand into a full multi-page experience.

---

## Global Requirements

### Performance
- First Contentful Paint < 1.5s
- Time to Interactive < 3s
- Bundle size < 600KB (currently ~553KB)

### Accessibility
- WCAG 2.1 AA compliant
- Keyboard-navigable
- Screen reader friendly
- `prefers-reduced-motion` respected

### SEO
- Meta tags per page (title, description, OG tags)
- Semantic HTML structure
- Sitemap generation
- Structured data for SoftwareApplication

### Analytics
- Page view tracking
- Download button click tracking
- CTA conversion funnel
- Scroll depth for long pages

---

## Current State

A single landing page with:
- **Notification bar** — dismissible, dark (#190019), "How wisdom might help you."
- **Glass navbar** — `wiztant.svg` logo, links: Wiztant / Wizprompt / Wizagent, Download CTA
- **Empty hero** — reserved for future content
- **Porcelain color scheme** (#FBE4D8)

---

## Page-by-Page Feature Map

### 1. Home (`/`)
**Goal**: Explain what Wiztant is and why you need it in 5 seconds.

| Section | Features | Priority |
|---|---|---|
| **Hero** | Large headline + subheadline + primary CTA (Download) + product screenshot or demo video | Critical |
| **Social Proof** | Logos of publications/mentions (TechCrunch, Product Hunt, etc.) | High |
| **Feature Grid** | 3 cards: Dictation, Conversation, Agent — with icons + 1-line descriptions | Critical |
| **Demo Section** | Embedded GIF / video showing F9 press → action → result | High |
| **Testimonials** | 3 rotating quotes from users with avatars and roles | Medium |
| **Pricing Teaser** | Mini pricing table linking to full /pricing page | High |
| **FAQ Accordion** | 5-7 common questions with expand/collapse | Medium |
| **Final CTA** | "Ready to try Wiztant?" + download button + trust badge (no credit card) | Critical |

**Content Needed**:
- Headline: "One key. Total control." or variant
- Subheadline: "The AI operating assistant that lives in your system tray."
- Feature descriptions (1 sentence each)
- 3+ user testimonials with photos
- FAQ copy (billing, privacy, system requirements, uninstall)

---

### 2. Features (`/features`)
**Goal**: Deep dive into each capability.

| Section | Features | Priority |
|---|---|---|
| **Page Header** | "Everything Wiztant can do" + subhead | High |
| **Dictation Feature** | Screenshot + how it works + supported apps | Critical |
| **Conversation Feature** | Screenshot + voice loop explanation + voice samples | Critical |
| **Agent Feature** | Screen recording of agent navigating + safety explanation | Critical |
| **Overlay Feature** | Show Ctrl+Space overlay + explain use cases | High |
| **Voice Selector** | Interactive: play 6 Kokoro voice samples | Medium |
| **Supported Apps** | Grid of app icons where Wiztant works (Word, Chrome, VS Code, etc.) | Medium |
| **Comparison Table** | Wiztant vs Dragon vs Windows Voice Access vs Copilot | Low |

**Content Needed**:
- Feature screenshots (3 modes)
- App compatibility list
- Voice sample audio files
- Competitor comparison research

---

### 3. How It Works (`/how-it-works`)
**Goal**: Remove fear of the unknown. Show the exact user journey.

| Section | Features | Priority |
|---|---|---|
| **Step 1: Install** | "Download the .exe. No install required." + screenshot | High |
| **Step 2: Press F9** | Animated key press (1× / 2× / 3×) with labels | Critical |
| **Step 3: Speak** | Waveform animation + transcribed text appearing | High |
| **Step 4: Watch** | Agent taking action on screen (GIF/MP4) | High |
| **System Tray** | Explain how Wiztant lives in the tray, always ready | Medium |
| **Settings** | Screenshot of settings modal with key options | Low |

**Content Needed**:
- Screen recordings of each step
- Animated F9 key graphic
- System tray icon screenshot

---

### 4. Pricing (`/pricing`)
**Goal**: Clear, honest pricing that converts.

| Section | Features | Priority |
|---|---|---|
| **Toggle** | Monthly / Annual switch with savings highlighted | Critical |
| **Plan Cards** | Free / Pro / Power — 3 cards side by side | Critical |
| **Plan Details** | Each card: price, feature list, usage limits, CTA button | Critical |
| **Usage Limits** | Visual bar or number showing chats, agent tasks, UI-TARS calls | High |
| **Trial Banner** | "3-day free trial — no credit card required" | High |
| **FAQ** | Billing questions (upgrade, downgrade, cancel, refund) | Medium |
| **Enterprise CTA** | "Need more? Contact us" link to /support | Low |

**Content Needed**:
- Finalized pricing (currently: Free $0, Pro $15/mo, Power $25/mo)
- Feature lists per tier
- Trial terms copy

---

### 5. Download (`/download`)
**Goal**: Friction-free download with platform clarity.

| Section | Features | Priority |
|---|---|---|
| **Hero** | "Download Wiztant for Windows" + big download button | Critical |
| **System Requirements** | Windows 10/11, RAM, disk space | High |
| **Version Info** | Latest version number + release date + changelog link | Medium |
| **SHA256 Hash** | Security verification for the .exe | Low |
| **Alternative** | "Not on Windows? Join the waitlist" email capture | Medium |
| **Post-Download** | "What's next?" steps (run, sign in, press F9) | High |

**Content Needed**:
- System requirements (min Windows version, RAM, .NET?)
- Version number auto-population
- Changelog page or section
- Waitlist email backend (Supabase table)

---

### 6. Login (`/login`)
**Goal**: Fast, secure authentication.

| Section | Features | Priority |
|---|---|---|
| **Email/Password** | Standard form with validation | Critical |
| **Google OAuth** | One-click Google sign-in | Critical |
| **Forgot Password** | Email reset flow | High |
| **Sign Up** | Toggle between login and register | Critical |
| **Post-Login Redirect** | Return to original page or /download | High |
| **Error States** | Clear error messages (invalid creds, unverified email) | High |

**Content Needed**:
- Supabase auth policies (already configured)
- Error message copy
- Terms agreement checkbox on sign-up

---

### 7. Support (`/support`)
**Goal**: Self-service help + direct contact.

| Section | Features | Priority |
|---|---|---|
| **Search** | Searchable help center | High |
| **Quick Links** | Top 5 articles (getting started, troubleshooting, billing) | High |
| **Contact Form** | Name, email, category, message → Supabase or email | Medium |
| **Discord / Community** | Link to community server | Medium |
| **Status Page** | Link to system status / uptime | Low |
| **Response Time** | "We typically respond within 24 hours" | Low |

**Content Needed**:
- 10-15 help articles
- Contact form backend (Supabase function or email service)
- Discord invite link

---

### 8. Docs (`/docs`)
**Goal**: Comprehensive user documentation.

| Section | Features | Priority |
|---|---|---|
| **Sidebar Navigation** | 7 sections, collapsible | High |
| **Search** | Full-text search across docs | Medium |
| **Getting Started** | Installation, first use, key bindings | Critical |
| **Dictation Guide** | How to dictate, supported commands, troubleshooting | High |
| **Conversation Guide** | Voice loop, changing voices, interrupting | High |
| **Agent Guide** | What the agent can do, safety, limitations | High |
| **Settings Reference** | Every setting explained | Medium |
| **Shortcuts** | All keyboard shortcuts table | Medium |
| **Troubleshooting** | Common issues and fixes | High |
| **Changelog** | Version history with dates | Medium |

**Content Needed**:
- All documentation copy (currently 7 sections planned)
- Screenshots for each feature
- Troubleshooting matrix

---

### 9. Press (`/press`)
**Goal**: Media kit and brand assets for journalists.

| Section | Features | Priority |
|---|---|---|
| **Brand Kit** | Logo downloads (SVG, PNG, EPS) in light/dark variants | High |
| **Product Screenshots** | High-res screenshots of all 3 modes | High |
| **Founder Bio** | Pranav — photo, short bio, contact | Medium |
| **Fact Sheet** | One-page PDF with key stats | Medium |
| **Mentions** | Links to press coverage | Low |
| **Contact** | press@wiztant.com email | Low |

**Content Needed**:
- Logo pack (already have SVGs)
- Founder photo and bio
- Key stats (users, countries, commands processed)

---

### 10. Legal Pages
**Goal**: Compliance and trust.

| Page | Content | Priority |
|---|---|---|
| **Privacy Policy** (`/privacy-policy`) | Data collection, storage, retention, third parties | Critical |
| **Terms of Service** (`/terms-of-service`) | Usage rights, limitations, liability | Critical |
| **Cookie Policy** (`/cookie-policy`) | What cookies are used, how to manage | Medium |

**Content Needed**:
- Lawyer-reviewed privacy policy
- Terms of service copy
- Cookie consent banner (GDPR/CCPA)

---

## Shared Components (Reusable)

| Component | Used On | Status |
|---|---|---|
| **NotificationBar** | All pages | ✅ Built |
| **Navbar** | All pages | ✅ Built |
| **Footer** | All pages | ❌ Not built — needs links, social, copyright |
| **PageTransition** | All pages | ❌ Not built — Framer Motion fade |
| **ScrollReveal** | Home, Features, How It Works | ❌ Not built |
| **GradientOrb** | Home hero background | ❌ Not built |
| **TiltCard** | Pricing, Features | ❌ Not built |
| **SectionDivider** | Between sections | ❌ Not built |
| **StaggerContainer** | Feature grids, testimonials | ❌ Not built |

---

## Missing Assets Checklist

| Asset | Needed For | Status |
|---|---|---|
| Product screenshots (dictation) | Home, Features, How It Works | ❌ |
| Product screenshots (conversation) | Home, Features, How It Works | ❌ |
| Product screenshots (agent) | Home, Features, How It Works | ❌ |
| Screen recordings / GIFs | Home, How It Works | ❌ |
| Founder photo | Press | ❌ |
| Voice samples (6 Kokoro voices) | Features | ❌ |
| Testimonial photos + quotes | Home | ❌ |
| App compatibility icons | Features | ❌ |
| Social proof logos | Home | ❌ |
| Press coverage links | Press | ❌ |
| Fact sheet PDF | Press | ❌ |

---

## Analytics & Conversion Tracking

| Event | Trigger | Priority |
|---|---|---|
| `page_view` | Every route change | Critical |
| `download_click` | Download button click | Critical |
| `pricing_toggle` | Monthly/Annual switch | Medium |
| `plan_select` | Click any pricing CTA | Critical |
| `signup_start` | Open login modal/page | High |
| `signup_complete` | Successful auth | Critical |
| `trial_start` | Begin free trial | Critical |
| `video_play` | Click demo video | Medium |
| `faq_expand` | Open FAQ item | Low |
| `scroll_depth` | 25/50/75/100% | Medium |

---

## Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|---|---|---|
| Mobile | < 640px | Stack all, hamburger menu, single column |
| Tablet | 640-1024px | 2-column grids, simplified nav |
| Desktop | > 1024px | Full layout, hover effects, side-by-side |

---

## Technical TODOs

1. [ ] Build Footer component
2. [ ] Add page routing (React Router)
3. [ ] Create all page components (Home, Features, How It Works, etc.)
4. [ ] Add Framer Motion page transitions
5. [ ] Implement scroll reveal animations
6. [ ] Add analytics events
7. [ ] Set up SEO meta tags per route
8. [ ] Generate sitemap
9. [ ] Add cookie consent banner
10. [ ] Create 404 page
11. [ ] Add loading skeletons
12. [ ] Implement search in docs
13. [ ] Auto-populate version number on /download
14. [ ] Connect /download to actual .exe file
15. [ ] Add waitlist email capture (non-Windows users)
16. [ ] Set up contact form backend
17. [ ] Write all help articles for /docs
18. [ ] Create logo download pack on /press
19. [ ] Add founder photo and bio
20. [ ] Record product demo videos/GIFs

---

*Website feature specification for Wiztant. Updated as of current build.*
