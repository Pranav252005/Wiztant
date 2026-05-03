"""
Whiztant core/ws_bridge.py — WebSocket bridge for Electron overlay IPC.

Runs a lightweight WebSocket server on localhost:9120 that the Electron
overlay connects to. Relays messages between the Python backend and the
overlay UI in real time.

Protocol:
  Python → Overlay:  {"type": "history", "messages": [...]}
                     {"type": "wave_state", "state": "idle|thinking|speaking|agent"}
                     {"type": "agent_step", "step": 1, "total": 5, "text": "..."}
  Overlay → Python:  {"type": "send_message", "text": "user message"}
                     {"type": "stop_agent"}
"""

import json
import asyncio
import threading
from datetime import datetime
from typing import Set, Optional, Dict

from ui.agent_confirmation_overlay import get_agent_confirmation_overlay

WS_PORT = 9120
_server_thread: Optional[threading.Thread] = None
_server_lock = threading.Lock()
_clients: Set = set()
_loop: Optional[asyncio.AbstractEventLoop] = None

# ── Agent interactive question store ─────────────────────────────────────────
_pending_questions: Dict[str, threading.Event] = {}
_question_answers: Dict[str, str] = {}
_question_lock = threading.Lock()


def _set_question_answer(question_id: str, answer: str) -> None:
    """Store an answer and signal any waiter."""
    with _question_lock:
        _question_answers[question_id] = answer
        evt = _pending_questions.get(question_id)
        if evt:
            evt.set()


def wait_for_agent_answer(question_id: str, timeout: float = 60.0) -> Optional[str]:
    """Block until the user answers a question (or timeout). Thread-safe."""
    evt = threading.Event()
    with _question_lock:
        _pending_questions[question_id] = evt
        # If answer already arrived before we started waiting
        if question_id in _question_answers:
            return _question_answers.pop(question_id, None)

    ok = evt.wait(timeout=timeout)
    with _question_lock:
        _pending_questions.pop(question_id, None)
        return _question_answers.pop(question_id, None) if ok else None


