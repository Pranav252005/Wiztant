# RePrompt (WizPrompt) — Complete Summary

> **Product:** Wiztant Desktop AI Assistant  
> **Feature Codename:** WizPrompt (branded as **RePrompt** in the UI)  
> **Trigger:** `Ctrl+Shift+Space` — reads clipboard, optimizes, writes back  
> **Location in codebase:** `core/wizprompt.py`, `core/wizprompt_memory.py`, `core/presets.py`, `core/tune_hub/tuners/reprompt_tuner.py`

---

## 1. What RePrompt Is

RePrompt is a **production-grade prompt optimization engine** built directly into Wiztant. It takes any raw text from your clipboard — a half-baked AI prompt, a messy email draft, a bug report scribble, pseudocode, or even a rough product idea — and transforms it into a polished, structurally sound, semantically precise, and emotionally calibrated piece of text ready for any LLM or human reader.

Unlike a simple "rewrite" tool, RePrompt treats prompt optimization as a **multi-dimensional engineering problem**. It doesn't just fix grammar. It re-architects the prompt's logic, removes ambiguity, stress-tests edge cases, and even selects the optimal emotional framing to unlock peak LLM performance.

---

## 2. How It Works — The Architecture

### 2.1 The Four Expert Agents

RePrompt deploys up to four specialized critique agents, each with a narrow, obsessive focus:

| Agent | Focus | What It Does |
|-------|-------|--------------|
| **Structure** | Logical flow & architecture | Checks instruction order, hierarchy, output format clarity, step numbering, and scope boundaries. |
| **Semantic** | Precision & ambiguity | Catches vague language, missing examples, implicit assumptions, and undefined jargon. |
| **Edge Case** | Robustness & failure modes | Finds boundary conditions, contradictions, incomplete coverage, and adversarial inputs that could break the prompt. |
| **Emotional** | Cognitive state calibration | Selects the single best emotion (from 27 scientifically-backed options) to frame the task for peak LLM performance. |

**The 27 Emotions:** admiration, adoration, aesthetic appreciation, amusement, anger, anxiety, awe, awkwardness, boredom, calmness, confusion, craving, disgust, empathic pain, entrancement, excitement, fear, horror, interest, joy, nostalgia, relief, clearance, sadness, satisfaction, paranoid, surprise.

> **Research-backed insight:** LLMs perform measurably better when prompts are emotionally framed. Creative tasks excel with *excitement* or *awe*. Analytical tasks prefer *calmness* and *interest*. Risk-aware tasks benefit from healthy *anxiety* framing.

### 2.2 Two Optimization Modes

#### **Fast Mode (Default) — Single-Shot, ~1–2s**
- One LLM call performs all four analyses simultaneously using a unified expert prompt.
- Outputs structured XML-like tags: `<optimized_prompt>`, `<emotion>`, `<framing>`, `<critique_structure>`, `<critique_semantic>`, `<critique_edge>`.
- Includes **few-shot learning** — retrieves up to 3 past accepted optimizations from memory and injects them as style examples.
- Uses **TuneHub persona weights** to bias the optimization toward what the user historically prefers.

#### **Deep Mode (Legacy) — Multi-Agent, ~3–5s**
- Each agent runs as an independent LLM call (parallelized via `asyncio`).
- A final **Synthesis Agent** merges all critiques into one cohesive, production-ready prompt.
- More thorough but more expensive in API credits. Reserved for future "Pro" tier or manual override.

### 2.3 Prompt Size-Adaptive Intelligence

RePrompt automatically scales its critique depth based on input size:

| Size | Lines | Agents Activated | Best For |
|------|-------|------------------|----------|
| Small | ≤5 | Structure + Semantic | Quick queries, tweets, short prompts |
| Medium | ≤15 | + Edge Case | Code snippets, mid-length instructions |
| Large | >15 | + Emotional | Complex system prompts, PRDs, multi-step workflows |

### 2.4 The Full Pipeline (Fast Mode)

```
Clipboard Text
      ↓
[Validation Layer] — rejects greetings, URLs, gibberish, too-short inputs
      ↓
[Cache Check] — MD5 hash deduplication, 5-min TTL
      ↓
[In-Flight Deduplication] — waits for identical in-progress requests
      ↓
[Credit Pre-Check] — verifies user can afford the call
      ↓
[Embedding + Cluster Lookup] — finds similar past optimizations
      ↓
[Few-Shot Injection] — loads top-3 accepted examples into context
      ↓
[TuneHub Persona Weights] — applies learned preference bias
      ↓
[Single-Shot LLM Call] — fast optimization with structured output
      ↓
[Tag Parsing + Markdown Cleanup] — extracts optimized prompt
      ↓
[Clipboard Write + UI Broadcast] — copies result, sends to overlay
      ↓
[Memory Storage] — stores original → optimized mapping for future learning
```

---

## 3. What RePrompt Helps You With — Use Cases

