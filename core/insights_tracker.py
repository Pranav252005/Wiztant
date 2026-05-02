"""
Whiztant core/insights_tracker.py — Usage analytics for the Insights dashboard.
Tracks dictation words, fixes, prompts, file touches, voice commands, and streaks.
Syncs to Supabase when online; falls back to local JSON.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSIGHTS_FILE = _PROJECT_ROOT / "data" / "insights.json"

# Column mapping: event_type -> (lifetime_col, daily_col)
_EVENT_COLS = {
    "words_dictated":   ("total_words_dictated", "words_dictated"),
    "fixes_made":       ("total_fixes_made",     "fixes_made"),
    "words_removed":    ("total_words_removed",  "words_removed"),
    "dictionary_used":  ("dictionary_items_used", "dictionary_items_used"),
    "work_message":     ("work_messages",        "work_messages"),
    "ai_prompt":        ("ai_prompts",           "ai_prompts"),
    "personal_message": ("personal_messages",    "personal_messages"),
    "document_touched": ("documents_touched",    "documents_touched"),
    "voice_command":    ("voice_commands",       "voice_commands"),
    "other_task":       ("other_tasks",          "other_tasks"),
    "app_opened":       ("apps_used",            "apps_used"),
}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_local() -> dict:
    if not INSIGHTS_FILE.exists():
        return _fresh_local()
    try:
        with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _fresh_local()


def _fresh_local() -> dict:
    return {
        "lifetime": {k: 0 for k, _ in _EVENT_COLS.values()},
        "daily": {},
        "current_streak": 0,
        "longest_streak": 0,
        "last_active_date": None,
    }


def _save_local(data: dict):
    try:
        INSIGHTS_FILE.parent.mkdir(exist_ok=True)
        with open(INSIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Insights] Local save error: {e}")


def _get_user_id() -> Optional[str]:
    """Get current Supabase user id if available."""
    try:
        from core.supabase_client import get_current_user
        user = get_current_user()
        if user and user.user:
            return str(user.user.id)
    except Exception:
        pass
    return None


def _sb_upsert_lifetime(user_id: str, lifetime: dict):
    """Upsert lifetime counters to Supabase."""
    try:
        from core.supabase_client import get_client
        client = get_client()
        if not client:
            return False
        row = {"user_id": user_id, "updated_at": datetime.utcnow().isoformat()}
        for _, (life_col, _) in _EVENT_COLS.items():
            row[life_col] = lifetime.get(life_col, 0)
        row["current_streak"] = lifetime.get("current_streak", 0)
        row["longest_streak"] = lifetime.get("longest_streak", 0)
        client.table("user_insights_lifetime").upsert(row, on_conflict="user_id").execute()
        return True
    except Exception as e:
        print(f"[Insights] Supabase lifetime upsert error: {e}")
        return False


def _sb_upsert_daily(user_id: str, date: str, daily: dict):
    """Upsert a single day's counters to Supabase."""
    try:
        from core.supabase_client import get_client
        client = get_client()
        if not client:
            return False
        row = {"user_id": user_id, "date": date}
        activity = 0
        for _, (_, day_col) in _EVENT_COLS.items():
            val = daily.get(day_col, 0)
            row[day_col] = val
            activity += val
        row["activity_score"] = activity
        client.table("user_insights_daily").upsert(row, on_conflict="user_id,date").execute()
        return True
    except Exception as e:
        print(f"[Insights] Supabase daily upsert error: {e}")
        return False


def _broadcast_insights(lifetime: dict, daily: dict):
    """Broadcast latest insights to the overlay via WebSocket."""
    try:
        from core.ws_bridge import broadcast_sync
        payload = {
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
            "current_streak": lifetime.get("current_streak", 0),
            "longest_streak": lifetime.get("longest_streak", 0),
            "today": daily,
        }
        broadcast_sync({"type": "insights_update", "payload": payload})
    except Exception:
        pass


def record_event(event_type: str, value: int = 1):
    """
    Record a usage event. Updates local JSON immediately, then tries Supabase.
    Also recalculates streaks and broadcasts the update.

    event_type: one of the keys in _EVENT_COLS, e.g. 'words_dictated', 'ai_prompt', etc.
    value: how much to increment (default 1).
    """
    if event_type not in _EVENT_COLS:
        print(f"[Insights] Unknown event type: {event_type}")
        return

    data = _load_local()
    life_col, day_col = _EVENT_COLS[event_type]
    today = _today()

    # Update lifetime
    data["lifetime"][life_col] = data["lifetime"].get(life_col, 0) + value

    # Update daily
    if today not in data["daily"]:
        data["daily"][today] = {}
    data["daily"][today][day_col] = data["daily"][today].get(day_col, 0) + value

    # Recalculate streaks
    _recalc_streaks(data)

    _save_local(data)

    # Try Supabase sync
    user_id = _get_user_id()
    if user_id:
        _sb_upsert_lifetime(user_id, data["lifetime"])
        _sb_upsert_daily(user_id, today, data["daily"][today])

    # Broadcast to overlay
    _broadcast_insights(data["lifetime"], data["daily"].get(today, {}))


