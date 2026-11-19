#!/usr/bin/env python3
"""Build the Week 11 register, the fixture register and the Week 10 -> Week 11 delta series.

Everything published is COMPUTED from two committed inputs:
  1. week11-desk/scripts/rows_week11.py   (this session's dated official transcription)
  2. availability-sweep/data/week10_rows_20261118.csv  (the 2026-11-18 Week 10 register,
     owned by session arena/9fa8ea61-korea2; read-only here, never rewritten)

Rules enforced here:
  * no value is invented: a field the official page leaves blank stays blank in the output;
  * the fixture register's venue/location come from the official game centre and are stored
    beside the value a differently-worded source would give, so a disagreement is visible
    rather than silently "fixed";
  * the delta is published as counts plus the named player-level changes, and every delta
    row carries the two source links it was computed between.

Run:  python3 week11-desk/scripts/build_register.py [--write]
Exit code non-zero on any internal consistency failure (drift alarm).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
ROOT = os.path.dirname(DESK)
DATA = os.path.join(DESK, "data")
sys.path.insert(0, HERE)

from rows_week11 import (  # noqa: E402
    CLUBS_NO_REPORT, CLUB_LABEL, GAME_SLOTS, NO_INJURIES_BLOCK, READS, READ_AT_UTC,
    ROWS, SEASON, SOURCE_TITLE, SOURCE_URL, WEEK,
)

W10_CSV = os.path.join(ROOT, "availability-sweep", "data", "week10_rows_20261118.csv")
W10_URL = "https://www.nfl.com/injuries/league/2026/REG10"
W10_READ_AT = "2026-11-18T03:55:37Z"

SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-11"

# ---------------------------------------------------------------------------------------
# Fixture register. `venue_official` is what the official game centre prints in its
# "STADIUM" field; `venue_prior_register` is what requirements-desk/data/schedule_2026_w11.csv
# (session arena/2ca76106-korea2) recorded on 2026-11-18. Both are stored; this session does
# not edit that file, it publishes the disagreement for the owner to reconcile.
# --------------------------------------------------------------------------------------
FIXTURES = [
    # date, kickoff_et, away, home, network, location_official, venue_official,
    # venue_prior_register, neutral, game_url
    ("2026-11-19", "8:15 PM", "IND", "HOU", "Prime Video", "HOUSTON, TX", "RELIANT STADIUM",
     "NRG Stadium", "no", "https://www.nfl.com/games/colts-at-texans-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "MIA", "BUF", "CBS", "ORCHARD PARK, NY", "HIGHMARK STADIUM",
     "Highmark Stadium", "no", "https://www.nfl.com/games/dolphins-at-bills-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "BAL", "CAR", "FOX", "CHARLOTTE, NC", "BANK OF AMERICA STADIUM",
     "Bank of America Stadium", "no", "https://www.nfl.com/games/ravens-at-panthers-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "NO", "CHI", "FOX", "CHICAGO, IL", "SOLDIER FIELD",
     "Soldier Field", "no", "https://www.nfl.com/games/saints-at-bears-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "TEN", "DAL", "FOX", "ARLINGTON, TX", "AT&T STADIUM",
     "AT&T Stadium", "no", "https://www.nfl.com/games/titans-at-cowboys-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "TB", "DET", "FOX", "DETROIT, MI", "FORD FIELD",
     "Ford Field", "no", "https://www.nfl.com/games/buccaneers-at-lions-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "AZ", "KC", "CBS", "KANSAS CITY, MO", "ARROWHEAD STADIUM",
     "GEHA Field at Arrowhead Stadium", "no",
     "https://www.nfl.com/games/cardinals-at-chiefs-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "PIT", "PHI", "CBS", "PHILADELPHIA, PA", "LINCOLN FINANCIAL FIELD",
     "Lincoln Financial Field", "no",
     "https://www.nfl.com/games/steelers-at-eagles-2026-reg-11"),
    ("2026-11-22", "4:05 PM", "NYJ", "LAC", "FOX", "INGLEWOOD, CA", "SOFI STADIUM",
     "SoFi Stadium", "no", "https://www.nfl.com/games/jets-at-chargers-2026-reg-11"),
    ("2026-11-22", "4:25 PM", "JAX", "NYG", "CBS", "EAST RUTHERFORD, NJ", "METLIFE STADIUM",
     "MetLife Stadium", "no", "https://www.nfl.com/games/jaguars-at-giants-2026-reg-11"),
    ("2026-11-22", "4:25 PM", "LV", "DEN", "CBS", "DENVER, CO", "EMPOWER FIELD AT MILE HIGH",
     "Empower Field at Mile High", "no",
     "https://www.nfl.com/games/raiders-at-broncos-2026-reg-11"),
    ("2026-11-22", "8:20 PM", "MIN", "SF", "NBC", "MEXICO CITY", "ESTADIO BANORTE",
     "Mexico City", "yes", "https://www.nfl.com/games/vikings-at-49ers-2026-reg-11"),
    ("2026-11-23", "8:15 PM", "CIN", "WAS", "ESPN", "LANDOVER, MD", "NORTHWEST STADIUM",
     "FedEx Field", "no",
     "https://www.nfl.com/games/bengals-at-commanders-2026-reg-11"),
]

# Bye clubs, from the official Week 11 schedule page "Teams on Bye" block.
BYES = [
    ("ATL", "3-7", SCHEDULE_URL), ("CLE", "6-4", SCHEDULE_URL), ("GB", "6-4", SCHEDULE_URL),
    ("LAR", "6-4", SCHEDULE_URL), ("NE", "5-5", SCHEDULE_URL), ("SEA", "6-4", SCHEDULE_URL),
]

# ---------------------------------------------------------------------------------------
# Named-absence check. The Week 11 injury page prints a "NEWS" block whose headlines are
# published on nfl.com and are linked from the page itself. Those headlines name players who
# are NOT in the weekly report tables. This register records, for each such player, whether
# the Week 11 table lists them. It exists to make one thing impossible: reading "not listed"
# as "available". A player on injured reserve is not listed because he is unavailable, not
# because he is healthy. The report tables alone cannot distinguish the two, so the headline
# that explains the absence is carried beside the observation, labelled as a news headline.
ABSENCE_CHECK = [
    # (club, player, page_headline, headline_url)
    ("BAL", "Lamar Jackson",
     "NFL news roundup: Ravens confirm Lamar Jackson expected to miss 6-10 weeks; Kenneth Walker questionable",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-friday-nov-13"),
    ("MIA", "Malik Willis",
     "Dolphins place QB Malik Willis (groin) on injured reserve; Kyle McCord in line for first start",
     "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start"),
    ("MIA", "Kyle McCord",
     "Dolphins place QB Malik Willis (groin) on injured reserve; Kyle McCord in line for first start",
     "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start"),
    ("MIN", "Jordan Addison",
     "NFL news roundup: Vikings WR Jordan Addison needs thumb surgery, could go to IR; Buccaneers add QB",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-monday-nov-16"),
    ("DET", "Aidan Hutchinson",
     "NFL Network: Lions' Aidan Hutchinson feared to have suffered significant knee injury on sack celebration",
     "https://www.nfl.com/news/lions-aidan-hutchinson-knee-injury-patriots"),
    ("TB", "Baker Mayfield",
     "NFL Network: Buccaneers QB Baker Mayfield dealing with lower leg injury ahead of Week 11",
     "https://www.nfl.com/news/buccaneers-qb-baker-mayfield-injury-week-11"),
    ("NE", "Drake Maye",
     "NFL Network: Patriots QB Drake Maye could miss rest of 2026 season",
     "https://www.nfl.com/news/nfl-network-patriots-qb-drake-maye-could-miss-rest-of-2026-season"),
    ("NE", "TreVeyon Henderson",
     "NFL news roundup: Patriots place RB TreVeyon Henderson (illness) on injured reserve",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14"),
    ("LAR", "Puka Nacua",
     "Rams WR Puka Nacua likely to be placed on injured reserve with turf toe, sprained MCL and PCL",
     "https://www.nfl.com/news/rams-wr-puka-nacua-likely-to-be-placed-on-injured-reserve-with-turf-toe-sprained-mcl-and-pcl"),
    ("GB", "Josh Jacobs",
     "Packers RB Josh Jacobs to undergo surgery on finger this week; timeline to return TBD",
     "https://www.nfl.com/news/packers-rb-josh-jacobs-to-undergo-surgery-on-finger-this-week"),
]


def build_absence(rows: list[dict]) -> list[dict]:
    """Present/absent in the Week 11 table, for players named in the page's own news block."""
    listed = {(r["club"], r["player"]) for r in rows}
    bye_clubs = {c for (c, _rec, _u) in BYES}
    out = []
    for club, player, headline, url in ABSENCE_CHECK:
        present = (club, player)
        in_table = present in listed
        if in_table:
            why = ""
        elif club in bye_clubs:
            why = ("club is on bye in Week 11, so it publishes no game-status column at all; "
                   "absence here carries no availability information")
        else:
            why = ("not listed in the Week 11 table; the page does not print a reason. "
                   "Absence is NOT evidence of availability")
        out.append(OrderedDict([
            ("club", club), ("player", player),
            ("listed_in_week11_table", "yes" if in_table else "no"),
            ("practical_reading", why),
            ("news_headline_on_official_page", headline),
            ("headline_url", url),
            ("table_source_url", SOURCE_URL),
            ("read_at_utc", READ_AT_UTC),
        ]))
    return out


