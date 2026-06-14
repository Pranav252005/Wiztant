"""
core/guardrails.py — Agent safety guardrails.

Provides pre-execution checks: destructive action detection, coordinate
validation, and loop detection. Designed to be called inside vlm._phase2_loop()
and agent_unified.py vision loop.
"""

from __future__ import annotations

import re
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List

# Screen bounds (conservative — agent should not click near edges)
SCREEN_MIN_X = 5
SCREEN_MIN_Y = 5
SCREEN_MAX_X = 3840  # supports up to 4K
SCREEN_MAX_Y = 2160

# =============================================================
#  DESTRUCTIVE ACTION PATTERNS (Expanded)
# =============================================================

DESTRUCTIVE_KEYWORDS = [
    # Classic destructive
    r"\bdelete\b.*\bfiles?\b",
    r"\bremove\b.*\bfiles?\b",
    r"\bformat\b.*\b(drive|disk|partition|volume)\b",
    r"\b(rm|del)\b.*(-rf?|/s|/q)\b",
    r"\bdrop\b.*\b(table|database|db)\b",
    r"\btruncate\b.*\btable\b",
    r"\buninstall\b.*\b(program|app|software)\b",
    r"\berase\b.*\b(disk|drive|partition)\b",
    r"\bwipe\b.*\b(disk|drive|partition|data)\b",
    r"\bshutdown\b",
    r"\brestart\b.*\b(computer|system|pc)\b",
    r"\bterminate\b.*\bprocess\b",
    r"\bkill\b.*\bprocess\b",
    r"\bempty\b.*\b(recycle|trash)\b",
    # LOLBAS vectors
    r"\bpowershell\s+(-enc| -encodedcommand| -ep bypass)\b",
    r"\bcertutil\s+(-urlcache| -decode)\b",
    r"\bbitsadmin\b",
    r"\bregsvr32\s+(\/s|\.\\|https?://)\b",
    r"\bmshta\b",
    r"\brundll32\b.*\.(dll|#,)\b",
    r"\bInvoke-Expression\b|\biex\b",
    r"\bDownloadString\b|\bDownloadFile\b",
    # Privilege escalation
    r"\bsudo\s+(?!npm|pip|apt-get\s+install)\b",
    r"\brunas\b",
    r"\bpkexec\b",
    r"\bchmod\s+.*\+s\b",
    # Data exfiltration
    r"\bnc\s+(-e| -c)\b",
    r"\bpython\s+-m\s+http\.server\b",
    # Network attacks
    r"\bnmap\b",
    r"\bhydra\b",
    r"\bsqlmap\b",
    # Crypto miners
    r"\bxmrig\b|\bminerd\b|\bstratum\+tcp://\b",
    # Ransomware
    r"\bvssadmin\s+delete\s+shadows\b",
]

_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_KEYWORDS]


def is_destructive_action(action_text: str) -> tuple[bool, str]:
    """
    Returns (is_destructive, matched_reason).
    Uses keyword/regex blocklist only — no LLM call here.
    """
    for pattern in _COMPILED_DESTRUCTIVE:
        m = pattern.search(action_text)
        if m:
            return True, f"destructive_keyword:{m.group(0)}"
    return False, ""


def validate_coordinates(x: int, y: int, screen_w: int = 1920, screen_h: int = 1080) -> tuple[bool, str]:
    """Returns (valid, reason). Rejects clicks near screen edges or outside bounds."""
    try:
        xv = int(x)
        yv = int(y)
    except (TypeError, ValueError):
        return False, f"coord_invalid_type:({type(x).__name__},{type(y).__name__})"
    if xv < SCREEN_MIN_X or yv < SCREEN_MIN_Y:
        return False, f"coord_too_low:({xv},{yv})"
    if xv >= screen_w - SCREEN_MIN_X or yv >= screen_h - SCREEN_MIN_Y:
        return False, f"coord_out_of_bounds:({xv},{yv}) screen=({screen_w},{screen_h})"
    return True, ""


