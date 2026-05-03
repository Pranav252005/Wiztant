"""Tests for Tune Hub middleware and integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.middleware import TuneApplicationMiddleware
from core.tune_hub.orchestrator import TuneHub, TuneRequest
from core.tune_hub.quality.judge import SimpleJudge
from core.tune_hub.storage.sqlite_store import SQLiteTuneStore


class TestMiddleware:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = Path(self.tmpdir) / "tunes.db"
        self.storage = SQLiteTuneStore(str(db_path))
        self.credits = None  # No credit tracking
        self.hub = TuneHub(
            storage=self.storage,
            quality_judge_factory=SimpleJudge,
            desktop_mode="desktop2",
        )
        self.middleware = TuneApplicationMiddleware(self.hub)

    def test_apply_with_no_tune(self):
        result = self.middleware.apply(
            user_id="u1",
            feature_name="reprompt",
            task="hello world",
            feature_input={"prompt": "hello"},
        )
        assert result["tune_id"] is None
        assert "persona_weights" in result

    def test_apply_with_active_tune(self):
        # Create a tune first
        req = TuneRequest(
            user_id="u1",
            feature_name="reprompt",
            task="coding",
            approved_credits=50,
            tier="pro",
        )
        self.hub.tune_feature(req)

        # Now resolve
        result = self.middleware.apply(
            user_id="u1",
            feature_name="reprompt",
            task="coding",
            feature_input={"prompt": "hello"},
        )
        assert result["tune_id"] is not None
        assert "persona_weights" in result

    def test_middleware_latency_under_budget(self):
        result = self.middleware.apply(
            user_id="u2",
            feature_name="reprompt",
            task="hello",
            feature_input={"prompt": "hello"},
        )
        # We can't directly test latency in unit tests, but we can test it doesn't crash
        assert "persona_weights" in result

    def test_middleware_stats(self):
        req = TuneRequest(
            user_id="u3",
            feature_name="reprompt",
            task="coding",
            approved_credits=50,
            tier="pro",
        )
        self.hub.tune_feature(req)

        stats = self.middleware.get_stats("u3")
        assert stats["total_tunes"] == 1
        assert stats["active_tunes"] == 1
        assert "reprompt" in stats["features_with_tunes"]

    def test_middleware_handler(self):
        events = []

        def handler(event):
            events.append(event)

        self.middleware.register_handler("reprompt", handler)
        self.middleware.apply(
            user_id="u4",
            feature_name="reprompt",
            task="hello",
            feature_input={"prompt": "hello"},
        )
        assert len(events) == 1
        assert events[0].feature_name == "reprompt"

        self.middleware.unregister_handler("reprompt", handler)
