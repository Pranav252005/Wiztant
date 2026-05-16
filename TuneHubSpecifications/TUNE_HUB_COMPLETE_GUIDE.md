# Tune Hub — Complete Guide & Feature Reference

> **Product:** Wiztant Universal Meta-Learning System  
> **Version:** 1.0 (Current Implementation)  
> **Last Updated:** 2026-05-14  
> **Status:** Phase 1 Implemented (Manual/Seed Tuning) | Phase 2 Planned (Full ML Pipeline)

---

## 1. What Is Tune Hub?

**Tune Hub** is Wiztant's universal meta-learning engine. It observes how you use Wiztant, learns your unique patterns, vocabulary, workflows, and preferences, then automatically injects optimized configuration parameters into every feature you touch.

Instead of a one-size-fits-all AI assistant, Tune Hub makes Wiztant **your** assistant — it learns that you prefer a "debug-heavy" persona for coding, that you dictate medical terms frequently, or that you automate the same Photoshop workflow every morning.

### The Flywheel

```
You use a feature → Tune Hub detects patterns → Learns optimal config
    → Applies it automatically next time → Better output → You use it more
        → More data → Better tunes → Deeper personalization
```

---

## 2. Architecture Overview

### Two-Desktop Design

| Desktop | Role | What's Running |
|---------|------|----------------|
| **Desktop 1** (Production) | Fast, deterministic runtime | Tune lookup & application (< 50ms), local SQLite cache |
| **Desktop 2** (Experimentation) | Slow, expensive learning | Bayesian optimization, A/B testing, validation, model training |

Communication between desktops happens via async message queue (NATS / RabbitMQ planned). Today, both run on the same machine — Desktop 2 is a logical separation that becomes physical when cloud learning launches.

### Core Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FEATURE TRIGGERS                        │
│   RePrompt    Dictation    Agent    (Future Features)       │
│       │           │          │                              │
│       └───────────┴──────────┘                              │
│                   │                                         │
│        ┌──────────▼──────────┐                             │
│        │  Tune Application   │  < 50ms hot path            │
│        │    Middleware       │                             │
│        └──────────┬──────────┘                             │
│                   │                                         │
│        ┌──────────▼──────────┐                             │
│        │     TuneHub Core    │  Orchestrator               │
│        │   (Orchestrator)    │                             │
│        └──────────┬──────────┘                             │
│                   │                                         │
│        ┌──────────▼──────────┐                             │
│        │   SQLite Storage    │  Local cache (Free/Pro)     │
│        │   data/tune_hub.db  │                             │
│        └─────────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
│        ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
│        │RePrompt │   │Dictation│   │  Agent  │
│        │ Tuner   │   │ Tuner   │   │ Tuner   │
│        │(Plugin) │   │(Plugin) │   │(Plugin) │
│        └─────────┘   └─────────┘   └─────────┘
```

---

## 3. What Can You Tune?

### 3.1 RePrompt Tuner (`feature_name="reprompt"`)

**What it learns:** Optimal persona blend weights for your prompt optimization tasks.

WizPrompt/RePrompt uses 5 expert personas internally:
- `debug` — Error detection & fixing
- `build` — Implementation & creation
- `research` — Information gathering
- `write` — Communication & prose
- `plan` — Organization & roadmapping

**What Tune Hub alters:**
- The **blend weights** of these 5 personas per task type
- Task classification (coding, writing, research, planning, building)
- Which persona dominates based on your actual usage patterns

**Example:**
```
Before tuning: All personas at 0.5 (generic)
After tuning for "coding tasks":
  debug: 0.75, build: 0.45, research: 0.25, write: 0.0, plan: 0.10
