"""
core/dictation_memory.py — Local-only dictation history storage.

Every voice input (dictation, agent, task, bg-agent) is stored locally
in data/dictation_memories.json on the user's computer only.
Never touches any database or cloud service.

Used by the dictation overlay dropdown to show previous prompts/memories.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_MAX_ENTRIES = 1000
_MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictation_memories.json"
_lock = threading.Lock()


def _path() -> Path:
    _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _MEMORY_PATH


def _load_unsafe() -> List[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("memories", [])
    except Exception:
        return []


def _save_unsafe(memories: List[dict]) -> None:
    path = _path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"memories": memories}, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def add_memory(original_text: str, final_text: str, mode: str = "dictation") -> dict:
    """
    Append a new dictation memory entry.

    Args:
        original_text: Raw transcript straight from Whisper.
        final_text:    Text after refinement, vocab, and formatting.
        mode:          One of 'dictation', 'agent', 'task', 'bg_agent'.
    """
    entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "original_text": (original_text or "").strip(),
        "final_text": (final_text or "").strip(),
    }
    with _lock:
        memories = _load_unsafe()
        memories.insert(0, entry)
        if len(memories) > _MAX_ENTRIES:
            memories = memories[:_MAX_ENTRIES]
        _save_unsafe(memories)

    # Push to overlay in real time
    try:
        from core.ws_bridge import broadcast_sync
        broadcast_sync({"type": "dictation_memories/update", "memories": [entry]})
    except Exception:
        pass

    return entry


def get_memories(limit: Optional[int] = None, mode: Optional[str] = None) -> List[dict]:
    """
    Retrieve memories, newest first.

    Args:
        limit: Cap the number of returned entries.
        mode:  Filter by mode (e.g. 'dictation'). None = all.
    """
    memories = _load_unsafe()
    if mode:
        memories = [m for m in memories if m.get("mode") == mode]
    return memories[:limit] if limit else memories


def clear_memories() -> None:
    """Wipe all local dictation history."""
    with _lock:
        _save_unsafe([])
    try:
        from core.ws_bridge import broadcast_sync
        broadcast_sync({"type": "dictation_memories/update", "memories": []})
    except Exception:
        pass


def delete_memory(entry_id: str) -> bool:
    """Remove a single memory by its id."""
    with _lock:
        memories = _load_unsafe()
        before = len(memories)
        memories = [m for m in memories if m.get("id") != entry_id]
        if len(memories) < before:
            _save_unsafe(memories)
            try:
                from core.ws_bridge import broadcast_sync
                broadcast_sync({"type": "dictation_memories/update", "memories": memories})
            except Exception:
                pass
            return True
    return False


def update_memory(entry_id: str, final_text: str, original_text: str | None = None) -> bool:
    """Update the text of an existing memory entry."""
    old_original = None
    old_final = None
    with _lock:
        memories = _load_unsafe()
        for m in memories:
            if m.get("id") == entry_id:
                old_original = m.get("original_text", "")
                old_final = m.get("final_text", "")
                m["final_text"] = (final_text or "").strip()
                if original_text is not None:
                    m["original_text"] = (original_text or "").strip()
                m["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_unsafe(memories)
                try:
                    from core.ws_bridge import broadcast_sync
                    broadcast_sync({"type": "dictation_memories/update", "memories": memories})
                except Exception:
                    pass
                break
        else:
            return False

    # Auto-learn corrections when the user edited the memory
    try:
        from core.dictation_correction import record_correction
        original = (original_text if original_text is not None else old_original) or old_final or ""
        corrected = (final_text or "").strip()
        if original and corrected and original != corrected:
            record_correction(original, corrected, confidence=0.8)
    except Exception:
        pass

    return True
