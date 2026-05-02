"""platforms/windows/config.py — Windows file-path configuration."""
from pathlib import Path
import os

_APPDATA = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

CONFIG_DIR = _APPDATA / "Whiztant" / "Config"
DATA_DIR = _APPDATA / "Whiztant" / "Data"
CACHE_DIR = _APPDATA / "Whiztant" / "Cache"
DB_PATH = DATA_DIR / "memory.db"
ENV_PATH = CONFIG_DIR / ".env"


def setup():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Config/Windows] Data dir: {DATA_DIR}")
