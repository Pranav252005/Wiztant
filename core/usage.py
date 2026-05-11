"""
Whiztant core/usage.py — tier-based usage tracking and rate limiting.
Uses Supabase as primary backend, falls back to local JSON if unreachable.
"""

import json
import os
from datetime import datetime
from pathlib import Path

USAGE_FILE = Path(__file__).resolve().parent.parent / "data" / "usage.json"

# Column name mapping: action -> Supabase column
_SUPABASE_COL = {
    "agent":  "agent_count",
    "vlm":    "vlm_count",
    "uitars": "uitars_count",
}

TIER_LIMITS = {
    "free": {
        "agent": 0,
        "vlm": 0,
        "uitars": 0,
    },
    "pro": {
        "agent": 50,
        "vlm": 30,
        "uitars": 30,
    },
    "power": {
        "agent": 200,
        "vlm": 200,
        "uitars": 200,
    },
    "trial": {
        "agent": 3,
        "vlm": 5,
        "uitars": 0,
    }
}


# =============================================================
#  TIER RESOLUTION — Supabase profile first, then .env fallback
# =============================================================

def get_tier() -> str:
    """Gets the user's tier. Tries Supabase profile first, falls back to .env."""
    env_tier = os.getenv("CURRENT_TIER", "").lower().strip()
    if env_tier in TIER_LIMITS:
        return env_tier
    try:
        from core.supabase_client import is_configured, get_profile
        if is_configured():
            profile = get_profile()
            tier = profile.get("tier", "").lower()
            if tier and tier in TIER_LIMITS:
                return tier
    except Exception:
        pass
    return os.getenv("CURRENT_TIER", "free").lower()


# =============================================================
#  LOAD USAGE — Supabase first, local JSON fallback
# =============================================================

def load_usage() -> dict:
    """Load current month's usage. Tries Supabase, falls back to local JSON."""
    month = datetime.now().strftime("%Y-%m")

    # Try Supabase
    try:
        from core.supabase_client import is_configured, get_usage as sb_get_usage
        if is_configured():
            sb_data = sb_get_usage(month)
            if sb_data and sb_data.get("user_id"):
                return {
                    "month": month,
                    "chat":   sb_data.get("chat_count", 0),
                    "agent":  sb_data.get("agent_count", 0),
                    "vlm":    sb_data.get("vlm_count", 0),
                    "uitars": sb_data.get("uitars_count", 0),
                }
    except Exception as e:
        print(f"[Usage] Supabase read failed: {e}")

    # Fallback to local JSON
    return _load_local()


def _load_local() -> dict:
    if not USAGE_FILE.exists():
        return _fresh_usage()
    try:
        with open(USAGE_FILE) as f:
            data = json.load(f)
        current_month = datetime.now().strftime("%Y-%m")
        if data.get("month") != current_month:
            data = _fresh_usage()
            _save_local(data)
        return data
    except Exception:
        return _fresh_usage()


def _fresh_usage() -> dict:
    return {
        "month": datetime.now().strftime("%Y-%m"),
        "chat": 0,
        "agent": 0,
        "vlm": 0,
        "uitars": 0,
    }


def _save_local(data: dict):
    try:
        USAGE_FILE.parent.mkdir(exist_ok=True)
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Usage] Local save error: {e}")


# Legacy compat
def save_usage(data: dict):
    _save_local(data)


# =============================================================
#  CHECK AND INCREMENT — Supabase first, local fallback
# =============================================================

def _limit_message(action: str, limit: int = 0, tier_has_none: bool = False) -> str:
    if tier_has_none or limit == 0:
        return f"{action.title()} is not available on your current plan. Upgrade at whiztant.app/pricing"
    return "You've hit your agent task limit for this month. Upgrade at whiztant.app/pricing"


def _offline_required_message(action: str) -> str:
    return "Agent mode needs an internet connection. Please turn on the internet and try again."


def check_usage(action: str, tier: str = None, fail_open: bool = False) -> tuple[bool, str]:
    """
    Check usage WITHOUT incrementing. Returns (allowed, message).

    fail_open=True  — if Supabase is configured but unreachable, allow the action
                      and fall back to the local counter.
    fail_open=False — if Supabase is configured but unreachable, block the action.
    """
    if tier is None:
        tier = get_tier()

    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(action, 0)
    if limit == 0:
        return False, _limit_message(action, tier_has_none=True)

    month = datetime.now().strftime("%Y-%m")
    supabase_online = False
    current = None

    try:
        from core.supabase_client import is_configured, get_current_user, get_usage as sb_get_usage
        if is_configured():
            user = get_current_user()
            if user and user.user:
                supabase_online = True
                sb_data = sb_get_usage(month)
                col = _SUPABASE_COL.get(action, f"{action}_count")
                current = sb_data.get(col, 0) if (sb_data and sb_data.get("user_id")) else 0
    except Exception as e:
        print(f"[Usage] Supabase check failed: {e}")

    if not supabase_online:
        if fail_open:
            print(f"[UsageGuard] Supabase offline — fail-open for {action}, using local counter")
            current = _load_local().get(action, 0)
        else:
            print(f"[UsageGuard] Supabase offline — fail-closed for {action}")
            return False, _offline_required_message(action)

    if current >= limit:
        return False, _limit_message(action, limit)

    remaining = limit - current
    return True, f"({remaining} {action} use{'s' if remaining != 1 else ''} remaining this month)"


def increment_usage_count(action: str, tier: str = None):
    """
    Increment usage counter after a successful action.
    Called separately from check_usage so errors don't burn quota.
    """
    if tier is None:
        tier = get_tier()
    month = datetime.now().strftime("%Y-%m")

    try:
        from core.supabase_client import is_configured, increment_usage as sb_increment
        if is_configured():
            sb_increment(action, month)
    except Exception:
        pass

    local = _load_local()
    local[action] = local.get(action, 0) + 1
    _save_local(local)


def get_remaining(action: str, tier: str = None) -> int:
    """Returns number of remaining uses this month. Uses local counter (fast, may lag Supabase)."""
    if tier is None:
        tier = get_tier()
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(action, 0)
    if limit == 0:
        return 0
    current = load_usage().get(action, 0)
    return max(0, limit - current)


def check_and_increment(action: str, tier: str = None) -> tuple[bool, str]:
    """
    Legacy combined check-and-increment. Kept for compatibility.
    Prefer check_usage() + increment_usage_count() for new code.
    """
    if tier is None:
        tier = get_tier()

    month = datetime.now().strftime("%Y-%m")
    usage = load_usage()
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(action, 0)
    current = usage.get(action, 0)

    if limit == 0:
        return False, _limit_message(action, tier_has_none=True)

    if current >= limit:
        return False, _limit_message(action, limit)

    # Increment in Supabase (non-blocking)
    try:
        from core.supabase_client import is_configured, increment_usage as sb_increment
        if is_configured():
            sb_increment(action, month)
    except Exception:
        pass

    local = _load_local()
    local[action] = local.get(action, 0) + 1
    _save_local(local)

    remaining = limit - (current + 1)
    return True, f"({remaining} {action} use{'s' if remaining != 1 else ''} remaining this month)"