→ Your RePrompt outputs become more debugging-oriented automatically
```

**How to make it better:**
- Run Tune Hub on specific task descriptions (e.g., "Optimize my React debugging prompts")
- Use higher complexity tiers for multi-domain blends
- Provide feedback on tuned outputs (thumbs up/down) — this feeds back into the GP model

**Integration point:** `core/wizprompt.py` → `_apply_persona_weights()`

---

### 3.2 Dictation Tuner (`feature_name="dictation"`)

**What it learns:** Domain-specific vocabulary corrections and your personal speech patterns.

**What Tune Hub alters:**
- **Correction map:** Heard word → Correct word mappings
- **Domain detection:** Software, crypto, medical, legal, creative writing, business, custom
- **Confidence thresholds:** When to auto-apply vs. suggest vs. pass
- **Fuzzy matching:** Phonetic similarity for words not in the exact map

**Example:**
```
You say: "Kuberneteas" → Tune Hub learns → Next time: "Kubernetes"
You say: "De-fi" → Tune Hub learns → Next time: "DeFi"
Domain: software → Boosts software term corrections
```

**How to make it better:**
- Seed with your domain vocabulary via the `vocabulary` context field
- Enable user correction recording (`record_user_correction()`) so it learns from your edits
- Tune the `auto_apply_threshold` per domain if it's too aggressive or too conservative

**Integration point:** `core/hotkeys.py` → dictation pipeline, after STT, before smart paste

---

### 3.3 Agent Tuner (`feature_name="agent"`)

**What it learns:** Automation sequences (recipes) for repetitive desktop tasks.

**What Tune Hub alters:**
- **Action recipes:** Learned sequences of clicks, hotkeys, types, menu selects
- **Target app detection:** Which app you're trying to automate
- **Subgoal decomposition:** Breaks tasks into steps (open → navigate → edit → save)
- **Causal model:** Learns which actions cause which state changes (for recovery)

**Example:**
```
Task: "Open Photoshop and apply my signature preset"
Learned recipe:
  1. open_app(target="Adobe Photoshop")
  2. menu_select(path=["File", "Open"])
  3. adjustment_apply(preset="signature")
```

**How to make it better:**
- Describe tasks with explicit step counts in the context (`estimated_steps`)
- Use similar task warm-start — the recipe library retrieves similar past recipes
- Validate on Desktop 2 first; dry-run before deploying to Desktop 1

**Integration point:** `core/agent.py` → recipe injection before agent loop execution

---

### 3.4 Future Tuners (Pluggable)

Because every tuner implements `TuneBase`, adding new features requires zero changes to Tune Hub core:

| Future Tuner | What It Would Learn |
|--------------|---------------------|
| **Browser Agent Tuner** | Web automation patterns, form fills, navigation sequences |
| **Task Tuner** | Your task creation patterns, due-time preferences, reminder habits |
| **Memory Tuner** | What you consider important vs. forgettable for memory storage |
| **STT Tuner** | Your accent patterns, preferred transcription style (formal vs. casual) |

---

## 4. How It Works — The Full Pipeline

### Phase 0: Complexity Estimation (< 100ms)

When you describe what you want to tune, the tuner analyzes the task:

```python
complexity = tuner.estimate_complexity(task, context)
# Returns: ComplexityLevel.LOW | MEDIUM | HIGH
```

| Complexity | Test Variations | Credit Range | Time | Use Case |
|------------|-----------------|--------------|------|----------|
| **LOW** | 1-3 | 100-800 | 30s-2min | "Make my emails more formal" |
| **MEDIUM** | 5-15 | 500-3,000 | 2-8min | "Optimize RePrompt for full-stack coding" |
| **HIGH** | 15-50+ | 2,000-10,000 | 5-20min | "Deep Salesforce workflow automation" |

---

### Phase 1: Learning (Desktop 2)

The core experimentation loop. This is where credits are consumed.

**RePrompt Tuner Algorithm:**
- **Surrogate Model:** Gaussian Process (Matern-5/2 kernel) via scikit-learn
- **Acquisition Function:** Expected Improvement (EI) with L-BFGS-B optimization
- **Exploration Strategy:** 3-phase loop — Warm-start → Exploration → Exploitation
- **Max iterations:** 12 (empirically: 90% convergence by iteration 10)
- **Convergence checks:** Quality plateau | Acquisition flat | Weight stability | Budget exhausted

**Dictation Tuner Algorithm:**
- **Base Corrector:** Trie-based prefix correction map with frequency weighting
- **Context Classifier:** Heuristic domain detection (8 domains)
- **Update Rule:** Exponential weighted moving average with recency bias
- **Active Learning:** Uncertainty sampling queue for low-confidence corrections

**Agent Tuner Algorithm:**
- **Exploration:** Hierarchical task planner with macro-action library
- **Causal Model:** Structural Causal Model (SCM) stub for action-outcome learning
- **Reward Function:** Multi-factor (goal progress 50%, efficiency 25%, stability 15%, safety 10%)

---

### Phase 2: Validation (Desktop 2)

Before any tune reaches your Desktop 1, it must pass validation:

| Check | Threshold | Failure Action |
|-------|-----------|----------------|
| Minimum quality score | ≥ 0.70 | Retry with more data |
| Minimum observations | ≥ 3 | Extend learning |
| Hold-out task testing | Average ≥ 0.75, Min ≥ 0.60 | Reject & refund 70% |
| User override rate | < 30% | Switch to preference learning |

---

### Phase 3: Deployment & Sync

Once validated, the tune is:
1. Marked `DEPLOYED` in storage
2. Synced to Desktop 1 (if Pro/Power tier)
3. Available for real-time application

---

### Runtime: Hot-Path Application (< 50ms)

Every time a tuned feature triggers:

```python
# In middleware (core/tune_hub/middleware.py)
tuned_input = middleware.apply(
    user_id=user_id,
    feature_name="dictation",  # or "reprompt", "agent"
    task=current_task,
    feature_input={"text": transcribed_text}
)
# Returns feature_input with learned parameters injected
```

**Latency budget:**
- Tune resolution (SQLite lookup): ~5-20ms
- Tune application (parameter injection): ~1-5ms
- Total overhead: **< 50ms** (P99 target)

---

## 5. How to Use Tune Hub

### 5.1 Via REST API

Tune Hub exposes a FastAPI router at `/tunehub`:

```bash
# Create a new tune
POST /tunehub/tune
{
  "user_id": "your_user_id",
  "feature_name": "reprompt",
  "task": "Learn optimal persona weights for my coding tasks",
  "budget_limit": 100,
  "context": {"user_id": "your_user_id"}
}

