"""Pytest configuration — ensures project root is on sys.path before any test imports."""
from __future__ import annotations

import sys
from pathlib import Path

# Insert project root (parent of tests/) at the front of sys.path so that
# 'from core import ...' resolves to the project's core/ package rather than
# any other 'core' package that might appear earlier on sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
