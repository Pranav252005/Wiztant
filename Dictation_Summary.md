# Wiztant Dictation — Executive Summary

> **Date:** 2026-05-14  
> **Scope:** How dictation works, why it matters, how TuneHub adapts it, competitive differentiation, and its value for building Wiztant itself.

---

## 1. How Dictation Works

Dictation in Wiztant is a **streaming voice-to-text pipeline** triggered by a single tap of **F9**.

```
Mic Audio → VAD (Voice Activity Detection) → Groq Whisper API →
Smart Local Processing → Phonetic Correction → Smart Paste at Cursor
```

### Step-by-step

| Stage | What happens | Cost |
|---|---|---|
| **Trigger** | F9 tap starts recording; pill turns recording color | Free |
| **VAD** | Streaming voice-activity detection decides when you stop speaking | Free |
| **Transcription** | Audio sent to **Groq Whisper Large v3 Turbo** (cloud) or local `faster-whisper` fallback | **1 credit** |
| **Smart Formatting** | Local deterministic rules: emails, scratch-that, symbols, capitalization | Free |
| **Phonetic Correction** | Double Metaphone + Soundex + domain context fixes misheard words | Free |
| **Smart Paste** | Cross-platform paste at text cursor with clipboard fallback | Free |

The entire pipeline is **< 1.5 seconds** end-to-end for typical phrases.

---

## 2. What It Does (Feature Breakdown)

### 2.1 Smart Dictation (`core/dictation_smart.py`)
Runs on **every transcription** before anything else — zero API cost.

- **Email Recognition**  
  *"contact me at john dot doe at gmail dot com"* → `contact me at john.doe@gmail.com`
- **Scratch-That**  
  *"the meeting is at 5 scratch that 6 PM"* → `the meeting is at 6 PM`  
  Supports 17 correction phrases: *scratch that, delete that, no wait, actually I meant, never mind, ignore that,* etc.
- **Spoken Symbols**  
  *"fifty percent"* → `50%`  
  *"dollar sign five"* → `$5`

### 2.2 Phonetic & Domain Correction (`core/dictation_correction.py`)
Learns from context and past mistakes.

- **Phonetic Fuzzy Matching** — Double Metaphone + Soundex indexes a correction map so *"kimi"* (misheard) matches *"Kimi"* even when spelled differently.
- **Domain Context** — Looks at the previous 3–5 words to disambiguate terms:
  - *"deploy the container"* → software context
  - *"stake the token"* → crypto context
- **Undo Hook** — Captures your manual edits in the preview window and feeds them back as training signals.

### 2.3 Dictation Memory (`core/dictation_memory.py`)
Every voice input is stored **locally** in `data/dictation_memories.json` (never cloud). The overlay dropdown shows your last dictations for quick re-use.

### 2.4 Smart Paste (`core/smart_paste.py`)
Unlike competitors that dump text to clipboard, Wiztant **pastes directly at the text cursor** using OS-level input simulation. Falls back to clipboard only when necessary.

---

## 3. How It Helps You

| Pain Point | How Dictation Solves It |
|---|---|
| **Typing fatigue** | Speak naturally; Wiztant types for you |
| **Context switching** | Keep eyes on code / design; never touch keyboard for notes |
| **Email & messaging speed** | Dictate long emails faster than typing |
| **Accessibility** | Wrist pain, RSI, or mobility limitations become non-issues |
| **Capturing ideas** | F9 → speak → done. No friction = no forgotten ideas |

### For Building Wiztant Specifically

You are writing:
- **Specs & architecture docs** (like `TuneHubSpecifications/`)
- **Markdown plans** (`Plans_Implementation/`)
- **Code comments & docstrings**
- **Discord / Slack updates** to users
- **Task entries** and reminders

Dictation lets you **narrate architecture decisions** while reviewing code, **create task lists** while testing the app, and **draft user-facing copy** without breaking your build-test loop. The scratch-that feature is especially useful when you verbally iterate on wording before committing to text.

---

## 4. How TuneHub Alters Dictation

TuneHub is Wiztant's **adaptive learning engine**. For dictation, it runs the **`DictationTuner`** (`core/tune_hub/tuners/dictation_tuner.py`).

### What TuneHub Learns

1. **Domain-Specific Vocabulary Corrections**
   - You seed it with vocabulary: `["ethereum", "defi", "kubernetes", "microservices"]`
   - It generates phonetic variants and builds a **Trie-based correction map**
   - Future dictations auto-correct *"etherium"* → *"Ethereum"*