# Resolve a tune at feature trigger time (hot path)
POST /tunehub/resolve
{
  "user_id": "your_user_id",
  "feature_name": "dictation",
  "task": "kubernetes docker typescript",
  "feature_input": {"text": "kuberneteas docker typeskript"}
}

# List your tunes
GET /tunehub/tunes/{user_id}

# Delete a tune
DELETE /tunehub/tunes/{user_id}/{tune_id}
```

### 5.2 Via Python API

```python
from core.tune_hub import create_tune_hub
from core.tune_hub.quality.judge import LLMJudge

# Initialize
hub = create_tune_hub(tier="pro", judge_factory=LLMJudge)

# Create a tune
from core.tune_hub import TuneRequest
req = TuneRequest(
    user_id="user_123",
    feature_name="reprompt",
    task="Optimize for React debugging",
    budget_limit=50
)
result = hub.tune_feature(req)

# Apply a tune at runtime (called automatically by middleware)
tuned = hub.resolve_tune(
    user_id="user_123",
    feature_name="dictation",
    task="software vocabulary",
    feature_input={"text": "kuberneteas"}
)
# tuned["text"] now contains "Kubernetes" if a tune exists
```

### 5.3 Via Middleware (Automatic)

Once initialized in `app/main.py`, Tune Hub middleware applies tunes automatically:

```python
# In your feature code — tunes are applied transparently
from core.tune_hub.middleware import TuneApplicationMiddleware

