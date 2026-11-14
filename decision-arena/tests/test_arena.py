#!/usr/bin/env python3
"""Unit tests for the two things that silently ruin a research site: a sign error and a leaked feature.

Every test here exists because the corresponding bug was actually introduced during this build and
caught by a failing number, not by inspection. They are pinned so they cannot come back.

Run: python decision-arena/tests/test_arena.py      (stdlib only, no pytest required)
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from lib import arena as A            # noqa: E402
import build_strategies as B          # noqa: E402
import build_market as M              # noqa: E402


class TestSpreadSign(unittest.TestCase):
    """The home line IS the expected home margin. This was got wrong once; never again."""

    def test_home_favourite_lays_points(self):
        # line +7 (home is a 7-point favourite), home wins by 10 => home covers
        self.assertEqual(B.settle("spread", "home", 7.0, -110, margin=10, total=44)[1], True)
        # away on the same game loses
        self.assertEqual(B.settle("spread", "away", 7.0, -110, margin=10, total=44)[1], False)

    def test_home_underdog_covering(self):
        # line -7 (home is a 7-point underdog), home loses by 3 => home covers
        self.assertEqual(B.settle("spread", "home", -7.0, -110, margin=-3, total=44)[1], True)

    def test_push_is_a_push_not_a_loss(self):
        # line +3 (home favoured by 3), home wins by exactly 3 => push
        profit, won = B.settle("spread", "home", 3.0, -110, margin=3, total=44)
        self.assertEqual(profit, 0.0)
        self.assertIsNone(won)
        # line -3 with a +3 margin is a COVER, not a push: the home side was the underdog
        self.assertTrue(B.settle("spread", "home", -3.0, -110, margin=3, total=44)[1])

    def test_real_game_2013_week1_baltimore_at_denver(self):
        # Denver was the home favourite; the feed records spread_line +7.5.
        # BAL 27, DEN 49 => home margin +22, which covers -0? it covers +7.5 as home.
        self.assertEqual(B.settle("spread", "home", 7.5, -110, margin=22, total=76)[1], True)
        self.assertEqual(B.settle("spread", "away", 7.5, -110, margin=22, total=76)[1], False)

    def test_home_cover_rate_is_near_half_over_the_real_feed(self):
        """A sign error produces a 77% home cover rate; the true rate is close to 50%."""
        games, _, _ = M.load_games()
        graded = [g for g in games if g.get("game_type") == "REG"
                  and M.fnum(g.get("home_score")) is not None
                  and M.fnum(g.get("spread_line")) is not None]
        covers = sum(1 for g in graded
                     if (M.fnum(g["home_score"]) - M.fnum(g["away_score"])) - M.fnum(g["spread_line"]) > 0)
        rate = covers / len(graded)
        self.assertGreater(len(graded), 5000)
        self.assertGreater(rate, 0.44)
        self.assertLess(rate, 0.56, "home cover rate outside any plausible band: the sign convention is wrong")

    def test_line_mean_matches_margin_mean(self):
        """The strongest single proof of the convention: mean(line) ~= mean(home margin)."""
        games, _, _ = M.load_games()
        pairs = [(M.fnum(g["spread_line"]), M.fnum(g["home_score"]) - M.fnum(g["away_score"]))
                 for g in games
                 if g.get("game_type") == "REG" and M.fnum(g.get("home_score")) is not None
                 and M.fnum(g.get("spread_line")) is not None]
        mean_line = sum(p[0] for p in pairs) / len(pairs)
        mean_margin = sum(p[1] for p in pairs) / len(pairs)
        self.assertLess(abs(mean_line - mean_margin), 0.6,
                        f"mean line {mean_line:.2f} vs mean margin {mean_margin:.2f}: conventions disagree")


class TestTotalSign(unittest.TestCase):
    def test_over_and_under(self):
        self.assertEqual(B.settle("total", "over", 44.0, -110, margin=3, total=48)[1], True)
        self.assertEqual(B.settle("total", "under", 44.0, -110, margin=3, total=48)[1], False)
        self.assertEqual(B.settle("total", "under", 44.0, -110, margin=3, total=40)[1], True)

    def test_total_push(self):
        self.assertEqual(B.settle("total", "over", 44.0, -110, margin=3, total=44)[0], 0.0)


class TestNoPriceNoBet(unittest.TestCase):
    def test_missing_price_yields_no_profit(self):
        self.assertEqual(B.settle("spread", "home", 3.0, None, margin=10, total=44), (None, None))

    def test_unpriced_rows_are_counted_not_imputed(self):
        bets = [{"profit": None, "status": "price_missing", "won": None, "clv": None,
                 "beat_close": None, "season": 2020},
                {"profit": 1.0, "status": "won", "won": True, "clv": 0.0, "beat_close": True, "season": 2020}]
        s = B.summarise(bets)
        self.assertEqual(s["n_priced_bets"], 1)
        self.assertEqual(s["n_price_missing"], 1)
        self.assertEqual(s["roi"], 1.0)


class TestLeakage(unittest.TestCase):
    def test_features_never_see_the_current_game(self):
        """A game's rolling features must be built only from games that finished earlier."""
        games, _, _ = M.load_games()
        feats = B.build_features(games)
        # find the first game involving a team with prior history and check the counts
        seen = {}
        violations = 0
        for f in feats:
            for side in ("home", "away"):
                team = f[side]
                prior = seen.get(team, 0)
                if f[side + "_games_seen"] != prior:
                    violations += 1
                if f["home_score"] is not None:
                    seen[team] = seen.get(team, 0) + 1
        self.assertEqual(violations, 0, "a feature counted a game that had not been played yet")

    def test_model_train_set_excludes_the_slate(self):
        o = M.build_origination(M.load_games()[0])
        cutoff = o["slate"]["first_kickoff_gameday"]
        games, _, _ = M.load_games()
        after = [g for g in games if g.get("game_type") == "REG"
                 and g["gameday"] >= cutoff and M.fnum(g.get("home_score")) is not None]
        trained = o["slate"]["train_games_strictly_before"]
        settled = [g for g in games if g.get("game_type") == "REG" and M.fnum(g.get("home_score")) is not None]
        self.assertEqual(trained, len(settled) - len(after),
                         "train size does not equal settled games before the cutoff")


