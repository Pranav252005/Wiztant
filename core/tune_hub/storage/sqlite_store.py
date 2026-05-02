"""SQLite-backed storage implementation for Free tier."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from ..base import LearnedModel, TuneStatus
from .abstract import TuneStorage


class SQLiteTuneStore(TuneStorage):
    """Free tier: local SQLite storage for tunes."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS local_tunes (
        tune_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        task_signature TEXT NOT NULL,
        payload TEXT NOT NULL,
        quality_score REAL,
        complexity TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        version INTEGER NOT NULL DEFAULT 1,
        parent_version INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, feature_name, task_signature)
    );
    CREATE INDEX IF NOT EXISTS idx_local_tunes_lookup
        ON local_tunes(user_id, feature_name, task_signature, status);
    CREATE TABLE IF NOT EXISTS tune_versions (
        tune_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        payload TEXT NOT NULL,
        quality_score REAL,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY(tune_id, version)
    );
    """

    def __init__(self, db_path: str = "data/tune_hub.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def store_tune(self, user_id: str, model: LearnedModel) -> bool:
        with self._conn() as conn:
            # Insert or replace current tune
            conn.execute(
                """
                INSERT INTO local_tunes
                (tune_id, user_id, feature_name, task_signature, payload,
                 quality_score, complexity, status, version, parent_version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id, feature_name, task_signature) DO UPDATE SET
                    tune_id=excluded.tune_id,
                    payload=excluded.payload,
                    quality_score=excluded.quality_score,
                    complexity=excluded.complexity,
                    status=excluded.status,
                    version=excluded.version,
                    parent_version=excluded.parent_version,
                    updated_at=datetime('now')
                """,
                (
                    model.tune_id,
                    user_id,
                    model.feature_name,
                    model.task_signature,
                    json.dumps(model.payload),
                    model.quality_score,
                    model.complexity.name,
                    model.status.name,
                    model.version,
                    model.parent_version,
                ),
            )
            # Store version history
            conn.execute(
                """
                INSERT OR REPLACE INTO tune_versions
                (tune_id, version, payload, quality_score)
                VALUES (?, ?, ?, ?)
                """,
                (
                    model.tune_id,
                    model.version,
                    json.dumps(model.payload),
                    model.quality_score,
                ),
            )
            conn.commit()
        return True

    def get_tune(
        self, user_id: str, feature_name: str, task_signature: str
    ) -> Optional[LearnedModel]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT tune_id, feature_name, task_signature, payload,
                       quality_score, complexity, status, version,
                       parent_version, created_at
                FROM local_tunes
                WHERE user_id = ? AND feature_name = ? AND task_signature = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id, feature_name, task_signature),
            ).fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    def get_tune_by_id(self, user_id: str, tune_id: str) -> Optional[LearnedModel]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT tune_id, feature_name, task_signature, payload,
                       quality_score, complexity, status, version,
                       parent_version, created_at
                FROM local_tunes
                WHERE user_id = ? AND tune_id = ?
                """,
                (user_id, tune_id),
            ).fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    def get_tune_version(
        self, user_id: str, tune_id: str, version: int
    ) -> Optional[LearnedModel]:
        # First get the base tune to know feature_name / task_signature
        base = self.get_tune_by_id(user_id, tune_id)
        if not base:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT payload, quality_score
                FROM tune_versions
                WHERE tune_id = ? AND version = ?
                """,
                (tune_id, version),
            ).fetchone()
        if not row:
            return None
        payload, quality_score = row
        return LearnedModel(
            tune_id=base.tune_id,
            feature_name=base.feature_name,
            task_signature=base.task_signature,
            payload=json.loads(payload),
            quality_score=quality_score,
            complexity=base.complexity,
            status=base.status,
            version=version,
            parent_version=base.parent_version,
            created_at=base.created_at,
            metadata=base.metadata,
        )

    def list_tunes(
        self, user_id: str, feature_name: Optional[str] = None
    ) -> List[LearnedModel]:
        query = """
            SELECT tune_id, feature_name, task_signature, payload,
                   quality_score, complexity, status, version,
                   parent_version, created_at
            FROM local_tunes
            WHERE user_id = ?
        """
        params: tuple = (user_id,)
        if feature_name:
            query += " AND feature_name = ?"
            params = (user_id, feature_name)
        query += " ORDER BY updated_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_model(r) for r in rows]

    def delete_tune(self, user_id: str, tune_id: str) -> bool:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM local_tunes WHERE user_id = ? AND tune_id = ?",
                (user_id, tune_id),
            )
            conn.execute(
                "DELETE FROM tune_versions WHERE tune_id = ?",
                (tune_id,),
            )
            conn.commit()
        return True

    def count_tunes(self, user_id: str, feature_name: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM local_tunes WHERE user_id = ?"
        params: tuple = (user_id,)
        if feature_name:
            query += " AND feature_name = ?"
            params = (user_id, feature_name)
        with self._conn() as conn:
            row = conn.execute(query, params).fetchone()
        return row[0] if row else 0

    def _row_to_model(self, row: sqlite3.Row) -> LearnedModel:
        from ..base import ComplexityLevel, TuneStatus

        return LearnedModel.from_storage_format(
            {
                "tune_id": row[0],
                "feature_name": row[1],
                "task_signature": row[2],
                "payload": json.loads(row[3]),
                "quality_score": row[4],
                "complexity": row[5],
                "status": row[6],
                "version": row[7],
                "parent_version": row[8],
                "created_at": row[9],
                "metadata": {},
            }
        )