### 3.1 For Developers & Engineers
- **Code Creation:** Turn "make a function that sorts stuff" into a production-ready, language-specific implementation with error handling and comments.
- **Code Review:** Paste broken or slow code; get a rigorous review with line-referenced issues and corrected code.
- **CLI Commands:** Convert "find files changed yesterday" into efficient `fd` / `ripgrep` commands with safety warnings.
- **Bug Reports:** Transform scattered error screenshots and complaints into structured, actionable bug reports.
- **Prompt Engineering:** Optimize AI prompts you intend to send to other models — adding constraints, structured output formats, and role clarity.

### 3.2 For Product Managers & Founders
- **Idea Refinement:** Turn brainstorming notes into structured concepts with Problem, Solution, Features, Audience, and Challenges.
- **Product Specs:** Convert rambling thoughts into concise PRDs with Objectives, User Stories, and Acceptance Criteria.
- **Project Architecture:** Decompose a product idea into 5 standard layers (Data, Auth, API, UI, Deploy) with phased execution plans.

### 3.3 For Writers & Communicators
- **General Polish:** Fix grammar, remove filler words, improve flow while preserving tone.
- **Technical Writing:** Transform rough explanations into scannable documentation with headers, bullets, and code blocks.
- **Communication:** Fix passive-aggressive Slack messages, clarify calls-to-action, and adjust workplace formality.

### 3.4 For AI Power Users
- **Prompt Optimization:** The meta-use-case — making your prompts to ChatGPT, Claude, Gemini, or any other LLM significantly more effective.
- **Emotional Framing:** Unlocking better LLM outputs by framing tasks with the right cognitive state.

---

## 4. The Memory System — It Learns From You

This is where RePrompt transcends every other prompt optimizer on the market.

### 4.1 Few-Shot Semantic Memory

Every time you accept (or edit and accept) an optimized prompt, RePrompt stores it in a **local SQLite database** (`data/wizprompt_memory.db`) with:
- The original prompt
- The optimized prompt
- Your final edited version (if you changed it)
- A 1536-dimensional semantic embedding
- The cluster it belongs to
- Your thumbs-up / thumbs-down feedback
- The preset used, model used, and emotion selected

### 4.2 Online Clustering

Prompts are automatically grouped into **semantic clusters** using cosine distance on embeddings. Each cluster tracks:
- A dynamic centroid (recalculated as new examples arrive)
- An **EMA (Exponentially Moving Average) score** based on your feedback
- A style bias derived from your preferences:
  - **EMA > 0.8** → "User prefers detailed, elaborate prompts with extensive context"
  - **EMA < 0.2** → "User prefers concise, minimal prompts — strip all fluff"

When you run RePrompt, it:
1. Embeds your input
2. Finds the nearest cluster
3. Retrieves the top-3 most similar **thumbs-up** examples from that cluster
4. Injects them as few-shot style guidance into the optimization call

### 4.3 TuneHub Integration — Bayesian Optimization of Persona Weights

RePrompt is deeply integrated with Wiztant's **TuneHub** adaptive tuning subsystem. The `RePromptTuner` uses:

- **Multi-Task Bayesian Optimization** with Gaussian Process surrogate (Matern-5/2 kernel)
- **Expected Improvement (EI)** acquisition function with L-BFGS-B optimization
- **Thompson Sampling** for exploration vs exploitation
- **Task Classification** via keyword + embedding ensemble (coding, writing, research, planning, building)

It learns five **persona blend weights** per task type:
- `debug` → edge-case agent priority
- `build` → implementation focus
- `research` → structure agent priority
- `write` → semantic precision priority
- `plan` → architectural organization priority

Over time, RePrompt learns *your* optimal blend for *your* typical tasks and applies it automatically.

---

## 5. The Preset System — 10 Optimized Personalities

RePrompt ships with **10 company-defined presets** and supports **user-created custom presets**:

| Preset | What It Does |
|--------|--------------|
| **General Polish** | Grammar, clarity, flow fixes for any text |
| **Code Creation** | Natural language → production-ready code |
| **Code Review** | Bug detection, performance tuning, style fixes |
| **Prompt Engineer** | Optimize AI prompts for other models |
| **Idea Refinement** | Raw thoughts → structured concept |
| **Product Spec** | Notes → PRD with acceptance criteria |
| **Technical Writing** | Documentation polish with headers and code blocks |
| **Communication** | Workplace tone adjustment and clarity |
| **Bug Report** | Scattered complaints → structured reports |
| **CLI Command** | Natural language → efficient terminal commands |
| **Project Architect** | Product idea → 5-layer architecture plan (L1–L5) |

Each preset injects a **system prompt addendum** that biases the optimizer toward that domain's best practices.

---

## 6. Why RePrompt Stands Out From Other Prompt Optimizers

