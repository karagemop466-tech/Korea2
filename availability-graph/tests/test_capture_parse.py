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


class DepthChartTests(unittest.TestCase):
    """The Packers depth chart is the named parsing case: jersey numbers are prepended to the
    name, one slot continues on a second row and one slot is published empty."""

    def setUp(self):
        html = read(os.path.join(FIX, "packers_depth_chart.html"))
        self.rows, self.meta = cap.parse_depth_chart(html)

    def _find(self, unit, slot, ordinal, rank):
        for r in self.rows:
            if (r["unit"], r["slot"], r["slot_ordinal"], r["rank"]) == (unit, slot, ordinal, rank):
                return r
        return None

    def test_metadata(self):
        self.assertTrue(self.meta["mentions_unofficial"])
        self.assertEqual(self.meta["date_label"], "Nov. 10, 2026")
        self.assertEqual(self.meta["tables"], 3)

    def test_jersey_number_is_split_off_but_kept(self):
        r = self._find("OFFENSE", "WR", 1, 1)
        self.assertIsNotNone(r)
        self.assertEqual(r["player"], "Christian Watson")
        self.assertEqual(r["jersey"], "9")
        self.assertEqual(r["raw_cell"], "9 Christian Watson")
        self.assertEqual(r["tier"], "1st string")

    def test_shared_slot_is_kept_as_two_slots(self):
        # The club publishes three receiver rows; they are three slots, not one slot with three
        # names, and they must not be collapsed.
        self.assertIsNotNone(self._find("OFFENSE", "WR", 1, 1))
        self.assertIsNotNone(self._find("OFFENSE", "WR", 2, 1))
        self.assertIsNotNone(self._find("OFFENSE", "WR", 3, 1))
        self.assertEqual(self._find("OFFENSE", "WR", 3, 1)["player"], "Savion Williams")

    def test_continuation_row_keeps_the_slot_and_adds_a_fourth_rank(self):
        r = self._find("OFFENSE", "RB", 1, 4)
        self.assertIsNotNone(r)
        self.assertEqual(r["player"], "Kaleb Johnson")
        self.assertEqual(r["tier"], "4th string")

    def test_empty_slot_stays_empty(self):
        # The returner row publishes no first-string player; the cell is not filled in.
        self.assertIsNone(self._find("SPECIAL TEAMS", "PR", 1, 1))
        r = self._find("SPECIAL TEAMS", "PR", 1, 2)
        self.assertIsNotNone(r)
        self.assertEqual(r["player"], "Matthew Golden")

    def test_no_rank_is_invented_for_an_empty_cell(self):
        self.assertIsNone(self._find("OFFENSE", "LT", 1, 3))
        self.assertIsNone(self._find("DEFENSE", "S", 1, 3))


class FixedWidthLineupTests(unittest.TestCase):
    """The masked fixture is the real runner output of `pdftotext -layout`.

    It keeps the official column offsets, position labels and jersey numbers of a real NFL Game
    Book and masks only the player names.
    """

    def setUp(self):
        text = read(os.path.join(FIX, "gamebook_lineups_layout_masked.txt"))
        self.result = cap.parse_lineups(text)

    def test_the_fixed_width_layout_is_parsed(self):
        self.assertTrue(self.result["ok"], self.result["note"])
        self.assertEqual(self.result["per_column"], [11, 11, 11, 11])

    def test_every_cell_is_a_position_a_number_and_a_name(self):
        for r in self.result["rows"]:
            self.assertTrue(r["pos"], "cell without a position")
            self.assertTrue(r["num"].isdigit(), f"cell with a bad jersey number {r['num']!r}")
            self.assertTrue(r["name"], "cell without a name")

    def test_the_four_columns_map_to_the_four_units(self):
        units = {}
        for r in self.result["rows"]:
            units.setdefault(r["col"], set()).add(r["unit"])
        self.assertEqual(units[0], {"offense"})
        self.assertEqual(units[1], {"defense"})
        self.assertEqual(units[2], {"offense"})
        self.assertEqual(units[3], {"defense"})

    def test_the_official_positions_and_numbers_are_kept(self):
        qb = [r for r in self.result["rows"] if r["col"] == 2 and r["pos"] == "QB"]
        self.assertEqual(len(qb), 1)
        self.assertEqual(qb[0]["num"], "4")
        self.assertEqual(len(qb[0]["name"]), 10)          # the mask keeps the official length

    def test_a_row_that_leaves_the_table_stops_the_parse(self):
        # The fixture ends with a trailing row that is not a lineup row.
        self.assertEqual(len(self.result["rows"]), 44)


