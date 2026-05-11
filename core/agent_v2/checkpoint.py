"""Git checkpoint helper for agent v2."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_checkpoint(project_path: Path, message: str) -> bool:
    """Auto-commit with message if inside a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False
        subprocess.run(["git", "add", "-A"], cwd=project_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=project_path, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
