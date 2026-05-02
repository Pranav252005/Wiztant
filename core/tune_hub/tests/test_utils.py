"""Tests for Tune Hub shared utilities."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.utils.convergence import ConvergenceChecker, check_convergence_status
from core.tune_hub.utils.feature_extraction import (
    cosine_similarity,
    embed_text,
    extract_text_features,
    extract_weight_features,
)
from core.tune_hub.utils.ab_testing import ABTestFramework, mann_whitney_u_test
from core.tune_hub.utils.model_persistence import TuneModelPersistence


class TestConvergence:
    def test_continue_with_no_observations(self):
        checker = ConvergenceChecker()
        result = checker.check()
        assert result.status == "CONTINUE"

    def test_quality_plateau_convergence(self):
        checker = ConvergenceChecker(max_iterations=20)
        for i in range(5):
            checker.record({"quality_score": 0.9})
        result = checker.check()
        assert result.status == "CONVERGED_HIGH_QUALITY"

    def test_budget_convergence(self):
        checker = ConvergenceChecker(max_iterations=5)
        for i in range(5):
            checker.record({"quality_score": 0.5})
        result = checker.check()
        assert result.status == "CONVERGED_BUDGET"

    def test_weight_stability(self):
        checker = ConvergenceChecker()
        for i in range(5):
            checker.record({"weights": [0.7, 0.3, 0.0, 0.0, 0.0]})
        result = checker.check()
        assert result.status == "CONVERGED_WEIGHTS_STABLE"

    def test_diverging(self):
        checker = ConvergenceChecker()
        for i in range(5):
            checker.record({"user_override": True})
        result = checker.check()
        assert result.status == "DIVERGING_REVIEW_NEEDED"

    def test_check_convergence_status_helper(self):
        obs = [{"quality_score": 0.92} for _ in range(5)]
        status = check_convergence_status(obs, max_iterations=10)
        assert status == "CONVERGED_HIGH_QUALITY"


class TestFeatureExtraction:
    def test_embed_text_deterministic(self):
        e1 = embed_text("hello world", dim=128)
        e2 = embed_text("hello world", dim=128)
        assert e1 == e2
        assert len(e1) == 128

    def test_cosine_similarity_identical(self):
        e = embed_text("test", dim=64)
        sim = cosine_similarity(e, e)
        assert sim >= 0.9999

    def test_cosine_similarity_different(self):
        e1 = embed_text("hello world", dim=64)
        e2 = embed_text("goodbye moon", dim=64)
        sim = cosine_similarity(e1, e2)
        assert -1.0 <= sim <= 1.0

    def test_extract_text_features(self):
        features = extract_text_features("How do I debug this Python function?")
        assert features["has_question"] is True
        assert features["keyword_signals"]["code"] is True
        assert features["keyword_signals"]["write"] is False

    def test_extract_weight_features(self):
        weights = [0.7, 0.3, 0.0, 0.0, 0.0]
        features = extract_weight_features(weights)
        assert features["concentration"] == 0.7
        assert features["active_count"] == 2
        assert features["entropy"] > 0


class TestABTesting:
    def test_mann_whitney_insufficient_data(self):
        result = mann_whitney_u_test([0.8], [0.7])
        assert result.status == "INSUFFICIENT_DATA"

    def test_mann_whitney_improvement(self):
        treatment = [0.9, 0.85, 0.88, 0.92, 0.87]
        control = [0.5, 0.55, 0.52, 0.48, 0.51]
        result = mann_whitney_u_test(treatment, control)
        assert result.status in ("SIGNIFICANT_IMPROVEMENT", "NO_SIGNIFICANT_DIFFERENCE")
        assert result.p_value >= 0.0

    def test_ab_test_framework_assignment(self):
        framework = ABTestFramework()
        group = framework.assign_group("user_123", "coding")
        assert group in ("control", "treatment")
        # Deterministic
        group2 = framework.assign_group("user_123", "coding")
        assert group == group2

    def test_ab_test_framework_record_and_evaluate(self):
        framework = ABTestFramework(min_sample_size=3)
        for i in range(5):
            framework.record_score("test_1", "treatment", 0.9)
            framework.record_score("test_1", "control", 0.5)
        result = framework.evaluate("test_1")
        assert result.status != "INSUFFICIENT_DATA"


class TestModelPersistence:
    def test_save_and_load_observations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pers = TuneModelPersistence(base_dir=tmpdir)
            obs = [{"iteration": i, "score": 0.8} for i in range(3)]
            path = pers.save_observations("u1", "reprompt", "coding", obs)
            assert path.exists()
            loaded = pers.load_observations("u1", "reprompt", "coding")
            assert len(loaded) == 3
            assert loaded[0]["iteration"] == 0

    def test_save_and_load_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pers = TuneModelPersistence(base_dir=tmpdir)
            data = {"blend": {"debug": 0.7}}
            path = pers.save_json("u1", "reprompt", "coding", data)
            assert path.exists()
            loaded = pers.load_json("u1", "reprompt", "coding")
            assert loaded["blend"]["debug"] == 0.7

    def test_checkpoint_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pers = TuneModelPersistence(base_dir=tmpdir)
            checkpoint = {"gp_weights": [0.1, 0.2], "version": 2}
            pers.save_checkpoint("u1", "reprompt", "coding", checkpoint)
            loaded = pers.load_checkpoint("u1", "reprompt", "coding")
            assert loaded["version"] == 2

    def test_delete_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pers = TuneModelPersistence(base_dir=tmpdir)
            pers.save_json("u1", "reprompt", "coding", {"a": 1})
            pers.save_observations("u1", "reprompt", "coding", [])
            pers.delete_all("u1", "reprompt", "coding")
            assert pers.load_json("u1", "reprompt", "coding") is None
