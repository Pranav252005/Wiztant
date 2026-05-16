# The Wiztant Agent

> **AI should operate your computer — not just chat inside a browser tab.**

---

## What Is the Wiztant Agent?

The Wiztant Agent is a **voice-first, vision-powered AI operating assistant** that physically controls your desktop. Unlike chatbots that only return text, the Wiztant Agent **sees your screen, moves your mouse, types on your keyboard, and opens applications** — all autonomously, safely, and verifiably.

It is not a Copilot that suggests code inline. It is not a voice assistant that sets timers. It is an **autonomous desktop agent** that executes multi-step tasks across any application by looking at pixels and emitting real OS-level input.

---

## How the Agent Works

### 1. Trigger: Voice, Not Typing

| Hotkey | Action |
|--------|--------|
| **F9 × 1** | Dictation — instant voice-to-text with smart paste at cursor |
| **F9 × 2** | Toggle Agent Mode — the vision loop starts |
| **Ctrl + Space** | Open/Close overlay — chat, tasks, and agent panel |

The microphone stream is **pre-warmed** at 16 kHz. The first tap has **zero cold-start lag**. You speak a command like:

> *"Open Chrome, go to YouTube, search for lofi hip hop, and play the first video."*

…and the agent executes it step by step without you touching the mouse.

### 2. The Agent Lifecycle

```
[F9 × 2] → User speaks command
    │
    ▼
ask_ai() in core/agent.py
    ├── Credit pre-flight: estimate steps, reserve credits
    ├── Endpoint check: verify OpenRouter/Groq connectivity
    ├── TuneHub tuning: rewrite task if learned patterns exist
    ├── Navigation brain: inject app-specific shortcuts from agent_rules/
    └── Delegates to → core/agent_unified.py
            │
            ├── App awareness: detect target app from task text
            │   └── Chrome profile picker (if multi-profile)
            ├── Ensure app is open + verify window title
            ├── Instruction optimization:
            │   "search YouTube for cats" → https://youtube.com/results?search_query=cats
            ├── Build completion checklist from keywords
            ├── FAST PATH: keyboard shortcuts bypass vision model entirely
            └── MAIN LOOP (max 15 steps):
                    1. Capture screenshot (prefetched in thread pool)
                    2. Call vision model (Gemini / UI-TARS) with screenshot + prompt
                    3. Parse JSON action: click, type, hotkey, scroll, open_app, navigate
                    4. GUARDRAILS: block destructive actions, validate coordinates, detect loops
                    5. Execute action via platform runtime (mouse/keyboard/OS)
                    6. VERIFY: screenshot hash before vs after
                    7. If no change → inject reflection note + retry differently
                    8. If done → check minimum verified actions gate
            │
            └── Result → overlay notification + conversation history
                    └── Credit true-up: refund unused / charge overage
```

### 3. Dual-Model Architecture: Planner vs. Executor

Wiztant separates **cognition** from **perception** using two specialized models:

| Role | Model | Purpose | Cost |
|------|-------|---------|------|
| **Planner** | Qwen 3.6 Plus (text-only, via OpenRouter) | Decomposes requests into architectural plans | Cheap |
| **Executor** | UI-TARS 1.5 7B (vision, via OpenRouter) | Sees screenshots and emits clicks/keys/scrolls | Higher |

**Why this matters:** Most agents (AutoGPT, single-model frameworks) use one model for both thinking and acting. This causes hallucinated tool calls, spiraling loops, and wasted API spend. Wiztant's planner thinks in text (fast, cheap) while the executor sees in pixels (precise, expensive). Each does what it is best at.

### 4. Vision-Based GUI Control

The executor takes a **screenshot of your actual screen**, encodes it as base64 JPEG (max 960 px side), and returns structured JSON actions:

```json
{"action": "click", "x": 342, "y": 518}
{"action": "type", "text": "hello world"}
{"action": "hotkey", "keys": ["ctrl", "t"]}
{"action": "scroll", "x": 500, "y": 300, "amount": -3}
```

Coordinates are emitted in a **normalized 0–1000 scale** and translated to actual pixels per display. This makes the agent **resolution-independent** — it works on 1080p, 1440p, or 4K without retraining.

---

## What Makes It Different from Other Agents

### Wiztant vs. ChatGPT / Claude

| | ChatGPT / Claude | Wiztant |
|---|---|---|
| **Input** | Type into a chat box | Speak (F9) or type in overlay |
| **Output** | Text, images, code | **Real mouse + keyboard actions** |
| **Screen awareness** | None — they are blind | **Screenshots every step** |
| **App control** | None | **Controls any app with pixels** |
| **Verification** | Self-assessment ("I think it worked") | **Screenshot hash diff after every action** |
| **Execution** | You copy-paste their output | **Agent executes directly** |

