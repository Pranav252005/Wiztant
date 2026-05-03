"""Tests for Tune Hub base classes."""

from __future__ import annotations

import pytest

from core.tune_hub.base import (
    ComplexityLevel,
    LearnedModel,
    TuneStatus,
)


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