PRACTICE_OK = {"Full Participation in Practice", "Limited Participation in Practice",
               "Did Not Participate In Practice", ""}
GAME_OK = {"Out", "Doubtful", "Questionable", ""}


def fail(msg: str) -> None:
    raise SystemExit("DRIFT: " + msg)


# ---------------------------------------------------------------------------------------
def build_rows() -> list[dict]:
    out = []
    for club, player, pos, injury, practice, game in ROWS:
        if practice not in PRACTICE_OK:
            fail(f"unknown practice status {practice!r} for {club}/{player}")
        if game not in GAME_OK:
            fail(f"unknown game status {game!r} for {club}/{player}")
        if club not in CLUB_LABEL:
            fail(f"unknown club {club!r}")
        out.append(OrderedDict([
            ("club", club), ("club_name", CLUB_LABEL[club]),
            ("player", player), ("position", pos), ("injury", injury),
            ("practice_status", practice), ("game_status", game),
            ("source_url", SOURCE_URL), ("read_at_utc", READ_AT_UTC),
        ]))
    return out


def club_counts(rows: list[dict]) -> list[dict]:
    by = OrderedDict()
    for r in rows:
        d = by.setdefault(r["club"], Counter())
        d["rows"] += 1
        d["designated"] += 1 if r["game_status"] else 0
        if r["game_status"]:
            d[r["game_status"]] += 1
        if r["injury"]:
            d["injury_named"] += 1
    for c in CLUBS_NO_REPORT:
        by.setdefault(c, Counter())
    out = []
    for club, d in by.items():
        out.append(OrderedDict([
            ("club", club), ("club_name", CLUB_LABEL[club]),
            ("rows", d["rows"]), ("injury_named", d["injury_named"]),
            ("game_designated", d["designated"]),
            ("out", d["Out"]), ("doubtful", d["Doubtful"]),
            ("questionable", d["Questionable"]),
            ("no_designation", d["rows"] - d["designated"]),
            ("page_block", NO_INJURIES_BLOCK if club in CLUBS_NO_REPORT else ""),
            ("source_url", SOURCE_URL), ("read_at_utc", READ_AT_UTC),
        ]))
    return out


