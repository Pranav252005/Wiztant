# Shortcuts Usage Rules

These rules govern how you (Qwen, the planner) use the shortcut map that is
injected into your system prompt under the heading `## Available shortcuts for
this task:`.

## Core rules

1. **Prefer keyboard shortcuts over mouse clicks** whenever a reliable shortcut
   for the intended action exists in the injected shortcut block. Shortcuts are
   faster, more deterministic, and do not depend on screen coordinates or
   UI-TARS grounding.

2. **Try the shortcut first; fall back to UI-TARS only if it fails.** If after
   executing a shortcut the expected UI state is not observed, then and only
   then emit a UI-TARS click / grounded action to accomplish the same goal.

3. **Never invent or guess at shortcuts.** Only use key combinations that
   appear in the injected `## Available shortcuts for this task:` block, in the
   `[Global]` section, or in the `## RULE FILE` section. If no listed shortcut
   matches the action, plan a UI-TARS step instead — do not fabricate one.

4. **One keypress per step for multi-step sequences.** When following a
   `Sequences:` entry (e.g. `Win+I -> type: display -> Enter`), emit each
   keypress or typed string as its own separate step in your plan. Do not
   compress multiple keypresses into a single step.

5. **Respect fallbacks.** If the injected block has a `Fallbacks:` entry for
   the shortcut you chose, queue the fallback as the next candidate action
   when the primary shortcut does not produce the expected state.

## Format you should emit

For a keyboard shortcut step, prefer the `press_hotkey` / `type` action style
the executor already understands. Examples:

- `{"type": "press_hotkey", "keys": ["win", "i"]}`
- `{"type": "type_text", "text": "display"}`
- `{"type": "press_key", "key": "enter"}`

For anything not covered by a listed shortcut, fall back to the usual
`ask_uitars` / click-based action.

## Red flags — STOP

- About to emit a key combination that is NOT in the injected block.
- Combining multiple keys + typed text into a single step.
- Using a mouse click when a listed shortcut does exactly the same thing.
- Skipping the shortcut "because UI-TARS is easier" — shortcuts are preferred.

## Reminder

The shortcut block is budgeted to ~400 tokens. If something you need is
missing, it is genuinely missing — do not invent it. Use UI-TARS instead and
report the gap so the shortcut map can be extended.