middleware = TuneApplicationMiddleware(hub)
tuned_input = middleware.apply(user_id, "reprompt", task, feature_input)
# tuned_input now has persona_weights injected if a tune exists
```

---

## 6. Credit System & Economics

Tune Hub uses the shared Wiztant credit system (`core/credit_system.py`).

### Tier Allocations

| Tier | Monthly Credits | Tune Complexity |
|------|-----------------|-----------------|
| **Free** | 50 | LOW only |
| **Pro** | 1,000 | LOW + MEDIUM |
| **Power** | 5,000 | LOW + MEDIUM + HIGH |

### Credit Costs

| Operation | Cost |
|-----------|------|
| RePrompt tune (LOW) | ~100-800 credits |
| RePrompt tune (MEDIUM) | ~500-3,000 credits |
| RePrompt tune (HIGH) | ~2,000-10,000 credits |
| Dictation tune (LOW) | ~100-500 credits |
| Dictation tune (MEDIUM) | ~300-1,500 credits |
| Agent tune (LOW) | ~200-1,000 credits |

### Refund Policy
- **70% refund** if learning fails or validation fails
- No refund if you manually discard a completed tune

---

## 7. Best Models for Each Tuner

### Quality Judge (Learning Phase)

The judge scores experiment outputs during learning. Model choice affects tune quality significantly.

| Judge Model | Speed | Quality | Best For |
|-------------|-------|---------|----------|
| `SimpleJudge` (heuristic) | Instant | Low | Development, testing, free tier fallback |
| `RandomJudge` | Instant | None | Debugging only |
| `LLMJudge` (Claude Sonnet) | ~2s/call | High | Production — default recommended |
| `ClaudeJudge` (Claude Sonnet 4) | ~2s/call | Highest | Complex multi-domain tasks |

**Recommendation:** Use `LLMJudge` for all production tuning. The cost is included in the tune credit estimate.

### RePrompt Feature Model

The model used to generate responses during the RePrompt learning loop:

| Model | Speed | Cost | When to Use |
|-------|-------|------|-------------|
| `google/gemini-3-flash-preview` | Fast | Low | Default, general purpose |
| `anthropic/claude-sonnet-4` | Medium | Medium | Higher quality coding/writing tunes |
| `anthropic/claude-opus-4` | Slow | High | Maximum quality, complex reasoning tasks |

### Dictation & Agent

These tuners don't call LLMs during learning (they use simulation/heuristics), so judge model is the only cost factor.

---

## 8. Guardrails & Safety

### Boundary Enforcement (`core/tune_hub/guardrails.py`)

- **Feature whitelist:** Only `reprompt`, `dictation`, `agent` are tunable
- **Injectable key whitelist:** Each tuner can only touch specific keys in `feature_input`
- **Path sanitization:** Persistence paths are checked for directory traversal
- **Immutable input protection:** `feature_input` is deep-copied before modification

### What Tuners CANNOT Do

| Restriction | Why |
|-------------|-----|
| Cannot modify arbitrary feature input keys | Prevents injection attacks |
| Cannot access files outside `data/tune_models/` | Sandbox enforcement |
| Cannot run without user-approved budget | Credit gate |
| Cannot deploy without validation | Quality gate |
| Cannot learn on Desktop 1 | Separation of concerns |

---

## 9. How to Make Tune Hub Better

### 9.1 Improving RePrompt Tunes

1. **Be specific in task descriptions** — "Coding" is weak; "React debugging with hooks" is strong
2. **Use MEDIUM/HIGH complexity** for multi-domain work — the GP needs more iterations to find good blends
3. **Provide feedback** — The system records your ratings; these become observations for the GP
4. **Warm-start from similar tasks** — Previous observations are loaded automatically
5. **Use presets + tunes together** — Presets set the direction, tunes optimize the blend

### 9.2 Improving Dictation Tunes

1. **Seed vocabulary proactively** — Pass your domain terms in the `vocabulary` context field
2. **Enable correction recording** — When you edit dictation output, call `record_user_correction()`
3. **Tune per-domain thresholds** — Medical domain may need lower auto-apply threshold than general
4. **Use custom domain** for niche fields not in the 8 defaults

### 9.3 Improving Agent Tunes

1. **Describe tasks with step estimates** — `context={"estimated_steps": 5}` improves complexity detection
2. **Name the target app explicitly** — "In Photoshop..." vs. "Edit a photo..."
3. **Validate dry-runs first** — The tuner runs 3 dry-run validations before marking DEPLOYED
4. **Build a recipe library** — Similar tasks warm-start from existing recipes automatically

### 9.4 System-Level Improvements

| Improvement | Impact | Effort |
|-------------|--------|--------|
| Switch from SQLite to PostgreSQL + Redis (Pro tier) | Faster lookups, versioning, sync | Medium |
| Add Desktop 2 cloud worker | True separation, parallel learning | High |
| Implement Thompson Sampling for RePrompt | Better exploration/exploitation balance | Medium |
| Add user feedback loop UI | Human-in-the-loop quality improvement | Medium |
| Enable marketplace (Power tier) | Community tunes, network effects | High |
| Add concept drift detection | Auto-re-tune when patterns change | Medium |

---

## 10. Storage & Persistence

### SQLite Schema (`data/tune_hub.db`)

Tunes are stored in a local SQLite database with the following logical structure:

```
tunes table:
  - user_id, tune_id, feature_name, task_signature
  - payload (JSON), quality_score, complexity, status
  - version, parent_version, created_at, metadata