def totals(rows: list[dict]) -> dict:
    c = Counter(r["game_status"] for r in rows)
    return OrderedDict([
        ("rows", len(rows)),
        ("clubs_with_rows", len({r["club"] for r in rows})),
        ("clubs_no_report", len(CLUBS_NO_REPORT)),
        ("injury_named", sum(1 for r in rows if r["injury"])),
        ("out", c["Out"]), ("doubtful", c["Doubtful"]),
        ("questionable", c["Questionable"]),
        ("no_designation", c[""]),
        ("designated", len(rows) - c[""]),
    ])


# ---------------------------------------------------------------------------------------
def build_delta(rows11: list[dict]) -> tuple[list[dict], dict]:
    """Week 10 -> Week 11 per-player change register.

    The two registers are not the same population: Week 10 listed 28 clubs, Week 11 lists 26
    clubs with rows plus 2 clubs printing "No Injuries Reported". A player present in one
    week and absent in the other is reported as exactly that ("not listed"), never as
    "cleared" or "healthy" — absence from the injury report is not evidence of availability.
    """
    with open(W10_CSV, newline="", encoding="utf-8") as fh:
        w10 = list(csv.DictReader(fh))
    idx10 = {(r["team"], r["player"]): r for r in w10}
    idx11 = {(r["club"], r["player"]): r for r in rows11}
    clubs10 = {r["team"] for r in w10}
    clubs11 = {r["club"] for r in rows11} | set(CLUBS_NO_REPORT)

    # Only clubs that published a table in BOTH weeks can produce a per-player change. A club
    # that was on bye in Week 10 has no Week 10 rows, so its Week 11 rows are not "newly
    # listed" injuries — they are the first listing of a club that did not have to publish.
    # Lumping them together would inflate the "newly listed" count and mislabel healthy clubs.
    both = clubs10 & clubs11

    # ---- publication-cycle guard -----------------------------------------------------
    # The official page fills a fixture's game-status column as that fixture's week
    # progresses: the Thursday game carried Out/Questionable in full at this read, while every
    # club whose game is later in the week carried a practice status only. So a blank game
    # status on a later fixture is "not yet published", NOT "cleared". Comparing a fully
    # designated Week 10 row with a not-yet-designated Week 11 row would manufacture
    # hundreds of false "cleared"/"game-status change" rows.
    # We therefore only compare game status inside a club whose Week 11 rows carry at least
    # one game designation at this read. Elsewhere the comparison is practice-only and is
    # labelled as such.
    club_has_designation11 = {c: any(r["club"] == c and r["game_status"] for r in rows11)
                              for c in clubs11}
    game_comparable = {c for c, v in club_has_designation11.items() if v}

    def fmt(practice: str, game: str, comparable: bool) -> str:
        if not practice and not game:
            return ""
        g = game if game else ("(blank)" if comparable else "(no designation published)")
        if not practice:
            return g
        return f"{practice} / {g}"

    out = []
    for key in sorted(set(idx10) | set(idx11)):
        club, player = key
        if club not in both:
            continue
        cmp_ = club in game_comparable
        a, b = idx10.get(key), idx11.get(key)
        if a is None:
            change = "newly listed"
            won, wnn = "", fmt(b["practice_status"], b["game_status"], cmp_)
        elif b is None:
            change = "no longer listed"
            won, wnn = fmt(a["practice_status"], a["game_status"], True), ""
        else:
            won = fmt(a["practice_status"], a["game_status"], True)
            wnn = fmt(b["practice_status"], b["game_status"], cmp_)
            p_changed = a["practice_status"] != b["practice_status"]
            # The change key only includes game status where a comparison is legitimate.
            key_a = (a["practice_status"], a["game_status"])
            key_b = (b["practice_status"], b["game_status"] if cmp_ else a["game_status"])
            if key_a == key_b:
                continue
            if not cmp_:
                change = "practice change" if p_changed else "unclassified"
            elif p_changed and a["game_status"] != b["game_status"]:
                change = "practice and game-status change"
            elif p_changed:
                change = "practice change"
            elif b["game_status"] == "":
                # A designation present in Week 10 and blank in Week 11 is reported as
                # withdrawn from the page. It is NOT published as "cleared": a blank cell is
                # the absence of a designation, not evidence that the player is available.
                change = "designation withdrawn (blank at this read)"
            else:
                change = "designation added"
        out.append(OrderedDict([
            ("club", club), ("player", player),
            ("position_w11", b["position"] if b else (a["position"] if a else "")),
            ("week10_practice / week10_game", won),
            ("week11_practice / week11_game", wnn),
            ("change", change),
            ("game_status_comparable", "yes" if cmp_ else "no - later fixture, designation not yet published"),
            ("week10_source", W10_URL), ("week11_source", SOURCE_URL),
        ]))

    summary = OrderedDict([
        ("week10_rows", len(w10)), ("week11_rows", len(rows11)),
        ("week10_clubs", len(clubs10)), ("week11_clubs", len(clubs11)),
        ("clubs_in_both", len(both)),
        ("clubs_only_week10", sorted(clubs10 - clubs11)),
        ("clubs_only_week11", sorted(clubs11 - clubs10)),
        ("clubs_excluded_from_delta", sorted(clubs11 - both)),
        ("clubs_excluded_reason",
         "These clubs published no table in Week 10 (bye week: " +
         ", ".join(sorted(clubs11 - both)) + "), so no per-player comparison is possible. "
         "Their Week 11 rows are published in full but excluded from the delta; calling them "
         "'newly listed' would be inference."),
        ("clubs_game_status_comparable", sorted(game_comparable)),
        ("clubs_game_status_not_comparable", sorted(both - game_comparable)),
        ("game_status_rule",
         "Game status is compared only for clubs whose Week 11 rows already carry at least "
         "one official game designation at the read time (here: IND and HOU, the Thursday "
         "fixture). For every later fixture the Week 11 game-status column was still empty at "
         "the read, so those rows are compared on practice status only and their week-11 game "
         "value prints '(no designation published)' instead of a blank that could be mistaken "
         "for 'cleared'."),
        ("players_compared", len({k for k in set(idx10) | set(idx11) if k[0] in both})),
        ("change_rows", len(out)),
        ("by_change", dict(Counter(r["change"] for r in out))),
    ])
    return out, summary