def detect_loop(history: list[tuple[str, str]], window: int = 3) -> bool:
    """
    Returns True if the last `window` (action, screenshot_hash) pairs are identical —
    indicating the agent is stuck in a no-progress loop.
    """
    if len(history) < window:
        return False
    last = history[-window:]
    return len(set(last)) == 1


def screenshot_hash(pixel_data: bytes) -> str:
    """Quick perceptual hash (MD5) of raw screenshot bytes for loop detection."""
    return hashlib.md5(pixel_data).hexdigest()


def pixel_diff_score(before: bytes, after: bytes) -> float:
    """
    Rough pixel-change ratio between two raw screenshot byte strings.
    Returns 0.0 (identical) to 1.0 (completely different).
    """
    if len(before) != len(after) or len(before) == 0:
        return 1.0
    diff = sum(1 for a, b in zip(before, after) if a != b)
    return diff / len(before)


# =============================================================
#  SECRET / PII SCANNER (Unified Agent)
# =============================================================

_SECRET_PATTERNS_UA = [
    (r"\b(sk-[a-zA-Z0-9]{20,})\b", "openai_api_key"),
    (r"\b(AIza[0-9A-Za-z_-]{35,})\b", "google_api_key"),
    (r"\b(pk_[a-zA-Z0-9]{20,})\b", "stripe_key"),
    (r"\b(sk_(live|test)_[a-zA-Z0-9]{20,})\b", "stripe_secret"),
    (r"\b(api[_-]?key\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{16,}[\"']?)\b", "generic_api_key"),
    (r"\b(password\s*[:=]\s*[\"']?[^\s\"']{8,}[\"']?)\b", "password"),
    (r"\b(token\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{16,}[\"']?)\b", "token"),
    (r"\b(AKIA[0-9A-Z]{16})\b", "aws_access_key"),
    (r"\b(eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*)\b", "jwt_token"),
    (r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "private_key"),
    (r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b", "ssn"),
]

_COMPILED_SECRETS_UA = [(re.compile(p, re.IGNORECASE), label) for p, label in _SECRET_PATTERNS_UA]


def scan_secrets(text: str) -> List[Tuple[str, str]]:
    """Scan text for secrets/PII. Returns list of (match, label)."""
    findings: List[Tuple[str, str]] = []
    for pattern, label in _COMPILED_SECRETS_UA:
        for match in pattern.finditer(text):
            findings.append((match.group(0), label))
    return findings


# =============================================================
#  ACTION SAFETY CLASSIFICATION
# =============================================================

SAFE = "safe"
DANGEROUS = "dangerous"
BLOCKED = "blocked"

# Dangerous action patterns — require overlay confirmation
_DANGEROUS_PATTERNS = [
    # Clicking risky UI elements
    r"\bclick\b.*\b(delete|remove|send|purchase|buy|pay|checkout|confirm|uninstall|erase|wipe)\b",
    r"\bclick\b.*\b(submit\b.*\bform|submit\b.*\bbutton)\b",
    r"\bdouble_click\b.*\b(delete|remove|send|purchase|buy|pay|checkout)\b",
    r"\bright_click\b.*\b(delete|remove|send|purchase|buy|pay|checkout)\b",
    # Typing sensitive data
    r"\btype\b.*\b(password|passcode|pin\b|cvv|credit card|ssn\b|social security)\b",
    r"\btype\b.*\b\d{3}-\d{2}-\d{4}\b",
    # File system operations
    r"\b(write_file|delete_file|move_file|rename_file)\b",
    r"\brun_command\b",
    # Explicit destructive keywords that aren't in the total blocklist (e.g. "delete" without "file")
    r"\bdelete\b.*\b(all|everything|every)\b",
    r"\bclear\b.*\b(history|cache|data|all)\b",
    r"\breset\b.*\b(account|password|settings|factory)\b",
    r"\bdisable\b.*\b(firewall|antivirus|defender|security)\b",
    r"\bstop\b.*\b(service|process|daemon)\b",
    r"\bend\b.*\b(task|process)\b",
]

_COMPILED_DANGEROUS = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_PATTERNS]


