# Plan: Feature Isolation, Credit Tracking, Security & Guardrails

**Date:** 2026-05-21
**Goal:** Ensure Reprompt, Dictation, Agent, and TuneHub do not clash; every feature reports credit usage to the main indicator and settings page; security guardrails are hardened with hardcoded system boundaries; comprehensive tests verify all guardrails.

---

## Architecture

### Wave 1: Foundation — Fix Concurrent State & Recording Race
- Unify recording locks into a single `_recording_lock`
- Add `threading.RLock` around `conversation_history` mutations
- Add `threading.Lock` around `credits.json` read/write (local fallback path)
- Add wave state arbitration so agent state cannot be overwritten by dictation finish

### Wave 2: Credit Tracking Completeness
- Include dictation in credit toasts (remove exclusion)
- Add per-feature usage summary API endpoint (`/credits/summary`) aggregating transactions by feature
- Render per-feature summary in Settings Credits tab
- Broadcast agent true-up events (refund/charge delta)
- Add credit reservation tracking so users see "reserved → charged" flow

### Wave 3: Security Hardening — Guardrails for Each Feature
| Feature | Guardrail |
|---|---|
| **Dictation** | Post-transcription content scanner (secrets, destructive commands, PII) before paste; max paste length limit |
| **RePrompt** | Pre-optimization secret/PII scanner on clipboard input; max input length; output injection check |
| **Agent** | Activate v2 guardrails in unified agent: path sandbox for read_file, app allowlist for open_app, clipboard validation, command allowlist/denylist, cost ceiling |
| **TuneHub** | Already has boundary guardrails — extend with file size limits on `.pkl` and rate limiting on learn endpoint |

### Wave 4: Guardrail Test Suite
- Expand `tests/test_agent_v2_guardrails.py` to 15+ tests covering all v2 guardrail classes
- Add `tests/test_feature_isolation.py` — simulate concurrent feature activation
- Add `tests/test_credit_race.py` — verify atomic deductions under concurrent load
- Add `tests/test_stt_guardrails.py` — verify paste blocking of dangerous content
- Add `tests/test_reprompt_guardrails.py` — verify PII redaction and input validation

---

## Tech Stack
- Python 3.11, pytest, `threading.RLock`, `filelock` (new dependency for cross-process credit safety)
- TypeScript/React — Settings Credits tab extension
- Existing test fixtures (`tmp_path`, `monkeypatch`) from `tests/conftest.py`

---

## Execution Steps

### Phase B: TDD — Write Failing Tests First

#### Step B1 — Test: Recording State Race Condition
**File:** `tests/test_feature_isolation.py` (new)
**Test:** `test_recording_lock_prevents_race`
- Mock `sounddevice.RawInputStream` and `StreamingSTT`
- Spawn two threads: one calls `start_recording()`, one calls `stop_recording()` rapidly
- Assert `state.recording` is always consistent with `_active_stt` presence
- **Watch it fail** (current code uses different locks → race possible)

#### Step B2 — Test: Conversation History Thread Safety
**File:** `tests/test_feature_isolation.py`
**Test:** `test_conversation_history_thread_safe`
- Spawn 10 threads appending to `state.conversation_history` simultaneously
- Assert list length == 10 and no `IndexError` / corruption
- **Watch it fail** (current code has no lock)

#### Step B3 — Test: Credit Deduction Atomicity
**File:** `tests/test_credit_race.py` (new)
**Test:** `test_concurrent_deductions_never_lose_credits`
- Initialize balance = 100
- Spawn 20 threads, each deducting 1 credit
- Assert final balance == 80
- **Watch it fail** (current `_save_local` has no file lock)

#### Step B4 — Test: Agent Path Sandbox
**File:** `tests/test_agent_v2_guardrails.py`
**Test:** `test_read_file_sandbox_blocks_etc_passwd`
- Call `tool_read_file("/etc/passwd")` via agent tool registry
- Assert blocked / sandboxed
- **Watch it fail** (current `tool_read_file` has no sandbox)

#### Step B5 — Test: STT Dangerous Content Blocking
**File:** `tests/test_stt_guardrails.py` (new)
**Test:** `test_paste_blocks_destructive_command`
- Simulate transcription "rm -rf /home/user"
- Assert `smart_paste` is NOT called; warning toast is sent
- **Watch it fail** (current paste has no validation)

