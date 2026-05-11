# Credit Usage Visibility & TaskStack AI Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time credit-consumption visibility for TaskStack, RePrompt, and TuneHub; add an AI opt-out toggle for TaskStack only; explicitly exclude Dictation from credit tracking.

**Architecture:** Extend the existing `credit_system.py` deduction hooks to broadcast per-feature credit cost via WebSocket after each transaction. Consume these messages in the overlay renderer to show transient toast-style notifications. For TaskStack, add a persisted boolean toggle (`task_ai_enabled`) in `data/settings.json` that gates the LLM refinement pipeline in `core/tasks.py`.

**Tech Stack:** Python 3.11 (FastAPI backend, WebSocket bridge), TypeScript/React 18 (Electron overlay), Tailwind CSS, Framer Motion.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `core/credit_system.py` | Modify | Broadcast `credits/consumed` WS message after every `deduct()` |
| `core/tasks.py` | Modify | Gate LLM task refinement behind `task_ai_enabled` setting |
| `core/wizprompt.py` | Modify | Pass credit cost into `_deduct_actual_tokens()` WS broadcast |
| `core/tune_hub/orchestrator.py` | Modify | Pass credit cost into TuneHub WS broadcast |
| `core/ws_bridge.py` | Modify | Route new `credits/consumed` message type to overlay |
| `ui/whiztant-overlay/src/renderer/overlay/TasksPanel.tsx` | Modify | Render AI toggle + consume credit toast |
| `ui/whiztant-overlay/src/renderer/overlay/WizPromptPanel.tsx` | Modify | Consume credit toast |
| `ui/whiztant-overlay/src/renderer/overlay/TuneHubPanel.tsx` | Modify | Consume credit toast |
| `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` | Modify | Add TaskStack AI toggle in Tasks settings tab |
| `ui/whiztant-overlay/src/renderer/shared/useBridge.ts` | Modify | Add `credits/consumed` to message type union |
| `data/settings.json` | Modify (schema) | Add `"task_ai_enabled": true` default |
| `tests/test_credit_visibility.py` | Create | Unit tests for WS broadcast + TaskStack gating |

---

## Task 1: Backend — Broadcast Credit Consumption via WebSocket

**Files:**
- Modify: `core/credit_system.py:362-422` (inside `deduct()`)
- Modify: `core/ws_bridge.py` (add `send_credit_consumed()` helper)
- Test: `tests/test_credit_visibility.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_credit_visibility.py`:
  ```python
  import json
  from unittest.mock import patch, MagicMock
  from core.credit_system import deduct, get_current_user_id

  def test_deduct_broadcasts_ws_message():
      user_id = get_current_user_id()
      with patch("core.credit_system._get_manager") as mock_mgr, \
           patch("core.ws_bridge.broadcast_sync") as mock_ws:
          mock_mgr.return_value.deduct.return_value = True
          deduct(user_id, "reprompt", 5, model="gpt-4")
          mock_ws.assert_called_once()
          call_args = mock_ws.call_args[0][0]
          assert call_args["type"] == "credits/consumed"
          assert call_args["feature"] == "reprompt"
          assert call_args["amount"] == 5
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_credit_visibility.py::test_deduct_broadcasts_ws_message -v
  ```

- [ ] **Step 3: Add `send_credit_consumed()` to `core/ws_bridge.py`**
  ```python
  def send_credit_consumed(feature: str, amount: int, balance_after: int, model: str | None = None):
      broadcast_sync({
          "type": "credits/consumed",
          "feature": feature,
          "amount": amount,
          "balance_after": balance_after,
          "model": model,
          "timestamp": datetime.utcnow().isoformat(),
      })
  ```

- [ ] **Step 4: Hook broadcast into `CreditBalanceManager.deduct()`**
  In `core/credit_system.py`, at the end of the `deduct()` method (after both Supabase and local fallback paths succeed), call:
  ```python
  self._broadcast_update(user_id)
  try:
      from core.ws_bridge import send_credit_consumed
      send_credit_consumed(feature, amount, new_balance, model)
  except Exception:
      pass
  return True
  ```

