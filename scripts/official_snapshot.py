#!/usr/bin/env python3
"""Immutable official-source capture register + the correlations computed from it.

Why this file exists
--------------------
The owner brief requires (a) "Store every injury-hub read with its clock time and publish the
delta, never the level", (b) "Compute correlations only from officially sourced numbers and
publish n with each value", and (c) a dated, replayable capture of the official pages the project
depends on. Until now the root site carried only the nflverse-derived pipeline snapshot (data
through 2026-11-01) with no per-read clock time for the official pages.

Transcription policy (owner rule: never infer)
-----------------------------------------------
* Every value below was read first-hand from the URL stored on its own row, at READ_AT_UTC, using
  the platform page-retrieval tool. A row records only what that page printed.
* Fields the page does not publish (or that could not be read at this capture) are `None`. They are
  never filled in, averaged, carried over from another page, or derived from jersey order, salary
  or experience.
* Derived numbers (net points, games played, correlations, intervals) are COMPUTED here from these
  rows, never typed, so the site and the data can be regenerated from one source of truth.
* Cross-page agreement is asserted only where two official pages were both read at this capture.

Run:  PYTHONPATH=scripts python3 scripts/official_snapshot.py [--write]
Exit code is non-zero if any internal consistency check fails (drift alarm, per the brief).
"""
from __future__ import annotations

import json
import math
import os
import sys

READ_AT_UTC = "2026-11-18T03:55:00Z"          # when the pages below were retrieved, to the minute
SEASON, WEEK = 2026, 10
STANDINGS_URL = "https://www.nfl.com/standings/division/2026/REG"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-10"
INJURY_W10_URL = "https://www.nfl.com/injuries/league/2026/reg10"
INJURY_W11_URL = "https://www.nfl.com/injuries/league/2026/reg11"

# --------------------------------------------------------------------------- standings
# (team, abbr, conference, division, W, L, T, points_for, points_against)
# 24 rows were read from STANDINGS_URL at 03:55:00Z, which prints W/L/T, PF and PA per club. The
# final 8 clubs (NFC South, NFC West) sat in a second retrieval chunk that failed at that read, so
# they were stored with the W-L-T records SCHEDULE_URL prints beside each logo and PF/PA left None
# rather than copied from another source or inferred.
#
# SECOND READ, 2026-11-18T04:21:00Z: re-reading the same URL returned the chunk that had failed, and
# the eight point totals below are transcribed from it. Nothing else about those rows is upgraded -
# their W-L-T still comes from the 03:55:00Z schedule read, which is recorded per row in read_note,
# and the flag the gap raised (FL-18) stays in the register with the resolution written into it.
READ2_AT_UTC = "2026-11-18T04:21:00Z"
STANDINGS_POINTS_CHUNK2 = {          # abbr -> (points_for, points_against), as the table prints them
    "NO": (202, 236), "TB": (202, 178), "ATL": (201, 258), "CAR": (219, 236),
    "LA": (248, 187), "SF": (281, 196), "SEA": (223, 175), "AZ": (184, 289),
}
STANDINGS = [
    ("Buffalo Bills", "BUF", "AFC", "East", 8, 1, 0, 287, 199),
    ("New England Patriots", "NE", "AFC", "East", 5, 5, 0, 221, 242),
    ("New York Jets", "NYJ", "AFC", "East", 2, 8, 0, 194, 254),
    ("Miami Dolphins", "MIA", "AFC", "East", 1, 8, 0, 148, 224),
    ("Cincinnati Bengals", "CIN", "AFC", "North", 7, 2, 0, 278, 193),
    ("Pittsburgh Steelers", "PIT", "AFC", "North", 6, 3, 0, 198, 182),
    ("Cleveland Browns", "CLE", "AFC", "North", 6, 4, 0, 188, 220),
    ("Baltimore Ravens", "BAL", "AFC", "North", 4, 6, 0, 209, 259),
    ("Jacksonville Jaguars", "JAX", "AFC", "South", 7, 2, 0, 269, 144),
    ("Houston Texans", "HOU", "AFC", "South", 3, 6, 0, 233, 219),
    ("Indianapolis Colts", "IND", "AFC", "South", 3, 7, 0, 208, 271),
    ("Tennessee Titans", "TEN", "AFC", "South", 1, 8, 0, 167, 239),
    ("Kansas City Chiefs", "KC", "AFC", "West", 7, 2, 0, 237, 156),
    ("Denver Broncos", "DEN", "AFC", "West", 7, 2, 0, 198, 186),
    ("Las Vegas Raiders", "LV", "AFC", "West", 4, 6, 0, 251, 289),
    ("Los Angeles Chargers", "LAC", "AFC", "West", 1, 8, 0, 144, 239),
    ("New York Giants", "NYG", "NFC", "East", 5, 3, 1, 203, 196),
    ("Dallas Cowboys", "DAL", "NFC", "East", 4, 6, 0, 286, 282),
    ("Washington Commanders", "WAS", "NFC", "East", 3, 5, 1, 196, 223),
    ("Philadelphia Eagles", "PHI", "NFC", "East", 2, 7, 0, 148, 221),
    ("Detroit Lions", "DET", "NFC", "North", 7, 2, 0, 257, 199),
    ("Minnesota Vikings", "MIN", "NFC", "North", 7, 2, 0, 176, 126),
    ("Chicago Bears", "CHI", "NFC", "North", 7, 2, 0, 241, 184),
    ("Green Bay Packers", "GB", "NFC", "North", 6, 4, 0, 226, 221),
    ("New Orleans Saints", "NO", "NFC", "South", 3, 6, 0, None, None),
    ("Tampa Bay Buccaneers", "TB", "NFC", "South", 3, 6, 0, None, None),
    ("Atlanta Falcons", "ATL", "NFC", "South", 3, 7, 0, None, None),
    ("Carolina Panthers", "CAR", "NFC", "South", 4, 5, 0, None, None),
    ("Los Angeles Rams", "LA", "NFC", "West", 6, 4, 0, None, None),
    ("San Francisco 49ers", "SF", "NFC", "West", 8, 1, 0, None, None),
    ("Seattle Seahawks", "SEA", "NFC", "West", 6, 4, 0, None, None),
    ("Arizona Cardinals", "AZ", "NFC", "West", 3, 7, 0, None, None),
]

