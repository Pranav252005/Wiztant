# Bistent Credit System — Complete Specification

## 1. Executive Summary

Bistent uses a **transparent, model-switchable credit system**. Every AI-powered operation costs credits. The credit cost is derived directly from the API cost of the model you choose — no hidden fees, no arbitrary numbers.

**Core principle:** You pay for what you use. Pick a cheaper model, pay fewer credits. Pick a premium model, pay more credits. The choice is always yours.

---

## 2. Plan Comparison

| Plan | Price | Monthly Credits | Best For |
|------|-------|----------------|----------|
| **Free** | $0 | 50 (one-time, non-renewing) | Trying Bistent |
| **Pro** | $20/month | 1,000 | Regular users |
| **Power** | $50/month | 5,000 | Power users, teams |

> **Key rule:** Credit costs are **identical across all plans**. A gemini-flash RePrompt costs 7 credits whether you're on Free, Pro, or Power. Only your monthly budget differs.

---

## 3. How Credits Work

### The Formula (Fully Transparent)

```
credits = ceil(API_cost_in_dollars × 5 / 0.006)
```

Where:
- `API_cost` = what we pay the AI provider for **your exact token usage** (not estimates)
- `5×` = platform margin multiplier
- `$0.006` = cost per credit (derived from Pro plan economics)
- `ceil(...)` = always round up to the next whole credit

**How actual tokens are measured:**
- **RePrompt:** After every optimization, we read the actual `prompt_tokens` and `completion_tokens` from the API response. You pay for exactly what you used — no more, no less.
- **TuneHub:** After each experiment iteration, actual tokens from both the feature call and the judge call are summed and charged.
- **Dictation:** Fixed at 1 credit (Whisper uses audio duration, not tokens).

**Example:** A short 1,500-token prompt to gemini-flash with a 500-token response costs **2 credits**. An 8,000-token prompt with a 4,000-token response costs **14 credits** for the same model. Same model, different usage = different cost.

**What this means:** 1 credit ≈ $0.0012 of API cost. You can verify any charge.

---

## 4. Feature Costs

### 4.1 Dictation — 1 Credit (Fixed)

Dictation uses **Groq Whisper Large v3 Turbo** at **$0.04 per hour** of audio.

| Average Utterance | Duration | API Cost | Credits |
|-------------------|----------|----------|---------|
| Short phrase | ~3 sec | ~$0.00003 | 1 |
| Normal sentence | ~5 sec | ~$0.00006 | 1 |
| Long paragraph | ~10 sec | ~$0.00011 | 1 |

> **Why so cheap?** Whisper is extremely fast and inexpensive. We pass the savings to you. A Pro user can dictate **1,000 times** before running out of credits.

---

### 4.2 RePrompt — 5 to 63 Credits (Model-Dependent)

RePrompt optimizes your prompts using the model you select.

**Typical usage:** ~3,000 input tokens (your prompt + instructions) + ~2,000 output tokens (optimized result)

#### Budget Models (Fast, Affordable)

| Model | Credits | Pro Uses (1,000 cr) | Speed |
|-------|---------|---------------------|-------|
| **qwen/qwen3.5-plus** | 5 | 200 | Fast |
| **google/gemini-3-flash** | 7 | 142 | Fast |
| **x-ai/grok-4.3** | 8 | 125 | Fast |
| **moonshotai/kimi-k2.6** | 8 | 125 | Fast |
| **openai/gpt-5.4-mini** | 10 | 100 | Fast |

> **Recommended default:** `google/gemini-3-flash` at **7 credits**. Best balance of speed, quality, and price.

#### Mid-Tier Models

| Model | Credits | Pro Uses (1,000 cr) | Speed |
|-------|---------|---------------------|-------|
| **anthropic/claude-haiku-4.5** | 11 | 90 | Fast |

#### Pro Models (Higher Quality, Higher Cost)