- [ ] **Step 5: Run test to verify it passes**
  ```bash
  pytest tests/test_credit_visibility.py -v
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add tests/test_credit_visibility.py core/credit_system.py core/ws_bridge.py
  git commit -m "feat(credits): broadcast credits/consumed WS message after every deduction"
  ```

---

## Task 2: Backend — TaskStack AI Opt-Out Toggle

**Files:**
- Modify: `core/tasks.py` (find `refine_task_text()` or LLM call site)
- Modify: `core/server.py` (expose `GET/POST /settings/task_ai_enabled`)
- Modify: `data/settings.json` (add default key)
- Test: `tests/test_credit_visibility.py`

- [ ] **Step 1: Write the failing test**
  ```python
  def test_task_refinement_skipped_when_ai_disabled(monkeypatch, tmp_path):
      settings = tmp_path / "settings.json"
      settings.write_text(json.dumps({"task_ai_enabled": False}))
      monkeypatch.setattr("core.tasks.SETTINGS_PATH", str(settings))
      from core.tasks import refine_task_text
      result = refine_task_text("buy milk")
      assert result == "buy milk"  # No LLM polish applied
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  pytest tests/test_credit_visibility.py::test_task_refinement_skipped_when_ai_disabled -v
  ```

- [ ] **Step 3: Implement the gating logic in `core/tasks.py`**
  At the top of `refine_task_text()` (or wherever the LLM refinement happens):
  ```python
  def _load_setting(key: str, default=None):
      try:
          with open(SETTINGS_PATH, "r") as f:
              return json.load(f).get(key, default)
      except Exception:
          return default

  def refine_task_text(text: str) -> str:
      if not _load_setting("task_ai_enabled", True):
          return text
      # ... existing LLM refinement logic ...
  ```

- [ ] **Step 4: Add default to `data/settings.json`**
  ```json
  {
    "task_ai_enabled": true
  }
  ```

- [ ] **Step 5: Add FastAPI endpoints in `core/server.py`**
  ```python
  @app.get("/settings/task_ai_enabled")
  def get_task_ai_enabled():
      try:
          from core.tasks import _load_setting
          return {"ok": True, "enabled": _load_setting("task_ai_enabled", True)}
      except Exception as e:
          raise HTTPException(status_code=500, detail=str(e))

  @app.post("/settings/task_ai_enabled")
  def set_task_ai_enabled(body: dict):
      try:
          from core.tasks import SETTINGS_PATH
          data = {}
          if os.path.exists(SETTINGS_PATH):
              with open(SETTINGS_PATH, "r") as f:
                  data = json.load(f)
          data["task_ai_enabled"] = bool(body.get("enabled", True))
          with open(SETTINGS_PATH, "w") as f:
              json.dump(data, f, indent=2)
          return {"ok": True, "enabled": data["task_ai_enabled"]}
      except Exception as e:
          raise HTTPException(status_code=500, detail=str(e))
  ```

- [ ] **Step 6: Run test to verify it passes**
  ```bash
  pytest tests/test_credit_visibility.py -v
  ```

- [ ] **Step 7: Commit**
  ```bash
  git add core/tasks.py core/server.py data/settings.json tests/test_credit_visibility.py
  git commit -m "feat(tasks): add task_ai_enabled toggle to gate LLM refinement"
  ```

---

## Task 3: Frontend — Credit Toast Notification Component

**Files:**
- Create: `ui/whiztant-overlay/src/renderer/shared/CreditToast.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/shared/useBridge.ts` (type union)
- Test: `cd ui/whiztant-overlay && npm run build`

