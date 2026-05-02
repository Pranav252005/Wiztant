"""
Whiztant core/supabase_client.py — Supabase client for auth, profiles, and usage.
Falls back gracefully if Supabase is unreachable or not configured.
Persists session to data/session.json for auto-login on restart.
"""

import os
import json
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = _PROJECT_ROOT / "data" / "session.json"

_client = None
_last_url = ""
_last_key = ""


def _get_env(key: str, fallbacks: tuple = ()) -> str:
    """Read env var with optional fallback names."""
    val = os.getenv(key, "").strip()
    if val:
        return val
    for fb in fallbacks:
        val = os.getenv(fb, "").strip()
        if val:
            return val
    return ""


def get_client():
    """Lazy-init Supabase client. Returns None if not configured."""
    global _client, _last_url, _last_key
    url = _get_env("SUPABASE_URL", ("NEXT_PUBLIC_SUPABASE_URL",)).strip()
    key = _get_env("SUPABASE_PUBLISHABLE_KEY", ("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY")).strip()

    # Auto-reload if env vars changed since last init
    if _client is not None and (url != _last_url or key != _last_key):
        print("[Supabase] Env vars changed — reloading client...")
        _client = None

    if _client is None:
        if not url or not key or "your-project" in url:
            print(f"[Supabase] Not configured (URL={'set' if url else 'MISSING'}, KEY={'set' if key else 'MISSING'})")
            _last_url = url
            _last_key = key
            return None
        # Diagnostic: show key prefix to verify it's not quoted
        key_prefix = key[:8] if len(key) > 8 else key
        key_suffix = "..." if len(key) > 8 else ""
        print(f"[Supabase] Attempting init with URL={url} KEY={key_prefix}{key_suffix}")

        # Publishable keys (sb_publishable_...) are NOT JWTs and won't work with supabase-py.
        # The Python client requires the anon key (a JWT starting with eyJ...).
        if key.startswith("sb_publishable_") or key.startswith("sb_") and "." not in key:
            print("[Supabase] ERROR: You are using a publishable key, but the Python client requires the anon key.")
            print("[Supabase] Fix: Set SUPABASE_ANON_KEY in your .env instead of SUPABASE_PUBLISHABLE_KEY.")
            print("[Supabase] The anon key is a long JWT that starts with 'eyJ...' and is found in Supabase Settings > API.")
            _last_url = url
            _last_key = key
            return None

        try:
            from supabase import create_client
            _client = create_client(url, key)
            _last_url = url
            _last_key = key
            print(f"[Supabase] Client initialized for {url}")
        except Exception as e:
            err = str(e)
            if "Invalid API key" in err:
                print(f"[Supabase] Init failed: {err}")
                print("[Supabase] The key you provided is not a valid JWT. Use SUPABASE_ANON_KEY (starts with eyJ...), not the publishable key.")
            else:
                print(f"[Supabase] Init failed: {e}")
            _client = None
            _last_url = ""
            _last_key = ""
            return None
    return _client


def reload_client():
    """Force re-read env vars and re-create the Supabase client. Call after updating .env."""
    global _client, _last_url, _last_key
    _client = None
    _last_url = ""
    _last_key = ""
    return get_client()


def is_configured() -> bool:
    """Returns True if Supabase credentials are set and valid."""
    return get_client() is not None


# =============================================================
#  SESSION PERSISTENCE
# =============================================================

def save_session(access_token: str, refresh_token: str):
    """Save session tokens to data/session.json."""
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "saved_at": datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Supabase] Session save error: {e}")


def load_session() -> dict:
    """Load saved session tokens. Returns {} if none."""
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def clear_session():
    """Delete saved session file."""
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass


def restore_session() -> bool:
    """
    Try to restore a saved session. Returns True if user is now signed in.
    This is called on app startup before showing the login screen.
    """
    saved = load_session()
    if not saved.get("access_token") or not saved.get("refresh_token"):
        return False

    client = get_client()
    if not client:
        return False

    try:
        response = client.auth.set_session(
            access_token=saved["access_token"],
            refresh_token=saved["refresh_token"],
        )
        if response and response.user:
            print(f"[Supabase] Session restored for {response.user.email}")
            # Re-save refreshed tokens
            if response.session:
                save_session(response.session.access_token, response.session.refresh_token)
            return True
    except Exception as e:
        print(f"[Supabase] Session restore failed: {e}")
        clear_session()

    return False


# =============================================================
#  AUTH
# =============================================================

def get_current_user():
    """Returns the currently signed-in user or None."""
    try:
        client = get_client()
        if not client:
            return None
        return client.auth.get_user()
    except Exception:
        return None


def sign_in(email: str, password: str) -> dict:
    """Signs in user with email + password. Saves session on success."""
    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Supabase not configured. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env"}
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        # Persist session
        if response.session:
            save_session(response.session.access_token, response.session.refresh_token)
        return {"success": True, "user": response.user, "session": response.session}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_up(email: str, password: str) -> dict:
    """Creates new account. Returns user or error."""
    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Supabase not configured. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env"}
        # Increase timeout for slow connections
        response = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": None
            }
        })
        return {"success": True, "user": response.user}
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return {"success": False, "error": "Connection timeout. Please check your internet and try again."}
        return {"success": False, "error": error_msg}


def sign_in_with_google() -> dict:
    """Initiates Google OAuth sign-in. Returns auth URL."""
    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Supabase not configured. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env"}
        
        # Get OAuth URL for Google
        response = client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "http://localhost:54321/auth/callback"
            }
        })
        return {"success": True, "url": response.url}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_out():
    """Signs out current user and clears saved session."""
    try:
        client = get_client()
        if client:
            client.auth.sign_out()
    except Exception:
        pass
    clear_session()


def get_profile() -> dict:
    """Gets current user's profile. Tier is sourced from the local license file."""
    try:
        from core.license import get_current_tier
        tier = get_current_tier()
    except Exception:
        tier = "free"
    return {"tier": tier}


def get_usage(month: str) -> dict:
    """Gets usage for a specific month (format: '2025-03')."""
    try:
        user = get_current_user()
        if not user:
            return {}
        client = get_client()
        response = client.table("usage").select("*").eq(
            "user_id", user.user.id).eq("month", month).single().execute()
        return response.data or {}
    except Exception:
        return {}


def increment_usage(action: str, month: str) -> bool:
    """Increments usage counter for action in given month. Returns True if success."""
    try:
        user = get_current_user()
        if not user:
            return False

        user_id = user.user.id
        col = f"{action}_count"
        client = get_client()

        # Upsert usage row
        existing = get_usage(month)
        if existing and existing.get("user_id"):
            new_count = existing.get(col, 0) + 1
            client.table("usage").update(
                {col: new_count, "updated_at": datetime.utcnow().isoformat()}
            ).eq("user_id", user_id).eq("month", month).execute()
        else:
            client.table("usage").insert({
                "user_id": user_id,
                "month": month,
                col: 1
            }).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Usage increment error: {e}")
        return False
