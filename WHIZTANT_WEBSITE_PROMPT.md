# Whiztant Marketing Website — Comprehensive Build Prompt

---

## Project Overview

You are building the **Whiztant marketing website** — a multi-page React + Vite application that
is the primary conversion funnel for a Windows AI operating assistant. Whiztant lives in the
system tray, activated by F9 hotkey combinations, and operates in three modes: **Dictation**
(F9 × 1), **Conversation** (F9 × 2), and **Agent** (F9 × 3). The product is distributed as a
portable `.exe` file. Pricing tiers: Free ($0), Pro ($15/mo), Power ($25/mo).

The goal of the website is: **communicate value in under 5 seconds, establish trust, and drive
downloads or sign-ups.**

---

## Visual Identity & Design Language

**Color palette:**
```
--porcelain:     #FBE4D8   (primary background)
--deep-plum:     #190019   (navbar, dark sections, notification bar)
--accent-warm:   #E8A87C   (CTA highlights, gradient stops)
--accent-glow:   #C96BFF   (AI/agent animations, electric accents)
--text-primary:  #1A0A1A   (body text on light bg)
--text-light:    #F5EDE8   (body text on dark bg)
--glass-light:   rgba(251, 228, 216, 0.12)
--glass-dark:    rgba(25, 0, 25, 0.65)
```

**Typography:**
- Display / Hero: `Clash Display` or `Syne` — bold, editorial weight
- Body: `DM Sans` — clean, readable
- Mono / Code labels: `JetBrains Mono` — used for hotkey callouts (F9, Ctrl+Space)

**Aesthetic direction:** Dark-glass luxury meets warm porcelain. The app is power + elegance —
like a cockpit interface wrapped in linen. Heavy use of glassmorphism on dark sections,
warm porcelain sections breathe with generous space. Every animation should feel like the AI
is *responding* — alive, fluid, intentional.

**DO NOT** use: purple gradients on white, Inter/Roboto, generic SaaS card layouts, confetti
particles, or flat icon-grid feature sections.

---

## Tech Stack (Website Only)

```
Framework:     React + Vite
Routing:       React Router v6
Animation:     Framer Motion (primary), GSAP + ScrollTrigger (scroll scenes)
3D:            @splinetool/react-spline (embed Spline scenes — no Three.js)
CSS:           Tailwind CSS + custom CSS variables
Icons:         Lucide React
Analytics:     Plausible or PostHog (event tracking)
Auth:          Supabase JS client (login page only)
Fonts:         Google Fonts / Fontsource
```

**3D Rule:** Use Spline embeds for hero 3D scenes (system tray orb, F9 key, waveform 3D).
For everything else, use CSS `perspective` + `transform: rotateX/Y/Z` + Framer Motion for
interactive 3D card tilts, floating elements, and depth effects. Never import Three.js or
any WebGL library directly — Spline handles that via iframe/embed.

---

## Global Shared Components

Build these first — they are used on every page.

### `<NotificationBar />`
- Background: `#190019`, dismissible via ✕ button
- Text: *"How wisdom might help you."* — center-aligned, small caps
- Animate in: slide down from top on page load (Framer Motion `y: -40 → 0`)
- Persists dismiss state in `localStorage`

### `<Navbar />`
- Glassmorphism: `backdrop-filter: blur(20px)`, `background: var(--glass-dark)`
- Logo: `wiztant.svg` left-aligned
- Nav links: Wiztant · Wizprompt · Wizagent (right side)
- CTA: "Download Free" button — pill shape, warm gradient border, porcelain fill
- On scroll > 60px: navbar shrinks slightly (Framer Motion `height` transition)
- Mobile: hamburger → full-screen overlay menu, slides in from right

### `<Footer />`
- Dark section (`#190019`)
- 4-column grid: Product links / Resources / Legal / Socials
- Bottom strip: copyright + "Built for Windows" badge
- Animated: columns fade-stagger in on scroll enter

### `<PageTransition />`
- Wraps every route with Framer Motion `AnimatePresence`
- Entry: `opacity 0→1` + `y: 16→0` over 300ms
- Exit: `opacity 1→0` over 200ms

