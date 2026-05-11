"""Tests for task category list management in core/tasks.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.tasks import (
    _load,
    _save,
    get_categories,
    add_category,
    remove_category,
    add_task,
    DEFAULT_CATEGORIES,
)


def setup_module():
    # Use a temp tasks file for hermetic tests
    from core import tasks as tasks_module
    tasks_module._TASKS_PATH = Path(__file__).resolve().parent / "_test_tasks.json"
    if tasks_module._TASKS_PATH.exists():
        tasks_module._TASKS_PATH.unlink()


def teardown_module():
    from core import tasks as tasks_module
    if tasks_module._TASKS_PATH.exists():
        tasks_module._TASKS_PATH.unlink()


def test_default_categories():
    cats = get_categories()
    assert "College" in cats
    assert "Home" in cats
    assert "Other" in cats


def test_add_category():
    result = add_category("Freelance")
    assert result is True
    cats = get_categories()
    assert "Freelance" in cats


def test_add_duplicate_category():
    add_category("Freelance")
    result = add_category("Freelance")
    assert result is False


def test_remove_category_moves_tasks():
    # Ensure category exists
    add_category("TempCat")
    task = add_task("something for tempcat", category="TempCat")
    assert task["category"] == "TempCat"

    result = remove_category("TempCat")
    assert result is True

    data = _load()
    updated_task = next((t for t in data["tasks"] if t["id"] == task["id"]), None)
    assert updated_task is not None
    assert updated_task["category"] == "Other"


def test_cannot_remove_other_category():
    result = remove_category("Other")
    assert result is False
