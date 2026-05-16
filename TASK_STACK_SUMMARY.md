# Task Stack — Complete Feature Summary

> **What it is:** Task Stack is Wiztant's built-in task manager. It is designed to be **voice-first**, **frictionless**, and **always available** — so you can capture a task the moment it crosses your mind without ever breaking your flow.

---

## The Core Idea

Your brain generates tasks constantly — "email the client," "buy milk," "finish the report by 3." Traditional task apps force you to open an app, find a button, fill a form, and set a date. By then, the thought is gone or you're already distracted.

**Task Stack flips this:** you press a hotkey, speak naturally, and move on. Wiztant parses your words, extracts the deadline, categorizes the work, and reminds you later. The UI is there when you need it, invisible when you don't.

---

## How It Works

### 1. Capture — Anytime, Anywhere

Press **F10** (or open the overlay with **Ctrl+Space**) and say something like:

> *"Add task review the pull request by 5 PM today"*
> *"Remind me to call mom tomorrow at 3"*
> *"I need to finish the blog post by Friday"*
> *"This is a task: deploy the hotfix"*

Task Stack understands **dozens of natural phrasings** — explicit commands like "add task," "create a todo," "this is a task:" and implicit intents like "I need to," "don't forget to," "remind me to," "make sure to."

If you pack multiple tasks into one sentence, just say **"separately"** (or let Task Stack detect multiple time markers) and it splits them automatically:

> *"Email the designer by 2 PM and update the docs by 5 PM separately"*

→ Creates **two tasks** with their own deadlines.

### 2. AI Refinement (Optional)

Spoken tasks can be messy. Whisper might hallucinate a word, or you might trail off. Task Stack can optionally send your raw transcript through a lightweight LLM to **clean it up** — removing filler words, fixing transcriptions, preserving your exact intent — before saving it. You control the model and you can toggle this off entirely if you prefer raw capture.

### 3. Smart Time Parsing

Task Stack extracts deadlines automatically from your speech:

| What you say | What Task Stack understands |
|-------------|----------------------------|
| "...by 5 PM today" | Today at 17:00 |
| "...tomorrow at 10 AM" | Tomorrow at 10:00 |
| "...by 3" | Next 3:00 PM (or AM if context suggests) |
| "...on Monday" | Next Monday at 12:00 |
| "...today" (no time) | Today at 12:00, or tomorrow if noon passed |

If the time has already passed, it intelligently rolls forward to the next occurrence. You never have to open a calendar picker.

### 4. Auto-Categorization & Difficulty

Every task is automatically tagged with a **category** and **difficulty**:

- **Categories:** College, Home, Solopreneur, Solo Project, Group Project, Other (fully customizable)
- **Difficulty:** Easy, Medium, Hard — estimated from keywords and task length

You can override these manually, but most of the time the system guesses right from your wording. "Finish homework for calculus" → College/Medium. "Buy groceries" → Home/Easy. "Deploy SaaS landing page" → Solopreneur/Hard.

### 5. Subtasks

Big tasks can be broken down. Attach subtasks to any parent task so you can track progress without cluttering your main list.

---

## Task Lifecycle

A task moves through clear states:

```
Captured → Pending → In Progress → Done
                ↘ Failed / Snoozed / Carried Over
```

| State | What it means |
|-------|--------------|
| **Pending** | Default state — waiting to be started |
| **In Progress** | You've started working on it |
| **Done** | Completed. Moves to history. |
| **Snoozed** | Hidden from active lists until a chosen time (15 min, 30 min, 1 hour, 1 day) |
| **Carried Over** | Rolled forward to the next day because it wasn't finished |
| **Failed** | Marked as missed / dropped. Kept for accountability. |

---

## Reminders & Notifications

Task Stack doesn't just store tasks — it **nudges you** at the right moments:

- **30-minute warning:** Before a task is due
- **Due alert:** Right when the deadline hits
- **Overdue repeats:** Every 15 minutes until you act or snooze
- **Yesterday summary:** See what you left pending from the previous day

All reminders sync to the overlay pill so they catch your attention without stealing focus.

---

## The UI — Clean, Fast, Keyboard-Driven

Task Stack lives inside the overlay's **"Today"** tab. It is designed for speed:

- **Smart sort** by default: pending first, then in-progress, overdue tasks bubble to the top, soonest due next
- **7 sort modes:** Smart, Due Soonest/Latest, A→Z/Z→A, Easy/Hard First
- **Category tabs:** Filter by project, life area, or team
- **Keyboard navigation:**
  - `↑` / `↓` — move through tasks
  - `Space` — toggle done / not done
  - `Delete` — remove a task (with confirmation)
- **Add tasks by typing** with inline due-time, category, and difficulty pickers
- **Daily AI suggestion** at the top based on your last 10 days of completed work

The interface is **fully themed** across 5 overlay themes (Onyx, Graphite, Porcelain, Midnight, Ember).

---

## Why Task Stack Is "Switchable"

Task Stack is a **feature-gated module**. You can turn it completely on or off in Settings. When off:

- The "Today" tab disappears from the overlay
- Task reminders stop firing
- The F10 hotkey is freed up
- No task-related AI calls are made

Toggle it back on and everything resumes instantly — your task data is preserved. This makes Wiztant feel lightweight for users who only want dictation or agent mode, while power users get a full productivity system.

---

## Storage & Sync

Tasks are stored in a local JSON file (`memory/tasks.json`) that both the Python backend and the Electron overlay read and write. There is **no cloud dependency** for core task functionality — your data stays on your machine. The file is atomically written (temp-then-replace) to prevent corruption.

---

## Use Cases — Who Is It For?

| Persona | How Task Stack helps |
|---------|---------------------|
| **Developer** | "Deploy the hotfix by 4 PM" → captured, categorized, reminded. No context-switching to a separate app. |
| **Student** | "Submit calculus assignment by Friday" → auto-tagged as College/Medium. Due alert prevents last-minute panic. |
| **Solo Founder** | Juggle marketing, coding, and customer support tasks in one stack. Auto-categorization separates business from personal. |
| **Busy Parent** | Voice-add grocery items and appointment reminders while cooking or driving. Hands-free capture. |
| **Project Lead** | Break large deliverables into subtasks. Track what's in progress vs. pending at a glance. |
| **Anyone with ADHD** | Offload working memory. Speak a task and forget it — the system will remind you. Reduces mental clutter. |

---

## How Easy Is It to Use?

**One hotkey. Natural words. Zero structure required.**

You don't need to learn a syntax. You don't need to click through menus. You don't need to decide on a category or difficulty — the system infers it. You can literally say:

> *"Add task thingy by later"*

and Task Stack will still create a task (it just won't have a precise time). The barrier to entry is **as low as speaking aloud**.

For keyboard users, adding a task by typing takes **three keystrokes** after focus: type, hit Enter, done. The form is always visible, always ready.

---

## What It Does for You Right Now

If you are working on something — coding, writing, designing, studying — Task Stack lets you:

1. **Dump distractions instantly.** A new idea pops up? Speak it. Your mind is clear again in 3 seconds.
2. **Never miss a deadline.** Spoken deadlines become real calendar nudges.
3. **Review your day.** See what you accomplished today vs. what carried over.
4. **Plan tomorrow.** Ask for a suggestion based on your recent history.
5. **Stay accountable.** Failed tasks are visible — a gentle push to finish what you started.

---

## In Short

Task Stack is not a separate app. It is not a complex project management suite. It is a **capture-and-remind layer** that sits on top of your existing workflow, designed to be so fast and so natural that you actually use it. Speak a task, get reminded, mark it done. That is the whole loop — and it takes less energy than deciding what to have for lunch.