| Model | Credits | Pro Uses (1,000 cr) | Speed |
|-------|---------|---------------------|-------|
| **google/gemini-3.1-pro** | 25 | 40 | Medium |
| **openai/gpt-5.4** | 32 | 31 | Medium |
| **anthropic/claude-sonnet-4.6** | 33 | 30 | Medium |

#### Ultra Model (Best Quality, Premium Price)

| Model | Credits | Pro Uses (1,000 cr) | Speed |
|-------|---------|---------------------|-------|
| **openai/gpt-5.5** | 63 | 15 | Slow |

> **Pro tip:** For most prompt optimization tasks, `gemini-3-flash` (7 cr) delivers excellent results. Reserve `gpt-5.5` (63 cr) for mission-critical prompts where quality is paramount.

---

### 4.3 TuneHub — 27 to 2,040+ Credits (Model + Complexity Dependent)

TuneHub learns your personal patterns by running experiments. Each experiment iteration calls:
1. **Your target feature** (e.g., RePrompt) with your chosen model
2. **An LLM Judge** to score the results

#### Default Configuration (Recommended)

| Complexity | Iterations | Feature Model | Judge Model | Per Iteration | Total Credits |
|-----------|-----------|---------------|-------------|---------------|---------------|
| **LOW** | 3 | gemini-3-flash (7 cr) | claude-haiku-4.5 (2 cr) | 9 cr | **27** |
| **MEDIUM** | 10 | gemini-3-flash (7 cr) | claude-haiku-4.5 (2 cr) | 9 cr | **90** |
| **HIGH** | 30 | gemini-3-flash (7 cr) | claude-haiku-4.5 (2 cr) | 9 cr | **270** |

> **Recommended default:** LOW for quick tweaks, MEDIUM for thorough optimization, HIGH for deep personalization.

#### What You Get Per Complexity

| Complexity | Use Cases | Time | Typical Improvement |
|-----------|-----------|------|---------------------|
| **LOW** | "Make my emails more formal", "Add 5 tech terms to dictation" | 30s–2min | 10–20% |
| **MEDIUM** | "Optimize RePrompt for full-stack coding", "Build medical dictation vocab" | 2–8min | 20–40% |
| **HIGH** | "Deeply optimize Agent for Salesforce workflow", "Multi-persona technical writing" | 5–20min | 40–60% |

#### Premium Configuration Example

If you choose premium models for both feature and judge:

| Complexity | Feature Model | Judge Model | Total Credits |
|-----------|---------------|-------------|---------------|
| **LOW** | gpt-5.5 (63 cr) | claude-sonnet (5 cr) | **204** |
| **MEDIUM** | gpt-5.5 (63 cr) | claude-sonnet (5 cr) | **680** |
| **HIGH** | gpt-5.5 (63 cr) | claude-sonnet (5 cr) | **2,040** |

> A Pro user (1,000 credits) can afford ~1 MEDIUM tune with premium models. A Power user (5,000 credits) can afford ~7 MEDIUM or ~2 HIGH tunes.

#### Judge Model Options

| Judge Model | Credits | Best For |
|------------|---------|----------|
| qwen3.5-plus | 1 | Speed |
| gemini-3-flash | 1 | Speed |
| claude-haiku-4.5 | 2 | **Default — balanced** |
| gpt-5.4-mini | 2 | Balanced |
| gemini-3.1-pro | 4 | Higher accuracy |
| gpt-5.4 | 5 | Higher accuracy |
| claude-sonnet-4.6 | 5 | Higher accuracy |
| gpt-5.5 | 9 | Maximum accuracy |

---

## 5. Model Price Reference

All prices are per-million-tokens, what Bistent pays the AI provider:

