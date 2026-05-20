# Wiztant Systematic Debugging — Master Synthesis & Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, or superpowers:subagent-driven-development for parallel task execution.

**Goal:** Fix all identified bugs across the Wiztant codebase, ranked by severity and dependency order.

**Architecture:** Wiztant is a voice-first AI desktop assistant with Python backend (~17,600 lines in `core/`, ~5,300 lines in `platforms/`), Electron overlay (`ui/whiztant-overlay/`), and marketing website. Systematic debugging by 20 independent subagents identified 150+ individual bugs and design flaws.

**Tech Stack:** Python 3.11, asyncio, FastAPI, Electron 33 + React 18 + TypeScript.

---

## Executive Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Bugs Found | 150+ | 12 | 38 | 52 | 48+ |
| Test Collection Errors | 23 | — | — | — | — |
| Missing Test Coverage | 15+ domains | — | — | — | — |
| Ghost Dependencies | 3 modules | 3 | — | — | — |

**Top 5 Systemic Issues:**
1. **Test infrastructure is broken** — No `conftest.py`, inconsistent `sys.path` guards, 23 collection errors in full suite.
2. **Ghost dependencies** — `core/system_task_executor.py`, `core/action_optimizer.py`, `core/wiztype/` referenced but deleted.
3. **Dual guardrail systems** — `core/guardrails.py` (weak, active) vs `core/agent_v2/guardrails.py` (strong, unused).
4. **Cross-process file races** — `memory/tasks.json` and `memory/memory.json` read/written by Python + Electron with no locking.
5. **Async/sync mismatch** — Multiple async handlers call blocking sync functions without `asyncio.to_thread()`.

---

## Bug Registry — Ranked by Severity

### 🔴 CRITICAL (Fix Immediately)

| # | Domain | File | Line | Bug | Fix Complexity |
|---|--------|------|------|-----|----------------|
| C1 | Test Infra | `tests/test_task_classifier.py` | 5 | Missing `sys.path.insert` poisons entire pytest suite's `sys.modules['core']` | 1 min |
| C2 | Test Infra | `tests/stt_tests/test_integration.py` | 5 | Missing `sys.path.insert`; imports `core.stt_refiner` which fails under pytest | 1 min |
| C3 | Test Infra | `tests/stt_tests/test_refiner.py` | 5 | Same missing `sys.path.insert` as C2 | 1 min |
| C4 | Test Infra | `tests/stt_tests/test_smart_paste.py` | 4 | Same missing `sys.path.insert` | 1 min |
| C5 | Test Infra | `tests/stt_tests/test_vocab.py` | 5 | Same missing `sys.path.insert` | 1 min |
| C6 | Test Infra | `tests/stt_tests/test_dictation_edge_cases.py` | 8 | Same missing `sys.path.insert` | 1 min |
| C7 | Test Infra | `tests/test_agent_shared.py` | 1 | Missing `sys.path.insert`; all 12 tests fail collection | 1 min |
| C8 | Background Agent | `core/background_agent.py` | 475-479 | Imports `SystemTaskExecutor` from `core.system_task_executor` — **module does not exist** | 5 min |
| C9 | Background Agent | `core/background_agent.py` | 813, 845-866 | Imports `ActionOptimizer` from `core.action_optimizer` — **module does not exist** | 5 min |
| C10 | Agent Core | `core/agent.py` | 231, 292 | References `core.wiztype.custom_model` — **subsystem removed** per AGENTS.md | 5 min |
| C11 | TuneHub | `core/tune_hub/orchestrator.py` | 177-183 | Failure paths pass `credits_used=` to `TuneResult` dataclass which lacks that field → `TypeError` | 5 min |
| C12 | TuneHub | `core/tune_hub/orchestrator.py` | 118-140 | Credits deducted **before** learning; no refund on exception → permanent credit loss | 10 min |

### 🟠 HIGH (Fix This Sprint)

