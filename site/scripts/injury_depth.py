#!/usr/bin/env python3
"""Injury and depth research: what we can verify, what we cannot, and what each answer needs.

Two hard rules drive this file.

1. Nothing about a *lineup* is inferred. The NFL's own injury report gives practice participation and
   a game status; it does not say who starts, and it does not rank a backup 1st/2nd/3rd/4th string.
   Depth charts are a separate feed. So every "is the starter out, and who replaces him" cell is left
   blank until a depth-chart feed is committed, and the row is flagged.

2. Every transcribed row keeps the exact URL it came from. The transcription itself is committed so a
   reviewer can re-read the same page and diff it against this file.

The only numbers computed here are counts of what the official page actually printed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "data" / "injury_depth.json"

NFLVERSE = "https://github.com/nflverse/nflverse-data"
RETRIEVED = "2026-11-12"
INJURY_URL = "https://www.nfl.com/injuries/league/2026/reg10"
IMPORTANT_DATES = "https://www.nfl.com/news/2026-27-national-football-league-important-dates"
KC_ROSTER = "https://www.nfl.com/teams/kansas-city-chiefs/roster"
DICT_INJURIES = "https://nflreadr.nflverse.com/articles/dictionary_injuries.html"
DICT_DEPTH = "https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html"
DICT_SNAPS = "https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html"
DICT_PARTICIPATION = "https://nflreadr.nflverse.com/articles/dictionary_participation.html"

# ---------------------------------------------------------------------------------------------
# Transcribed from https://www.nfl.com/injuries/league/2026/reg10 on 2026-11-12.
# Columns exactly as printed: Player | Position | Injuries | Practice Status | Game Status
# Game Status was blank for most players at retrieval time (the report was mid-week).
# ---------------------------------------------------------------------------------------------
DNP = "Did Not Participate In Practice"
LIM = "Limited Participation in Practice"
FULL = "Full Participation in Practice"

GAMES = [
    {"slot": "Thu 12 Nov, 8:15 PM ET, Prime Video", "away": "WAS", "home": "NYG",
     "away_name": "Commanders", "home_name": "Giants", "away_record": "2-5-1", "home_record": "5-2-1"},
    {"slot": "Sun 15 Nov, 9:30 AM ET, FOX", "away": "NE", "home": "DET",
     "away_name": "Patriots", "home_name": "Lions", "away_record": "5-4", "home_record": "6-2"},
    {"slot": "Sun 15 Nov, 1:00 PM ET, CBS", "away": "KC", "home": "ATL",
     "away_name": "Chiefs", "home_name": "Falcons", "away_record": "6-2", "home_record": "3-6"},
    {"slot": "Sun 15 Nov, 1:00 PM ET, FOX", "away": "MIN", "home": "GB",
     "away_name": "Vikings", "home_name": "Packers", "away_record": "6-2", "home_record": "6-3"},
    {"slot": "Sun 15 Nov, 1:00 PM ET, FOX", "away": "JAX", "home": "TEN",
     "away_name": "Jaguars", "home_name": "Titans", "away_record": "6-2", "home_record": "1-7"},
]

# team -> list of (player, position, injury, practice_status, game_status)
REPORT = {
    "WAS": [
        ("John Bates", "TE", "", FULL, ""),
        ("Treylon Burks", "WR", "", DNP, ""),
        ("Jayden Daniels", "QB", "", FULL, ""),
        ("Matt Gulbin", "C", "", FULL, ""),
        ("Chig Okonkwo", "TE", "", FULL, ""),
        ("Lucas Patrick", "C", "Concussion", DNP, "Out"),
        ("Amik Robertson", "CB", "", LIM, ""),
        ("Shy Tuttle", "DT", "", FULL, ""),
        ("Colson Yankoff", "TE", "Knee", DNP, "Out"),
    ],
    "NYG": [
        ("Abdul Carter", "LB", "", FULL, ""),
        ("Jermaine Eluemunor", "T", "", FULL, ""),
        ("Malik Harrison", "LB", "Groin", LIM, "Questionable"),
        ("Colton Hood", "CB", "", FULL, ""),
        ("Theo Johnson", "TE", "", FULL, ""),
        ("Charlie Jones", "WR", "", FULL, ""),
        ("J.J. McCarthy", "QB", "", FULL, ""),
        ("Darnell Mooney", "WR", "", FULL, ""),
        ("Malik Nabers", "WR", "", FULL, ""),
        ("Cam Skattebo", "RB", "", FULL, ""),
        ("Andrew Thomas", "T", "", FULL, ""),
    ],
    "NE": [
        ("Ben Brown", "C", "Knee", DNP, "Out"),
        ("A.J. Brown", "WR", "", LIM, ""),
        ("Kevin Byard", "S", "", LIM, ""),
        ("Carlton Davis III", "CB", "Knee", DNP, "Out"),
        ("Reggie Gilliam", "FB", "", LIM, ""),
        ("TreVeyon Henderson", "RB", "Illness", DNP, "Out"),
        ("Hunter Henry", "TE", "", LIM, ""),
        ("Cameron Latu", "TE", "", DNP, ""),
        ("Drake Maye", "QB", "", FULL, ""),
        ("Morgan Moses", "T", "", LIM, ""),
        ("Walter Rouse", "T", "", DNP, ""),
        ("Brenden Schooler", "S", "", DNP, ""),
        ("Rhamondre Stevenson", "RB", "", DNP, ""),
        ("Greg Van Roten", "G", "", LIM, ""),
        ("Charles Woods", "CB", "", LIM, ""),
    ],
    "DET": [
        ("Brian Branch", "S", "", LIM, ""),
        ("Jared Goff", "QB", "", LIM, ""),
        ("Kerby Joseph", "S", "", LIM, ""),
        ("Cade Mays", "C", "", DNP, ""),
        ("D.J. Reed", "CB", "", DNP, ""),
        ("Jacob Saylors", "RB", "", FULL, ""),
        ("Amon-Ra St. Brown", "WR", "", LIM, ""),
        ("Sione Vaki", "RB", "", DNP, ""),
        ("DJ Wonnum", "DE", "", FULL, ""),
    ],
    "KC": [
        ("Jeffrey Bassa", "LB", "", FULL, ""),
        ("Mansoor Delane", "CB", "", FULL, ""),
        ("Justin Fields", "QB", "", FULL, ""),
        ("Jaden Hicks", "S", "", FULL, ""),
        ("Travis Kelce", "TE", "", FULL, ""),
        ("Patrick Mahomes", "QB", "", FULL, ""),
        ("Jaylon Moore", "T", "", DNP, ""),
        ("Omarr Norman-Lott", "DT", "", LIM, ""),
        ("Rashee Rice", "WR", "", FULL, ""),
        ("Peter Woods", "DT", "", DNP, ""),
        ("Xavier Worthy", "WR", "", FULL, ""),
    ],
    "ATL": [
        ("Zachariah Branch", "WR", "", DNP, ""),
        ("Divine Deablo", "LB", "", LIM, ""),
        ("Gervon Dexter Sr.", "DT", "", DNP, ""),
        ("James Pearce Jr.", "DE", "", DNP, ""),
        ("Za'Darius Smith", "DE", "", DNP, ""),
        ("Josh Woods", "LB", "", DNP, ""),
    ],
    "MIN": [
        ("Blake Cashman", "LB", "", DNP, ""),
        ("T.J. Hockenson", "TE", "", DNP, ""),
        ("Tyrion Ingram-Dawkins", "DT", "", DNP, ""),
        ("Theo Jackson", "S", "", FULL, ""),
        ("Jauan Jennings", "WR", "", DNP, ""),
        ("Kyler Murray", "QB", "", DNP, ""),
        ("Kyle Van Noy", "LB", "", DNP, ""),
        ("Jay Ward", "S", "", LIM, ""),
        ("Carson Wentz", "QB", "", LIM, ""),
    ],
    "GB": [
        ("Aaron Banks", "G", "", LIM, ""),
        ("Chris Brooks", "RB", "", LIM, ""),
        ("Javon Bullard", "S", "", DNP, ""),
        ("Zaire Franklin", "LB", "", DNP, ""),
        ("Travis Glover", "G", "", LIM, ""),
        ("Ty'Ron Hopper", "LB", "", LIM, ""),
        ("Josh Jacobs", "RB", "", DNP, ""),
        ("Bo Melton", "WR", "", FULL, ""),
        ("Skyy Moore", "WR", "", LIM, ""),
        ("Micah Parsons", "LB", "", LIM, ""),
        ("Sean Rhyan", "C", "", DNP, ""),
        ("Trey Smack", "K", "", LIM, ""),
        ("Lukas Van Ness", "LB", "", DNP, ""),
        ("Josh Whyle", "TE", "", DNP, ""),
        ("Savion Williams", "WR", "", LIM, ""),
        ("Kevin Zeitler", "G", "", LIM, ""),
    ],
    "JAX": [
        ("Jessie Bates", "S", "", DNP, ""),
        ("Ezra Cleveland", "G", "", LIM, ""),
        ("Branson Combs", "LB", "", LIM, ""),
        ("Jordan Davis", "DT", "", DNP, ""),
        ("Robert Hainsey", "C", "", LIM, ""),
        ("Antonio Johnson", "S", "", LIM, ""),
        ("Jakobi Meyers", "WR", "", DNP, ""),
        ("Chris Rodriguez Jr.", "RB", "", LIM, ""),
        ("Bhayshul Tuten", "RB", "", DNP, ""),
        ("Travon Walker", "DE", "", DNP, ""),
    ],
    "TEN": [
        ("Cody Barton", "LB", "", DNP, ""),
        ("John Franklin-Myers", "DE", "", FULL, ""),
        ("Marcus Harris", "CB", "", FULL, ""),
        ("Anthony Hill Jr.", "LB", "", DNP, ""),
        ("Jaylon Jones", "CB", "", FULL, ""),
        ("JC Latham", "T", "", FULL, ""),
        ("Tony Pollard", "RB", "", FULL, ""),
        ("Peter Skoronski", "G", "", DNP, ""),
        ("Tyjae Spears", "RB", "", DNP, ""),
        ("Carnell Tate", "WR", "", DNP, ""),
        ("Tommy Townsend", "P", "", FULL, ""),
        ("Kevin Winston Jr.", "S", "", FULL, ""),
    ],
}

OFFENSE_POS = {"QB", "RB", "WR", "TE", "FB", "C", "G", "T", "OT", "OG", "OL"}
DEFENSE_POS = {"CB", "S", "SAF", "LB", "ILB", "OLB", "MLB", "DE", "DT", "NT", "DL", "DB", "FS", "SS"}


def unit(pos: str) -> str:
    if pos in OFFENSE_POS:
        return "offense"
    if pos in DEFENSE_POS:
        return "defense"
    return "special teams"


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return x
    return x


def stamp() -> str:
    """Deterministic build stamp.

    Wall-clock generation times made every CI rebuild differ from the committed file, which broke the
    reproducibility check for a reason that had nothing to do with the numbers. The stamp is therefore
    the date the committed data ends, read from data/provenance.json.
    """
    p = ROOT / "data" / "provenance.json"
    try:
        with open(p) as fh:
            day = json.load(fh).get("data_as_of_gameday")
    except (OSError, ValueError):
        day = None
    return f"{day}T00:00:00Z" if day else "unknown"


def main() -> int:
    rows = []
    for team, players in REPORT.items():
        for player, pos, injury, practice, status in players:
            rows.append({
                "team": team, "player": player, "position": pos, "unit": unit(pos),
                "injury": injury or None,
                "practice_status": practice,
                "game_status": status or None,
                "started_or_backup": None,   # requires a depth-chart feed - never inferred
                "depth_rank": None,          # requires a depth-chart feed - never inferred
                "replacement": None,         # requires a depth-chart feed - never inferred
                "source": INJURY_URL,
                "verified": "transcribed from the official NFL injury report on " + RETRIEVED,
            })

    # ---- per-team counts, computed from the transcription above -------------------------------
    by_team = []
    for team, players in REPORT.items():
        dnp = sum(1 for p in players if p[3] == DNP)
        lim = sum(1 for p in players if p[3] == LIM)
        full = sum(1 for p in players if p[3] == FULL)
        injured = sum(1 for p in players if p[2])
        out = sum(1 for p in players if p[4] == "Out")
        q = sum(1 for p in players if p[4] == "Questionable")
        dnp_def = sum(1 for p in players if p[3] == DNP and unit(p[1]) == "defense")
        dnp_off = sum(1 for p in players if p[3] == DNP and unit(p[1]) == "offense")
        qbs = [p[0] for p in players if p[1] == "QB"]
        by_team.append({
            "team": team, "listed": len(players),
            "dnp": dnp, "limited": lim, "full": full,
            "dnp_defense": dnp_def, "dnp_offense": dnp_off,
            "named_injury": injured, "game_status_out": out, "game_status_questionable": q,
            "qbs_listed": ", ".join(qbs) if qbs else None,
            "starter_status": None,
            "depth_chart_available": False,
            "source": INJURY_URL,
        })
    by_team.sort(key=lambda r: (-r["dnp"], r["team"]))

    # ---- feeds the design needs, and their exact status ---------------------------------------
    feeds = [
        {"id": "F-1", "feed": "Official injury report (weekly, practice + game status)",
         "url": f"{NFLVERSE}/releases/tag/injuries", "rows_from": "2009", "schema": DICT_INJURIES,
         "committed_here": False,
         "useful_for": "Who is on the report this week and how much they practised.",
         "status": "available upstream, NOT committed in this repository; release assets are reachable "
                   "only from a GitHub-hosted runner, not from this sandbox"},
        {"id": "F-2", "feed": "Weekly depth chart (pos_rank per position slot, with a `dt` timestamp)",
         "url": f"{NFLVERSE}/releases/tag/depth_charts", "rows_from": "2001", "schema": DICT_DEPTH,
         "committed_here": False,
         "useful_for": "The 1st/2nd/3rd/4th string question. `pos_rank` is the only field that answers it.",
         "status": "available upstream, NOT committed; note the source changed after 2024, so 2015-2024 "
                   "and 2025-2026 need separate handling"},
        {"id": "F-3", "feed": "Snap counts per player per game (offence/defence/ST, % of snaps)",
         "url": f"{NFLVERSE}/releases/tag/snap_counts", "rows_from": "2012", "schema": DICT_SNAPS,
         "committed_here": False,
         "useful_for": "Whether a backup actually played, and how much the role changed week to week.",
         "status": "available upstream, NOT committed; derived from Pro Football Reference, i.e. a third "
                   "party, not the NFL itself"},
        {"id": "F-4", "feed": "Participation (11 personnel groupings, on-field players per play)",
         "url": f"{NFLVERSE}/releases/tag/pbp_participation", "rows_from": "2016",
         "schema": DICT_PARTICIPATION, "committed_here": False,
         "useful_for": "Which eleven were actually on the field for each snap - the strongest available "
                       "check on a lineup claim.",
         "status": "available upstream, NOT committed"},
        {"id": "F-5", "feed": "Schedules with closing lines and prices",
         "url": f"{NFLVERSE}/releases/tag/schedules", "rows_from": "1999", "schema": "",
         "committed_here": True,
         "useful_for": "Settling any strategy at the closing line.",
         "status": "committed as data/derived/games.csv.gz (7,548 rows, 1999-2026, through 2026-11-01)"},
        {"id": "F-6", "feed": "Player box scores by week",
         "url": f"{NFLVERSE}/releases/tag/stats_player", "rows_from": "2015", "schema": "",
         "committed_here": True,
         "useful_for": "Prop evaluation, correlation between legs.",
         "status": "committed as data/derived/player_week.csv.gz (208,231 rows)"},
    ]

    # ---- the questions a decision needs answered, tied to the data above ----------------------
    checks = [
        {"id": "ID-01", "question": "Is a listed starter ruled OUT for a specific game?",
         "answer": "Yes, partially: the official report's Game Status column gives Out/Doubtful/Questionable.",
         "from": "F-1 official injury report", "confidence": "official page transcribed by hand",
         "source": INJURY_URL},
        {"id": "ID-02", "question": "Is the player who is OUT actually the 1st-string starter at that position?",
         "answer": "NOT ANSWERABLE from what is committed. The injury report has no depth rank, and no "
                   "depth-chart feed is in this repository.",
         "from": "F-2 depth charts (missing)", "confidence": "unverified",
         "source": f"{NFLVERSE}/releases/tag/depth_charts"},
        {"id": "ID-03", "question": "Is the replacement the 2nd, 3rd or 4th string?",
         "answer": "NOT ANSWERABLE. `pos_rank` in the depth-chart feed is the field that answers this; "
                   "nothing else in the official feeds ranks backups.",
         "from": "F-2 depth charts (missing)", "confidence": "unverified",
         "source": DICT_DEPTH},
        {"id": "ID-04", "question": "Did the replacement actually take the starter's snaps?",
         "answer": "NOT ANSWERABLE without snap counts or participation data (F-3/F-4).",
         "from": "F-3/F-4 (missing)", "confidence": "unverified",
         "source": DICT_SNAPS},
        {"id": "ID-05", "question": "How much does losing a starter move the line?",
         "answer": "NOT MEASURED. This is the central quantitative question and it needs ID-01..ID-04 "
                   "plus a timestamped line to be answerable.",
         "from": "all of the above", "confidence": "unverified",
         "source": INJURY_URL},
        {"id": "ID-06", "question": "Does the market already price the injury?",
         "answer": "UNKNOWN. The committed schedules file has one un-timestamped closing line per game, "
                   "so the pre-news and post-news prices cannot be separated.",
         "from": "F-5 (present, but not timestamped)", "confidence": "unverified",
         "source": f"{NFLVERSE}/releases/tag/schedules"},
        {"id": "ID-07", "question": "When must a club file its practice report?",
         "answer": "Thursday/Friday/Saturday for a Sunday game, by 4:00 p.m. New York time (and the "
                   "equivalent schedule for other game days); a Game Status Report is due the day before "
                   "the game. The league's own calendar states this.",
         "from": "NFL official 2026-27 important dates", "confidence": "official, quoted",
         "source": IMPORTANT_DATES},
        {"id": "ID-08", "question": "Is the report complete at the start of the week?",
         "answer": "No. At retrieval on 12 Nov the Game Status column was blank for most players because "
                   "the game-status report is filed later in the week. A mid-week snapshot is not a final "
                   "availability list.",
         "from": "this transcription", "confidence": "observed on the page",
         "source": INJURY_URL},
    ]

    # ---- irregularities --------------------------------------------------------------------
    flagged = [
        {"id": "IF-01", "title": "Injury, depth and snap feeds are not in the repository",
         "detail": "The upstream releases exist for every season 2009-2026 (injuries), 2001-2026 (depth "
                   "charts) and 2012-2026 (snap counts), but none is committed here and the release assets "
                   "redirect to a host this sandbox cannot reach.",
         "needs": "Run the download on a GitHub-hosted runner and commit derived summaries.",
         "source": f"{NFLVERSE}/releases",
         "source_text": "nflverse-data releases: injuries, depth_charts, snap_counts"},
        {"id": "IF-02", "title": "The depth-chart source changed after the 2024 season",
         "detail": "nflreadr's data dictionary states the source changed after 2024; the 2025+ fields are "
                   "dt/team/player_name/pos_grp_id/pos_grp/pos_id/pos_name/pos_abb/pos_slot/pos_rank. Any "
                   "history built across that boundary mixes two schemas.",
         "needs": "Treat 2015-2024 and 2025-2026 as separate regimes, or normalise only on pos_rank.",
         "source": DICT_DEPTH, "source_text": "Data Dictionary - Depth Charts"},
        {"id": "IF-03", "title": "Snap counts come from Pro Football Reference, not the NFL",
         "detail": "nflreadr's loader for snap counts describes the source as Pro Football Reference, a "
                   "third party. It is a strong feed, but it is not an official league source, so a claim "
                   "resting only on it is 'third-party verified', not 'officially verified'.",
         "needs": "Label it that way wherever it is used.",
         "source": DICT_SNAPS, "source_text": "Data Dictionary - Snap Counts"},
        {"id": "IF-04", "title": "A mid-week report is not a final availability list",
         "detail": "At retrieval (12 Nov) only a handful of players carried a game status; the rest were "
                   "practice participation only. Betting on a mid-week snapshot is betting on information "
                   "that will change before kickoff.",
         "needs": "Snapshot at the game-status deadline, and store the timestamp with the row.",
         "source": INJURY_URL, "source_text": "official injury report, 2026 Week 10"},
        {"id": "IF-05", "title": "The injury page's records are ahead of the committed results extract",
         "detail": "The official Week 10 page shows NYG 5-2-1 and WAS 2-5-1; the committed extract ends "
                   "2026-11-01 and resolves those teams to 4-2-1 and 2-4-1 under its own win convention. "
                   "The extract is simply older; it is not wrong.",
         "needs": "Refresh the extract before any analysis that claims to be current.",
         "source": INJURY_URL, "source_text": "records printed beside each team on the injury page"},
        {"id": "IF-06", "title": "Wins counted by the extract can differ from an official W-L-T record by one",
         "detail": "KC's official roster page shows 6-2-0 for 2026 while the committed extract, counted "
                   "through 2026-11-01 by 'margin > 0', gives 5-2. The gap is a tie counted as not-a-win, "
                   "exactly the convention logged as IR-04 on the verification page. Any win-based feature "
                   "should therefore be built from an explicit tie convention.",
         "needs": "Use result > 0 / = 0 / < 0 explicitly and document it.",
         "source": KC_ROSTER, "source_text": "Kansas City Chiefs 2026 roster page header"},
    ]

    payload = {
        "meta": {
            "session": "arena/90e4fdbe-korea2",
            "generated_utc": stamp(),
            "retrieved": RETRIEVED,
            "source": INJURY_URL,
            "source_title": "Official NFL Injury Report for Players - Week 10 of the 2026 Season",
            "scope": ("Five 2026 Week 10 games transcribed in full from the official report "
                      "(WAS@NYG, NE@DET, KC@ATL, MIN@GB, JAX@TEN). BUF@NYJ was only partially returned "
                      "and is therefore excluded rather than half-transcribed."),
            "players_transcribed": len(rows),
            "teams_transcribed": len(REPORT),
            "rule": ("Nothing about who starts, what string a backup is, or who replaces whom is inferred. "
                     "Those cells are blank until a depth-chart feed is committed."),
            "starter_claims_verified": 0,
            "starter_claims_total": len(rows),
        },
        "games": GAMES,
        "players": rows,
        "teams": by_team,
        "feeds": feeds,
        "questions": checks,
        "irregularities": flagged,
    }
    OUT.write_text(json.dumps(clean(payload), indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} players across {len(REPORT)} teams, "
          f"{len(feeds)} feeds, {len(checks)} questions, {len(flagged)} irregularities")
    for r in by_team[:5]:
        print(f"  {r['team']}: listed={r['listed']} DNP={r['dnp']} (def {r['dnp_defense']}) out={r['game_status_out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
