# Wiztant — Project Summary

## Overview

**Wiztant** is a Windows AI operating assistant distributed as a portable `.exe` (no install required) and sold as SaaS. It enables hands-free computer control through a single hotkey (`F9`) with three distinct modes, plus a transparent chat overlay toggled via `Ctrl+Space`.

---

## Architecture

Wiztant consists of **three separate applications** that share a unified design system but operate independently:

| Application | Stack | Entry Point |
|---|---|---|
| **Desktop App** | Python 3.11 + PyQt6 | `main.py` |
| **React Overlay** | Electron + React 19 + Vite + TypeScript | `ui/wiztant-clui/` |
| **Marketing Website** | React + Vite + Tailwind CSS v3 | `whiztant-website/` |

---

## Desktop App (Python / PyQt6)

### Core Modules (`core/`)

| Module | Responsibility |
|---|---|
| Hotkeys | Global F9 and Ctrl+Space registration (debounced triple-press detection) |
| VLM | Vision-language model integration |
| Voice | Audio capture, STT, and TTS orchestration |
| Agent | UI-TARS computer control loop |
| TTS | Kokoro text-to-speech (6 voices, `af_nova` default) |
| Auth | Supabase email/password authentication |
| Usage | Helicone cost tracking and usage guard |

### UI (`ui/`)

| Component | Description |
|---|---|
| Main Window | PyQt6 window with sidebar, pages: Home, Chat, Agent, System |
| Chat Overlay | Glass panel (340×420px, alpha 0.88) with 3 tabs: Chat / Convo / Agent |
| Login Splash | Supabase email/password + Google OAuth |
| Settings Modal | Frameless 700×540px settings window |
| Waveform Overlay | Bottom-center pill, PIL-rendered (Wispr Flow style) |

### Overlay System

| Overlay | Technology | File |
|---|---|---|
| Waveform | PyQt6 / PIL | `overlay/waveform_overlay.py` |
| Chat (Electron) | React 19 + Framer Motion | `ui/wiztant-clui/src/overlay/` |

The React overlay is launched from Python via `ui/react_overlay.py` using subprocess, with IPC communication via command files.

---

## Feature Modes (F9 Hotkey)

| Presses | Mode | What It Does |
|---|---|---|
| **F9 ×1** | **Dictation** | Whisper transcription → pasted at cursor position |
| **F9 ×2** | **Conversation** | Voice loop with GPT-5.4 + Kokoro TTS (6 voices) |
| **F9 ×3** | **Agent** | UI-TARS 1.5 7B screen-to-action loop; follows `WHISrules.md` navigation spec |
| **Ctrl+Space** | **Overlay Toggle** | Transparent chat overlay (340×420px, alpha 0.88) |

### Dictation Flow
1. User presses F9 once
2. Audio is captured via microphone
3. Sent to Groq Whisper Large v3 Turbo (cloud) or `faster-whisper` (local fallback)
4. Transcribed text is copied to clipboard and pasted at cursor

### Conversation Flow
1. User presses F9 twice
2. Voice capture begins
3. Audio → Whisper → GPT-5.4 (via OpenRouter)
4. GPT response → Kokoro TTS (`af_nova` default, 6 voices available)
5. Spoken response plays back; loop continues

### Agent Flow
1. User presses F9 three times
2. UI-TARS 1.5 7B (via OpenRouter) takes a screenshot
3. Model decides next action (click, type, scroll, etc.)
4. Action is executed via system automation
5. Loop repeats until task completion or user cancellation

---

## React Overlay (`wiztant-clui`)

### Stack
- React 19
- Vite
- TypeScript
- Framer Motion
- Phosphor Icons

### Key Behaviors
- **Opacity-based show/hide** (`setOpacity(0/1)`) — never hide/show to avoid DWM repaint lag on Windows
- Collapsible tune panel (hidden by default, expands on first message)
- Circle action buttons: Review (ShieldCheck), History (ChartBar), Attach (Plus)
- Attach menu popup: Add file / Add image / Trigger workflow
- Background daemon thread launch (no main thread blocking)
- Stale process check via `tasklist` (not `wmic` — faster on Windows)

### Build
```bash
cd ui/wiztant-clui
npm run build
```
Bundle size: ~553KB. Electron serves the `dist/` folder.

---

## Marketing Website (`whiztant-website`)

### Stack
- React 19
- Vite
- Tailwind CSS v3
- PostCSS (CJS config due to `"type": "module"`)

### Current Structure
- Single landing page with notification bar, glass navbar, and empty hero
- Design system: porcelain `#FBE4D8`, notification `#190019`, download button `#2B124C`
- Logo: `wiztantW.svg` (dark backgrounds), `wiztant.svg` (light backgrounds)
- Font: Inter (sans-serif), Banana Pro for CTA button (Poppins fallback)

### Build & Deploy
```bash
cd whiztant-website
npm install
npm run build
```
Previous deployment was manual via `deploy.bat` → Netlify.

---

## Design System (Shared Across All Apps)

### Colors
| Token | Hex | Usage |
|---|---|---|
| Background | `#07070f` | Dark app backgrounds |
| Primary | `#c0c1ff` | Indigo accent |
| Secondary | `#d0bcff` | Purple accent |
| Tertiary | `#4cd7f6` | Teal accent |
| Porcelain | `#FBE4D8` | Website background |
| Notification | `#190019` | Website top bar |
| Download Btn | `#2B124C` | Website CTA |

