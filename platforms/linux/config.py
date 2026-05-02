"""platforms/linux/config.py — Linux file-path configuration."""
from pathlib import Path
import os

_home = Path.home()

CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", _home / ".config")) / "whiztant"
DATA_DIR = Path(os.getenv("XDG_DATA_HOME", _home / ".local" / "share")) / "whiztant"
CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", _home / ".cache")) / "whiztant"
DB_PATH = DATA_DIR / "memory.db"
ENV_PATH = CONFIG_DIR / ".env"


def setup():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Config/Linux] Data dir: {DATA_DIR}")
