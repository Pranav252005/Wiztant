"""
Integrations vault for the Wiztant agent.

Stores per-app authorization so the agent can log into apps automatically.

Two auth styles:
  - "oauth"      : real OAuth 2.0 (PKCE loopback). Used for apps that support it
                   (Google, Slack, GitHub, ...). A short-lived browser flow yields
                   an access/refresh token.
  - "credential" : a credential vault for apps WITHOUT OAuth. The screen-driven
                   UI-TARS agent types these fields (email, phone, password, ...)
                   into the app's login screen.

Security model (per product requirement):
  - Nothing is ever stored in the app's / Wiztant's cloud database.
  - Everything lives ONLY on the user's machine, encrypted at rest with Fernet.
  - The encryption key is kept in the OS keyring when available, otherwise in a
    0600 key file under the user's home directory.
  - The plaintext secrets are NEVER exposed to the planner LLM. Only the list of
    app names + which field keys exist is surfaced (see list_public()).
"""

from __future__ import annotations

import base64
import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

# ── Storage locations (user's machine only — never the app DB) ──────────────
_VAULT_DIR = Path.home() / ".wiztant"
_VAULT_FILE = _VAULT_DIR / "integrations.enc"
_KEY_FILE = _VAULT_DIR / "vault.key"
_KEYRING_SERVICE = "wiztant-integrations"
_KEYRING_USER = "vault-key"


# ── Encryption key management ───────────────────────────────────────────────
def _ensure_dir() -> None:
    _VAULT_DIR.mkdir(parents=True, exist_ok=True)
    # Best-effort lock down the directory (no-op on Windows for these flags).
    try:
        os.chmod(_VAULT_DIR, stat.S_IRWXU)
    except OSError:
        pass


def _load_key() -> bytes:
    """Return the Fernet key, creating + persisting one on first use.

    Prefers the OS keyring; falls back to a 0600 key file in ~/.wiztant.
    """
    # 1) Try OS keyring (most secure; survives even if the key file is deleted).
    try:
        import keyring  # type: ignore

        existing = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        if existing:
            return existing.encode("utf-8")
        new_key = Fernet.generate_key()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, new_key.decode("utf-8"))
        return new_key
    except Exception:
        pass  # keyring not installed / no backend — fall back to key file.

    # 2) Local key file.
    _ensure_dir()
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    new_key = Fernet.generate_key()
    _KEY_FILE.write_bytes(new_key)
    try:
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass
    return new_key


def _fernet() -> Fernet:
    return Fernet(_load_key())


# ── Low-level encrypted read/write ──────────────────────────────────────────
def _read_all() -> List[Dict[str, Any]]:
    if not _VAULT_FILE.exists():
        return []
    try:
        blob = _VAULT_FILE.read_bytes()
        if not blob:
            return []
        raw = _fernet().decrypt(blob)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, list) else []
    except (InvalidToken, ValueError, json.JSONDecodeError):
        # Corrupt / key mismatch — treat as empty rather than crash the agent.
        return []