### `<ScrollReveal />`
- HOC/hook that triggers Framer Motion animation when element enters viewport
- Props: `delay`, `direction` (up/down/left/right), `once`

### `<TiltCard />`
- CSS `perspective: 1000px` + JS `mousemove` → `rotateX/Y` max ±12°
- Framer Motion spring on reset
- Inner glow follows cursor position (`radial-gradient` on `::before`)

### `<GradientOrb />`
- Blurred radial blob, animated with Framer Motion `animate` loop
- Used as ambient background element in hero sections
- Props: `color1`, `color2`, `size`, `position`, `blur`

### `<WaveBar />`
- CSS-only animated audio waveform (7 vertical bars, staggered `scaleY` keyframes)
- Replicate the Whiztant wave visualizer from the app — this is a brand element
- Used inline near feature callouts about voice modes

---

## Page 1 — Home (`/`)

**Goal: Land → understand → want → download. All in one scroll.**

---

### Section 1.1 — Hero

**Layout:** Full viewport height, centered content, dark plum background with animated porcelain
gradient orb bleeding from bottom.

**Content:**
```
EYEBROW:    "AI Operating Assistant for Windows"
HEADLINE:   "One key.
             Total control."
SUBHEAD:    "Whiztant lives in your system tray. Press F9 once to dictate,
             twice to converse, three times to let it take the wheel."
CTA:        [Download Free — Windows]    [Watch it work ↓]
TRUST NOTE: "No install. No credit card. Just press F9."
```

**Animations:**
- Headline: each word animates in with `clip-path: inset(0 100% 0 0 → 0)` stagger — like
  a typewriter that reveals entire words, not characters
- Subhead: fade + `y: 20→0` after headline completes, 400ms delay
- CTAs: scale in with spring bounce
- Background: Spline embed of a floating 3D system tray icon (dark sphere with Whiztant logo
  engraved) — slowly rotates, responds to mouse parallax
- `<GradientOrb />` pulses with warm accent glow behind the Spline scene
- Scroll indicator: bouncing chevron at bottom

**F9 Key Visualizer (Hero sub-element):**
- Render a stylized keyboard key labeled "F9" in `JetBrains Mono`
- On page load, animate: F9 key depresses (`scale: 0.95`, `translateY: 2px`), triggers a
  ripple ring + the headline appears
- This should feel like pressing F9 *caused* the website to load

---

### Section 1.2 — Social Proof Bar

- Single horizontal strip, muted background (`#F2D4C5`)
- Text: "Featured on" + greyscale logos (Product Hunt, Hacker News, etc.)
- Logos auto-scroll marquee (CSS `animation: marquee` infinite) — no JS needed
- On hover: marquee pauses

---

### Section 1.3 — Three Modes Feature Grid

**Layout:** 3 cards side by side (stack on mobile), full-width dark section.

**Each card has:**
- Hotkey badge: `F9 ×1` / `F9 ×2` / `F9 ×3` in `JetBrains Mono`, glowing border
- Mode name: "Dictation" / "Conversation" / "Agent"
- 1-line description
- Animated illustration (CSS/SVG — no image dependencies)

**Card-specific animations (build as CSS + Framer Motion, no external assets needed):**

**Dictation card:**
- Animate a microphone icon → pulse ring → words appear letter by letter in a fake text cursor
- Loop: mic pulse → text fills → cursor blinks

**Conversation card:**
- Animate `<WaveBar />` (the brand waveform), voice wave expands on hover
- Show a back-and-forth speech bubble exchange, bubbles pop in alternating left/right

**Agent card:**
- Animate a cursor moving across a ghost UI (simplified CSS boxes representing a screen)
- Cursor clicks → box highlights → next box → task complete checkmark
- This should feel like watching the agent work — eerie and impressive

**Card interaction:**
- `<TiltCard />` on all three
- On hover: card rises `y: -8px`, glow intensifies on the hotkey badge
- Active card: scale `1.02`, others dim to `0.85 opacity`

---

### Section 1.4 — Live Demo Scene

**Layout:** Full-width, alternating dark/light panel.

**Content:**
```
HEADLINE:  "Watch it happen."
SUBHEAD:   "This is what F9 × 3 looks like."
```

**Animation (pure CSS + Framer Motion — simulates the app in the browser):**

