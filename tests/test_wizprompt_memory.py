"""Tests for core/wizprompt_memory.py — few-shot memory store."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import core.wizprompt_memory as mem


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Use a temporary SQLite DB for each test."""
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr(mem, "_DB_PATH", db_path)
    monkeypatch.setattr(mem, "_embedding_cache", {})
    # Re-init schema on new path
    mem._init_db()
    yield


@pytest.fixture
def fake_embedding():
    """Return a deterministic fake embedding vector."""
    def _make(seed: float = 1.0):
        dim = mem._EMBEDDING_DIM
        import math
        return [math.sin(seed + i * 0.1) for i in range(dim)]
    return _make


class TestVectorMath:
    def test_cosine_similarity_identical(self, fake_embedding):
        vec = fake_embedding(1.0)
        assert mem._cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_opposite(self, fake_embedding):
        vec = fake_embedding(1.0)
        neg = [-x for x in vec]
        assert mem._cosine_similarity(vec, neg) == pytest.approx(-1.0, abs=1e-6)

    def test_cosine_distance(self, fake_embedding):
        vec = fake_embedding(1.0)
        assert mem._cosine_distance(vec, vec) == pytest.approx(0.0, abs=1e-6)

    def test_mean_vector(self, fake_embedding):
        a = fake_embedding(1.0)
        b = fake_embedding(2.0)
        mean = mem._mean_vector([a, b])
        assert len(mean) == len(a)
        assert mean[0] == pytest.approx((a[0] + b[0]) / 2, abs=1e-6)

    def test_embedding_serialization(self, fake_embedding):
        vec = fake_embedding(1.0)[:10]
        blob = mem._embedding_to_blob(vec)
        restored = mem._blob_to_embedding(blob)
        assert restored == pytest.approx(vec, abs=1e-5)


