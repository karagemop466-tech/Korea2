"""Regression tests for the issue #19 / #34 fixes in the retired analysis build.

Run from the repository root:

    python -m unittest discover -s scripts/analysis -t scripts/analysis -v

These assert, per issue #34, that the sources page is rendered from the real
manifest at data/provenance.json (extract names, row counts and the
manifest-derived as-of date are present, no literal URL placeholders, no
claimed raw hashes that the manifest does not record), and, per issue #19,
that no price is imputed at -110 anywhere in the pipeline, that exclusions of
price-less rows are disclosed in results/*.json, that the road-favourite angle
selects negative spreads, and that the retired generator cannot clobber the
published root site.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_site  # noqa: E402
from common import ROOT  # noqa: E402

PROV = ROOT / "data" / "provenance.json"
RESULTS = ROOT / "results"


def rload(name: str):
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


class SourcesPageTests(unittest.TestCase):
    """Issue #34: the manifest is read from data/provenance.json."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_site.page_sources()
        cls.prov = json.loads(PROV.read_text())

    def test_every_extract_named(self):
        for f in self.prov["files"]:
            self.assertIn(f["name"], self.html, f"{f['name']} missing from sources page")

    def test_row_counts_present(self):
        for f in self.prov["files"]:
            self.assertIn(f"{f['rows']:,}", self.html,
                          f"row count for {f['name']} missing from sources page")

    def test_manifest_date_present(self):
        self.assertIn(self.prov["data_as_of_gameday"], self.html)
        self.assertNotIn("gameday unknown", self.html)

    def test_no_literal_url_placeholders(self):
        self.assertNotIn("{year}", self.html)
        self.assertNotIn("{season}", self.html)

    def test_no_unrecorded_hash_claims(self):
        # the old page printed the word "pattern" in the SHA-256 column
        self.assertNotIn(">pattern<", self.html)
        sha_cells = re.findall(r"<code>([0-9a-f]{16})&hellip;</code>", self.html)
        recorded = {f.get("raw_sha256", "")[:16] for f in self.prov["files"]}
        for cell in sha_cells:
            self.assertIn(cell, recorded, "page shows a hash the manifest does not record")

    def test_per_season_urls_expanded(self):
        for f in self.prov["files"]:
            pattern = f.get("source_url_pattern")
            if pattern and f.get("seasons"):
                for s in f["seasons"]:
                    self.assertIn(pattern.replace("{year}", str(s)), self.html)


class NoImputationTests(unittest.TestCase):
    """Issue #19: nothing is settled at an assumed -110 price."""

    def test_no_fillna_minus_110_in_pipeline(self):
        for name in ("market.py", "strategies.py"):
            text = (HERE / name).read_text()
            self.assertNotIn("fillna(-110", text, f"{name} still imputes -110")

    def test_blind_bets_disclose_exclusions(self):
        mkt = rload("market.json")
        self.assertIsNotNone(mkt, "results/market.json missing; run scripts/analysis/build.py")
        for side, v in mkt["blind"].items():
            self.assertIn("n_excluded_missing_price", v, f"blind {side} hides exclusions")
            self.assertIsInstance(v["n_excluded_missing_price"], int)

    def test_angle_tests_disclose_exclusions(self):
        mkt = rload("market.json")
        for name, t in mkt["bias_tests"].items():
            self.assertIn("n_excluded_missing_price", t, f"angle {name} hides exclusions")
            self.assertIn("n_selected", t)

    def test_strategies_disclose_price_policy(self):
        strat = rload("strategies.json")
        self.assertIsNotNone(strat)
        for key, s in strat["strategies"].items():
            if not s.get("n"):
                continue
            self.assertIn("n_excluded_missing_price", s, f"{key} hides exclusions")
            self.assertIn("issue #19", s.get("price_policy", ""))
        self.assertIn("n_excluded_missing_price", strat["model"])
        parlays = strat.get("parlays") or {}
        self.assertNotIn("cross_game_independence", parlays,
                         "overclaiming independence key is back")

    def test_road_favourite_angle_selects_negative_spreads(self):
        """spread_line > 0 means HOME is favourite in this feed (proven in
        results/market.json -> convention_check), so the road-favourite angle
        must select spread_line < 0."""
        import gzip
        import csv
        n_neg = 0
        with gzip.open(ROOT / "data" / "derived" / "games.csv.gz", "rt") as fh:
            for row in csv.DictReader(fh):
                if row.get("game_type") != "REG" or not row.get("result"):
                    continue
                try:
                    if float(row["spread_line"]) < 0:
                        n_neg += 1
                except (TypeError, ValueError):
                    continue
        mkt = rload("market.json")
        t = mkt["bias_tests"]["away_fav"]
        self.assertEqual(t["side"], "away")
        self.assertEqual(t["n_selected"], n_neg,
                         "away_fav must select exactly the negative-spread (road favourite) games")


class CorrelationHonestyTests(unittest.TestCase):
    """Issue #19.3/.4: ex-post selection and independence wording."""

    def test_no_bare_wr1_labels(self):
        corr = rload("correlations.json")
        self.assertIsNotNone(corr)
        for c in corr["correlations"]:
            self.assertNotIn("WR1 receiving yards (same game)", c["name"])
        names = " ".join(c["name"] for c in corr["correlations"])
        self.assertIn("ex-post", names)

    def test_sgp_example_labelled_descriptive(self):
        corr = rload("correlations.json")
        sgp = corr["sgp"]["qb_plus_wr1"]
        self.assertIn("selection", sgp)
        self.assertIn("NOT a pregame strategy", sgp["selection"])

    def test_cross_game_note_does_not_overclaim(self):
        corr = rload("correlations.json")
        self.assertIn("does not establish", corr["cross_game"]["note"])


class ClobberGuardTests(unittest.TestCase):
    """Issue #34 follow-on: the retired generator must not overwrite the
    published root site while the line-lab generator owns it."""

    def test_owner_detected_at_root(self):
        self.assertEqual(build_site.published_owner(), "line-lab")

    def test_guard_renders_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            (fake_root / "index.html").write_text(
                '<meta name="generator" content="line-lab/scripts/build_site.py">')
            original = build_site.ROOT
            build_site.ROOT = fake_root
            try:
                build_site.main()
            finally:
                build_site.ROOT = original
            # nothing beyond the pre-seeded index.html may appear
            self.assertEqual(sorted(p.name for p in fake_root.iterdir()), ["index.html"])
            self.assertFalse((fake_root / "pages").exists())


if __name__ == "__main__":
    unittest.main()