def _write_all(items: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    raw = json.dumps(items).encode("utf-8")
    blob = _fernet().encrypt(raw)
    _VAULT_FILE.write_bytes(blob)
    try:
        os.chmod(_VAULT_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def _now() -> int:
    return int(time.time())


# ── Public CRUD API ─────────────────────────────────────────────────────────
def list_integrations() -> List[Dict[str, Any]]:
    """Full records INCLUDING secrets. Internal / executor use only."""
    return _read_all()


def list_public() -> List[Dict[str, Any]]:
    """Safe view for the UI and the planner LLM — no secret values.

    Reveals only: id, app, auth_type, which field keys are set, and whether an
    OAuth token is present. Never the actual passwords / tokens.
    """
    out: List[Dict[str, Any]] = []
    for it in _read_all():
        fields = it.get("fields", {}) or {}
        oauth = it.get("oauth", {}) or {}
        out.append(
            {
                "id": it.get("id"),
                "app": it.get("app"),
                "auth_type": it.get("auth_type", "credential"),
                "field_keys": sorted(fields.keys()),
                "oauth_connected": bool(oauth.get("access_token")),
                "updated_at": it.get("updated_at"),
            }
        )
    return out


def save_integration(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update an integration. Returns the public view of it.

    payload: { id?, app, auth_type, fields?: {key: value}, oauth?: {...} }
    """
    app = (payload.get("app") or "").strip()
    if not app:
        raise ValueError("app name is required")
    auth_type = payload.get("auth_type") or "credential"
    if auth_type not in ("credential", "oauth"):
        raise ValueError(f"invalid auth_type: {auth_type!r}")
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        fields = {}
    # Drop empty-string fields so we don't persist blanks.
    fields = {k: v for k, v in fields.items() if isinstance(v, str) and v.strip()}

    items = _read_all()
    iid = payload.get("id")
    record: Optional[Dict[str, Any]] = None
    if iid:
        record = next((x for x in items if x.get("id") == iid), None)

    if record is None:
        record = {
            "id": str(uuid.uuid4()),
            "app": app,
            "auth_type": auth_type,
            "fields": {},
            "oauth": {},
            "created_at": _now(),
        }
        items.append(record)

    record["app"] = app
    record["auth_type"] = auth_type
    # Merge fields (so a partial update doesn't wipe untouched secrets).
    record.setdefault("fields", {}).update(fields)
    if isinstance(payload.get("oauth"), dict):
        record.setdefault("oauth", {}).update(payload["oauth"])
    record["updated_at"] = _now()

    _write_all(items)
    pub = next(x for x in list_public() if x["id"] == record["id"])
    return pub


def delete_integration(iid: str) -> bool:
    items = _read_all()
    new_items = [x for x in items if x.get("id") != iid]
    if len(new_items) == len(items):
        return False
    _write_all(new_items)
    return True


def get_credentials(app: str) -> Optional[Dict[str, Any]]:
    """Return the secret credentials/token for an app (executor use).

    Matches case-insensitively on app name. Returns None if not configured.
    """
    target = (app or "").strip().lower()
    for it in _read_all():
        if (it.get("app") or "").strip().lower() == target:
            return {
                "app": it.get("app"),
                "auth_type": it.get("auth_type", "credential"),
                "fields": it.get("fields", {}),
                "oauth": it.get("oauth", {}),
            }
    return None


def agent_context_block() -> str:
    """A short text block listing available integrations for the planner prompt.

    Contains NO secrets — only which apps are connected and what login fields
    are available, so the planner knows it CAN log into them automatically.
    """
    pub = list_public()
    if not pub:
        return ""
    lines = ["Connected app integrations (the agent can authorize these automatically):"]
    has_vault = False
    for it in pub:
        if it["auth_type"] == "oauth" and it["oauth_connected"]:
            lines.append(f"  - {it['app']}: OAuth connected (token available).")
        elif it["field_keys"]:
            has_vault = True
            lines.append(
                f"  - {it['app']}: stored login fields [{', '.join(it['field_keys'])}]."
            )
    if has_vault:
        lines.append(
            "To fill a login field, emit the placeholder {{cred:App Name:field_key}} as the "
            "text to type (e.g. {{cred:Slack:password}}). The real secret is substituted at "
            "type time and is never shown to you. If the app asks for an OTP / 2FA code, pause "
            "and ask the user for it — never guess it."
        )
    return "\n".join(lines)


# ── OAuth 2.0 (PKCE loopback) ───────────────────────────────────────────────
# Provider registry. client_id/secret are supplied by the user (env or the
# integration record) — Wiztant ships no embedded app credentials.
OAUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/userinfo.email"],
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["users:read"],
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes": ["read:user"],
    },
}


# Map common app names → OAuth provider so we can auto-detect when the user
# never set anything up in Settings.
_APP_PROVIDER_ALIASES: Dict[str, str] = {
    "gmail": "google",
    "google": "google",
    "google drive": "google",
    "google calendar": "google",
    "youtube": "google",
    "slack": "slack",
    "github": "github",
}


def detect_provider(app: str) -> Optional[str]:
    """Return the OAuth provider for an app name, or None if not OAuth-capable."""
    key = (app or "").strip().lower()
    if key in _APP_PROVIDER_ALIASES:
        return _APP_PROVIDER_ALIASES[key]
    if key in OAUTH_PROVIDERS:
        return key
    return None


def _builtin_oauth_client(provider: str) -> tuple[str, str]:
    """Wiztant's own registered OAuth client for a provider, from env config.

    Lets the agent run OAuth directly without the user pasting a client ID.
    Set e.g. WIZTANT_GOOGLE_CLIENT_ID / WIZTANT_GOOGLE_CLIENT_SECRET.
    Returns ("", "") if not configured.
    """
    up = provider.upper()
    return (
        os.environ.get(f"WIZTANT_{up}_CLIENT_ID", ""),
        os.environ.get(f"WIZTANT_{up}_CLIENT_SECRET", ""),
    )


def ensure_authorized(app: str) -> Dict[str, Any]:
    """Make sure the agent can sign into `app`, authorizing on demand.

    Resolution order:
      1. Already in the vault (credential fields or a live OAuth token) → ok.
      2. Not configured, but the app maps to a known OAuth provider AND a
         built-in client ID is available → run OAuth directly now and store it.
      3. Otherwise → caller must collect credentials from the user.

    Returns a status dict:
      {status: "ok"|"oauth_started"|"needs_setup", app, auth_type?, error?}
    This is blocking when it runs OAuth (opens the browser, waits for redirect).
    """
    existing = get_credentials(app)
    if existing:
        if existing.get("auth_type") == "oauth" and (existing.get("oauth") or {}).get("access_token"):
            return {"status": "ok", "app": app, "auth_type": "oauth"}
        if existing.get("fields"):
            return {"status": "ok", "app": app, "auth_type": "credential"}

    provider = detect_provider(app)
    if provider:
        client_id, client_secret = _builtin_oauth_client(provider)
        if client_id:
            try:
                tok = run_oauth_flow(provider, client_id, client_secret)
                save_integration({
                    "app": app,
                    "auth_type": "oauth",
                    "oauth": tok,
                })
                return {"status": "ok", "app": app, "auth_type": "oauth"}
            except Exception as e:
                return {"status": "needs_setup", "app": app, "error": str(e)}

    # No vault entry, and OAuth can't run unattended → ask the user to set up.
    return {"status": "needs_setup", "app": app, "provider": provider}


def _pkce_pair() -> tuple[str, str]:
    import hashlib

    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode("ascii")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


def oauth_provider_known(provider: str) -> bool:
    return (provider or "").strip().lower() in OAUTH_PROVIDERS


def run_oauth_flow(provider: str, client_id: str, client_secret: str = "", timeout: int = 180) -> Dict[str, Any]:
    """Run a blocking PKCE loopback OAuth flow.

    Opens the browser, spins up a localhost redirect server, exchanges the code
    for tokens. Returns {access_token, refresh_token?, expires_in?, raw}.

    Designed to be run in a background thread (it blocks until redirect/timeout).
    """
    import http.server
    import socket
    import threading
    import urllib.parse
    import urllib.request
    import webbrowser

    provider = provider.strip().lower()
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"unknown OAuth provider: {provider}")
    if not client_id:
        raise ValueError("client_id is required for OAuth")

    # Reserve a loopback port.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    verifier, challenge = _pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = cfg["auth_url"] + "?" + urllib.parse.urlencode(params)

    result: Dict[str, Any] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if "code" in qs and qs.get("state", [""])[0] == state:
                result["code"] = qs["code"][0]
                self.wfile.write(b"<h2>Wiztant: authorization complete. You can close this tab.</h2>")
            else:
                result["error"] = qs.get("error", ["unknown"])[0]
                self.wfile.write(b"<h2>Wiztant: authorization failed. You can close this tab.</h2>")

        def log_message(self, *_args):  # silence
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = timeout
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    webbrowser.open(auth_url)
    t.join(timeout + 5)
    server.server_close()

    if "code" not in result:
        raise RuntimeError(f"OAuth failed: {result.get('error', 'timeout')}")

    # Exchange the code for tokens.
    token_params = {
        "client_id": client_id,
        "code": result["code"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }
    if client_secret:
        token_params["client_secret"] = client_secret
    body = urllib.parse.urlencode(token_params).encode("ascii")
    req = urllib.request.Request(
        cfg["token_url"],
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))

    return {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "connected_at": _now(),
        "raw": token_data,
    }