#### Step B6 — Test: RePrompt PII Redaction
**File:** `tests/test_reprompt_guardrails.py` (new)
**Test:** `test_reprompt_redacts_api_key_in_input`
- Call `validate_prompt()` with text containing `sk-abc123...`
- Assert `ValidationError` or redaction before LLM call
- **Watch it fail** (current validation does not scan for secrets)

#### Step B7 — Test: Agent Cost Ceiling
**File:** `tests/test_agent_v2_guardrails.py`
**Test:** `test_agent_loop_respects_cost_ceiling`
- Mock agent loop running 100 steps
- Assert loop aborts when `COST_CEILING_USD` reached
- **Watch it fail** (v2 guardrails not wired into unified agent)

#### Step B8 — Test: Wave State Arbitration
**File:** `tests/test_feature_isolation.py`
**Test:** `test_agent_wave_state_not_overwritten_by_dictation`
- Set agent wave state to "agent"
- Simulate dictation stop → send_voice_state("idle")
- Assert wave state remains "agent" while `_agent_running` is True
- **Watch it fail** (current code overwrites unconditionally)

---

### Phase C: Implementation — Green

#### Step C1 — Fix Recording Lock Race
**File:** `core/hotkeys.py`
**Change:** Replace `_start_recording_lock` and `_stop_recording_lock` with single `_recording_lock`
**Lines:** ~1043, ~1097
**Verify:** `test_recording_lock_prevents_race` passes

#### Step C2 — Add Conversation History Lock
**File:** `core/__init__.py` or `core/agent.py`
**Change:** Add `conversation_history_lock = threading.RLock()` in `core/__init__.py`; wrap all `.append()` calls
**Files touched:** `core/agent.py`, `core/hotkeys.py` (dictation path to agent)
**Verify:** `test_conversation_history_thread_safe` passes

#### Step C3 — Add File Lock to Credit System
**File:** `core/credit_system.py`
**Change:** Add `filelock.FileLock` around `_load_local` / `_save_local` in `CreditBalanceManager`
**New dependency:** `filelock` (add to `requirements.txt`)
**Verify:** `test_concurrent_deductions_never_lose_credits` passes

#### Step C4 — Add Wave State Arbitration
**File:** `core/ws_bridge.py`
**Change:** In `send_voice_state()`, check `state._agent_running` — if True and requested state is "idle", skip broadcast
**Verify:** `test_agent_wave_state_not_overwritten_by_dictation` passes

#### Step C5 — Add Dictation to Credit Toasts
**File:** `core/credit_system.py`
**Change:** Remove `if feature != "dictation":` exclusion in both Supabase and local fallback paths of `deduct()`
**Verify:** Dictation toast appears in overlay

#### Step C6 — Add Per-Feature Credit Summary
**Backend:** `core/credit_system.py` — add `get_feature_summary(user_id)` aggregating transactions by feature
**Backend:** `core/server.py` — add `GET /credits/summary` endpoint
**Frontend:** `ui/whiztant-overlay/src/renderer/settings/Settings.tsx` — add feature summary section in `CreditsTab`
**Verify:** Settings page shows "Agent: 45 credits used · Dictation: 12 · RePrompt: 23 · TuneHub: 54"

#### Step C7 — Add Agent True-Up Broadcast
**File:** `core/agent.py`
**Change:** After true-up refund/charge, call `send_credit_consumed("agent_trueup", delta, new_balance)`
**Verify:** WS message received in overlay

#### Step C8 — STT Paste Guardrails
**File:** `core/stt_engine.py` (or new `core/stt_guardrails.py`)
**Change:** Before `smart_paste()`, run content through:
- Secret scanner (reuse `core/guardrails.py` `scan_secrets`)
- Destructive command regex (reuse `is_destructive_action`)
- Max length check (hardcoded `MAX_PASTE_CHARS = 10000`)
**If blocked:** Send `pill/notice` warning instead of pasting
**Verify:** `test_paste_blocks_destructive_command` passes

#### Step C9 — RePrompt Input Guardrails
**File:** `core/wizprompt.py`
**Change:** In `validate_prompt()`, add:
- Secret/PII scan — if found, reject with clear error
- Max input length (`MAX_REPROMPT_INPUT = 10000` chars)
- After optimization, scan output for prompt leakage / injection patterns
**Verify:** `test_reprompt_redacts_api_key_in_input` passes