| Model | Input $/M | Output $/M | Category |
|-------|-----------|-----------|----------|
| qwen/qwen3.5-plus-20260420 | $0.40 | $2.40 | Budget |
| google/gemini-3-flash-preview | $0.50 | $3.00 | Budget |
| x-ai/grok-4.3 | $1.25 | $2.50 | Budget |
| moonshotai/kimi-k2.6 | $0.75 | $3.50 | Budget |
| openai/gpt-5.4-mini | $0.75 | $4.50 | Budget |
| anthropic/claude-haiku-4.5 | $1.00 | $5.00 | Mid |
| google/gemini-3.1-pro-preview | $2.00 | $12.00 | Pro |
| openai/gpt-5.4 | $2.50 | $15.00 | Pro |
| anthropic/claude-sonnet-4.6 | $3.00 | $15.00 | Pro |
| openai/gpt-5.5 | $5.00 | $30.00 | Ultra |

---

## 6. Usage Scenarios

### Scenario A: Budget User (Free Tier, 50 credits)

| Day | Activity | Credits Used | Running Total |
|-----|----------|-------------|---------------|
| 1 | 30 dictations + 5 RePrompts (gemini-flash) + 1 TuneHub LOW | 30 + 35 + 27 = 92 | 92 |
| 2 | 30 dictations + 5 RePrompts (gemini-flash) | 30 + 35 = 65 | 157 |
| 3 | 20 dictations + 3 RePrompts (gemini-flash) | 20 + 21 = 41 | 198 |

> **Result:** Free tier lasts ~3 days of moderate use. Enough to fully evaluate Bistent.

---

### Scenario B: Typical Pro User (1,000 credits/month)

Uses **default models** (gemini-flash + claude-haiku judge).

| Day | Activity | Credits | Monthly Burn |
|-----|----------|---------|-------------|
| Mon | 50 dictations + 10 RePrompts + 1 TuneHub LOW | 50 + 70 + 27 = 147 | 147 |
| Tue | 50 dictations + 8 RePrompts | 50 + 56 = 106 | 253 |
| Wed | 50 dictations + 12 RePrompts + 1 TuneHub MEDIUM | 50 + 84 + 90 = 224 | 477 |
| Thu | 50 dictations + 5 RePrompts | 50 + 35 = 85 | 562 |
| Fri | 50 dictations + 10 RePrompts + 1 TuneHub LOW | 50 + 70 + 27 = 147 | 709 |

> **Result:** ~709 credits/week. Pro lasts ~1.4 weeks of heavy use or ~1 month of moderate use (3–4 days/week).

---

### Scenario C: Power User with Premium Models (5,000 credits/month)

Uses **gpt-5.5** for RePrompt and **claude-sonnet** for judge.

| Day | Activity | Credits | Monthly Burn |
|-----|----------|---------|-------------|
| Mon | 50 dictations + 5 RePrompts (gpt-5.5) + 1 TuneHub MEDIUM | 50 + 315 + 680 = 1,045 | 1,045 |
| Tue | 50 dictations + 3 RePrompts (gpt-5.5) | 50 + 189 = 239 | 1,284 |
| Wed | 50 dictations + 5 RePrompts (gpt-5.5) + 1 TuneHub LOW | 50 + 315 + 204 = 569 | 1,853 |

> **Result:** ~1,853 credits in 3 days. Power with premium models lasts ~8–10 heavy days or ~3–4 weeks of moderate premium use.

---

### Scenario D: Heavy Day (Burn Through 1,000 Credits)

| Activity | Count | Model | Credits | Subtotal |
|----------|-------|-------|---------|----------|
| Dictations | 300 | Whisper | 1 | 300 |
| RePrompts | 50 | gemini-3-flash | 7 | 350 |
| TuneHub LOW | 2 | defaults | 27 | 54 |
| TuneHub MEDIUM | 1 | defaults | 90 | 90 |
| **Total** | | | | **794** |

> Push harder with more RePrompts or a second MEDIUM tune to hit ~1,000.

---

## 7. FAQ

### Can I change models mid-month?
**Yes.** Change your default model anytime in Settings. The next operation uses the new model at its corresponding credit cost.

