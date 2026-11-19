#!/usr/bin/env python3
"""Build the availability graph from the official captures.

The graph answers one question per position slot: who was expected to start (the official
starting lineup of the previous captured week) and who actually started (the official starting
lineup of the later week), with the official designation of each player taken from the official
weekly injury report and the official roster status taken from the official club roster page.

Rules
-----
* Only official rows are used: the official NFL Game Book (starters, substitutions, Did Not Play,
  Not Active), the official NFL.com weekly injury report (designations) and the official NFL.com
  club roster page (roster status).
* A depth tier (1st string, 2nd string, ...) is published ONLY where an official depth order has
  been verified for that club. Until then the tier is blank and the row is flagged.
* Nothing is inferred: a blank means "not published by an official source", never "healthy".
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "availability_graph.csv")
TEAM_OUT = os.path.join(DATA, "team_view.csv")
SUMMARY_OUT = os.path.join(DATA, "summary.json")

INJURY_ROWS = os.path.join(ROOT, "availability-sweep", "data", "week10_rows_20261118.csv")
INJURY_SOURCE = "https://www.nfl.com/injuries/league/2026/REG10"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    lineups = read_csv(os.path.join(DATA, "lineups.csv"))
    inactives = read_csv(os.path.join(DATA, "inactives.csv"))
    gamebooks = read_csv(os.path.join(DATA, "gamebooks.csv"))
    roster = read_csv(os.path.join(DATA, "roster_status.csv"))
    injury = read_csv(INJURY_ROWS)

    if not lineups:
        print("no captured lineups: run the capture workflow first", file=sys.stderr)
        return 1

    weeks = sorted({int(r["week"]) for r in lineups})
    earlier, later = weeks[0], weeks[-1]

    # Slot key: club + unit + position + ordinal of that position within the unit's lineup.
    def slot_index(rows):
        counters = defaultdict(int)
        out = {}
        for r in rows:
            key = (r["team"], r["unit"], r["slot"])
            counters[key] += 1
            out[(r["team"], r["unit"], r["slot"], counters[key])] = r
        return out

    by_week = defaultdict(list)
    for r in lineups:
        by_week[int(r["week"])].append(r)
    idx_early = slot_index(by_week[earlier])
    idx_late = slot_index(by_week[later])

    # Official injury-report designations for the later week.
    designation = {}
    for r in injury:
        key = (r["team"], r["player"])
        status = (r.get("game_status") or "").strip()
        if status:
            designation[key] = status

    # Official roster status per club/player (from the official club roster page).
    roster_status = {}
    for r in roster:
        roster_status[(r["club"], r["player"])] = r["status"]

    game_url = {}
    for g in gamebooks:
        game_url[(g["week"], g["slug"])] = (g["game_url"], g["gamebook_url"])

    # Inactive players (official Not Active / Did Not Play lists).
    inactive = defaultdict(list)
    for r in inactives:
        inactive[(r["team"], r["category"])].append(r)

    rows = []
    for key in sorted(set(idx_early) | set(idx_late)):
        team, unit, slot, ordinal = key
        early = idx_early.get(key)
        late = idx_late.get(key)
        e_player = early["player"] if early else ""
        a_player = late["player"] if late else ""
        e_jersey = early["jersey"] if early else ""
        a_jersey = late["jersey"] if late else ""
        e_desig = designation.get((team, e_player), "") if e_player else ""
        a_desig = designation.get((team, a_player), "") if a_player else ""
        e_status = roster_status.get((team, e_player), "") if e_player else ""
        a_status = roster_status.get((team, a_player), "") if a_player else ""
        na_players = {r["player"] for r in inactive.get((team, "not_active"), [])}
        dnp_players = {r["player"] for r in inactive.get((team, "did_not_play"), [])}
        if late:
            src = game_url.get((later, late["slug"]), ("", ""))
        elif early:
            src = game_url.get((earlier, early["slug"]), ("", ""))
        else:
            src = ("", "")
        rows.append({
            "team": team,
            "unit": unit,
            "slot": slot,
            "slot_ordinal": ordinal,
            "expected_player_wk%d" % earlier: e_player,
            "expected_jersey_wk%d" % earlier: e_jersey,
            "expected_designation": e_desig,
            "expected_roster_status": e_status,
            "actual_player_wk%d" % later: a_player,
            "actual_jersey_wk%d" % later: a_jersey,
            "actual_designation": a_desig,
            "actual_roster_status": a_status,
            "changed": "yes" if (e_player and a_player and e_player != a_player) else "no",
            "replacement_named": "yes" if (e_player and a_player and e_player != a_player) else "no",
            "actual_player_not_active": "yes" if a_player in na_players else "no",
            "actual_player_did_not_play": "yes" if a_player in dnp_players else "no",
            "depth_tier": "",                      # blank until an official depth order is verified
            "game_url": src[0],
            "gamebook_url": src[1],
            "injury_report_url": INJURY_SOURCE if (e_desig or a_desig) else "",
            "captured_utc": (late or early)["captured_utc"] if (late or early) else "",
        })

    # Per-club view.
    team_rows = []
    for team in sorted({r["team"] for r in rows}):
        mine = [r for r in rows if r["team"] == team]
        changed = [r for r in mine if r["changed"] == "yes"]
        starters_out = [r for r in mine if r["actual_designation"] in ("Out", "Doubtful", "Questionable")]
        out_desig = [r for r in mine if r["expected_designation"] == "Out"]
        na = inactive.get((team, "not_active"), [])
        dnp = inactive.get((team, "did_not_play"), [])
        report_rows = [r for r in injury if r["team"] == team]
        net = sum(1 for r in report_rows if (r.get("game_status") or "").strip() == "Out")
        q = sum(1 for r in report_rows if (r.get("game_status") or "").strip() == "Questionable")
        d = sum(1 for r in report_rows if (r.get("game_status") or "").strip() == "Doubtful")
        team_rows.append({
            "team": team,
            "slots_compared": len(mine),
            "slots_changed": len(changed),
            "out_designated": net,
            "questionable": q,
            "doubtful": d,
            "not_active": len(na),
            "did_not_play": len(dnp),
            "net_injury_count": net,
            "starters_out": "; ".join(sorted({r["expected_player_wk%d" % earlier] for r in out_desig})),
            "replacements_named": "; ".join(
                f"{r['actual_player_wk%d' % later]} (was {r['expected_player_wk%d' % earlier]})"
                for r in changed),
            "injury_report_url": INJURY_SOURCE,
            "game_url": next((r["game_url"] for r in mine if r["game_url"]), ""),
            "gamebook_url": next((r["gamebook_url"] for r in mine if r["gamebook_url"]), ""),
        })

    write_csv(OUT, rows)
    write_csv(TEAM_OUT, team_rows)

    summary = {
        "weeks_captured": weeks,
        "comparison_weeks": [earlier, later],
        "games_captured": len({(g["week"], g["slug"]) for g in gamebooks}),
        "lineup_rows": len(lineups),
        "slots_compared": len(rows),
        "slots_changed": len([r for r in rows if r["changed"] == "yes"]),
        "not_active_rows": len([r for r in inactives if r["category"] == "not_active"]),
        "did_not_play_rows": len([r for r in inactives if r["category"] == "did_not_play"]),
        "substitution_rows": len(read_csv(os.path.join(DATA, "substitutions.csv"))),
        "roster_rows": len(roster),
        "clubs_with_roster_status": len({r["club"] for r in roster}),
        "injury_report_rows_used": len(injury),
        "teams": len({r["team"] for r in rows}),
        "depth_tiers_published": 0,
        "depth_tier_policy": (
            "blank: a depth tier is published only where an official depth order has been verified "
            "for that club; no tier is inferred from a roster listing, a jersey number, experience "
            "or salary"),
    }
    with open(SUMMARY_OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
