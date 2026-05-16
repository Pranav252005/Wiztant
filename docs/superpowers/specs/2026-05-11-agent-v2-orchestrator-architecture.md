# Wiztant Agent v2: The Orchestrator Architecture
## Not a Coder. The Brain That Uses Coders.

---

## 1. The Core Philosophy

**Wiztant Agent v2 does not write code.**

It does not open files and start typing `import React from 'react'`. It does not generate CSS. It does not run `git commit` on its own. It does not replace Windsurf, Cursor, Warp, or Lovable.

**Wiztant Agent v2 is the universal project manager that sits above all your tools and tells them what to do.**

Think of it like this:

| Role | Analogy | What It Actually Is |
|------|---------|---------------------|
| **Windsurf / Cursor** | The developer | Writes code, refactors, generates components |
| **Warp** | The DevOps engineer | Runs commands, deploys, manages infrastructure |
| **Lovable / v0** | The UI designer | Generates pages, layouts, visual components |
| **Wiztant Agent v2** | **The CTO / Tech Lead** | Plans architecture, breaks work into tasks, decides which tool does what, reviews output, asks for improvements, tracks progress, learns from mistakes |

The agent is **the human in the loop** — but for the AI tools, not for you.

---

## 2. What the Agent Actually Does

### 2.1 It Thinks Before Any Tool Touches Code

When you say:
> *"Build me a subscription dashboard with Stripe webhooks, MRR charts, and weekly email reports"*

The agent does **NOT** open Windsurf and start typing prompts.

It runs an **internal thinking loop**:

```
1. DECOMPOSE
   "What are the actual pieces here?"
   → Auth layer (who can see the dashboard?)
   → Data layer (what tables do we need? subscriptions? payments? users?)
   → API layer (Stripe webhook handlers, MRR calculation endpoint)
   → UI layer (dashboard page, charts component, settings page)
   → Integration layer (Stripe keys, webhook URLs, email service)

2. SEQUENCE
   "What order must these happen in?"
   → Schema FIRST (can't build API without knowing data shape)
   → Auth SECOND (can't protect routes without auth)
   → API THIRD (can't render data without endpoints)
   → UI FOURTH (can't style what doesn't exist)
   → Deploy LAST

3. TOOL MATCH
   "Which tool is best for each piece?"
   → Schema design → Cursor (best for structured code + types)
   → Auth setup → Windsurf (great for Next.js patterns)
   → API routes → Cursor (fast iteration)
   → UI/charts → Lovable (visual generation)
   → Commands/deployment → Warp (terminal control)

4. RISK ASSESS
   "What could go wrong?"
   → Stripe webhooks need idempotency keys
   → MRR calculation is sensitive — must handle prorations
   → Email reports need cron scheduling
   → All of this needs env vars — don't leak keys

5. PROMPT CRAFT
   "What exact prompt should I give each tool?"
   → Not: "build a dashboard"
   → Instead: "Create a Next.js API route at /api/webhooks/stripe that handles invoice.payment_succeeded events. Use idempotency checks via a processed_events table. Return 200 on success."
```

### 2.2 It Stages Work in Tools — But Never Auto-Executes

The agent **opens** the right tool, **types** the perfect prompt, **stops**.

| Tool | What Agent Does | What Tool Does | What You Do |
|------|-----------------|----------------|-------------|
| **Windsurf** | Opens Cascade panel, types full contextual prompt with file references, file content, and exact requirements | Generates/refactors code | Review, edit if needed, hit Accept |
| **Cursor** | Opens Composer, drafts prompt with @file references, schema context, and type constraints | Generates code with full project awareness | Review, edit, hit Accept |
| **Warp** | Focuses terminal, types exact command with env vars, flags, and safety checks | Executes command | Review, edit, hit Enter |
| **Lovable** | Navigates to project, fills generation prompt with feature spec + design constraints | Generates UI/page | Review, tweak, hit Publish |

**The agent never hits "Accept", "Enter", or "Publish" on its own.**
You are the final gate. But the agent has done all the thinking, planning, and prompt engineering so that what you see is 90% ready.

### 2.3 It Verifies Before Moving On

After a tool finishes, the agent **checks the work** before advancing to the next subphase:

```
Subphase complete: "Draft Stripe webhook handler in Cursor"

VERIFICATION:
✓ Does src/app/api/webhooks/stripe/route.ts exist?
✓ Does it import Stripe SDK?
✓ Does it handle invoice.payment_succeeded?
✓ Does it have idempotency check?
✓ Run: npx tsc --noEmit → passes?
✓ Run: curl -X POST http://localhost:3000/api/webhooks/stripe → 200?

IF ANY FAIL:
  → Agent reads error
  → Generates "fix" prompt for the same tool
  → Stages fix prompt
  → You review and accept
```

### 2.4 It Learns Your Preferences

After every project, the agent updates its memory:

```json
{
  "projects": {
    "proj_saas_001": {
      "patterns": [
        {"type": "validation", "value": "zod", "confidence": 0.98},
        {"type": "fetching", "value": "tanstack_query", "confidence": 0.91},
        {"type": "styling", "value": "tailwind", "confidence": 0.99}
      ],
      "tool_preferences": {
        "api_design": "cursor",
        "ui_generation": "lovable",
        "deployment": "warp"
      },
      "mistakes_learned": [
        "User prefers explicit error types over throwing",
        "User likes server actions over API routes for internal ops"
      ]
    }
  }
}
```

Next project:
> *"Build a blog with comments"*

Agent thinks:
> *"Last time they preferred Zod + TanStack Query + Tailwind. They like Cursor for APIs and Lovable for UI. They prefer server actions. I'll use those defaults unless the project screams otherwise."*

### 2.5 It Fails Over Gracefully

Cursor out of fast requests? The agent pauses and asks:

> *"Cursor daily limit reached. I can resume with:
> - [Windsurf] — same context, same prompt
> - [Claude Code CLI] — terminal-based, no limits
> - [Pause until tomorrow] — I'll create a reminder task"*

If you pick Windsurf, the agent:
1. Opens the same project in Windsurf
2. Loads the same file context
3. Drafts the same prompt in Cascade
4. Continues from the exact subphase where it stopped

No context lost. No "where were we?" moments.

---

## 3. The Execution Loop (Step by Step)

### Step 1: User Trigger

You hit **F9×2** (Agent Mode) or click **"New Build"** in the overlay.

You speak or type:
> *"I want a SaaS dashboard with Stripe billing, team invites, and a kanban board"*

### Step 2: The Agent Thinks (Internal)

The agent runs its **Master Planner**:

```
INPUT: "SaaS dashboard with Stripe billing, team invites, kanban board"

DETECT STACK:
→ package.json exists → Next.js 14, TypeScript, Tailwind, Prisma
→ supabase/config.toml exists → Supabase backend

DECOMPOSE INTO 5 LAYERS:

L1: Data & Schema
├── P1.1: User & Team schema
│   ├── S1.1.1: Read existing schema (auto)
│   ├── S1.1.2: Add teams table with invite_token (Cursor)
│   └── S1.1.3: Add team_memberships junction table (Cursor)
├── P1.2: Subscription schema
│   ├── S1.2.1: Add subscriptions table with stripe_customer_id (Cursor)
│   └── S1.2.2: Add invoices table for history (Cursor)

L2: Auth & Security
├── P2.1: Team invite auth
│   ├── S2.1.1: Add invite acceptance flow (Windsurf)
│   └── S2.1.2: Protect team-scoped routes (Windsurf)

L3: API & Business Logic
├── P3.1: Stripe integration
│   ├── S3.1.1: Create webhook handler (Cursor)
│   ├── S3.1.2: Create checkout session endpoint (Cursor)
│   └── S3.1.3: Create subscription status endpoint (Cursor)
├── P3.2: Team management
│   ├── S3.2.1: Create invite generation endpoint (Cursor)
│   └── S3.2.2: Create member role update endpoint (Cursor)
├── P3.3: Kanban API
│   ├── S3.3.1: Create board CRUD endpoints (Cursor)
│   └── S3.3.2: Create card CRUD endpoints (Cursor)

L4: UI & Frontend
├── P4.1: Dashboard shell
│   ├── S4.1.1: Generate dashboard layout with sidebar (Lovable)
│   └── S4.1.2: Add team switcher component (Cursor)
├── P4.2: Billing page
│   ├── S4.2.1: Generate subscription management UI (Lovable)
│   └── S4.2.2: Add invoice history table (Cursor)
├── P4.3: Kanban board
│   ├── S4.3.1: Generate kanban board UI (Lovable)
│   └── S4.3.2: Add drag-and-drop interactions (Cursor)

L5: Integration & Deploy
├── P5.1: Stripe webhooks
│   ├── S5.1.1: Configure Stripe webhook endpoint in dashboard (Browser)
│   └── S5.1.2: Add webhook secret to .env (manual)
├── P5.2: Deployment
│   ├── S5.2.1: Run database migrations (Warp)
│   └── S5.2.2: Deploy to Vercel (Warp)
```