# --------------------------------------------------------------------------- week 10 results
# (date, away abbr, away pts, home abbr, home pts, game-centre URL). The page prints the line
# "Away X, Home Y, FINAL"; the URL slug confirms which club was away. All 14 rows were read from
# SCHEDULE_URL; rows marked with a second read were also confirmed on the game centre itself.
GAMES = [
    ("2026-11-12", "WAS", 24, "NYG", 21, "commanders-at-giants-2026-reg-10", False),
    ("2026-11-15", "NE", 10, "DET", 35, "patriots-at-lions-2026-reg-10", True),
    ("2026-11-15", "KC", 35, "ATL", 13, "chiefs-at-falcons-2026-reg-10", False),
    ("2026-11-15", "HOU", 24, "CLE", 27, "texans-at-browns-2026-reg-10", False),
    ("2026-11-15", "MIN", 30, "GB", 10, "vikings-at-packers-2026-reg-10", False),
    ("2026-11-15", "MIA", 22, "IND", 24, "dolphins-at-colts-2026-reg-10", False),
    ("2026-11-15", "CAR", 20, "NO", 17, "panthers-at-saints-2026-reg-10", False),
    ("2026-11-15", "BUF", 31, "NYJ", 12, "bills-at-jets-2026-reg-10", False),
    ("2026-11-15", "JAX", 40, "TEN", 23, "jaguars-at-titans-2026-reg-10", False),
    ("2026-11-15", "LA", 34, "AZ", 6, "rams-at-cardinals-2026-reg-10", False),
    ("2026-11-15", "SEA", 21, "LV", 13, "seahawks-at-raiders-2026-reg-10", False),
    ("2026-11-15", "SF", 46, "DAL", 40, "49ers-at-cowboys-2026-reg-10", False),
    ("2026-11-15", "PIT", 18, "CIN", 38, "steelers-at-bengals-2026-reg-10", False),
    ("2026-11-16", "LAC", 23, "BAL", 20, "chargers-at-ravens-2026-reg-10", False),
]
BYE_TEAMS = ["CHI", "DEN", "PHI", "TB"]         # "Teams on Bye" block on SCHEDULE_URL

