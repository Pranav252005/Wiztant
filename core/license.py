"""
Wiztant core/license.py — Lemon Squeezy license validation.

Flow:
  activate_license(key)  →  first-time activation, stores data/license.json
  get_current_tier()     →  reads cache; revalidates against LS API if >24h old
  validate_license(key)  →  direct LS API call (no cache write)
  deactivate_license()   →  uninstall / transfer
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

_ROOT = Path(__file__).resolve().parent.parent
LICENSE_FILE = _ROOT / "data" / "license.json"
CACHE_FILE   = _ROOT / "data" / "license_cache.json"
CACHE_TTL_HOURS = 24
INSTANCE_NAME   = "wiztant-desktop"

_LS_VALIDATE_URL   = "https://api.lemonsqueezy.com/v1/licenses/validate"
_LS_ACTIVATE_URL   = "https://api.lemonsqueezy.com/v1/licenses/activate"
_LS_DEACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/deactivate"


# ── helpers ──────────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.getenv("LEMONSQUEEZY_API_KEY", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "application/json",
    }


def _extract_tier(data: dict) -> str:
    """Extract tier string from a LS API response dict."""
    try:
        name = data.get("meta", {}).get("variant_name", "").lower()
        if "power" in name:
            return "power"
        if "pro" in name:
            return "pro"
    except Exception:
        pass
    return "free"


def _load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["cached_at"] = datetime.now().isoformat()
    CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cache_stale(cache: dict) -> bool:
    cached_at = cache.get("cached_at")
    if not cached_at:
        return True
    try:
        return datetime.now() - datetime.fromisoformat(cached_at) > timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return True


def _load_license_file() -> dict:
    try:
        if LICENSE_FILE.exists():
            return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _update_env_tier(tier: str):
    """Patch CURRENT_TIER= in .env so the next cold start picks up the right value."""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated, found = [], False
    for line in lines:
        if line.startswith("CURRENT_TIER="):
            updated.append(f"CURRENT_TIER={tier}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"CURRENT_TIER={tier}")
    env_path.write_text("\n".join(updated), encoding="utf-8")


# ── public API ────────────────────────────────────────────────────────────────

def validate_license(key: str) -> dict:
    """
    Validate a key against the Lemon Squeezy API.
    Retries up to 3 times on network errors; falls back to free on failure.
    Returns: {valid, tier, expiry, message, instance_id}
    """
    key = key.strip()
    if not key:
        return {"valid": False, "tier": "free", "expiry": "", "message": "No license key provided.", "instance_id": ""}

    if not _api_key():
        return {"valid": False, "tier": "free", "expiry": "", "message": "LEMONSQUEEZY_API_KEY not set in .env", "instance_id": ""}

    last_err = ""
    for attempt in range(3):
        try:
            resp = requests.post(
                _LS_VALIDATE_URL,
                headers=_headers(),
                data={"license_key": key, "instance_name": INSTANCE_NAME},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("valid"):
                tier = _extract_tier(data)
                expiry = data.get("license_key", {}).get("expires_at") or ""
                instance_id = data.get("instance", {}).get("id") or ""
                return {"valid": True, "tier": tier, "expiry": expiry,
                        "message": f"Valid {tier.upper()} license", "instance_id": instance_id}
            # API returned but key is invalid
            error = data.get("error", "Invalid license key.")
            return {"valid": False, "tier": "free", "expiry": "", "message": error, "instance_id": ""}
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                time.sleep(1.5)

    # All 3 attempts failed — network issue
    try:
        from core.toast import show_toast
        show_toast("License check failed — running as Free tier. Check your internet.", "⚠ Wiztant")
    except Exception:
        pass
    return {"valid": False, "tier": "free", "expiry": "", "message": f"Network error: {last_err}", "instance_id": ""}


def activate_license(key: str) -> bool:
    """
    First-time activation. Calls the LS activate endpoint, saves license.json
    and primes the cache. Returns True on success.
    """
    key = key.strip()
    if not key or not _api_key():
        return False

    try:
        resp = requests.post(
            _LS_ACTIVATE_URL,
            headers=_headers(),
            data={"license_key": key, "instance_name": INSTANCE_NAME},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code in (200, 201) and data.get("activated"):
            tier = _extract_tier(data)
            expiry = data.get("license_key", {}).get("expires_at") or ""
            instance_id = data.get("instance", {}).get("id") or ""

            # Persist
            info = {
                "key": key,
                "tier": tier,
                "expiry": expiry,
                "instance_id": instance_id,
                "activated_at": datetime.now().isoformat(),
            }
            LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
            LICENSE_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")
            _save_cache({"valid": True, "tier": tier, "expiry": expiry, "instance_id": instance_id})
            _update_env_tier(tier)
            os.environ["CURRENT_TIER"] = tier
            return True
        return False
    except Exception:
        return False


def deactivate_license() -> bool:
    """
    Deactivate the current license instance (uninstall / machine transfer).
    Returns True on success.
    """
    saved = _load_license_file()
    key = saved.get("key", "")
    instance_id = saved.get("instance_id", "")
    if not key or not instance_id or not _api_key():
        return False

    try:
        resp = requests.post(
            _LS_DEACTIVATE_URL,
            headers=_headers(),
            data={"license_key": key, "instance_id": instance_id},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("deactivated"):
            for f in (LICENSE_FILE, CACHE_FILE):
                if f.exists():
                    f.unlink()
            _update_env_tier("free")
            os.environ["CURRENT_TIER"] = "free"
            return True
        return False
    except Exception:
        return False


def get_current_tier() -> str:
    """
    Returns the active tier string ("free" / "pro" / "power").
    Reads from the 24-hour cache; revalidates against LS if stale.
    Never raises — always returns a string.
    """
    saved = _load_license_file()
    key = saved.get("key", "")
    if not key:
        return "free"

    cache = _load_cache()
    if not _cache_stale(cache):
        return cache.get("tier", "free")

    # Cache is stale — revalidate
    result = validate_license(key)
    if result["valid"]:
        _save_cache({
            "valid": True,
            "tier": result["tier"],
            "expiry": result["expiry"],
            "instance_id": result.get("instance_id", ""),
        })
        _update_env_tier(result["tier"])
        os.environ["CURRENT_TIER"] = result["tier"]
        return result["tier"]

    # Validation failed (network?) — honour cached tier if available
    return cache.get("tier", "free")