Build a fake Windows desktop UI using HTML/CSS:
- Dark taskbar strip at bottom with clock and system tray area
- "Whiztant" icon glows in the tray
- On scroll trigger (ScrollTrigger): F9 key animates ×3 tap (3 quick depress animations)
- Wave visualizer appears floating in bottom-right corner (CSS bars animated)
- A ghost screen overlay appears (semi-transparent dark pane)
- Animated cursor moves → clicks "Open Chrome" (CSS box) → Chrome opens (another CSS pane)
- Search bar types a query letter by letter
- Cursor moves → hits enter → results appear (placeholder CSS lines)
- Wave disappears. Task complete ✓ badge

This entire sequence runs on ScrollTrigger progress — scrubbed by scroll, not time.
Use GSAP `timeline` pinned to a sticky container so user scrolls through the animation.

---

### Section 1.5 — Testimonials

- 3 cards in a horizontal carousel (Framer Motion drag-to-scroll on mobile, auto on desktop)
- Each card: avatar circle (CSS gradient placeholder), quote, name, role
- Glassmorphism card on porcelain background
- Auto-advances every 4s, pauses on hover

---

### Section 1.6 — Pricing Teaser

- Mini version of full pricing page — 3 columns, just plan name + price + top 3 features + CTA
- Annual/Monthly toggle with animated pill slide (Framer Motion `layoutId`)
- "View full pricing →" link to `/pricing`
- Power tier card: slightly elevated, `--accent-glow` border pulse

---

### Section 1.7 — FAQ Accordion

- 5 questions:
  1. "What is Whiztant?" — plain English, no technical jargon
  2. "Does it work without internet?"
  3. "Is my voice data stored?"
  4. "What Windows versions does it support?"
  5. "How do I uninstall it?"
- Framer Motion `AnimateHeight` expand/collapse
- Active item: left border lights up with accent glow

---

### Section 1.8 — Final CTA

- Full-width dark section
- Giant headline: "One key away from a smarter Windows."
- Download button (large, warm gradient)
- Trust badges: "No credit card" · "Windows 10/11" · "3-day free trial"
- Animated: `<GradientOrb />` pulses behind the button

---

## Page 2 — Features (`/features`)

**Goal: Deep-dive into each capability. Show, don't tell.**

---

### Section 2.1 — Page Header
```
HEADLINE: "Everything Whiztant can do."
SUBHEAD:  "Three hotkeys. Infinite possibilities."
```
- Background: animated dark section with a horizontal waveform spanning full width
- The waveform is CSS-only, not an image

---

### Section 2.2–2.4 — Three Feature Deep-Dives

Use **alternating layout** (image left/text right, then flip) for each mode.

**Each feature block:**
- Left: CSS-animated illustration of the feature in action (as described in Hero section 1.3)
- Right: Headline, description paragraph, 3 bullet points of what it can do
- Animated: on scroll enter, illustration plays its loop; text stagger-reveals

**Dictation:**
```
Headline: "Your words. Instantly typed."
Body:     "Press F9 once, speak naturally, and Whiztant transcribes directly at your cursor —
           in any app, any window, any field."
Bullets:
  → Paste into any application
  → Powered by Whisper-grade transcription
  → One tap to start. One tap to send.
```

**Conversation:**
```
Headline: "An AI that actually listens back."
Body:     "Press F9 twice to start a voice conversation. No window needed.
           Just speak. Whiztant answers through your speakers."
Bullets:
  → Continuous voice loop — no typing required
  → 6 distinct voices to choose from
  → Ctrl+Space opens a chat overlay if you prefer to read
```

**Agent:**
```
Headline: "Let it take the wheel."
Body:     "Press F9 three times. Whiztant sees your screen and acts — opening apps,
           filling forms, navigating the web. You describe the goal. It gets it done."
Bullets:
  → Clicks, types, and navigates autonomously
  → Logs every action — full undo capability
  → Safety-first: requires explicit activation each time
```

---

### Section 2.5 — Overlay Feature
```
Hotkey: Ctrl + Space
Name:   "The Overlay"
Body:   "At any time, in any mode, press Ctrl+Space to summon a transparent tune panel.
         Type instead of speak. Or read the conversation history. It floats above everything."
```
- Animation: show a simulated overlay window appearing over a blurred desktop background (CSS)
- The overlay is a CSS `position: fixed`-style element that fades in during scroll

