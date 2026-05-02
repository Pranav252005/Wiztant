# Whiztant — F10 Task Creation Hotkey: Comprehensive Implementation Prompt

**Deadline:** 2026-04-19 12:00 PM  
**Project root:** `C:\whis\whiztant-app\`  
**Electron UI root:** `C:\whis\ui\whiztant-overlay\`

---

## What to Build

Add a dedicated **F10 hotkey** (remappable by user) that opens a voice overlay on the pill specifically for creating tasks. This is completely separate from F9 (which handles dictation/conversation/agent). The user presses F10 once, speaks their task, and it's saved automatically. No slash commands needed.

**User flow:**
1. User presses F10
2. Pill animates: circle disappears, pill shows a purple/indigo "Add Task" label + recording wave
3. User speaks: `"Buy groceries at 6pm tomorrow"` or `"Finish the report"`
4. Whisper transcribes → LLM parses task title + optional date/time
5. Pill shows Task Saved confirm (existing flow: Edit / Save / Decline, auto-saves in 5s)
6. Done

---

## Files to Modify

### 1. `core/hotkeys.py` — Register F10

Add F10 listener alongside the existing F9 counter logic.

```python
# In the pynput keyboard listener's on_press callback, AFTER existing F9 logic:

from pynput.keyboard import Key

# Add these lines wherever F9 is handled:
elif key == Key.f10:
    threading.Thread(target=self._handle_task_hotkey, daemon=True).start()
```

Add a new method `_handle_task_hotkey` in the same class:

```python
def _handle_task_hotkey(self):
    """F10 pressed — open task creation voice mode."""
    from core.voice import record_task_voice
    record_task_voice()
```

**Also:** read the hotkey from config so it's remappable:

```python
# At class init, load the task hotkey from settings:
import json, os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'settings.json')

def _load_task_hotkey(self) -> Key:
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
        key_str = data.get('task_hotkey', 'f10')
        return getattr(Key, key_str)
    except Exception:
        return Key.f10

# In __init__:
self.task_hotkey = self._load_task_hotkey()

# In on_press, replace Key.f10 with self.task_hotkey:
elif key == self.task_hotkey:
    threading.Thread(target=self._handle_task_hotkey, daemon=True).start()
```

---

### 2. `core/voice.py` — Add `record_task_voice()`

Add a new function that:
1. Sets wave state to `recording` with a "task" label variant
2. Records audio (same Groq Whisper pipeline as existing push-to-talk)
3. Parses the transcript to extract task title + optional date/time using a quick LLM call
4. Calls `task_manager.save_task()` with the result
5. Triggers the pill Task Saved confirmation notification

```python
def record_task_voice():
    """F10 task creation: record → transcribe → parse → save task."""
    import threading
    from ui import visualizer
    from core import task_manager, agent

    try:
        # 1. Signal pill to show task-recording state
        visualizer.set_state("task_recording")  # new state — see Electron section

        # 2. Record audio (reuse existing push-to-talk recorder)
        audio_data = record_audio()  # existing function in this file

        if not audio_data:
            visualizer.set_state("idle")
            return

        # 3. Transcribe via Groq Whisper (same as existing)
        transcript = transcribe_audio(audio_data)  # existing function

        if not transcript or not transcript.strip():
            visualizer.set_state("idle")
            return

        logging.info(f"[task_voice] Transcript: {transcript}")

        # 4. Parse task title + optional datetime using LLM
        parsed = _parse_task_from_speech(transcript)

        # 5. Check for duplicate (existing duplicate detection)
        if task_manager.is_duplicate(parsed['title']):
            # Show duplicate alert on pill
            visualizer.show_notification({
                "type": "duplicate_task",
                "existing_task": task_manager.find_similar(parsed['title']),
                "attempted_time": parsed.get('time_str', '')
            })
            return

        # 6. Show Task Saved confirm on pill (existing confirm flow)
        visualizer.show_notification({
            "type": "task_saved_confirm",
            "title": parsed['title'],
            "time_str": parsed.get('time_str', ''),
            "day_str": parsed.get('day_str', ''),
            "task_data": parsed
        })
        # The confirm flow auto-saves after 5s via the pill notification handler

    except Exception as e:
        logging.error(f"[task_voice] Error: {e}")
        visualizer.set_state("idle")


def _parse_task_from_speech(transcript: str) -> dict:
    """Use LLM to extract task title and optional due date/time from speech."""
    import openai, json, os
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d %A")

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=os.getenv("MODEL_FREE", "gpt-4o-mini"),
        messages=[{
            "role": "system",
            "content": (
                f"Today is {today}. Extract a task from the user's speech. "
                "Return JSON only: {\"title\": \"...\", \"due_date\": \"YYYY-MM-DD or null\", "
                "\"due_time\": \"HH:MM or null\", \"time_str\": \"human readable or empty\", "
                "\"day_str\": \"human readable day or empty\"}. "
                "Be concise. title should be clean imperative text."
            )
        }, {
            "role": "user",
            "content": transcript
        }],
        max_tokens=150,
        response_format={"type": "json_object"}
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"title": transcript.strip(), "due_date": None, "due_time": None,
                "time_str": "", "day_str": ""}
