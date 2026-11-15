"""Tests for scripts/capture/capture_injury_reports.py.

The HTML fixtures below are SYNTHETIC. They imitate the structure of the NFL.com injury page
(a club logo before each team table, the pinned five-column header) so the parser's rules can
be tested offline. They are not NFL data and no value in them is published anywhere.
The real page is captured by .github/workflows/capture-injury-reports.yml.

Run:  python -m unittest tests.test_capture_parser -v
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "capture"))

import capture_injury_reports as cap  # noqa: E402

HEADER = "<tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>"


def team_table(rows_html: str, header: str = HEADER) -> str:
    return f"<table>{header}{rows_html}</table>"


def row(name, pos, inj, prac, game) -> str:
    return (f"<tr><td><a href='https://www.nfl.com/players/x/'>{name}</a></td><td>{pos}</td>"
            f"<td>{inj}</td><td>{prac}</td><td>{game}</td></tr>")


SYNTH_PAGE = (
    "<html><head><script>var x='clubs/logos/KC';</script></head><body>"
    "<h2>THURSDAY, NOVEMBER 12TH</h2>"
    "<img src='https://static.example/clubs/logos/WAS'><span>Commanders</span>"
    "<img src='https://static.example/clubs/logos/NYG'><span>Giants</span>"
    + team_table(row("Synth Alpha", "C", "Knee", "Did Not Participate In Practice", "Out")
                 + row("Synth Beta", "WR", "", "Full Participation in Practice", "")) +
    "<h3>Giants</h3>" + team_table(row("Synth Gamma", "LB", "Groin", "Limited Participation in Practice", "Questionable")
                                   + row("Synth Delta", "CB", "", "Did Not Participate In Practice", "")) +
    "</body></html>"
)


class ParserTests(unittest.TestCase):
    def test_tables_are_attributed_in_document_order(self):
        doc = cap.parse_report(SYNTH_PAGE, 2026, 10)
        teams = [r["team"] for r in doc["rows"]]
        self.assertEqual(teams, ["WAS", "WAS", "NYG", "NYG"])
        self.assertEqual(doc["tables"], 2)
        self.assertEqual(doc["alarms"], [])

    def test_script_text_is_ignored(self):
        # 'clubs/logos/KC' appears only inside <script>; it must not create a team.
        doc = cap.parse_report(SYNTH_PAGE, 2026, 10)
        self.assertNotIn("KC", [t["team"] for t in doc["teams"]])

    def test_pinned_header_mismatch_raises_alarm(self):
        bad = SYNTH_PAGE.replace("<th>Game Status</th>", "<th>Status</th>", 1)
        doc = cap.parse_report(bad, 2026, 10)
        self.assertTrue(any("header" in a for a in doc["alarms"]), doc["alarms"])

    def test_malformed_row_raises_alarm(self):
        bad = SYNTH_PAGE.replace("<td>WR</td>", "", 1)
        doc = cap.parse_report(bad, 2026, 10)
        self.assertTrue(any("malformed row" in a for a in doc["alarms"]), doc["alarms"])

    def test_table_without_club_raises_alarm(self):
        html = "<html><body>" + team_table(row("Synth Epsilon", "S", "", "Full Participation in Practice", "")) + "</body></html>"
        doc = cap.parse_report(html, 2026, 10)
        self.assertTrue(any("no club" in a for a in doc["alarms"]), doc["alarms"])

    def test_flags_dnp_without_game_status_and_duplicates(self):
        # Synth Beta is renamed to Synth Alpha inside the WAS table only: a same-team duplicate.
        dup = SYNTH_PAGE.replace("Synth Beta", "Synth Alpha", 1)
        doc = cap.parse_report(dup, 2026, 10)
        self.assertIn("duplicate_player:WAS:Synth Alpha", doc["flags"])
        self.assertIn("dnp_without_game_status:NYG:Synth Delta", doc["flags"])
        self.assertNotIn("dnp_without_game_status:WAS:Synth Alpha", doc["flags"])


class ContentHashTests(unittest.TestCase):
    def test_byte_only_noise_keeps_content_hash(self):
        noisy = SYNTH_PAGE.replace("<body>", "<body><p data-jsonid=\"0000-1111\"></p>", 1)
        a = cap.parse_report(SYNTH_PAGE, 2026, 10)["content_sha256"]
        b = cap.parse_report(noisy, 2026, 10)["content_sha256"]
        self.assertEqual(a, b)
        self.assertNotEqual(hashlib.sha256(SYNTH_PAGE.encode()).hexdigest(),
                            hashlib.sha256(noisy.encode()).hexdigest())

    def test_designation_change_changes_content_hash(self):
        changed = SYNTH_PAGE.replace("<td>Out</td>", "<td>Questionable</td>", 1)
        self.assertNotEqual(cap.parse_report(SYNTH_PAGE, 2026, 10)["content_sha256"],
                            cap.parse_report(changed, 2026, 10)["content_sha256"])


class AliasAndWeekTests(unittest.TestCase):
    def test_page_abbreviations_AZ_and_LA_map_to_their_clubs(self):
        html = ("<html><body><h3>Injuries - WEEK 10</h3>"
                "<img src='https://x/clubs/logos/AZ'><span>Cardinals</span>"
                "<img src='https://x/clubs/logos/LA'><span>Rams</span>"
                + team_table(row("Synth Zeta", "QB", "", "Full Participation in Practice", ""))
                + team_table(row("Synth Eta", "RB", "", "Full Participation in Practice", "")) +
                "</body></html>")
        doc = cap.parse_report(html, 2026, 10)
        self.assertEqual([r["team"] for r in doc["rows"]], ["AZ", "LA"])
        self.assertEqual(doc["alarms"], [])
        self.assertEqual(doc["declared_week"], 10)

    def test_week_echo_is_flagged_not_parsed_as_requested_week(self):
        echo = SYNTH_PAGE.replace("<html>", "<html><h3>Injuries - WEEK 10</h3>", 1)
        doc = cap.parse_report(echo, 2026, 11)
        self.assertEqual(doc["declared_week"], 10)
        self.assertTrue(any(f.startswith("week_mismatch") for f in doc["flags"]), doc["flags"])

    def test_static_title_is_reported_not_trusted(self):
        html = ("<html><head><title>Official NFL Injury Report for Players - Week 10 of the 2026 Season | NFL.com</title></head>"
                "<body><h3>Injuries - WEEK 1</h3></body></html>")
        doc = cap.parse_report(html, 2026, 1)
        self.assertTrue(any(f.startswith("title_week_static") for f in doc["flags"]), doc["flags"])


class DiffTests(unittest.TestCase):
    def test_changed_added_removed(self):
        old = {"rows": [
            {"team": "WAS", "player": "A", "injuries": "Knee", "practice_status": "Limited", "game_status": "Questionable"},
            {"team": "WAS", "player": "B", "injuries": "", "practice_status": "Full", "game_status": ""},
        ]}
        new = {"rows": [
            {"team": "WAS", "player": "A", "injuries": "Knee", "practice_status": "Did Not Participate", "game_status": "Out"},
            {"team": "WAS", "player": "C", "injuries": "", "practice_status": "Full", "game_status": ""},
        ]}
        ch = cap.diff_rows(old, new)
        kinds = sorted((c["player"], c["change"], c["field"]) for c in ch)
        self.assertEqual(kinds, [
            ("A", "changed", "game_status"), ("A", "changed", "practice_status"),
            ("B", "removed", None), ("C", "added", None)])


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_once_refuses_different_content(self):
        p = os.path.join(self.tmp, "f.bin")
        self.assertTrue(cap.write_once(p, b"one"))
        self.assertFalse(cap.write_once(p, b"one"))
        with self.assertRaises(RuntimeError):
            cap.write_once(p, b"two")

    def _run(self, pages: dict[int, tuple[int, bytes]], extra_args=()):
        def fake_fetch(url, timeout=60):
            week = int(url.rsplit("reg", 1)[1])
            return pages.get(week, (404, b""))[0], pages.get(week, (404, b""))[1], {"Date": "Sun, 15 Nov 2026 18:00:00 GMT"}
        argv = ["--root", self.tmp, "--season", "2026", "--weeks", ",".join(map(str, pages)) or "1", "--pause", "0"]
        with mock.patch.object(cap, "fetch", side_effect=fake_fetch):
            return cap.main(argv + list(extra_args))

    def test_end_to_end_capture_manifest_and_delta(self):
        body1 = SYNTH_PAGE.encode()
        self.assertEqual(self._run({10: (200, body1)}), 0)
        changed = SYNTH_PAGE.replace("<td>Out</td>", "<td>Questionable</td>", 1)
        body2 = changed.encode()
        self.assertEqual(self._run({10: (200, body2)}), 0)
        manifest = jsonl(os.path.join(self.tmp, cap.DATA_REL, "manifest.jsonl"))
        self.assertEqual(len(manifest), 2)  # one line per fetch, never rewritten
        self.assertEqual(manifest[0]["sha256"], hashlib.sha256(body1).hexdigest())
        self.assertTrue(all(m["captured_at_utc"].endswith("Z") for m in manifest))
        bodies = os.listdir(os.path.join(self.tmp, cap.DATA_REL, "bodies"))
        self.assertEqual(len(bodies), 2)  # content-addressed, stored once each
        with gzip.open(os.path.join(self.tmp, cap.DATA_REL, "bodies", manifest[0]["body_file"].split("/")[1]), "rb") as fh:
            self.assertEqual(fh.read(), body1)
        deltas = jsonl(os.path.join(self.tmp, cap.DATA_REL, "deltas.jsonl"))
        self.assertTrue(any(d["field"] == "game_status" and d["before"] == "Out" for d in deltas), deltas)

    def test_alarm_exits_nonzero_and_keeps_raw_body(self):
        bad = SYNTH_PAGE.replace("<th>Game Status</th>", "<th>Status</th>", 1).encode()
        self.assertEqual(self._run({10: (200, bad)}), 1)
        manifest = jsonl(os.path.join(self.tmp, cap.DATA_REL, "manifest.jsonl"))
        self.assertTrue(manifest[0]["alarm"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, cap.DATA_REL, "bodies", manifest[0]["body_file"].split("/")[1])))

    def test_page_that_lost_its_tables_raises_alarm(self):
        self.assertEqual(self._run({10: (200, SYNTH_PAGE.encode())}), 0)
        empty = b"<html><body><h1>2026 NFL Injury Report</h1>No data here</body></html>"
        self.assertEqual(self._run({10: (200, empty)}), 1)

    def test_all_fetches_failed_is_an_alarm(self):
        self.assertEqual(self._run({18: (404, b"")}), 1)

    def test_unpublished_week_is_not_an_alarm(self):
        self.assertEqual(self._run({18: (404, b""), 17: (200, SYNTH_PAGE.encode())}), 0)


if __name__ == "__main__":
    unittest.main()
