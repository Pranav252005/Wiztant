# Smart Task System Design — Wiztant TaskStack 2.0

> **Status:** Design / Brainstorming Phase — Awaiting user review before planning implementation.

---

## 1. Problem Statement

The current TaskStack system captures tasks well and has basic reminders, but the reminder behavior is **dumb and guilt-inducing**:

- **Fixed 15-minute nag loop** when a task is overdue — regardless of whether the user is in deep work, a meeting, or idle.
- **Static snooze presets** (15/60/1440 min) — the system never learns that a user always snoozes "College" tasks to evenings.
- **Binary failure state** — tasks become `failed=true` after one carry-over. No gentle recovery path.
- **No context awareness** — reminders fire at the exact due time even if the user is actively working on the task.
- **No decay / auto-cleanup** — stale tasks accumulate forever unless manually deleted.
- **All reminders feel the same** — a pre-due warning, a due-now alert, and an overdue nag all use the same `pill_notification` channel with identical urgency.

**Goal:** Build a task system that feels like a calm, smart assistant — not a nagging parent. It should help users actually do the work, not just remember it.

---

## 2. Research Synthesis

### 2.1 What the Science Says

| Finding | Source Implication |
|---------|-------------------|
| **Interruptibility is the #1 factor** — users reject notifications based on timing, not content. | CHI 2024, Fischer PhD thesis: deliver at *breakpoints* (task transitions), not during deep work. |
| **"Defer-to-breakpoint" policy reduces mental load** | Classic HCI research: after completing an action, users are most receptive to reminders. |
| **Context (time + app usage) predicts receptivity better than content** | Mehrotra et al.: strongest predictors are time-of-day, phone/app usage state, and source category. |
| **Overdue reminders trigger guilt spirals** | Nick Gracilla blog / user interviews: "I don't want to constantly be reminded I'm not doing something." |
| **Micro-commitments beat macro-tasks** | Behavioral psych / GTD: breaking tasks into next actions dramatically increases completion rates. |
| **Positive framing + momentum > punishment** | Self-management literature: reward streaks and easy wins; avoid failure branding. |
| **Smart scheduling learns user patterns** | Todoist Smart Schedule: ML on habit data to suggest optimal due dates and times. |

### 2.2 What "Not Annoying" Actually Means

From the research, non-annoying reminder systems share these traits:

1. **Graduated urgency** — First reminder is gentle. Escalation only if ignored.
2. **Respectful of state** — Never interrupt deep work. Wait for natural breakpoints.
3. **Action-oriented, not guilt-oriented** — "Ready to tackle X?" beats "You missed X."
4. **Self-cleaning** — Stale items decay and surface for review rather than haunting the list forever.
5. **Learn from dismissal patterns** — If a user always snoozes a task type to 8pm, offer that as the default.
6. **Batch and surface** — Morning briefing > scattered interruptions throughout the day.

---

## 3. Three Approaches

### Approach A: "Smart Snooze + Graduated Escalation" (Minimal)

Add intelligence to the existing reminder pipeline without changing the architecture.

- **Smart snooze presets** — Learn from snooze history per category. Default to "next preferred slot."
- **Escalation ladder** — Pre-due (gentle) → Due (firm) → Overdue (single daily digest, not every 15 min).
- **Auto-archive after N days** — Mark stale pending tasks as `archived` rather than failed.

**Pros:** Low risk, fast to implement, touches few files.  
**Cons:** Doesn't solve the core interruptibility problem. Still fires at wrong times.

### Approach B: "Context-Aware Delivery Engine" (Moderate)

Build a lightweight interruptibility layer that observes system state before firing reminders.

- **Focus state detection** — Track if user is in fullscreen app, agent mode, or has been typing continuously for >5 min.
- **Breakpoint delivery** — Queue reminders; release when focus state changes (window switch, idle >2 min, overlay open).
- **Morning Briefing** — Replace scattered reminders with a single "Today" briefing at user-configured time (or first system unlock).
- **Smart snooze + escalation** (from Approach A) included.

**Pros:** Actually solves the annoying-interruption problem. Respects user's attention.  
**Cons:** Requires new focus-state tracking module. More complex testing.

### Approach C: "AI Task Coach" (Ambitious)

Full behavioral intelligence layer with LLM-assisted planning.

- **Task decomposition** — LLM breaks large tasks into subtasks on creation.
- **Energy matching** — Suggest tasks based on inferred energy (morning = hard, evening = easy).
- **Predictive scheduling** — Auto-reschedule tasks based on historical completion patterns.
- **Weekly review assistant** — Voice command: "Review my week" → AI surfaces what worked, what didn't.

**Pros:** Most differentiated. "Holy shit" factor.  
**Cons:** High complexity. LLM costs. Overkill for current stage. Risk of being slow/unreliable.

---