**Total: 5 layers, 8 phases, 20 subphases**

### Step 3: The Agent Presents the Plan

The overlay shows:

```
┌─ Project: SaaS Dashboard ─────────────────────────┐
│                                                   │
│  L1  Data & Schema        [PENDING]  4 subphases │
│  L2  Auth & Security      [PENDING]  2 subphases │
│  L3  API & Business Logic [PENDING]  7 subphases │
│  L4  UI & Frontend        [PENDING]  6 subphases │
│  L5  Integration & Deploy [PENDING]  2 subphases │
│                                                   │
│  Estimated time: 3-4 hours with human gates       │
│  Tools: Cursor (12 subphases)                     │
│         Windsurf (2 subphases)                    │
│         Lovable (3 subphases)                     │
│         Warp (2 subphases)                        │
│                                                   │
│  [Approve All]  [Step-by-Step]  [Edit Plan]       │
└───────────────────────────────────────────────────┘
```

You can:
- **Approve All** — agent runs sequentially, pausing only for verification failures
- **Step-by-Step** — agent pauses after every subphase for your review
- **Edit Plan** — drag to reorder, remove phases, or change tool assignments

### Step 4: The Agent Executes One Subphase

You hit **"Approve All"**.

The agent starts **Subphase 1.1.1**:
```
TOOL: auto (no external tool needed)
ACTION: Read existing Prisma schema
RESULT: Found schema with User model. No Team or Subscription models.
VERIFICATION: ✓ (manual/auto — just information gathering)
```

**Subphase 1.1.2**:
```
TOOL: Cursor
ACTION: Open Cursor Composer
        Draft prompt:
        "@prisma/schema.prisma Add a Team model with:
        - id: cuid
        - name: string
        - slug: string (unique)
        - invite_token: string (unique, nullable)
        - owner_id: string → User relation
        - created_at, updated_at timestamps
        Also add a team_id field to the existing User model.
        Use Prisma conventions. Return the full updated schema."
STATUS: STAGED (prompt typed, cursor blinking — waiting for user to hit Enter in Cursor)
```

**You see Cursor open with the prompt ready.** You review it. Looks good. You hit Enter.

Cursor generates the code. You hit Accept.

**Subphase 1.1.2 verification:**
```
✓ schema.prisma modified
✓ Team model exists with correct fields
✓ User model has team_id relation
✓ npx prisma validate → passes
✓ npx tsc --noEmit → passes
```

Agent auto-commits:
```
git commit -m "wip(agent): L1-P1-S2 — Add Team model to Prisma schema"
```

### Step 5: The Agent Continues

It moves to **Subphase 1.1.3**, then **P1.2**, then **L2**, etc.

After every layer completes, it stops:

```
┌─ Layer Complete ──────────────────────────────────┐
│                                                   │
│  ✅ L1 Data & Schema complete                     │
│                                                   │
│  Files modified:                                  │
│  - prisma/schema.prisma                           │
│  - src/types/team.ts (new)                        │
│                                                   │
│  Git checkpoint: wip(agent): L1-P1 — Team schema  │
│                                                   │
│  Approve L2 (Auth & Security)?                    │
│                                                   │
│  [Yes, Continue]  [Pause]  [Edit Next Layer]      │
└───────────────────────────────────────────────────┘
```

This is the **Layer Gate** — the agent never rushes ahead. You approve each layer.

---

## 4. The "Thinking" Layer

This is what makes the agent different from AutoGPT or CrewAI.

