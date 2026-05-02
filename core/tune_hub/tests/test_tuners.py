"""Tests for TuneHub tuner plugins."""

from __future__ import annotations

from core.tune_hub.base import ComplexityLevel, CreditBudget, TuneStatus
from core.tune_hub.quality.judge import SimpleJudge
from core.tune_hub.tuners.agent_tuner import AgentTuner
from core.tune_hub.tuners.dictation_tuner import DictationTuner
from core.tune_hub.tuners.reprompt_tuner import RePromptTuner


class TestRePromptTuner:
    def setup_method(self):
        self.tuner = RePromptTuner()
        self.judge = SimpleJudge()

    def test_estimate_complexity(self):
        assert self.tuner.estimate_complexity("code") == ComplexityLevel.LOW
        assert self.tuner.estimate_complexity("code write") == ComplexityLevel.MEDIUM
        assert (
            self.tuner.estimate_complexity("code write research debug plan")
            == ComplexityLevel.HIGH
        )

    def test_learn_and_validate(self):
        budget = CreditBudget(approved=20)
        model = self.tuner.learn(
            task="coding tasks", budget=budget, judge=self.judge
        )
        assert model.feature_name == "reprompt"
        assert model.status == TuneStatus.DRAFT
        assert "personas" in model.payload

        valid = self.tuner.validate(model)
        assert isinstance(valid, bool)

    def test_apply(self):
        budget = CreditBudget(approved=20)
        model = self.tuner.learn(
            task="coding tasks", budget=budget, judge=self.judge
        )
        result = self.tuner.apply(model, {"prompt": "hello"})
        assert "persona_weights" in result
        assert result["tune_id"] == model.tune_id

    def test_default_config(self):
        default = self.tuner.get_default_config("any")
        assert default["tune_id"] is None
        assert set(default["persona_weights"].keys()) == set(
            RePromptTuner.PERSONAS
        )


class TestDictationTuner:
    def setup_method(self):
        self.tuner = DictationTuner()

    def test_estimate_complexity(self):
        assert self.tuner.estimate_complexity("general speech") == ComplexityLevel.LOW
        assert self.tuner.estimate_complexity("crypto trading") == ComplexityLevel.MEDIUM
        assert self.tuner.estimate_complexity("medical terminology") == ComplexityLevel.HIGH

    def test_learn_and_validate(self):
        budget = CreditBudget(approved=20)
        model = self.tuner.learn(
            task="crypto vocabulary",
            budget=budget,
            context={"vocabulary": ["ethereum", "bitcoin", "defi"]},
        )
        assert model.feature_name == "dictation"
        assert "corrections" in model.payload

        valid = self.tuner.validate(model)
        assert isinstance(valid, bool)

    def test_apply(self):
        budget = CreditBudget(approved=20)
        model = self.tuner.learn(
            task="crypto vocabulary",
            budget=budget,
            context={"vocabulary": ["ethereum", "bitcoin"]},
        )
        result = self.tuner.apply(model, {"text": "ethreum"})
        assert "correction_map" in result


class TestAgentTuner:
    def setup_method(self):
        self.tuner = AgentTuner()

    def test_estimate_complexity(self):
        assert self.tuner.estimate_complexity("simple click") == ComplexityLevel.LOW
        assert (
            self.tuner.estimate_complexity("multi step", {"estimated_steps": 5})
            == ComplexityLevel.MEDIUM
        )
        assert (
            self.tuner.estimate_complexity("multi_app workflow", {"estimated_steps": 12})
            == ComplexityLevel.HIGH
        )

    def test_learn_and_validate(self):
        budget = CreditBudget(approved=10)
        model = self.tuner.learn(
            task="automate photoshop dark photo editing",
            budget=budget,
        )
        assert model.feature_name == "agent"
        assert "recipe" in model.payload

        valid = self.tuner.validate(model)
        assert isinstance(valid, bool)

    def test_apply(self):
        budget = CreditBudget(approved=10)
        model = self.tuner.learn(
            task="automate file open",
            budget=budget,
        )
        result = self.tuner.apply(model, {"target": "photoshop"})
        assert "recipe" in result


class TestPluginRegistry:
    def test_registered_tuners(self):
        registry = RePromptTuner.get_registered_tuners()
        assert "reprompt" in registry
        assert "dictation" in registry
        assert "agent" in registry

    def test_create_by_name(self):
        t1 = RePromptTuner.create("reprompt")
        assert isinstance(t1, RePromptTuner)
        t2 = RePromptTuner.create("dictation")
        assert isinstance(t2, DictationTuner)

    def test_create_unknown_raises(self):
        try:
            RePromptTuner.create("nonexistent")
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "nonexistent" in str(e)