async def _handler(websocket):
    """Handle a single WebSocket client connection."""
    _clients.add(websocket)
    print(f"[WsBridge] Client connected ({len(_clients)} total)")

    # Send current conversation history on connect
    try:
        import core as state
        history = getattr(state, "conversation_history", [])
        # If history was wiped by a module reload, attempt to restore from disk.
        if not history:
            try:
                from core.agent import _load_conversation_history
                restored = _load_conversation_history()
                if restored:
                    state.conversation_history = restored
                    history = restored
            except Exception:
                pass
        await websocket.send(json.dumps({
            "type": "history",
            "messages": [
                {"role": m.get("role", ""), "content": m.get("content", "")}
                for m in history
                if m.get("content", "").strip() and len(m.get("content", "")) < 5000
            ]
        }))

        try:
            from core.tasks import get_task_snapshot
            snapshot = get_task_snapshot()
            await websocket.send(json.dumps({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            }))
        except Exception as task_error:
            print(f"[WsBridge] Initial tasks send error: {task_error}")

        try:
            from core.dictation_memory import get_memories
            memories = get_memories(limit=50)
            await websocket.send(json.dumps({
                "type": "dictation_memories/update",
                "memories": memories,
            }))
        except Exception as mem_error:
            print(f"[WsBridge] Initial memories send error: {mem_error}")

        try:
            import os
            settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
            settings_data = {}
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
            await websocket.send(json.dumps({
                "type": "settings/update",
                "settings": settings_data,
            }))
        except Exception as settings_error:
            print(f"[WsBridge] Initial settings send error: {settings_error}")

        confirmation_snapshot = get_agent_confirmation_overlay().get_bridge_snapshot()
        if confirmation_snapshot:
            await websocket.send(json.dumps(confirmation_snapshot))
    except Exception as e:
        print(f"[WsBridge] History send error: {e}")

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "send_message":
                    text = msg.get("text", "").strip()
                    if text:
                        _handle_user_message(text)

                elif msg_type == "send_agent_task":
                    text = msg.get("text", "").strip()
                    if text:
                        _handle_agent_task(text)

                elif msg_type == "stop_agent":
                    import core as state
                    if getattr(state, "_agent_stop_event", None):
                        state._agent_stop_event.set()

                elif msg_type == "confirmation_response":
                    choice = str(msg.get("choice", "cancel") or "cancel")
                    get_agent_confirmation_overlay().on_user_choice(choice)

                elif msg_type == "tasks/add":
                    _handle_tasks_add(msg)

                elif msg_type == "tasks/toggle_status":
                    _handle_tasks_toggle(msg)

                elif msg_type == "tasks/delete":
                    _handle_tasks_delete(msg)

                elif msg_type == "tasks/edit":
                    _handle_tasks_edit(msg)

                elif msg_type == "tasks/reschedule":
                    _handle_tasks_reschedule(msg)

                elif msg_type == "tasks/refresh":
                    _handle_tasks_refresh(msg)

                elif msg_type == "tasks/snooze":
                    _handle_tasks_snooze(msg)

                elif msg_type == "tasks/settings/set":
                    await _handle_tasks_settings_set(websocket, msg)

                elif msg_type == "tasks/settings/get":
                    await _handle_tasks_settings_get(websocket)

                elif msg_type == "vocab_add":
                    _handle_vocab_add(msg)

                elif msg_type == "agent/undo":
                    _handle_agent_undo(msg)

                elif msg_type == "agent/answer":
                    question_id = str(msg.get("question_id", ""))
                    choice = str(msg.get("choice", ""))
                    if question_id and choice:
                        _set_question_answer(question_id, choice)

                elif msg_type == "save_session":
                    _handle_save_session(msg)

                elif msg_type == "hotkey":
                    _handle_hotkey(msg)

                elif msg_type == "request_insights":
                    try:
                        from core.insights_tracker import load_insights
                        data = load_insights()
                        lifetime = data.get("lifetime", {})
                        today = datetime.now().strftime("%Y-%m-%d")
                        daily_today = data.get("daily", {}).get(today, {})
                        await websocket.send(json.dumps({
                            "type": "insights_update",
                            "payload": {
                                "total_words_dictated": lifetime.get("total_words_dictated", 0),
                                "total_fixes_made": lifetime.get("total_fixes_made", 0),
                                "total_words_removed": lifetime.get("total_words_removed", 0),
                                "dictionary_items_used": lifetime.get("dictionary_items_used", 0),
                                "work_messages": lifetime.get("work_messages", 0),
                                "ai_prompts": lifetime.get("ai_prompts", 0),
                                "personal_messages": lifetime.get("personal_messages", 0),
                                "documents_touched": lifetime.get("documents_touched", 0),
                                "voice_commands": lifetime.get("voice_commands", 0),
                                "other_tasks": lifetime.get("other_tasks", 0),
                                "apps_used": lifetime.get("apps_used", 0),
                                "current_streak": data.get("current_streak", 0),
                                "longest_streak": data.get("longest_streak", 0),
                                "today": daily_today,
                            }
                        }))
                    except Exception as e:
                        print(f"[WsBridge] request_insights error: {e}")

                elif msg_type == "request_supabase_status":
                    try:
                        import os
                        url = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")).strip()
                        key = os.getenv("SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_ANON_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))).strip()
                        from core.supabase_client import is_configured
                        await websocket.send(json.dumps({
                            "type": "supabase_status",
                            "configured": is_configured(),
                            "url": url,
                            "key_prefix": key[:4] + "..." if len(key) > 4 else (key or ""),
                        }))
                    except Exception as e:
                        print(f"[WsBridge] request_supabase_status error: {e}")

                elif msg_type == "reload_env":
                    try:
                        from core.supabase_client import reload_client
                        client = reload_client()
                        status = "ok" if client else "failed"
                        await websocket.send(json.dumps({
                            "type": "env_reloaded",
                            "status": status,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] reload_env error: {e}")

                elif msg_type == "dictation_memories/get":
                    try:
                        from core.dictation_memory import get_memories
                        limit = msg.get("limit", 50)
                        mode = msg.get("mode")
                        memories = get_memories(limit=limit, mode=mode)
                        await websocket.send(json.dumps({
                            "type": "dictation_memories/update",
                            "memories": memories,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] dictation_memories/get error: {e}")

                elif msg_type == "dictation_preview/confirm":
                    _handle_dictation_preview_confirm(msg)

                elif msg_type == "dictation_preview/optimize":
                    _handle_dictation_preview_optimize(msg)

                elif msg_type == "dictation_preview/cancel":
                    # No-op on Python side; pill just closes the preview
                    pass

                elif msg_type == "learn_from_edit":
                    try:
                        from core.learning_agent import learn_from_edit
                        original = msg.get("original", "")
                        corrected = msg.get("corrected", "")
                        learned = learn_from_edit(original, corrected)
                        if learned:
                            await websocket.send(json.dumps({
                                "type": "learn_from_edit/result",
                                "learned": learned,
                            }))
                    except Exception as e:
                        print(f"[WsBridge] learn_from_edit error: {e}")

                elif msg_type == "dictation_memories/edit":
                    try:
                        from core.dictation_memory import update_memory, get_memories
                        entry_id = msg.get("id", "")
                        final_text = msg.get("final_text", "")
                        original_text = msg.get("original_text")
                        ok = update_memory(entry_id, final_text, original_text)
                        if ok:
                            broadcast_sync({
                                "type": "dictation_memories/update",
                                "memories": get_memories(limit=50),
                            })
                        await websocket.send(json.dumps({
                            "type": "dictation_memories/edited",
                            "id": entry_id,
                            "ok": ok,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] dictation_memories/edit error: {e}")

                elif msg_type == "dictation_memories/delete":
                    try:
                        from core.dictation_memory import delete_memory, get_memories
                        entry_id = msg.get("id", "")
                        ok = delete_memory(entry_id)
                        if ok:
                            broadcast_sync({
                                "type": "dictation_memories/update",
                                "memories": get_memories(limit=50),
                            })
                        await websocket.send(json.dumps({
                            "type": "dictation_memories/deleted",
                            "id": entry_id,
                            "ok": ok,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] dictation_memories/delete error: {e}")

                elif msg_type == "settings/get":
                    try:
                        import json as _json
                        import os
                        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
                        data = {}
                        if os.path.exists(settings_path):
                            with open(settings_path, "r", encoding="utf-8") as f:
                                data = _json.load(f)
                        await websocket.send(json.dumps({
                            "type": "settings/update",
                            "settings": data,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] settings/get error: {e}")

                elif msg_type == "settings/set":
                    try:
                        import json as _json
                        import os
                        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
                        key = msg.get("key", "")
                        value = msg.get("value")
                        data = {}
                        if os.path.exists(settings_path):
                            with open(settings_path, "r", encoding="utf-8") as f:
                                data = _json.load(f)
                        data[key] = value
                        with open(settings_path, "w", encoding="utf-8") as f:
                            _json.dump(data, f, indent=2)
                        await websocket.send(json.dumps({
                            "type": "settings/update",
                            "settings": data,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] settings/set error: {e}")

                elif msg_type == "features/update":
                    try:
                        import sys
                        from app.main import update_feature_flags
                        incoming = msg.get("features", {})
                        if isinstance(incoming, dict):
                            updated = update_feature_flags(incoming)
                            # Broadcast to all clients so they stay in sync
                            broadcast_sync({
                                "type": "features/update",
                                "features": updated,
                            })
                        else:
                            await websocket.send(json.dumps({
                                "type": "features/update",
                                "features": {},
                                "error": "Invalid features payload",
                            }))
                    except Exception as e:
                        print(f"[WsBridge] features/update error: {e}")

                elif msg_type == "features/get":
                    try:
                        from app.main import get_feature_flags
                        flags = get_feature_flags()
                        await websocket.send(json.dumps({
                            "type": "features/update",
                            "features": flags,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] features/get error: {e}")

                # ── Tune Hub ─────────────────────────────────────────────
                elif msg_type == "tunehub/stats":
                    try:
                        import core as _core_state
                        middleware = getattr(_core_state, "tune_middleware", None)
                        user_id = msg.get("user_id", _get_local_user_id())
                        if middleware:
                            stats = middleware.get_stats(user_id)
                            await websocket.send(json.dumps({
                                "type": "tunehub/stats",
                                "stats": stats,
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "tunehub/stats",
                                "stats": {"total_tunes": 0, "active_tunes": 0, "features_with_tunes": []},
                            }))
                    except Exception as e:
                        print(f"[WsBridge] tunehub/stats error: {e}")

                elif msg_type == "tunehub/list":
                    try:
                        import core as _core_state
                        hub = getattr(_core_state, "tune_hub", None)
                        user_id = msg.get("user_id", _get_local_user_id())
                        feature_name = msg.get("feature_name")
                        if hub:
                            tunes = hub.list_tunes(user_id, feature_name)
                            await websocket.send(json.dumps({
                                "type": "tunehub/list",
                                "tunes": [t.to_storage_format() for t in tunes],
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "tunehub/list",
                                "tunes": [],
                            }))
                    except Exception as e:
                        print(f"[WsBridge] tunehub/list error: {e}")

                elif msg_type == "tunehub/credits":
                    try:
                        import core as _core_state
                        hub = getattr(_core_state, "tune_hub", None)
                        user_id = msg.get("user_id", _get_local_user_id())
                        if hub:
                            balance = hub.credit_tracker.get_balance(user_id)
                            await websocket.send(json.dumps({
                                "type": "tunehub/credits",
                                "credits": {
                                    "available": balance.available,
                                    "consumed": balance.consumed,
                                    "reserved": balance.reserved,
                                },
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "tunehub/credits",
                                "credits": {"available": 0, "consumed": 0, "reserved": 0},
                            }))
                    except Exception as e:
                        print(f"[WsBridge] tunehub/credits error: {e}")

                elif msg_type == "tunehub/learn":
                    _handle_tunehub_learn(msg)

                elif msg_type == "tunehub/get_settings":
                    try:
                        import core as _core_state
                        settings = dict(getattr(_core_state, "tune_hub_settings", {}))
                        await websocket.send(json.dumps({
                            "type": "tunehub/settings",
                            "settings": settings,
                        }))
                    except Exception as e:
                        print(f"[WsBridge] tunehub/get_settings error: {e}")

                elif msg_type == "tunehub/set_settings":
                    try:
                        import core as _core_state
                        incoming = msg.get("settings", {})
                        if isinstance(incoming, dict):
                            _core_state.tune_hub_settings.update(incoming)
                            # Persist to disk
                            try:
                                import json as _json
                                import os
                                settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "tunehub_settings.json")
                                with open(settings_path, "w", encoding="utf-8") as f:
                                    _json.dump(_core_state.tune_hub_settings, f, indent=2)
                            except Exception:
                                pass
                            await websocket.send(json.dumps({
                                "type": "tunehub/settings",
                                "settings": dict(_core_state.tune_hub_settings),
                            }))
                    except Exception as e:
                        print(f"[WsBridge] tunehub/set_settings error: {e}")

            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        _clients.discard(websocket)
        print(f"[WsBridge] Client disconnected ({len(_clients)} total)")


def _handle_user_message(text: str):
    """Route user message from overlay to the agent pipeline."""
    def _run():
        try:
            from core.agent import ask_ai
            ask_ai(text)
        except Exception as e:
            print(f"[WsBridge] Message dispatch error: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _handle_agent_task(text: str):
    """Route an agent task from the overlay to the agent pipeline (force_agent=True)."""
    def _run():
        try:
            from core.agent import ask_ai
            ask_ai(text, force_agent=True)
        except Exception as e:
            print(f"[WsBridge] Agent task dispatch error: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _handle_save_session(msg: dict):
    def _run():
        try:
            from core.tasks import save_session_as_task, get_task_snapshot
            import core as state
            # Build title from last user message; fall back to a generic label
            history = getattr(state, "conversation_history", [])
            last_user = next((m for m in reversed(history) if m.get("role") == "user" and m.get("content")), None)
            title = (last_user.get("content", "").strip()[:60] if last_user else "Session continuation")
            # Use last ~10 messages to capture recent prompt context
            recent = history[-10:]
            body = "\n\n".join(f"[{(m.get('role') or '').upper()}]: {m.get('content','')}" for m in recent if m.get('content'))
            task = save_session_as_task(title=title, prompt_content=body)

            # Notify overlay: task_saved + refreshed tasks/update snapshot
            broadcast_sync({
                "type": "task_saved",
                "task": task,
                "reply": f"\u2713 Saved as task for tomorrow: \"{task.get('text','')[:40]}\"",
            })
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] save_session error: {e}")
    threading.Thread(target=_run, daemon=True).start()


async def _broadcast(data: dict):
    """Send a message to all connected overlay clients."""
    if not _clients:
        return
    payload = json.dumps(data)
    disconnected = set()
    for ws in list(_clients):
        try:
            await ws.send(payload)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        _clients.discard(ws)


def has_overlay_clients() -> bool:
    """Return True if any Electron overlay client is currently connected."""
    return bool(_clients)


def broadcast_sync(data: dict):
    """Thread-safe broadcast — callable from any thread."""
    if _loop is None or not _clients:
        return
    try:
        asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)
    except Exception:
        pass


def send_history_update():
    """Push updated conversation history to all overlay clients."""
    try:
        import core as state
        history = getattr(state, "conversation_history", [])
        # If history was wiped by a module reload, attempt to restore from disk.
        if not history:
            try:
                from core.agent import _load_conversation_history
                restored = _load_conversation_history()
                if restored:
                    state.conversation_history = restored
                    history = restored
            except Exception:
                pass
        broadcast_sync({
            "type": "history",
            "messages": [
                {"role": m.get("role", ""), "content": m.get("content", "")}
                for m in history
                if m.get("content", "").strip() and len(m.get("content", "")) < 5000
            ]
        })
    except Exception:
        pass


def send_wave_state(state_name: str):
    """Push wave/overlay state change."""
    broadcast_sync({"type": "wave_state", "state": state_name})


def send_agent_step(step: int, total: int, text: str):
    """Push agent step progress."""
    broadcast_sync({"type": "agent_step", "step": step, "total": total, "text": text})


def send_voice_state(voice_state: str, text: str = "") -> None:
    """Push voice capture lifecycle: idle | listening | processing | pasted | error.

    The overlay uses this to drive the pill wave animation and the green
    paste-complete flash.
    """
    broadcast_sync({"type": "voice_state", "state": voice_state, "text": text or ""})


def send_mic_level(level: float) -> None:
    """Push current microphone RMS amplitude (0..1ish scale). The overlay clamps.

    This should be throttled by the caller (~20–30 Hz is plenty) to avoid
    saturating the WebSocket.
    """
    try:
        lvl = max(0.0, float(level))
    except (TypeError, ValueError):
        return
    broadcast_sync({"type": "mic_level", "level": lvl})


# ------------------------------------------------------------------
# Inbound message handlers (React → Python)
# ------------------------------------------------------------------

def _handle_tasks_add(msg: dict):
    def _run():
        try:
            from core.tasks import add_task, get_task_snapshot, parse_due_time
            text = msg.get("text", "").strip()
            due_at = msg.get("due_at")
            # If the client didn't pass an explicit due time, try to pull one
            # out of the task text itself (e.g. "review PR by 10pm"), so the
            # badge shows up without forcing users to use the day/time picker.
            if text and not due_at:
                cleaned, parsed_due = parse_due_time(text)
                if parsed_due:
                    text = cleaned or text
                    due_at = parsed_due
            saved = add_task(
                text,
                source=msg.get("source", "typed"),
                due_at=due_at,
            )
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
            if saved:
                broadcast_sync({
                    "type": "task_saved",
                    "task": saved,
                    "reply": f"✓ Task saved: \"{text[:40]}\"",
                })
        except Exception as e:
            print(f"[WsBridge] tasks/add error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_toggle(msg: dict):
    def _run():
        try:
            from core.tasks import toggle_status, get_task_snapshot
            toggle_status(msg.get("task_id", ""))
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] tasks/toggle error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_delete(msg: dict):
    def _run():
        try:
            from core.tasks import delete_task, get_task_snapshot
            delete_task(msg.get("task_id", ""))
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] tasks/delete error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_edit(msg: dict):
    def _run():
        try:
            from core.tasks import edit_task_fields, get_task_snapshot
            task_id = msg.get("task_id", "")
            fields = msg.get("fields", {})
            if isinstance(fields, dict) and task_id:
                edit_task_fields(task_id, fields)
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] tasks/edit error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_reschedule(msg: dict):
    def _run():
        try:
            from core.tasks import reschedule_to_tomorrow, get_task_snapshot
            task_id = msg.get("task_id", "")
            if task_id:
                reschedule_to_tomorrow(task_id)
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] tasks/reschedule error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_refresh(_msg: dict):
    def _run():
        try:
            from core.tasks import get_task_snapshot
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
            })
        except Exception as e:
            print(f"[WsBridge] tasks/refresh error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_snooze(msg: dict):
    def _run():
        try:
            from core.tasks import snooze_task, get_task_snapshot
            task_id = msg.get("taskId") or msg.get("task_id", "")
            minutes = int(msg.get("minutes", 15))
            if task_id and minutes > 0:
                snooze_task(task_id, minutes)
                snapshot = get_task_snapshot()
                broadcast_sync({
                    "type": "tasks/update",
                    "payload": snapshot.get("tasks", []),
                    "history": snapshot.get("history", []),
                    "suggestion": snapshot.get("suggestion"),
                })
        except Exception as e:
            print(f"[WsBridge] tasks/snooze error: {e}")
    threading.Thread(target=_run, daemon=True).start()


async def _handle_tasks_settings_set(websocket, msg: dict):
    """Save task settings to settings.json and acknowledge."""
    try:
        import json as _json
        import os
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        data = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        # Merge task-specific settings
        for key in ("reminder_interval_min", "default_due_time", "snooze_presets", "pre_due_warning", "carry_over"):
            if key in msg:
                data[key] = msg[key]
        with open(settings_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)
        await websocket.send(_json.dumps({
            "type": "tasks/settings/update",
            "settings": data,
        }))
    except Exception as e:
        print(f"[WsBridge] tasks/settings/set error: {e}")


async def _handle_tasks_settings_get(websocket):
    """Return current task settings from settings.json."""
    try:
        import json as _json
        import os
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        data = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        task_settings = {
            "reminder_interval_min": data.get("reminder_interval_min", 15),
            "default_due_time": data.get("default_due_time", "17:00"),
            "snooze_presets": data.get("snooze_presets", [15, 30, 60, 1440]),
            "pre_due_warning": data.get("pre_due_warning", True),
            "carry_over": data.get("carry_over", True),
        }
        await websocket.send(_json.dumps({
            "type": "tasks/settings/update",
            "settings": task_settings,
        }))
    except Exception as e:
        print(f"[WsBridge] tasks/settings/get error: {e}")


def _handle_vocab_add(msg: dict):
    def _run():
        try:
            from core.vocab import add_correction
            add_correction(msg.get("heard", ""), msg.get("actual", ""))
        except Exception as e:
            print(f"[WsBridge] vocab_add error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_dictation_preview_confirm(msg: dict):
    """Copy the confirmed preview text to clipboard and dismiss the preview."""
    def _run():
        try:
            text = msg.get("text", "").strip()
            if not text:
                return
            import pyperclip
            pyperclip.copy(text)
            send_pill_notice("added", "Copied to clipboard", text[:60], duration_ms=2000)
            broadcast_sync({"type": "dictation_preview/dismiss"})
        except Exception as e:
            print(f"[WsBridge] dictation_preview/confirm error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_dictation_preview_optimize(msg: dict):
    """Run WizPrompt on the preview text and broadcast the result back."""
    def _run():
        try:
            text = msg.get("text", "").strip()
            if not text:
                return
            import asyncio
            from core.wizprompt import optimize_prompt_with_dynamic_agents
            import pyperclip

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(optimize_prompt_with_dynamic_agents(text))
                optimized = result.get("optimized_prompt", "").strip()
                if optimized:
                    pyperclip.copy(optimized)
                    broadcast_sync({
                        "type": "dictation_preview/optimized",
                        "text": optimized,
                        "original": text,
                        "agent_count": result.get("agent_count", 0),
                        "emotion": result.get("emotional_state"),
                        "prompt_size": result.get("prompt_size"),
                        "line_count": result.get("line_count", 0),
                        "framing_directive": result.get("framing_directive"),
                        "synthesis_failed": result.get("synthesis_failed", False),
                        "critiques": result.get("critiques", {}),
                    })
                    send_pill_notice(
                        "updated",
                        "Prompt optimized",
                        f"Copied to clipboard • {result.get('agent_count', 0)} agents used",
                        duration_ms=3000,
                    )
                else:
                    send_pill_notice("error", "Optimization failed", "Synthesis returned empty.", duration_ms=3000)
            finally:
                loop.close()
        except Exception as e:
            print(f"[WsBridge] dictation_preview/optimize error: {e}")
            send_pill_notice("error", "Optimization failed", str(e)[:60], duration_ms=3000)
    threading.Thread(target=_run, daemon=True).start()


def _handle_agent_undo(msg: dict):
    def _run():
        try:
            from core.agent import get_agent_memory
            mem = get_agent_memory()
            if mem:
                mem.rollback_to_checkpoint()
        except Exception as e:
            print(f"[WsBridge] agent/undo error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _get_local_user_id() -> str:
    """Return a stable local user id for Tune Hub when no auth is available."""
    try:
        import os
        import hashlib
        user = os.environ.get("USER", os.environ.get("USERNAME", "local"))
        host = os.environ.get("HOSTNAME", "unknown")
        return hashlib.sha256(f"{user}@{host}".encode()).hexdigest()[:16]
    except Exception:
        return "local"


def _handle_tunehub_learn(msg: dict):
    def _run():
        try:
            import core as _core_state
            hub = getattr(_core_state, "tune_hub", None)
            user_id = msg.get("user_id", _get_local_user_id())
            feature_name = msg.get("feature_name", "reprompt")
            task = msg.get("task", "")
            tier = msg.get("tier", "free")
            credits = msg.get("credits", 100)
            if hub and task:
                from core.tune_hub.orchestrator import TuneRequest
                result = hub.tune_feature(TuneRequest(
                    user_id=user_id,
                    feature_name=feature_name,
                    task=task,
                    approved_credits=credits,
                    tier=tier,
                ))
                broadcast_sync({
                    "type": "tunehub/learn_result",
                    "success": result.success,
                    "credits_used": result.credits_used,
                    "credits_remaining": result.credits_remaining,
                    "message": result.message,
                    "reusable": result.reusable,
                })
            else:
                broadcast_sync({
                    "type": "tunehub/learn_result",
                    "success": False,
                    "message": "TuneHub not initialized or no task provided",
                })
        except Exception as e:
            print(f"[WsBridge] tunehub/learn error: {e}")
            broadcast_sync({
                "type": "tunehub/learn_result",
                "success": False,
                "message": str(e),
            })
    threading.Thread(target=_run, daemon=True).start()


def _handle_hotkey(msg: dict):
    """Handle hotkey events from Electron overlay (Linux: works without root)."""
    def _run():
        try:
            key = msg.get("key", "")
            if not key:
                return

            # Import here to avoid circular imports
            from core import hotkeys

            if key == "f9_start":
                hotkeys.start_recording()
            elif key == "f9_stop":
                hotkeys.stop_and_process()
            elif key == "f9_toggle_agent":
                hotkeys.toggle_agent_mode()
            elif key == "f10_start":
                hotkeys.task_hotkey_handler()
            elif key == "f10_stop":
                hotkeys.stop_and_process()
            elif key == "ctrl_space":
                hotkeys.toggle_chat_overlay()
            elif key == "escape":
                hotkeys.hide_chat_overlay_if_visible()
            elif key == "ctrl_shift_space":
                hotkeys.optimize_clipboard_prompt()
        except Exception as e:
            print(f"[WsBridge] hotkey error: {e}")
    threading.Thread(target=_run, daemon=True).start()


# ------------------------------------------------------------------
# Outbound broadcasters (Python → React)
# ------------------------------------------------------------------

def send_tasks_update(tasks: list):
    try:
        from core.tasks import get_task_snapshot
        snapshot = get_task_snapshot()
        payload = tasks if isinstance(tasks, list) else snapshot.get("tasks", [])
        broadcast_sync({
            "type": "tasks/update",
            "payload": payload,
            "history": snapshot.get("history", []),
            "suggestion": snapshot.get("suggestion"),
        })
    except Exception:
        broadcast_sync({"type": "tasks/update", "payload": tasks})


def send_agent_step_v2(task_id: str, step: int, of: int, action: str, target: str = ""):
    broadcast_sync({"type": "agent/step", "task_id": task_id, "step": step,
                    "of": of, "action": action, "target": target})


def send_agent_blocked(task_id: str, reason: str, undoable: bool = True):
    broadcast_sync({"type": "agent/blocked", "task_id": task_id,
                    "reason": reason, "undoable": undoable})


def send_agent_done(task_id: str, result: str = "", success: bool = True):
    broadcast_sync({"type": "agent/done", "task_id": task_id,
                    "result": result, "success": success})


def send_agent_question(question_id: str, text: str, options: list[str]):
    """Ask the user a question with clickable options in the agent panel."""
    broadcast_sync({
        "type": "agent/question",
        "question_id": question_id,
        "text": text,
        "options": list(options),
    })


def send_vocab_correct(heard: str, context_before: str = "", context_after: str = ""):
    broadcast_sync({"type": "vocab_correct", "heard": heard,
                    "context_before": context_before, "context_after": context_after})


def send_pill_notice(kind: str, title: str, summary: str = "", duration_ms: int = 2600):
    """Push a pill notice: green/amber/red flash with a title + grey summary.

    kind: 'added' | 'updated' | 'duplicate' | 'subtask' | 'memory_added'
          | 'memory_updated' | 'error'
    The pill renderer resizes the pill window sideways for duration_ms and
    shows title + summary, then restores the normal pill.
    """
    broadcast_sync({
        "type": "pill/notice",
        "kind": str(kind or "added"),
        "title": str(title or ""),
        "summary": str(summary or ""),
        "duration_ms": int(duration_ms) if duration_ms else 2600,
    })


async def _run_server():
    """Run the WebSocket server."""
    global _loop
    _loop = asyncio.get_event_loop()

    try:
        import websockets
        async with websockets.serve(_handler, "localhost", WS_PORT):
            print(f"[WsBridge] WebSocket server running on ws://localhost:{WS_PORT}")
            await asyncio.Future()  # Run forever
    except ImportError:
        print("[WsBridge] websockets package not installed. Run: pip install websockets")
    except OSError as e:
        print(f"[WsBridge] Server start failed (port {WS_PORT} in use?): {e}")


def start_ws_bridge():
    """Start the WebSocket bridge server in a background thread."""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return
    with _server_lock:
        # Double-check inside the lock to close the race window.
        if _server_thread and _server_thread.is_alive():
            return
        def _thread():
            asyncio.run(_run_server())

        _server_thread = threading.Thread(target=_thread, daemon=True)
        _server_thread.start()
        print("[WsBridge] Bridge thread started")
