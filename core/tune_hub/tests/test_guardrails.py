"""Tests for TuneHub boundary guardrails."""

from __future__ import annotations

import pytest
from pathlib import Path

from core.tune_hub.guardrails import (
    ALLOWED_FEATURES,
    ALLOWED_SUFFIXES,
    INJECTABLE_KEYS,
    TuneBoundaryGuard,
    TuneBoundaryViolation,
)


class TestValidateFeatureName:
    def test_allowed_feature(self):
        for feat in ALLOWED_FEATURES:
            ok, reason = TuneBoundaryGuard.validate_feature_name(feat)
            assert ok is True
            assert reason == ""

    def test_unknown_feature(self):
        ok, reason = TuneBoundaryGuard.validate_feature_name("system")
        assert ok is False
        assert "not in ALLOWED_FEATURES" in reason

    def test_empty_feature(self):
        ok, reason = TuneBoundaryGuard.validate_feature_name("")
        assert ok is False
        assert "non-empty" in reason

    def test_non_string_feature(self):
        ok, reason = TuneBoundaryGuard.validate_feature_name(None)  # type: ignore[arg-type]
        assert ok is False


class TestValidateInjection:
    def test_unchanged_input(self):
        original = {"prompt": "hello"}
        modified = {"prompt": "hello"}
        ok, reason = TuneBoundaryGuard.validate_injection(
            "reprompt", original, modified
        )
        assert ok is True

    def test_add_allowed_key(self):
        original = {"prompt": "hello"}
        modified = {"prompt": "hello", "persona_weights": {"debug": 0.5}}
        ok, reason = TuneBoundaryGuard.validate_injection(
            "reprompt", original, modified
        )
        assert ok is True

    def test_add_disallowed_key(self):
        original = {"prompt": "hello"}
        modified = {"prompt": "hello", "system_cmd": "rm -rf /"}
        ok, reason = TuneBoundaryGuard.validate_injection(
            "reprompt", original, modified
        )
        assert ok is False
        assert "not an injectable key" in reason

    def test_mutate_non_injectable_key(self):
        original = {"prompt": "hello"}
        modified = {"prompt": "goodbye"}
        ok, reason = TuneBoundaryGuard.validate_injection(
            "reprompt", original, modified
        )
        assert ok is False
        assert "not injectable" in reason

    def test_remove_key(self):
        original = {"prompt": "hello", "persona_weights": {"debug": 0.5}}
        modified = {"prompt": "hello"}
        ok, reason = TuneBoundaryGuard.validate_injection(
            "reprompt", original, modified
        )
        assert ok is False
        assert "removed" in reason

    def test_unknown_feature_injection(self):
        ok, reason = TuneBoundaryGuard.validate_injection(
            "unknown", {"a": 1}, {"a": 1}
        )
        assert ok is False


class TestSanitizePersistencePath:
    def test_basic_path(self, tmp_path: Path):
        result = TuneBoundaryGuard.sanitize_persistence_path(
            tmp_path, "user1", "reprompt", "coding_tasks", ".json"
        )
        assert result.parent == tmp_path
        assert result.name.startswith("user1_reprompt_coding_tasks")
        assert result.suffix == ".json"

    def test_path_traversal_user_id(self, tmp_path: Path):
        with pytest.raises(TuneBoundaryViolation):
            TuneBoundaryGuard.sanitize_persistence_path(
                tmp_path, "../etc/passwd", "reprompt", "task", ".json"
            )

    def test_path_traversal_task_signature(self, tmp_path: Path):
        with pytest.raises(TuneBoundaryViolation):
            TuneBoundaryGuard.sanitize_persistence_path(
                tmp_path, "user", "reprompt", "../../secrets", ".json"
            )

    def test_null_byte_in_segment(self, tmp_path: Path):
        result = TuneBoundaryGuard.sanitize_persistence_path(
            tmp_path, "u\x00ser", "reprompt", "task", ".json"
        )
        assert "\x00" not in str(result)

    def test_disallowed_suffix(self, tmp_path: Path):
        with pytest.raises(ValueError):
            TuneBoundaryGuard.sanitize_persistence_path(
                tmp_path, "user", "reprompt", "task", ".exe"
            )

    def test_path_is_under_base_dir(self, tmp_path: Path):
        result = TuneBoundaryGuard.sanitize_persistence_path(
            tmp_path, "user", "reprompt", "task", ".json"
        )
        resolved = result.resolve()
        base_resolved = tmp_path.resolve()
        assert str(resolved).startswith(str(base_resolved))


