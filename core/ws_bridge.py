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

# ── RePrompt ready signal ────────────────────────────────────────────────────
_reprompt_ready_event: Optional[threading.Event] = None


def get_reprompt_ready_event() -> threading.Event:
    """Return a threading.Event that is set when the overlay confirms Reprompt tab is open."""
    global _reprompt_ready_event
    if _reprompt_ready_event is None:
        _reprompt_ready_event = threading.Event()
    _reprompt_ready_event.clear()
    return _reprompt_ready_event


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
    # Reject cross-site WebSocket hijacking: a remote web page can open this
    # loopback socket (WS is exempt from the same-origin policy), so only serve
    # connections from the Electron app (no Origin) or our own renderer origins.
    try:
        from core.local_security import origin_allowed

        origin = None
        request = getattr(websocket, "request", None)
        if request is not None:
            origin = request.headers.get("Origin")
        if not origin_allowed(origin):
            print(f"[WsBridge] Rejected connection from disallowed origin: {origin!r}")
            await websocket.close(code=1008, reason="origin not allowed")
            return
    except Exception as e:
        print(f"[WsBridge] Origin check error (rejecting): {e}")
        try:
            await websocket.close(code=1011, reason="origin check failed")
        finally:
            return

    _clients.add(websocket)
    websocket._wz_meta = {"connected_at": datetime.now().isoformat()}
    print(f"[WsBridge] Client connected ({len(_clients)} total)")

    try:
        from core.tasks import get_task_snapshot
        snapshot = get_task_snapshot()
        await websocket.send(json.dumps({
            "type": "tasks/update",
            "payload": snapshot.get("tasks", []),
            "history": snapshot.get("history", []),
            "suggestion": snapshot.get("suggestion"),
            "categories": snapshot.get("categories", []),
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

    try:
        confirmation_snapshot = get_agent_confirmation_overlay().get_bridge_snapshot()
        if confirmation_snapshot:
            await websocket.send(json.dumps(confirmation_snapshot))
    except Exception as e:
        print(f"[WsBridge] Confirmation snapshot send error: {e}")

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    continue
                msg_type = msg.get("type", "")

                if msg_type == "send_agent_task":
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

                elif msg_type == "tasks/add_category":
                    _handle_tasks_add_category(msg)

                elif msg_type == "tasks/remove_category":
                    _handle_tasks_remove_category(msg)

                elif msg_type == "task_confirm_approve":
                    _handle_task_confirm_approve(msg)

                elif msg_type == "task_confirm_reject":
                    _handle_task_confirm_reject(msg)

                elif msg_type == "tasks/settings/set":
                    await _handle_tasks_settings_set(websocket, msg)

                elif msg_type == "tasks/settings/get":
                    await _handle_tasks_settings_get(websocket)

                elif msg_type == "settings/agent/save":
                    await _handle_agent_settings_set(websocket, msg)

                elif msg_type == "settings/agent/get":
                    await _handle_agent_settings_get(websocket)

                elif msg_type == "vocab_add":
                    _handle_vocab_add(msg)

                elif msg_type == "vocab/list":
                    try:
                        await websocket.send(json.dumps(_vocab_snapshot()))
                    except Exception as e:
                        print(f"[WsBridge] vocab/list error: {e}")

                elif msg_type == "vocab/add_word":
                    try:
                        from core.vocab import add_word
                        add_word(str(msg.get("word", "")))
                        broadcast_sync(_vocab_snapshot())
                    except Exception as e:
                        print(f"[WsBridge] vocab/add_word error: {e}")

                elif msg_type == "vocab/delete_word":
                    try:
                        from core.vocab import delete_word
                        delete_word(str(msg.get("word", "")))
                        broadcast_sync(_vocab_snapshot())
                    except Exception as e:
                        print(f"[WsBridge] vocab/delete_word error: {e}")

                elif msg_type == "vocab/add_pair":
                    try:
                        from core.vocab import add_correction
                        heard = str(msg.get("heard", "")).strip()
                        actual = str(msg.get("actual", "")).strip()
                        if heard and actual:
                            add_correction(heard, actual)
                        broadcast_sync(_vocab_snapshot())
                    except Exception as e:
                        print(f"[WsBridge] vocab/add_pair error: {e}")

                elif msg_type == "vocab/delete_correction":
                    try:
                        from core.vocab import delete_correction
                        delete_correction(str(msg.get("heard", "")))
                        broadcast_sync(_vocab_snapshot())
                    except Exception as e:
                        print(f"[WsBridge] vocab/delete_correction error: {e}")

                elif msg_type == "agent/undo":
                    _handle_agent_undo(msg)

                elif msg_type == "agent/answer":
                    question_id = str(msg.get("question_id", ""))
                    choice = str(msg.get("choice", ""))
                    if question_id and choice:
                        _set_question_answer(question_id, choice)

                elif msg_type == "save_session":
                    _handle_save_session(msg)

                elif msg_type == "agent_v2:initiate":
                    _handle_agent_v2_initiate(msg)

                elif msg_type == "agent_v2:select_template":
                    _handle_agent_v2_select_template(msg)

                elif msg_type == "agent_v2:run_preset":
                    _handle_agent_v2_run_preset(msg)

                elif msg_type == "agent_v2:pause":
                    _handle_agent_v2_pause(msg)

                elif msg_type == "agent_v2:resume":
                    _handle_agent_v2_resume(msg)

                elif msg_type == "agent_v2:decision":
                    _handle_agent_v2_decision(msg)

                elif msg_type == "agent_v2:abort":
                    _handle_agent_v2_abort(msg)

                elif msg_type == "workflow:decision":
                    _handle_workflow_decision(msg)

                elif msg_type == "tunehub:trigger_learning":
                    _handle_tunehub_trigger_learning(msg)

                elif msg_type == "tunehub:approve_learned":
                    _handle_tunehub_approve_learned(msg)

                elif msg_type == "tunehub:reject_learned":
                    _handle_tunehub_reject_learned(msg)

                elif msg_type == "hotkey":
                    _handle_hotkey(msg)

                elif msg_type == "request_insights":
                    try:
                        from core.insights_tracker import load_insights, get_daily_summary
                        data = load_insights()
                        lifetime = data.get("lifetime", {})
                        today = datetime.now().strftime("%Y-%m-%d")
                        daily_today = data.get("daily", {}).get(today, {})
                        daily_history = get_daily_summary(180)
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
                                "daily_history": daily_history,
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

                elif msg_type == "wizprompt/feedback":
                    _handle_wizprompt_feedback(msg)

                elif msg_type == "dictation_preview/cancel":
                    # No-op on Python side; pill just closes the preview
                    pass

                elif msg_type == "correction_capture/open":
                    try:
                        from core.dictation_correction import start_undo_hook
                        start_undo_hook(
                            msg.get("session_id", ""),
                            msg.get("original_text", ""),
                            msg.get("stt_text", ""),
                        )
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/open error: {e}")

                elif msg_type == "correction_capture/edit":
                    try:
                        from core.dictation_correction import on_preview_edit
                        on_preview_edit(msg.get("session_id", ""), msg.get("new_text", ""))
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/edit error: {e}")

                elif msg_type == "correction_capture/undo":
                    try:
                        from core.dictation_correction import on_preview_undo
                        on_preview_undo(msg.get("session_id", ""), msg.get("new_text", ""))
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/undo error: {e}")

                elif msg_type == "correction_capture/copy":
                    try:
                        from core.dictation_correction import on_preview_copy
                        on_preview_copy(msg.get("session_id", ""))
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/copy error: {e}")

                elif msg_type == "correction_capture/close":
                    try:
                        from core.dictation_correction import on_preview_close
                        on_preview_close(msg.get("session_id", ""))
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/close error: {e}")

                elif msg_type == "correction_capture/optimize":
                    try:
                        from core.dictation_correction import on_preview_optimize
                        on_preview_optimize(msg.get("session_id", ""), msg.get("optimized", ""))
                    except Exception as e:
                        print(f"[WsBridge] correction_capture/optimize error: {e}")

                elif msg_type == "reprompt_ready":
                    evt = _reprompt_ready_event
                    if evt:
                        evt.set()

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

                elif msg_type == "integrations/list":
                    try:
                        from core import integrations as _intg
                        await websocket.send(json.dumps({
                            "type": "integrations/update",
                            "integrations": _intg.list_public(),
                        }))
                    except Exception as e:
                        print(f"[WsBridge] integrations/list error: {e}")

                elif msg_type == "integrations/save":
                    try:
                        from core import integrations as _intg
                        _intg.save_integration(msg.get("integration", {}))
                        broadcast_sync({
                            "type": "integrations/update",
                            "integrations": _intg.list_public(),
                        })
                    except Exception as e:
                        await websocket.send(json.dumps({
                            "type": "integrations/error",
                            "error": str(e),
                        }))

                elif msg_type == "integrations/delete":
                    try:
                        from core import integrations as _intg
                        _intg.delete_integration(msg.get("id", ""))
                        broadcast_sync({
                            "type": "integrations/update",
                            "integrations": _intg.list_public(),
                        })
                    except Exception as e:
                        print(f"[WsBridge] integrations/delete error: {e}")

                elif msg_type == "integrations/oauth/start":
                    # Runs the blocking PKCE loopback flow in a background thread
                    # so the websocket loop stays responsive.
                    try:
                        from core import integrations as _intg
                        import threading
                        app_name = msg.get("app", "")
                        provider = (msg.get("provider") or app_name).strip().lower()
                        client_id = msg.get("client_id", "")
                        client_secret = msg.get("client_secret", "")
                        iid = msg.get("id")

                        if not _intg.oauth_provider_known(provider):
                            await websocket.send(json.dumps({
                                "type": "integrations/oauth/result",
                                "app": app_name,
                                "ok": False,
                                "error": f"No OAuth support for '{provider}'. Use credential vault instead.",
                            }))
                        else:
                            def _do_oauth():
                                try:
                                    tok = _intg.run_oauth_flow(provider, client_id, client_secret)
                                    _intg.save_integration({
                                        "id": iid,
                                        "app": app_name or provider,
                                        "auth_type": "oauth",
                                        "oauth": tok,
                                    })
                                    broadcast_sync({
                                        "type": "integrations/oauth/result",
                                        "app": app_name or provider,
                                        "ok": True,
                                    })
                                    broadcast_sync({
                                        "type": "integrations/update",
                                        "integrations": _intg.list_public(),
                                    })
                                except Exception as oe:
                                    broadcast_sync({
                                        "type": "integrations/oauth/result",
                                        "app": app_name or provider,
                                        "ok": False,
                                        "error": str(oe),
                                    })
                            threading.Thread(target=_do_oauth, daemon=True).start()
                    except Exception as e:
                        print(f"[WsBridge] integrations/oauth/start error: {e}")

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
                print(f"[WsBridge] Malformed JSON from client: {raw[:200]!r}")
    except Exception:
        pass
    finally:
        _clients.discard(websocket)
        print(f"[WsBridge] Client disconnected ({len(_clients)} total)")


def _handle_agent_task(text: str):
    """Route an agent task from the overlay to the agent pipeline (force_agent=True)."""
    print(f"[WsBridge] _handle_agent_task received: {text[:80]}")
    def _run():
        try:
            from core.hotkeys import _agent_feature_enabled
            if not _agent_feature_enabled():
                print("[WsBridge] Agent task ignored (agent feature disabled)")
                return
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
                "categories": snapshot.get("categories", []),
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
    coro = _broadcast(data)
    try:
        asyncio.run_coroutine_threadsafe(coro, _loop)
    except Exception as e:
        coro.close()
        print(f"[WsBridge] broadcast_sync error: {e}")


def send_wave_state(state_name: str):
    """Push wave/overlay state change."""
    print(f"[WsBridge] send_wave_state: {state_name}")
    broadcast_sync({"type": "wave_state", "state": state_name})


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


def send_agent_step(step: int, total: int, text: str):
    """Push agent step progress."""
    broadcast_sync({"type": "agent_step", "step": step, "total": total, "text": text})


def send_voice_state(voice_state: str, text: str = "") -> None:
    """Push voice capture lifecycle: idle | listening | processing | pasted | error.

    The overlay uses this to drive the pill wave animation and the green
    paste-complete flash.

    Wave-state arbitration: if the agent is currently running, dictation must
    not reset the wave to 'idle' — that would hide the agent's progress indicator.
    """
    import core as _state
    if voice_state == "idle" and getattr(_state, "_agent_running", False):
        # Agent is active — suppress the idle reset so the agent wave persists
        return
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


def send_agent_phase_start(project_id: str, layer: Optional[str], phase: Optional[str], subphase: Optional[str]) -> None:
    asyncio.run_coroutine_threadsafe(
        _broadcast({"type": "agent.phase_start", "project_id": project_id, "layer": layer, "phase": phase, "subphase": subphase}),
        _loop,
    )


def send_agent_step_complete(project_id: str, subphase_id: str) -> None:
    asyncio.run_coroutine_threadsafe(
        _broadcast({"type": "agent.step_complete", "project_id": project_id, "subphase_id": subphase_id}),
        _loop,
    )


def send_agent_needs_approval(project_id: str, message: str) -> None:
    asyncio.run_coroutine_threadsafe(
        _broadcast({"type": "agent.needs_approval", "project_id": project_id, "message": message}),
        _loop,
    )


def send_agent_limit_hit(project_id: str, reason: str) -> None:
    asyncio.run_coroutine_threadsafe(
        _broadcast({"type": "agent.limit_hit", "project_id": project_id, "reason": reason}),
        _loop,
    )


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
            category = msg.get("category")
            difficulty = msg.get("difficulty")
            saved = add_task(
                text,
                source=msg.get("source", "typed"),
                due_at=due_at,
                category=category,
                difficulty=difficulty,
            )
            snapshot = get_task_snapshot()
            broadcast_sync({
                "type": "tasks/update",
                "payload": snapshot.get("tasks", []),
                "history": snapshot.get("history", []),
                "suggestion": snapshot.get("suggestion"),
                "categories": snapshot.get("categories", []),
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
                "categories": snapshot.get("categories", []),
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
                "categories": snapshot.get("categories", []),
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
                "categories": snapshot.get("categories", []),
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
                "categories": snapshot.get("categories", []),
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
                "categories": snapshot.get("categories", []),
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
                    "categories": snapshot.get("categories", []),
                })
        except Exception as e:
            print(f"[WsBridge] tasks/snooze error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_add_category(msg: dict):
    def _run():
        try:
            from core.tasks import add_category, get_task_snapshot
            name = msg.get("name", "").strip()
            if name:
                add_category(name)
                snapshot = get_task_snapshot()
                broadcast_sync({
                    "type": "tasks/update",
                    "payload": snapshot.get("tasks", []),
                    "history": snapshot.get("history", []),
                    "suggestion": snapshot.get("suggestion"),
                    "categories": snapshot.get("categories", []),
                })
        except Exception as e:
            print(f"[WsBridge] tasks/add_category error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_tasks_remove_category(msg: dict):
    def _run():
        try:
            from core.tasks import remove_category, get_task_snapshot
            name = msg.get("name", "").strip()
            if name:
                remove_category(name)
                snapshot = get_task_snapshot()
                broadcast_sync({
                    "type": "tasks/update",
                    "payload": snapshot.get("tasks", []),
                    "history": snapshot.get("history", []),
                    "suggestion": snapshot.get("suggestion"),
                    "categories": snapshot.get("categories", []),
                })
        except Exception as e:
            print(f"[WsBridge] tasks/remove_category error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_task_confirm_approve(msg: dict):
    def _run():
        try:
            from core.hotkeys import _pending_task_confirmations, _handle_new_task
            confirm_id = msg.get("confirm_id", "")
            pending = _pending_task_confirmations.pop(confirm_id, None)
            if pending:
                _handle_new_task(pending["text"], pending["due_at"])
        except Exception as e:
            print(f"[WsBridge] task_confirm_approve error: {e}")
    threading.Thread(target=_run, daemon=True).start()


def _handle_task_confirm_reject(msg: dict):
    def _run():
        try:
            from core.hotkeys import _pending_task_confirmations
            _pending_task_confirmations.pop(msg.get("confirm_id", ""), None)
        except Exception as e:
            print(f"[WsBridge] task_confirm_reject error: {e}")
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
        for key in ("reminder_interval_min", "default_due_time", "snooze_presets", "pre_due_warning", "carry_over", "task_creation_mode"):
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
            "task_creation_mode": data.get("task_creation_mode", "smart"),
        }
        await websocket.send(_json.dumps({
            "type": "tasks/settings/update",
            "settings": task_settings,
        }))
    except Exception as e:
        print(f"[WsBridge] tasks/settings/get error: {e}")


_AGENT_SETTING_KEYS = ("agent_max_steps", "AGENT_PLANNER_MODEL", "AGENT_OMNI_MODEL")


async def _handle_agent_settings_set(websocket, msg: dict):
    """Save agent settings to settings.json and acknowledge."""
    try:
        import json as _json
        import os
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        data = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        for key in _AGENT_SETTING_KEYS:
            if key in msg:
                data[key] = msg[key]
        if "agent_max_steps" in data:
            try:
                data["agent_max_steps"] = max(0, int(data["agent_max_steps"]))
            except Exception:
                data.pop("agent_max_steps", None)
        with open(settings_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)
        await websocket.send(_json.dumps({
            "type": "settings/agent/update",
            "settings": {k: data.get(k) for k in _AGENT_SETTING_KEYS},
        }))
    except Exception as e:
        print(f"[WsBridge] settings/agent/save error: {e}")


async def _handle_agent_settings_get(websocket):
    """Return current agent settings from settings.json."""
    try:
        import json as _json
        import os
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        data = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        await websocket.send(_json.dumps({
            "type": "settings/agent/update",
            "settings": {
                "agent_max_steps": data.get("agent_max_steps", 100),
                "AGENT_PLANNER_MODEL": data.get("AGENT_PLANNER_MODEL", ""),
                "AGENT_OMNI_MODEL": data.get("AGENT_OMNI_MODEL", ""),
            },
        }))
    except Exception as e:
        print(f"[WsBridge] settings/agent/get error: {e}")


def _vocab_snapshot() -> dict:
    """Build the vocab/update payload: dictionary words + heard->actual pairs."""
    from core.vocab import list_words, load_vocab
    data = load_vocab()
    return {
        "type": "vocab/update",
        "words": [e.get("word", "") for e in list_words()],
        "corrections": [
            {"heard": c.get("heard", ""), "actual": c.get("actual", "")}
            for c in data.get("corrections", [])
        ],
    }


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


def _handle_wizprompt_feedback(msg: dict):
    """Store wizprompt feedback and edited result from the UI."""
    def _run():
        try:
            if msg.get("ephemeral"):
                print("[WsBridge] wizprompt feedback skipped (ephemeral)")
                return
            import asyncio
            import core.wizprompt_memory as mem
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    mem.remember_optimization(
                        original_prompt=msg.get("original", ""),
                        optimized_prompt=msg.get("optimized", ""),
                        final_prompt=msg.get("final", ""),
                        was_edited=msg.get("was_edited", False),
                        feedback=msg.get("feedback"),
                        preset=msg.get("preset"),
                        model=msg.get("model"),
                        emotion=msg.get("emotion"),
                    )
                )
                print(f"[WsBridge] wizprompt feedback stored: id={result['example_id']} cluster={result['cluster_id']}")
            finally:
                loop.close()
        except Exception as e:
            print(f"[WsBridge] wizprompt/feedback error: {e}")
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
            if hub and task:
                from core.tune_hub.orchestrator import TuneRequest
                result = hub.tune_feature(TuneRequest(
                    user_id=user_id,
                    feature_name=feature_name,
                    task=task,
                    budget_limit=msg.get("budget_limit", 100),
                ))
                broadcast_sync({
                    "type": "tunehub/learn_result",
                    "success": result.success,
                    "iterations_used": result.iterations_used,
                    "iterations_remaining": result.iterations_remaining,
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
            "categories": snapshot.get("categories", []),
        })
    except Exception:
        broadcast_sync({"type": "tasks/update", "payload": tasks, "categories": []})


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


def send_credits_update(balance: int, tier: str = "free", allocation: int = 0):
    """Push credit balance update to overlay."""
    broadcast_sync({
        "type": "credits/update",
        "balance": balance,
        "tier": tier,
        "allocation": allocation,
    })


def send_credit_consumed(feature: str, amount: int, balance_after: int, model: str | None = None):
    """Push a real-time credit consumption notification to the overlay.

    Dictation is excluded from this broadcast at the call site.
    """
    broadcast_sync({
        "type": "credits/consumed",
        "feature": feature,
        "amount": amount,
        "balance_after": balance_after,
        "model": model,
    })


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
        "duration_ms": int(duration_ms) if duration_ms is not None else 2600,
    })


def send_mic_error(title: str, detail: str = "", duration_ms: int = 5000) -> None:
    """Push microphone error to overlay pill with voice_state error flash."""
    send_voice_state("error", detail)
    send_pill_notice("error", title, detail, duration_ms=duration_ms)


def _attach_engine_listeners(engine):
    def listener(event, payload):
        if event == "agent.phase_start":
            send_agent_phase_start(payload.get("plan_id"), payload.get("layer"), payload.get("phase"), payload.get("subphase"))
        elif event == "agent.step_complete":
            send_agent_step_complete(payload.get("plan_id"), payload.get("subphase_id"))
        elif event == "agent.needs_approval":
            send_agent_needs_approval(payload.get("plan_id"), payload.get("message"))
        elif event == "agent.limit_hit":
            send_agent_limit_hit(payload.get("plan_id"), payload.get("reason"))
    engine.add_listener(listener)


# ── TuneHub Learning broadcast helpers ───────────────────────────────────────

def send_tunehub_learning_started(workflow_name: str, query: str, estimated_time: int):
    broadcast_sync({"type": "tunehub:learning_started", "workflow_name": workflow_name, "query": query, "estimated_time": estimated_time})


def send_tunehub_learning_progress(percent: int, current_source: str, steps_found: int):
    broadcast_sync({"type": "tunehub:learning_progress", "percent": percent, "current_source": current_source, "steps_found": steps_found})


def send_tunehub_learning_complete(template: dict, confidence: float, sources: list[str], requires_review: bool):
    broadcast_sync({"type": "tunehub:learning_complete", "template": template, "confidence": confidence, "sources": sources, "requires_review": requires_review})


def send_tunehub_learning_failed(reason: str, fallback: str):
    broadcast_sync({"type": "tunehub:learning_failed", "reason": reason, "fallback": fallback})


async def _run_server():
    """Run the WebSocket server."""
    global _loop
    _loop = asyncio.get_event_loop()

    try:
        import websockets
        async with websockets.serve(
            _handler,
            "localhost",
            WS_PORT,
            ping_interval=30,
            ping_timeout=60,
        ):
            print(f"[WsBridge] WebSocket server running on ws://localhost:{WS_PORT}")
            await asyncio.Future()  # Run forever
    except ImportError:
        print("[WsBridge] websockets package not installed. Run: pip install websockets")
    except OSError as e:
        print(f"[WsBridge] Server start failed (port {WS_PORT} in use?): {e}")


# ── Agent V2 broadcast helpers ───────────────────────────────────────────────

def send_agent_v2_template_list(templates: list[dict]):
    """Push available workflow templates to the overlay."""
    broadcast_sync({"type": "agent_v2/template_list", "templates": templates})


def send_agent_v2_plan_ready(workflow: dict, estimated_steps: int, estimated_budget: int):
    """Push generated workflow plan to the overlay."""
    broadcast_sync({
        "type": "agent_v2/plan_ready",
        "workflow": workflow,
        "estimated_steps": estimated_steps,
        "estimated_budget": estimated_budget,
    })


def send_agent_v2_status_update(
    workflow_name: str,
    current_step: int,
    total_steps: int,
    current_app: str,
    current_action: str,
    steps_used: int,
    steps_budget: int,
    apps_chain: list[str],
):
    """Push real-time workflow status to the overlay."""
    broadcast_sync({
        "type": "agent_v2/status_update",
        "workflow_name": workflow_name,
        "current_step": current_step,
        "total_steps": total_steps,
        "current_app": current_app,
        "current_action": current_action,
        "steps_used": steps_used,
        "steps_budget": steps_budget,
        "apps_chain": apps_chain,
    })


def send_agent_v2_step_complete(step: dict, requires_decision: bool = False):
    """Push step completion to the overlay."""
    broadcast_sync({
        "type": "agent_v2/step_complete",
        "step": step,
        "requires_decision": requires_decision,
    })


def send_agent_v2_paused(pause_context: dict, live_screenshot: str = ""):
    """Push pause state to the overlay."""
    broadcast_sync({
        "type": "agent_v2/paused",
        "pause_context": pause_context,
        "live_screenshot": live_screenshot,
    })


def send_agent_v2_completed(summary: dict, total_steps_used: int, apps_used: list[str]):
    """Push workflow completion to the overlay."""
    broadcast_sync({
        "type": "agent_v2/completed",
        "summary": summary,
        "total_steps_used": total_steps_used,
        "apps_used": apps_used,
    })


def send_agent_v2_error(message: str, app: str = "", recoverable: bool = True):
    """Push workflow error to the overlay."""
    broadcast_sync({
        "type": "agent_v2/error",
        "message": message,
        "app": app,
        "recoverable": recoverable,
    })


# ── Agent V2 message handlers ────────────────────────────────────────────────

_v2_engine = None


def _get_v2_engine():
    global _v2_engine
    if _v2_engine is None:
        from core.agent_v2_engine import AgentV2Engine
        _v2_engine = AgentV2Engine()
    return _v2_engine


def _handle_agent_v2_initiate(msg: dict):
    """Handle agent_v2:initiate from overlay."""
    intent = msg.get("intent", "").strip()
    voice = msg.get("voice", False)
    engine = _get_v2_engine()
    try:
        session_id = engine.initiate_freeform(intent)
        print(f"[WsBridge] AgentV2 freeform started: {session_id}")
    except Exception as e:
        print(f"[WsBridge] AgentV2 initiate error: {e}")
        send_agent_v2_error(str(e), app="engine", recoverable=True)


def _handle_agent_v2_select_template(msg: dict):
    """Handle agent_v2:select_template from overlay."""
    template_id = msg.get("template_id", "").strip()
    params = msg.get("params", {})
    engine = _get_v2_engine()
    try:
        session_id = engine.initiate_workflow(template_id, params)
        print(f"[WsBridge] AgentV2 template started: {session_id}")
    except Exception as e:
        print(f"[WsBridge] AgentV2 template error: {e}")
        send_agent_v2_error(str(e), app="engine", recoverable=True)


def _handle_agent_v2_run_preset(msg: dict):
    """Handle agent_v2:run_preset from overlay."""
    preset_id = msg.get("preset_id", "").strip()
    intent = msg.get("intent", "").strip()
    params = msg.get("params", {})
    engine = _get_v2_engine()
    try:
        session_id = engine.initiate_preset(preset_id, intent, params)
        print(f"[WsBridge] AgentV2 preset started: {preset_id} session={session_id}")
    except Exception as e:
        print(f"[WsBridge] AgentV2 preset error: {e}")
        send_agent_v2_error(str(e), app="engine", recoverable=True)


def _handle_agent_v2_pause(msg: dict):
    """Handle agent_v2:pause from overlay."""
    reason = msg.get("reason", "user_request")
    engine = _get_v2_engine()
    engine.pause(reason)


def _handle_agent_v2_resume(msg: dict):
    """Handle agent_v2:resume from overlay."""
    engine = _get_v2_engine()
    engine.resume()


def _handle_agent_v2_decision(msg: dict):
    """Handle agent_v2:decision from overlay."""
    decision = msg.get("decision", "accept")
    engine = _get_v2_engine()
    engine.submit_decision(decision)


def _handle_agent_v2_abort(msg: dict):
    """Handle agent_v2:abort from overlay."""
    engine = _get_v2_engine()
    engine.abort()


# ── Workflow decision gates ──────────────────────────────────────────────────

_gate_manager = None

def _get_gate_manager():
    global _gate_manager
    if _gate_manager is None:
        from core.workflow_gates import GateManager
        _gate_manager = GateManager()
    return _gate_manager

def _handle_workflow_decision(msg: dict):
    """Handle workflow:decision from overlay — resolves a pending gate."""
    gate_id = msg.get("gate_id", "").strip()
    choice = msg.get("choice", "").strip()
    if gate_id and choice:
        manager = _get_gate_manager()
        manager.resolve(gate_id, choice)


def _handle_tunehub_trigger_learning(msg: dict):
    """Handle tunehub:trigger_learning from overlay."""
    intent = msg.get("intent", "").strip()
    if not intent:
        return
    engine = _get_v2_engine()
    result = engine.initiate_with_matching(intent, msg.get("params", {}))
    if result.get("action") == "learning":
        print(f"[WsBridge] TuneHub learning triggered: {intent}")
    else:
        print(f"[WsBridge] TuneHub matched action: {result.get('action')}")


def _handle_tunehub_approve_learned(msg: dict):
    """Handle tunehub:approve_learned from overlay."""
    template_id = msg.get("template_id", "").strip()
    if template_id:
        print(f"[WsBridge] Learned template approved: {template_id}")


def _handle_tunehub_reject_learned(msg: dict):
    """Handle tunehub:reject_learned from overlay."""
    template_id = msg.get("template_id", "").strip()
    reason = msg.get("reason", "")
    if template_id:
        try:
            from core.tune_hub.adaptive_matcher import delete_learned_template
            delete_learned_template(template_id)
            print(f"[WsBridge] Learned template rejected and deleted: {template_id} ({reason})")
        except Exception as e:
            print(f"[WsBridge] Failed to delete learned template: {e}")


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
