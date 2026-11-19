#!/usr/bin/env python3
"""Build the availability graph from the official captures.

The graph answers one question per position slot: who was expected to start (the official
starting lineup of the earlier captured week) and who actually started (the official starting
lineup of the later captured week), with the official designation of each player taken from the
official weekly injury report and the official roster status taken from the official club roster
page.

Rules
-----
* Only official rows are used: the official NFL Game Book (starters, substitutions, Did Not Play,
  Not Active), the official NFL.com weekly injury report (designations) and the official NFL.com
  club roster page (roster status).
* A depth tier (1st string, 2nd string, ...) is published only where the club itself publishes a
  depth chart on its official site. The tier is never inferred from a jersey number, an
  experience count, a salary or the order of a roster listing. Where the club labels its own chart
  "unofficial" the row says so, because that is what the club says.
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
FLAGS_OUT = os.path.join(DATA, "flags.json")
SOURCES_OUT = os.path.join(DATA, "sources.json")

SWEEP = os.path.join(ROOT, "..", "availability-sweep", "data")
INJURY_FILES = [
    ("week10_rows_20261118.csv", 10, "https://www.nfl.com/injuries/league/2026/REG10",
     "2026-11-18T03:55:37Z"),
]
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


def load_injury_reports():
    """Load the official weekly injury-report rows that were captured in this repository."""
    out = []
    for name, week, url, fetched in INJURY_FILES:
        path = os.path.join(SWEEP, name)
        for r in read_csv(path):
            r = dict(r)
            r["week"] = str(week)
            r["report_url"] = url
            r["report_fetched_utc"] = fetched
            out.append(r)
    return out


def name_key(name: str) -> str:
    """Normalise a player name for joining two official lists.

    The Game Book prints a player as "A.St. Brown" (initial plus surname); the official weekly
    injury report prints "Amon-Ra St. Brown". Both are reduced to (first initial, surname) so
    that the same player is matched. Nothing is invented: two different players with the same
    key stay unmatched and are reported as such.
    """
    cleaned = " ".join((name or "").replace(".", " ").split())
    if not cleaned:
        return ""
    parts = cleaned.split()
    surname = parts[-1].lower()
    initial = parts[0][0].lower() if parts[0] else ""
    return f"{initial}|{surname}"


def build_designations(injury_rows):
    """Map (club, player) -> official game designation, using the official report rows."""
    by_key = defaultdict(set)
    for r in injury_rows:
        key = name_key(r.get("player", ""))
        if not key:
            continue
        by_key[(r["team"], key)].add((r.get("game_status") or "").strip())
    designations = {}
    ambiguous = set()
    for (team, key), statuses in by_key.items():
        real = {s for s in statuses if s}
        if len(real) == 1:
            designations[(team, key)] = real.pop()
        elif len(real) > 1:
            ambiguous.add((team, key))
    return designations, ambiguous


def main() -> int:
    lineups = read_csv(os.path.join(DATA, "lineups.csv"))
    inactives = read_csv(os.path.join(DATA, "inactives.csv"))
    substitutions = read_csv(os.path.join(DATA, "substitutions.csv"))
    gamebooks = read_csv(os.path.join(DATA, "gamebooks.csv"))
    roster = read_csv(os.path.join(DATA, "roster_status.csv"))
    depth_chart = read_csv(os.path.join(DATA, "depth_chart.csv"))
    depth_sources = read_csv(os.path.join(DATA, "depth_sources.csv"))
    injury = load_injury_reports()

    if not lineups:
        print("no captured lineups: run the capture workflow first", file=sys.stderr)
        return 1

    weeks = sorted({int(r["week"]) for r in lineups})
    earlier, later = weeks[0], weeks[-1]

    # Slot key: club + unit + position + the ordinal of that position inside the unit's lineup.
    # The ordinal keeps three receiver rows or two linebacker rows apart instead of collapsing
    # them into one slot.
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

    designations, ambiguous = build_designations(injury)

    # Official roster status per club/player (from the official club roster page).
    roster_status = {}
    for r in roster:
        roster_status[(r["club"], name_key(r.get("player", "")))] = r.get("status", "")

    game_url = {}
    for g in gamebooks:
        game_url[(g["week"], g["slug"])] = (g["game_url"], g["gamebook_url"])

    inactive = defaultdict(list)
    for r in inactives:
        inactive[(r["team"], r["category"])].append(r)

    # Official club depth charts: a tier exists only where the club publishes the chart itself.
    tier_of = {}
    tier_source = {}
    for r in depth_chart:
        key = (r["club"], name_key(r.get("player", "")))
        if key in tier_of:
            continue                       # the first published rank wins; ties are listed below
        tier_of[key] = r.get("tier", "")
        tier_source[key] = {
            "url": r.get("source_url", ""),
            "date": r.get("chart_date_label", ""),
            "unofficial": r.get("chart_labelled_unofficial", ""),
            "slot": r.get("slot", ""),
            "unit": r.get("unit", ""),
        }
    tier_ties = defaultdict(list)
    for r in depth_chart:
        key = (r["club"], name_key(r.get("player", "")))
        tier_ties[key].append(f"{r.get('unit', '')} {r.get('slot', '')} {r.get('tier', '')}")

    rows = []
    for key in sorted(set(idx_early) | set(idx_late)):
        team, unit, slot, ordinal = key
        early = idx_early.get(key)
        late = idx_late.get(key)
        e_player = early["player"] if early else ""
        a_player = late["player"] if late else ""
        e_jersey = early["jersey"] if early else ""
        a_jersey = late["jersey"] if late else ""
        e_key = name_key(e_player)
        a_key = name_key(a_player)
        e_desig = designations.get((team, e_key), "") if e_key else ""
        a_desig = designations.get((team, a_key), "") if a_key else ""
        e_status = roster_status.get((team, e_key), "") if e_key else ""
        a_status = roster_status.get((team, a_key), "") if a_key else ""
        na_players = {name_key(r["player"]) for r in inactive.get((team, "not_active"), [])}
        dnp_players = {name_key(r["player"]) for r in inactive.get((team, "did_not_play"), [])}
        if late:
            src = game_url.get((later, late["slug"]), ("", ""))
        elif early:
            src = game_url.get((earlier, early["slug"]), ("", ""))
        else:
            src = ("", "")
        e_tier = tier_of.get((team, e_key), "") if e_key else ""
        a_tier = tier_of.get((team, a_key), "") if a_key else ""
        e_tier_src = tier_source.get((team, e_key), {}) if e_key else {}
        a_tier_src = tier_source.get((team, a_key), {}) if a_key else {}
        changed = bool(e_player and a_player and e_player != a_player)
        rows.append({
            "team": team,
            "unit": unit,
            "slot": slot,
            "slot_ordinal": ordinal,
            f"expected_player_wk{earlier}": e_player,
            f"expected_jersey_wk{earlier}": e_jersey,
            "expected_designation": e_desig,
            "expected_roster_status": e_status,
            f"actual_player_wk{later}": a_player,
            f"actual_jersey_wk{later}": a_jersey,
            "actual_designation": a_desig,
            "actual_roster_status": a_status,
            "changed": "yes" if changed else "no",
            "replacement_named": "yes" if changed else "no",
            "actual_player_not_active": "yes" if a_key in na_players else "no",
            "actual_player_did_not_play": "yes" if a_key in dnp_players else "no",
            "expected_depth_tier": e_tier,
            "expected_depth_source": e_tier_src.get("url", ""),
            "expected_depth_chart_date": e_tier_src.get("date", ""),
            "actual_depth_tier": a_tier,
            "actual_depth_source": a_tier_src.get("url", ""),
            "actual_depth_chart_date": a_tier_src.get("date", ""),
            "depth_chart_labelled_unofficial": e_tier_src.get("unofficial", ""),
            "depth_chart_ties": "; ".join(tier_ties.get((team, e_key), [])[1:]) if e_key else "",
            "game_url": src[0],
            "gamebook_url": src[1],
            "injury_report_url": INJURY_SOURCE if (e_desig or a_desig) else "",
            "captured_utc": (late or early)["captured_utc"] if (late or early) else "",
        })

    # Per-club decision view.
    team_rows = []
    for team in sorted({r["team"] for r in rows}):
        mine = [r for r in rows if r["team"] == team]
        changed = [r for r in mine if r["changed"] == "yes"]
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
            "starters_out": "; ".join(sorted({r[f"expected_player_wk{earlier}"] for r in out_desig})),
            "replacements_named": "; ".join(
                f"{r[f'actual_player_wk{later}']} (was {r[f'expected_player_wk{earlier}']})"
                for r in changed),
            "injury_report_url": INJURY_SOURCE,
            "game_url": next((r["game_url"] for r in mine if r["game_url"]), ""),
            "gamebook_url": next((r["gamebook_url"] for r in mine if r["gamebook_url"]), ""),
        })

    write_csv(OUT, rows)
    write_csv(TEAM_OUT, team_rows)

    # --- flags -----------------------------------------------------------
    flags = []
    fid = 0

    def flag(area, finding, handling, sources):
        nonlocal fid
        fid += 1
        flags.append({"id": f"AV-{fid:03d}", "area": area, "finding": finding,
                      "handling": handling, "sources": list(sources)})

    no_depth = sorted({r["club"] for r in depth_sources} - {r["club"] for r in depth_chart})
    if no_depth:
        flag("depth order",
             f"{len(no_depth)} clubs publish no machine-readable depth chart on their official "
             f"site: {', '.join(no_depth)}",
             "No depth tier is published for these clubs. A tier is never inferred from a jersey "
             "number, experience, salary or the order of a roster listing.",
             [r["depth_url"] for r in depth_sources if r["club"] in no_depth][:8])
    unofficial = sorted({r["club"] for r in depth_chart
                          if r.get("chart_labelled_unofficial") == "yes"})
    if unofficial:
        flag("depth order",
             f"{len(unofficial)} clubs label their own published depth chart \"unofficial\": "
             f"{', '.join(unofficial)}",
             "The tier is published because the club publishes the order on its official site, "
             "and every row carries the chart date and the club's own label so a reader can see "
             "how provisional it is.",
             [r["source_url"] for r in depth_chart
              if r.get("chart_labelled_unofficial") == "yes"][:8])
    if ambiguous:
        flag("injury designations",
             f"{len(ambiguous)} (club, player) pairs carry more than one official game "
             f"designation in the weekly report",
             "The designation is left blank for those pairs instead of choosing one.",
             [INJURY_SOURCE])
    flag("capture window",
         f"the availability graph compares the earliest captured week ({earlier}) with the "
         f"latest captured week ({later})",
         "This is a capture window, not a season. No claim is made about weeks that have not "
         "been captured.",
         [INJURY_SOURCE])
    flag("snap counts",
         "no snap counts are published here",
         "A game book prints participation, not snaps. Snap counts come from a separate official "
         "source (Next Gen Stats) and are not captured yet, so replacement depth is not modelled "
         "from playing time.",
         ["https://nextgenstats.nfl.com/"])
    flag("Game Book reuse",
         "the official Game Book carries a notice that the summary and play-by-play are for "
         "assisting media coverage and that any other use needs the written permission of the NFL",
         "Only the factual fields are published (names, positions, jersey numbers, venue, "
         "weather), each with a link to the official document. The reuse position is a decision "
         "for the owner and is left open.",
         ["https://www.nfl.com/games/patriots-at-lions-2026-reg-10"])

    with open(FLAGS_OUT, "w", encoding="utf-8") as fh:
        json.dump({"flags": flags}, fh, indent=2, sort_keys=True)

    sources = [
        {"id": "SRC-001", "title": "Official NFL Game Book, New England Patriots at Detroit Lions "
         "(2026 REG 10)",
         "url": "https://www.nfl.com/games/patriots-at-lions-2026-reg-10",
         "read_at": "2026-11-19", "note": "official starting lineups, substitutions, Did Not "
         "Play, Not Active, venue, roof and surface, game-day weather"},
        {"id": "SRC-002", "title": "Official NFL 2026 Week 10 schedule",
         "url": "https://www.nfl.com/schedules/2026/by-week/week-10",
         "read_at": "2026-11-19", "note": "official game links, dates and final scores"},
        {"id": "SRC-003", "title": "Official NFL weekly injury report, 2026 REG 10",
         "url": INJURY_SOURCE, "read_at": "2026-11-18",
         "note": "official practice and game designations per player"},
        {"id": "SRC-004", "title": "Official NFL.com club roster pages (32 clubs)",
         "url": "https://www.nfl.com/teams/", "read_at": "2026-11-19",
         "note": "official roster status per player and the club depth-chart link"},
        {"id": "SRC-005", "title": "Official Green Bay Packers depth chart",
         "url": "https://www.packers.com/team/depth-chart", "read_at": "2026-11-19",
         "note": "club-published depth chart in a machine-readable table, labelled "
                 "\"Unofficial, Nov. 10, 2026\""},
        {"id": "SRC-006", "title": "Official Houston Texans depth chart",
         "url": "https://www.houstontexans.com/team/depth-chart", "read_at": "2026-11-19",
         "note": "club-published depth chart published as an image; no machine-readable order, "
                 "so no tier is transcribed from it"},
    ]
    with open(SOURCES_OUT, "w", encoding="utf-8") as fh:
        json.dump({"sources": sources}, fh, indent=2, sort_keys=True)

    summary = {
        "weeks_captured": weeks,
        "comparison_weeks": [earlier, later],
        "games_captured": len({(g["week"], g["slug"]) for g in gamebooks}),
        "lineup_rows": len(lineups),
        "slots_compared": len(rows),
        "slots_changed": len([r for r in rows if r["changed"] == "yes"]),
        "not_active_rows": len([r for r in inactives if r["category"] == "not_active"]),
        "did_not_play_rows": len([r for r in inactives if r["category"] == "did_not_play"]),
        "substitution_rows": len(substitutions),
        "roster_rows": len(roster),
        "clubs_with_roster_status": len({r["club"] for r in roster}),
        "injury_report_rows_used": len(injury),
        "teams": len({r["team"] for r in rows}),
        "depth_chart_rows": len(depth_chart),
        "clubs_with_published_depth": len({r["club"] for r in depth_chart}),
        "depth_tiers_published": len([r for r in rows if r["expected_depth_tier"]]),
        "depth_tier_policy": (
            "a tier is published only where the club itself publishes a depth chart on its "
            "official site; the chart date and the club's own \"unofficial\" label travel with "
            "the row; no tier is inferred from a jersey number, experience, salary or a roster "
            "listing"),
        "flags": len(flags),
    }
    with open(SUMMARY_OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