def _recalc_streaks(data: dict):
    """Recalculate current and longest streak from daily history."""
    daily = data.get("daily", {})
    if not daily:
        data["current_streak"] = 0
        data["longest_streak"] = 0
        return

    # Build sorted list of active dates (any activity > 0)
    active_dates = set()
    for date_str, counts in daily.items():
        total = sum(v for v in counts.values() if isinstance(v, (int, float)))
        if total > 0:
            active_dates.add(datetime.strptime(date_str, "%Y-%m-%d").date())

    if not active_dates:
        data["current_streak"] = 0
        data["longest_streak"] = 0
        return

    sorted_dates = sorted(active_dates, reverse=True)
    today_date = datetime.now().date()

    # Current streak: consecutive days ending today or yesterday
    current = 0
    check_date = today_date
    while check_date in active_dates:
        current += 1
        check_date -= timedelta(days=1)

    # If today is not active, check from yesterday
    if current == 0 and (today_date - timedelta(days=1)) in active_dates:
        check_date = today_date - timedelta(days=1)
        while check_date in active_dates:
            current += 1
            check_date -= timedelta(days=1)

    # Longest streak
    longest = 0
    temp = 0
    all_sorted = sorted(active_dates)
    for i, d in enumerate(all_sorted):
        if i == 0 or d == all_sorted[i - 1] + timedelta(days=1):
            temp += 1
        else:
            longest = max(longest, temp)
            temp = 1
    longest = max(longest, temp)

    data["current_streak"] = current
    data["longest_streak"] = longest
    data["last_active_date"] = sorted_dates[0].isoformat()


def load_insights() -> dict:
    """
    Load insights. Tries Supabase first, falls back to local JSON.
    Returns dict with lifetime counters + last 180 daily rows + streaks.
    """
    user_id = _get_user_id()
    if user_id:
        try:
            from core.supabase_client import get_client
            client = get_client()
            if client:
                # Lifetime
                life_resp = (
                    client.table("user_insights_lifetime")
                    .select("*")
                    .eq("user_id", user_id)
                    .single()
                    .execute()
                )
                lifetime = life_resp.data or {}

                # Daily (last 180 days)
                cutoff = (datetime.now() - timedelta(days=180)).isoformat()
                day_resp = (
                    client.table("user_insights_daily")
                    .select("*")
                    .eq("user_id", user_id)
                    .gte("date", cutoff[:10])
                    .order("date", desc=True)
                    .execute()
                )
                daily_rows = day_resp.data or []
                daily = {r["date"]: {k: r.get(k, 0) for k, _ in _EVENT_COLS.values()} for r in daily_rows}

                return {
                    "lifetime": lifetime,
                    "daily": daily,
                    "current_streak": lifetime.get("current_streak", 0),
                    "longest_streak": lifetime.get("longest_streak", 0),
                }
        except Exception as e:
            print(f"[Insights] Supabase load failed: {e}")

    # Fallback to local
    data = _load_local()
    return {
        "lifetime": data.get("lifetime", {}),
        "daily": data.get("daily", {}),
        "current_streak": data.get("current_streak", 0),
        "longest_streak": data.get("longest_streak", 0),
    }


def get_daily_summary(days: int = 180) -> List[dict]:
    """Return daily activity rows for the heatmap, newest first."""
    insights = load_insights()
    daily = insights.get("daily", {})
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    result = []
    for date_str in sorted(daily.keys(), reverse=True):
        if date_str >= cutoff:
            row = {"date": date_str, **daily[date_str]}
            row["activity_score"] = sum(
                v for k, v in daily[date_str].items()
                if k != "activity_score" and isinstance(v, (int, float))
            )
            result.append(row)
    return result


def reset_all():
    """Reset all insights to zero (for testing or fresh start)."""
    fresh = _fresh_local()
    _save_local(fresh)
    user_id = _get_user_id()
    if user_id:
        try:
            from core.supabase_client import get_client
            client = get_client()
            if client:
                client.table("user_insights_lifetime").delete().eq("user_id", user_id).execute()
                client.table("user_insights_daily").delete().eq("user_id", user_id).execute()
        except Exception as e:
            print(f"[Insights] Supabase reset error: {e}")
    _broadcast_insights(fresh["lifetime"], {})
