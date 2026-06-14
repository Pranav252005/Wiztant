# Agent Mode Presets Redesign — Implementation Plan

## Goal
Replace the emoji-heavy template grid in the Agent ("Builder") tab with a clean, preset-driven dropdown system similar to RePrompt. Each preset must explain what it does, what it is useful for, and its limitations in plain language understandable by any user. No emojis. Rotating examples. Tab renamed to "Agent". Button renamed to "Run Agent".

---

## Files to Touch

| # | File | Change |
|---|---|---|
| 1 | `ui/whiztant-overlay/src/renderer/overlay/TopTabBar.tsx` | Label: "Builder" → "Agent" |
| 2 | `core/agent_presets.py` | **NEW** — Preset dataclass + 8 well-specified presets |
| 3 | `core/server.py` | Add `GET /agent_presets` endpoint |
| 4 | `ui/whiztant-overlay/src/renderer/overlay/AgentV2Panel.tsx` | Full UI rewrite: dropdown, info panel, dynamic params, rotating placeholder, "Run Agent" button, remove all emojis |
| 5 | `ui/whiztant-overlay/src/renderer/overlay/useAgentV2.ts` | Add `initiateWithPreset(intent, presetId, params)` |
| 6 | `core/ws_bridge.py` | Add `agent_v2:run_preset` handler |
| 7 | `core/agent_v2_engine.py` | Add `initiate_preset(preset_id, intent, params)` |

---

## Preset Schema (backend)

```python
@dataclass
class AgentPreset:
    id: str
    name: str
    display_name: str
    category: str          # "Development", "Productivity", "Creative", "System"
    description: str       # one-line
    what_it_does: str      # paragraph
    usage: str             # when to use
    limitations: str       # common limits in plain English
    template_id: str       # existing template id or "freeform"
    params_schema: list    # input fields
    examples: list[str]    # rotating placeholder pool
    system_prompt_addendum: str   # planner guidance
```

---

## Presets to Define

1. **Describe Freely** — Freeform intent, agent plans dynamically (General)
2. **Replicate Component** — Screenshot any UI → identify library or recreate → verify in browser → iterate until match (Development)
3. **PR Context Assembly** — Gather ticket details, design links, and screenshots into a complete Pull Request description (Development)
4. **Visual Bug Report** — Screenshot a bug, capture console errors, and create a detailed bug ticket with evidence (Development)
5. **Git Commit & Push** — Stage, commit with message, push to remote (Development)
6. **Staging Verification** — Post-merge sanity checks: click through flows, screenshot, report regressions (Development)
7. **Clone Private Repo** — SSH key setup + git clone workflow (Development)
8. **Slack to Notion PRD** — Requirements capture → structured PRD page (Productivity)
9. **Doc Screenshot Update** — Find outdated screenshots in docs, capture new ones from live app, replace them (Productivity)
10. **Browser Research** — Open sites, search, extract answers to clipboard (Productivity)
11. **App Optimizer** — Game/app performance tuning (7-layer pipeline) (System)

---

## Frontend UI Changes

### AgentV2Panel.tsx — Idle State

```
┌─────────────────────────────────────┐
│  Agent Preset  [Dropdown ▼]         │
│  ├─ Category headers                │
│  └─ Each option shows name + desc   │
│                                     │
│  [Selected Preset Info Card]        │
│  What it does:  ...                 │
│  Useful for:    ...                 │
│  Limitations:   ...                 │
│                                     │
│  [Dynamic param inputs]             │
│                                     │
│  Or describe freely:                │
│  ┌─────────────────────────────┐    │
│  │  (rotating placeholder)     │    │
│  └─────────────────────────────┘    │
│  [Run Agent]                        │
└─────────────────────────────────────┘
```

### Rotating Placeholder
- Cycle every 4 seconds through `examples` array
- Use `useEffect` + `setInterval`
- Pause rotation while user is typing

### Emoji Removal
- Remove 📦 🎨 🐛 📋 📝 ✅ 📚 from all JSX
- Replace with text labels or Lucide icons if needed (but user said no emojis; Lucide SVG icons are fine since they are not emojis)
- Keep the UI clean and text-only where possible

---

## Backend Wiring

1. `core/agent_presets.py` returns presets as JSON via `preset_to_dict()`
2. `core/server.py` exposes `GET /agent_presets`
3. `core/ws_bridge.py` handles `agent_v2:run_preset` → calls `engine.initiate_preset()`
4. `core/agent_v2_engine.py`:
   - `initiate_preset(preset_id, intent, params)`
   - If preset maps to a template → `initiate_workflow(template_id, params)`
   - If preset is freeform → `initiate_freeform(intent)`
   - Inject `system_prompt_addendum` into planner if present

---

## Verification Steps

1. `python -c "import main"` passes
2. `cd ui/whiztant-overlay && npm run build` succeeds
3. Overlay tab shows "Agent" not "Builder"
4. No emojis visible in Agent panel
5. Dropdown renders with categories and descriptions
6. Placeholder cycles through examples
7. Button says "Run Agent"

---

## Definition of Done

- [ ] Plan file written (this file)
- [ ] `TopTabBar.tsx` renamed to "Agent"
- [ ] `core/agent_presets.py` created with 8 presets
- [ ] `core/server.py` exposes `/agent_presets`
- [ ] `AgentV2Panel.tsx` uses dropdown, shows info cards, rotating examples, "Run Agent"
- [ ] All emojis removed from agent UI
- [ ] Build passes (`npm run build`)
- [ ] Python imports pass (`python -c "import main"`)