---

### Section 2.6 — Voice Selector
- 6 voice buttons: `af_nova`, `af_sky`, `bf_emma`, `bf_isabella`, `am_adam`, `bm_george`
- Each button is a pill with the voice name
- On hover: animated `<WaveBar />` appears next to the pill
- On click: placeholder "Now playing…" animation (waveform pulses for 2s)
- Note: "Audio samples coming soon" until actual files are ready — show state gracefully

---

### Section 2.7 — Supported Apps Grid
- Icon grid: VS Code, Chrome, Word, Notepad, Excel, Outlook, Slack, Notion, etc.
- CSS grid, 6 cols on desktop
- Each icon tile: `<TiltCard />` micro-tilt on hover
- "Works everywhere Windows works." — tagline below

---

## Page 3 — How It Works (`/how-it-works`)

**Goal: Remove fear. Show the exact user journey step by step.**

**Use a GSAP ScrollTrigger pinned scroll-story for steps 1–4.**

Pin a sticky container. As the user scrolls, progress through 4 animated steps:

---

**Step 1 — Download**
```
"Download the .exe. Run it. Done."
Sub: "No installer wizard. No admin rights needed. Just double-click."
```
- CSS animation: `.exe` file icon slides in, double-click cursor, Whiztant tray icon appears
  in a CSS taskbar at the bottom of the illustration panel

**Step 2 — Press F9**
```
"Press F9. Once, twice, or three times."
```
- Animated F9 key with tap counter: `1×` label fades in → `2×` → `3×`
- Each tap: key depress animation, colored ripple (dictation = warm, conversation = blue,
  agent = purple glow)
- The mode name animates in beneath the key on each tap count

**Step 3 — Speak**
```
"Just say what you need."
```
- Large `<WaveBar />` centered, bars animate like real audio response
- Words appear above the waveform as if being transcribed in real time (CSS text animation,
  typewriter style, cycling through 3 example phrases)

**Step 4 — Done**
```
"Whiztant handles the rest."
```
- CSS illustration: agent cursor completes a task, checkmark appears
- Confetti-lite: a few geometric shapes (squares, circles) scatter from the checkmark using
  Framer Motion — nothing heavy

---

**After the scroll story:**

**System Tray Explainer**
- CSS illustration of a Windows taskbar bottom strip
- Arrow pointing to tray area: "Lives here. Always ready. Zero window clutter."
- Whiztant icon pulses gently

---

## Page 4 — Pricing (`/pricing`)

**Goal: Clear, honest, friction-free conversion.**

---

### Section 4.1 — Monthly/Annual Toggle
- Pill toggle, Framer Motion `layoutId` animated selection indicator
- Annual shows "Save 1 month free" badge (animated pop-in)

---

### Section 4.2 — Three Plan Cards

| | Free | Pro | Power |
|---|---|---|---|
| Price | $0 | $15/mo | $25/mo |
| Chats/mo | 15 | 300 | 500 |
| Agent tasks | — | 50 | 200 |
| CTA | Get Started | Start Free Trial | Start Free Trial |

**Card styling:**
- Free: simple border, no glow
- Pro: warm gradient border
- Power: `--accent-glow` animated border pulse (CSS `@keyframes` border-color animation),
  "Most Popular" badge floats above the card

**Interaction:**
- `<TiltCard />` on all three
- Hover: card lifts, shadow deepens
- CTA buttons: fill-sweep animation on hover (`background` sweeps left→right)

---

### Section 4.3 — Usage Limits Visual
- Horizontal progress bars showing usage limits per tier
- Bars animate from 0 to their fill percentage on scroll enter (Framer Motion)
- Labels: "15 chats" / "300 chats" / "500 chats"

---

### Section 4.4 — Trial Banner
```
"3-day free trial. No credit card. Cancel any time."
```
- Centered, porcelain bg, simple pill badge + text

---

### Section 4.5 — Billing FAQ
- 5 questions: upgrade, downgrade, cancellation, refund, annual billing
- Same accordion component as Home