# ---------------------------------------------------------------------------------------
def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def write_csv(path: str, rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(buf.getvalue())
    return sha256_of(path)


def main(argv: list[str]) -> int:
    write = "--write" in argv
    os.makedirs(DATA, exist_ok=True)

    rows = build_rows()
    counts = club_counts(rows)
    tot = totals(rows)
    delta, dsum = build_delta(rows)
    absence = build_absence(rows)

    # --- internal consistency (drift alarms) -------------------------------------------
    if tot["clubs_with_rows"] + tot["clubs_no_report"] != 26:
        fail(f"expected 26 clubs on the Week 11 page, saw {tot['clubs_with_rows']}+{tot['clubs_no_report']}")
    if len(GAME_SLOTS) != 13:
        fail("expected 13 Week 11 fixtures")
    if len(FIXTURES) != len(GAME_SLOTS):
        fail("fixture register and page game slots disagree in length")
    clubs_in_slots = [c for g in GAME_SLOTS for c in (g[3], g[4])]
    if sorted(clubs_in_slots) != sorted(counts and [c["club"] for c in counts]):
        fail("clubs in the game-slot headers != clubs in the row register + no-report clubs")
    if sum(c["rows"] for c in counts) != len(rows):
        fail("per-club row counts do not sum to the register")
    if tot["out"] + tot["doubtful"] + tot["questionable"] + tot["no_designation"] != len(rows):
        fail("game-status split does not sum to the register")
    # Every designated row in Week 11 must also carry a named injury string.
    for r in rows:
        if r["game_status"] and not r["injury"]:
            fail(f"{r['club']}/{r['player']} carries a game designation but no injury string")

    fixture_rows = [OrderedDict([
        ("date", d), ("kickoff_et", k), ("away", a), ("home", h), ("network", n),
        ("location_official", loc), ("venue_official", v), ("venue_prior_register", pv),
        ("neutral_site", nu), ("source_url", url),
    ]) for (d, k, a, h, n, loc, v, pv, nu, url) in FIXTURES]

    bye_rows = [OrderedDict([("club", c), ("record_w11", rec), ("source_url", u)])
                for (c, rec, u) in BYES]

    cols_rows = ["club", "club_name", "player", "position", "injury", "practice_status",
                 "game_status", "source_url", "read_at_utc"]
    cols_counts = ["club", "club_name", "rows", "injury_named", "game_designated", "out",
                   "doubtful", "questionable", "no_designation", "page_block", "source_url",
                   "read_at_utc"]
    cols_fix = ["date", "kickoff_et", "away", "home", "network", "location_official",
                "venue_official", "venue_prior_register", "neutral_site", "source_url"]
    cols_delta = list(delta[0].keys()) if delta else [
        "club", "player", "position_w11", "week10_practice / week10_game",
        "week11_practice / week11_game", "change", "game_status_comparable", "week10_source",
        "week11_source"]

    payload = {
        "meta": OrderedDict([
            ("title", "Week 11 (2026) official availability register and Week 10 -> 11 delta series"),
            ("generated_by", "week11-desk/scripts/build_register.py"),
            ("session", "arena/5d001552-korea2"),
            ("season", SEASON), ("week", WEEK),
            ("source_url", SOURCE_URL), ("source_title", SOURCE_TITLE),
            ("page_heading", "Injuries - WEEK 11"),
            ("read_at_utc", READ_AT_UTC),
            ("reads", [OrderedDict([("started_utc", a), ("finished_utc", b), ("chunks", c),
                                    ("note", d)]) for (a, b, c, d) in READS]),
            ("week10_comparison_url", W10_URL),
            ("week10_read_at_utc", W10_READ_AT),
            ("week11_schedule_url", SCHEDULE_URL),
            ("totals", tot),
            ("fixtures", len(FIXTURES)),
            ("byes", len(BYES)),
            ("delta", dsum),
            ("raw_bytes_retained", False),
            ("raw_bytes_note",
             "The sandbox shell has no network route to nfl.com (verified with curl, exit 35 "
             "CONNECT tunnel failure), so no HTTP response body could be stored. The register "
             "hash below covers the transcribed rows as committed, not the NFL response bytes. "
             "This is flag W11-F01 on the Flagged page."),
        ]),
        "totals": tot,
        "delta_summary": dsum,
    }

    if not write:
        print(json.dumps({"totals": tot, "delta": dsum}, indent=2))
        print(f"OK (dry run): {len(rows)} rows, {len(counts)} club blocks, "
              f"{len(fixture_rows)} fixtures, {len(delta)} delta rows")
        return 0

    hashes = {}
    hashes["week11_rows.csv"] = write_csv(os.path.join(DATA, "week11_rows.csv"), rows, cols_rows)
    hashes["week11_team_counts.csv"] = write_csv(
        os.path.join(DATA, "week11_team_counts.csv"), counts, cols_counts)
    hashes["week11_fixtures.csv"] = write_csv(
        os.path.join(DATA, "week11_fixtures.csv"), fixture_rows, cols_fix)
    hashes["week11_byes.csv"] = write_csv(os.path.join(DATA, "week11_byes.csv"), bye_rows,
                                          ["club", "record_w11", "source_url"])
    hashes["delta_week10_week11.csv"] = write_csv(
        os.path.join(DATA, "delta_week10_week11.csv"), delta, cols_delta)
    hashes["week11_absence_check.csv"] = write_csv(
        os.path.join(DATA, "week11_absence_check.csv"), absence,
        ["club", "player", "listed_in_week11_table", "practical_reading",
         "news_headline_on_official_page", "headline_url", "table_source_url", "read_at_utc"])

    payload["register_sha256"] = hashes
    payload["register_manifest_sha256"] = hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(DATA, "week11_register.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
        fh.write("\n")

    # capture log, append-only, mirroring the availability-sweep convention
    log_path = os.path.join(DATA, "capture_log.csv")
    log_rows = []
    if os.path.exists(log_path):
        with open(log_path, newline="", encoding="utf-8") as fh:
            log_rows = list(csv.DictReader(fh))
    cap_id = "20261119-5d001552"
    if not any(r["capture_id"] == cap_id for r in log_rows):
        log_rows.append(OrderedDict([
            ("capture_id", cap_id), ("week", WEEK), ("url", SOURCE_URL),
            ("fetched_utc_start", READS[0][0]), ("fetched_utc_end", READS[-1][1]),
            ("method", "page-retrieval tool read (8 chunks)"),
            ("scope", f"full: all {tot['clubs_with_rows']} listed clubs transcribed row by row; "
                      f"{tot['clubs_no_report']} clubs print '{NO_INJURIES_BLOCK}'"),
            ("rows_captured", len(rows)), ("teams_captured", tot["clubs_with_rows"]),
            ("raw_bytes_hash", "not retained"),
            ("source_url", SOURCE_URL),
        ]))
        write_csv(log_path, log_rows, list(log_rows[0].keys()))

    print(f"wrote {len(rows)} rows, {len(counts)} club blocks, {len(fixture_rows)} fixtures, "
          f"{len(delta)} delta rows")
    print(json.dumps(tot, indent=2))
    print("manifest", payload["register_manifest_sha256"][:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
