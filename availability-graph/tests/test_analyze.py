#!/usr/bin/env python3
"""Schema-level tests for the availability-graph builder.

These tests do not need a capture: they build a small synthetic register set that mirrors the
official capture format, run the analysis over it and check the resulting schema and the
blank-by-policy rules.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AG_ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AG_ROOT, "scripts")

_spec = importlib.util.spec_from_file_location("ag_analyze", os.path.join(SCRIPTS, "analyze.py"))
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)


def write_csv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else ["empty"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_fixture(tmp):
    """Two captured weeks of official starting lineups for two clubs."""
    data = os.path.join(tmp, "data")
    os.makedirs(data, exist_ok=True)

    gamebooks = [
        {"season": "2026", "week": "9", "slug": "a-at-b-2026-reg-9",
         "game_url": "https://www.nfl.com/games/a-at-b-2026-reg-9",
         "gamebook_url": "https://static.www.nfl.com/gb9.pdf",
         "away_team": "AAA", "home_team": "BBB", "away_score": "10", "home_score": "7",
         "status": "FINAL", "slot": "Sunday 4:25 PM ET", "broadcast": "FOX",
         "gamebook_date": "Sunday, 11/8/2026", "venue_text": "Test Stadium",
         "start_time": "4:25 PM", "roof": "Closed Stadium", "surface": "Natural Grass",
         "weather": "Cloudy", "temp": "52 F", "humidity": "51%", "wind": "SE 3 mph",
         "attendance": "60,000", "pdf_sha256": "a" * 64, "pdf_bytes": "1000",
         "text_method": "pdftotext-layout", "lineups_parsed": "yes",
         "captured_utc": "2026-11-19T00:00:00Z"},
        {"season": "2026", "week": "10", "slug": "a-at-b-2026-reg-10",
         "game_url": "https://www.nfl.com/games/a-at-b-2026-reg-10",
         "gamebook_url": "https://static.www.nfl.com/gb10.pdf",
         "away_team": "AAA", "home_team": "BBB", "away_score": "21", "home_score": "14",
         "status": "FINAL", "slot": "Sunday 4:25 PM ET", "broadcast": "FOX",
         "gamebook_date": "Sunday, 11/15/2026", "venue_text": "Test Stadium",
         "start_time": "4:25 PM", "roof": "Closed Stadium", "surface": "Natural Grass",
         "weather": "Clear", "temp": "60 F", "humidity": "40%", "wind": "NW 5 mph",
         "attendance": "61,000", "pdf_sha256": "b" * 64, "pdf_bytes": "1000",
         "text_method": "pdftotext-layout", "lineups_parsed": "yes",
         "captured_utc": "2026-11-19T00:00:00Z"},
    ]
    write_csv(os.path.join(data, "gamebooks.csv"), gamebooks)

    lineups = []
    # AAA: QB, WR x2, RB / DE, LB x2, CB x2, S x2 -> 11 per unit
    off = [("QB", "7 A.Player"), ("WR", "11 B.Sample"), ("WR", "14 C.Player"),
           ("RB", "21 D.Runner"), ("TE", "88 E.Tight"), ("LT", "71 F.Lineman"),
           ("LG", "74 G.Lineman"), ("C", "63 H.Center"), ("RG", "68 I.Lineman"),
           ("RT", "77 J.Lineman"), ("K", "3 K.Kicker")]
    dfn = [("DE", "55 L.Edge"), ("DT", "93 M.DT"), ("DT", "94 N.DT"), ("LB", "58 O.Line"),
           ("LB", "50 P.Line"), ("CB", "25 Q.Corner"), ("CB", "26 R.Corner"),
           ("S", "29 S.Safety"), ("S", "31 T.Safety"), ("NB", "23 U.Back"), ("P", "6 V.Punter")]
    for week, qb in (("9", "7 A.Player"), ("10", "8 W.QB")):
        for team in ("AAA", "BBB"):
            rows = off if team == "AAA" else off
            for slot, who in rows:
                player = who
                if team == "BBB":
                    player = who.replace(" ", " Z.", 1)
                if slot == "QB" and team == "AAA" and week == "10":
                    player = "8 W.QB"
                lineups.append({"season": "2026", "week": week,
                                "slug": f"a-at-b-2026-reg-{week}",
                                "game_url": f"https://www.nfl.com/games/a-at-b-2026-reg-{week}",
                                "team": team, "unit": "offense", "slot": slot,
                                "jersey": who.split(" ")[0], "player": player.split(" ", 1)[1],
                                "source_url": f"https://static.www.nfl.com/gb{week}.pdf",
                                "captured_utc": "2026-11-19T00:00:00Z"})
            for slot, who in dfn:
                player = who if team == "AAA" else who.replace(" ", " Z.", 1)
                lineups.append({"season": "2026", "week": week,
                                "slug": f"a-at-b-2026-reg-{week}",
                                "game_url": f"https://www.nfl.com/games/a-at-b-2026-reg-{week}",
                                "team": team, "unit": "defense", "slot": slot,
                                "jersey": who.split(" ")[0], "player": player.split(" ", 1)[1],
                                "source_url": f"https://static.www.nfl.com/gb{week}.pdf",
                                "captured_utc": "2026-11-19T00:00:00Z"})
    write_csv(os.path.join(data, "lineups.csv"), lineups)

    write_csv(os.path.join(data, "inactives.csv"), [
        {"season": "2026", "week": "10", "slug": "a-at-b-2026-reg-10",
         "game_url": "https://www.nfl.com/games/a-at-b-2026-reg-10", "team": "AAA",
         "category": "not_active", "position": "WR", "jersey": "14", "player": "C.Player",
         "source_url": "https://static.www.nfl.com/gb10.pdf",
         "captured_utc": "2026-11-19T00:00:00Z"}])
    write_csv(os.path.join(data, "substitutions.csv"), [])
    write_csv(os.path.join(data, "roster_status.csv"), [
        {"season": "2026", "club": "AAA", "player": "C.Player", "jersey": "14", "position": "WR",
         "status": "RES", "height": "71", "weight": "195",
         "source_url": "https://www.nfl.com/teams/aaa/roster",
         "captured_utc": "2026-11-19T00:00:00Z"}])
    write_csv(os.path.join(data, "depth_sources.csv"), [
        {"season": "2026", "club": "AAA", "club_slug": "aaa",
         "roster_url": "https://www.nfl.com/teams/aaa/roster",
         "depth_url": "https://www.aaa.com/team/depth-chart", "depth_http_status": "200",
         "depth_sha256": "c" * 64, "depth_has_table": "yes", "depth_table_headers": "Position",
         "depth_image_count": "2", "depth_mentions_unofficial": "no",
         "depth_text_sample": "", "depth_image_srcs": "", "depth_date_label": "",
         "depth_parsed_rows": "2", "roster_rows": "1",
         "captured_utc": "2026-11-19T00:00:00Z", "note": ""},
        {"season": "2026", "club": "BBB", "club_slug": "bbb",
         "roster_url": "https://www.nfl.com/teams/bbb/roster",
         "depth_url": "https://www.bbb.com/team/depth-chart", "depth_http_status": "200",
         "depth_sha256": "d" * 64, "depth_has_table": "no", "depth_table_headers": "",
         "depth_image_count": "4", "depth_mentions_unofficial": "yes",
         "depth_text_sample": "", "depth_image_srcs": "", "depth_date_label": "",
         "depth_parsed_rows": "0", "roster_rows": "1",
         "captured_utc": "2026-11-19T00:00:00Z", "note": "chart is an image"}])
    write_csv(os.path.join(data, "depth_chart.csv"), [
        {"season": "2026", "club": "AAA", "club_slug": "aaa", "unit": "OFFENSE", "slot": "QB",
         "slot_ordinal": "1", "rank": "1", "tier": "1st string", "jersey": "7",
         "player": "A.Player", "raw_cell": "7 A.Player", "rank_collision": "no",
         "continuation_row": "no", "chart_date_label": "Nov. 10, 2026",
         "chart_labelled_unofficial": "no", "source_url": "https://www.aaa.com/team/depth-chart",
         "captured_utc": "2026-11-19T00:00:00Z"}])
    return data


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ag-analyze-")
        cls.data = build_fixture(cls.tmp)
        cls.sweep = os.path.join(cls.tmp, "sweep")
        os.makedirs(cls.sweep, exist_ok=True)
        write_csv(os.path.join(cls.sweep, "week10_rows_20261118.csv"), [
            {"team": "AAA", "game_date": "2026-11-15", "opponent": "BBB", "player": "C.Player",
             "position": "WR", "injuries": "", "practice_status": "Did Not Participate In Practice",
             "game_status": "Out", "player_url": "https://www.nfl.com/players/c-player/",
             "source_url": "https://www.nfl.com/injuries/league/2026/REG10",
             "fetched_utc": "2026-11-18T03:55:37Z"}])
        cls._old = (analyze.DATA, analyze.OUT, analyze.TEAM_OUT, analyze.SUMMARY_OUT,
                    analyze.FLAGS_OUT, analyze.SOURCES_OUT, analyze.SWEEP)
        analyze.DATA = cls.data
        analyze.OUT = os.path.join(cls.data, "availability_graph.csv")
        analyze.TEAM_OUT = os.path.join(cls.data, "team_view.csv")
        analyze.SUMMARY_OUT = os.path.join(cls.data, "summary.json")
        analyze.FLAGS_OUT = os.path.join(cls.data, "flags.json")
        analyze.SOURCES_OUT = os.path.join(cls.data, "sources.json")
        analyze.SWEEP = cls.sweep
        rc = analyze.main()
        assert rc == 0, "analysis failed"
        with open(analyze.OUT, newline="", encoding="utf-8") as fh:
            cls.graph = list(csv.DictReader(fh))
        with open(analyze.TEAM_OUT, newline="", encoding="utf-8") as fh:
            cls.teams = list(csv.DictReader(fh))
        with open(analyze.SUMMARY_OUT, encoding="utf-8") as fh:
            cls.summary = json.load(fh)

    @classmethod
    def tearDownClass(cls):
        (analyze.DATA, analyze.OUT, analyze.TEAM_OUT, analyze.SUMMARY_OUT,
         analyze.FLAGS_OUT, analyze.SOURCES_OUT, analyze.SWEEP) = cls._old
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_graph_has_one_row_per_slot(self):
        self.assertEqual(len(self.graph), 2 * 22)
        self.assertEqual(self.summary["slots_compared"], 2 * 22)

    def test_expected_and_actual_players_are_present(self):
        for r in self.graph:
            self.assertTrue(r["expected_player_wk9"])
            self.assertTrue(r["actual_player_wk10"])

    def test_changed_qb_is_detected(self):
        qb = [r for r in self.graph if r["team"] == "AAA" and r["slot"] == "QB"
              and r["unit"] == "offense"]
        self.assertEqual(len(qb), 1)
        self.assertEqual(qb[0]["expected_player_wk9"], "A.Player")
        self.assertEqual(qb[0]["actual_player_wk10"], "W.QB")
        self.assertEqual(qb[0]["changed"], "yes")
        self.assertEqual(qb[0]["replacement_named"], "yes")

    def test_designation_and_roster_status_are_joined_by_name(self):
        c = [r for r in self.graph if r["team"] == "AAA" and r["slot"] == "WR"
             and r["actual_player_wk10"] == "C.Player"]
        self.assertTrue(c)
        self.assertEqual(c[0]["actual_designation"], "Out")
        self.assertEqual(c[0]["actual_roster_status"], "RES")
        self.assertEqual(c[0]["actual_player_not_active"], "yes")

    def test_depth_tier_is_published_only_where_the_club_publishes_one(self):
        aaa = [r for r in self.graph if r["team"] == "AAA" and r["slot"] == "QB"]
        self.assertEqual(aaa[0]["expected_depth_tier"], "1st string")
        self.assertEqual(aaa[0]["expected_depth_source"], "https://www.aaa.com/team/depth-chart")
        bbb = [r for r in self.graph if r["team"] == "BBB"]
        self.assertTrue(all(r["expected_depth_tier"] == "" for r in bbb))
        self.assertTrue(all(r["expected_depth_source"] == "" for r in bbb))

    def test_blank_means_not_published_never_healthy(self):
        for r in self.graph:
            for key, value in r.items():
                self.assertNotIn("TBD", value)
                self.assertNotIn("Unknown", value)

    def test_team_view_counts(self):
        aaa = [t for t in self.teams if t["team"] == "AAA"][0]
        self.assertEqual(int(aaa["slots_compared"]), 22)
        self.assertEqual(int(aaa["slots_changed"]), 1)
        self.assertEqual(int(aaa["out_designated"]), 1)
        self.assertEqual(int(aaa["not_active"]), 1)
        self.assertIn("W.QB", aaa["replacements_named"])

    def test_flags_and_sources_are_written(self):
        with open(analyze.FLAGS_OUT, encoding="utf-8") as fh:
            flags = json.load(fh)["flags"]
        self.assertTrue(flags)
        for f in flags:
            self.assertTrue(f["finding"])
            self.assertTrue(f["handling"])
            self.assertTrue(f["sources"])
        with open(analyze.SOURCES_OUT, encoding="utf-8") as fh:
            sources = json.load(fh)["sources"]
        self.assertTrue(sources)
        for s in sources:
            self.assertTrue(s["url"].startswith("https://"))

    def test_name_key_normalisation(self):
        self.assertEqual(analyze.name_key("A.St. Brown"), analyze.name_key("Amon-Ra St. Brown"))
        self.assertNotEqual(analyze.name_key("A.St. Brown"), analyze.name_key("B.St. Brown"))


if __name__ == "__main__":
    unittest.main()