### 4.1 Pre-Prompt Optimization

Before sending ANY prompt to ANY tool, the agent runs it through **WizPrompt** (its own RePrompt feature):

```
RAW PROMPT (agent generated):
"Build a Stripe webhook handler"

OPTIMIZED PROMPT (after WizPrompt):
"Create a Next.js API route at src/app/api/webhooks/stripe/route.ts
that handles Stripe webhook events. Requirements:
- Verify webhook signature using STRIPE_WEBHOOK_SECRET
- Handle invoice.payment_succeeded and invoice.payment_failed
- Idempotency: check processed_events table before processing
- Return 200 for processed events, 400 for invalid signatures
- Use Zod to validate event payload structure
- Log errors to console with event id
- Include comprehensive error handling

Context:
- Project uses Next.js 14 App Router
- Database: Prisma + PostgreSQL
- Existing schema: User, Team models
- Stripe SDK version: ^14.0.0"
```

The agent literally uses its own product to think better.

### 4.2 Mid-Build Adaptation

You can interrupt anytime:

> *"Actually, use Resend for emails instead of SendGrid"*

The agent:
1. Transcribes your voice (F9×1 dictation)
2. Updates the master plan
3. Changes tool assignments if needed
4. Regenerates prompts for affected subphases
5. Continues from where it left off

No "start over". No lost work.

### 4.3 Post-Build Reflection

After the project completes, the agent writes a reflection:

```
PROJECT RETROSPECTIVE: proj_saas_001

What went well:
- Layer 1 (Schema) completed in 15 minutes — no errors
- Cursor handled all API routes efficiently
- Lovable generated clean dashboard UI

What could be better:
- Subphase 3.1.1 (Stripe webhook) needed 2 retries because
  the first prompt didn't mention idempotency explicitly
  → UPDATED TEMPLATE: Always include idempotency in webhook prompts
- User manually switched from SendGrid to Resend mid-build
  → UPDATED PREFERENCE: Default email provider = Resend

Patterns learned:
- User prefers Zod over Yup (confidence: 0.98)
- User likes server actions for internal ops (confidence: 0.87)
- User wants explicit error types, not throwing (confidence: 0.94)
```

This feeds back into the **TuneHub** persona weights. Next project starts smarter.

---

## 5. Safety & Trust

### The "Press Enter" Philosophy

The agent **never** auto-executes. It always stages and waits.

| Action | Who Does It |
|--------|-------------|
| Plan generation | Agent |
| Prompt drafting | Agent |
| Code generation | Cursor / Windsurf / Lovable |
| Command execution | Warp |
| Hit "Accept" / "Enter" | **YOU** |
| Approve next layer | **YOU** |
| Deploy to production | **YOU** |

The agent is transparent. You see every prompt before it goes to a tool. You see every command before it runs. You see the plan before execution starts.

### Guardrails (Hard Rules)

1. **Never commits to `main`** — always works on `wiztant-agent/{project_id}` branch
2. **Never writes real secrets** — reads `.env.example`, suggests vars in `.env.wiztant`
3. **Destructive commands flagged red** — `git push`, `rm -rf`, `vercel --prod` need extra confirmation
4. **Max $10 API spend per project** — approaching limit triggers pause
5. **Max 15 new files per phase** — forces decomposition
6. **Sandboxed paths** — can only touch files within the project directory

---

## 6. The Memory Architecture

### Hermes Ledger (`memory/agent_index.json`)

One living file. Append-only.

```json
{
  "version": "1",
  "projects": {
    "proj_saas_001": {
      "path": "~/Projects/saas-dashboard",
      "stack": ["nextjs", "typescript", "tailwind", "prisma", "supabase", "stripe"],
      "patterns": [
        {"type": "validation", "value": "zod", "confidence": 0.98},
        {"type": "state_management", "value": "server_actions", "confidence": 0.87},
        {"type": "error_handling", "value": "explicit_types", "confidence": 0.94}
      ],
      "tool_preferences": {
        "schema_design": "cursor",
        "api_generation": "cursor",
        "ui_generation": "lovable",
        "deployment": "warp"
      },
      "mistakes": [
        "webhook_prompt_v1_missing_idempotency"
      ],
      "last_run_at": "2026-05-11T12:00:00Z"
    }
  }
}
```

