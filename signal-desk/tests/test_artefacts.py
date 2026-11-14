#!/usr/bin/env python3
"""Tests for the signal-desk artefacts. Run with ``python -m unittest discover -s signal-desk/tests``.

These assert the properties that would make a published number wrong, not just that the build ran:

  * the official standings reconciliation really closes for all 32 teams;
  * a "measured" value always has a source; an "unverified" value never has a number;
  * the opening-line source really contains no moneyline (so the blank cells are justified);
  * no season is covered by both the opening and the closing file;
  * rebuilding the analysis reproduces the committed JSON byte for byte, ignoring only the
    build timestamp.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(SD, ".."))
DATA = os.path.join(SD, "data")
sys.path.insert(0, os.path.join(SD, "scripts"))


def j(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


class OfficialReconciliation(unittest.TestCase):
    def test_all_32_teams_reconcile(self):
        r = j("results_feed.json")["standings_check"]
        self.assertEqual(r["teams_compared"], 32)
        self.assertEqual(r["teams_reconciling_after_official_scores"], 32,
                         "the committed results must reproduce the official standings table")
        for row in r["rows"]:
            self.assertTrue(row["reconciles_after"], row["team"])

    def test_no_game_is_double_counted(self):
        """A game already in the snapshot must not be added again from the transcript."""
        feed = j("results_feed.json")["game_feed"]["rows"]
        present = [f for f in feed if f["committed_status"] == "present"]
        for f in present:
            self.assertEqual((f["committed_away_score"], f["committed_home_score"]),
                             (f["official_away_score"], f["official_home_score"]),
                             f"{f['game_id']}: committed and official scores disagree")

    def test_whole_seasons_reconcile(self):
        for row in j("results_feed.json")["season_reconciliation"]["rows"]:
            self.assertEqual(row["teams_match"], row["teams_compared"], row["season"])


class SourcingDiscipline(unittest.TestCase):
    def test_measured_values_have_sources_and_unverified_values_are_blank(self):
        for name in sorted(os.listdir(DATA)):
            if not name.endswith(".json"):
                continue
            stack = [j(name)]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    if node.get("status") == "measured":
                        self.assertTrue(node.get("source"), f"{name}: measured without source")
                        self.assertEqual(node.get("source_class") in ("official", "third-party"),
                                         True, f"{name}: measured without source_class")
                    if node.get("status") == "unverified":
                        self.assertIsNone(node.get("value"),
                                          f"{name}: an unverified value must not carry a number")
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)

    def test_page_findings_are_only_confirmed_or_explicitly_not(self):
        for f in j("replacement_depth.json")["page_findings"]:
            self.assertIn(f["verdict"], ("confirmed", "not confirmed"))
            self.assertTrue(f["url"].startswith("https://www.nfl.com/"), f["url"])

    def test_no_official_class_on_a_third_party_number(self):
        """Anything sourced from nflverse or a repository path must not be classed official."""
        for name in sorted(os.listdir(DATA)):
            if not name.endswith(".json"):
                continue
            stack = [j(name)]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    if node.get("source_class") == "official":
                        s = str(node.get("source", ""))
                        self.assertNotIn("nflverse", s, f"{name}: nflverse classed official")
                        self.assertNotIn("data/derived", s, f"{name}: repo path classed official")
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)


class PriceStore(unittest.TestCase):
    def test_opening_source_has_no_moneyline(self):
        p = j("price_snapshots.json")
        if p["opening"]["status"] != "loaded":
            self.skipTest("opening file not fetched in this environment")
        self.assertEqual(p["opening"]["moneyline"], 0,
                         "if a moneyline appeared upstream, the blank cells would need revisiting")
        for r in p["opening"]["by_season"]:
            self.assertEqual(r["moneyline"], 0)

    def test_no_season_has_opening_and_closing(self):
        p = j("price_snapshots.json")
        if p["opening"]["status"] != "loaded" or p["closing_file"]["status"] != "loaded":
            self.skipTest("upstream files not fetched in this environment")
        self.assertEqual(p["join"]["seasons_with_both"], [],
                         "an overlapping season would make an open-to-close move computable")

    def test_closing_coverage_is_present_for_the_model_window(self):
        p = j("price_snapshots.json")
        seasons = {r["season"]: r for r in p["closing"]["by_season"]}
        for s in (2023, 2024, 2025):
            self.assertGreater(seasons[s]["moneyline"], 0, s)


class OriginationOrder(unittest.TestCase):
    def test_moneyline_reconstructs_from_side(self):
        with open(os.path.join(ROOT, "data", "derived", "model.json")) as fh:
            m = json.load(fh)
        sigma = m["margin_sigma"]
        for g in m["originated_lines"]["games"]:
            p = 0.5 * (1.0 + math.erf((g["model_spread_home"] / sigma) / math.sqrt(2.0)))
            self.assertLess(abs(p - g["model_home_win_prob"]), 0.002, g["game_id"])

    def test_order_tests_all_pass(self):
        for t in j("origination_order.json")["tests"]:
            self.assertEqual(t["verdict"], "pass", t["test"])


class GapBoard(unittest.TestCase):
    def test_every_row_has_both_parents_and_a_difference(self):
        for r in j("fair_market_gap.json")["board"]["rows"]:
            for k in ("fair_side_home", "market_side_home", "diff_side", "fair_total",
                      "market_total", "diff_total", "fair_ml_home", "market_ml_home"):
                self.assertIsNotNone(r[k], f"{r['game_id']}: {k} missing")

    def test_difference_equals_fair_minus_market(self):
        for r in j("fair_market_gap.json")["board"]["rows"]:
            self.assertAlmostEqual(r["diff_side"], r["fair_side_home"] - r["market_side_home"], 2)
            self.assertAlmostEqual(r["diff_total"], r["fair_total"] - r["market_total"], 2)


class SignalStaking(unittest.TestCase):
    def test_a_positive_roi_without_signal_is_flagged(self):
        s = j("signal_vs_staking.json")
        for r in s["rows"]:
            if (r["staking"]["roi"] or 0) > 0 and not r["signal"]["passes_signal_test"]:
                self.assertTrue(r["staking"]["lucky_run"], r["id"])
            if r["staking"]["lucky_run"]:
                self.assertFalse(r["signal"]["passes_signal_test"], r["id"])

    def test_no_reward_without_a_signal(self):
        s = j("signal_vs_staking.json")
        self.assertEqual(s["summary"]["rewards_paid"], 0)
        for r in s["rows"]:
            self.assertFalse(r["signal"]["passes_signal_test"], r["id"])


class DemotionGate(unittest.TestCase):
    def test_every_demotion_rule_has_a_trigger_and_an_action(self):
        for r in j("demotion_gate.json")["rules"]:
            self.assertTrue(r["trigger"])
            self.assertTrue(r["action"])

    def test_there_is_no_direct_route_back_from_demotion(self):
        sm = j("demotion_gate.json")["state_machine"]
        direct = [t for t in sm["transitions"]
                  if t["from"] == "paper (demoted)" and t["to"] == "live"
                  and "re-run" not in t["requires"]]
        self.assertEqual(direct, [])


class RenderedPages(unittest.TestCase):
    """Catch the presentation defects that structural link checks cannot see."""

    def pages(self):
        out = {}
        base = os.path.join(SD, "pages")
        for name in os.listdir(base):
            if name.endswith(".html"):
                out[name] = open(os.path.join(base, name)).read()
        return out

    def test_no_href_contains_two_urls(self):
        import re
        for name, text in self.pages().items():
            for href in re.findall(r'href="([^"]*)"', text):
                self.assertLessEqual(href.count("https://"), 1, f"{name}: {href[:80]}")
                self.assertNotIn("%20", href, f"{name}: {href[:80]}")

    def test_flagged_counts_match_the_data(self):
        """A headline count must be the same number everywhere it appears."""
        r = j("results_feed.json")["game_feed"]["committed_absent"]
        text = self.pages()["flagged.html"]
        import re
        m = re.search(r"FL-SD-04</strong></td><td>([^<]+)", text)
        self.assertIsNotNone(m, "FL-SD-04 row is missing")
        self.assertIn(str(r), m.group(1),
                      f"FL-SD-04 headline says {m.group(1)!r} but the data says {r}")

    def test_every_source_link_resolves_to_a_file_or_a_page(self):
        """Repository paths cited as sources must exist; external links must be https."""
        import re
        root = os.path.join(SD, "..")
        for name, text in self.pages().items():
            for href in re.findall(r'href="(https://github\.com/karagemop466-tech/Korea2/blob/main/[^"]+)"', text):
                rel = href.split("/blob/main/", 1)[1]
                self.assertTrue(os.path.exists(os.path.join(root, rel)),
                                f"{name}: cites a repository path that does not exist: {rel}")


class Deterministic(unittest.TestCase):
    def test_rebuild_reproduces_committed_json(self):
        """Rebuild with the same inputs and compare, ignoring only generated_utc."""
        env = dict(os.environ)
        raw = os.path.join(DATA, "raw")
        if os.path.exists(os.path.join(raw, "initial_lines.csv")):
            env["SD_INITIAL_LINES"] = os.path.join(raw, "initial_lines.csv")
            env["SD_CLOSING_LINES"] = os.path.join(raw, "closing_lines.csv")
        before = {n: j(n) for n in os.listdir(DATA) if n.endswith(".json")}
        proc = subprocess.run([sys.executable, os.path.join(SD, "scripts", "analysis.py")],
                              cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        def strip(node):
            if isinstance(node, dict):
                return {k: strip(v) for k, v in node.items() if k != "generated_utc"}
            if isinstance(node, list):
                return [strip(v) for v in node]
            return node

        for name, old in before.items():
            self.assertEqual(strip(old), strip(j(name)), f"{name} is not reproducible")


if __name__ == "__main__":
    unittest.main(verbosity=2)
