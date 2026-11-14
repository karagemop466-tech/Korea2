#!/usr/bin/env python3
"""Regression test for issue #9 hardening in the live strategy pipeline.

`scripts/analyze_strategies.py` settles every bet at the closing price the feed reports. A selected
bet with no reported price is excluded from settlement and counted in
`data/derived/strategies.json` meta (`missing_price_policy.n_excluded_missing_price`) rather than
being imputed at a default -110. The published 2023-2026 window contains 0 such rows, so no
published number changes — this test pins the drop-not-impute behaviour so a future feed change cannot
silently reintroduce an imputed price.

Run from the repository root:

    python -m unittest tests.test_analyze_strategies -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import analyze_strategies as AS  # noqa: E402


class MissingPriceDropTests(unittest.TestCase):
    """A bet with no quoted price is dropped and counted, never imputed."""

    def setUp(self):
        AS._price_exclusions.clear()

    def _spread_df(self) -> pd.DataFrame:
        # Two home picks: one with a real price, one with a missing price.
        return pd.DataFrame([
            {"game_id": "g1", "season": 2026, "week": 8, "home_team": "A", "away_team": "B",
             "result": 10.0, "spread_line": 3.0, "home_spread_odds": -110.0,
             "away_spread_odds": -110.0},
            {"game_id": "g2", "season": 2026, "week": 8, "home_team": "C", "away_team": "D",
             "result": 5.0, "spread_line": 3.0, "home_spread_odds": np.nan,
             "away_spread_odds": np.nan},
        ])

    def _total_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"game_id": "g1", "season": 2026, "week": 8, "away_team": "A", "home_team": "B",
             "total": 47.0, "total_line": 46.5, "over_odds": -110.0, "under_odds": -110.0},
            {"game_id": "g2", "season": 2026, "week": 8, "away_team": "C", "home_team": "D",
             "total": 40.0, "total_line": 46.5, "over_odds": np.nan, "under_odds": np.nan},
        ])

    def test_price_helper_rejects_missing_and_bad_prices(self):
        self.assertIsNone(AS._price(np.nan))
        self.assertIsNone(AS._price(None))
        # a real quoted price is returned as a float
        self.assertEqual(AS._price(-110.0), -110.0)
        self.assertEqual(AS._price(150.0), 150.0)

    def test_spread_bet_with_missing_price_is_dropped_not_imputed(self):
        recs = AS.spread_bets(self._spread_df(), lambda r: "home", "S_test", "note")
        # Only the priced row is settled; the missing-price row is gone.
        self.assertEqual([r["game_id"] for r in recs], ["g1"])
        self.assertEqual(AS._price_exclusions, {"S_test": 1})
        # The settled row kept its real price, not a -110 fallback for the dropped one.
        self.assertEqual(recs[0]["odds"], -110.0)

    def test_total_bet_with_missing_price_is_dropped_not_imputed(self):
        recs = AS.total_bets(self._total_df(), lambda r: "over", "T_test", "note")
        self.assertEqual([r["game_id"] for r in recs], ["g1"])
        self.assertEqual(AS._price_exclusions, {"T_test": 1})

    def test_no_missing_price_records_empty_exclusions(self):
        df = self._spread_df().iloc[[0]]  # only the priced row
        recs = AS.spread_bets(df, lambda r: "home", "S_clean", "note")
        self.assertEqual(len(recs), 1)
        self.assertEqual(AS._price_exclusions, {})


if __name__ == "__main__":
    unittest.main()