class TestEnsureImmutableInput:
    def test_returns_deep_copy(self):
        original = {"nested": {"key": "value"}}
        copied = TuneBoundaryGuard.ensure_immutable_input(original)
        assert copied == original
        copied["nested"]["key"] = "mutated"
        assert original["nested"]["key"] == "value"


class TestTuneModelPersistenceHardening:
    def test_save_json_with_traversal_raises(self, tmp_path: Path):
        from core.tune_hub.utils.model_persistence import TuneModelPersistence

        persist = TuneModelPersistence(str(tmp_path))
        with pytest.raises(TuneBoundaryViolation):
            persist.save_json("../etc/passwd", "reprompt", "task", {"a": 1})

    def test_save_json_disallowed_suffix(self, tmp_path: Path):
        from core.tune_hub.utils.model_persistence import TuneModelPersistence

        persist = TuneModelPersistence(str(tmp_path))
        with pytest.raises(ValueError):
            persist.save_json("user", "reprompt", "task", {"a": 1}, suffix=".exe")

    def test_allowed_suffixes_pass(self, tmp_path: Path):
        from core.tune_hub.utils.model_persistence import TuneModelPersistence

        persist = TuneModelPersistence(str(tmp_path))
        for suffix in ALLOWED_SUFFIXES:
            path = persist.save_json("user", "reprompt", "task", {"a": 1}, suffix=suffix)
            assert path.exists() or suffix == ".pkl"  # .pkl uses save_checkpoint
            # Clean up
            if path.exists():
                path.unlink()


class TestSafeApply:
    def test_safe_apply_allows_injectable_keys(self):
        from core.tune_hub.base import CreditBudget, LearnedModel, TuneStatus
        from core.tune_hub.tuners.reprompt_tuner import RePromptTuner

        tuner = RePromptTuner()
        model = LearnedModel(
            tune_id="test_123",
            feature_name="reprompt",
            task_signature="coding",
            payload={"personas": {"debug": 0.8}},
            quality_score=0.9,
            complexity=tuner.estimate_complexity("coding"),
            status=TuneStatus.DEPLOYED,
        )
        result = tuner.safe_apply(model, {"prompt": "hello"})
        assert result["persona_weights"] == {"debug": 0.8}
        assert result["tune_id"] == "test_123"

    def test_safe_apply_rejects_disallowed_key(self):
        from core.tune_hub.base import CreditBudget, LearnedModel, TuneStatus
        from core.tune_hub.tuners.reprompt_tuner import RePromptTuner

        tuner = RePromptTuner()
        model = LearnedModel(
            tune_id="test_123",
            feature_name="reprompt",
            task_signature="coding",
            payload={"personas": {"debug": 0.8}},
            quality_score=0.9,
            complexity=tuner.estimate_complexity("coding"),
            status=TuneStatus.DEPLOYED,
        )
        # Temporarily override apply to inject a bad key
        original_apply = tuner.apply
        tuner.apply = lambda m, inp: {**inp, "system_cmd": "rm -rf /"}
        try:
            with pytest.raises(TuneBoundaryViolation):
                tuner.safe_apply(model, {"prompt": "hello"})
        finally:
            tuner.apply = original_apply

    def test_safe_apply_preserves_original_dict(self):
        from core.tune_hub.base import CreditBudget, LearnedModel, TuneStatus
        from core.tune_hub.tuners.reprompt_tuner import RePromptTuner

        tuner = RePromptTuner()
        model = LearnedModel(
            tune_id="test_123",
            feature_name="reprompt",
            task_signature="coding",
            payload={"personas": {"debug": 0.8}},
            quality_score=0.9,
            complexity=tuner.estimate_complexity("coding"),
            status=TuneStatus.DEPLOYED,
        )
        original = {"prompt": "hello"}
        result = tuner.safe_apply(model, original)
        assert original == {"prompt": "hello"}
        assert "persona_weights" in result

    def test_agent_tuner_does_not_mutate_task(self):
        from core.tune_hub.base import CreditBudget, LearnedModel, TuneStatus
        from core.tune_hub.tuners.agent_tuner import AgentTuner

        tuner = AgentTuner()
        model = LearnedModel(
            tune_id="agent_123",
            feature_name="agent",
            task_signature="open_photoshop",
            payload={"recipe": [{"action": "open_app"}], "dsl_code": "RECIPE {}"},
            quality_score=0.9,
            complexity=tuner.estimate_complexity("open photoshop"),
            status=TuneStatus.DEPLOYED,
        )
        result = tuner.apply(model, {"task": "open photoshop"})
        assert result["task"] == "open photoshop"
        assert "recipe_hint" in result


