#!/usr/bin/env python3
"""Parser tests for the official Game Book reader.

The fixtures are the official NFL Game Book for New England Patriots at Detroit Lions,
2026 REG 10, read first-hand on 2026-11-19 (see the fixture headers for the source URL).
The tests pin the parser to those official rows: a change in the parser that silently drops a
starter, a substitution or an inactive player fails here.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import capture_availability as cap  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
MD = os.path.join(FIX, "ne_det_2026_reg10_gamebook.md")
LAYOUT = os.path.join(FIX, "ne_det_2026_reg10_gamebook_layout.txt")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class HeadFieldTests(unittest.TestCase):
    def test_header_fields_from_layout(self):
        gb = cap.parse_gamebook(read(LAYOUT))
        self.assertEqual(gb["date_text"], "Sunday, 11/15/2026")
        self.assertEqual(gb["venue"], "Allianz Arena, Munich, Germany")
        self.assertEqual(gb["weather"], "Cloudy")
        self.assertEqual(gb["temp"], "52° F (11.1° C)")
        self.assertEqual(gb["humidity"], "51%")
        self.assertEqual(gb["wind"], "SE 3 mph")
        self.assertEqual(gb["roof"], "Open Stadium")
        self.assertEqual(gb["surface"], "Natural Grass")

    def test_header_fields_from_markdown(self):
        gb = cap.parse_gamebook(read(MD))
        self.assertEqual(gb["date_text"], "Sunday, 11/15/2026")
        self.assertEqual(gb["venue"], "Allianz Arena, Munich, Germany")
        self.assertEqual(gb["weather"], "Cloudy")
        self.assertEqual(gb["roof"], "Open Stadium")
        self.assertEqual(gb["surface"], "Natural Grass")


class LineupTests(unittest.TestCase):
    def _rows(self, text):
        gb = cap.parse_gamebook(text)
        self.assertTrue(gb["lineups"]["ok"], gb["lineups"]["note"])
        return gb["lineups"]["rows"]

    def test_layout_lineups(self):
        rows = self._rows(read(LAYOUT))
        self.assertEqual(len(rows), 44)          # 11 starters x 2 clubs x 2 units
        cols = {c: [r for r in rows if r["col"] == c] for c in range(4)}
        for c, name in ((0, "away offence"), (1, "away defence"),
                        (2, "home offence"), (3, "home defence")):
            self.assertEqual(len(cols[c]), 11, name)
        # away offence (col 0)
        self.assertEqual((cols[0][0]["pos"], cols[0][0]["num"], cols[0][0]["name"]),
                         ("LT", "66", "W.Campbell"))
        self.assertEqual((cols[0][7]["pos"], cols[0][7]["num"], cols[0][7]["name"]),
                         ("QB", "10", "D.Maye"))
        self.assertEqual((cols[0][8]["pos"], cols[0][8]["num"], cols[0][8]["name"]),
                         ("RB", "38", "R.Stevenson"))
        # away defence (col 1)
        self.assertEqual((cols[1][0]["pos"], cols[1][0]["num"], cols[1][0]["name"]),
                         ("OLB", "5", "Dr.Jones"))
        self.assertEqual((cols[1][10]["pos"], cols[1][10]["num"], cols[1][10]["name"]),
                         ("S", "31", "K.Byard"))
        # home offence (col 2)
        self.assertEqual((cols[2][0]["pos"], cols[2][0]["num"], cols[2][0]["name"]),
                         ("WR", "18", "I.TeSlaa"))
        self.assertEqual((cols[2][9]["pos"], cols[2][9]["num"], cols[2][9]["name"]),
                         ("QB", "16", "J.Goff"))
        self.assertEqual((cols[2][10]["pos"], cols[2][10]["num"], cols[2][10]["name"]),
                         ("RB", "0", "J.Gibbs"))
        self.assertEqual([r["name"] for r in cols[2] if r["pos"] == "WR"],
                         ["I.TeSlaa", "J.Williams", "A.St. Brown"])
        # home defence (col 3)
        self.assertEqual((cols[3][0]["pos"], cols[3][0]["num"], cols[3][0]["name"]),
                         ("DE", "97", "A.Hutchinson"))
        self.assertEqual([r["name"] for r in cols[3] if r["pos"] == "CB"], ["R.Ya-Sin", "R.McCreary"])

    def test_markdown_lineups(self):
        rows = self._rows(read(MD))
        self.assertEqual(len(rows), 44)
        cols = {c: [r for r in rows if r["col"] == c] for c in range(4)}
        self.assertEqual((cols[0][0]["num"], cols[0][0]["name"]), ("66", "W.Campbell"))
        self.assertEqual([r["name"] for r in cols[2] if r["pos"] == "QB"], ["J.Goff"])
        self.assertEqual([r["name"] for r in cols[2] if r["pos"] == "WR"],
                         ["I.TeSlaa", "J.Williams", "A.St. Brown"])

    def test_never_invents_a_starter(self):
        gb = cap.parse_gamebook("National Football League Game Summary\nnothing useful here\n")
        self.assertFalse(gb["lineups"]["ok"])
        self.assertEqual(gb["lineups"]["rows"], [])


class SectionTests(unittest.TestCase):
    def test_not_active_lists(self):
        gb = cap.parse_gamebook(read(LAYOUT))
        sec = gb["sections"]["not_active"]
        self.assertTrue(sec["ok"])
        away = [p["name"] for p in sec["away"]]
        home = [p["name"] for p in sec["home"]]
        self.assertEqual(away, ["C.Davis", "B.Morton", "B.Schooler", "D.Crownover", "W.Rouse", "B.Brown"])
        self.assertEqual(home, ["D.Reed", "K.Abney", "A.Ogbongbemiga", "C.Mays", "M.Wingo", "A.Hassanein"])
        self.assertEqual(sec["away"][0]["pos"], "CB")
        self.assertEqual(sec["away"][1]["pos"], "3QB")

    def test_substitution_lists(self):
        gb = cap.parse_gamebook(read(LAYOUT))
        sec = gb["sections"]["substitutions"]
        self.assertTrue(sec["ok"])
        self.assertEqual(len(sec["away"]), 26)
        self.assertEqual(len(sec["home"]), 26)
        self.assertEqual(sec["away"][0]["name"], "D.Douglas")
        self.assertEqual(sec["away"][-1]["name"], "Da.Jones")
        self.assertEqual(sec["home"][0]["name"], "E.Rakestraw")
        self.assertEqual(sec["home"][-1]["name"], "D.Wonnum")

    def test_did_not_play_is_empty_not_invented(self):
        gb = cap.parse_gamebook(read(LAYOUT))
        sec = gb["sections"]["did_not_play"]
        self.assertTrue(sec["ok"])
        self.assertEqual(sec["away"], [])
        self.assertEqual(sec["home"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