def classify_action(action_text: str) -> tuple[str, str]:
    """
    Classify an agent action as SAFE, DANGEROUS, or BLOCKED.
    Returns (safety, reason).
    """
    if not action_text:
        return SAFE, ""

    text = str(action_text).lower()

    # First check hard blocklist (destructive keywords)
    is_dest, dest_reason = is_destructive_action(action_text)
    if is_dest:
        return BLOCKED, dest_reason

    # Check dangerous patterns
    for pattern in _COMPILED_DANGEROUS:
        m = pattern.search(action_text)
        if m:
            return DANGEROUS, f"dangerous_pattern:{m.group(0)}"

    return SAFE, ""


# =============================================================
#  DOMAIN / URL BLOCKLIST
# =============================================================

BLOCKED_DOMAINS = {
    # Known phishing / malware examples (expand as needed)
    "phishing-site.example",
    "malware-dl.example",
    "evil.example",
    # Common suspicious TLDs used in phishing (heuristic fallback in is_blocked_domain)
}

_SUSPICIOUS_TLD_PATTERNS = [
    r"\.(tk|ml|ga|cf|gq)$",  # Free TLDs commonly abused
]

_COMPILED_SUSPICIOUS_TLDS = [re.compile(p, re.IGNORECASE) for p in _SUSPICIOUS_TLD_PATTERNS]


def is_blocked_domain(url: str) -> tuple[bool, str]:
    """
    Check if a URL navigates to a blocked or suspicious domain.
    Returns (blocked, reason).
    """
    if not url:
        return False, ""

    # Extract domain
    m = re.search(r"(?:https?://)?(?:www\.)?([^/\s:]+)", str(url).lower())
    if not m:
        return False, ""

    domain = m.group(1).strip()

    # Exact match against blocklist
    if domain in BLOCKED_DOMAINS:
        return True, f"blocked_domain:{domain}"

    # Check suspicious TLDs
    for pattern in _COMPILED_SUSPICIOUS_TLDS:
        if pattern.search(domain):
            return True, f"suspicious_tld:{domain}"

    # IP-address literal navigation (often malicious)
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain):
        return True, f"ip_literal_blocked:{domain}"

    return False, ""


# =============================================================
#  BLOCKED APPLICATIONS
# =============================================================

BLOCKED_APPS = {
    "settings",
    "system settings",
    "control panel",
    "registry editor",
    "regedit",
    "task manager",
    "terminal",
    "windows terminal",
    "cmd",
    "command prompt",
    "powershell",
    "password manager",
    "1password",
    "bitwarden",
    "lastpass",
    "keepass",
    "sudo",
    "su",
    "pkexec",
}


def is_blocked_app(app_name: str) -> tuple[bool, str]:
    """
    Check if the agent is trying to open a blocked system app.
    Returns (blocked, reason).
    """
    if not app_name:
        return False, ""

    normalized = str(app_name).lower().strip()
    if normalized in BLOCKED_APPS:
        return True, f"blocked_app:{normalized}"

    return False, ""


# =============================================================
#  AUDIT LOGGER
# =============================================================