class TestOrchestratorBoundaries:
    def test_tune_feature_rejects_unknown_feature(self):
        from core.tune_hub.orchestrator import TuneHub, TuneRequest
        from core.tune_hub.storage.sqlite_store import SQLiteTuneStore

        store = SQLiteTuneStore(":memory:")
        hub = TuneHub(storage=store)
        req = TuneRequest(
            user_id="u1",
            feature_name="system_hack",
            task="do bad thing",
            budget_limit=10,
        )
        result = hub.tune_feature(req)
        assert result.success is False
        assert "ALLOWED_FEATURES" in result.message

    def test_resolve_tune_rejects_unknown_feature(self):
        from core.tune_hub.orchestrator import TuneHub
        from core.tune_hub.storage.sqlite_store import SQLiteTuneStore

        store = SQLiteTuneStore(":memory:")
        hub = TuneHub(storage=store)
        with pytest.raises(TuneBoundaryViolation):
            hub.resolve_tune("u1", "system_hack", "task", {"prompt": "hello"})


class TestMiddlewareBoundaries:
    def test_middleware_preserves_original_dict(self):
        import tempfile
        from pathlib import Path
        from core.tune_hub.middleware import TuneApplicationMiddleware
        from core.tune_hub.orchestrator import TuneHub
        from core.tune_hub.storage.sqlite_store import SQLiteTuneStore

        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "tunes.db"
        store = SQLiteTuneStore(str(db_path))
        hub = TuneHub(storage=store)
        middleware = TuneApplicationMiddleware(hub)

        original = {"prompt": "hello", "nested": {"key": "value"}}
        result = middleware.apply("u1", "reprompt", "hello", original)
        assert original == {"prompt": "hello", "nested": {"key": "value"}}
        assert "persona_weights" in result

    def test_middleware_logs_boundary_violation_and_fallback(self):
        import tempfile
        from pathlib import Path
        from core.tune_hub.middleware import TuneApplicationMiddleware
        from core.tune_hub.orchestrator import TuneHub
        from core.tune_hub.storage.sqlite_store import SQLiteTuneStore

        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "tunes.db"
        store = SQLiteTuneStore(str(db_path))
        hub = TuneHub(storage=store)
        middleware = TuneApplicationMiddleware(hub)

        # Unknown feature should fallback to returning original input
        result = middleware.apply("u1", "unknown_feature", "task", {"prompt": "hello"})
        assert result == {"prompt": "hello"}

    def test_middleware_raises_when_fallback_disabled(self):
        import tempfile
        from pathlib import Path
        from core.tune_hub.middleware import TuneApplicationMiddleware
        from core.tune_hub.orchestrator import TuneHub
        from core.tune_hub.storage.sqlite_store import SQLiteTuneStore

        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "tunes.db"
        store = SQLiteTuneStore(str(db_path))
        hub = TuneHub(storage=store)
        middleware = TuneApplicationMiddleware(hub)
        middleware.disable_fallback()

        with pytest.raises(TuneBoundaryViolation):
            middleware.apply("u1", "unknown_feature", "task", {"prompt": "hello"})
