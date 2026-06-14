"""
Tests for RePrompt (WizPrompt) guardrails — PII/secrets must be blocked
or redacted before sending to the LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.wizprompt import validate_prompt


def test_reprompt_rejects_api_key_in_input():
    """Clipboard containing an OpenAI API key must be rejected before optimization."""
    prompt_with_secret = "Optimize this: my key is sk-abcdefghijklmnopqrstuvwxyz123456"

    # Current validate_prompt does NOT scan for secrets — this test documents the gap
    error = validate_prompt(prompt_with_secret)
    assert error is not None, (
        "validate_prompt allowed a prompt containing an API key to pass — secret leakage risk"
    )


def test_reprompt_rejects_password_in_input():
    """Clipboard containing a password must be rejected."""
    prompt_with_password = "password: SuperSecret123!\nPlease optimize the above config."

    error = validate_prompt(prompt_with_password)
    assert error is not None, (
        "validate_prompt allowed a prompt containing a password to pass — PII leakage risk"
    )


def test_reprompt_rejects_jwt_token():
    """Clipboard containing a JWT must be rejected."""
    prompt_with_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c\n"
        "Optimize this auth token."
    )

    error = validate_prompt(prompt_with_jwt)
    assert error is not None, (
        "validate_prompt allowed a prompt containing a JWT to pass — auth token leakage risk"
    )


def test_reprompt_rejects_too_long_input():
    """Input longer than MAX_REPROMPT_INPUT chars must be rejected."""
    long_prompt = "x" * 15000

    error = validate_prompt(long_prompt)
    assert error is not None, (
        f"validate_prompt allowed {len(long_prompt)} char input — exceeds MAX_REPROMPT_INPUT limit"
    )


def test_reprompt_allows_clean_input():
    """Normal, safe prompts must still pass validation."""
    clean = (
        "Write a Python function that sorts a list of dictionaries by a key. "
        "Include type hints and docstring."
    )
    assert validate_prompt(clean) is None, (
        "validate_prompt wrongly rejected a clean, safe prompt"
    )