```

### Files Created

| Path | Purpose |
|------|---------|
| `data/tune_hub.db` | Main tune storage (SQLite) |
| `data/tune_models/*_corrections.json` | Dictation tuner correction maps |
| `data/tune_models/*_recipes.json` | Agent tuner recipe libraries |
| `data/tunehub_settings.json` | User settings (model preferences, tier) |

---

## 11. Integration Points

### Where Tune Hub Touches the Rest of Wiztant

| File | Integration | What Happens |
|------|-------------|--------------|
| `app/main.py` | Initialization | Creates `create_tune_hub()` + `TuneApplicationMiddleware`, stores in `core.tune_hub` |
| `core/hotkeys.py` | Dictation pipeline | After STT transcription, middleware applies dictation corrections |
| `core/wizprompt.py` | RePrompt optimization | `_apply_persona_weights()` consumes Tune Hub's learned persona blends |
| `core/agent.py` | Agent execution | Recipe hints from AgentTuner are injected before the agent loop runs |
| `core/server.py` | REST API | `/tunehub/*` endpoints expose full Tune Hub API |
| `core/credit_system.py` | Billing | `calculate_tunehub_credits()` estimates and deducts learning costs |

### Feature Toggle

Tune Hub is gated by the `tunehub` feature flag in `data/settings.json`:

```json
{"features": {"agent": true, "tunehub": true, "tasks": true, "reprompt": true}}
```

---

## 12. Known Limitations & Phase 2 Plan

### Current Limitations (Phase 1)

1. **No true Desktop 2 separation** — Learning runs on the same machine (logical separation only)
2. **No marketplace** — Cannot share or import community tunes yet
3. **Limited model training** — GP surrogate is lightweight; no deep neural model training yet
4. **No automatic re-tuning** — Tunes don't auto-update when your behavior drifts
5. **Simulated agent execution** — Agent tuner uses simulation, not real desktop interaction
6. **Single-machine only** — No cross-device sync of tunes

### Phase 2 Roadmap

| Feature | Description | ETA |
|---------|-------------|-----|
| Cloud Desktop 2 | Remote learning workers on GPU instances | TBD |
| Deep model training | Actual neural network training for dictation & agent | TBD |
| Marketplace | Share, sell, and import community tunes | TBD |
| Concept drift detection | Auto-detect when a tune is stale and re-learn | TBD |
| Cross-device sync | Pro tier cloud sync of tunes across machines | TBD |
| A/B testing framework | Built-in statistical validation of tune effectiveness | TBD |

---

## 13. Quick Reference

### Tuner Registry

```python
from core.tune_hub import TuneBase

TuneBase.get_registered_tuners()
# {"reprompt": RePromptTuner, "dictation": DictationTuner, "agent": AgentTuner}
```

### Status Lifecycle

```
DRAFT → PENDING_VALIDATION → VALIDATED → DEPLOYED → ARCHIVED
   └────────────────────────────────────→ FAILED
```

### Injectable Keys Per Feature

| Feature | Keys Tune Hub Can Touch |
|---------|------------------------|
| `reprompt` | `persona_weights`, `tune_id`, `task_type` |
| `dictation` | `correction_map`, `tune_id`, `domain`, `auto_apply_threshold`, `text`, `applied_corrections` |
| `agent` | `recipe`, `tune_id`, `dsl_code`, `recipe_hint` |

### Complexity Triggers

| Tuner | LOW | MEDIUM | HIGH |
|-------|-----|--------|------|
| RePrompt | 0-1 domains mentioned | 2-3 domains | 4+ domains |
| Dictation | General vocabulary | Tech/finance/gaming | Medical/legal/scientific |
| Agent | 1-4 steps | 5-9 steps | 10+ steps or multi-app |

---

## 14. Summary

**Tune Hub makes Wiztant personal.** It learns from how you actually work and automatically optimizes the assistant's behavior across RePrompt, Dictation, and Agent modes.

| Aspect | Today (Phase 1) | Future (Phase 2+) |
|--------|-----------------|-------------------|
| **Learning** | Heuristic + lightweight GP | Full Bayesian optimization + neural training |
| **Storage** | Local SQLite | PostgreSQL + Redis + encrypted S3 |
| **Sync** | None | Real-time cross-device |
| **Community** | None | Marketplace with revenue sharing |
| **Intelligence** | Static task classification | Dynamic embedding-based matching |
| **Automation** | Simulated recipes | Real Desktop 2 execution |

**The more you use Wiztant, the better Tune Hub gets.** Every dictation correction, every RePrompt optimization, every agent task — it all feeds back into making the next interaction smoother, faster, and more "you."