### Waveform States
| State | Color | Hex |
|---|---|---|
| Idle | Burgundy | `#7B2241` |
| Recording | Mic-reactive (animated) | — |
| Thinking | Cappuccino | `#C4956A` |
| Speaking | Dark Blue | `#1a3a6b` |
| Agent | Green | `#2d6e3e` |

---

## Authentication & Backend

| Service | Purpose |
|---|---|
| **Supabase** | Auth (email/password + Google OAuth), user data, insights tables |
| **Helicone** | Usage guard, cost tracking, request logging |
| **OpenRouter** | LLM gateway (GPT-5.4, UI-TARS 1.5 7B) |
| **Groq** | Whisper STT (cloud) |

### Insights Schema
Two tables track usage metrics:
- `user_insights_lifetime` — lifetime counters per user (words dictated, fixes made, streaks, etc.)
- Daily insights table (implied by schema comments)

Row Level Security (RLS) policies ensure users can only read/upsert their own data.

---

## Pricing

| Plan | Monthly | Annual | Chat | Agent | UI-TARS |
|---|---|---|---|---|---|
| Free | $0 | — | 15/mo | — | — |
| Pro | $15 | $165/yr | 300/mo | 50/mo | 30/mo |
| Power | $25 | $275/yr | 500/mo | 200/mo | 200/mo |

- **Trial**: 3 days, 30 messages, 3 agent tasks, no credit card required
- Annual plans save ~1 month vs monthly

---

## Project File Structure

```
C:\whis\
├── main.py                      # Desktop app entry point
├── whiztant.spec                # PyInstaller spec
├── build.bat                    # Build script for .exe
├── deploy.bat                   # Website deploy script (Netlify)
├── requirements.txt             # Python dependencies
├── WHISrules.md                 # Agent navigation specification
├── wiztant.svg                  # Logo (light backgrounds)
├── wiztantW.svg                 # Logo (dark backgrounds)
│
├── core/                        # Python core logic
│   ├── hotkeys.py
│   ├── vlm.py
│   ├── voice.py
│   ├── agent.py
│   ├── tts.py
│   ├── auth.py
│   └── usage.py
│
├── ui/                          # PyQt6 UI
│   ├── style.py                 # Design tokens + load_svg_pixmap()
│   ├── chat_overlay.py          # PyQt6 glass chat overlay
│   ├── react_overlay.py         # Electron overlay launcher
│   ├── main_window.py           # Main PyQt6 window
│   ├── login.py                 # Login splash
│   ├── settings.py              # Settings modal
│   └── wiztant-clui/            # React overlay app
│       ├── index.html
│       ├── overlay.html
│       ├── package.json
│       ├── vite.config.js
│       └── src/
│           ├── main.tsx
│           ├── overlay/
│           ├── BrandMark.tsx
│           └── ...
│
├── overlay/
│   └── waveform_overlay.py      # PyQt6 waveform pill
│
└── whiztant-website/            # Marketing website
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.cjs
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        └── components/
            ├── NotificationBar.jsx
            ├── Navbar.jsx
            └── Hero.jsx
```

---

## Development Commands

### Desktop App (Python)
```bash
# Install dependencies
pip install -r requirements.txt

# Run app
python main.py

# Build .exe
pyinstaller whiztant.spec --clean
```

### React Overlay
```bash
cd ui/wiztant-clui
npm install
npm run build        # ~1-3 seconds, 553KB bundle
```

### Website
```bash
cd whiztant-website
npm install
npm run build        # Vite build → dist/
npm run preview      # Preview production build
```

---

## Voice & Model Stack

| Layer | Technology | Details |
|---|---|---|
| **STT (cloud)** | Groq Whisper Large v3 Turbo | Fast cloud transcription |
| **STT (local)** | faster-whisper | Fallback when offline |
| **LLM (chat)** | GPT-5.4 via OpenRouter | General conversation |
| **LLM (agent)** | UI-TARS 1.5 7B via OpenRouter | Screen-to-action loop |
| **TTS** | Kokoro (local) | 6 voices, `af_nova` default |

---

## Key Technical Decisions

1. **Portable `.exe`** — No installer required; runs from any folder
2. **Opacity-based overlay toggle** — Avoids Windows DWM repaint lag caused by hide/show
3. **Subprocess IPC for overlay** — Python launches Electron, communicates via file-based commands
4. **Dual STT pipeline** — Groq cloud primary, faster-whisper local fallback
5. **Helicone proxy** — All LLM requests routed through Helicone for usage tracking and guardrails
6. **PIL-rendered waveform** — Custom drawn waveform pill instead of HTML/Canvas for consistent performance
7. **CJS PostCSS config** — Required because `package.json` has `"type": "module"`

---

## Known Limitations & Improvement Areas

- Overlay dropdown menus styling has theme variable gaps
- Chat overlay tab switching between PyQt6 and Electron not fully unified
- File upload refs in attach menu are wired but not connected to a backend handler
- No E2E tests for the overlay IPC protocol
- Website deploy is manual (`deploy.bat`) — no CI/CD pipeline
- Banana Pro font is referenced but Poppins is used as fallback until font files are added

---

## Entry Points Quick Reference

| What | Path |
|---|---|
| Desktop app | `main.py` |
| React overlay launcher | `ui/react_overlay.py` |
| React overlay UI | `ui/wiztant-clui/src/main.tsx` |
| Website | `whiztant-website/index.html` → `src/main.jsx` |
| Design tokens (Python) | `ui/style.py` |
| Agent rules | `WHISrules.md` |
| Logo (dark bg) | `wiztantW.svg` |
| Logo (light bg) | `wiztant.svg` |

---

*Generated for Wiztant project documentation. Solo project by Pranav.*