class TestClusterManagement:
    def test_create_first_cluster(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        assert cid is not None
        assert cid > 0

    def test_find_nearest_cluster_creates_new_when_empty(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem.find_nearest_cluster(vec)
        assert cid > 0

    def test_find_nearest_cluster_assigns_nearby(self, fake_embedding):
        vec1 = fake_embedding(1.0)
        cid1 = mem.find_nearest_cluster(vec1)
        # Very similar vector should join same cluster
        vec2 = [v + 0.001 for v in vec1]
        cid2 = mem.find_nearest_cluster(vec2)
        assert cid2 == cid1

    def test_find_nearest_cluster_creates_new_when_far(self, fake_embedding):
        vec1 = fake_embedding(1.0)
        cid1 = mem.find_nearest_cluster(vec1)
        # Very different vector should create new cluster
        vec2 = fake_embedding(10.0)
        cid2 = mem.find_nearest_cluster(vec2)
        assert cid2 != cid1

    def test_update_cluster_centroid(self, fake_embedding):
        vec1 = fake_embedding(1.0)
        cid = mem._create_cluster(vec1)
        vec2 = fake_embedding(2.0)
        mem.store_example(
            original_prompt="test1",
            optimized_prompt="opt1",
            final_prompt="fin1",
            embedding=vec1,
            cluster_id=cid,
            feedback="up",
        )
        mem.store_example(
            original_prompt="test2",
            optimized_prompt="opt2",
            final_prompt="fin2",
            embedding=vec2,
            cluster_id=cid,
            feedback="up",
        )
        mem.update_cluster_centroid(cid)
        # Centroid should be roughly mean of vec1 and vec2
        with mem._conn() as conn:
            row = conn.execute(
                "SELECT centroid FROM clusters WHERE cluster_id = ?", (cid,)
            ).fetchone()
        centroid = mem._blob_to_embedding(row["centroid"])
        expected = mem._mean_vector([vec1, vec2])
        assert centroid[0] == pytest.approx(expected[0], abs=1e-5)


class TestEMA:
    def test_ema_up(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        mem.update_cluster_ema(cid, "up")
        with mem._conn() as conn:
            row = conn.execute(
                "SELECT ema_score FROM clusters WHERE cluster_id = ?", (cid,)
            ).fetchone()
        # ema = 0.3 * 1.0 + 0.7 * 0.5 = 0.65
        assert row["ema_score"] == pytest.approx(0.65, abs=1e-6)

    def test_ema_down(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        mem.update_cluster_ema(cid, "down")
        with mem._conn() as conn:
            row = conn.execute(
                "SELECT ema_score FROM clusters WHERE cluster_id = ?", (cid,)
            ).fetchone()
        # ema = 0.3 * 0.0 + 0.7 * 0.5 = 0.35
        assert row["ema_score"] == pytest.approx(0.35, abs=1e-6)

    def test_ema_multiple_updates(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        mem.update_cluster_ema(cid, "up")
        mem.update_cluster_ema(cid, "up")
        with mem._conn() as conn:
            row = conn.execute(
                "SELECT ema_score FROM clusters WHERE cluster_id = ?", (cid,)
            ).fetchone()
        # After 2 ups: 0.65, then 0.3*1 + 0.7*0.65 = 0.755
        assert row["ema_score"] == pytest.approx(0.755, abs=1e-6)

    def test_cluster_style_bias_high(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        # Force high EMA
        with mem._conn() as conn:
            conn.execute(
                "UPDATE clusters SET ema_score = 0.9 WHERE cluster_id = ?", (cid,)
            )
            conn.commit()
        bias = mem.get_cluster_style_bias(cid)
        assert bias is not None
        assert "detailed" in bias.lower()

    def test_cluster_style_bias_low(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        with mem._conn() as conn:
            conn.execute(
                "UPDATE clusters SET ema_score = 0.1 WHERE cluster_id = ?", (cid,)
            )
            conn.commit()
        bias = mem.get_cluster_style_bias(cid)
        assert bias is not None
        assert "concise" in bias.lower()

    def test_cluster_style_bias_mid(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem._create_cluster(vec)
        bias = mem.get_cluster_style_bias(cid)
        assert bias is None


class TestExampleStorage:
    def test_store_and_retrieve(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem.find_nearest_cluster(vec)
        eid = mem.store_example(
            original_prompt="Write a poem",
            optimized_prompt="You are a poet...",
            final_prompt="You are a poet... (edited)",
            embedding=vec,
            cluster_id=cid,
            was_edited=True,
            feedback="up",
            preset="general_polish",
            model="test-model",
            emotion="joy",
        )
        assert eid > 0
        assert mem.get_example_count() == 1

    def test_retrieve_filters_to_up_only(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem.find_nearest_cluster(vec)
        mem.store_example(
            original_prompt="A",
            optimized_prompt="B",
            final_prompt="B",
            embedding=vec,
            cluster_id=cid,
            feedback="up",
        )
        mem.store_example(
            original_prompt="C",
            optimized_prompt="D",
            final_prompt="D",
            embedding=vec,
            cluster_id=cid,
            feedback="down",
        )
        examples = mem.get_similar_examples(vec, cluster_id=cid, limit=10)
        assert len(examples) == 1
        assert examples[0]["original"] == "A"

    def test_retrieve_orders_by_similarity(self, fake_embedding):
        vec_a = fake_embedding(1.0)
        vec_b = fake_embedding(2.0)
        cid = mem.find_nearest_cluster(vec_a)
        mem.store_example(
            original_prompt="near",
            optimized_prompt="opt",
            final_prompt="opt",
            embedding=vec_a,
            cluster_id=cid,
            feedback="up",
        )
        mem.store_example(
            original_prompt="far",
            optimized_prompt="opt",
            final_prompt="opt",
            embedding=vec_b,
            cluster_id=cid,
            feedback="up",
        )
        examples = mem.get_similar_examples(vec_a, cluster_id=cid, limit=10)
        assert examples[0]["original"] == "near"

    def test_update_feedback(self, fake_embedding):
        vec = fake_embedding(1.0)
        cid = mem.find_nearest_cluster(vec)
        eid = mem.store_example(
            original_prompt="X",
            optimized_prompt="Y",
            final_prompt="Y",
            embedding=vec,
            cluster_id=cid,
            feedback=None,
        )
        ok = mem.update_example_feedback(eid, "up")
        assert ok is True
        with mem._conn() as conn:
            row = conn.execute(
                "SELECT feedback FROM examples WHERE id = ?", (eid,)
            ).fetchone()
        assert row["feedback"] == "up"

    def test_format_few_shot_block(self):
        examples = [
            {
                "id": 1,
                "original": "Write code",
                "final": "You are a senior engineer...",
            },
            {
                "id": 2,
                "original": "Explain AI",
                "final": "You are an expert educator...",
            },
        ]
        block = mem.format_few_shot_block(examples)
        assert "Example 1:" in block
        assert "Example 2:" in block
        assert "Write code" in block
        assert "Explain AI" in block

    def test_format_few_shot_block_empty(self):
        assert mem.format_few_shot_block([]) == ""

    def test_prune_old_examples(self, fake_embedding):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mem, "_MAX_EXAMPLES", 3)
        vec = fake_embedding(1.0)
        cid = mem.find_nearest_cluster(vec)
        for i in range(5):
            mem.store_example(
                original_prompt=f"prompt_{i}",
                optimized_prompt="opt",
                final_prompt="opt",
                embedding=vec,
                cluster_id=cid,
                feedback="up",
            )
        assert mem.get_example_count() == 3
        monkeypatch.undo()


class TestHashEmbedding:
    def test_deterministic(self):
        a = mem._hash_embedding("hello world")
        b = mem._hash_embedding("hello world")
        assert a == b

    def test_different_texts(self):
        a = mem._hash_embedding("hello world")
        b = mem._hash_embedding("goodbye world")
        assert a != b

    def test_dimension(self):
        vec = mem._hash_embedding("test")
        assert len(vec) == mem._EMBEDDING_DIM