class GameBookHeaderTests(unittest.TestCase):
    """The header fields of the official game book: date, venue, roof, surface and weather."""

    def setUp(self):
        self.md = cap.parse_gamebook(read(os.path.join(FIX, "ne_det_2026_reg10_gamebook.md")))
        self.txt = cap.parse_gamebook(read(os.path.join(FIX, "ne_det_2026_reg10_gamebook_layout.txt")))

    def test_the_two_official_renderings_agree(self):
        for key in ("date_text", "away_printed", "home_printed", "venue", "start_time",
                    "weather", "temp", "humidity", "wind", "roof", "surface"):
            self.assertEqual(self.md[key], self.txt[key], f"{key} differs between the renderings")

    def test_the_verified_header_values(self):
        self.assertEqual(self.md["date_text"], "Sunday, 11/15/2026")
        self.assertEqual(self.md["away_printed"], "New England Patriots")
        self.assertEqual(self.md["home_printed"], "Detroit Lions")
        self.assertEqual(self.md["venue"], "Allianz Arena, Munich, Germany")
        self.assertEqual(self.md["start_time"], "3:33 PM CET")
        self.assertEqual(self.md["weather"], "Cloudy")
        self.assertEqual(self.md["temp"], "52° F (11.1° C)")
        self.assertEqual(self.md["humidity"], "51%")
        self.assertEqual(self.md["wind"], "SE 3 mph")
        self.assertEqual(self.md["roof"], "Open Stadium")
        self.assertEqual(self.md["surface"], "Natural Grass")

    def test_no_field_is_invented(self):
        for value in (self.md["weather"], self.md["temp"], self.md["humidity"], self.md["wind"]):
            self.assertNotIn("TBD", value)
            self.assertNotIn("N/A", value)


class ClubNicknameTests(unittest.TestCase):
    """The official schedule page and the official game URL use the short club name."""

    def test_every_club_has_a_unique_nickname(self):
        self.assertEqual(len(cap.NICKNAME_TO_ABBR), 32)
        self.assertEqual(len(set(cap.NICKNAME_TO_ABBR.values())), 32)

    def test_the_nickname_is_the_last_word_of_the_official_name(self):
        self.assertEqual(cap.NICKNAME_TO_ABBR["steelers"], "PIT")
        self.assertEqual(cap.NICKNAME_TO_ABBR["49ers"], "SF")
        self.assertEqual(cap.NICKNAME_TO_ABBR["commanders"], "WAS")
        self.assertEqual(cap.NICKNAME_TO_ABBR["buccaneers"], "TB")


class ScheduleParseTests(unittest.TestCase):
    """The official schedule page prints the short club names and the official score."""

    def _one(self, html, season="2026", week="10"):
        games = cap.parse_schedule(html, season, week)
        self.assertEqual(len(games), 1)
        return games[0]

    def test_the_official_score_is_attached_to_the_right_game(self):
        g = self._one(
            '<a href="/games/steelers-at-bengals-2026-reg-10">'
            'Steelers 18, Bengals 38, FINAL, Sunday, November 15th</a>')
        self.assertEqual(g["away_team"], "PIT")
        self.assertEqual(g["home_team"], "CIN")
        self.assertEqual(g["away_score"], "18")
        self.assertEqual(g["home_score"], "38")
        self.assertEqual(g["status"], "FINAL")

    def test_a_club_name_that_starts_with_digits(self):
        g = self._one(
            '<a href="/games/49ers-at-cowboys-2026-reg-10">'
            '49ers 10, Cowboys 27, FINAL, Sunday, November 15th</a>')
        self.assertEqual(g["away_team"], "SF")
        self.assertEqual(g["home_team"], "DAL")
        self.assertEqual(g["away_score"], "10")

    def test_a_score_is_never_attached_to_the_wrong_game(self):
        games = cap.parse_schedule(
            '<a href="/games/steelers-at-bengals-2026-reg-10">'
            'Steelers 18, Bengals 38, FINAL</a>'
            '<a href="/games/chargers-at-ravens-2026-reg-10">'
            'Chargers 23, Ravens 20, FINAL</a>', "2026", "10")
        self.assertEqual(len(games), 2)
        for g in games:
            self.assertTrue(g["away_score"], f"{g['slug']} has no score")
            self.assertTrue(g["home_score"], f"{g['slug']} has no score")

    def test_an_unfinished_game_has_no_score(self):
        g = self._one('<a href="/games/bills-at-jets-2026-reg-10">'
                      'Bills at Jets, Sunday, November 15th</a>')
        self.assertEqual(g["away_team"], "BUF")
        self.assertEqual(g["home_team"], "NYJ")
        self.assertEqual(g["away_score"], "")
        self.assertEqual(g["home_score"], "")

    def test_the_week_filter_is_applied(self):
        games = cap.parse_schedule(
            '<a href="/games/steelers-at-bengals-2026-reg-10">Steelers 18, Bengals 38</a>'
            '<a href="/games/bills-at-jets-2026-reg-9">Bills 20, Jets 17</a>', "2026", "9")
        self.assertEqual([g["slug"] for g in games], ["bills-at-jets-2026-reg-9"])