---

## Page 5 — Download (`/download`)

**Goal: Get the file in their hands in the fewest clicks.**

---

### Hero
- Giant download button centered: "Download Whiztant for Windows"
- Below: Version badge, release date
- System requirements: Windows 10 / 11 · 4GB RAM minimum · 200MB disk
- SHA256 hash shown in a `<code>` block (copyable, one-click copy button)

### Post-Download Steps
```
1. Run Whiztant.exe
2. Sign in or create a free account
3. Press F9 — you're live
```
- Animated: step numbers count up, each step fades in sequentially

### Non-Windows Banner
```
"Not on Windows? Join the waitlist."
```
- Email input + "Notify Me" button
- Submits to Supabase `waitlist` table
- Success state: animated checkmark, "You're on the list."

---

## Page 6 — Login (`/login`)

**Goal: Fast, clean authentication. No friction.**

- Center-card layout on dark porcelain background
- Google OAuth button (primary, prominent)
- Divider: "or continue with email"
- Email + Password fields with animated label float
- Toggle: Login ↔ Sign Up (animated panel flip using Framer Motion `AnimatePresence`)
- Forgot Password: link → email input step (same card, animated swap)
- Error states: shake animation on card, red border on bad fields
- Post-login redirect: back to `/download` or previous page

---

## Page 7 — Support (`/support`)

- Search bar (prominent, top of page) — filters the article list client-side
- Quick links: 5 article cards (Getting Started, Troubleshooting, Billing, Agent Safety, Uninstall)
- Contact form: Name, Email, Category dropdown, Message textarea → Supabase function
- Discord link card: "Join the community →"

---

## Page 8 — Docs (`/docs`)

- Sidebar navigation (7 sections, collapsible) + main content area
- Sections: Getting Started · Dictation Guide · Conversation Guide · Agent Guide · Settings · Shortcuts · Troubleshooting
- Keyboard shortcuts section: rendered as a styled table with `JetBrains Mono` key badges
- `prefers-reduced-motion` respected everywhere
- Mobile: sidebar collapses into a drawer

---

## Page 9 — Press (`/press`)

- Brand kit download section: Logo pack (SVG, PNG) — download buttons
- Product screenshot placeholders (with "Coming Soon" overlay until assets ready)
- Founder bio card: photo placeholder + bio text + press contact email
- Press mentions list (empty state: "Coverage coming soon")

---

## Page 10 — Legal Pages

Three pages: `/privacy-policy`, `/terms-of-service`, `/cookie-policy`

- All use the same layout: max-width prose container, good typographic rhythm
- Sidebar: anchor link nav to each section
- Last updated date shown at top
- Cookie banner (bottom of page, first visit): "We use cookies to improve your experience."
  Accept / Decline buttons. Respects `localStorage` state.

---

## Analytics Events (Track Every One)

| Event name | Trigger |
|---|---|
| `page_view` | Every route change |
| `download_click` | Download button click |
| `pricing_toggle` | Monthly/Annual switch |
| `plan_select` | Click pricing CTA |
| `signup_start` | Open login modal/page |
| `signup_complete` | Successful Supabase auth |
| `trial_start` | Begin free trial flow |
| `waitlist_signup` | Non-Windows email capture |
| `faq_expand` | Open any FAQ item |
| `scroll_depth` | At 25%, 50%, 75%, 100% |

---

## Animation System Rules (Global)

1. **All animations respect `prefers-reduced-motion`** — wrap every Framer Motion animation with:
   ```js
   const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
   ```
   If true: skip transitions, show final states immediately.

2. **ScrollTrigger scenes** use GSAP `ScrollTrigger.create()` with `start: "top 80%"` for
   stagger reveals and `pin: true` for the How It Works scroll-story.

3. **Framer Motion variants** — define a global `fadeUp`, `fadeIn`, `staggerContainer` variants
   object in `src/animations/variants.js` and import across pages.

4. **Spline scenes** — embed as `<Spline scene="URL" />` inside a `loading` wrapper that shows
   a CSS gradient placeholder until the 3D scene loads.

5. **CSS 3D perspective** — set `perspective: 1200px` on parent containers for tilt effects.
   Never apply `perspective` to the animated element itself.

