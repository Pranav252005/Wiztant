"""
core/agent_v2/guardrails.py — Comprehensive safety guardrails for the IDE Controller Agent.

Expands from 8 patterns to 60+ covering LOLBAS vectors, data exfiltration,
privilege escalation, network attacks, crypto miners, ransomware indicators,
plus path sandboxing, command allowlisting, PII scanning, and audit logging.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# =============================================================
#  COST & FILE LIMITS
# =============================================================

COST_CEILING_USD = 10.0
MAX_FILES_PER_PHASE = 15
MAX_RETRIES_PER_SUBPHASE = 5
HARD_STEP_CEILING = 50  # Non-configurable absolute max

# =============================================================
#  DESTRUCTIVE COMMAND PATTERNS (60+)
# =============================================================

# LOLBAS (Living Off The Land Binaries and Scripts)
_LOLBAS_PATTERNS = [
    r"\bpowershell\s+(-enc| -encodedcommand| -ep bypass| -executionpolicy bypass)",
    r"\bcertutil\s+(-urlcache| -decode| -encode)",
    r"\bbitsadmin\s+(\/transfer|\/download|\/upload)",
    r"\bregsvr32\s+(\/s|\/u|\.\\|https?://)",
    r"\bmshta\s+(https?://|javascript:|vbscript:)",
    r"\bcscript\s+.*\.(js|vbs|wsf)",
    r"\bwscript\s+.*\.(js|vbs|wsf)",
    r"\brundll32\s+.*\.(dll|#,)",
    r"\bcmd\.exe\s+\/c\s+",
    r"\bInvoke-Expression\b|\biex\b",
    r"\bInvoke-WebRequest\b|\biwr\b|\bwget\b.*\-UseBasicParsing",
    r"\bStart-Process\b|\bsaps\b",
    r"\bDownloadString\b|\bDownloadFile\b",
    r"\bNet\.WebClient\b",
    r"\bSystem\.Net\.Sockets",
    r"\bReflection\.Assembly\b.*\.Load",
    r"\bAdd-Type\b.*\-TypeDefinition",
    r"\bFromBase64String\b",
    r"\bGzipStream\b.*\bMemoryStream\b",
]

# Data exfiltration
_EXFIL_PATTERNS = [
    r"\bcurl\s+.*\s+-F\s+",
    r"\bwget\s+.*\s+--post-file",
    r"\bscp\s+.*\s+.*@.*:",
    r"\brsync\s+.*\s+.*@.*:",
    r"\bnc\s+(-e| -c)\s+",
    r"\bnetcat\s+(-e| -c)\s+",
    r"\bpython\s+-m\s+http\.server",
    r"\bpython3?\s+.*\bhttp\.server",
    r"\bphp\s+-S\s+",
    r"\bpython\s+.*\bBaseHTTPServer",
    r"\bpython\s+.*\bSimpleHTTPServer",
]

# Privilege escalation
_PRIVESC_PATTERNS = [
    r"\bsudo\s+(?!npm|pip|apt-get\s+install\s+)(.*)",
    r"\brunas\s+",
    r"\bpkexec\s+",
    r"\bsu\s+-\s+",
    r"\bchmod\s+.*\+s",
    r"\bsetuid\b",
    r"\bsetgid\b",
    r"\bchown\s+root",
    r"\bchmod\s+777\s+",
    r"\bchmod\s+4755\s+",
]

# Network attacks
_NETWORK_ATTACK_PATTERNS = [
    r"\bnmap\s+",
    r"\bmasscan\s+",
    r"\bhydra\s+",
    r"\bsqlmap\s+",
    r"\bmetasploit\b|\bmsfconsole\b",
    r"\baircrack-ng\b",
    r"\bettercap\b",
    r"\bwireshark\s+.*\-k",
    r"\btcpdump\s+.*\-w",
]

# Crypto miners
_MINER_PATTERNS = [
    r"\bxmrig\b",
    r"\bminerd\b",
    r"\bstratum\+tcp://",
    r"\bstratum\+ssl://",
    r"\bcrypto miner\b",
    r"\bmining pool\b",
]

# Ransomware indicators
_RANSOMWARE_PATTERNS = [
    r"\bvssadmin\s+delete\s+shadows",
    r"\bwbadmin\s+delete\s+catalog",
    r"\bbcdedit\s+\/set\s+\{default\}\s+recoveryenabled\s+No",
    r"\bwevtutil\s+clear-log",
    r"\bfsutil\s+usn\s+deletejournal",
]

# Classic destructive
_CLASSIC_DESTRUCTIVE = [
    r"\brm\s+-rf\b",
    r"\brm\s+-rf\s+/\b",
    r"\brm\s+-rf\s+~\/\b",
    r"\bformat\s+(?:C:|D:|E:|/dev/sd|/dev/hd|/dev/nvme)",
    r"\bdd\s+if=",
    r"\bfdisk\s+",
    r"\bmkfs\.",
    r"\bdel\s+\/f\s+\/s\s+\/q\b",
    r"\brd\s+\/s\s+\/q\b",
    r"\breg\s+delete\b",
    r"\bsc\s+delete\b",
    r"\bgit\s+push\b",
    r"\bnpm\s+publish\b",
    r"\bvercel\s+--prod\b",
    r"\bdrop\s+table\b",
    r"\bdrop\s+database\b",
    r"\btruncate\s+table\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\binit\s+0\b",
    r"\bkillall\s+",
    r"\bpkill\s+",
    r"\btaskkill\s+\/f\s+\/im\b",
]

_ALL_DESTRUCTIVE_PATTERNS = (
    _LOLBAS_PATTERNS
    + _EXFIL_PATTERNS
    + _PRIVESC_PATTERNS
    + _NETWORK_ATTACK_PATTERNS
    + _MINER_PATTERNS
    + _RANSOMWARE_PATTERNS
    + _CLASSIC_DESTRUCTIVE
)

_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in _ALL_DESTRUCTIVE_PATTERNS]

# =============================================================
#  COMMAND ALLOWLIST / DENYLIST
# =============================================================

_COMMAND_ALLOWLIST = {
    # Package managers
    "npx", "npm", "node", "pnpm", "yarn", "bun",
    "pip", "pip3", "python", "python3", "poetry", "uv",
    # Version control
    "git",
    # Type checking / linting / formatting
    "tsc", "eslint", "prettier", "biome", "oxlint", "stylelint",
    # Build tools
    "vite", "next", "react-scripts", "astro", "nuxt", "remix",
    "webpack", "rollup", "esbuild", "parcel", "turbo", "gulp",
    # Testing
    "jest", "vitest", "cypress", "playwright", "mocha", "karma",
    # Database
    "prisma", "drizzle-kit", "supabase", "migrate", "seed",
    # DevOps / Container
    "docker", "docker-compose", "kubectl", "terraform", "pulumi",
    # Cloud
    "vercel", "netlify", "fly", "railway", "render",
    # Utilities
    "curl", "mkdir", "cp", "mv", "ls", "cat", "echo", "touch",
    "grep", "find", "sed", "awk", "sort", "uniq", "wc", "head", "tail",
    "less", "more", "which", "whereis", "file", "diff", "patch",
    "tar", "zip", "unzip", "gzip", "gunzip",
    # System (read-only / safe)
    "df", "du", "free", "uptime", "whoami", "pwd", "date", "time",
    # Package installation (Linux)
    "apt-get", "apt", "snap", "brew", "choco", "winget",
}

_COMMAND_DENYLIST = {
    "rm", "rmdir", "del", "erase", "format", "dd", "fdisk", "mkfs",
    "shutdown", "reboot", "poweroff", "halt", "init", "systemctl",
    "kill", "killall", "pkill", "taskkill", "xkill",
    "chmod", "chown", "chgrp", "setfacl", "sudo", "su", "runas", "pkexec",
    "wget", "curl"  # curl is in allowlist but wget is denylisted by default (can exfil)
}

# =============================================================
#  PATH SANDBOX
# =============================================================

# Paths that are ALWAYS blocked (read and write)
_BLOCKED_PATHS = [
    r"^/etc/",
    r"^/sys/",
    r"^/proc/",
    r"^/dev/",
    r"^/boot/",
    r"^/var/log/",
    r"^/var/spool/",
    r"^/usr/sbin/",
    r"^/usr/bin/\.*$",  # specific binaries handled by command allowlist
    r"^C:\\\\Windows\\\\",
    r"^C:\\\\Program\sFiles",
    r"^C:\\\\ProgramData\\\\",
    r"^C:\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Microsoft\\\\Windows",
    r"^/Users/[^/]+/Library/Keychains",
    r"^~/.ssh/",
    r"^~/.aws/",
    r"^~/.env",
    r"^~/.bash_history",
    r"^~/.zsh_history",
    r"^~/.npmrc",
    r"^~/.pypirc",
    r"^~/.netrc",
    r"^~/.docker/config.json",
    r"^~/.kube/",
    r"^~/.gnupg/",
    r"^~/.password-store/",
    r"^~/.local/share/keyrings/",
]

# Paths allowed for READ ONLY
_READONLY_PATHS = [
    r"^~/.config/",
    r"^~/.local/",
    r"^%APPDATA%/",
    r"^%LOCALAPPDATA%/",
    r"^/usr/share/",
    r"^/opt/",
]

_COMPILED_BLOCKED_PATHS = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATHS]
_COMPILED_READONLY_PATHS = [re.compile(p, re.IGNORECASE) for p in _READONLY_PATHS]

# =============================================================
#  PII / SECRET SCANNER
# =============================================================

_SECRET_PATTERNS = [
    # API Keys
    (r"\b(sk-[a-zA-Z0-9]{20,})\b", "openai_api_key"),
    (r"\b(AIza[0-9A-Za-z_-]{35,})\b", "google_api_key"),
    (r"\b(sg\.[a-zA-Z0-9_-]{20,})\b", "sendgrid_key"),
    (r"\b(re_[a-zA-Z0-9]{20,})\b", "resend_key"),
    (r"\b(pk_[a-zA-Z0-9]{20,})\b", "stripe_publishable_key"),
    (r"\b(sk_(live|test)_[a-zA-Z0-9]{20,})\b", "stripe_secret_key"),
    # Generic secrets
    (r"\b(api[_-]?key\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{16,}[\"']?)\b", "generic_api_key"),
    (r"\b(secret\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{16,}[\"']?)\b", "generic_secret"),
    (r"\b(password\s*[:=]\s*[\"']?[^\s\"']{8,}[\"']?)\b", "password"),
    (r"\b(token\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{16,}[\"']?)\b", "token"),
    # AWS
    (r"\b(AKIA[0-9A-Z]{16})\b", "aws_access_key"),
    (r"\b([0-9a-zA-Z/+]{40})\b", "aws_secret_key"),  # loose, needs context
    # JWT
    (r"\b(eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*)\b", "jwt_token"),
    # Private keys
    (r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "private_key"),
    # Credit cards (basic Luhn-checkable patterns)
    (r"\b4[0-9]{12}(?:[0-9]{3})?\b", "visa_card"),
    (r"\b5[1-5][0-9]{14}\b", "mastercard"),
    # SSN
    (r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b", "ssn"),
    # Email
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
]

_COMPILED_SECRETS = [(re.compile(p, re.IGNORECASE), label) for p, label in _SECRET_PATTERNS]


# =============================================================
#  AUDIT LOGGER
# =============================================================

class AuditLogger:
    """Append-only audit log for agent actions."""

    _LOG_PATH: Path = Path(__file__).resolve().parent.parent.parent / "data" / "agent_audit.jsonl"

    @classmethod
    def _ensure_dir(cls) -> None:
        cls._LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def log(
        cls,
        *,
        user_id: str,
        intent: str,
        action: str,
        tool: Optional[str] = None,
        args_hash: Optional[str] = None,
        result: str = "pending",
        credits_used: int = 0,
        guardrail_triggered: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a single audit entry. Cannot be called by agent tools."""
        from datetime import datetime, timezone
        import json
        import hashlib

        cls._ensure_dir()

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "intent": intent,
            "action": action,
            "tool": tool,
            "args_hash": args_hash or "",
            "result": result,
            "credits_used": credits_used,
            "guardrail_triggered": guardrail_triggered,
            "metadata": metadata or {},
        }

        # Tamper-evident: hash the JSON string
        entry_json = json.dumps(entry, sort_keys=True)
        entry["_integrity"] = hashlib.sha256(entry_json.encode()).hexdigest()[:16]

        with open(cls._LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @classmethod
    def read_recent(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """Read the most recent N audit entries."""
        import json
        if not cls._LOG_PATH.exists():
            return []
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
#  GUARDRAIL CLASS
# =============================================================

class Guardrails:
    """Per-project comprehensive guardrail state."""

    def __init__(self, project_path: str, user_id: Optional[str] = None) -> None:
        self.project_root = Path(project_path).resolve()
        self.user_id = user_id or "anonymous"
        self.cost_accumulated: float = 0.0
        self.files_created_this_phase: int = 0
        self.max_files_per_phase: int = MAX_FILES_PER_PHASE
        self.step_count: int = 0
        self.max_steps: int = HARD_STEP_CEILING

    # -- Cost & Limits --

    def can_spend(self, amount: float) -> bool:
        return (self.cost_accumulated + amount) <= COST_CEILING_USD

    def record_spend(self, amount: float) -> None:
        self.cost_accumulated += amount

    def allow_file_creation(self) -> bool:
        return self.files_created_this_phase < self.max_files_per_phase

    def record_file_created(self) -> None:
        self.files_created_this_phase += 1

    def reset_phase_counter(self) -> None:
        self.files_created_this_phase = 0

    def can_step(self) -> bool:
        self.step_count += 1
        return self.step_count <= self.max_steps

    def reset_step_counter(self) -> None:
        self.step_count = 0

    # -- Command Validation --

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Return (ok, reason). Checks destructive patterns, then allowlist."""
        if not command or not command.strip():
            return False, "empty_command"

        # Check destructive patterns first
        for pattern in _COMPILED_DESTRUCTIVE:
            if pattern.search(command):
                reason = f"destructive_pattern_blocked:{pattern.pattern[:50]}"
                self._audit("command_rejected", command, reason)
                return False, reason

        # Strip env vars for command extraction
        cleaned = re.sub(r"^[A-Z_]+=\S+\s+", "", command).strip()
        first = cleaned.split()[0] if cleaned else ""

        # Check explicit denylist
        if first in _COMMAND_DENYLIST:
            reason = f"command_in_denylist:{first}"
            self._audit("command_rejected", command, reason)
            return False, reason

        # Check allowlist
        if first and first not in _COMMAND_ALLOWLIST:
            reason = f"command_not_in_allowlist:{first}"
            self._audit("command_rejected", command, reason)
            return False, reason

        self._audit("command_allowed", command)
        return True, None

    # -- Path Sandbox --

    def validate_path(self, target: str, mode: str = "read") -> Tuple[bool, Optional[str]]:
        """Validate that target path is within allowed boundaries."""
        try:
            target_path = Path(target).expanduser().resolve()
        except (OSError, ValueError):
            return False, f"invalid_path:{target}"

        path_str = str(target_path)

        # Check blocked paths
        for pattern in _COMPILED_BLOCKED_PATHS:
            if pattern.search(path_str):
                reason = f"path_blocked:{target}"
                self._audit("path_rejected", target, reason)
                return False, reason

        # Check readonly restriction
        if mode in ("write", "create", "delete"):
            for pattern in _COMPILED_READONLY_PATHS:
                if pattern.search(path_str):
                    reason = f"path_readonly_write_attempt:{target}"
                    self._audit("path_rejected", target, reason)
                    return False, reason

        # Must be within project root for write operations
        if mode in ("write", "create", "delete"):
            try:
                target_path.relative_to(self.project_root)
            except ValueError:
                reason = f"path_outside_project:{target}"
                self._audit("path_rejected", target, reason)
                return False, reason

        self._audit("path_allowed", target)
        return True, None

    # -- PII / Secret Scanner --

    def scan_for_secrets(self, text: str) -> List[Tuple[str, str]]:
        """Scan text for secrets/PII. Returns list of (match, label)."""
        findings: List[Tuple[str, str]] = []
        for pattern, label in _COMPILED_SECRETS:
            for match in pattern.finditer(text):
                findings.append((match.group(0), label))
        return findings

    def validate_content(self, text: str, source: str = "unknown") -> Tuple[bool, Optional[str], List[Tuple[str, str]]]:
        """Validate text content for secrets. Returns (ok, reason, findings)."""
        findings = self.scan_for_secrets(text)
        if findings:
            labels = ", ".join(set(label for _, label in findings))
            reason = f"secrets_detected:{labels}"
            self._audit("content_rejected", source, reason, metadata={"findings": findings})
            return False, reason, findings
        return True, None, findings

    # -- Audit Helper --

    def _audit(self, action: str, target: str, reason: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        AuditLogger.log(
            user_id=self.user_id,
            intent="guardrail",
            action=action,
            args_hash=target,
            result="blocked" if reason else "allowed",
            guardrail_triggered=reason,
            metadata=metadata,
        )


# =============================================================
#  STANDALONE FUNCTIONS (for unified agent compatibility)
# =============================================================

def is_destructive_command(command: str) -> Tuple[bool, Optional[str]]:
    """Standalone check for destructive commands."""
    for pattern in _COMPILED_DESTRUCTIVE:
        if pattern.search(command):
            return True, f"destructive_pattern:{pattern.pattern[:50]}"
    return False, None


def sandbox_path(target: Path, project_root: Path) -> bool:
    """Ensure target is within project_root."""
    try:
        target.resolve().relative_to(project_root.resolve())
        return True
    except ValueError:
        return False


def scan_secrets(text: str) -> List[Tuple[str, str]]:
    """Standalone secret scanner."""
    findings: List[Tuple[str, str]] = []
    for pattern, label in _COMPILED_SECRETS:
        for match in pattern.finditer(text):
            findings.append((match.group(0), label))
    return findings