class AgentAuditLogger:
    """Thread-safe append-only audit log for agent guardrail decisions."""

    _LOG_PATH: Path = Path("memory/agent_log.jsonl")
    _lock = threading.Lock()

    @classmethod
    def _ensure_dir(cls) -> None:
        cls._LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def log_decision(
        cls,
        *,
        intent: str,
        action: str,
        safety: str,
        reason: str,
        user_id: str = "",
    ) -> None:
        """Append a single guardrail decision to the audit log."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "intent": intent,
            "action": action,
            "safety": safety,
            "reason": reason,
            "user_id": user_id,
        }

        with cls._lock:
            cls._ensure_dir()
            with open(cls._LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @classmethod
    def read_recent(cls, limit: int = 100) -> list[dict]:
        """Read the most recent N audit entries."""
        if not cls._LOG_PATH.exists():
            return []

        with cls._lock:
            lines = cls._LOG_PATH.read_text(encoding="utf-8").strip().split("\n")

        entries = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


# =============================================================
#  WORKFLOW GUARDRAILS
# =============================================================

# Filesystem path patterns that suggest file write attempts
_FILE_PATH_PATTERNS = [
    r"[A-Z]:\\[^\s]*",  # Windows absolute paths
    r"/etc/[^\s]*",
    r"/usr/[^\s]*",
    r"/home/[^\s]*",
    r"/var/[^\s]*",
    r"/tmp/[^\s]*",
    r"~/[^\s]*",
    r"\.ssh/[^\s]*",
    r"\.git/[^\s]*",
    r"\.env[^\s]*",
    r"\.bashrc",
    r"\.zshrc",
    r"\.profile",
]

_COMPILED_FILE_PATHS = [re.compile(p) for p in _FILE_PATH_PATTERNS]

# Allowed work domains for navigate_to
_ALLOWED_WORK_DOMAINS = {
    "jira", "atlassian", "slack", "notion", "github", "gitlab", "linear",
    "figma", "gmail", "google", "outlook", "office365", "teams",
    "linkedin", "twitter", "x.com", "reddit", "stackoverflow",
    "docs.google", "sheets.google", "drive.google",
    "amazon", "aws", "azure", "cloud.google",
    "zoom", "meet.google", "webex",
}

# Max screenshots per workflow
MAX_SCREENSHOTS_PER_WORKFLOW = 50

# Max workflow duration in seconds
MAX_WORKFLOW_DURATION_SECONDS = 600  # 10 minutes


class WorkflowGuardrails:
    """Guardrails specific to Workflow Mode: no file writes, URL filtering, budget limits."""

    def __init__(self) -> None:
        self.screenshot_count = 0
        self.start_time = time.time()

    def check_type_input(self, text: str) -> tuple[bool, str]:
        """Check if typed text contains filesystem paths."""
        if not text:
            return False, ""
        for pattern in _COMPILED_FILE_PATHS:
            m = pattern.search(text)
            if m:
                return True, f"file_path_detected:{m.group(0)}"
        return False, ""

    def check_navigate_url(self, url: str) -> tuple[bool, str]:
        """Check if a URL is blocked or suspicious."""
        if not url:
            return False, ""
        # Use existing domain checker
        blocked, reason = is_blocked_domain(url)
        if blocked:
            return True, reason
        # Allowlist check — if domain is not in allowlist, warn but don't block
        # (we're permissive for workflows since users may need various sites)
        return False, ""

    def check_screenshot_budget(self) -> tuple[bool, str]:
        """Check if screenshot budget is exhausted."""
        if self.screenshot_count >= MAX_SCREENSHOTS_PER_WORKFLOW:
            return True, f"screenshot_budget_exceeded:{self.screenshot_count}/{MAX_SCREENSHOTS_PER_WORKFLOW}"
        return False, ""

    def check_time_ceiling(self) -> tuple[bool, str]:
        """Check if workflow has exceeded max duration."""
        elapsed = time.time() - self.start_time
        if elapsed >= MAX_WORKFLOW_DURATION_SECONDS:
            return True, f"time_ceiling_exceeded:{elapsed:.0f}s/{MAX_WORKFLOW_DURATION_SECONDS}s"
        return False, ""

    def redact_credentials(self, text: str) -> str:
        """Redact potential credentials from log text."""
        if not text:
            return text
        findings = scan_secrets(text)
        redacted = text
        for match, label in findings:
            redacted = redacted.replace(match, f"[{label}_REDACTED]")
        return redacted

    def record_screenshot(self) -> None:
        """Increment screenshot counter."""
        self.screenshot_count += 1