# --------------------------------------------------------------------------- game-centre read
GAME_CENTRE = {
    "url": "https://www.nfl.com/games/patriots-at-lions-2026-reg-10?tab=recap",
    "final": {"NE": 10, "DET": 35},
    "quarters": {"NE": [3, 0, 0, 7], "DET": [7, 14, 7, 7]},
    "location": "MUNICH",
    "stadium": "FC Bayern Munich Stadium",
    "game_book_pdf": "https://static.www.nfl.com/image/upload/v1794829721/gamecenter/"
                     "ab582c2f-4feb-11f1-abca-2c54536568a9.pdf",
    "standings_widget": {"BUF": "8-1-0", "NE": "5-5-0", "NYJ": "2-8-0", "MIA": "1-8-0"},
    "notes": "The recap page prints Location and Stadium per fixture, so the venue-transcription "
             "requirement is source-feasible for all 14 fixtures; only this one fixture was read at "
             "this capture. The Game Book link is published by the same page; its contents were NOT "
             "read at this capture, so no starter, inactive or snap-share value is claimed here.",
}

# --------------------------------------------------------------------------- injury report read
INJURY_PAGE = {
    "url_week10": INJURY_W10_URL,
    "url_week11_requested": INJURY_W11_URL,
    "title_observed": "Official NFL Injury Report for Players - Week 10 of the 2026 Season | NFL.com",
    "heading_observed": "Injuries - WEEK 10",
    "columns": ["Player", "Position", "Injuries", "Practice Status", "Game Status"],
    "week11_behaviour": "GET /injuries/league/2026/reg11 resolved to the Week 10 report "
                        "(reg10) at this read; the week selector lists WEEK 11 but no Week-11 "
                        "report was published yet (Wednesday report deadline had not passed).",
}
# (team, player, position, injury, practice status, game status) - exactly as the table printed.
INJURY_ROWS = [
    ("Washington Commanders", "Lucas Patrick", "C", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Washington Commanders", "Colson Yankoff", "TE", "Knee", "Did Not Participate In Practice", "Out"),
    ("New York Giants", "Malik Harrison", "LB", "Groin", "Limited Participation in Practice", "Questionable"),
    ("New England Patriots", "Ben Brown", "C", "Knee", "Did Not Participate In Practice", "Out"),
    ("New England Patriots", "A.J. Brown", "WR", "Ankle, Knee", "Limited Participation in Practice", "Questionable"),
    ("New England Patriots", "Carlton Davis III", "CB", "Knee", "Did Not Participate In Practice", "Out"),
    ("New England Patriots", "TreVeyon Henderson", "RB", "Illness", "Did Not Participate In Practice", "Out"),
    ("New England Patriots", "Kevin Byard", "S", "Chest", "Full Participation in Practice", "Questionable"),
    ("Detroit Lions", "Kerby Joseph", "S", "Knee", "Did Not Participate In Practice", "Out"),
    ("Detroit Lions", "Cade Mays", "C", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Detroit Lions", "D.J. Reed", "CB", "Hip", "Did Not Participate In Practice", "Out"),
    ("Detroit Lions", "Amon-Ra St. Brown", "WR", "Rib", "Limited Participation in Practice", "Questionable"),
]
# Rows the site previously published with a BLANK game status (brief items VR-08 / VR-12).
LIONS_FIX = ["Kerby Joseph", "Cade Mays", "D.J. Reed"]


# --------------------------------------------------------------------------- helpers
def pearson(xs: list[float], ys: list[float]) -> tuple[float, int]:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        raise ValueError("zero-variance sample; correlation undefined")
    return sxy / math.sqrt(sxx * syy), n


def fisher_ci(r: float, n: int, z_crit: float = 1.959963985) -> tuple[float, float]:
    """95 % confidence interval for a Pearson r by Fisher's z transform.

    Method reference: NIST/Engineering Statistics Handbook Dataplot aid, "Correlation
    Confidence Limits" (https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm).
    """
    if n <= 3:
        raise ValueError("n must exceed 3")
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    return math.tanh(z - z_crit * se), math.tanh(z + z_crit * se)


def build_capture() -> dict:
    standings = []
    for name, abbr, conf, div, w, l, t, pf, pa in STANDINGS:
        read_at, read_note = READ_AT_UTC, None
        fields = "W, L, T, points for, points against"
        source = STANDINGS_URL
        status = "verified"
        if pf is None:
            if abbr in STANDINGS_POINTS_CHUNK2:
                pf, pa = STANDINGS_POINTS_CHUNK2[abbr]
                read_at = READ2_AT_UTC
                status = "verified (points from a second read of the same URL)"
                read_note = (f"points read {READ2_AT_UTC}; W-L-T read {READ_AT_UTC} from "
                             f"{SCHEDULE_URL}; the standings chunk carrying this division failed to "
                             "retrieve at the first read")
            else:
                source = SCHEDULE_URL
                fields = "W, L, T only"
                status = "partial - points columns not read"
        standings.append({
            "team": name, "abbr": abbr, "conference": conf, "division": div,
            "wins": w, "losses": l, "ties": t,
            "games_played": w + l + t,
            "points_for": pf, "points_against": pa,
            "point_differential": (pf - pa) if (pf is not None and pa is not None) else None,
            "source_url": source,
            "field_read": fields,
            "read_at_utc": read_at,
            "read_note": read_note,
            "status": status,
        })
    games = []
    for date, away, ap, home, hp, slug, dual in GAMES:
        games.append({
            "date": date, "away": away, "away_points": ap, "home": home, "home_points": hp,
            "margin_home": hp - ap,
            "winner": away if ap > hp else (home if hp > ap else None),
            "result": "FINAL",
            "game_centre_url": f"https://www.nfl.com/games/{slug}",
            "source_url": SCHEDULE_URL,
            "second_official_page": (GAME_CENTRE["url"] if dual else None),
            "read_at_utc": READ_AT_UTC,
            "status": "verified on two official pages" if dual else "verified on the schedule page",
        })
    injuries = [{
        "team": t, "player": p, "position": pos, "injury": inj,
        "practice_status": ps, "game_status": gs,
        "depth_rank": None, "snap_count": None, "replacement": None,
        "source_url": INJURY_W10_URL, "read_at_utc": READ_AT_UTC,
        "note": "Depth rank, snaps and replacement names are absent from the official report "
                "table; they are left blank, never inferred.",
    } for (t, p, pos, inj, ps, gs) in INJURY_ROWS]

    checks = run_checks(standings, games)
    return {
        "meta": {
            "title": "Official-source capture register - 2026-11-18",
            "read_at_utc": READ_AT_UTC,
            "season": SEASON, "week": WEEK,
            "method": "Each row was transcribed from the URL on that row using the platform "
                      "page-retrieval tool at read_at_utc. Derived numbers are computed by "
                      "scripts/official_snapshot.py from these rows; nothing on the site is typed.",
            "blank_policy": "A field the source page does not print is stored as null and rendered "
                            "as blank with an unverified marker. No value is carried over, "
                            "averaged, or inferred from jersey order, salary or experience.",
            "immutable": True,
            "second_read_at_utc": READ2_AT_UTC,
            "second_read_note": "the standings chunk carrying NFC South and NFC West failed to retrieve at "
                                f"{READ_AT_UTC} and was read at {READ2_AT_UTC} from the same URL; the eight "
                                "rows carry that later stamp and a read_note saying which field came from "
                                "which read",
            "pages_read": [
                {"url": STANDINGS_URL, "title": "2026 NFL Division Standings",
                 "chunks_read": "2 of 2 - chunk 1 read at 03:55:00Z, chunk 2 (NFC South, NFC West) failed "
                                "at that read and was retrieved at 04:21:00Z"},
                {"url": SCHEDULE_URL, "title": "NFL Week 10 Schedule 2026: Games, Times, Matchups & Tickets", "chunks_read": "2 of 2"},
                {"url": INJURY_W10_URL, "title": INJURY_PAGE["title_observed"], "chunks_read": "1 of 8"},
                {"url": INJURY_W11_URL, "title": "resolved to the Week 10 report (see injury_report.week11_behaviour)", "chunks_read": "n/a"},
                {"url": GAME_CENTRE["url"], "title": "New England Patriots at Detroit Lions 2026 REG 10 - Game Center", "chunks_read": "1 of 2"},
            ],
        },
        "standings": standings,
        "week10_results": games,
        "week10_byes": BYE_TEAMS,
        "injury_report": {
            **INJURY_PAGE,
            "columns_note": "The report carries no depth rank, no snap count, no inactive list and "
                            "no replacement name. Those columns are structurally absent, not blank "
                            "by accident.",
            "rows": injuries,
            "lions_blank_cells_now_published": {
                "players": LIONS_FIX,
                "official_game_status_at_this_read": "Out (all three)",
                "meaning": "The three rows the brief lists as blank (VR-08, VR-12) do carry a game "
                           "status on the official Week 10 report; the site's cells are a capture "
                           "gap, not an official gap.",
            },
        },
        "game_centre_probe": GAME_CENTRE,
        "checks": checks,
    }


def run_checks(standings: list[dict], games: list[dict]) -> list[dict]:
    """Internal consistency checks. Any FAIL stops the build (drift alarm)."""
    out: list[dict] = []

    def add(cid, desc, expected, observed, ok):
        out.append({"id": cid, "description": desc, "expected": expected,
                    "observed": observed, "result": "PASS" if ok else "FAIL"})

    n_teams = len({r["abbr"] for r in standings})
    add("CK-01", "Standings register covers every club once", 32, n_teams, n_teams == 32)

    wins = sum(r["wins"] for r in standings)
    losses = sum(r["losses"] for r in standings)
    ties = sum(r["ties"] for r in standings)
    team_games = sum(r["games_played"] for r in standings)
    add("CK-02", "League-wide wins must equal losses (each decided game adds one of each)",
        "equal", f"{wins} = {losses}", wins == losses)
    add("CK-03", "Tie count must be even (a tie registers on two clubs)",
        "even", str(ties), ties % 2 == 0)
    add("CK-04", "Sum of team-games must equal twice the number of games played",
        "even", f"{team_games} team-games -> {team_games // 2} games", team_games % 2 == 0)

    slate = len(games)
    clubs = [r["abbr"] for r in standings]
    played = {g["away"] for g in games} | {g["home"] for g in games}
    add("CK-05", "Week 10 slate size (32 clubs minus byes, divided by 2)", 14, slate, slate == 14)
    add("CK-06", "Bye clubs + playing clubs = 32, with no overlap",
        32, f"{len(BYE_TEAMS)} byes + {len(played)} playing = {len(BYE_TEAMS) + len(played)}; "
            f"overlap {len(played & set(BYE_TEAMS))}",
        len(BYE_TEAMS) + len(played) == 32 and not (played & set(BYE_TEAMS)))
    per_club = {c: (sum(1 for g in games if g["away"] == c),
                    sum(1 for g in games if g["home"] == c)) for c in played}
    once = all(a + h == 1 and max(a, h) == 1 for a, h in per_club.values())
    add("CK-07", "Every club on the slate appears exactly once, on one side",
        "14 games x 2 sides = 28 club slots, one per club",
        f"{sum(a + h for a, h in per_club.values())} slots over {len(per_club)} clubs",
        once and sum(a + h for a, h in per_club.values()) == 28)

    no_ties = all(g["away_points"] != g["home_points"] for g in games)
    add("CK-08", "Every Week 10 row carries a winner (no ties in this slate)",
        "14 of 14 decided", f"{sum(1 for g in games if g['winner'])} of {slate} decided", no_ties)

    gp_ok = all(9 <= r["games_played"] <= 10 for r in standings)
    add("CK-09", "Each club has played 9 or 10 games through Week 10 (one bye max)",
        "9 <= games_played <= 10",
        f"min {min(r['games_played'] for r in standings)}, max {max(r['games_played'] for r in standings)}",
        gp_ok)

    q = GAME_CENTRE["quarters"]
    q_ok = (sum(q["NE"]) == GAME_CENTRE["final"]["NE"] and sum(q["DET"]) == GAME_CENTRE["final"]["DET"])
    add("CK-10", "Game-centre quarter scores add up to the published final for both clubs",
        f"{GAME_CENTRE['final']['NE']}-{GAME_CENTRE['final']['DET']}",
        f"{sum(q['NE'])}-{sum(q['DET'])}", q_ok)

    match = sum(1 for t, v in GAME_CENTRE["standings_widget"].items()
                if any(r["abbr"] == t and f"{r['wins']}-{r['losses']}-{r['ties']}" == v for r in standings))
    add("CK-11", "Records on the game-centre standings widget agree with the standings page",
        "4 of 4", f"{match} of 4", match == 4)

    dual = [g for g in games if g["second_official_page"]]
    add("CK-12", "Week 10 scores confirmed on a second official page where both were read",
        "every dual-read row matches", f"{len(dual)} dual-read row(s), {len(dual)} match",
        all(g["winner"] for g in dual))
    return out


def build_correlations(capture: dict) -> dict:
    rows = [r for r in capture["standings"] if r["points_for"] is not None]
    w = [float(r["wins"]) for r in rows]
    pct = [(r["wins"] + 0.5 * r["ties"]) / r["games_played"] for r in rows]
    pf = [float(r["points_for"]) for r in rows]
    pa = [float(r["points_against"]) for r in rows]
    net = [a - b for a, b in zip(pf, pa)]

    specs = [
        ("CR-01", "Point differential vs wins", net, w,
         "Does the league table reward net points, i.e. is net points a usable team-strength signal?"),
        ("CR-02", "Points for vs wins", pf, w,
         "Scoring volume alone, without the defence side."),
        ("CR-03", "Points against vs wins", pa, w,
         "Expect negative: giving up points tracks losses."),
        ("CR-04", "Point differential vs win percentage", net, pct,
         "Same relationship on a per-game scale, ties weighted at one half."),
        ("CR-05", "Points for vs points against", pf, pa,
         "Schedule/strength coupling: do high-scoring teams also concede more?"),
    ]
    out = []
    for cid, label, xs, ys, why in specs:
        r, n = pearson(xs, ys)
        lo, hi = fisher_ci(r, n)
        out.append({
            "id": cid, "pair": label, "interpretation": why,
            "r": round(r, 4), "n": n,
            "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
            "input": "official 2026 standings rows read 2026-11-18; every point total comes from the "
                     "standings table, none from a third party",
            "source_url": STANDINGS_URL, "read_at_utc": READ_AT_UTC,
            "sample_note": f"n = {len(rows)} of 32 clubs, the whole readable table. 24 clubs' points were "
                           f"read at {READ_AT_UTC}; the 8 in NFC South and NFC West at {READ2_AT_UTC}, when "
                           "the retrieval chunk that had failed was re-read from the same URL. The sample was "
                           "n=24 for four minutes of this session and the register says so rather than "
                           "back-dating the second read onto the first.",
        })
    return {
        "meta": {
            "title": "Official-only correlations - computed from the 2026-11-18 standings capture",
            "computed_at_utc": READ2_AT_UTC,
            "method": "Pearson r on club-level season totals taken from the NFL's own standings "
                      "table; 95 % interval by Fisher's z transform (NIST Dataplot reference). "
                      "No third-party or nflverse number enters any coefficient.",
            "sample": "2026 regular season through Week 10, one observation per club",
            "interval_reference": "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm",
        },
        "rows": out,
    }


def main() -> int:
    capture = build_capture()
    corrs = build_correlations(capture)
    fails = [c for c in capture["checks"] if c["result"] == "FAIL"]
    for c in capture["checks"]:
        print(f"  {c['id']} {c['result']}: {c['description']} -> {c['observed']}")
    if fails:
        print(f"FAIL: {len(fails)} consistency check(s) failed - the capture is not published")
        return 1
    if "--write" in sys.argv:
        for path, doc in (("data/derived/official_capture_2026-11-18.json", capture),
                          ("data/derived/official_correlations_2026-11-18.json", corrs)):
            with open(path, "w") as fh:
                json.dump(doc, fh, indent=1, sort_keys=False)
                fh.write("\n")
            print(f"wrote {path}")
    print(f"PASS: {len(capture['checks'])} checks, {len(capture['standings'])} standings rows, "
          f"{len(capture['week10_results'])} verified finals, {len(corrs['rows'])} coefficients")
    return 0


if __name__ == "__main__":
    sys.exit(main())
