#!/usr/bin/env python3
"""Unit tests for the 2026-11-14 correctness-sweep changes.

Covers:
1. D1 demotion gate (scripts/lib/backtest.evaluate_demotion): dormant, demote on signal decay,
   demote on staking collapse, hold on a healthy live strategy, and the re-promotion rule text.
2. Missing-price exclusion in scripts/analyze_strategies (no -110 imputation; bets without a
   stored price are excluded and counted).

Run: python3 scripts/test_correctness_sweep.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import backtest as B  # noqa: E402


class DemotionGateTests(unittest.TestCase):
    @staticmethod
    def bets(n, wins, clv=None, profit=None):
        out = []
        for i in range(n):
            won = i < wins
            out.append({
                "outcome": "win" if won else "loss",
                "profit": (0.909 if won else -1.0) if profit is None else profit(i),
                "staked": 1.0,
                "clv": clv(i) if clv else None,
            })
        return out

    def test_dormant_when_not_live(self):
        res = B.evaluate_demotion(self.bets(60, 5), live=False)
        self.assertEqual(res["status"], "dormant")
        self.assertIn("not live", res["reason"])

    def test_demote_on_staking_collapse(self):
        # 30% win rate at even-ish prices => rolling ROI far below the -5% floor.
        res = B.evaluate_demotion(self.bets(50, 15), live=True)
        self.assertEqual(res["status"], "demote-to-paper")
        self.assertTrue(any("ROI" in r for r in res["reasons"]))

    def test_demote_on_signal_decay_even_when_roi_positive(self):
        # A lucky staking run: profitable window but CLV <= 0 must still demote.
        res = B.evaluate_demotion(
            self.bets(50, 30, clv=lambda i: -0.01), live=True)
        self.assertEqual(res["status"], "demote-to-paper")
        self.assertTrue(any("CLV" in r for r in res["reasons"]))

    def test_hold_on_healthy_live_strategy(self):
        res = B.evaluate_demotion(
            self.bets(50, 30, clv=lambda i: 0.02), live=True)
        self.assertEqual(res["status"], "live")
        self.assertEqual(res["reasons"], [])
        self.assertAlmostEqual(res["rolling_clv"], 0.02, places=4)

    def test_clv_gap_disclosed_when_no_opening_prices(self):
        res = B.evaluate_demotion(self.bets(50, 30), live=True)
        self.assertFalse(res["clv_bets_in_window"])
        self.assertIsNone(res["rolling_clv"])
        self.assertIn("closing-type prices", res["data_limitation"])

    def test_gate_definition_declares_proposed_thresholds(self):
        self.assertIn("PROPOSED", B.DEMOTION_GATE["thresholds_status"])
        self.assertEqual(B.DEMOTION_GATE["id"], "D1")
        # the demotion decision must be able to read the signal, not only ROI
        self.assertIn("CLV", B.DEMOTION_GATE["rule"])


class MissingPriceExclusionTests(unittest.TestCase):
    """A bet with no stored price is excluded and counted, never settled at -110."""

    def test_spread_missing_price_excluded(self):
        import pandas as pd
        import importlib
        asp = importlib.import_module("analyze_strategies")
        asp.MISSING_PRICE_EXCLUSIONS.clear()
        df = pd.DataFrame([{
            "game_id": "g1", "season": 2024, "week": 1, "home_team": "H", "away_team": "A",
            "result": 3, "spread_line": -3.0, "home_spread_odds": float("nan"),
            "away_spread_odds": -110.0,
        }])
        recs = asp.spread_bets(df, lambda r: "home", "S_test", "test")
        self.assertEqual(recs, [])
        self.assertEqual(asp.MISSING_PRICE_EXCLUSIONS.get("S_test"), 1)

    def test_total_missing_price_excluded(self):
        import pandas as pd
        import importlib
        asp = importlib.import_module("analyze_strategies")
        asp.MISSING_PRICE_EXCLUSIONS.clear()
        df = pd.DataFrame([{
            "game_id": "g1", "season": 2024, "week": 1, "home_team": "H", "away_team": "A",
            "total": 41, "total_line": 44.5, "over_odds": float("nan"), "under_odds": -110.0,
        }])
        recs = asp.total_bets(df, lambda r: "over", "T_test", "test")
        self.assertEqual(recs, [])
        self.assertEqual(asp.MISSING_PRICE_EXCLUSIONS.get("T_test"), 1)

    def test_priced_bet_still_settles(self):
        import pandas as pd
        import importlib
        asp = importlib.import_module("analyze_strategies")
        asp.MISSING_PRICE_EXCLUSIONS.clear()
        df = pd.DataFrame([{
            "game_id": "g1", "season": 2024, "week": 1, "home_team": "H", "away_team": "A",
            "result": 7, "spread_line": -3.0, "home_spread_odds": -105.0,
            "away_spread_odds": -115.0,
        }])
        recs = asp.spread_bets(df, lambda r: "home", "S_test2", "test")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["odds"], -105.0)
        self.assertNotIn("S_test2", asp.MISSING_PRICE_EXCLUSIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
