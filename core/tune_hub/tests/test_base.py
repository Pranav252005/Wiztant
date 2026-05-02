"""Tests for Tune Hub base classes."""

from __future__ import annotations

import pytest

from core.tune_hub.base import (
    ComplexityLevel,
    CreditBudget,
    InsufficientCreditsError,
    LearnedModel,
    TuneStatus,
)


class TestCreditBudget:
    def test_can_spend(self):
        budget = CreditBudget(approved=10)
        assert budget.can_spend(5)
        assert not budget.can_spend(11)

    def test_spend(self):
        budget = CreditBudget(approved=10)
        new_budget = budget.spend(3)
        assert new_budget.consumed == 3
        assert new_budget.can_spend(7)
        assert not new_budget.can_spend(8)

    def test_spend_exceeds(self):
        budget = CreditBudget(approved=10)
        with pytest.raises(InsufficientCreditsError):
            budget.spend(11)


class TestLearnedModel:
    def test_roundtrip(self):
        model = LearnedModel(
            tune_id="t1",
            feature_name="reprompt",
            task_signature="coding_tasks",
            payload={"personas": {"debug": 0.8}},
            quality_score=0.9,
            complexity=ComplexityLevel.MEDIUM,
            status=TuneStatus.DEPLOYED,
        )
        data = model.to_storage_format()
        restored = LearnedModel.from_storage_format(data)
        assert restored.tune_id == "t1"
        assert restored.feature_name == "reprompt"
        assert restored.status == TuneStatus.DEPLOYED
        assert restored.complexity == ComplexityLevel.MEDIUM


class TestEnums:
    def test_complexity_levels(self):
        assert ComplexityLevel.LOW.name == "LOW"
        assert ComplexityLevel.MEDIUM.name == "MEDIUM"
        assert ComplexityLevel.HIGH.name == "HIGH"

    def test_tune_status_order(self):
        assert TuneStatus.DRAFT.value < TuneStatus.VALIDATED.value
