"""Tests for Tune Hub storage layer."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.base import ComplexityLevel, LearnedModel, TuneStatus
from core.tune_hub.storage.sqlite_store import SQLiteTuneStore


class TestSQLiteTuneStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = SQLiteTuneStore(str(Path(self.tmpdir) / "tunes.db"))
        self.model = LearnedModel(
            tune_id="t1",
            feature_name="reprompt",
            task_signature="coding_tasks",
            payload={"personas": {"debug": 0.8}},
            quality_score=0.9,
            complexity=ComplexityLevel.MEDIUM,
            status=TuneStatus.DEPLOYED,
        )

    def test_store_and_retrieve(self):
        assert self.store.store_tune("u1", self.model)
        retrieved = self.store.get_tune("u1", "reprompt", "coding_tasks")
        assert retrieved is not None
        assert retrieved.tune_id == "t1"
        assert retrieved.quality_score == 0.9

    def test_get_by_id(self):
        self.store.store_tune("u1", self.model)
        found = self.store.get_tune_by_id("u1", "t1")
        assert found is not None
        assert found.feature_name == "reprompt"

    def test_list_tunes(self):
        self.store.store_tune("u1", self.model)
        tunes = self.store.list_tunes("u1")
        assert len(tunes) == 1

    def test_list_tunes_by_feature(self):
        self.store.store_tune("u1", self.model)
        tunes = self.store.list_tunes("u1", feature_name="reprompt")
        assert len(tunes) == 1
        tunes = self.store.list_tunes("u1", feature_name="dictation")
        assert len(tunes) == 0

    def test_delete_tune(self):
        self.store.store_tune("u1", self.model)
        assert self.store.delete_tune("u1", "t1")
        assert self.store.get_tune_by_id("u1", "t1") is None

    def test_count_tunes(self):
        assert self.store.count_tunes("u1") == 0
        self.store.store_tune("u1", self.model)
        assert self.store.count_tunes("u1") == 1

    def test_versioning(self):
        self.store.store_tune("u1", self.model)
        self.model.version = 2
        self.model.payload = {"personas": {"debug": 0.9}}
        self.store.store_tune("u1", self.model)

        v1 = self.store.get_tune_version("u1", "t1", 1)
        assert v1 is not None
        assert v1.payload["personas"]["debug"] == 0.8

        v2 = self.store.get_tune_version("u1", "t1", 2)
        assert v2 is not None
        assert v2.payload["personas"]["debug"] == 0.9


class TestEncryption:
    def test_roundtrip(self):
        from core.tune_hub.storage.encryption import (
            PowerTierEncryption,
            derive_key_from_password,
        )

        key = derive_key_from_password("user_42", "secret_password")
        enc = PowerTierEncryption(lambda uid: key)

        payload = {"personas": {"debug": 0.8}, "secret": "api_key_123"}
        blob = enc.encrypt("user_42", "tune_1", payload)
        decrypted = enc.decrypt("user_42", "tune_1", blob)
        assert decrypted == payload

    def test_different_users_different_keys(self):
        from core.tune_hub.storage.encryption import (
            PowerTierEncryption,
            derive_key_from_password,
        )

        key_a = derive_key_from_password("user_a", "pass_a")
        key_b = derive_key_from_password("user_b", "pass_b")
        enc_a = PowerTierEncryption(lambda uid: key_a if uid == "user_a" else key_b)

        payload = {"data": "sensitive"}
        blob = enc_a.encrypt("user_a", "tune_x", payload)

        # Same user can decrypt
        assert enc_a.decrypt("user_a", "tune_x", blob) == payload

        # Different key should fail
        enc_wrong = PowerTierEncryption(lambda uid: derive_key_from_password(uid, "wrong"))
        try:
            enc_wrong.decrypt("user_a", "tune_x", blob)
            assert False, "Should have failed"
        except Exception:
            pass
