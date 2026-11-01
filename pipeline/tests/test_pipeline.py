"""Unit tests for the pieces that are easy to get silently wrong.

Run: python -m unittest discover -s pipeline/tests -v
These run in CI (see .github/workflows/check.yml) and need pandas + numpy only.
"""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

import numpy as np  # noqa: E402

from lib.common import (american_to_decimal, american_to_prob, bh_qvalues,  # noqa: E402
                        bootstrap_mean_ci, deflated_sharpe_ratio, devig_two_way, normal_cdf)


class TestOdds(unittest.TestCase):
    def test_american_to_decimal(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1.9090909, places=6)
        self.assertAlmostEqual(american_to_decimal(150), 2.5, places=9)
        self.assertAlmostEqual(american_to_decimal(-100), 2.0, places=9)
        self.assertAlmostEqual(american_to_decimal(100), 2.0, places=9)
        self.assertTrue(math.isnan(american_to_decimal(float("nan"))))

    def test_implied_probability_symmetry(self):
        self.assertAlmostEqual(american_to_prob(-110), 110 / 210, places=9)
        self.assertAlmostEqual(american_to_prob(110), 100 / 210, places=9)

    def test_devig_sums_to_one(self):
        a, b = devig_two_way(american_to_prob(-110), american_to_prob(-110))
        self.assertAlmostEqual(a + b, 1.0, places=12)
        self.assertLess(a, 0.5 + 1e-12)  # a fair -110/-110 coin has no favourite


class TestSettlement(unittest.TestCase):
    """Settlement must be reproducible by hand."""

    def setUp(self):
        from strategies import _settle_ml, _settle_spread, _settle_total
        self.spread, self.total, self.ml = _settle_spread, _settle_total, _settle_ml

    def test_spread(self):
        self.assertEqual(self.spread(7, 3.5, "home"), "win")     # 24-17 home, -3.5
        self.assertEqual(self.spread(0, 3.5, "home"), "loss")
        self.assertEqual(self.spread(-7, 3.5, "away"), "win")    # away covered as a dog
        self.assertEqual(self.spread(3, 3.0, "home"), "push")
        self.assertEqual(self.spread(3, 3.0, "away"), "push")

    def test_total(self):
        self.assertEqual(self.total(51, 48.5, "over"), "win")
        self.assertEqual(self.total(45, 48.5, "over"), "loss")
        self.assertEqual(self.total(45, 48.5, "under"), "win")
        self.assertEqual(self.total(48, 48.0, "over"), "push")

    def test_moneyline(self):
        self.assertEqual(self.ml(3, "home"), "win")
        self.assertEqual(self.ml(3, "away"), "loss")
        self.assertEqual(self.ml(0, "home"), "push")

    def test_control_lands_near_the_vig(self):
        """A no-information control should return roughly minus the vig, not zero."""
        lb = json.loads((ROOT / "site_data" / "leaderboard.json").read_text())
        rows = {m["strategy"]: m for m in lb["strategies"]}
        for name in ("CTRL_ALL_HOME", "CTRL_ALL_OVER"):
            self.assertLess(rows[name]["roi"], 0.0)
            self.assertGreater(rows[name]["roi"], -0.12, f"{name} is outside any plausible vig range")

    def test_lookahead_control_is_rejected(self):
        lb = json.loads((ROOT / "site_data" / "leaderboard.json").read_text())
        leak = [m for m in lb["strategies"] if m["strategy"] == "CTRL_LEAK"][0]
        self.assertEqual(leak["tier"], "REJECTED")
        gates = {g["gate"]: g["status"] for g in leak["gates"]}
        self.assertEqual(gates["G1"], "FAIL")


class TestStatistics(unittest.TestCase):
    def test_normal_cdf(self):
        self.assertAlmostEqual(normal_cdf(0), 0.5, places=9)
        self.assertAlmostEqual(normal_cdf(1.959964), 0.975, places=5)

    def test_bh_qvalues_monotone(self):
        p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
        q = bh_qvalues(p)
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(q, q[1:])))
        self.assertTrue(all(0 <= x <= 1 for x in q))
        self.assertLessEqual(q[0], 0.0100000001)

    def test_bh_single(self):
        self.assertEqual(bh_qvalues([0.03])[0], 0.03)

    def test_bootstrap_ci_covers_mean(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0.05, 1.0, 400)
        mean, lo, hi = bootstrap_mean_ci(x, n_boot=2000)
        self.assertLess(lo, mean)
        self.assertGreater(hi, mean)

    def test_deflated_sharpe_penalises_trials(self):
        rng = np.random.default_rng(2)
        r = rng.normal(0.02, 1.0, 800)
        few = deflated_sharpe_ratio(r, n_trials=1)["dsr"]
        many = deflated_sharpe_ratio(r, n_trials=1000)["dsr"]
        self.assertGreater(few, many)


class TestOutputs(unittest.TestCase):
    """The published artefacts must exist and carry the fields the site renders."""

    def test_site_data_contract(self):
        needed = {
            "origination.json": ["accuracy", "accuracy_extra", "current_board"],
            "leaderboard.json": ["summary", "strategies"],
            "props.json": ["markets", "correlations", "coverage"],
            "correlation.json": ["market", "strategy", "parlay_legs"],
            "verification.json": ["checks", "spot_checks", "unverified", "summary"],
            "strategy_registry.json": ["single", "parlay"],
        }
        for fname, keys in needed.items():
            path = ROOT / "site_data" / fname
            self.assertTrue(path.exists(), f"{fname} missing")
            data = json.loads(path.read_text())
            for k in keys:
                self.assertIn(k, data, f"{fname} missing key {k}")

    def test_every_strategy_has_ten_gates(self):
        lb = json.loads((ROOT / "site_data" / "leaderboard.json").read_text())
        for m in lb["strategies"]:
            self.assertEqual(len(m["gates"]), 10, m["strategy"])
            self.assertIn(m["tier"], {"GOLD", "SILVER", "BRONZE", "NEEDS_REVIEW", "REJECTED"})

    def test_unverified_items_are_listed(self):
        v = json.loads((ROOT / "site_data" / "verification.json").read_text())
        self.assertGreaterEqual(len(v["unverified"]), 5)
        for u in v["unverified"]:
            self.assertTrue(u["why"])
            self.assertTrue(u["source_that_would_settle_it"])

    def test_props_publish_no_roi(self):
        """Prop ROI must not exist anywhere: there is no price feed."""
        pr = json.loads((ROOT / "site_data" / "props.json").read_text())
        for m in pr["markets"]:
            self.assertNotIn("roi", m)
            self.assertNotIn("units", m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
