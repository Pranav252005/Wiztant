"""core/wizprompt_memory.py — Few-shot memory store for WizPrompt.

SQLite-backed storage for accepted prompt optimizations with semantic embedding
similarity, online clustering, and per-cluster EMA preference tracking.
"""
from __future__ import annotations

import array
import asyncio
import logging
import math
import os
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI

log = logging.getLogger("core.wizprompt_memory")

# =============================================================
#  CONFIG
# =============================================================

_DB_PATH = Path(__file__).parent.parent / "data" / "wizprompt_memory.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_EMBEDDING_DIM = 1536
_NEW_CLUSTER_THRESHOLD = 0.25  # cosine distance; >0.25 = new cluster
_EMA_ALPHA_DEFAULT = 0.3
_MAX_EXAMPLES = 5000

# In-memory embedding cache: text -> (timestamp, vector)
_embedding_cache: Dict[str, Tuple[float, List[float]]] = {}
_embedding_cache_lock = threading.Lock()
_EMBEDDING_CACHE_TTL = 300  # 5 minutes
_EMBEDDING_CACHE_MAX = 100

# =============================================================
#  SCHEMA
# =============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_prompt TEXT NOT NULL,
    optimized_prompt TEXT NOT NULL,
    final_prompt TEXT NOT NULL,
    was_edited INTEGER DEFAULT 0,
    embedding BLOB NOT NULL,
    cluster_id INTEGER,
    feedback TEXT CHECK(feedback IN ('up', 'down')),
    preset TEXT,
    model TEXT,
    emotion TEXT,
    created_at REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS clusters (
    cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    centroid BLOB NOT NULL,
    example_count INTEGER DEFAULT 0,
    ema_score REAL DEFAULT 0.5,
    ema_alpha REAL DEFAULT 0.3,
    created_at REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_examples_cluster ON examples(cluster_id);
CREATE INDEX IF NOT EXISTS idx_examples_feedback ON examples(feedback);
CREATE INDEX IF NOT EXISTS idx_examples_created ON examples(created_at);
"""

# =============================================================
#  DB HELPERS
# =============================================================


def _init_db() -> None:
    with sqlite3.connect(str(_DB_PATH)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_init_db()


# =============================================================
#  EMBEDDING SERIALIZATION
# =============================================================


def _embedding_to_blob(vec: List[float]) -> bytes:
    """Pack a float list into compact binary (array of floats)."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _blob_to_embedding(blob: bytes) -> List[float]:
    """Unpack binary blob back into float list."""
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


# =============================================================
#  EMBEDDING GENERATION
# =============================================================

_async_client: Optional[AsyncOpenAI] = None


def _get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
        )
    return _async_client


async def _get_embedding(text: str) -> List[float]:
    """Generate a semantic embedding for text. Cached in memory."""
    # Normalize cache key
    key = text.strip().lower()[:512]

    with _embedding_cache_lock:
        now = time.time()
        entry = _embedding_cache.get(key)
        if entry is not None:
            ts, vec = entry
            if now - ts < _EMBEDDING_CACHE_TTL:
                return vec

    # Try OpenRouter embedding API
    try:
        client = _get_async_client()
        resp = await client.embeddings.create(
            model="openai/text-embedding-3-small",
            input=text[:8000],  # safety cap
        )
        vec = resp.data[0].embedding
    except Exception as e:
        log.warning("OpenRouter embedding failed (%s), falling back to hash embedding", e)
        vec = _hash_embedding(text)

    with _embedding_cache_lock:
        _embedding_cache[key] = (time.time(), vec)
        # LRU eviction
        if len(_embedding_cache) > _EMBEDDING_CACHE_MAX:
            oldest = min(_embedding_cache, key=lambda k: _embedding_cache[k][0])
            del _embedding_cache[oldest]

    return vec


def _hash_embedding(text: str, dim: int = _EMBEDDING_DIM) -> List[float]:
    """Deterministic hash-based fallback embedding."""
    import hashlib

    h = hashlib.sha256(text.lower().encode("utf-8")).digest()
    vec = []
    for i in range(dim):
        byte_val = h[i % len(h)]
        mixed = (byte_val * 31 + i * 17) & 0xFF
        val = (mixed / 255.0) * 2 - 1
        vec.append(round(val, 6))
    return vec


# =============================================================
#  VECTOR MATH
# =============================================================


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cosine_distance(a: List[float], b: List[float]) -> float:
    return 1.0 - _cosine_similarity(a, b)