2. **Context-Aware Classification**
   - Detects 8 domains: `general, software, crypto, medical, legal, creative_writing, business, custom`
   - Uses **3 signals**: recent text content, active application window, time of day
   - Example: VS Code open + words like *"deploy"* → software domain with high confidence

3. **Confidence Threshold Learning**
   - Per-domain auto-apply thresholds (default 0.85)
   - If you repeatedly **reject** a high-confidence correction, the threshold rises
   - If you **accept** low-confidence suggestions, the threshold drops
   - Result: corrections become more aggressive or conservative based on your behavior

4. **Fuzzy Matching with Penalty**
   - Exact matches auto-apply above threshold
   - Fuzzy matches (> 0.7 similarity) are **suggested** rather than auto-applied, with confidence penalized by 20%

### How to Use It

```bash
# TuneHub is triggered automatically when you use RePrompt or Agent,
# or manually via the Tune panel in the overlay.
# For dictation-specific tuning:
```

In the **Tune panel** → select dictation context → provide your vocabulary list → TuneHub trains a correction model → deployed automatically for future transcriptions.

---

## 5. How Wiztant Dictation Stands Out

| Competitor | Wiztant Difference |
|---|---|
| **Windows Speech Recognition** | No smart paste at cursor; no scratch-that; no domain learning |
| **Apple Dictation** | Cloud-only, no local correction pipeline, no phonetic fuzzy matching |
| **Dragon NaturallySpeaking** | Expensive, heavy, no adaptive domain context, no TuneHub integration |
| **Otter.ai / Rev** | Meeting-focused, not real-time cursor paste, no OS integration |
| **Whisper Web UIs** | Manual upload/download, no hotkey trigger, no smart formatting |

### Unique Strengths

1. **Local-First Intelligence** — Smart formatting, phonetic correction, and domain detection run **locally at zero cost**. Only the raw transcription hits the cloud.
2. **Phonetic Fuzzy + Metaphone** — Most STT tools do exact-word correction. Wiztant uses **Double Metaphone + Soundex** to catch phonetic mishearings (*"kimi"* vs *"kimi"* is trivial; *"kimmy"* vs *"Kimi"* is not).
3. **Scratch-That as First-Class** — 17 built-in verbal editing commands. Competitors treat corrections as afterthoughts.
4. **Cursor-Aware Paste** — Pasting at the cursor is harder than dumping to clipboard. Wiztant does it cross-platform (Windows + Linux).
5. **TuneHub Integration** — No competitor offers an adaptive engine that learns your vocabulary, adjusts confidence per domain, and improves weekly.
6. **Credit-Based, Not Tier-Blocked** — Free users get **50 credits/month** and can use dictation (and agent, RePrompt, TuneHub) within that budget. No feature is artificially walled off.

---

## 6. Credit & Access Model

| Plan | Monthly Credits | Dictation Cost | Availability |
|---|---|---|---|
| **Free** | 50 | 1 credit/use | ✅ Available (not blocked) |
| **Pro** | 1,000 | 1 credit/use | ✅ Available |
| **Power** | 5,000 | 1 credit/use | ✅ Available |

**Key principle:** Features are **never blocked by tier**. They are only blocked when you run out of credits. This ensures every user can experience the full product within their budget.

---

## 7. Quick Reference

| Hotkey | Action |
|---|---|
| **F9 × 1** | Start dictation |
| **F9 × 2+** | Toggle Agent mode |
| **Ctrl + Space** | Open overlay (chat, tasks, history) |
| **Esc** | Dismiss overlay |

| File | Purpose |
|---|---|
| `core/stt_engine.py` | Streaming STT pipeline + VAD |
| `core/voice.py` | Groq Whisper transcription |
| `core/dictation_smart.py` | Email, scratch-that, symbols |
| `core/dictation_correction.py` | Phonetic fuzzy + domain context |
| `core/dictation_memory.py` | Local history storage |
| `core/smart_paste.py` | Cross-platform cursor paste |
| `core/tune_hub/tuners/dictation_tuner.py` | TuneHub adaptive learning |

---

## 8. Summary

Wiztant Dictation is not just "voice-to-text." It is a **context-aware, self-improving dictation system** that respects your workflow:

- Speaks your domain language (crypto, software, medical, legal)
- Learns from your corrections
- Pastes exactly where you need it
- Costs almost nothing (1 credit = one of 50 free monthly uses)
- Integrates deeply with the rest of Wiztant (Agent, Tasks, RePrompt, TuneHub)

For you — building Wiztant itself — it is a **force multiplier**. You can spec features, write docs, manage tasks, and communicate with users without ever leaving your code editor or breaking your train of thought.