ChatGPT can tell you *how* to do something. Wiztant **does it for you**.

### Wiztant vs. GitHub Copilot

| | Copilot | Wiztant |
|---|---|---|
| **Scope** | Inside VS Code only | **Any app on your desktop** |
| **Input** | Code context + inline suggestions | Voice + screen vision |
| **Actions** | Suggests code; you type it | **Clicks, types, opens apps autonomously** |
| **Verification** | None (you compile/test) | **Screenshot diff + completion checklist** |

Copilot is a pair programmer. Wiztant is a **digital employee** that operates the entire machine.

### Wiztant vs. Siri / Alexa

| | Siri / Alexa | Wiztant |
|---|---|---|
| **Trigger** | Wake word (always listening) | Push-to-talk (F9) — privacy-first |
| **Scope** | Pre-defined apps/skills | **Any app with a GUI** |
| **Developer support** | None | **8-layer code-aware dictation correction** |
| **Screen awareness** | None | **Full screenshot vision** |
| **Background work** | None | **Hidden window execution without focus theft** |

Siri sets timers. Wiztant **fills out forms, researches topics, and builds software** while you keep working.

### Wiztant vs. AutoGPT

| | AutoGPT | Wiztant |
|---|---|---|
| **Planning** | Single model (prone to loops) | **Dedicated planner + dedicated executor** |
| **Vision** | Fragile / none | **UI-TARS pixel-level control** |
| **Safety** | None (would `rm -rf` or buy things) | **Destructive regex + coordinate bounds + loop detection** |
| **Verification** | Self-assessment | **Screenshot hash + completion checklist** |
| **Background** | Steals focus | **No focus theft via PostMessage isolation** |
| **Cost control** | Unbounded | **Per-step credit gating + true-up refunds** |

AutoGPT proved agents can spiral. Wiztant proves agents can be **controlled, verified, and safe**.

---

## How the Agent Helps You — Real Scenarios

### For Developers

| You Say | What the Agent Does |
|---------|---------------------|
| *"Open Cursor and create a new Next.js project"* | Opens Cursor, stages the command, stops before Enter for your review |
| *"Search Stack Overflow for Python asyncio best practices"* | Opens Chrome, navigates, searches, copies the top answer to your clipboard |
| *"Open Terminal and run npm install"* | Opens terminal, types the command, executes |
| *"Open Figma and create a new file called Landing Page"* | Opens Figma, clicks New File, names it, confirms |
| *"Open YouTube, search for React tutorials, play the first video fullscreen"* | Full multi-app workflow executed autonomously |

The agent knows **40+ apps by name** (Chrome, VS Code, Cursor, Photoshop, Excel, Slack, Discord, etc.) and **10+ websites** with direct URL optimization. It reads your system's installed apps, browser extensions, and PATH so it **never asks "do you have Chrome installed?"**

### For Non-Developers

| You Say | What the Agent Does |
|---------|---------------------|
| *"Open Word and start a new document"* | Opens Word, clicks Blank Document |
| *"Open Settings and turn on dark mode"* | Opens Settings, navigates to Personalization, toggles dark mode |
| *"Search Google for flights to London next week"* | Opens Chrome, goes to Google, types query, executes search |
| *"Open File Explorer and go to Downloads"* | Opens Explorer, navigates to Downloads folder |

### Background Execution (The Productivity Killer Feature)

The agent can run tasks **while you keep working** in your foreground app:

1. You say: *"Research competitors on Product Hunt and copy the top 5 to my clipboard"*
2. The agent launches a **hidden Chrome window**
3. It navigates, extracts data, and copies results
4. You get a **toast notification** when done — never losing focus

Up to **3 parallel background tasks** can run simultaneously. This is impossible with Copilot, Cursor, or AutoGPT — they all steal your screen.

### Project Building (Agent v2)

For structured software development, the agent operates as a **CTO orchestrator**:

1. **Master Planner** (Qwen) generates a 5-layer architectural blueprint:
   - L1: Data & Schema
   - L2: Auth
   - L3: API
   - L4: UI
   - L5: Integration & Deploy

2. Each layer is broken into phases and subphases with **tool assignments**:
   - Cursor for database schema
   - Windsurf for auth logic
   - Lovable for UI components
   - Warp for deployment commands

