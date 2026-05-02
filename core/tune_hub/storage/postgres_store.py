"""PostgreSQL-backed storage implementation for Pro/Power tiers."""

from __future__ import annotations

import json
from typing import List, Optional

from .abstract import TuneStorage
from ..base import LearnedModel


class PostgresTuneStore(TuneStorage):
    """
    Pro/Power tier: PostgreSQL storage for tunes with full versioning.

    Expects a SQLAlchemy-like session or raw psycopg2 connection pool.
    For MVP, uses a simple connection-string approach.
    """

    def __init__(self, dsn: str = "postgresql://localhost/wiztant") -> None:
        self.dsn = dsn
        self._conn = None
        self._init_db()

    def _get_conn(self):
        """Lazy import psycopg2 to avoid hard dependency."""
        try:
            import psycopg2
            if self._conn is None or self._conn.closed:
                self._conn = psycopg2.connect(self.dsn)
            return self._conn
        except ImportError:
            raise RuntimeError(
                "psycopg2 is required for PostgresTuneStore. "
                "Install with: pip install psycopg2-binary"
            )

    def _init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS user_tunes (
            tune_id VARCHAR(128) PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            feature_name VARCHAR(32) NOT NULL,
            task_signature VARCHAR(64) NOT NULL,
            current_version INTEGER NOT NULL DEFAULT 1,
            complexity VARCHAR(16) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
            quality_score DECIMAL(4,3) CHECK (quality_score BETWEEN 0.0 AND 1.0),
            reusable BOOLEAN DEFAULT TRUE,
            encrypted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, feature_name, task_signature, current_version)
        );
        CREATE INDEX IF NOT EXISTS idx_user_tunes_lookup
            ON user_tunes(user_id, feature_name, task_signature, status);

        CREATE TABLE IF NOT EXISTS tune_versions (
            tune_id VARCHAR(128) NOT NULL REFERENCES user_tunes(tune_id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            payload JSONB NOT NULL,
            quality_score DECIMAL(4,3),
            parent_version INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            metadata JSONB DEFAULT '{}',
            PRIMARY KEY(tune_id, version)
        );
        CREATE INDEX IF NOT EXISTS idx_tune_versions_latest
            ON tune_versions(tune_id, version DESC);
        """
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()

    def store_tune(self, user_id: str, model: LearnedModel) -> bool:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_tunes
                (tune_id, user_id, feature_name, task_signature,
                 current_version, complexity, status, quality_score, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, feature_name, task_signature, current_version)
                DO UPDATE SET
                    current_version = EXCLUDED.current_version,
                    status = EXCLUDED.status,
                    quality_score = EXCLUDED.quality_score,
                    updated_at = NOW()
                """,
                (
                    model.tune_id,
                    user_id,
                    model.feature_name,
                    model.task_signature,
                    model.version,
                    model.complexity.name,
                    model.status.name,
                    model.quality_score,
                ),
            )
            cur.execute(
                """
                INSERT INTO tune_versions
                (tune_id, version, payload, quality_score, parent_version, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tune_id, version) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    quality_score = EXCLUDED.quality_score,
                    metadata = EXCLUDED.metadata
                """,
                (
                    model.tune_id,
                    model.version,
                    json.dumps(model.payload),
                    model.quality_score,
                    model.parent_version,
                    json.dumps(model.metadata),
                ),
            )
        conn.commit()
        return True

    def get_tune(
        self, user_id: str, feature_name: str, task_signature: str
    ) -> Optional[LearnedModel]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tune_id, feature_name, task_signature,
                       payload, quality_score, complexity, status,
                       current_version, parent_version, created_at, metadata
                FROM user_tunes
                WHERE user_id = %s AND feature_name = %s AND task_signature = %s
                ORDER BY current_version DESC
                LIMIT 1
                """,
                (user_id, feature_name, task_signature),
            )
            row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def get_tune_by_id(self, user_id: str, tune_id: str) -> Optional[LearnedModel]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tune_id, feature_name, task_signature,
                       payload, quality_score, complexity, status,
                       current_version, parent_version, created_at, metadata
                FROM user_tunes
                WHERE user_id = %s AND tune_id = %s
                """,
                (user_id, tune_id),
            )
            row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def get_tune_version(
        self, user_id: str, tune_id: str, version: int
    ) -> Optional[LearnedModel]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload, quality_score
                FROM tune_versions
                WHERE tune_id = %s AND version = %s
                """,
                (tune_id, version),
            )
            row = cur.fetchone()
        if not row:
            return None
        base = self.get_tune_by_id(user_id, tune_id)
        if not base:
            return None
        return LearnedModel(
            tune_id=base.tune_id,
            feature_name=base.feature_name,
            task_signature=base.task_signature,
            payload=row[0] if isinstance(row[0], dict) else json.loads(row[0]),
            quality_score=row[1],
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
        conn = self._get_conn()
        query = """
            SELECT tune_id, feature_name, task_signature,
                   payload, quality_score, complexity, status,
                   current_version, parent_version, created_at, metadata
            FROM user_tunes
            WHERE user_id = %s
        """
        params: tuple = (user_id,)
        if feature_name:
            query += " AND feature_name = %s"
            params = (user_id, feature_name)
        query += " ORDER BY updated_at DESC"
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._row_to_model(r) for r in rows if r]

    def delete_tune(self, user_id: str, tune_id: str) -> bool:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_tunes WHERE user_id = %s AND tune_id = %s",
                (user_id, tune_id),
            )
        conn.commit()
        return True

    def count_tunes(self, user_id: str, feature_name: Optional[str] = None) -> int:
        conn = self._get_conn()
        query = "SELECT COUNT(*) FROM user_tunes WHERE user_id = %s"
        params: tuple = (user_id,)
        if feature_name:
            query += " AND feature_name = %s"
            params = (user_id, feature_name)
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        return row[0] if row else 0

    def _row_to_model(self, row: tuple) -> LearnedModel:
        return LearnedModel.from_storage_format(
            {
                "tune_id": row[0],
                "feature_name": row[1],
                "task_signature": row[2],
                "payload": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                "quality_score": row[4],
                "complexity": row[5],
                "status": row[6],
                "version": row[7],
                "parent_version": row[8],
                "created_at": row[9].isoformat() if hasattr(row[9], "isoformat") else str(row[9]),
                "metadata": row[10] if isinstance(row[10], dict) else json.loads(row[10] or "{}"),
            }
        )