- [ ] **Step 1: Write the component**
  ```tsx
  import { useEffect, useState } from 'react';
  import { motion, AnimatePresence } from 'framer-motion';
  import { useBridgeMessage } from './useBridge';

  type CreditToast = {
    id: string;
    feature: string;
    amount: number;
    balanceAfter: number;
  };

  const FEATURE_LABELS: Record<string, string> = {
    taskstack: 'TaskStack',
    reprompt: 'RePrompt',
    tunehub: 'Tune Hub',
    agent: 'Agent',
    chat: 'Chat',
  };

  export function useCreditToasts() {
    const [toasts, setToasts] = useState<CreditToast[]>([]);

    useBridgeMessage((msg) => {
      if (msg?.type === 'credits/consumed') {
        const feature = String(msg.feature ?? '');
        // Dictation is explicitly excluded from tracking visibility
        if (feature === 'dictation') return;
        const toast: CreditToast = {
          id: `${Date.now()}-${Math.random()}`,
          feature,
          amount: Number(msg.amount ?? 0),
          balanceAfter: Number(msg.balance_after ?? 0),
        };
        setToasts((prev) => [...prev.slice(-2), toast]);
        window.setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== toast.id));
        }, 3000);
      }
    });

    return toasts;
  }

  export function CreditToastContainer({ toasts }: { toasts: CreditToast[] }) {
    return (
      <div style={{ position: 'fixed', bottom: 80, left: '50%', transform: 'translateX(-50%)', zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                background: 'rgba(15,15,26,0.95)',
                border: '1px solid rgba(192,193,255,0.25)',
                color: '#e2e2e2',
                fontSize: 12,
                fontWeight: 500,
                backdropFilter: 'blur(8px)',
                whiteSpace: 'nowrap',
                boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              }}
            >
              <span style={{ color: '#c0c1ff' }}>{FEATURE_LABELS[t.feature] || t.feature}</span>
              {' — '}
              <span style={{ color: '#F59E0B' }}>−{t.amount} credit{t.amount !== 1 ? 's' : ''}</span>
              {' · '}
              <span style={{ color: '#6b7280' }}>{t.balanceAfter} left</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    );
  }
  ```

- [ ] **Step 2: Add `credits/consumed` to `useBridge.ts` message types**
  Locate the message type union and add:
  ```ts
  | { type: 'credits/consumed'; feature: string; amount: number; balance_after: number; model?: string; timestamp?: string }
  ```

- [ ] **Step 3: Render `<CreditToastContainer>` inside the overlay root**
  In `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx`, import and render:
  ```tsx
  import { useCreditToasts, CreditToastContainer } from '../shared/CreditToast';
  // ... inside Overlay component:
  const creditToasts = useCreditToasts();
  // ... inside JSX return:
  <CreditToastContainer toasts={creditToasts} />
  ```

- [ ] **Step 4: Build**
  ```bash
  cd ui/whiztant-overlay && npm run build
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add ui/whiztant-overlay/src/renderer/shared/CreditToast.tsx ui/whiztant-overlay/src/renderer/shared/useBridge.ts ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx
  git commit -m "feat(ui): add CreditToast component for real-time credit consumption visibility"
  ```

---

## Task 4: Frontend — TaskStack AI Toggle UI

