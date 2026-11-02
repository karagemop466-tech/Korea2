"""Regression tests for the issue #24 fixes in quant-lab (G9 price gate).

Run from the repository root:

    python -m unittest discover -s quant-lab/scripts -t quant-lab/scripts -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import validation  # noqa: E402

PROC = os.path.join(os.path.dirname(HERE), "data", "processed")


def bet(hit, decimal):
    return {"hit": hit, "void": False, "decimal": decimal, "season": 2021, "units": 0}


class G9MathTests(unittest.TestCase):
    """Issue #24: repricing must use each ticket's own recorded decimal."""

    def test_single_leg_shift(self):
        roi = validation.repriced_roi([bet(True, 1.9091)], -105, legs=1)
        self.assertAlmostEqual(roi, validation.decimal_of(-105) - 1.0, places=4)
        self.assertAlmostEqual(roi, 0.9524, places=3)

    def test_two_leg_ticket_is_not_replaced_by_a_single_price(self):
        """The old code replaced a 3.6446 parlay ticket with 1.9524 (-1.71 units of error)."""
        roi = validation.repriced_roi([bet(True, 3.6446)], -105, legs=2)
        ratio = validation.decimal_of(-105) / validation.decimal_of(-110)
        self.assertAlmostEqual(roi, 3.6446 * ratio ** 2 - 1.0, places=4)
        self.assertGreater(roi, 2.7, "leg-aware repricing must not collapse a 2-leg payout")
        buggy = validation.decimal_of(-105) - 1.0
        self.assertLess(abs(roi - buggy), 10)  # both finite ...
        self.assertGreater(roi - buggy, 1.7)   # ... but far apart, as the issue says

    def test_losing_bet_is_minus_one_regardless(self):
        self.assertAlmostEqual(validation.repriced_roi([bet(False, 3.6446)], -105, legs=2), -1.0)

    def test_worse_price_is_used_too(self):
        good = validation.repriced_roi([bet(True, 1.9091)], -105, legs=1)
        bad = validation.repriced_roi([bet(True, 1.9091)], -115, legs=1)
        self.assertLess(bad, good)
        self.assertAlmostEqual(bad, validation.decimal_of(-115) - 1.0, places=4)

    def test_void_and_unsettled_are_dropped(self):
        bets = [bet(True, 1.9091), {"hit": None, "void": False, "decimal": 1.9091},
                {"hit": True, "void": True, "decimal": 1.9091}]
        self.assertAlmostEqual(validation.repriced_roi(bets, -105, legs=1),
                               validation.decimal_of(-105) - 1.0, places=4)


class GateTests(unittest.TestCase):
    """The published gate must fail closed where a price cannot be decomposed."""

    def setUp(self):
        path = os.path.join(PROC, "leaderboard.json")
        if not os.path.exists(path):
            self.skipTest("leaderboard.json not built")
        with open(path) as fh:
            self.rows = json.load(fh)

    def test_no_strategy_is_ranked(self):
        self.assertEqual(self.rows["summary"]["qualified"], 0)
        self.assertIsNone(self.rows["summary"]["top"])

    def test_teaser_kind_fails_closed(self):
        legs = validation.LEGS_BY_KIND.get("teaser")
        self.assertIsNone(legs, "teaser prices are quoted packages and must not be repriced")

    def test_published_g9_values_are_both_prices(self):
        for r in self.rows["leaderboard"]:
            g9 = r["gates"]["G9_price_sensitivity"]
            if isinstance(g9.get("value"), dict):
                self.assertIn("roi_at_-105", g9["value"])
                self.assertIn("roi_at_-115", g9["value"])
                # a gate can only pass if BOTH prices are profitable
                if g9["pass"]:
                    self.assertGreater(g9["value"]["roi_at_-105"], 0)
                    self.assertGreater(g9["value"]["roi_at_-115"], 0)

    def test_multi_leg_rows_record_their_leg_count(self):
        kinds = {r["strategy"]: r["kind"] for r in self.rows["leaderboard"]}
        for r in self.rows["leaderboard"]:
            g9 = r["gates"]["G9_price_sensitivity"]
            if kinds[r["strategy"]] in ("parlay2", "sgp"):
                self.assertEqual(g9["value"]["legs"], 2)
            if kinds[r["strategy"]] == "parlay3":
                self.assertEqual(g9["value"]["legs"], 3)


if __name__ == "__main__":
    unittest.main()
