"""Tests for TuneHub orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.base import ComplexityLevel, CreditBudget, TuneStatus
from core.tune_hub.credit_system.free_tracker import FreeCreditTracker
from core.tune_hub.orchestrator import TuneHub, TuneRequest
from core.tune_hub.quality.judge import SimpleJudge
from core.tune_hub.storage.sqlite_store import SQLiteTuneStore


class TestTuneHub:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = Path(self.tmpdir) / "tunes.db"
        ledger_path = Path(self.tmpdir) / "credits.json"
        self.storage = SQLiteTuneStore(str(db_path))
        self.credits = FreeCreditTracker(str(ledger_path))
        self.hub = TuneHub(
            storage=self.storage,
            credit_tracker=self.credits,
            quality_judge_factory=SimpleJudge,
            desktop_mode="desktop2",
        )

    def test_tune_feature_success(self):
        req = TuneRequest(
            user_id="u1",
            feature_name="reprompt",
            task="coding tasks",
            approved_credits=50,
            tier="pro",
        )
        result = self.hub.tune_feature(req)
        assert result.success
        assert result.model is not None
        assert result.model.status == TuneStatus.DEPLOYED
        assert result.credits_used > 0

    def test_free_tier_one_tune_limit(self):
        req = TuneRequest(
            user_id="u2",
            feature_name="reprompt",
            task="coding tasks",
            approved_credits=50,
            tier="free",
        )
        result1 = self.hub.tune_feature(req)
        assert result1.success

        # Second tune should be blocked
        req2 = TuneRequest(
            user_id="u2",
            feature_name="reprompt",
            task="writing tasks",
            approved_credits=50,
            tier="free",
        )
        result2 = self.hub.tune_feature(req2)
        assert not result2.success
        assert "Only 1 tune" in result2.message

    def test_tier_gate_blocks_complexity(self):
        req = TuneRequest(
            user_id="u3",
            feature_name="reprompt",
            task="code write research debug plan everything",
            approved_credits=100,
            tier="free",
        )
        result = self.hub.tune_feature(req)
        assert not result.success
        assert "tier upgrade" in result.message

    def test_resolve_tune_hot_path(self):
        # First create a tune
        req = TuneRequest(
            user_id="u4",
            feature_name="reprompt",
            task="coding",
            approved_credits=50,
            tier="pro",
        )
        self.hub.tune_feature(req)

        # Resolve should return tuned config
        result = self.hub.resolve_tune("u4", "reprompt", "coding", {"prompt": "hello"})
        assert "persona_weights" in result
        assert result["tune_id"] is not None

    def test_resolve_tune_fallback(self):
        # No tune exists — should return default
        result = self.hub.resolve_tune("u5", "reprompt", "unknown_task", {"prompt": "hello"})
        assert result["tune_id"] is None
        assert "persona_weights" in result

    def test_list_and_delete(self):
        req = TuneRequest(
            user_id="u6",
            feature_name="reprompt",
            task="coding",
            approved_credits=50,
            tier="pro",
        )
        self.hub.tune_feature(req)
        tunes = self.hub.list_tunes("u6")
        assert len(tunes) == 1

        self.hub.delete_tune("u6", tunes[0].tune_id)
        assert len(self.hub.list_tunes("u6")) == 0

    def test_rollback(self):
        req = TuneRequest(
            user_id="u7",
            feature_name="reprompt",
            task="coding",
            approved_credits=50,
            tier="power",
        )
        self.hub.tune_feature(req)
        original = self.hub.list_tunes("u7")[0]

        # Store a new version manually
        original.version = 2
        self.storage.store_tune("u7", original)

        rollback = self.hub.rollback_tune("u7", original.tune_id, 1)
        assert rollback is not None
        assert rollback.version == 3
        assert rollback.parent_version == 2
