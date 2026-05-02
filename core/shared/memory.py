"""
=============================================================
  MEMORY MODULE  —  core/memory.py
=============================================================

  Stores what the AI learns about you across sessions.
  All data lives on your machine at:  {PROJECT_ROOT}/memory/memory.json
=============================================================
"""

import json
import re
import threading
import pathlib
import hashlib

# =============================================================
#  PATH
# =============================================================

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
MEMORY_DIR  = PROJECT_ROOT / "memory"
MEMORY_FILE = MEMORY_DIR / "memory.json"
LEGACY_MEMORY_FILE = PROJECT_ROOT / "data" / "memory.json"

# =============================================================
#  SCHEMA
# =============================================================

_SCHEMA = {
    "memory_enabled":   True,
    "identity":         {},
    "preferences":      {},
    "current_projects": {},
    "tools_and_tech":   {},
    "goals":            {},
    "context":          {},
    "notes":            {},
    "memory_hashes":    {}
}

_data = {}
_lock = threading.Lock()

# =============================================================
#  PERMISSION PROMPT
# =============================================================

def _ask_permission() -> bool:
    print()
    print("=" * 54)
    print("  MEMORY PERMISSION")
    print("=" * 54)
    print("  The assistant can remember things about you")
    print("  across sessions — your name, what you're building,")
    print("  tools you use, and preferences.")
    print()
    print("  This data is stored ONLY on your machine at:")
    print(f"  {MEMORY_FILE}")
    print()
    print("  You can view or delete the file at any time.")
    print("  No data is sent to any server.")
    print()
    try:
        ans = input("  Enable memory? (y/n) [y]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "y"
    enabled = ans != "n"
    print()
    if enabled:
        print("  Memory enabled. Learning starts now.")
    else:
        print("  Memory disabled. Running without memory.")
    print("=" * 54)
    print()
    return enabled

# =============================================================
#  LOAD / SAVE
# =============================================================

def _empty_data() -> dict:
    return {k: (v if not isinstance(v, dict) else {}) for k, v in _SCHEMA.items()}

def _has_user_memory(data: dict) -> bool:
    for section, content in data.items():
        if section in {"memory_enabled", "memory_hashes"}:
            continue
        if isinstance(content, dict) and any(str(value).strip() for value in content.values() if value is not None):
            return True
        if isinstance(content, str) and content.strip():
            return True
        if isinstance(content, list) and content:
            return True
    return False

def _merge_memory_data(primary: dict, secondary: dict) -> dict:
    merged = _empty_data()
    merged["memory_enabled"] = primary.get("memory_enabled", secondary.get("memory_enabled", True))
    valid_sections = {
        "identity",
        "preferences",
        "current_projects",
        "tools_and_tech",
        "goals",
        "context",
        "notes",
    }
    for section in valid_sections:
        section_data = {}
        if isinstance(secondary.get(section), dict):
            section_data.update(secondary.get(section, {}))
        if isinstance(primary.get(section), dict):
            section_data.update(primary.get(section, {}))
        merged[section] = section_data
    merged["memory_hashes"] = _compute_memory_hashes(merged)
    return merged

def _read_memory_file(path: pathlib.Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            merged = {**_SCHEMA}
            for k in merged:
                if k in raw:
                    merged[k] = raw[k]
            for k in raw:
                if k not in merged:
                    merged[k] = raw[k]
            return merged
    except Exception as e:
        print(f"[Memory] Load error: {e} — starting fresh")
    return _empty_data()

def _compute_memory_hashes(data: dict) -> dict:
    hashes: dict[str, dict[str, str]] = {}
    for section, content in data.items():
        if section in {"memory_enabled", "memory_hashes"} or not isinstance(content, dict):
            continue
        section_hashes: dict[str, str] = {}
        for key, value in content.items():
            if not value:
                continue
            raw = f"{section}:{key}:{value}".encode("utf-8")
            section_hashes[str(key)] = hashlib.md5(raw).hexdigest()
        hashes[section] = section_hashes
    return hashes

def _ensure_storage_location() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not LEGACY_MEMORY_FILE.exists():
        return
    try:
        if not MEMORY_FILE.exists():
            MEMORY_FILE.write_text(LEGACY_MEMORY_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            return
        current_data = _read_memory_file(MEMORY_FILE)
        legacy_data = _read_memory_file(LEGACY_MEMORY_FILE)
        if not _has_user_memory(current_data) and _has_user_memory(legacy_data):
            MEMORY_FILE.write_text(
                json.dumps(_merge_memory_data(current_data, legacy_data), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    except Exception as e:
        print(f"[Memory] Migration error: {e}")

def _load() -> dict:
    _ensure_storage_location()
    if MEMORY_FILE.exists():
        merged = _read_memory_file(MEMORY_FILE)
        merged["memory_hashes"] = _compute_memory_hashes(merged)
        return merged
    return _empty_data()

def _save(data: dict):
    try:
        data["memory_hashes"] = _compute_memory_hashes(data)
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[Memory] Save error: {e}")

# =============================================================
#  PUBLIC API
# =============================================================

def init() -> bool:
    global _data

    _ensure_storage_location()
    if MEMORY_FILE.exists():
        _data = _load()
        enabled = _data.get("memory_enabled", True)
        status  = "enabled" if enabled else "disabled"
        print(f"[Memory] Loaded — {MEMORY_FILE}  ({status})")
        return enabled

    enabled = _ask_permission()
    _data = _empty_data()
    _data["memory_enabled"] = enabled
    if enabled:
        _save(_data)
        print(f"[Memory] Created — {MEMORY_FILE}")
    return enabled

def as_text() -> str:
    lines = []
    skip  = {"memory_enabled", "memory_hashes"}
    for section, content in _data.items():
        if section in skip or not content:
            continue
        if isinstance(content, dict):
            items = ", ".join(f"{k}: {v}" for k, v in content.items() if v)
            if items:
                lines.append(f"  {section}: {items}")
        elif isinstance(content, list) and content:
            lines.append(f"  {section}: {', '.join(str(i) for i in content)}")
        elif isinstance(content, str) and content.strip():
            lines.append(f"  {section}: {content}")
    return "\n".join(lines) if lines else "  (no memory yet — still learning)"

def is_empty() -> bool:
    skip = {"memory_enabled", "memory_hashes"}
    return all(
        not v for k, v in _data.items() if k not in skip
    )

# =============================================================
#  BACKGROUND EXTRACTION
# =============================================================

_EXTRACT_PROMPT = """You are a memory extractor for a personal AI assistant.
Given ONE exchange, find NEW lasting facts about the USER worth storing.

STORE: name, location, occupation, tools they use, projects they are building,
       goals, preferences, hardware/setup, anything specific and persistent.

SKIP: questions, requests, assistant replies, vague statements, temporary info,
      anything already in the existing memory shown below.

EXISTING MEMORY:
{existing}

USER SAID: {user}
ASSISTANT REPLIED: {assistant}

Reply with ONLY:
  null
OR
  a JSON object with section keys and fact dicts

Valid section keys: identity, preferences, current_projects, tools_and_tech,
                    goals, context, notes

Example:
{{"identity": {{"name": "Alex"}}, "tools_and_tech": {{"editor": "VS Code"}}}}

No explanation. Output the JSON or null, nothing else."""


def update_from_exchange(user_text: str, assistant_reply: str):
    if not _data.get("memory_enabled", True):
        return

    def _extract():
        try:
            from core.agent import call_llm

            prompt = _EXTRACT_PROMPT.format(
                existing=as_text(),
                user=user_text[:500],
                assistant=assistant_reply[:300]
            )
            raw = call_llm(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            raw = raw.strip()

            if raw.lower() in ("null", "none", "{}"):
                return

            cleaned = raw
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```\w*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)

            facts = json.loads(cleaned)
            if not isinstance(facts, dict) or not facts:
                return

            valid_sections = {
                "identity", "preferences", "current_projects",
                "tools_and_tech", "goals", "context", "notes"
            }
            changed = False
            with _lock:
                for section, items in facts.items():
                    if section not in valid_sections:
                        continue
                    if not isinstance(items, dict):
                        continue
                    if section not in _data:
                        _data[section] = {}
                    for k, v in items.items():
                        if v and str(v).strip():
                            _data[section][str(k)] = str(v).strip()
                            changed = True
                if changed:
                    _save(_data)
                    print(f"[Memory] Updated: {list(facts.keys())}")

        except Exception:
            pass

    threading.Thread(target=_extract, daemon=True).start()
