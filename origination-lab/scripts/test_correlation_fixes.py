"""Regression tests for the issue #32 fixes in origination-lab.

Run from the repository root:

    python -m unittest discover -s origination-lab/scripts -t origination-lab/scripts -v

Covers: the copula latent-rho calibration at a known phi (0.55 -> rho 0.7604 ->
joint 0.3875), the corrected push-rate sign, the any-receiver relabel, the
week-clustered cross-game interval and its qualified wording, and the
price-aware edge-curve null.
"""
from __future__ import annotations

import csv
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_correlations as bc  # noqa: E402

DERIVED = ROOT / "data" / "derived"
RAW = ROOT / "data" / "raw"


def load(name):
    p = DERIVED / name
    return json.loads(p.read_text()) if p.exists() else None


class CopulaCalibrationTests(unittest.TestCase):
    """Issue #32.4: binary phi and latent Gaussian rho are different numbers."""

    def test_known_phi_identity(self):
        rho = bc.rho_from_phi(0.55)
        self.assertAlmostEqual(rho, 0.7604, places=4)
        joint = bc.copula_joint(0.5, 0.5, rho)
        self.assertAlmostEqual(joint, 0.3875, places=3)
        # feeding the measured phi straight in as if it were rho is the old error
        self.assertAlmostEqual(bc.copula_joint(0.5, 0.5, 0.55), 0.3427, places=3)

    def test_bisection_recovers_rho(self):
        rho = bc.rho_for_joint(0.5, 0.5, 0.3875)
        self.assertAlmostEqual(rho, 0.7604, places=3)
        self.assertAlmostEqual(bc.copula_joint(0.5, 0.5, rho), 0.3875, places=6)

    def test_every_calibrated_row_reproduces_its_joint(self):
        corr = load("correlations.json")
        rows = corr.get("copula_calibration") or []
        self.assertTrue(rows, "no copula_calibration rows published")
        for r in rows:
            if r["latent_rho_calibrated"] is None:
                continue
            self.assertAlmostEqual(r["copula_joint_at_calibrated_rho"],
                                   r["p_both_actual"], places=4,
                                   msg=f"{r['pair']} calibration does not reproduce the joint")

    def test_pricing_table_is_labelled_hypothetical(self):
        corr = load("correlations.json")
        self.assertIn("latent", corr["pricing_table_kind"].lower())
        self.assertIn("not the observed binary phi".lower(),
                      corr["pricing_table_kind"].lower())


class PushRateSignTests(unittest.TestCase):
    """Issue #32.1: the published line must carry the sign that was selected."""

    @unittest.skipUnless((RAW / "games.csv").exists(), "raw games.csv not present")
    def test_minus_three_is_the_favourite_line(self):
        rows = {-3: []}
        with open(RAW / "games.csv", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    if int(r["season"]) < 2006:             # same filter as key_numbers()
                        continue
                    spread = float(r["spread_line"])
                    float(r["total_line"])                  # must be present, as in key_numbers()
                    hl = -spread                            # home_line = -spread_line
                    margin = float(r["home_score"]) - float(r["away_score"])
                except (TypeError, ValueError, KeyError):
                    continue
                if abs(hl + 3.0) > 1e-9:                    # home favourite by exactly 3
                    continue
                rows[-3].append((margin + hl) == 0)
        corr = load("correlations.json")
        published = corr["key_numbers"]["push_rates_by_line"]["-3"]
        n = len(rows[-3])
        self.assertEqual(published["n"], n,
                         "published -3 row does not select home_line == -3")
        self.assertAlmostEqual(published["push_rate"], sum(rows[-3]) / n, places=3)

    def test_favourite_line_pushes_more_than_underdog_line(self):
        corr = load("correlations.json")
        rates = corr["key_numbers"]["push_rates_by_line"]
        for fav, dog in (("-3", "3"), ("-7", "7"), ("-10", "10")):
            if fav in rates and dog in rates:
                self.assertGreater(rates[fav]["push_rate"], rates[dog]["push_rate"],
                                   f"{fav} (favourite) should push more often than {dog}")


class CrossGameTests(unittest.TestCase):
    """Issue #32.3: bounded, week-clustered finding; not an independence proof."""

    def test_interval_is_week_clustered_and_labelled(self):
        corr = load("correlations.json")
        cg = corr["cross_game"]
        self.assertIn("week-clustered bootstrap", cg["ci_method"])
        self.assertGreater(cg["n"], 10000, "expected all within-week pairs, not 12 samples")
        self.assertIn("n_weeks", cg)
        self.assertIn("does not establish", cg["note"])
        self.assertLessEqual(cg["ci_lo"], cg["phi"])
        self.assertGreaterEqual(cg["ci_hi"], cg["phi"])


class LabelTests(unittest.TestCase):
    """Issue #32.2: the QB/receiver label must match the max() aggregation."""

    def test_qb_pair_is_any_receiver(self):
        corr = load("correlations.json")
        names = [p["pair"] for p in corr["prop_pairs"]]
        match = [n for n in names if n.startswith("QB passing yards") and "receiver" in n]
        self.assertTrue(match)
        self.assertIn("at least one receiver", match[0])
        notes = [p["note"] for p in corr["prop_pairs"] if p["pair"] == match[0]][0]
        self.assertIn("NOT a pregame-identified", notes)


class EdgeCurveNullTests(unittest.TestCase):
    """Issue #32.5: a fixed 0.5238 null is an approximation; use the prices."""

    def test_price_aware_null(self):
        lines = load("lines.json")
        for market in ("spread", "total"):
            for row in lines["edge_curves"][market]:
                self.assertIn("p_null", row)
                self.assertIn("price-aware", row["null_note"])
                self.assertTrue(0.3 < row["p_null"] < 0.7)


if __name__ == "__main__":
    unittest.main()
