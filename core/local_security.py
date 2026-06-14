"""
core/local_security.py — Origin allowlist for the local loopback servers.

Both loopback services (the FastAPI bridge on :8765 and the WebSocket bridge on
:9120) bind to 127.0.0.1, but binding to localhost is NOT an access control:

  * WebSockets are exempt from the browser same-origin policy, so any web page
    the user visits can open ws://localhost:9120 and drive the agent, read
    dictation memory, or inject entries into the credential vault.
  * Cross-origin "simple" POSTs (e.g. to /agent/run) execute server-side even
    when CORS blocks the attacker from reading the response — the side effect
    still happens.

The only clients that legitimately talk to these ports are:
  * the Electron main process (Node `ws` / Node `fetch`) — sends NO Origin header
  * the Electron renderer windows — send one of the origins below

So the rule is: allow a request when it has no Origin header, or its Origin is
one we ship. Reject anything else (i.e. a remote web page). This closes the
browser-driven CSRF / cross-site-WebSocket-hijacking surface without needing a
shared token threaded through every client.
"""

from __future__ import annotations

from typing import Optional

# Origins the Electron renderer windows can present, across dev and packaged
# builds. Kept in sync with the CORS list in core/server.py and the CSP
# connect-src in ui/whiztant-overlay/src/renderer/overlay/index.html.
ALLOWED_ORIGINS = frozenset(
    {
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "app://.",
        "file://",
        "null",
    }
)


def origin_allowed(origin: Optional[str]) -> bool:
    """True if a request bearing this Origin header may be served.

    A missing/empty Origin (the Electron main process and other non-browser
    clients) is allowed; a present Origin must be one we ship.
    """
    if not origin:
        return True
    return origin in ALLOWED_ORIGINS