| # | Domain | File | Line | Bug | Fix Complexity |
|---|--------|------|------|-----|----------------|
| H1 | Task System | `core/tasks.py` | 147-152 | `_save()` not thread-safe; concurrent writes cause lost updates | 10 min |
| H2 | Task System | `ui/whiztant-overlay/src/main/ipc.ts` | 74-92 | `buildTask()` strips Python-only fields (`snoozed_until`, `category`, `difficulty`, `progress`) | 15 min |
| H3 | Task System | `ui/whiztant-overlay/src/main/ipc.ts` + `core/tasks.py` | 69-71 | Cross-process race: Electron + Python both read/write `tasks.json` with no locking | 20 min |
| H4 | Memory | `core/memory.py` | 177-186 | Writes are non-atomic; crash during save corrupts `memory.json` | 10 min |
| H5 | Memory | `core/memory.py` | 121-135 | Silent total data loss on read error — returns empty dict | 10 min |
| H6 | Memory | `core/memory.py` | 192-201 | Race condition on `_data` global; `_ensure_loaded()` mutates without `_lock` | 10 min |
| H7 | Memory | `core/agent.py` | 65-71, 146-147 | `AgentMemory` also uses non-atomic writes and broad-exception swallowing | 10 min |
| H8 | Agent Core | `core/agent.py` | 1093 | `parse_response` regex cannot parse nested JSON tool calls | 15 min |
| H9 | Agent Core | `core/agent.py` | 377-380 | `call_llm` silently truncates conversation history `[-14:]` / `[-15:]` with no warning | 5 min |
| H10 | Agent Core | `core/agent.py` | 209 | Global `agent_memory` singleton with no session isolation | 20 min |
| H11 | Agent Core | `core/agent.py` | 620-624 | `tool` decorator silently overwrites duplicate names | 5 min |
| H12 | Agent Core | `core/agent.py` | 679 | `run_command` tool executes `shell=True` with zero guardrails | 15 min |
| H13 | Agent Core | `core/agent.py` | 727 | `write_file` tool has no path sandboxing — can write anywhere | 10 min |
| H14 | Agent Engine | `core/agent_engine.py` | 63-68 | Duplicate constants (`DEFAULT_TIMEOUT` defined twice) | 1 min |
| H15 | Agent Engine | `core/agent_engine.py` | 357-363 | `to_base64()` crashes on RGBA images (JPEG doesn't support alpha) | 5 min |
| H16 | Agent Engine | `core/agent_unified.py` | 167-177 | Null-pointer risk: `title` can be `None` before dereference | 5 min |
| H17 | Agent Engine | `core/agent_unified.py` | 307 | Coordinate guardrail only checks `click`/`scroll`, missing `double_click`, `right_click`, `drag` | 5 min |
| H18 | Agent Engine | `core/agent_unified.py` | 311-315 | Coordinate validation runs on **normalized 0–1000 scale** with default `screen_w=1920` | 15 min |
| H19 | Agent Engine | `core/agent_unified.py` | 312-315 | Invalid coordinates trigger `break` instead of `return` — silent failure | 5 min |
| H20 | Agent Engine | `core/agent_unified.py` | 680-690 | `_adaptive_settle` while loop could hang if `runtime.screenshot()` blocks | 10 min |
| H21 | Guardrails | `core/shared/guardrails.py` | Entire file | Stale duplicate guardrails module — zero imports, weaker patterns, risk of accidental use | 1 min |
| H22 | Guardrails | `platforms/linux/_vlm_impl.py` | 677 | Loop detection hashes `b""` when `prefetched_img` is not bytes → false positive | 5 min |
| H23 | Guardrails | `platforms/windows/_vlm_impl.py` | 2005 | Same empty-bytes loop detection bug as Linux | 5 min |
| H24 | STT Engine | `core/stt_engine.py` | ~360 | Missing `import subprocess` — `smart_paste()` calls `subprocess` but module not imported | 1 min |
| H25 | STT Engine | `core/hotkeys.py` | ~995-1121 | Double `clean_transcript` when `_was_streaming` is True | 5 min |
| H26 | STT Engine | `core/hotkeys.py` | 995-1121 | Start/stop recording race: different locks allow interleaving | 20 min |
| H27 | STT Engine | `core/hotkeys.py` | 1096-1120 | Windows: `_stop_recording` blocks on Groq HTTP call inside keyboard hook thread | 20 min |
| H28 | Hotkeys | `platforms/linux/hotkeys.py` | 98-115 | Combo shortcuts fire on **any** keypress while modifier held | 10 min |
| H29 | WS Bridge | `core/ws_bridge.py` | 662-687 | Agent event helpers call `asyncio.run_coroutine_threadsafe(_broadcast(...), _loop)` without null guard | 5 min |
| H30 | WS Bridge | `core/ws_bridge.py` | 649-659 | `send_mic_level` broadcasts `NaN`/`Infinity` without validation → JavaScript `JSON.parse` crash | 5 min |
| H31 | WS Bridge | `ui/whiztant-overlay/src/main/bridge.ts` | 46-54 | `sendBridgeMessage` calls `JSON.stringify` without try/catch — crashes on circular refs | 5 min |
| H32 | FastAPI | `core/server.py` | 185 | `/agent/run` is async but calls sync `agent_module.ask_ai()` without `await` / `to_thread` | 10 min |
| H33 | FastAPI | `core/server.py` | 42-56 | Overly permissive CORS: `app://.`, `file://`, `null` with `allow_credentials=True` | 10 min |
| H34 | FastAPI | `core/server.py` | 460-506 | Agent v2 engines stored in global dict with no cleanup or locking | 15 min |
| H35 | FastAPI | `core/server.py` | 215, 409 | Multiple endpoints accept `body: dict` with no Pydantic validation | 20 min |
| H36 | TuneHub | `core/tune_hub/credit_system/credit_tracker.py` | 25-28 | `get_balance()` stub always returns 0; public API reports wrong balance | 10 min |
| H37 | WizPrompt | `core/wizprompt.py` | 558-573 | `_apply_persona_weights()` only reorders list; fast mode ignores weights entirely | 15 min |
| H38 | WizPrompt | `core/presets.py` + `core/wizprompt.py` | 246-255 | User presets have zero validation; prompt injection possible via `system_prompt_addendum` | 15 min |
| H39 | Electron Overlay | `main/index.ts`, `main/ipc.ts`, `main/shortcuts.ts`, `main/windows.ts` | Multiple | Overlay uses `hide()/show()` extensively instead of mandated `setOpacity(0/1)` | 30 min |
| H40 | Electron Overlay | `renderer/pill/Pill.tsx` | 258-268 | Memory leak: IPC listeners registered without cleanup | 15 min |
| H41 | Electron Overlay | `renderer/overlay/Overlay.tsx` | 189-203 | Memory leak: settings & navigate IPC listeners not properly cleaned up | 15 min |
| H42 | Electron Overlay | `renderer/settings/Settings.tsx` | 108-110 | Memory leak: theme change listener not cleaned up | 5 min |

### 🟡 MEDIUM (Fix Next Sprint)

| # | Domain | File | Line | Bug | Fix Complexity |
|---|--------|------|------|-----|----------------|
| M1 | Task System | `core/tasks.py` | 907-915 | DST gap bug: `_parse_due_time()` uses `datetime.replace()` which doesn't handle DST | 15 min |
| M2 | Task System | `core/tasks.py` | 843-852 | `_find_best_task_match()` over-matches on single-character queries | 10 min |
| M3 | Task System | `core/reminder_scheduler.py` | 305-312 | Reminder scheduler blocks asyncio loop on OpenRouter call | 15 min |
| M4 | Task System | `core/reminder_scheduler.py` | 202-216 | File watcher can miss rapid successive writes (1-sec mtime resolution) | 10 min |
| M5 | Task Classification | `core/task_classifier.py` | 165-170 | `classify()` breaks at first open task with shared subject, ignoring better matches | 15 min |
| M6 | Task Classification | `core/task_classifier.py` | 130 | `_strip_subject()` partially matches dotted domain names due to `\b` behavior | 10 min |
| M7 | Dictation | `core/dictation_smart.py` | ~125 | Multi-email garbling in `_replace_emails()` — overlapping span reconstruction | 10 min |
| M8 | Dictation | `core/dictation_smart.py` | ~200-220 | 3 symbol regexes are too loose (`hash`, `slash`, `star`) | 10 min |
| M9 | Dictation | `core/dictation_correction.py` | ~350 | `hash()` used for correction IDs — non-deterministic across runs | 5 min |
| M10 | Smart Paste | `core/smart_paste.py` | ~170 | `paste_via_hotkey()` is ~170 lines of platform spaghetti | 20 min |
| M11 | Smart Paste | `platforms/linux/system_access.py` | ~45 | `UnboundLocalError` in `cursor_position()` — `x, y` not initialized before try | 1 min |
| M12 | Agent Core | `core/agent.py` | 22 | `import keyboard` at top level crashes on Linux (requires root) | 5 min |
| M13 | Agent Core | `core/agent.py` | 324-329 | `_endpoint_reachable` causes false offline negatives (GET on API base path 404s) | 10 min |
| M14 | Agent Core | `core/agent.py` | 699 | `os.startfile(target)` is Windows-only; crashes on Linux | 5 min |
| M15 | Agent Core | `core/agent.py` | 477 | `call_llm` can raise `TypeError: exceptions must derive from BaseException` | 5 min |
| M16 | Agent Core | `core/agent.py` | 452 | API calls have no network timeout | 5 min |
| M17 | Agent Core | `core/agent.py` | 741-757 | `web_search` uses unreliable unofficial DuckDuckGo endpoint | 15 min |
| M18 | Agent Engine | `core/agent_engine.py` | ~520 | `intent_gate.py` imports `get_openrouter_client` from `agent_engine.py` but function doesn't exist | 5 min |
| M19 | Agent V2 | `core/agent_v2/phase_engine.py` | 95-105 | `advance()` increments `completed_count` as side effect of `can_step()` | 5 min |
| M20 | Agent V2 | `core/agent_v2/phase_engine.py` | 80-90 | `pause()` / `resume()` have no state guards (e.g., pausing a done engine) | 5 min |
| M21 | Agent V2 | `core/agent_v2/phase_engine.py` | 160-170 | `run_verification` subprocess has no timeout | 5 min |
| M22 | Agent V2 | `core/agent_v2/plan_executor.py` | ~350 | `can_step()` side-effect increments counter before boolean check | 5 min |
| M23 | Agent V2 | `core/agent_v2/plan_executor.py` | ~280 | `_git_checkpoint()` doesn't check `git add -A` return code | 5 min |
| M24 | Agent V2 | `core/agent_v2/plan_executor.py` | ~400 | `write_run_artifact()` is non-atomic | 5 min |
| M25 | Agent V2 | `core/agent_v2/models.py` | ~80 | Home-path regexes in `_BLOCKED_PATHS` don't match resolved absolute paths | 10 min |
| M26 | Background Agent | `core/background_agent.py` | 656-657 | Browser tasks never call `_cleanup_browser()` — finally block has inverted condition | 5 min |
| M27 | Background Agent | `core/background_agent.py` | 661-697 | `_execute_browser_task()` bypasses isolation, operates on foreground window | 20 min |
| M28 | Background Agent | `core/background_agent.py` | 591-601 | Race condition in `_process_queue()`: check outside lock, pop after releasing lock | 10 min |
| M29 | Background Agent | `core/agent_task_queue.py` | 114-123 | `save_task_to_log()` non-atomic RMW with no lock | 10 min |
| M30 | Background Agent | `core/background_agent.py` | 306-317 | Dead code `_execute_browser_planned_action` contains focus-theft via `SetForegroundWindow` | 5 min |
| M31 | Background Agent | `core/background_agent.py` | 113-143 | `_find_browser_path()` relies on `winreg` / hardcoded Windows paths; crashes on Linux | 10 min |
| M32 | Hotkeys | `core/hotkeys.py` | 375-386 | Unbounded `audio_frames` growth; no max recording duration guard | 10 min |
| M33 | Hotkeys | `core/hotkeys.py` | 1177-1180 | F9×2+ is documented as "toggle Agent mode" but is silent no-op (`pass`) | 5 min |
| M34 | Hotkeys | `core/hotkeys.py` | 1157-1181 | Hotkey entry points lack broad `try/except` — crash kills listener thread | 10 min |
| M35 | Hotkeys | `platforms/linux/hotkeys.py` | 55-82 | `_pressed` set accessed unsynchronized across threads | 10 min |
| M36 | WS Bridge | `core/ws_bridge.py` | 539 | Malformed JSON caught with bare `pass` — no logging | 1 min |
| M37 | WS Bridge | `core/ws_bridge.py` | 122-542 | Non-dict payloads cause `AttributeError` → client disconnect | 5 min |
| M38 | WS Bridge | `core/ws_bridge.py` | 614-627 | `broadcast_sync` prints on every invocation (~25 Hz for mic level) | 1 min |
| M39 | WS Bridge | `core/ws_bridge.py` | 1236-1250 | `send_pill_notice` treats `0` as falsy, forcing `2600` ms duration | 1 min |
| M40 | WS Bridge | `core/ws_bridge.py` | 904-909 | `_handle_task_confirm_reject` runs sync in WS coroutine; approve spawns thread | 5 min |
| M41 | FastAPI | `core/server.py` | 154-166 | `/tune` async handler performs blocking credit check + `process_tune()` + `deduct()` | 10 min |
| M42 | FastAPI | `core/server.py` | 528-556 | `/agent/project/{project_id}/approve` handles pause/resume despite name | 5 min |
| M43 | FastAPI | `core/server.py` | 288-296 | `/voice/dictate` sync handler calls `hk._on_f9_taps(1)` synchronously | 10 min |
| M44 | FastAPI | `core/server.py` | 229-238 | `/agent/undo` returns ad-hoc dict on exception instead of `HTTPException` | 5 min |
| M45 | FastAPI | `core/server.py` | 108-113 | `ProjectStartRequest.approval_mode` is plain `str` instead of constrained enum | 5 min |
| M46 | FastAPI | `core/server.py` | 203-227 | Settings file read/write has no file locking | 10 min |
| M47 | FastAPI | `core/server.py` | 460-506 | `project_id` derived from `uuid.uuid4().hex[:8]` has collision risk | 5 min |
| M48 | Guardrails | `core/guardrails.py` | 25-66 | Multiple regex bypasses for destructive actions (LOLBAS variants missing) | 15 min |
| M49 | Guardrails | `core/guardrails.py` | 145-151 | `scan_secrets()` defined but never called | 5 min |
| M50 | WizPrompt | `core/wizprompt.py` | 616-624 | `get_preset_by_id()` bare `except Exception` swallows all errors silently | 5 min |
| M51 | Electron Overlay | `tsconfig.node.json` | N/A | Includes renderer files; `npm run typecheck` fails with 30+ errors | 10 min |
| M52 | Electron Overlay | `renderer/overlay/Overlay.tsx` | 71, 448, 482 | Unsafe `as any` casts for CSS properties | 5 min |

### 🟢 LOW (Fix When Convenient)

| # | Domain | File | Line | Bug | Fix Complexity |
|---|--------|------|------|-----|----------------|
| L1 | Task System | `core/tasks.py` | 180-183 | `history` array grows unbounded on disk | 10 min |
| L2 | Task System | `core/tasks.py` | 735-744 | `_IMPLICIT_PATTERNS` compiled but never referenced (dead code) | 1 min |
| L3 | Task System | `core/tasks.py` | 1249 | `parse_task_command()` prepends "by " unconditionally for reschedule | 1 min |
| L4 | Task System | `core/tasks.py` | 512 | `edit_task_fields()` silently rejects `"in_progress"` status | 1 min |
| L5 | Task System | `core/tasks.py` | 596-605 | `is_snoozed()` silently swallows `TypeError` for naive datetimes | 5 min |
| L6 | Task Categorizer | `core/task_categorizer.py` | 51-56 | No tie-breaker when two categories score equally | 5 min |
| L7 | Memory | `core/memory.py` | 66 | `_ask_permission()` uses interactive `input()` in headless backend | 5 min |
| L8 | Memory | `core/agent.py` | 46, 193 | Relative `data_dir` resolved at global import time (CWD-dependent) | 5 min |
| L9 | Dictation | `core/dictation_memory.py` | Multiple | Bare `except Exception: pass` in multiple places | 5 min |
| L10 | Dictation | `core/dictation_correction.py` | Multiple | Bare `except Exception: pass` in multiple places | 5 min |
| L11 | Smart Paste | `core/smart_paste.py` | ~45 | Bare `except Exception: pass` in clipboard verification | 1 min |
| L12 | Smart Paste | `core/smart_paste.py` | ~220 | `self.last_paste_text` never set; `get_last_paste()` always returns `None` | 1 min |
| L13 | Agent Core | `core/agent.py` | 536-541 | Side effects at module import time (`_load_conversation_history`) | 10 min |
| L14 | Agent V2 | `core/agent_v2/master_planner.py` | ~45 | `detect_stack()` string-sniffs `package.json` instead of using `json.loads` | 5 min |
| L15 | Agent V2 | `core/agent_v2/master_planner.py` | ~60 | No guard clauses for empty `project_id`/`description` | 5 min |
| L16 | Agent V2 | `core/agent_v2/master_planner.py` | ~80 | `self_optimize_plan()` is a stub that returns unchanged plan | 10 min |
| L17 | Background Agent | `core/background_agent.py` | 1066-1071 | `stop_background_agent()` doesn't use `try/finally` for cleanup | 1 min |
| L18 | Background Agent | `core/agent_isolation.py` | 205-207 | `press_key_in_window` maps chars via `ord()` — wrong for symbols | 10 min |
| L19 | Background Agent | `core/agent_isolation.py` | 248-262 | `find_window_by_pid` weak heuristic (first visible window) | 10 min |
| L20 | Background Agent | `core/background_agent.py` | 600 | Uses deprecated `asyncio.ensure_future()` instead of `asyncio.create_task()` | 1 min |
| L21 | Hotkeys | `core/hotkeys.py` | 1666-1671 | `register_hotkeys()` docstring claims "Windows-side only" but called on all platforms | 1 min |
| L22 | WS Bridge | `core/ws_bridge.py` | 72-88 | Handshake push failures don't disconnect client explicitly | 5 min |
| L23 | FastAPI | `core/server.py` | 124-133 | `/status` returns hardcoded `latency: 18` and tier `"pro"` | 5 min |
| L24 | Guardrails | `core/guardrails.py` | 113-121 | `pixel_diff_score()` is dead code (defined but never called) | 1 min |
| L25 | Electron Overlay | `renderer/pill/Pill.tsx` | 652-670 | Pill edge listener leak | 5 min |
| L26 | Electron Overlay | `main/bridge.ts` | 56-64 | `closeBridge()` doesn't clear `pendingQueue` | 1 min |
| L27 | Electron Overlay | `renderer/overlay/useTasks.ts` | 20-32 | Dual-path refresh is redundant | 5 min |
| L28 | Electron Overlay | `main/ipc.ts` | 19 | `memoryPanel` not closed by `closeAuxiliaryWindows()` | 5 min |
| L29 | Electron Overlay | `main/index.ts` | 163-168 | Pill reload listener uses `.on` instead of `.once` | 1 min |
| L30 | Electron Overlay | `main/windows.ts` | 238-261 | Blur auto-hide contradicts Linux persistent-HUD rule | 5 min |
| L31 | Electron Overlay | `main/ipc.ts` | 450-469 | Task panel `show()` without display bounds validation | 5 min |
| L32 | Electron Overlay | `main/ipc.ts` | 94-109 | `syncTaskPanels` only sends theme, not task data | 10 min |
| L33 | Naming | `core/task_categorizer.py` | 23 | Still contains legacy `"whiztant"` string | 1 min |
| L34 | Platform | `platforms/linux/system_access.py` | 164-230 | Screenshot 7-fallback chain is fragile; `scrot` deprecated, `ffmpeg` may hang | 15 min |
| L35 | Platform | `platforms/windows/system_access.py` | 62-66 | `take_screenshot()` has zero fallbacks; crashes if `mss` fails | 10 min |
| L36 | Platform | `core/vlm.py` | 27-31 | Unconditionally imports `platforms.linux._vlm_impl` with no `sys.platform` guard | 5 min |
| L37 | Platform | `platforms/linux/system_access.py` | 286-329 | `type_text()` passes raw text to xdotool without shell escaping | 5 min |
| L38 | Platform | `platforms/linux/system_access.py` | 445-456 | `launch_app()` breaks on app paths containing spaces | 5 min |
| L39 | Platform | `core/platform_backends.py` | 163-164 | `platform_name()` duplicates factory logic with different behavior | 5 min |
| L40 | Platform | Various | — | Inconsistent mss monitor indexing (`monitors[0]` vs `monitors[1]`) | 5 min |

---

## Cross-Domain Dependencies & Deduplication

### Dependency Graph (Fix Order Matters)

```
Wave 1: Test Infrastructure
  └─> Unblocks running all other tests

Wave 2: Ghost Dependencies + Dead Code
  └─> Remove references to deleted modules
  └─> Delete stale duplicate files

Wave 3: Safety & Guardrails
  └─> Fix path sandboxing in agent tools
  └─> Integrate v2 guardrails into active runtime
  └─> Fix coordinate validation

Wave 4: Concurrency & Atomicity
  └─> Fix file write races (tasks.json, memory.json)
  └─> Fix thread-safety in hotkeys, WS bridge, background agent

Wave 5: Async/Sync Mismatch
  └─> Fix blocking calls in async handlers (server.py, ws_bridge.py)

Wave 6: Electron Overlay
  └─> Fix memory leaks, IPC cleanup, setOpacity pattern
  └─> Fix typecheck config

Wave 7: Polish & UX
  └─> All remaining low-severity bugs
```

### Deduplicated Cross-Cutting Issues

1. **Missing `sys.path.insert` in tests** — Affects 7 test files. Fixed by adding `tests/conftest.py` (one file fixes all) OR adding guards to each file.
2. **Bare `except Exception: pass`** — Found in dictation, memory, agent, ws_bridge, smart_paste. Systematic replacement with `logging.warning()` or narrowed exceptions.
3. **Non-atomic file writes** — Found in `core/tasks.py`, `core/memory.py`, `core/agent.py`, `core/agent_v2/memory.py`, `core/agent_task_queue.py`. Standardize on `tmp + os.replace` pattern.
4. **Unbounded collection growth** — Found in `core/tasks.py` (history), `core/agent.py` (tasks, undo_stack), `core/dictation_correction.py` (undo_hooks). Add caps.
5. **Async/sync mismatch** — Found in `core/server.py`, `core/ws_bridge.py`, `core/agent_unified.py`. Wrap blocking calls in `asyncio.to_thread()`.
6. **Memory leaks (Electron)** — Found in Pill.tsx, Overlay.tsx, Settings.tsx. Add `removeListener` cleanup in useEffect.

---

## Execution Waves

### Wave 1: Foundation (Test Infrastructure + Ghost Dependencies)
**Goal:** Make the test suite runnable and remove crashing references to missing modules.

#### Task 1.1: Add `tests/conftest.py`
**Files:**
- Create: `tests/conftest.py`

**Steps:**
- [ ] Create `tests/conftest.py` with `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
- [ ] Run `pytest tests/ --co -q` and verify 0 collection errors
- [ ] Run `pytest tests/ -q` and verify tests run (may still have failures, but no collection errors)

#### Task 1.2: Fix remaining test files that lack `sys.path` guards (backup)
**Files:**
- Modify: `tests/test_task_classifier.py`
- Modify: `tests/stt_tests/test_integration.py`
- Modify: `tests/stt_tests/test_refiner.py`
- Modify: `tests/stt_tests/test_smart_paste.py`
- Modify: `tests/stt_tests/test_vocab.py`
- Modify: `tests/stt_tests/test_dictation_edge_cases.py`
- Modify: `tests/test_agent_shared.py`

**Steps:**
- [ ] Add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` at top of each file (before any `from core import`)
- [ ] Run each file individually with `pytest <file> -v` to verify collection succeeds

#### Task 1.3: Remove ghost dependencies
**Files:**
- Modify: `core/background_agent.py` (remove `SystemTaskExecutor` and `ActionOptimizer` imports)
- Modify: `core/agent.py` (remove `core.wiztype.custom_model` references)
- Modify: `core/agent_engine.py` (remove duplicate constants)

**Steps:**
- [ ] In `core/background_agent.py`, replace missing imports with `NotImplementedError` stubs or remove usage
- [ ] In `core/agent.py`, remove `_get_custom_client()` and `get_model()` wiztype references
- [ ] In `core/agent_engine.py`, remove duplicate `DEFAULT_TIMEOUT` definition
- [ ] Run `python -c "import main"` to verify no import errors

#### Task 1.4: Delete stale duplicate files
**Files:**
- Delete: `core/shared/guardrails.py` (if truly unused)

**Steps:**
- [ ] Verify zero imports of `core.shared.guardrails` via `grep -r "from core.shared import guardrails"` or similar
- [ ] Delete file
- [ ] Run `python -c "import main"`

---

### Wave 2: Safety & Guardrails
**Goal:** Prevent destructive actions, fix coordinate validation, close security holes.

#### Task 2.1: Fix `tool_write_file` path sandboxing
**Files:**
- Modify: `core/agent.py` (around line 723-732)

**Steps:**
- [ ] Import `sandbox_path` from `core.agent_v2.guardrails`
- [ ] Call `sandbox_path(path)` before writing in `tool_write_file`
- [ ] Call `validate_path(path)` before reading in `tool_read_file`
- [ ] Write test verifying rejection of `/etc/passwd`

#### Task 2.2: Fix `run_command` guardrails
**Files:**
- Modify: `core/agent.py` (around line 679)

**Steps:**
- [ ] Import `is_destructive_command` from `core.guardrails` (or v2)
- [ ] Check command with `is_destructive_command` before `subprocess.run(..., shell=True)`
- [ ] Return blocked message if destructive

#### Task 2.3: Fix coordinate validation in `agent_unified.py`
**Files:**
- Modify: `core/agent_unified.py` (around lines 307, 311-315)

**Steps:**
- [ ] Expand action type check to include `double_click`, `right_click`, `drag`
- [ ] Change `break` to `return f"Blocked: {coord_reason}"` for invalid coordinates
- [ ] Validate against actual screen dimensions after `_translate_coords`, not normalized 0-1000

#### Task 2.4: Fix loop detection empty-bytes bug
**Files:**
- Modify: `platforms/linux/_vlm_impl.py` (around line 677)
- Modify: `platforms/windows/_vlm_impl.py` (around line 2005)

**Steps:**
- [ ] Convert PIL Image to bytes before hashing (e.g., `.tobytes()` or save to BytesIO)
- [ ] Remove `else b""` fallback that causes false-positive loop detection

#### Task 2.5: Integrate v2 guardrails patterns into active guardrails
**Files:**
- Modify: `core/guardrails.py`

**Steps:**
- [ ] Copy the 60+ destructive patterns from `core/agent_v2/guardrails.py` into `core/guardrails.py`
- [ ] Ensure `scan_secrets()` is called in LLM input/output logging path, or remove if unused

---

### Wave 3: Concurrency & Data Integrity
**Goal:** Fix race conditions, non-atomic writes, and cross-process file corruption.

#### Task 3.1: Add `threading.Lock` to `core/tasks.py`
**Files:**
- Modify: `core/tasks.py`

**Steps:**
- [ ] Add module-level `_tasks_lock = threading.Lock()`
- [ ] Wrap `_load()` → mutate → `_save()` sequences with `with _tasks_lock:`
- [ ] Run `pytest tests/test_tasks.py -v` to verify no regressions

#### Task 3.2: Fix non-atomic writes in `core/memory.py`
**Files:**
- Modify: `core/memory.py`

**Steps:**
- [ ] Change `_save()` to use temp-file + `os.replace()` pattern (copy from `core/agent_v2/memory.py`)
- [ ] Use `_lock` consistently in `_ensure_loaded()` and `_save()`
- [ ] Narrow exception handling in `_read_memory_file()` — don't swallow all errors silently

#### Task 3.3: Fix non-atomic writes in `core/agent.py` (`AgentMemory`)
**Files:**
- Modify: `core/agent.py`

**Steps:**
- [ ] Change `AgentMemory._save_history()` to use temp-file + `os.replace()`
- [ ] Narrow exception handling

#### Task 3.4: Add file locking for cross-process safety
**Files:**
- Modify: `core/tasks.py`
- Modify: `core/memory.py`
- Modify: `core/server.py`

**Steps:**
- [ ] Add `filelock` to `requirements.txt` if not present
- [ ] Use `FileLock` around `tasks.json` and `memory.json` reads/writes
- [ ] Use `FileLock` around `data/settings.json` read/writes in `core/server.py`

#### Task 3.5: Fix Electron `buildTask()` field stripping
**Files:**
- Modify: `ui/whiztant-overlay/src/main/ipc.ts` (around lines 74-92)

**Steps:**
- [ ] Add missing fields to TypeScript `Task` interface: `snoozed_until`, `category`, `difficulty`, `progress`, `reminder_sent`
- [ ] Ensure `buildTask()` preserves these fields from incoming data
- [ ] Run `npm run build` in `ui/whiztant-overlay/`

---

### Wave 4: Async/Sync Mismatch
**Goal:** Prevent event loop blocking in async handlers.

#### Task 4.1: Fix `/agent/run` blocking call
**Files:**
- Modify: `core/server.py` (around line 185)

**Steps:**
- [ ] Wrap `agent_module.ask_ai(...)` in `await asyncio.to_thread(agent_module.ask_ai, ...)`
- [ ] Verify endpoint still works

#### Task 4.2: Fix `/tune` blocking calls
**Files:**
- Modify: `core/server.py` (around lines 154-166)

**Steps:**
- [ ] Wrap `process_tune()` and `deduct()` in `asyncio.to_thread()`

#### Task 4.3: Fix `/voice/dictate` blocking call
**Files:**
- Modify: `core/server.py` (around lines 288-296)

**Steps:**
- [ ] Make endpoint async
- [ ] Offload `hk._on_f9_taps(1)` to background thread/task

#### Task 4.4: Fix `run_unified_agent` async-in-name-only
**Files:**
- Modify: `core/agent_unified.py`

**Steps:**
- [ ] Identify all blocking operations (screenshots, HTTP, sleep, platform I/O)
- [ ] Wrap each in `asyncio.to_thread()` or use async-native equivalents
- [ ] Add timeout to `call_api()` in `agent_engine.py`

#### Task 4.5: Fix reminder scheduler blocking OpenRouter call
**Files:**
- Modify: `core/reminder_scheduler.py` (around lines 305-312)

**Steps:**
- [ ] Make suggestion generation async or cached
- [ ] Skip LLM suggestion inside scheduler's tight loop

---

### Wave 5: Electron Overlay
**Goal:** Fix memory leaks, IPC cleanup, and DWM performance.

#### Task 5.1: Replace `hide()/show()` with `setOpacity(0/1)`
**Files:**
- Modify: `ui/whiztant-overlay/src/main/index.ts`
- Modify: `ui/whiztant-overlay/src/main/ipc.ts`
- Modify: `ui/whiztant-overlay/src/main/shortcuts.ts`
- Modify: `ui/whiztant-overlay/src/main/windows.ts`

**Steps:**
- [ ] Find all `.hide()` and `.show()` calls on BrowserWindow instances
- [ ] Replace `.hide()` with `.setOpacity(0)`
- [ ] Replace `.show()` with `.setOpacity(1)` + `.focus()` if needed
- [ ] Ensure windows are created with `show: true` so opacity is the only gate
- [ ] Run `npm run build`

#### Task 5.2: Fix IPC memory leaks in renderer
**Files:**
- Modify: `ui/whiztant-overlay/src/preload/index.ts`
- Modify: `ui/whiztant-overlay/src/renderer/pill/Pill.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/overlay/Overlay.tsx`
- Modify: `ui/whiztant-overlay/src/renderer/settings/Settings.tsx`

**Steps:**
- [ ] Change preload API to return unsubscribe functions: `onX(cb) => () => ipcRenderer.off(channel, cb)`
- [ ] Update all `useEffect` hooks to call unsubscribe in cleanup
- [ ] Run `npm run build`

#### Task 5.3: Fix `tsconfig.node.json`
**Files:**
- Modify: `ui/whiztant-overlay/tsconfig.node.json`

**Steps:**
- [ ] Exclude `src/renderer/**` from `tsconfig.node.json`
- [ ] Run `npm run typecheck` and verify 0 errors

#### Task 5.4: Fix Linux blur auto-hide contradiction
**Files:**
- Modify: `ui/whiztant-overlay/src/main/windows.ts`

**Steps:**
- [ ] Add `process.platform !== 'linux'` guard to blur handler
- [ ] Run `npm run build`

---

### Wave 6: STT, Dictation, Hotkeys
**Goal:** Fix voice pipeline bugs and input system races.

#### Task 6.1: Add missing `import subprocess` to `core/stt_engine.py`
**Files:**
- Modify: `core/stt_engine.py`

**Steps:**
- [ ] Add `import subprocess` at module level

#### Task 6.2: Remove double `clean_transcript` in hotkeys
**Files:**
- Modify: `core/hotkeys.py`

**Steps:**
- [ ] Remove redundant `clean_transcript` call when `_was_streaming` is True

#### Task 6.3: Fix dictation symbol regexes
**Files:**
- Modify: `core/dictation_smart.py`

**Steps:**
- [ ] Tighten `hash`, `slash`, `star` regexes with word boundaries / negative lookarounds
- [ ] Fix multi-email garbling in `_replace_emails()`

#### Task 6.4: Fix Linux combo shortcut logic
**Files:**
- Modify: `platforms/linux/hotkeys.py`

**Steps:**
- [ ] Verify non-modifier key is in `_pressed` set before firing combo
- [ ] Add `threading.Lock()` around `_pressed` mutations

#### Task 6.5: Add recording duration guard
**Files:**
- Modify: `core/hotkeys.py`

**Steps:**
- [ ] Add 60-second auto-stop timer in `start_recording()`

---

### Wave 7: Polish & Remaining Bugs
**Goal:** Fix all remaining medium and low severity issues.

#### Task 7.1: Cap unbounded collections
**Files:**
- Modify: `core/tasks.py` (cap history to 200)
- Modify: `core/agent.py` (cap tasks to 100, undo_stack to 50)
- Modify: `core/dictation_correction.py` (cap undo_hooks, use `hashlib.md5`)

#### Task 7.2: Fix TuneHub credit issues
**Files:**
- Modify: `core/tune_hub/orchestrator.py` (add refund on failure, fix `TuneResult` schema)
- Modify: `core/tune_hub/credit_system/credit_tracker.py` (wire to real credit system)

#### Task 7.3: Fix WizPrompt preset validation
**Files:**
- Modify: `core/wizprompt.py`
- Modify: `core/presets.py`

**Steps:**
- [ ] Add validation for user preset `system_prompt_addendum`
- [ ] Narrow exception handling in `get_preset_by_id()`

#### Task 7.4: Fix TopTabBar labels
**Files:**
- Modify: `ui/whiztant-overlay/src/renderer/overlay/TopTabBar.tsx`

**Steps:**
- [ ] Change labels to match AGENTS.md spec: "Chat", "Today", "Agent"

#### Task 7.5: Fix remaining WS Bridge issues
**Files:**
- Modify: `core/ws_bridge.py`

**Steps:**
- [ ] Add `if _loop is None: return` to agent event helpers
- [ ] Clamp mic level with `math.isfinite()`
- [ ] Replace `broadcast_sync` print with debug flag
- [ ] Add `if not isinstance(msg, dict): continue` after `json.loads`

#### Task 7.6: Fix FastAPI remaining issues
**Files:**
- Modify: `core/server.py`

**Steps:**
- [ ] Standardize error responses on `HTTPException`
- [ ] Add Pydantic models for `/settings/task_ai_enabled`, `/credits/calculate`
- [ ] Tighten CORS origins
- [ ] Add `asyncio.Lock` around `_agent_v2_engines`

#### Task 7.7: Fix Agent V2 state machine
**Files:**
- Modify: `core/agent_v2/phase_engine.py`
- Modify: `core/agent_v2/plan_executor.py`

**Steps:**
- [ ] Add state guards to `advance()`, `pause()`, `resume()`
- [ ] Separate `can_step()` boolean check from counter increment
- [ ] Add timeout to `run_verification` subprocess

#### Task 7.8: Fix Background Agent issues
**Files:**
- Modify: `core/background_agent.py`

**Steps:**
- [ ] Fix browser cleanup gate (remove `!= "browser"` or invert)
- [ ] Fix `_process_queue()` race (extend critical section)
- [ ] Add Linux platform gate to prevent initialization
- [ ] Delete dead code `_execute_browser_planned_action`

#### Task 7.9: Fix DST bug in tasks
**Files:**
- Modify: `core/tasks.py`

**Steps:**
- [ ] Use `zoneinfo` / `pytz` normalize instead of `datetime.replace()` for time shifts

#### Task 7.10: Fix Agent Core `os.startfile` Windows-only issue
**Files:**
- Modify: `core/agent.py`

**Steps:**
- [ ] Add `hasattr(os, 'startfile')` guard or use `subprocess.Popen` fallback in `try/except AttributeError`

#### Task 7.11: Fix Platform Abstraction issues
**Files:**
- Modify: `core/vlm.py`
- Modify: `platforms/windows/system_access.py`
- Modify: `platforms/linux/system_access.py`
- Modify: `core/platform_backends.py`

**Steps:**
- [ ] In `core/vlm.py`, make `_vlm_impl` import conditional on `sys.platform`
- [ ] In `platforms/windows/system_access.py`, add screenshot fallbacks (`PIL.ImageGrab.grab()`, `pyautogui.screenshot()`)
- [ ] In `platforms/linux/system_access.py`, add `shlex.quote(text)` around xdotool/wtype/ydotool input
- [ ] In `platforms/linux/system_access.py`, use `shlex.split(cmd)` or `shell=True` in `launch_app()` for paths with spaces
- [ ] Standardize mss monitor indexing across all screenshot callers
- [ ] Delete or merge `platform_name()` duplicate from `core/platform_backends.py`

---

## Verification Checklist

After each wave:
1. `python -c "import main"` — must pass without errors
2. `pytest tests/ --co -q` — must show 0 collection errors
3. `pytest tests/ -q` — must run all tests (failures noted but no crashes)
4. `npm run typecheck` in `ui/whiztant-overlay/` — must pass
5. `npm run build` in `ui/whiztant-overlay/` — must pass
6. Check `data/agent_debug.log` for new errors after running

---

## Definition of Done

- [ ] All 23 test collection errors resolved
- [ ] All Critical and High bugs fixed or explicitly deferred with justification
- [ ] `python -c "import main"` passes
- [ ] `pytest tests/` runs without collection errors
- [ ] `npm run build` in `ui/whiztant-overlay/` succeeds
- [ ] `npm run typecheck` in `ui/whiztant-overlay/` succeeds
- [ ] No new ghost dependencies introduced
- [ ] Cross-domain deduplication items addressed