3. **Human-in-the-loop staging**: The agent stages prompts in Cursor chat or terminal commands in Warp — but **stops before pressing Enter**. You review, then approve.

4. **Automatic verification**: Before advancing to the next phase, the agent runs `tsc --noEmit`, `eslint`, or `curl` health checks.

5. **Git checkpoints**: Every completed layer auto-commits with `wip(agent): L3-P3.1 — Core API Routes`.

This is **not code generation** — it is **project orchestration**.

---

## Special Features That Set It Apart

### 1. Navigation Brain — Rule-File RAG

Before executing any task, the agent reads **10+ markdown rule files** (~350 KB) from `agent_rules/`:

- `agent_navigation.md` — 1,388-line master shortcut file
- `browser_navigation_spec.md` — 1,233-line browser deep reference
- `apps_microsoft.md`, `apps_creative.md`, `apps_browsers.md` — app-specific shortcuts
- `shortcuts_usage_rules.md` — **"Prefer keyboard shortcuts over UI-TARS clicking"**

The agent tokenizes your task, scores every shortcut line for relevance, and injects the best matches into its system prompt. This means it **knows Ctrl+L goes to the address bar** before it ever takes a screenshot.

### 2. Completion Checklists — It Cannot Lie About Being Done

The agent dynamically builds a **task-specific checklist** from keywords:

| Task Keyword | Minimum Verified Actions Required |
|--------------|-----------------------------------|
| "search" | ≥ 2 verified changes |
| "theme" / "dark mode" | ≥ 2 verified changes |
| "first video" | ≥ 3 verified changes |
| "open" / "navigate" | ≥ 1 verified change |

If the agent tries to return `done` too early, the checklist blocks it. It **must prove progress** via screenshot diffs.

### 3. Guardrails — Safety Before Every Action

Three hard-coded checks run **before any action reaches the OS**:

1. **Destructive Action Regex** — Blocks `rm -rf`, `format drive`, `drop table`, `shutdown`, `kill process`, `empty recycle bin`
2. **Coordinate Validation** — Rejects clicks within 5 px of screen edges; bounds up to 4K
3. **Loop Detection** — Compares MD5 hashes of last 3 screenshots; aborts if identical

These are **pure regex + hash comparison** — zero LLM calls, sub-millisecond latency.

### 4. Shortcut-First Philosophy

Most vision agents default to **clicking everything**. Wiztant defaults to **keyboard shortcuts** and only falls back to vision when shortcuts fail. This is faster, more reliable, and coordinate-independent.

### 5. Two-Path Execution (Windows)

On Windows, the agent tries **UI Automation API** (accessibility tree via `pywinauto`) **first** — faster and deterministic — and only falls back to screenshot vision when UIA is insufficient. Most agents are pure vision; Wiztant is **hybrid intelligence**.

### 6. System Context Scanner

On first run, Wiztant performs a **deep scan** of your entire machine (~5–10 seconds):

- Installed apps (Windows Registry HKLM/HKCU)
- Browsers + extensions (Chrome, Edge, Brave, Arc, Firefox, Opera, Vivaldi)
- Running processes (desktop-visible only)
- PATH / CLI commands (`python`, `node`, `git`, `docker`, etc.)
- User folders (Desktop, Downloads)
- Network (IP, gateway, DNS)
- System info (OS, RAM, disk space)

It refreshes **hourly** (lightweight) and **daily at midnight** (full scan). The agent reads this briefing before every task, so it **already knows your environment**.

### 7. Persistent Local Memory

Structured JSON memory (`memory/memory.json`) tracks:

- `identity` — who you are
- `preferences` — how you like things done
- `current_projects` — what you're building
- `tools_and_tech` — your stack (Zod, TanStack, Tailwind, etc.)
- `goals` — what you're working toward
- `agent_tasks` — outcomes of past agent runs

After every exchange, a background thread extracts **new lasting facts** via LLM. This memory is **100% local** — never leaves your machine.

### 8. Credit-Gated Execution

Every agent step costs credits:
- Base fee: 5 credits
- Per step: 2 credits
- Dictation: 1 credit
- RePrompt: varies by model

The system **reserves credits upfront**, checks balance mid-flight, and **refunds unused credits** (true-up) after execution. This prevents runaway API costs.

### 9. Cross-Platform Abstraction

All OS-specific code lives behind abstract base classes in `platforms/`:

| Platform | Screenshot | Input | Window Management |
|----------|------------|-------|-------------------|
| **Windows** | `pyautogui` | `pyautogui` + `win32gui` | `win32con` |
| **Linux (X11)** | `mss` | `xdotool` | `xdotool` |
| **Linux (Wayland)** | `mss` | `wtype` / `ydotool` | `wtype` |