6. **No animation should block interactivity** — all animations run on the compositor thread
   (only `transform` and `opacity` — never `width`, `height`, `margin`).

---

## Responsive Breakpoints

| Token | Width | Key Changes |
|---|---|---|
| `sm` | < 640px | Single column, hamburger nav, stacked cards |
| `md` | 640–1024px | 2-col grids, simplified tilt, reduced parallax |
| `lg` | > 1024px | Full layout, full parallax, hover effects active |

Disable mouse-parallax and TiltCard tilt on touch devices (detect via `pointer: coarse`).

---

## File Structure (Website)

```
whiztant-website/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── NotificationBar.jsx
│   │   │   ├── Navbar.jsx
│   │   │   ├── Footer.jsx
│   │   │   └── PageTransition.jsx
│   │   ├── ui/
│   │   │   ├── TiltCard.jsx
│   │   │   ├── GradientOrb.jsx
│   │   │   ├── WaveBar.jsx
│   │   │   ├── ScrollReveal.jsx
│   │   │   ├── FAQ.jsx
│   │   │   └── SectionDivider.jsx
│   │   └── home/
│   │       ├── HeroSection.jsx
│   │       ├── ModeCards.jsx
│   │       ├── DemoScene.jsx
│   │       ├── Testimonials.jsx
│   │       ├── PricingTeaser.jsx
│   │       └── FinalCTA.jsx
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Features.jsx
│   │   ├── HowItWorks.jsx
│   │   ├── Pricing.jsx
│   │   ├── Download.jsx
│   │   ├── Login.jsx
│   │   ├── Support.jsx
│   │   ├── Docs.jsx
│   │   ├── Press.jsx
│   │   ├── PrivacyPolicy.jsx
│   │   ├── TermsOfService.jsx
│   │   ├── CookiePolicy.jsx
│   │   └── NotFound.jsx
│   ├── animations/
│   │   └── variants.js
│   ├── hooks/
│   │   ├── useScrollProgress.js
│   │   └── usePrefersReducedMotion.js
│   ├── lib/
│   │   └── supabase.js
│   ├── App.jsx
│   └── main.jsx
├── public/
│   ├── wiztant.svg
│   └── favicon.ico
├── index.html
├── vite.config.js
└── tailwind.config.js
```

---

## SEO Requirements

- Each page: `<title>`, `<meta description>`, Open Graph tags (`og:title`, `og:image`,
  `og:description`), Twitter card tags
- Home page: `StructuredData` JSON-LD for `SoftwareApplication` schema
- `robots.txt` and `sitemap.xml` auto-generated at build time
- All images: `alt` text, `loading="lazy"`, `width`/`height` set to prevent CLS

---

## Implementation Order (Build in this sequence)

```
Phase 1 — Foundation
  ├── Vite + React + Tailwind + Router setup
  ├── CSS variables + font imports
  ├── NotificationBar, Navbar, Footer
  └── PageTransition wrapper + routes

Phase 2 — Shared UI Kit
  ├── TiltCard, GradientOrb, WaveBar
  ├── ScrollReveal hook + variants.js
  └── FAQ accordion component

Phase 3 — Home Page (highest priority)
  ├── Hero section (Spline + F9 key animation)
  ├── Social proof marquee
  ├── Three mode cards with CSS animations
  ├── GSAP demo scroll-scene
  ├── Testimonials carousel
  ├── Pricing teaser
  ├── FAQ accordion
  └── Final CTA

Phase 4 — Conversion Pages
  ├── Pricing (full)
  ├── Download
  └── Login

Phase 5 — Content Pages
  ├── Features
  ├── How It Works (GSAP pinned scroll)
  ├── Support
  └── Docs

Phase 6 — Supplementary
  ├── Press
  ├── Legal pages
  ├── 404 page
  └── Cookie consent banner

Phase 7 — Polish & Perf
  ├── Analytics events
  ├── SEO meta tags per route
  ├── sitemap + robots.txt
  ├── Performance audit (LCP < 1.5s)
  └── prefers-reduced-motion pass
```

---

*This is the complete specification for the Whiztant marketing website. Build exactly as
described. Every animation should feel like the product is alive — not decorative.*