### What happens when I run out of credits?
You get a friendly notification with an option to **upgrade your plan** or **wait until your next billing cycle** when credits reset. No surprise charges.

### Do credits roll over?
**No.** Credits reset monthly on your billing anniversary. Use them or lose them — this encourages active usage.

### Why does the same model cost the same credits on Free and Power?
**Fairness.** We don't penalize Free users with higher per-operation costs or give Power users "cheaper" operations. Power users simply get a larger monthly budget.

### Can I buy extra credits without upgrading?
**Not in v1.** Future versions may offer credit top-ups. For now, upgrade to Power for 5× the credits.

### Why is dictation only 1 credit?
**Voice-first philosophy.** Whisper is extremely cheap ($0.04/hour). We pass the savings to you so you can dictate freely.

### How do I know how many credits an operation will cost?
- **RePrompt:** The button shows "Optimize — 7 credits" before you click.
- **TuneHub:** The Cost Estimate screen shows an itemized breakdown before you approve.
- **Dictation:** Always 1 credit.

### What if a TuneHub tune fails?
Credits spent during the learning process are **not refunded**. This is communicated clearly on the Cost Estimate screen before you approve. Failed tunes still consumed API resources.

### Can I use different models for different features?
**Yes.** Set a default model per feature in Settings. For example: gemini-flash for RePrompt, claude-sonnet for TuneHub judge.

---

## 8. Fairness Manifesto

1. **Transparent pricing** — You see the formula. You see the model prices. No black box.
2. **Equal per-operation costs** — Free, Pro, and Power users pay the same credits for the same model.
3. **Model choice = cost control** — You decide how fast to burn credits by picking your model.
4. **Voice is free-ish** — Dictation at 1 credit removes friction from the core product experience.
5. **No hidden fees** — What you see on the cost preview is exactly what you pay.

---

## 9. Technical Specification (For Developers)

### Credit Calculation API

```python
from core.credit_system import calculate_reprompt_credits, calculate_tunehub_credits

# RePrompt
cost = calculate_reprompt_credits(
    model="google/gemini-3-flash-preview",
    input_tokens=3000,
    output_tokens=2000
)  # Returns: 7

# TuneHub
cost = calculate_tunehub_credits(
    complexity="MEDIUM",
    feature_model="google/gemini-3-flash-preview",
    judge_model="anthropic/claude-haiku-4.5",
    feature_tokens=(3000, 2000),
    judge_tokens=(2000, 20)
)  # Returns: 90
```

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/credits/balance` | GET | Current credit balance |
| `/credits/history` | GET | Transaction history |
| `/credits/calculate` | POST | Preview credit cost for an operation |

### Supabase Schema

```sql
create table credits (
  user_id uuid primary key references auth.users,
  balance integer not null default 0,
  tier text not null default 'free',
  reset_at timestamptz
);

create table credit_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  feature text not null,
  model text,
  amount integer not null,
  balance_after integer not null,
  created_at timestamptz default now()
);
```

### Integration Points

| Module | Hook |
|--------|------|
| `core/voice.py` | Deduct 1 credit after successful transcription |
| `core/wizprompt.py` | Deduct `calculate_reprompt_credits()` before optimization |
| `core/tune_hub/orchestrator.py` | Calculate + deduct before `tuner.learn()` |
| `core/ws_bridge.py` | Broadcast `credits/update` after every deduction |

---

## 10. Changelog

| Version | Change |
|---------|--------|
| v1.0.0 | Migrated from tier-based limits (agent/vlm/uitars counts) to unified credit system |
| v1.0.0 | Introduced model-switchable credit pricing |
| v1.0.0 | Removed chat and tasks from credit tracking (not AI-powered in current architecture) |
| v1.0.0 | Added TuneHub credit costs based on complexity × model choice |

---

*Last updated: 2026-05-07*
*For questions: support@bistent.com*
