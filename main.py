"""main.py — Backward-compatible entry-point shim.

Delegates to app/main.py. Prefer running `python -m app.main` directly.
"""
from __future__ import annotations

import sys
import os

# Ensure project root is on path
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

if __name__ == "__main__":
    from app.main import run_app
    run_app()
