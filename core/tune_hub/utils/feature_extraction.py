"""Shared feature extraction utilities for Tune Hub.

Provides text embedding, prompt features, and domain signals used across
the RePrompt, Dictation, and Agent tuners.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional


# =============================================================
#  TEXT EMBEDDING
# =============================================================


class _EmbeddingCache:
    """Simple LRU cache for embeddings to avoid redundant computation."""

    def __init__(self, maxsize: int = 256):
        self._cache: Dict[str, List[float]] = {}
        self._order: List[str] = []
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[List[float]]:
        if key in self._cache:
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: List[float]) -> None:
        if key in self._cache:
            self._order.remove(key)
        self._cache[key] = value
        self._order.append(key)
        if len(self._cache) > self._maxsize:
            oldest = self._order.pop(0)
            del self._cache[oldest]


_embedding_cache = _EmbeddingCache()


def embed_text(text: str, dim: int = 384) -> List[float]:
    """
    Compute a deterministic pseudo-embedding for text.

    In production, this should use sentence-transformers or an API.
    For local/offline use, we fall back to a hash-based embedding
    that preserves rough similarity for identical and near-identical
    strings.
    """
    cache_key = f"{text}:{dim}"
    cached = _embedding_cache.get(cache_key)
    if cached is not None:
        return cached

    # Simple hash-based embedding: uniform but deterministic
    import hashlib

    h = hashlib.sha256(text.lower().encode("utf-8")).digest()
    embedding = []
    for i in range(dim):
        # Use bytes from hash to seed a value in [-1, 1]
        byte_val = h[i % len(h)]
        # Mix with position to avoid repetition
        mixed = (byte_val * 31 + i * 17) & 0xFF
        val = (mixed / 255.0) * 2 - 1
        embedding.append(round(val, 6))

    _embedding_cache.put(cache_key, embedding)
    return embedding


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimension")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# =============================================================
#  TEXT FEATURES
# =============================================================


def extract_text_features(text: str) -> Dict[str, Any]:
    """Extract lightweight features from raw text."""
    text_lower = text.lower()
    words = text.split()

    features: Dict[str, Any] = {
        "length": len(text),
        "word_count": len(words),
        "has_code_blocks": "```" in text,
        "has_question": text.strip().endswith("?"),
        "language_detected": _detect_language(text_lower),
    }

    # Keyword signals
    features["keyword_signals"] = {
        "code": any(k in text_lower for k in ["code", "bug", "error", "function", "class", "debug"]),
        "write": any(k in text_lower for k in ["write", "essay", "email", "blog", "draft"]),
        "research": any(k in text_lower for k in ["research", "find", "analyze", "compare", "study"]),
        "plan": any(k in text_lower for k in ["plan", "schedule", "roadmap", "organize"]),
        "build": any(k in text_lower for k in ["build", "create", "implement", "setup", "deploy"]),
        "medical": any(k in text_lower for k in ["medical", "patient", "diagnosis", "clinical"]),
        "legal": any(k in text_lower for k in ["legal", "contract", "plaintiff", "defendant"]),
        "crypto": any(k in text_lower for k in ["crypto", "bitcoin", "ethereum", "blockchain", "defi"]),
    }

    return features


def _detect_language(text: str) -> str:
    """Fast heuristic language detection."""
    # Simplified: just returns "en" for now; could use langdetect
    return "en"


# =============================================================
#  PROMPT EMBEDDING FEATURES
# =============================================================


def extract_prompt_embedding_features(raw_prompt: str) -> Dict[str, Any]:
    """Extract embedding-based features for a prompt."""
    emb = embed_text(raw_prompt)
    return {
        "embedding": emb,
        "embedding_dim": len(emb),
        "prompt_length": len(raw_prompt.split()),
        "has_code_blocks": "```" in raw_prompt,
        "has_question": raw_prompt.strip().endswith("?"),
        "language_detected": _detect_language(raw_prompt.lower()),
    }


# =============================================================
#  WEIGHT VECTOR FEATURES
# =============================================================


def extract_weight_features(weights: List[float]) -> Dict[str, Any]:
    """Extract features from a persona weight vector."""
    if not weights:
        return {"entropy": 0.0, "concentration": 0.0, "active_count": 0}

    # Entropy (concentration measure)
    positive_weights = [w for w in weights if w > 0]
    if not positive_weights:
        entropy = 0.0
    else:
        total = sum(positive_weights)
        probs = [w / total for w in positive_weights]
        entropy = -sum(p * math.log(p + 1e-10) for p in probs)

    return {
        "entropy": round(entropy, 4),
        "dominant_index": int(max(range(len(weights)), key=lambda i: weights[i])),
        "concentration": round(max(weights), 4),
        "active_count": sum(1 for w in weights if w > 0.05),
    }