The same agent brain runs on both platforms with **zero code changes**.

### 10. Portable, Privacy-First Distribution

- Single portable executable (PyInstaller)
- No installer, no registry writes
- All data lives locally: `memory/`, `data/`, `memory/tasks.json`
- Dictation memory, vocab, task history, agent memory — **never cloud-synced**

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                      User Voice / Overlay                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  core/agent.py — Router & Credit Gate                       │
│  • Tool registry (25+ tools)                                │
│  • Conversation history persistence                         │
│  • Credit pre-flight & true-up                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  core/agent_unified.py — Unified Brain                      │
│  • App detection → Navigation brain injection               │
│  • Instruction optimization (direct URLs)                   │
│  • Completion checklist builder                             │
│  • Fast-path shortcut detection                             │
│  • Vision loop: screenshot → OMNI → action → verify         │
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Guardrails  │   │ Platform    │   │ WS Bridge   │
    │ (safety)    │   │ Factory     │   │ (UI comms)  │
    └─────────────┘   └─────────────┘   └─────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
           ┌─────────────┐      ┌─────────────┐
           │   Windows   │      │    Linux    │
           │  AgentRuntime│      │ AgentRuntime│
           │  (pyautogui) │      │(xdotool/   │
           │              │      │ wtype/      │
           │  WindowsVLM  │      │ ydotool)    │
           │ (UIA+Vision) │      │             │
           │              │      │  LinuxVLM   │
           │ UI-TARS exec │      │ (Vision only)│
           └─────────────┘      └─────────────┘
```

---

## Comparison Matrix

| Feature | Wiztant | ChatGPT/Claude | Copilot | Siri/Alexa | AutoGPT |
|---------|---------|----------------|---------|------------|---------|
| Voice-first hotkey (F9) | ✅ Instant | ❌ Chat box | ❌ Inline | ✅ Limited | ❌ None |
| Vision-based GUI control | ✅ UI-TARS | ❌ Blind | ❌ Blind | ❌ Blind | ⚠️ Fragile |
| Planner + Executor split | ✅ Qwen + UI-TARS | ❌ Single | ❌ Single | ❌ None | ❌ Single |
| System context scanning | ✅ Full machine map | ❌ None | ❌ None | ❌ Minimal | ❌ None |
| Background execution | ✅ No focus theft | ❌ N/A | ❌ N/A | ❌ N/A | ❌ Steals focus |
| Local persistent memory | ✅ Structured JSON | ⚠️ Cloud | ❌ None | ❌ Minimal | ❌ None |
| Dictation correction | ✅ 8-layer dev-aware | ❌ None | ❌ None | ⚠️ Basic | ❌ N/A |
| Safety guardrails | ✅ Regex + coords + loops | ⚠️ Policy | ⚠️ Policy | ✅ Basic | ❌ None |
| Cross-platform | ✅ PAL layer | ❌ Cloud | ❌ VS Code | ❌ OS-locked | ❌ OS-specific |
| Project orchestration | ✅ 5-layer phase engine | ❌ Code | ❌ Code | ❌ None | ❌ Unstructured |
| Shortcut-first execution | ✅ Shortcuts > clicks | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |
| Credit-gated steps | ✅ Per-step billing | ❌ Flat | ❌ Flat | ❌ N/A | ❌ Unbounded |

---

## The Bottom Line

**What the Wiztant Agent does that no one else does:**

1. **It is the only assistant that plans like a CTO, sees like a user, and acts like a robot** — using separate models for each role.

2. **It is the only voice assistant built for developers** — with 8 layers of code-aware transcription correction that knows `Docker`, `kubectl`, `Windsurf`, and `Supabase`.

3. **It is the only agent that maps your entire machine** — so it never asks "do you have Chrome installed?" It already knows.

4. **It is the only desktop agent that runs in the background without stealing focus** — letting you keep coding while it researches, fills forms, or configures settings.

5. **It is the only portable, privacy-first AI OS assistant** — no installer, no registry, no cloud memory, single `.exe`. Your data never leaves your machine.

6. **It verifies every action** — not with self-assessment, but with screenshot hash diffs and completion checklists that prohibit premature "done" claims.

7. **It prefers shortcuts over clicking** — inverting the typical vision-agent approach for speed and reliability.

**The core thesis:** AI should not be a chatbot you visit in a browser tab. It should be an **operating-layer assistant** that lives on your desktop, understands your environment, and executes tasks autonomously — safely, verifiably, and without getting in your way.
