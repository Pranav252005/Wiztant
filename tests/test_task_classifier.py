"""Tests for core/task_classifier.classify."""

import pytest

from core import task_classifier, tasks


def _task(tid: str, text: str, status: str = "pending") -> dict:
    return {"id": tid, "text": text, "status": status}


def test_empty_input_is_new():
    assert task_classifier.classify("", [])["action"] == "new"


def test_exact_match_is_duplicate():
    existing = [_task("t1", "Build SHIVORA landing page")]
    result = task_classifier.classify("build shivora landing page", existing)
    assert result["action"] == "duplicate"
    assert result["parent_id"] == "t1"


def test_no_shared_subject_is_new(monkeypatch):
    # Disable LLM path so we only test heuristic.
    monkeypatch.setattr(task_classifier, "_llm_arbitrate", lambda *a, **kw: None)
    existing = [_task("t1", "Build SHIVORA landing page")]
    result = task_classifier.classify("Fix COGLIO auth bug", existing)
    assert result["action"] == "new"


def test_shared_subject_fallback_is_subtask_when_no_llm(monkeypatch):
    monkeypatch.setattr(task_classifier, "_llm_arbitrate", lambda *a, **kw: None)
    existing = [_task("t1", "Build SHIVORA landing page")]
    result = task_classifier.classify("SHIVORA landing page due 6 pm", existing)
    assert result["action"] == "subtask"
    assert result["parent_id"] == "t1"
    # subtask_text should strip the shared subject
    assert "due 6 pm" in result["subtask_text"].lower()


def test_llm_independent_overrides_heuristic(monkeypatch):
    monkeypatch.setattr(
        task_classifier,
        "_llm_arbitrate",
        lambda a, b: {"relation": "independent", "reason": "different domain"},
    )
    existing = [_task("t1", "Build SHIVORA landing page")]
    result = task_classifier.classify("Record SHIVORA demo video", existing)
    assert result["action"] == "new"


def test_llm_duplicate_verdict(monkeypatch):
    monkeypatch.setattr(
        task_classifier,
        "_llm_arbitrate",
        lambda a, b: {"relation": "duplicate", "reason": "same action"},
    )
    existing = [_task("t1", "Build SHIVORA landing page")]
    result = task_classifier.classify(
        "create the SHIVORA landing page", existing
    )
    assert result["action"] == "duplicate"


def test_done_tasks_are_ignored():
    existing = [_task("t1", "Build SHIVORA landing page", status="done")]
    result = task_classifier.classify("Build SHIVORA landing page", existing)
    assert result["action"] == "new"


# ─── _find_best_task_match via tasks.py ──────────────────────────────

def test_find_best_match_exact():
    existing = [
        {"id": "t1", "text": "Build SHIVORA landing page", "status": "pending"},
        {"id": "t2", "text": "Fix COGLIO auth bug", "status": "pending"},
    ]
    matched = tasks._find_best_task_match("Build SHIVORA landing page", existing)
    assert matched is not None
    assert matched["id"] == "t1"


def test_find_best_match_fuzzy():
    existing = [
        {"id": "t1", "text": "Build SHIVORA landing page", "status": "pending"},
    ]
    matched = tasks._find_best_task_match("build shivora landing", existing)
    assert matched is not None
    assert matched["id"] == "t1"


def test_find_best_match_no_good_match():
    existing = [
        {"id": "t1", "text": "Build SHIVORA landing page", "status": "pending"},
    ]
    matched = tasks._find_best_task_match("completely unrelated thing", existing)
    assert matched is None


def test_find_best_match_empty_list():
    matched = tasks._find_best_task_match("anything", [])
    assert matched is None