```

---

### 3. `core/task_manager.py` — Add `save_task()`, `is_duplicate()`, `find_similar()`

If `task_manager.py` doesn't exist yet, create it. Add these methods:

```python
import json, os, uuid
from datetime import datetime

TASKS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'tasks.json')


def _load() -> list:
    if not os.path.exists(TASKS_PATH):
        return []
    with open(TASKS_PATH) as f:
        return json.load(f)


def _save(tasks: list):
    os.makedirs(os.path.dirname(TASKS_PATH), exist_ok=True)
    with open(TASKS_PATH, 'w') as f:
        json.dump(tasks, f, indent=2)


def save_task(parsed: dict) -> dict:
    """Save a new task from parsed voice data. Returns the saved task."""
    tasks = _load()
    task = {
        "id": str(uuid.uuid4()),
        "title": parsed.get("title", ""),
        "due_date": parsed.get("due_date"),
        "due_time": parsed.get("due_time"),
        "done": False,
        "created_at": datetime.now().isoformat(),
        "source": "voice"
    }
    tasks.append(task)
    _save(tasks)
    return task


def is_duplicate(title: str) -> bool:
    """Check if a task with similar title already exists (undone)."""
    tasks = _load()
    title_lower = title.lower().strip()
    for t in tasks:
        if not t.get("done") and t.get("title", "").lower().strip() == title_lower:
            return True
    return False


def find_similar(title: str) -> dict | None:
    """Find the first undone task with a matching title."""
    tasks = _load()
    title_lower = title.lower().strip()
    for t in tasks:
        if not t.get("done") and t.get("title", "").lower().strip() == title_lower:
            return t
    return None
```

---

### 4. Electron — `src/renderer/src/` — New pill state + `task_recording` variant

In whatever component controls pill states (likely `PillOverlay.tsx` or `WaveVisualization.tsx`), add a new state `task_recording`:

```tsx
// Add to your pill state union type:
type PillState = 'idle' | 'recording' | 'thinking' | 'speaking' | 'agent' | 'task_recording'

// In the pill render logic, when state === 'task_recording':
// - Hide the center circle
// - Show a small indigo/purple label "Add Task" on the left of the wave
// - The wave animates the same as 'recording' state
// - Color accent: use indigo (#6366F1) instead of the default recording color

// Example with Tailwind:
{state === 'task_recording' && (
  <span className="text-xs font-medium text-indigo-400 mr-2 tracking-wide">Add Task</span>
)}
```

Also handle the WebSocket message from Python for `task_recording` state:

```ts
// In your WS message handler (wherever you handle 'state_change' or equivalent):
case 'task_recording':
  setPillState('task_recording')
  break
```

---

### 5. `data/settings.json` — Add `task_hotkey` field

Create or update `data/settings.json` to include the default task hotkey:

```json
{
  "task_hotkey": "f10"
}
```

This lets users remap it to any F-key or other key by editing this file (or later via a settings UI). Valid values are pynput `Key` attribute names: `"f10"`, `"f8"`, `"f11"`, etc.

---

### 6. `ui/tray.py` — Add settings shortcut (optional but recommended)

In the tray menu, add an item "Change task hotkey (F10)" that opens `data/settings.json` in Notepad for now:

```python
import subprocess

pystray.MenuItem(
    "Change task hotkey (F10)",
    lambda: subprocess.Popen(['notepad.exe', SETTINGS_PATH])
)
```

---

## What NOT to Change

- F9 logic stays exactly as-is (dictation × 1, conversation × 2, agent × 3)
- The existing Task Saved confirm pill notification flow (Edit/Save/Decline, 5s auto-save) — F10 feeds into that existing flow, it doesn't bypass it
- Duplicate detection logic — F10 uses the same duplicate check

---

## Testing Checklist

1. Press F10 → pill shows "Add Task" label + recording wave
2. Say "Finish the landing page at 9pm" → task parsed correctly (title + time)
3. Pill shows Task Saved confirm with "Finish the landing page" + "9:00 PM today"
4. Wait 5 seconds → task saved to `data/tasks.json`
5. Press F10 again, say same task → pill shows duplicate alert (gold), auto-dismisses in 10s
6. Edit `data/settings.json` to `"task_hotkey": "f8"` → restart app → F8 now triggers task mode, F10 does nothing
7. F9 still works normally for all three modes — no regression

---

## Architecture Note

This keeps the hotkey architecture clean:
- **F9** = input mode selector (dictation / conversation / agent) — counts taps
- **F10 (remappable)** = task creation only — single tap, dedicated pipeline
- No slash commands needed
- No mode counter for F10 — one press = one task recording session