def _mean_vector(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return [0.0] * _EMBEDDING_DIM
    dim = len(vectors[0])
    sums = [0.0] * dim
    for vec in vectors:
        for i, val in enumerate(vec):
            sums[i] += val
    n = len(vectors)
    return [s / n for s in sums]


# =============================================================
#  CLUSTER MANAGEMENT
# =============================================================


def _list_clusters() -> List[Tuple[int, List[float]]]:
    """Return list of (cluster_id, centroid_vector)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT cluster_id, centroid FROM clusters"
        ).fetchall()
    return [(r["cluster_id"], _blob_to_embedding(r["centroid"])) for r in rows]


def find_nearest_cluster(embedding: List[float]) -> int:
    """Find nearest cluster by cosine similarity. Create new cluster if too far."""
    clusters = _list_clusters()
    if not clusters:
        return _create_cluster(embedding)

    best_id = None
    best_dist = float("inf")
    for cid, centroid in clusters:
        dist = _cosine_distance(embedding, centroid)
        if dist < best_dist:
            best_dist = dist
            best_id = cid

    if best_dist > _NEW_CLUSTER_THRESHOLD:
        return _create_cluster(embedding)
    return best_id


def _create_cluster(embedding: List[float]) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO clusters (centroid, example_count, ema_score, ema_alpha) VALUES (?, 0, 0.5, ?)",
            (_embedding_to_blob(embedding), _EMA_ALPHA_DEFAULT),
        )
        conn.commit()
        return cur.lastrowid


def update_cluster_centroid(cluster_id: int) -> None:
    """Recalculate centroid from all examples in cluster."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT embedding FROM examples WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchall()

    if not rows:
        return

    vectors = [_blob_to_embedding(r["embedding"]) for r in rows]
    centroid = _mean_vector(vectors)
    count = len(vectors)

    with _conn() as conn:
        conn.execute(
            "UPDATE clusters SET centroid = ?, example_count = ? WHERE cluster_id = ?",
            (_embedding_to_blob(centroid), count, cluster_id),
        )
        conn.commit()


def update_cluster_ema(cluster_id: int, feedback: str) -> None:
    """Update EMA score for a cluster based on feedback."""
    signal = 1.0 if feedback == "up" else 0.0
    with _conn() as conn:
        row = conn.execute(
            "SELECT ema_score, ema_alpha FROM clusters WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchone()
        if not row:
            return
        old_ema, alpha = row["ema_score"], row["ema_alpha"]
        new_ema = alpha * signal + (1.0 - alpha) * old_ema
        conn.execute(
            "UPDATE clusters SET ema_score = ? WHERE cluster_id = ?",
            (new_ema, cluster_id),
        )
        conn.commit()
        log.info("Cluster %d EMA: %.3f -> %.3f", cluster_id, old_ema, new_ema)


def get_cluster_style_bias(cluster_id: int) -> Optional[str]:
    """Return a style directive if EMA is extreme."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT ema_score FROM clusters WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchone()
    if not row:
        return None
    ema = row["ema_score"]
    if ema > 0.8:
        return "The user prefers detailed, elaborate prompts with extensive context, examples, and thorough explanations."
    if ema < 0.2:
        return "The user prefers concise, minimal prompts — strip all fluff and get straight to the point."
    return None


# =============================================================
#  EXAMPLE STORAGE
# =============================================================


def store_example(
    original_prompt: str,
    optimized_prompt: str,
    final_prompt: str,
    embedding: List[float],
    cluster_id: int,
    was_edited: bool = False,
    feedback: Optional[str] = None,
    preset: Optional[str] = None,
    model: Optional[str] = None,
    emotion: Optional[str] = None,
) -> int:
    """Store a new example. Returns the example ID."""
    blob = _embedding_to_blob(embedding)
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO examples
            (original_prompt, optimized_prompt, final_prompt, was_edited,
             embedding, cluster_id, feedback, preset, model, emotion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                original_prompt,
                optimized_prompt,
                final_prompt,
                1 if was_edited else 0,
                blob,
                cluster_id,
                feedback,
                preset,
                model,
                emotion,
            ),
        )
        conn.commit()
        example_id = cur.lastrowid

    # Recalculate centroid for the cluster
    update_cluster_centroid(cluster_id)

    # Prune old examples if over limit
    _prune_old_examples()

    return example_id


def _prune_old_examples() -> None:
    """Keep only the most recent _MAX_EXAMPLES entries."""
    with _conn() as conn:
        count_row = conn.execute("SELECT COUNT(*) FROM examples").fetchone()
        count = count_row[0] if count_row else 0
        if count > _MAX_EXAMPLES:
            to_delete = count - _MAX_EXAMPLES
            conn.execute(
                "DELETE FROM examples WHERE id IN (SELECT id FROM examples ORDER BY created_at ASC LIMIT ?)",
                (to_delete,),
            )
            conn.commit()
            log.info("Pruned %d old examples", to_delete)


def update_example_feedback(example_id: int, feedback: str) -> bool:
    """Update feedback on an existing example. Also update cluster EMA."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT cluster_id FROM examples WHERE id = ?",
            (example_id,),
        ).fetchone()
        if not row:
            return False
        cluster_id = row["cluster_id"]
        conn.execute(
            "UPDATE examples SET feedback = ? WHERE id = ?",
            (feedback, example_id),
        )
        conn.commit()

    update_cluster_ema(cluster_id, feedback)
    return True


# =============================================================
#  RETRIEVAL
# =============================================================


def get_similar_examples(
    embedding: List[float],
    cluster_id: Optional[int] = None,
    preset: Optional[str] = None,
    limit: int = 3,
) -> List[Dict]:
    """Retrieve top-N similar examples filtered to thumbs-up."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, original_prompt, optimized_prompt, final_prompt,
                   was_edited, embedding, cluster_id, feedback, preset, emotion
            FROM examples
            WHERE feedback = 'up'
            ORDER BY created_at DESC
            """
        ).fetchall()

    if not rows:
        return []

    scored = []
    for row in rows:
        vec = _blob_to_embedding(row["embedding"])
        sim = _cosine_similarity(embedding, vec)
        # Boost same cluster (+0.1) and same preset (+0.05)
        if cluster_id is not None and row["cluster_id"] == cluster_id:
            sim += 0.1
        if preset and row["preset"] == preset:
            sim += 0.05
        scored.append((sim, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return [
        {
            "id": row["id"],
            "original": row["original_prompt"],
            "optimized": row["optimized_prompt"],
            "final": row["final_prompt"],
            "was_edited": bool(row["was_edited"]),
            "similarity": round(sim, 4),
            "cluster_id": row["cluster_id"],
            "preset": row["preset"],
            "emotion": row["emotion"],
        }
        for sim, row in top
    ]


def get_example_count() -> int:
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM examples").fetchone()
        return row[0] if row else 0


def get_cluster_stats() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT cluster_id, example_count, ema_score, ema_alpha, created_at
            FROM clusters
            ORDER BY example_count DESC
            """
        ).fetchall()
    return [
        {
            "cluster_id": r["cluster_id"],
            "example_count": r["example_count"],
            "ema_score": round(r["ema_score"], 3),
            "ema_alpha": r["ema_alpha"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# =============================================================
#  HIGH-LEVEL API (async)
# =============================================================


async def remember_optimization(
    original_prompt: str,
    optimized_prompt: str,
    final_prompt: str,
    was_edited: bool = False,
    feedback: Optional[str] = None,
    preset: Optional[str] = None,
    model: Optional[str] = None,
    emotion: Optional[str] = None,
) -> Dict:
    """Full pipeline: embed, cluster, store. Returns metadata."""
    embedding = await _get_embedding(original_prompt)
    cluster_id = find_nearest_cluster(embedding)
    example_id = store_example(
        original_prompt=original_prompt,
        optimized_prompt=optimized_prompt,
        final_prompt=final_prompt,
        embedding=embedding,
        cluster_id=cluster_id,
        was_edited=was_edited,
        feedback=feedback,
        preset=preset,
        model=model,
        emotion=emotion,
    )
    return {
        "example_id": example_id,
        "cluster_id": cluster_id,
        "embedding_dim": len(embedding),
    }


async def retrieve_examples_for_prompt(
    prompt: str,
    preset: Optional[str] = None,
    limit: int = 3,
) -> Tuple[List[Dict], Optional[int], Optional[str]]:
    """Get examples, cluster id, and style bias for a given prompt."""
    embedding = await _get_embedding(prompt)
    cluster_id = find_nearest_cluster(embedding)
    examples = get_similar_examples(embedding, cluster_id, preset, limit)
    bias = get_cluster_style_bias(cluster_id)
    return examples, cluster_id, bias


def format_few_shot_block(examples: List[Dict]) -> str:
    """Format retrieved examples as a few-shot prompt block."""
    if not examples:
        return ""

    lines = [
        "Here are examples of prompt optimizations you previously produced that the user accepted:",
        "",
    ]
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i}:")
        lines.append(f"Original: {ex['original']}")
        lines.append(f"Optimized: {ex['final']}")
        lines.append("")
    lines.append("Please follow the same style and level of detail as these examples.")
    lines.append("")
    return "\n".join(lines)
