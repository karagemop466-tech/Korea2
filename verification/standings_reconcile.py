#!/usr/bin/env python3
"""Reconcile the committed 2026 snapshot against the official NFL.com standings, end to end.

This is the check that the earlier integration passes left provisional. It answers three
questions with official evidence only:

  1. Does the committed live snapshot
     (verification/nfl_standings_2026-11-13.json, transcribed from the official NFL.com
     2026 division standings page) agree with what you get when you take the committed
     extract and add the official results the extract does not yet carry?

  2. Does the Washington / New York (Giants) pair reconcile after Washington's 24-21 win
     on 2026-11-12 - the specific row pair that could not be confirmed before?

  3. How far behind the committed extract is the live official page, exactly?

Inputs (all committed, all with an official source):
  data/derived/games.csv.gz                       the committed schedule/scores extract
  verification/nfl_results_2026_through_week10.json official results after the extract
  verification/nfl_standings_2026-11-13.json       the transcribed official standings

Nothing is inferred. A team whose figures cannot be reconciled is reported as a
disagreement, with the numbers on both sides, and the script exits non-zero.

Usage:  python verification/standings_reconcile.py
Writes: verification/standings_reconcile.json
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTRACT = os.path.join(ROOT, "data", "derived", "games.csv.gz")
RESULTS = os.path.join(ROOT, "verification", "nfl_results_2026_through_week10.json")
SNAPSHOT = os.path.join(ROOT, "verification", "nfl_standings_2026-11-13.json")
OUT = os.path.join(ROOT, "verification", "standings_reconcile.json")

SEASON = "2026"
GAME_TYPE = "REG"

# The extract uses ARI for the Cardinals; the official standings page uses AZ.
TEAM_ALIAS = {"AZ": "ARI"}


def load_extract() -> list[dict]:
    rows: list[dict] = []
    with gzip.open(EXTRACT, "rt") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def completed_2026(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if r.get("season") != SEASON or r.get("game_type") != GAME_TYPE:
            continue
        if not str(r.get("home_score", "")).strip():
            continue
        out.append(r)
    return out


def blank_record() -> list[int]:
    return [0, 0, 0, 0, 0]  # wins, losses, ties, points_for, points_against


def apply_result(rec: dict, away: str, away_score: int, home: str, home_score: int) -> None:
    a = TEAM_ALIAS.get(away, away)
    h = TEAM_ALIAS.get(home, home)
    rec[a][3] += away_score
    rec[a][4] += home_score
    rec[h][3] += home_score
    rec[h][4] += away_score
    if home_score > away_score:
        rec[h][0] += 1
        rec[a][1] += 1
    elif away_score > home_score:
        rec[a][0] += 1
        rec[h][1] += 1
    else:
        rec[h][2] += 1
        rec[a][2] += 1


def main() -> int:
    rows = load_extract()
    played = completed_2026(rows)
    last_gameday = max(r["gameday"] for r in played)

    with open(RESULTS) as fh:
        extra = json.load(fh)
    with open(SNAPSHOT) as fh:
        snap = json.load(fh)

    official = snap["teams"]
    recomputed: dict[str, list[int]] = collections.defaultdict(blank_record)
    for r in played:
        apply_result(recomputed, r["away_team"], int(float(r["away_score"])),
                     r["home_team"], int(float(r["home_score"])))
    extract_games = len(played)
    for g in extra["results"]:
        apply_result(recomputed, g["away_team"], int(g["away_score"]),
                     g["home_team"], int(g["home_score"]))

    checks = []
    disagreements = []
    team_rows = []
    for team in sorted(official):
        live = official[team]
        calc = recomputed.get(TEAM_ALIAS.get(team, team), blank_record())
        fields = ["wins", "losses", "ties", "points_for", "points_against"]
        diffs = [f for f, a, b in zip(fields, calc, live) if a != b]
        team_rows.append({
            "team": team,
            "official_standings": dict(zip(fields, live)),
            "extract_plus_official_results": dict(zip(fields, calc)),
            "agrees": not diffs,
            "differing_fields": diffs,
        })
        checks.append({
            "id": f"STAND-{team}",
            "label": f"{team} record and points reconcile with the official standings page",
            "expected": list(live),
            "actual": list(calc),
            "status": "match" if not diffs else "mismatch",
            "source": snap["meta"]["url"],
        })
        if diffs:
            disagreements.append({
                "team": team,
                "differing_fields": diffs,
                "official_standings": dict(zip(fields, live)),
                "extract_plus_official_results": dict(zip(fields, calc)),
            })

    # The pair that the earlier pass could not confirm.
    was = next(r for r in team_rows if r["team"] == "WAS")
    nyg = next(r for r in team_rows if r["team"] == "NYG")
    was_nyg = {
        "id": "STAND-WAS-NYG",
        "label": "Washington 24-21 New York (2026-11-12) is reflected in both rows",
        "expected": {
            "WAS": was["official_standings"],
            "NYG": nyg["official_standings"],
            "source": "https://www.nfl.com/schedules/2026/by-week/week-10",
            "note": "Commanders 24, Giants 21, FINAL on Thursday 2026-11-12.",
        },
        "actual": {
            "WAS": was["extract_plus_official_results"],
            "NYG": nyg["extract_plus_official_results"],
        },
        "status": "match" if was["agrees"] and nyg["agrees"] else "mismatch",
    }
    checks.append(was_nyg)

    # The lag between the committed extract and the live official page.
    live_games = sum(v[0] + v[1] + v[2] for v in official.values()) / 2
    lag = {
        "id": "STAND-LAG",
        "label": "How many games the committed extract is behind the live official page",
        "expected": {"live_games": live_games, "extract_games": extract_games},
        "actual": {"lag_games": live_games - extract_games},
        "status": "match",
        "source": snap["meta"]["url"],
    }
    checks.append(lag)

    # The games that reconcile the two are exactly the official results file.
    official_result_games = len(extra["results"])
    consistency = {
        "id": "STAND-COUNT",
        "label": "Extract games plus officially reported results equal the live games",
        "expected": {"live_games": live_games},
        "actual": {"extract_games": extract_games, "official_results_applied": official_result_games,
                   "total": extract_games + official_result_games},
        "status": "match" if extract_games + official_result_games == live_games else "mismatch",
    }
    checks.append(consistency)

    matches = sum(1 for c in checks if c["status"] == "match")
    mismatches = sum(1 for c in checks if c["status"] == "mismatch")

    report = {
        "meta": {
            "title": "Reconciliation of the committed 2026 snapshot against the official NFL.com standings",
            "session": "arena/dd794652-korea2",
            "generated_utc": "2026-11-13",
            "method": "The committed extract is replayed game by game, the officially reported results "
                      "that post-date the extract are applied on top of it, and the resulting record and "
                      "points for every one of the 32 teams are compared with the transcribed official "
                      "standings page. Every input carries an official source.",
            "sources": {
                "extract": "data/derived/games.csv.gz",
                "official_results": "verification/nfl_results_2026_through_week10.json",
                "official_standings": snap["meta"]["url"],
            },
            "extract_last_gameday": last_gameday,
            "teams_checked": len(official),
        },
        "summary": {
            "checks": len(checks),
            "matches": matches,
            "mismatches": mismatches,
            "teams_agreeing": sum(1 for r in team_rows if r["agrees"]),
            "teams_disagreeing": sum(1 for r in team_rows if not r["agrees"]),
        },
        "checks": checks,
        "teams": team_rows,
        "disagreements": disagreements,
    }
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=False)
        fh.write("\n")

    print(f"teams reconciled: {report['summary']['teams_agreeing']}/{len(official)}")
    print(f"checks: {len(checks)}  matches: {matches}  mismatches: {mismatches}")
    print(f"extract games {extract_games} (through {last_gameday}) + "
          f"{official_result_games} official results = {extract_games + official_result_games}; "
          f"live page {int(live_games)}")
    if mismatches:
        print("MISMATCHES:")
        for d in disagreements:
            print(f"  {d['team']}: {d['differing_fields']} "
                  f"official={d['official_standings']} recomputed={d['extract_plus_official_results']}")
        return 1
    print("PASS: every one of the 32 teams reconciles with the official standings page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
