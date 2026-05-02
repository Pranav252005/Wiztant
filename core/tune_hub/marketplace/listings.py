"""Marketplace listing storage and operations for Tune Hub."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MarketplaceListing:
    """A tune listing in the marketplace."""

    listing_id: str
    tune_id: str
    seller_id: str
    title: str
    description: str = ""
    price_credits: int = 0
    category: str = ""
    tags: List[str] = field(default_factory=list)
    rating: float = 0.0
    downloads: int = 0
    is_featured: bool = False
    created_at: str = ""
    updated_at: str = ""
    pii_scan_result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "tune_id": self.tune_id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "price_credits": self.price_credits,
            "category": self.category,
            "tags": self.tags,
            "rating": self.rating,
            "downloads": self.downloads,
            "is_featured": self.is_featured,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pii_scan_result": self.pii_scan_result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MarketplaceListing:
        return cls(
            listing_id=data["listing_id"],
            tune_id=data["tune_id"],
            seller_id=data["seller_id"],
            title=data["title"],
            description=data.get("description", ""),
            price_credits=data.get("price_credits", 0),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            rating=data.get("rating", 0.0),
            downloads=data.get("downloads", 0),
            is_featured=data.get("is_featured", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            pii_scan_result=data.get("pii_scan_result", {}),
        )


class ListingStore:
    """SQLite-backed store for marketplace listings."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS marketplace_listings (
        listing_id TEXT PRIMARY KEY,
        tune_id TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        price_credits INTEGER NOT NULL DEFAULT 0,
        category TEXT,
        tags TEXT,
        rating REAL DEFAULT 0.0,
        downloads INTEGER DEFAULT 0,
        is_featured INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        pii_scan_result TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_listings_category
        ON marketplace_listings(category);
    CREATE INDEX IF NOT EXISTS idx_listings_featured
        ON marketplace_listings(is_featured);
    CREATE INDEX IF NOT EXISTS idx_listings_rating
        ON marketplace_listings(rating DESC);
    """

    def __init__(self, db_path: str = "data/marketplace.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def create_listing(self, listing: MarketplaceListing) -> bool:
        now = datetime.utcnow().isoformat()
        listing.created_at = now
        listing.updated_at = now
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO marketplace_listings
                (listing_id, tune_id, seller_id, title, description, price_credits,
                 category, tags, rating, downloads, is_featured, created_at, updated_at, pii_scan_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.listing_id,
                    listing.tune_id,
                    listing.seller_id,
                    listing.title,
                    listing.description,
                    listing.price_credits,
                    listing.category,
                    json.dumps(listing.tags),
                    listing.rating,
                    listing.downloads,
                    int(listing.is_featured),
                    listing.created_at,
                    listing.updated_at,
                    json.dumps(listing.pii_scan_result),
                ),
            )
            conn.commit()
        return True

    def get_listing(self, listing_id: str) -> Optional[MarketplaceListing]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM marketplace_listings WHERE listing_id = ?",
                (listing_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_listing(row)

    def list_listings(
        self,
        category: Optional[str] = None,
        featured_only: bool = False,
        min_rating: float = 0.0,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MarketplaceListing]:
        query = "SELECT * FROM marketplace_listings WHERE 1=1"
        params: List[Any] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if featured_only:
            query += " AND is_featured = 1"
        if min_rating > 0:
            query += " AND rating >= ?"
            params.append(min_rating)
        query += " ORDER BY rating DESC, downloads DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_listing(r) for r in rows]

    def increment_downloads(self, listing_id: str) -> bool:
        with self._conn() as conn:
            conn.execute(
                "UPDATE marketplace_listings SET downloads = downloads + 1 WHERE listing_id = ?",
                (listing_id,),
            )
            conn.commit()
        return True

    def update_rating(self, listing_id: str, new_rating: float) -> bool:
        listing = self.get_listing(listing_id)
        if not listing:
            return False
        # Weighted average with downloads as weight
        total_weight = listing.downloads + 1
        avg = (listing.rating * listing.downloads + new_rating) / total_weight
        with self._conn() as conn:
            conn.execute(
                "UPDATE marketplace_listings SET rating = ? WHERE listing_id = ?",
                (avg, listing_id),
            )
            conn.commit()
        return True

    def delete_listing(self, listing_id: str) -> bool:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM marketplace_listings WHERE listing_id = ?",
                (listing_id,),
            )
            conn.commit()
        return True

    def search(self, query: str, limit: int = 20) -> List[MarketplaceListing]:
        """Simple text search across title, description, and tags."""
        pattern = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM marketplace_listings
                WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
                ORDER BY rating DESC, downloads DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._row_to_listing(r) for r in rows]

    def _row_to_listing(self, row: sqlite3.Row) -> MarketplaceListing:
        return MarketplaceListing(
            listing_id=row["listing_id"],
            tune_id=row["tune_id"],
            seller_id=row["seller_id"],
            title=row["title"],
            description=row["description"] or "",
            price_credits=row["price_credits"],
            category=row["category"] or "",
            tags=json.loads(row["tags"] or "[]"),
            rating=row["rating"],
            downloads=row["downloads"],
            is_featured=bool(row["is_featured"]),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            pii_scan_result=json.loads(row["pii_scan_result"] or "{}"),
        )