| Dimension | RePrompt | Typical "Prompt Optimizer" Tools |
|-----------|----------|----------------------------------|
| **Depth** | 4 specialized critique dimensions + synthesis | Usually 1 generic rewrite pass |
| **Emotional Framing** | 27-emotion cognitive state calibration | Not present |
| **Memory** | Semantic embedding store with online clustering and EMA feedback tracking | Stateless — no learning |
| **Few-Shot Learning** | Retrieves and injects your past accepted optimizations | No personalization |
| **Adaptive Tuning** | Bayesian Optimization of persona weights per task type | Static, one-size-fits-all |
| **Validation** | Rejects nonsense inputs (greetings, URLs, gibberish) before wasting API calls | Often accepts anything |
| **Presets** | 10 domain-specific optimizers + user-defined custom presets | Generic or limited |
| **Credit System** | Exact token-based deduction with grace overdraft | Usually flat-rate or free |
| **Desktop Integration** | `Ctrl+Shift+Space` — reads clipboard instantly, writes back instantly | Web-only, manual copy-paste |
| **Caching** | 5-minute result cache + in-flight request deduplication | No caching |
| **Model Choice** | User-selectable from 10+ models (Gemini, Claude, GPT, Grok, Qwen, Kimi) | Locked to one provider |
| **Editable Output** | You can edit the result before feedback; it stores your final version | Static output |

### The Key Differentiator: **It Learns Your Voice**

Most prompt optimizers are stateless SaaS tools that treat every user the same. RePrompt is **embedded in your desktop workflow**, remembers every optimization you approve or reject, clusters them by semantic similarity, and gradually learns whether you prefer verbose, detailed prompts or terse, minimal ones. It becomes **your** prompt optimizer — not a generic one.

---

## 7. How RePrompt Helps You Right Now

### The Problem You Face

You are building Wiztant — a complex, multi-layered AI desktop assistant with:
- A Python backend (~17,600 lines)
- An Electron overlay (React + TypeScript)
- A marketing website
- 50+ core modules, platform abstraction layers, STT pipelines, agent loops, memory systems

You constantly need to:
1. **Write prompts** for the UI-TARS vision agent, the Qwen planner, the STT refiner, the dictation corrector
2. **Communicate** bug reports, feature specs, and architecture decisions
3. **Document** APIs, modules, and system behavior
4. **Optimize** your own prompts to other AI models (Claude, GPT, Gemini) when you need help

### How RePrompt Solves Each Pain Point

| Pain Point | RePrompt Solution |
|------------|-------------------|
| **"My prompts to Claude/GPT get mediocre results"** | RePrompt restructures them with explicit roles, constraints, output formats, and emotional framing — immediately improving output quality. |
| **"I spend 10 minutes rewriting the same prompt style over and over"** | The memory system learns your preferred style. After 5–10 uses, it starts retrieving your past accepted optimizations and mirroring your voice. |
| **"My bug reports to myself are messy and I forget details"** | Use the **Bug Report** preset. Paste scattered notes → get structured Title, Steps to Reproduce, Expected/Actual Behavior, Environment. |
| **"I have a feature idea but don't know how to spec it"** | Use **Product Spec** or **Idea Refinement** presets. Get a PRD-ready structure instantly. |
| **"My code review prompts are too vague"** | Use **Code Review** preset. It adds rigor: line references, security checks, performance analysis. |
| **"I want the AI to sound like me, not generic"** | The EMA clustering and few-shot memory mean RePrompt gradually adopts your style — detailed vs concise, formal vs casual. |
| **"I'm burning credits on bad prompt attempts"** | Validation layer rejects bad inputs before API call. Cache prevents re-optimization of identical prompts. Exact token-based billing means you only pay for what you use. |

### The Meta-Benefit: You Become a Better Prompt Engineer

Every time you use RePrompt, you see the **critiques** (structural, semantic, edge-case, emotional). Over time, you internalize these patterns. You start writing better raw prompts instinctively. RePrompt doesn't just optimize your text — it **teaches you** how to think like a prompt engineer.

---

## 8. Technical Quick Reference

| Property | Value |
|----------|-------|
| **Default Model** | `google/gemini-3-flash-preview` |
| **Temperature** | 0.2 (deterministic, precise) |
| **Max Tokens** | 1200 (agents), 1800 (synthesis), 2000 (fast mode) |
| **Cache TTL** | 300 seconds (5 minutes) |
| **Max Memory Examples** | 5000 stored optimizations |
| **Embedding Model** | `openai/text-embedding-3-small` via OpenRouter |
| **Embedding Dim** | 1536 |
| **New Cluster Threshold** | 0.25 cosine distance |
| **EMA Alpha** | 0.3 |
| **API Endpoint** | `POST /wizprompt/optimize` |
| **Feedback Endpoint** | `POST /wizprompt/feedback` |
| **Preset Endpoint** | `GET /presets` |

---

## 9. Conclusion

RePrompt is not a toy. It is a **serious prompt engineering tool** that combines:
- Multi-agent critique architecture
- Emotional cognitive calibration
- Semantic memory with online clustering
- Bayesian adaptive tuning
- Deep desktop integration

It stands out because it is **stateful, personal, and adaptive** — it learns from every interaction and becomes progressively better at matching your style. For a builder like you, juggling a massive multi-stack project, it is a force multiplier: better prompts → better AI outputs → faster development → higher quality → shipped product.

**Use it. Feed it. Let it learn you.**
