"""
tests/test_guardrails_integration.py — Tests for the enhanced guardrail system.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tempfile
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.guardrails import (
    classify_action,
    is_blocked_domain,
    is_blocked_app,
    AgentAuditLogger,
    SAFE,
    DANGEROUS,
    BLOCKED,
)


class TestClassifyAction:
    def test_safe_navigate(self):
        safety, reason = classify_action("navigate to https://google.com")
        assert safety == SAFE
        assert reason == ""

    def test_safe_scroll(self):
        safety, reason = classify_action("scroll down")
        assert safety == SAFE
        assert reason == ""

    def test_safe_open_app(self):
        safety, reason = classify_action("open chrome")
        assert safety == SAFE
        assert reason == ""

    def test_safe_type_search(self):
        safety, reason = classify_action("type hello world in search bar")
        assert safety == SAFE
        assert reason == ""

    def test_dangerous_click_delete(self):
        safety, reason = classify_action("click the Delete button")
        assert safety == DANGEROUS
        assert "dangerous_pattern" in reason

    def test_dangerous_type_password(self):
        safety, reason = classify_action("type my password into the field")
        assert safety == DANGEROUS
        assert "dangerous_pattern" in reason

    def test_dangerous_send_email(self):
        safety, reason = classify_action("click send")
        assert safety == DANGEROUS
        assert "dangerous_pattern" in reason

    def test_dangerous_purchase(self):
        safety, reason = classify_action("click purchase")
        assert safety == DANGEROUS
        assert "dangerous_pattern" in reason

    def test_blocked_delete_files(self):
        safety, reason = classify_action("delete all files")
        assert safety == BLOCKED
        assert "destructive_keyword" in reason

    def test_blocked_format_drive(self):
        safety, reason = classify_action("format the drive")
        assert safety == BLOCKED
        assert "destructive_keyword" in reason

    def test_blocked_rm_rf(self):
        safety, reason = classify_action("rm -rf /")
        assert safety == BLOCKED
        assert "destructive_keyword" in reason

    def test_blocked_shutdown(self):
        safety, reason = classify_action("shutdown the computer")
        assert safety == BLOCKED
        assert "destructive_keyword" in reason

    def test_blocked_powershell_encoded(self):
        safety, reason = classify_action("powershell -enc abc123")
        assert safety == BLOCKED
        assert "destructive_keyword" in reason

    def test_empty_action(self):
        safety, reason = classify_action("")
        assert safety == SAFE
        assert reason == ""


class TestIsBlockedDomain:
    def test_blocked_exact_domain(self):
        blocked, reason = is_blocked_domain("https://evil.example")
        assert blocked is True
        assert "blocked_domain" in reason

    def test_blocked_ip_literal(self):
        blocked, reason = is_blocked_domain("http://192.168.1.1")
        assert blocked is True
        assert "ip_literal_blocked" in reason

    def test_safe_google(self):
        blocked, reason = is_blocked_domain("https://www.google.com")
        assert blocked is False
        assert reason == ""

    def test_safe_github(self):
        blocked, reason = is_blocked_domain("github.com")
        assert blocked is False
        assert reason == ""

    def test_empty_url(self):
        blocked, reason = is_blocked_domain("")
        assert blocked is False
        assert reason == ""


class TestIsBlockedApp:
    def test_blocked_settings(self):
        blocked, reason = is_blocked_app("settings")
        assert blocked is True
        assert "blocked_app" in reason

    def test_blocked_terminal(self):
        blocked, reason = is_blocked_app("terminal")
        assert blocked is True
        assert "blocked_app" in reason

    def test_blocked_regedit(self):
        blocked, reason = is_blocked_app("regedit")
        assert blocked is True
        assert "blocked_app" in reason

    def test_safe_chrome(self):
        blocked, reason = is_blocked_app("chrome")
        assert blocked is False
        assert reason == ""

    def test_safe_vscode(self):
        blocked, reason = is_blocked_app("vscode")
        assert blocked is False
        assert reason == ""

    def test_empty_app(self):
        blocked, reason = is_blocked_app("")
        assert blocked is False
        assert reason == ""


class TestAgentAuditLogger:
    def test_log_append_and_read(self, tmp_path: Path):
        # Override log path for test isolation
        original_path = AgentAuditLogger._LOG_PATH
        test_path = tmp_path / "agent_log.jsonl"
        AgentAuditLogger._LOG_PATH = test_path

        try:
            AgentAuditLogger.log_decision(
                intent="test intent",
                action="test_action",
                safety="safe",
                reason="",
                user_id="user_123",
            )
            AgentAuditLogger.log_decision(
                intent="test intent 2",
                action="test_action_2",
                safety="blocked",
                reason="destructive",
                user_id="user_123",
            )

            entries = AgentAuditLogger.read_recent(limit=10)
            assert len(entries) == 2
            assert entries[0]["intent"] == "test intent"
            assert entries[0]["safety"] == "safe"
            assert entries[1]["intent"] == "test intent 2"
            assert entries[1]["safety"] == "blocked"
            assert entries[1]["reason"] == "destructive"

            # Verify valid JSONL
            lines = test_path.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 2
            for line in lines:
                parsed = json.loads(line)
                assert "ts" in parsed
                assert "intent" in parsed
        finally:
            AgentAuditLogger._LOG_PATH = original_path

    def test_thread_safety(self, tmp_path: Path):
        original_path = AgentAuditLogger._LOG_PATH
        test_path = tmp_path / "agent_log.jsonl"
        AgentAuditLogger._LOG_PATH = test_path

        try:
            errors = []

            def worker(i: int):
                try:
                    AgentAuditLogger.log_decision(
                        intent=f"thread_{i}",
                        action="thread_action",
                        safety="safe",
                        reason="",
                    )
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors, f"Thread errors: {errors}"

            entries = AgentAuditLogger.read_recent(limit=50)
            intents = {e["intent"] for e in entries}
            assert len(intents) == 20
        finally:
            AgentAuditLogger._LOG_PATH = original_path
