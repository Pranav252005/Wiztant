"""Tests for Tune Hub marketplace and PII scanner."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.marketplace.pii_scanner import PIIScanner, PIIScanResult
from core.tune_hub.marketplace.listings import ListingStore, MarketplaceListing


class TestPIIScanner:
    def test_clean_payload(self):
        scanner = PIIScanner()
        payload = {
            "personas": {"debug": 0.7, "build": 0.3},
            "description": "Optimal blend for coding tasks",
        }
        result = scanner.scan(payload)
        assert result.clean is True
        assert result.risk_score == 0.0

    def test_detects_email(self):
        scanner = PIIScanner()
        payload = {
            "description": "Contact me at john.doe@example.com for support",
        }
        result = scanner.scan(payload)
        assert result.clean is False
        assert any(i["type"] == "email" for i in result.issues)
        assert result.risk_score > 0.0

    def test_detects_api_key(self):
        scanner = PIIScanner()
        payload = {
            "config": "api_key=sk-1234567890abcdef1234567890abcdef",
        }
        result = scanner.scan(payload)
        assert result.clean is False
        assert any(i["type"] == "api_key" for i in result.issues)

    def test_detects_url(self):
        scanner = PIIScanner()
        payload = {
            "notes": "See https://my-private-server.com/config for details",
        }
        result = scanner.scan(payload)
        assert result.clean is False
        assert any(i["type"] == "url" for i in result.issues)

    def test_scrub_payload(self):
        scanner = PIIScanner(auto_scrub=True)
        payload = {
            "description": "Contact me at john.doe@example.com",
            "config": "api_key=sk-1234567890abcdef",
        }
        scrubbed = scanner.scrub(payload)
        text = str(scrubbed)
        assert "john.doe@example.com" not in text
        assert "sk-1234567890abcdef" not in text

    def test_risk_score_calculation(self):
        scanner = PIIScanner()
        payload = {
            "ssn": "My SSN is 123-45-6789",
            "password": "password = secret123",
        }
        result = scanner.scan(payload)
        assert result.risk_score >= 0.5


class TestListingStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = Path(self.tmpdir) / "marketplace.db"
        self.store = ListingStore(str(db_path))

    def test_create_and_get(self):
        listing = MarketplaceListing(
            listing_id="lst_001",
            tune_id="tune_001",
            seller_id="seller_001",
            title="Coding Persona Blend",
            description="Optimized for Python development",
            price_credits=200,
            category="RePrompt",
            tags=["coding", "python", "developer"],
            rating=4.5,
        )
        assert self.store.create_listing(listing) is True

        fetched = self.store.get_listing("lst_001")
        assert fetched is not None
        assert fetched.title == "Coding Persona Blend"
        assert fetched.price_credits == 200

    def test_list_and_filter(self):
        for i in range(3):
            listing = MarketplaceListing(
                listing_id=f"lst_{i}",
                tune_id=f"tune_{i}",
                seller_id="seller_001",
                title=f"Tune {i}",
                category="RePrompt" if i < 2 else "Dictation",
                rating=4.0 + i * 0.5,
            )
            self.store.create_listing(listing)

        all_listings = self.store.list_listings()
        assert len(all_listings) == 3

        reprompt = self.store.list_listings(category="RePrompt")
        assert len(reprompt) == 2

        featured = self.store.list_listings(min_rating=4.5)
        assert len(featured) == 2

    def test_search(self):
        listing = MarketplaceListing(
            listing_id="lst_search",
            tune_id="tune_search",
            seller_id="seller_001",
            title="Python Coding Helper",
            description="Best blend for pythonistas",
            tags=["python", "coding"],
        )
        self.store.create_listing(listing)

        results = self.store.search("python")
        assert len(results) == 1
        assert results[0].title == "Python Coding Helper"

    def test_increment_downloads(self):
        listing = MarketplaceListing(
            listing_id="lst_dl",
            tune_id="tune_dl",
            seller_id="seller_001",
            title="Test",
            downloads=5,
        )
        self.store.create_listing(listing)
        self.store.increment_downloads("lst_dl")
        fetched = self.store.get_listing("lst_dl")
        assert fetched.downloads == 6

    def test_update_rating(self):
        listing = MarketplaceListing(
            listing_id="lst_rate",
            tune_id="tune_rate",
            seller_id="seller_001",
            title="Test",
            rating=4.0,
            downloads=10,
        )
        self.store.create_listing(listing)
        self.store.update_rating("lst_rate", 5.0)
        fetched = self.store.get_listing("lst_rate")
        # Weighted average: (4.0*10 + 5.0) / 11
        expected = (4.0 * 10 + 5.0) / 11
        assert abs(fetched.rating - expected) < 0.01

    def test_delete_listing(self):
        listing = MarketplaceListing(
            listing_id="lst_del",
            tune_id="tune_del",
            seller_id="seller_001",
            title="To Delete",
        )
        self.store.create_listing(listing)
        assert self.store.delete_listing("lst_del") is True
        assert self.store.get_listing("lst_del") is None
