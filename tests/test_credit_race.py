"""
Tests for credit system atomicity under concurrent deduction from multiple features.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.credit_system import CreditBalanceManager


def test_concurrent_deductions_never_lose_credits(tmp_path):
    """5 threads each making 20 deductions from balance=500 must leave exactly 0."""
    credits_file = tmp_path / "credits.json"
    from datetime import datetime, timezone
    credits_file.write_text(
        json.dumps({
            "user1": {
                "balance": 500,
                "tier": "free",
                "transactions": [],
                "reset_at": datetime.now(timezone.utc).isoformat(),
            }
        })
    )

    mgr = CreditBalanceManager(local_path=credits_file)

    errors: list[Exception] = []

    def deduct_loop():
        try:
            for _ in range(5):
                mgr.deduct("user1", "dictation", 1, model="whisper")
                mgr.deduct("user1", "reprompt", 1, model="gemini")
                mgr.deduct("user1", "agent", 1, model="qwen")
                mgr.deduct("user1", "tunehub", 1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=deduct_loop) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = mgr.get_balance("user1")
    # 5 threads × 5 iterations × 4 deductions × 1 credit = 100 credits deducted from 500 = 400
    assert final == 400, (
        f"Race condition lost credits: expected 400, got {final}. "
        f"Concurrent deductions from 4 features are not atomic."
    )
    assert not errors, f"Exceptions during concurrent deduction: {errors}"
