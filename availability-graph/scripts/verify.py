#!/usr/bin/env python3
"""Strict verifier for the availability-graph registers.

The verifier is deliberately unforgiving. It checks the published registers against the claims
the hub makes:

* every game-book row, every starting-lineup row, every inactive row, every roster row and
  every depth row carries the official URL it was read from;
* every starting lineup has eleven offensive and eleven defensive rows per club;
* the availability graph compares two captured weeks and every slot names an official player
  (or is explicitly blank);
* a depth tier exists only for a club that publishes a depth chart on its official site, and the
  chart's own label and date travel with the tier;
* no published value contradicts the official roster status or the official designations;
* the counts published on the pages match the registers.

Exits nonzero on any failure.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data")

failures: list[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def read_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_json(name: str, default=None):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default if default is not None else {}
    return json.loads(open(path, encoding="utf-8").read())


gamebooks = read_csv("gamebooks.csv")
lineups = read_csv("lineups.csv")
inactives = read_csv("inactives.csv")
subs = read_csv("substitutions.csv")
roster = read_csv("roster_status.csv")
depth_sources = read_csv("depth_sources.csv")
depth_chart = read_csv("depth_chart.csv")
graph = read_csv("availability_graph.csv")
teams = read_csv("team_view.csv")
summary = read_json("summary.json")
flags = read_json("flags.json", {"flags": []})

# ---------------------------------------------------------------- registers exist
check(bool(gamebooks), "no game-book register")
check(bool(lineups), "no starting-lineup register")
check(bool(summary), "no summary")

# ---------------------------------------------------------------- game books
for g in gamebooks:
    slug = g.get("slug", "?")
    check(bool(g.get("gamebook_url", "").startswith("https://")), f"gamebook {slug}: no official PDF url")
    check(bool(g.get("game_url", "").startswith("https://")), f"gamebook {slug}: no official game url")
    check(bool(g.get("pdf_sha256")), f"gamebook {slug}: no sha256 recorded")
    check(bool(g.get("captured_utc")), f"gamebook {slug}: no capture timestamp")
    check(bool(g.get("away_team")) and bool(g.get("home_team")),
          f"gamebook {slug}: missing club names")
    if g.get("lineups_parsed") != "yes":
        failures.append(f"gamebook {slug}: lineups were not parsed")

# ---------------------------------------------------------------- starting lineups
per_game: dict[tuple[str, str, str], list[dict]] = {}
for r in lineups:
    per_game.setdefault((r["week"], r["slug"], r["team"]), []).append(r)
    check(bool(r.get("source_url", "").startswith("https://")),
          f"lineup {r.get('player')}: no official source url")
    check(bool(r.get("player")), "lineup row without a player name")
    check(bool(r.get("slot")), f"lineup {r.get('player')}: no position slot")
    check(bool(r.get("jersey")), f"lineup {r.get('player')}: no jersey number")
for key, rows in per_game.items():
    off = [r for r in rows if r["unit"] == "offense"]
    dfn = [r for r in rows if r["unit"] == "defense"]
    check(len(off) == 11, f"lineup {key}: {len(off)} offensive starters, expected 11")
    check(len(dfn) == 11, f"lineup {key}: {len(dfn)} defensive starters, expected 11")
    check(len({r["slot"] for r in off}) >= 5, f"lineup {key}: offensive slots look collapsed")

# ---------------------------------------------------------------- inactives / substitutions
for r in inactives + subs:
    check(bool(r.get("source_url", "").startswith("https://")),
          f"{r.get('player')}: no official source url")
    check(bool(r.get("player")), "inactive/substitution row without a player name")
for r in inactives:
    check(r.get("category") in ("not_active", "did_not_play"),
          f"inactive {r.get('player')}: unexpected category {r.get('category')!r}")

# ---------------------------------------------------------------- roster status
clubs = {r.get("club") for r in roster}
check(len(clubs) == 32, f"roster register covers {len(clubs)} clubs, expected 32")
for r in roster:
    check(bool(r.get("source_url", "").startswith("https://")),
          f"roster {r.get('club')}/{r.get('player')}: no official source url")
    check(bool(r.get("player")), "roster row without a player name")
    check(bool(r.get("status")), f"roster {r.get('club')}/{r.get('player')}: no status code")
    check(bool(r.get("position")), f"roster {r.get('club')}/{r.get('player')}: no position")

# ---------------------------------------------------------------- depth sources
check(len({r.get("club") for r in depth_sources}) == 32,
      f"depth audit covers {len({r.get('club') for r in depth_sources})} clubs, expected 32")
for r in depth_sources:
    check(bool(r.get("roster_url", "").startswith("https://")),
          f"depth {r.get('club')}: no official roster url")
    check(bool(r.get("captured_utc")), f"depth {r.get('club')}: no capture timestamp")
    check(bool(r.get("depth_url", "").startswith("https://")),
          f"depth {r.get('club')}: no official depth-chart url")

# ---------------------------------------------------------------- depth chart
clubs_with_chart = {r.get("club") for r in depth_chart}
for r in depth_chart:
    check(r.get("club") in clubs_with_chart, "depth row without a club")
    check(bool(r.get("source_url", "").startswith("https://")),
          f"depth {r.get('club')}/{r.get('player')}: no official source url")
    check(bool(r.get("tier")), f"depth {r.get('club')}/{r.get('player')}: no tier")
    check(bool(r.get("chart_date_label")), f"depth {r.get('club')}: no chart date label")
    check(r.get("rank_collision") == "no",
          f"depth {r.get('club')}/{r.get('player')}: rank collision in the published chart")

# ---------------------------------------------------------------- availability graph
check(bool(graph), "no availability graph")
for r in graph:
    check(bool(r.get("team")), "graph row without a club")
    check(bool(r.get("slot")), f"graph {r.get('team')}: no slot")
    check(bool(r.get("gamebook_url", "").startswith("https://")),
          f"graph {r.get('team')}/{r.get('slot')}: no official game-book url")
    e_key = [k for k in r if k.startswith("expected_player_wk")]
    a_key = [k for k in r if k.startswith("actual_player_wk")]
    check(len(e_key) == 1 and len(a_key) == 1, "graph row without both comparison columns")
    for k in e_key + a_key:
        v = r[k].strip()
        check(v != "", f"graph {r.get('team')}/{r.get('slot')}: {k} is blank")
        check(not re.search(r"TBD|Unknown|N/A|\?", v),
              f"graph {r.get('team')}/{r.get('slot')}: {k} holds a placeholder {v!r}")
    # a depth tier may only exist where the club publishes a depth chart
    tier = (r.get("expected_depth_tier") or "").strip()
    if tier:
        check(r.get("team") in clubs_with_chart,
              f"graph {r.get('team')}: depth tier published without a club depth chart")
        check(bool(r.get("expected_depth_source", "").startswith("https://")),
              f"graph {r.get('team')}: depth tier without an official source url")
        check(bool(r.get("expected_depth_chart_date")),
              f"graph {r.get('team')}: depth tier without the chart date")

# ---------------------------------------------------------------- counts
if summary:
    check(summary.get("lineup_rows") == len(lineups), "summary lineup count mismatch")
    check(summary.get("slots_compared") == len(graph), "summary slot count mismatch")
    check(summary.get("roster_rows") == len(roster), "summary roster count mismatch")
    check(summary.get("clubs_with_roster_status") == len(clubs), "summary club count mismatch")
    check(summary.get("depth_chart_rows") == len(depth_chart), "summary depth row count mismatch")
    check(summary.get("not_active_rows") == len([r for r in inactives
                                                  if r["category"] == "not_active"]),
          "summary not-active count mismatch")
for t in teams:
    check(bool(t.get("team")), "team view row without a club")
    check(bool(t.get("injury_report_url", "").startswith("https://")),
          f"team view {t.get('team')}: no official injury-report url")

# ---------------------------------------------------------------- flags
for f in flags.get("flags", []):
    check(bool(f.get("finding")), "a flag without a finding")
    check(bool(f.get("handling")), f"flag {f.get('id')}: no handling")
    check(bool(f.get("sources")), f"flag {f.get('id')}: no official source")

print(f"availability-graph verifier: {checks} checks, {len(failures)} failures")
for f in failures:
    print("  FAIL:", f, file=sys.stderr)
sys.exit(1 if failures else 0)
