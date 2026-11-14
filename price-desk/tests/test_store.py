"""Unit tests for the price-desk store arithmetic and policy."""
import csv
import gzip
import json
import os
import sys
import unittest

PD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(PD, ".."))
sys.path.insert(0, os.path.join(PD, "scripts"))
import build_store as bs  # noqa: E402


class ConventionTests(unittest.TestCase):
    def test_american_to_prob(self):
        self.assertAlmostEqual(bs.american_to_prob(-110), 110 / 210)
        self.assertAlmostEqual(bs.american_to_prob(150), 100 / 250)

    def test_prob_to_american_roundtrip(self):
        for p in (0.2, 0.5, 0.6244, 0.8):
            a = bs.prob_to_american(p)
            self.assertAlmostEqual(bs.american_to_prob(a), p, places=2)

    def test_settle_push(self):
        self.assertEqual(bs.settle(0.0), "push")
        self.assertEqual(bs.settle(1.5), "win")
        self.assertEqual(bs.settle(-2.0), "loss")


class StoreFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PD, "data", "price_snapshots.csv"), newline="") as f:
            cls.snaps = list(csv.DictReader(f))
        with open(os.path.join(PD, "data", "results_feed.csv"), newline="") as f:
            cls.feed = list(csv.DictReader(f))
        with open(os.path.join(PD, "data", "verified_results_2026.json")) as f:
            cls.verified = json.load(f)

    def test_spread_difference_arithmetic(self):
        for r in self.snaps:
            if r["market_type"] in ("SPREAD", "TOTAL"):
                a, b, d = bs.fnum(r["our_fair_line"]), bs.fnum(r["market_close_line"]), bs.fnum(r["difference"])
                if a != "" and a is not None and b not in ("", None) and d not in ("", None):
                    self.assertAlmostEqual(a - b, d, places=3, msg=r["market_id"])

    def test_open_columns_blank_everywhere(self):
        for r in self.snaps:
            self.assertEqual(r["market_open_line"], "", r["market_id"])
            self.assertIn("blank", r["open_status"])

    def test_every_verified_score_has_official_url(self):
        for r in self.feed:
            if r["score_status"].startswith("verified-official"):
                self.assertIn("nfl.com", r["official_source_url"], r["game_id"])

    def test_no_archived_value_marked_verified(self):
        for r in self.feed:
            if r["score_status"] == "archived-unverified":
                self.assertEqual(r["official_source_url"], "", r["game_id"])

    def test_official_overlay_matches_verification_record(self):
        rec = {v["game_id"]: v for v in self.verified["verified_scores"]}
        n = 0
        for r in self.feed:
            if r["game_id"] in rec:
                v = rec[r["game_id"]]
                self.assertEqual(float(r["away_score"]), float(v["away_score"]), r["game_id"])
                self.assertEqual(float(r["home_score"]), float(v["home_score"]), r["game_id"])
                n += 1
        self.assertGreaterEqual(n, 22)

    def test_was_nyg_gamebook_score(self):
        rec = {v["game_id"]: v for v in self.verified["verified_scores"]}
        v = rec["2026_10_WAS_NYG"]
        self.assertEqual((v["away_score"], v["home_score"]), (24, 21))

    def test_slate_display_conversion(self):
        """origination-lab our_spread is display convention; store negates it."""
        with open(os.path.join(ROOT, "origination-lab", "data", "derived", "lines.json")) as f:
            slate = {r["game_id"]: r for r in json.load(f)["slate"]["rows"]}
        checked = 0
        for r in self.snaps:
            if r["origin_engine"] == "origination-lab" and r["market_type"] == "SPREAD":
                s = slate[r["game_id"]]
                self.assertAlmostEqual(-bs.fnum(s["our_spread"]), bs.fnum(r["our_fair_line"]), places=3)
                checked += 1
        self.assertGreater(checked, 100)


if __name__ == "__main__":
    unittest.main()
