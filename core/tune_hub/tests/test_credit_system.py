"""Tests for Tune Hub credit system."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.tune_hub.credit_system.free_tracker import FreeCreditTracker
from core.tune_hub.credit_system.pro_tracker import ProCreditTracker


class TestFreeCreditTracker:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tracker = FreeCreditTracker(str(Path(self.tmpdir) / "ledger.json"))

    def test_initial_balance(self):
        bal = self.tracker.get_balance("u1")
        assert bal.available == 2_000
        assert bal.consumed == 0

    def test_reserve_and_consume(self):
        assert self.tracker.reserve("u1", 500)
        bal = self.tracker.get_balance("u1")
        assert bal.reserved == 500

        remaining = self.tracker.consume("u1", 300)
        assert remaining == 1_700
        bal = self.tracker.get_balance("u1")
        assert bal.reserved == 200
        assert bal.consumed == 300

    def test_reserve_insufficient(self):
        assert not self.tracker.reserve("u1", 3_000)

    def test_refund(self):
        self.tracker.consume("u1", 500)
        remaining = self.tracker.refund("u1", 200)
        assert remaining == 1_700
        bal = self.tracker.get_balance("u1")
        assert bal.consumed == 300

    def test_grant(self):
        remaining = self.tracker.grant("u1", 500, "bonus")
        assert remaining == 2_500


class TestProCreditTracker:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tracker = ProCreditTracker(
            str(Path(self.tmpdir) / "ledger.json"), tier="pro"
        )

    def test_initial_balance(self):
        bal = self.tracker.get_balance("u1")
        assert bal.available == 10_000

    def test_power_initial_balance(self):
        power = ProCreditTracker(
            str(Path(self.tmpdir) / "ledger_power.json"), tier="power"
        )
        bal = power.get_balance("u1")
        assert bal.available == 25_000