#### Step C10 — Agent Tool Sandboxing
**File:** `core/agent.py`
**Change:**
- `tool_read_file`: Use `core/agent_v2/guardrails.py` `sandbox_path()` — reject paths outside project root
- `tool_open_app`: Add app allowlist — only allow apps from `agent_rules/apps_*.md` or user-installed apps; block system apps
- `tool_clipboard_write`: Max length 5000 chars, scan for secrets before writing
- `tool_run_command`: Use v2 `Guardrails.validate_command()` instead of weak v1 `is_destructive_action`
**Verify:** `test_read_file_sandbox_blocks_etc_passwd` passes

#### Step C11 — Wire V2 Guardrails into Unified Agent
**File:** `core/agent_unified.py`
**Change:** Replace v1 guardrail calls with v2 `Guardrails` class:
- Use v2 `classify_action()` ( richer DANGEROUS list)
- Use v2 `validate_command()` for verification commands
- Enforce v2 `COST_CEILING_USD` per agent run
- Use v2 path sandbox for any file operations
**Verify:** `test_agent_loop_respects_cost_ceiling` passes

#### Step C12 — Fix Curl Allowlist/Denylist Conflict
**File:** `core/agent_v2/guardrails.py`
**Change:** Remove `curl` from `_COMMAND_ALLOWLIST` (keep in denylist for safety)
**Verify:** Existing tests still pass

#### Step C13 — Increase Dangerous Confirmation Timeout
**File:** `core/agent_unified.py`
**Change:** Increase confirmation overlay timeout from `3.0` to `8.0` seconds
**Verify:** Manual test — overlay stays open long enough to read

#### Step C14 — Add Rate Limiting to REST Endpoints
**File:** `core/server.py`
**Change:** Add in-memory rate limiter (`slowapi` or simple dict) to `/agent/run` and `/wizprompt/optimize` — max 10 requests/minute per IP
**Verify:** 11th request returns 429

---

### Phase D: Verification & Regression Testing

#### Step D1 — Run full pytest suite
```bash
pytest tests/ -x -v
```
**Goal:** All existing tests pass + all new tests pass

#### Step D2 — Python import test
```bash
python -c "import main"
```
**Goal:** No import errors

#### Step D3 — Overlay build verification
```bash
cd ui/whiztant-overlay && npm run build
```
**Goal:** TypeScript compiles, no errors

#### Step D4 — Manual feature isolation smoke test
1. Start app (`python main.py`)
2. Trigger dictation (F9×1) — verify recording, wave state, credit toast
3. While dictation active, try triggering agent (overlay chat) — verify blocked or queued
4. Run agent task — verify wave state stays "agent" throughout
5. Run RePrompt (Ctrl+Shift+Space) — verify credit toast, no interference with agent
6. Run TuneHub learning — verify credit deduction, no interference
7. Check Settings Credits tab — verify all 4 features show usage

#### Step D5 — Security penetration test
1. Agent: Ask to "read /etc/passwd" — verify blocked
2. Agent: Ask to "open regedit" — verify blocked
3. Dictation: Say "format C drive" — verify NOT pasted, warning shown
4. RePrompt: Copy `sk-abcdefghijklmnopqrstuvwxyz` to clipboard, trigger RePrompt — verify blocked/redacted
5. Agent: Run 50-step task — verify aborts at cost ceiling or step limit

---

## Notes & Assumptions
- `filelock` is acceptable as a new dependency (lightweight, cross-platform)
- The user wants **all 4 features** to show credit usage, including dictation (remove exclusion)
- V2 guardrails are intentionally stronger — we migrate the unified agent to use them
- We do NOT do a global "Wiztant" rename — only touch lines we change
- We preserve existing API contracts (`/credits/balance`, `/credits/history`) — only add new `/credits/summary`

---

## Definition of Done
1. ✅ `pytest tests/` passes (all old + all new tests)
2. ✅ `python -c "import main"` passes
3. ✅ `npm run build` in overlay passes
4. ✅ Each feature (dictation, reprompt, agent, tunehub) shows distinct credit usage in Settings
5. ✅ No feature can corrupt another feature's state under rapid concurrent activation
6. ✅ Guardrails block dangerous actions in all 4 features (verified by tests)
7. ✅ Hardcoded limits documented and enforced (max paste length, max reprompt input, cost ceiling, step limits)
