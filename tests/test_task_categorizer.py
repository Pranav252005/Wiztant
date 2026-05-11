"""Tests for core/task_categorizer.py"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.task_categorizer import categorize_task, estimate_difficulty, auto_categorize


def test_categorize_task_college():
    assert categorize_task("finish calculus homework") == "College"
    assert categorize_task("study for exam tomorrow") == "College"
    assert categorize_task("write lab report") == "College"


def test_categorize_task_home():
    assert categorize_task("clean my room") == "Home"
    assert categorize_task("buy groceries for dinner") == "Home"
    assert categorize_task("do laundry today") == "Home"


def test_categorize_task_solopreneur():
    assert categorize_task("deploy wiztant landing page") == "Solopreneur"
    assert categorize_task("write newsletter for customers") == "Solopreneur"
    assert categorize_task("fix onboarding flow in app") == "Solopreneur"


def test_categorize_task_solo_project():
    assert categorize_task("build my personal portfolio") == "Solo Project"
    assert categorize_task("practice guitar by myself") == "Solo Project"


def test_categorize_task_group_project():
    assert categorize_task("team meeting with classmates") == "Group Project"
    assert categorize_task("collaborate on group project") == "Group Project"


def test_categorize_task_other():
    assert categorize_task("something random") == "Other"
    assert categorize_task("xyz abc") == "Other"


def test_estimate_difficulty_easy():
    assert estimate_difficulty("easy fix") == "easy"
    assert estimate_difficulty("quick simple task") == "easy"
    assert estimate_difficulty("ok") == "easy"


def test_estimate_difficulty_hard():
    assert estimate_difficulty("hard complex algorithm") == "hard"
    assert estimate_difficulty("major challenging implementation") == "hard"


def test_estimate_difficulty_medium():
    assert estimate_difficulty("finish homework before dinner time") == "medium"
    assert estimate_difficulty("call mom about weekend plans") == "medium"


def test_estimate_difficulty_length_heuristic():
    assert estimate_difficulty("a" * 200) == "hard"
    assert estimate_difficulty("a" * 10) == "easy"


def test_auto_categorize_basic():
    cat, diff = auto_categorize("finish calculus homework and study for the exam")
    assert cat == "College"
    assert diff == "medium"


def test_auto_categorize_with_categories():
    cat, diff = auto_categorize("random unknown task about nothing important", categories=["College", "Home", "Other"])
    assert cat == "Other"
    assert diff == "medium"