**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/settings/Settings.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/overlay/TasksPanel.tsx`
- Test: `cd ui/whiztant-overlay && npm run build`

- [ ] **Step 1: Add toggle in Settings → Tasks tab**
  In `Settings.tsx`, inside the Tasks settings section (or create one if absent), add:
  ```tsx
  const [taskAiEnabled, setTaskAiEnabled] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8765/settings/task_ai_enabled')
      .then((r) => r.json())
      .then((d) => { if (d.ok) setTaskAiEnabled(d.enabled); })
      .catch(() => {});
  }, []);

  const handleTaskAiToggle = (enabled: boolean) => {
    setTaskAiEnabled(enabled);
    fetch('http://localhost:8765/settings/task_ai_enabled', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }).catch(() => {});
  };
  ```

  Render the toggle:
  ```tsx
  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
    <input
      type="checkbox"
      checked={taskAiEnabled}
      onChange={(e) => handleTaskAiToggle(e.target.checked)}
      style={{ width: 18, height: 18, accentColor: theme.aiAccent }}
    />
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>Use AI for TaskStack</div>
      <div style={{ fontSize: 11, color: theme.textMuted }}>
        {taskAiEnabled
          ? 'AI will refine and improve task text before saving.'
          : 'Tasks will be saved exactly as typed or spoken.'}
      </div>
    </div>
  </label>
  ```

- [ ] **Step 2: Show AI badge in TasksPanel when enabled**
  In `TasksPanel.tsx`, read the same setting and render a small indicator next to the task input:
  ```tsx
  const [taskAiEnabled, setTaskAiEnabled] = useState(true);
  useEffect(() => {
    fetch('http://localhost:8765/settings/task_ai_enabled')
      .then((r) => r.json())
      .then((d) => { if (d.ok) setTaskAiEnabled(d.enabled); })
      .catch(() => {});
  }, []);
  ```
  Next to the task input form, conditionally render:
  ```tsx
  {taskAiEnabled && (
    <span style={{ fontSize: 10, color: theme.aiAccent, fontWeight: 600 }}>✨ AI ON</span>
  )}
  ```

- [ ] **Step 3: Build**
  ```bash
  cd ui/whiztant-overlay && npm run build
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add ui/whiztant-overlay/src/renderer/settings/Settings.tsx ui/whiztant-overlay/src/renderer/overlay/TasksPanel.tsx
  git commit -m "feat(ui): add TaskStack AI opt-out toggle in Settings + indicator in TasksPanel"
  ```

---

## Task 5: Verify Dictation Exclusion

**Files:**
- Modify: None (verify-only)
- Test: `tests/test_credit_visibility.py`

- [ ] **Step 1: Write assertion test**
  ```python
  def test_dictation_does_not_trigger_credit_toast():
      with patch("core.ws_bridge.broadcast_sync") as mock_ws:
          user_id = get_current_user_id()
          deduct(user_id, "dictation", 1, model="whisper")
          calls = [c[0][0] for c in mock_ws.call_args_list]
          consumed_calls = [c for c in calls if c.get("type") == "credits/consumed"]
          assert len(consumed_calls) == 0, "Dictation should NOT broadcast credits/consumed"
  ```

- [ ] **Step 2: Make it pass**
  In `core/credit_system.py`, inside the `deduct()` broadcast hook, add:
  ```python
  if feature != "dictation":
      try:
          from core.ws_bridge import send_credit_consumed
          send_credit_consumed(feature, amount, new_balance, model)
      except Exception:
          pass
  ```

- [ ] **Step 3: Run tests**
  ```bash
  pytest tests/test_credit_visibility.py -v
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add core/credit_system.py tests/test_credit_visibility.py
  git commit -m "feat(credits): exclude dictation from credit consumption visibility"
  ```

---

## Sample Notification Message Template

```
RePrompt — −3 credits · 47 left
TaskStack — −1 credit · 46 left
Tune Hub — −12 credits · 34 left
```

- **Format:** `{FeatureLabel} — −{amount} credit{s} · {balanceAfter} left`
- **Color:** Feature label in Primary (`#c0c1ff`), cost in Amber (`#F59E0B`), balance in Muted (`#6b7280`).
- **Duration:** 3 seconds, auto-dismiss with Framer Motion exit animation.
- **Position:** Fixed bottom-center, 80px above the pill.
- **Max stacked:** 3 toasts; older ones slide out.

---

## TaskStack AI Toggle Logic Flow

```
User toggles "Use AI for TaskStack" in Settings
  │
  ▼
POST /settings/task_ai_enabled { enabled: false }
  │
  ▼
Backend writes "task_ai_enabled": false to data/settings.json
  │
  ▼
Next time user creates a task (voice or typed):
  ├─ refine_task_text() reads settings.json
  ├─ If task_ai_enabled == false → returns raw text immediately
  └─ If task_ai_enabled == true  → runs LLM refinement as before
  │
  ▼
No credits consumed for LLM call when disabled
```

---

## Self-Review Checklist

| Requirement | Task | Status |
|-------------|------|--------|
| Real-time credit toast for TaskStack | Task 1 + Task 3 | ✅ |
| Real-time credit toast for RePrompt | Task 1 + Task 3 | ✅ |
| Real-time credit toast for TuneHub | Task 1 + Task 3 | ✅ |
| Dictation excluded from visibility | Task 5 | ✅ |
| TaskStack AI opt-out toggle | Task 2 + Task 4 | ✅ |
| TuneHub/RePrompt mandatory (no toggle) | N/A — no UI added | ✅ |
| Persist toggle in settings.json | Task 2 | ✅ |
