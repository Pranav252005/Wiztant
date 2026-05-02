"""PII Scanner for Tune Hub Marketplace.

Detects and flags personally identifiable information in tune payloads
before they are shared publicly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PIIScanResult:
    """Result of a PII scan."""

    clean: bool
    issues: List[Dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 = clean, 1.0 = high risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean": self.clean,
            "issues": self.issues,
            "risk_score": self.risk_score,
        }


class PIIScanner:
    """Scans tune payloads for PII before marketplace publication."""

    # Patterns for common PII
    PATTERNS = {
        "email": re.compile(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            re.IGNORECASE,
        ),
        "phone": re.compile(
            r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        ),
        "url": re.compile(
            r"https?://[^\s\"'<>]+",
            re.IGNORECASE,
        ),
        "ip_address": re.compile(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        ),
        "ssn": re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b",
        ),
        "credit_card": re.compile(
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        ),
        "api_key": re.compile(
            r"(?:api[_-]?key|apikey|token)\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{16,})[\"']?",
            re.IGNORECASE,
        ),
    }

    # High-risk keywords
    HIGH_RISK_KEYWORDS = [
        "password", "passwd", "pwd", "secret", "credential",
        "private_key", "access_token", "auth_token", "bearer",
    ]

    def __init__(self, auto_scrub: bool = False):
        self.auto_scrub = auto_scrub

    def scan(self, payload: Dict[str, Any]) -> PIIScanResult:
        """Scan a tune payload for PII."""
        issues: List[Dict[str, Any]] = []
        text = self._flatten_payload(payload)

        for pii_type, pattern in self.PATTERNS.items():
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) < 3:
                    continue
                issues.append({
                    "type": pii_type,
                    "match": match[:50],  # Truncate for display
                    "severity": "high" if pii_type in ("ssn", "credit_card", "api_key") else "medium",
                })

        # Keyword scan
        text_lower = text.lower()
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in text_lower:
                # Find context
                idx = text_lower.index(keyword)
                context = text[max(0, idx - 20):idx + len(keyword) + 20]
                issues.append({
                    "type": "high_risk_keyword",
                    "match": context,
                    "severity": "high",
                })

        risk_score = self._calculate_risk_score(issues)
        return PIIScanResult(
            clean=len(issues) == 0,
            issues=issues,
            risk_score=risk_score,
        )

    def scrub(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-scrub detected PII from payload."""
        text = json.dumps(payload)

        for pii_type, pattern in self.PATTERNS.items():
            text = pattern.sub(f"[{pii_type}_REDACTED]", text)

        for keyword in self.HIGH_RISK_KEYWORDS:
            # Simple replacement: remove surrounding context
            text = re.sub(
                rf"({keyword}[^\"']*[=:]\s*)[\"']?[^\"'\s,}}]{{4,}}[\"']?",
                r"\1[REDACTED]",
                text,
                flags=re.IGNORECASE,
            )

        return json.loads(text)

    def _flatten_payload(self, payload: Dict[str, Any]) -> str:
        """Recursively flatten payload dict to a searchable string."""
        parts = []

        def _walk(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)
            elif isinstance(obj, str):
                parts.append(obj)

        _walk(payload)
        return " ".join(parts)

    def _calculate_risk_score(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate aggregate risk score from issues."""
        if not issues:
            return 0.0
        high = sum(1 for i in issues if i["severity"] == "high")
        medium = sum(1 for i in issues if i["severity"] == "medium")
        score = min(1.0, high * 0.3 + medium * 0.1)
        return round(score, 2)


import json