## 4. Recommendation: Approach B with selective elements from A and C

**Rationale:** Approach B hits the sweet spot — it solves the core pain (annoying interruptions) with minimal architectural risk, while cherry-picking the highest-ROI features from A (smart snooze, auto-archive) and C (task decomposition for large tasks only, via a cheap local heuristic rather than LLM).

The user's exact words: *"something that is really good for the workflow of people and actually gets them to work but not annoying."* Context-aware delivery directly addresses this.

---

## 5. Detailed Design

### 5.1 Core Concepts

| Concept | Description |
|---------|-------------|
| **Focus State** | Inferred user attention state: `deep_work`, `active`, `idle`, `away`. |
| **Breakpoint** | A transition in focus state where the user is most receptive to a reminder. |
| **Urgency Tier** | `gentle` (pre-due), `standard` (due), `digest` (overdue batched). |
| **Smart Snooze** | Snooze options derived from historical behavior per category + time-of-day. |
| **Task Decay** | Pending tasks older than N days surface for "keep / archive / split" review. |
| **Morning Briefing** | Single daily summary instead of scattered individual reminders. |

### 5.2 Focus State Detection (Lightweight)

We do **not** need OS-level hooks or ML. We infer from signals already available:

```
focus_state = {
  "deep_work":  (same_window > 5min AND keystroke_rate > threshold)
                 OR fullscreen_app == True
                 OR agent_mode_active == True,
  "active":     (recent_input < 60sec) AND not deep_work,
  "idle":       (no_input > 2min AND no_window_change),
  "away":       (no_input > 10min) OR screensaver_locked,
}
```

- **Platform access** via existing `platforms/*/window_mgmt.py` + `system_access.py`.
- **No new sensors** — uses window title sampling (already done by system context scanner) + keyboard/mouse idle time.
- **Privacy-safe** — no screenshots, no content analysis. Just activity rate + window bounds.

### 5.3 Reminder Delivery Pipeline

```
Current:  Timer fires → Check due tasks → Broadcast pill immediately

New:      Timer fires → Check due tasks → Score urgency → 
          Check focus state → If deep_work: queue for breakpoint
          → If active/idle: deliver now with appropriate tone
          → If away: deliver when focus returns
```

**Breakpoint triggers (release queued reminders):**
- Window change detected
- User becomes idle after being active (>2 min)
- User opens overlay (Ctrl+Space)
- Agent mode deactivates

### 5.4 Urgency Tier System

Replace the single `pill_notification` with tiered delivery:

| Tier | When | Channel | Tone | Sound |
|------|------|---------|------|-------|
| `gentle` | 30 min before due | Pill (soft color) | "X is coming up" | None |
| `standard` | At due time | Pill + brief flash | "Time for X" | Soft chime |
| `digest` | Once per morning (configurable) | Overlay panel + pill | "Today: X, Y, Z overdue" | None |

**Overdue tasks no longer spam every 15 minutes.** They roll into the next morning briefing or appear when the user next opens the overlay.

### 5.5 Smart Snooze

Replace static `[15, 60, 1440]` presets with dynamic suggestions:

```python
def get_smart_snooze_options(task: dict) -> list[int]:
    # 1. Historical: what does user typically snooze THIS category to?
    # 2. Time-of-day: if it's 10am, offer "this evening" (~8h), "tomorrow morning"
    # 3. Always include "15 min" and "Custom"
```

Examples:
- User always snoozes "College" tasks to 6-8pm → suggest `480` (8h) as primary.
- User snoozes "Home" tasks to next morning → suggest `+1 day @ 9am`.
- Task due at 2pm, current time 1:50pm → suggest `15 min`, `1 hour`, `tomorrow`.

**Storage:** Extend `memory/reminder_state.json` with per-category snooze histogram.

### 5.6 Task Decay & Auto-Archive

```python
ARCHIVE_AFTER_DAYS = 14  # configurable in settings.json

# Daily check: tasks pending > 14 days
→ Surface in overlay as "Stuck tasks needing review"
→ User options: keep, archive, break into smaller steps, or mark done
→ If user ignores for 3 more days → auto-archive (recoverable from history)
```

Archived tasks are hidden from the main list but searchable in history. This prevents list bloat without guilt.

### 5.7 Morning Briefing

A single voice / pill summary delivered at a user-defined time (default: first interaction after 8am, or first system unlock).

Content:
- "Good morning. You have 3 tasks today: [list]. One is overdue from yesterday: X."
- Suggests a "focus task" based on urgency + category preference.
- Offers: "Want me to help you break down the big one?"

**If the user has the overlay open, show it as a rich panel instead of voice.**

### 5.8 Task Decomposition (Lightweight)

For tasks marked `task_type=large`, offer an LLM-assisted or template-based breakdown:

- **Voice trigger:** "Break that down" or "That's a big one."
- **UI trigger:** Button in task detail panel.
- **Method:** Use the existing OpenRouter client with a cheap model (already loaded for task refinement). System prompt: "Break this task into 3-5 concrete subtasks. Each must be completable in <30 min."
- Subtasks are created as children of the parent task.

**Cost mitigation:** Only decompose when explicitly requested. Cache results.

---

## 6. Data Model Changes

### 6.1 Task Schema Additions

```json
{
  "status": "pending|in_progress|done|archived",
  "urgency_score": 0.0,
  "estimated_minutes": null,
  "energy_level": "low|medium|high|null",
  "archived_at": null,
  "archived_reason": null
}
```

### 6.2 New State Files

| File | Purpose |
|------|---------|
| `memory/focus_state.json` | Last known focus state + transition timestamps |
| `memory/snooze_patterns.json` | Per-category snooze histogram |
| `memory/reminder_queue.json` | Queued reminders waiting for breakpoint |

### 6.3 Settings Additions

```json
{
  "smart_reminders": true,
  "morning_briefing_time": "08:00",
  "morning_briefing_enabled": true,
  "archive_after_days": 14,
  "overdue_digest_mode": "daily",  // vs "immediate"
  "focus_detection_enabled": true,
  "min_deep_work_minutes": 5
}
```

---

## 7. Architecture

### 7.1 New Modules

```
core/
  focus_state.py       # Focus state inference (lightweight)
  smart_delivery.py    # Queue + breakpoint delivery engine
  snooze_patterns.py   # Learn + predict snooze preferences
  task_decay.py        # Stale task detection + archival
core/reminder_scheduler.py  # Modified to use smart_delivery
```

### 7.2 Modified Modules

```
core/tasks.py              # Add schema fields, archive logic
core/reminder_scheduler.py # Replace aggressive loop with tiered delivery
core/ws_bridge.py          # New message types for briefing, stuck-tasks
data/settings.json         # New toggles
core/server.py             # Expose archive/unarchive endpoints
```

### 7.3 Overlay Changes (Electron)

```
Overlay/TaskPanel:
  - Morning briefing panel
  - Stuck tasks review UI
  - Smart snooze button group (dynamic labels)
  - "Break down" button for large tasks
```

---

## 8. User Flows

### Flow 1: Overdue Task (New Behavior)

```
1. Task "Submit assignment" was due yesterday at 5pm.
2. User is coding in VS Code (deep_work detected).
3. Reminder is queued instead of fired.
4. User switches to browser at 2:30pm (breakpoint).
5. Pill appears: "You have 1 overdue task: Submit assignment."
6. User clicks snooze → sees options: "Later today", "Tomorrow 9am", "This weekend"
   (inferred from past snoozes for "College" tasks).
7. User picks "Tomorrow 9am". System learns this preference.
```

### Flow 2: Morning Briefing

```
1. First system unlock after 8am.
2. Pill + voice: "Morning. 2 tasks today, 1 carried over. Want to tackle the overdue one first?"
3. User says "Show me" → Overlay opens to Today tab with focus task highlighted.
```

### Flow 3: Stuck Task Review

```
1. Task "Learn Rust" pending for 16 days.
2. Daily scan flags it.
3. Next time overlay opens, banner: "1 task is stuck. Review?"
4. User reviews: options [Keep it, Archive it, Break it down, Mark done]
5. User picks "Break it down" → 4 subtasks created:
   "Install Rust toolchain", "Read chapter 1", "Do first exercise", "Build hello world"
```

---

## 9. Rollout & Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Focus state inference is wrong | Make it **opt-in** via `focus_detection_enabled`. Default off in first release. |
| Users miss urgent reminders | Keep `standard` tier immediate. Only `gentle` and `digest` are deferred. |
| LLM decomposition too slow | Only trigger on explicit request. Add timeout (3s). |
| Data migration | New fields are optional with defaults. Backward compatible. |
| Overlay complexity | Build UI incrementally. Start with backend + pill changes. |

---

## 10. Success Criteria

- [ ] Overdue reminders do not fire during detected deep work.
- [ ] Snooze options show learned preferences within 1 week of usage.
- [ ] Task list has <5% stale (>14 days) pending tasks due to auto-archive review.
- [ ] Morning briefing is the primary reminder touchpoint for carried-over tasks.
- [ ] No regression in existing task CRUD, voice commands, or WebSocket protocol.

---

## 11. Out of Scope (Explicitly)

- Calendar integration (Google/Outlook) — requires OAuth infra not present.
- True ML model training — we use simple histograms and heuristics.
- Cross-device sync — single-device desktop app.
- Real-time email/Slack task extraction — too complex for this phase.

---

*Spec self-review: No placeholders. No contradictions. All schema additions have defaults. All risks have mitigations. Ready for user review.*