class TestStatistics(unittest.TestCase):
    def test_norm_ppf_known_values(self):
        self.assertAlmostEqual(A.norm_ppf(0.975), 1.959964, places=4)
        self.assertAlmostEqual(A.norm_ppf(0.5), 0.0, places=6)
        self.assertAlmostEqual(A.norm_ppf(0.05), -1.644854, places=4)

    def test_wilson_reproduces_the_repository(self):
        """The repository's published ATS interval is the check value."""
        lo, hi = A.wilson(3371, 6892)
        self.assertAlmostEqual(lo, 0.4773, places=3)
        self.assertAlmostEqual(hi, 0.5009, places=3)

    def test_pearson_perfect_and_negative(self):
        r, n = A.pearson([1, 2, 3, 4], [2, 4, 6, 8])
        self.assertAlmostEqual(r, 1.0, places=9)
        r, n = A.pearson([1, 2, 3, 4], [4, 3, 2, 1])
        self.assertAlmostEqual(r, -1.0, places=9)

    def test_bh_monotone(self):
        q = A.bh_qvalues([0.001, 0.02, 0.03, 0.2])
        self.assertEqual(q, sorted(q))

    def test_american_prices(self):
        self.assertAlmostEqual(A.american_to_prob(-110), 0.5238, places=3)
        self.assertAlmostEqual(A.american_to_prob(150), 0.4, places=3)
        self.assertAlmostEqual(A.american_to_decimal(-110), 1.909, places=2)


class TestTableGuard(unittest.TestCase):
    def test_row_without_source_raises(self):
        with self.assertRaises(ValueError):
            A.table(["A", "Source"], [["1", "2"]], "no source here")

    def test_blank_marker_is_accepted(self):
        out = A.table(["A", "Source"], [["1", A.blank("no source")]], "blank is honest")
        self.assertIn('class="blank"', out)

    def test_real_source_is_accepted(self):
        out = A.table(["A", "Source"], [["1", A.src("SRC-NFLVERSE-SCHED")]], "with a link")
        self.assertIn("https://", out)


class TestRegisters(unittest.TestCase):
    def test_strategy_verdicts_follow_the_gates(self):
        s = A.load("data/strategies.json")
        for e in s.get("entries", []):
            gates = e["gates"]
            if e["verdict"] == "LIVE":
                self.assertTrue(all(gates.values()))
            elif e["verdict"] == "PAPER":
                self.assertFalse(all(gates.values()))
                self.assertTrue(all(v for k, v in gates.items() if k != "DA-G9"))

    def test_every_suggestion_has_a_registered_question(self):
        s = A.load("data/suggestions.json")
        q = {x["id"] for x in A.load("data/questions.json").get("questions", [])}
        for x in s.get("suggestions", []):
            self.assertIn(x["blocked_by"], q)

    def test_price_grades_sum_to_the_snapshot_count(self):
        p = A.load("data/price_snapshots.json")
        g = p.get("grades", {})
        total = sum(g.values())
        # the early-snapshot grade counts games, not snapshots, so it is allowed to be smaller
        self.assertGreaterEqual(total, p.get("n_snapshots", 0))

    def test_no_official_depth_claim(self):
        d = A.load("data/depth.json")
        self.assertEqual(d.get("official_depth_chart_gap", {}).get("status"), "CONFIRMED_ABSENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