### Per-Run Directory (`memory/agent_runs/{run_id}/`)

```
memory/agent_runs/run_proj_saas_001/
├── master_plan.json       → The canonical blueprint
├── phase_manifest.json    → Current execution state
├── execution.json         → Step-by-step log with timestamps
├── artifacts.json         → Files created/modified per subphase
└── paused_state.json      → Only exists if interrupted
```

---

## 7. How It Uses Existing Wiztant Features

| Feature | Agent v2 Usage |
|---------|----------------|
| **F9×2 Agent Mode** | Triggers the Phase Engine. Opens Project Builder overlay. |
| **F9×1 Dictation** | Mid-build voice commands: *"Use bar charts not line charts"* → plan updated |
| **Ctrl+Shift+Space RePrompt** | Optimizes every prompt before sending to tools |
| **Task System** | Paused projects become Tasks with reminders |
| **TuneHub** | Post-build pattern extraction updates persona weights |
| **Overlay UI** | Project Builder view with phase timeline and approval gates |
| **Pill** | Shows active phase: "L3-P1: API Layer" with tool icon |
| **WebSocket Bridge** | Streams events to overlay in real-time |

---

## 8. Summary: The Agent's Identity

```
┌─────────────────────────────────────────────────────────────┐
│                    WIZTANT AGENT v2                         │
│                                                             │
│   NOT A CODER                                               │
│   ├── Does not write code                                   │
│   ├── Does not run commands without staging                 │
│   ├── Does not replace your tools                           │
│                                                             │
│   IS AN ORCHESTRATOR                                        │
│   ├── Plans architecture (5 layers)                         │
│   ├── Breaks work into atomic subphases                     │
│   ├── Chooses the right tool for each job                   │
│   ├── Crafts optimized prompts for each tool                │
│   ├── Verifies output before advancing                      │
│   ├── Learns from every project                             │
│   ├── Fails over when tools hit limits                      │
│   ├── Keeps you in control (you press Enter)                │
│                                                             │
│   IS THE HUMAN IN THE LOOP — FOR THE AI TOOLS               │
│   ├── Cursor/Windsurf are the hands                         │
│   ├── Warp is the feet                                      │
│   ├── Lovable is the eyes                                   │
│   └── Wiztant Agent v2 is the brain                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. What Needs to Change From Current Implementation

The current Month 1 foundation has the **structure** right (models, state machine, memory, endpoints) but the **behavior** needs to be reoriented:

### Current (Wrong)
- `cursor_adapter.py` is a skeleton that returns `{"staged": True}`
- `phase_engine.py` auto-advances without actually opening tools
- The agent conceptually "does" the work internally

### Required (Right)
- `cursor_adapter.py` **actually focuses Cursor window** and **types the prompt** via OS automation
- `warp_adapter.py` **actually focuses Warp terminal** and **types the command**
- `phase_engine.py` **waits for the tool to finish** (detects when you hit Accept in Cursor)
- The agent **orchestrates** — it opens tools, stages work, waits for human gate, verifies, continues

### The Missing Pieces

1. **OS-level tool integration** (Month 2/3 scope)
   - Window detection: Is Cursor open? Which project?
   - Keystroke injection: Type prompt into Composer/Cascade
   - Clipboard staging: For long prompts
   - Completion detection: How does the agent know you hit Accept?

2. **Vision loop for tool monitoring**
   - The agent takes screenshots of the tool window
   - Uses UI-TARS (vision model) to read UI state
   - "Cursor is showing generated code → User hasn't accepted yet → WAIT"
   - "Warp shows command completed → Proceed to verification"

3. **Context extraction**
   - Before prompting Cursor, the agent reads relevant files
   - Includes file content in the prompt as @references
   - "Here's the current schema, here's the types, here's what we need"

4. **Self-optimization loop**
   - Before every prompt: run through WizPrompt
   - After every failure: generate reflection, update templates
   - After every project: update TuneHub weights

---

**This document is the north star.** If this architecture matches your vision, the next step is to implement the **behavior layer** — making the agent actually open tools, stage prompts, monitor completion, and orchestrate across your stack.

**Tell me what's wrong, what's missing, or what needs to change.**
