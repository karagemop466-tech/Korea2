#!/usr/bin/env python3
"""Strict verifier for the availability-sweep hub registers.

Checks the committed CSV/JSON data against the sweep's own claims:
- 347 rows, 28 listed teams, every row sourced to the official report page;
- 4 bye teams sourced to the official schedule page;
- 14 games with FINAL scores and game-centre sources;
- capture log integrity (3 dated reads, Week 11 attempt with 0 rows);
- delta register: 33 comparisons, zero changed fields;
- flags register: every flag carries at least one source link;
- status/practice vocabularies exactly match the official page's strings.
Exits nonzero on any failure.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

failures: list[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


rows = read_csv("week10_rows_20261118.csv")
byes = read_csv("week10_byes.csv")
games = read_csv("week10_games.csv")
log = read_csv("capture_log.csv")
counts = read_csv("week10_team_counts_20261118.csv")
delta = read_csv("delta_20261115_20261118.csv")
flags = json.loads((DATA / "flags.json").read_text(encoding="utf-8"))

# --- row register ---
check(len(rows) == 347, f"row count {len(rows)} != 347")
cols = ["team", "game_date", "opponent", "player", "position", "injuries", "practice_status",
        "game_status", "player_url", "source_url", "fetched_utc"]
check(all(list(r.keys()) == cols for r in rows), "row register columns mismatch")

PRACTICE_OK = {"Full Participation in Practice", "Limited Participation in Practice", "Did Not Participate In Practice"}
GAME_OK = {"Out", "Doubtful", "Questionable", ""}
teams_seen = []
for i, r in enumerate(rows, start=2):
    check(r["practice_status"] in PRACTICE_OK, f"row {i}: unknown practice status {r['practice_status']!r}")
    check(r["game_status"] in GAME_OK, f"row {i}: unknown game status {r['game_status']!r}")
    check(r["source_url"] == "https://www.nfl.com/injuries/league/2026/REG10", f"row {i}: bad source_url")
    check(r["player_url"].startswith("https://www.nfl.com/players/"), f"row {i}: bad player_url")
    check(bool(r["player"].strip()) and bool(r["position"].strip()), f"row {i}: missing player/position")
    check(bool(r["fetched_utc"]), f"row {i}: missing fetched_utc")
    if r["team"] not in teams_seen:
        teams_seen.append(r["team"])
    try:
        datetime.strptime(r["game_date"], "%Y-%m-%d")
    except ValueError:
        failures.append(f"row {i}: bad game_date {r['game_date']!r}")

check(len(teams_seen) == 28, f"listed teams {len(teams_seen)} != 28")
EXPECTED_TEAMS = {"WAS", "NYG", "NE", "DET", "KC", "ATL", "MIN", "GB", "JAX", "TEN", "BUF", "NYJ",
                  "MIA", "IND", "CAR", "NO", "HOU", "CLE", "LAR", "AZ", "SEA", "LV", "SF", "DAL",
                  "PIT", "CIN", "LAC", "BAL"}
check(set(teams_seen) == EXPECTED_TEAMS, "listed team set mismatch")
check(len(rows) == len({(r["team"], r["player"]) for r in rows}), "duplicate (team, player) keys in register")

# --- counts register reconciles with the register itself ---
per_team = {t: sum(1 for r in rows if r["team"] == t) for t in teams_seen}
check(sum(int(c["rows"]) for c in counts) == 347, "counts file total != 347")
for c in counts:
    check(per_team.get(c["team"]) == int(c["rows"]), f"counts mismatch for {c['team']}")

# --- independent reconciliation against the 2026-11-15 manual counts ---
old_counts = read_csv_raw = None
alt = (ROOT.parent / "injury-report-w10" / "data" / "week10_team_counts_manual.csv")
check(alt.exists(), "injury-report-w10 manual counts file missing")
if alt.exists():
    with alt.open(newline="", encoding="utf-8") as fh:
        manual = {m["team"]: int(m["listed_players_manual_count"]) for m in csv.DictReader(fh)}
    check(len(manual) == 28, "manual counts do not cover 28 teams")
    # Cross-register code convention: the 2026-11-15 manual-count register writes the Cardinals
    # as ARI; the official injury-report and schedule pages use AZ (club logo slugs, standings).
    # AZ is kept verbatim here; the alias applies only to this reconciliation.
    alias = {"ARI": "AZ"}
    for team, n in manual.items():
        canon = alias.get(team, team)
        check(per_team.get(canon) == n, f"manual count mismatch for {team}: manual {n} vs register {per_team.get(canon)}")

# --- byes ---
check(len(byes) == 4, f"bye rows {len(byes)} != 4")
check({b["team"] for b in byes} == {"CHI", "DEN", "PHI", "TB"}, "bye team set mismatch")
for b in byes:
    check(b["source_url"] == "https://www.nfl.com/schedules/2026/by-week/week-10", f"bye {b['team']}: bad source")
check(not (EXPECTED_TEAMS & {b["team"] for b in byes}), "a bye club also appears in the report register")
check(len(byes) + len(teams_seen) == 32, "28 listed + 4 byes != 32 clubs")

# --- games ---
check(len(games) == 14, f"games {len(games)} != 14")
gteams = {t for g in games for t in (g["away_team"], g["home_team"])}
check(gteams == EXPECTED_TEAMS, "game team set != listed team set")
for g in games:
    check(g["status"] == "FINAL", f"game {g['away_team']}@{g['home_team']} not FINAL")
    check(g["source_url"].startswith("https://www.nfl.com/games/"), f"game {g['away_team']}@{g['home_team']}: bad source")
    check(g["away_score"].isdigit() and g["home_score"].isdigit(), f"game {g['away_team']}@{g['home_team']}: non-numeric score")

# --- capture log ---
check(len(log) == 3, f"capture log rows {len(log)} != 3")
reg11 = [c for c in log if c["week"] == "11"]
check(len(reg11) == 1 and reg11[0]["rows_captured"] == "0", "Week 11 attempt must record 0 rows")
check(all(c["raw_bytes_hash"] == "not retained" for c in log), "raw hash policy rows changed")
for c in log:
    check(bool(c["fetched_utc_end"]), "capture missing end timestamp")
    check(c["source_url"].startswith("https://www.nfl.com/"), "capture source not nfl.com")

# --- delta register ---
overlapping = {(r["team"], r["player"]) for r in csv.DictReader((ROOT.parent / "injury-report-w10" / "data" / "week10_rows_read.csv").open(newline="", encoding="utf-8"))}
check(len(delta) == len(overlapping), f"delta rows {len(delta)} != overlapping {len(overlapping)}")
check({(d["team"], d["player"]) for d in delta} == overlapping, "delta keys != overlapping keys")
check(all(d["changed"] == "no" for d in delta), "delta register contains changed fields; page claim of 0 changes would be false")

# --- flags ---
ids = [f["id"] for f in flags["flags"]]
check(len(ids) == len(set(ids)), "duplicate flag ids")
for f in flags["flags"]:
    srcs = f.get("source_urls", [f.get("source_url", "")])
    check(any(s.startswith("https://") for s in srcs), f"flag {f['id']} has no external source link")

# --- pages present ---
for p in [ROOT / "index.html", ROOT / "pages" / "week10.html", ROOT / "pages" / "deltas.html", ROOT / "pages" / "flags.html"]:
    check(p.exists(), f"missing generated page {p.name}")

print(f"availability-sweep verify: {checks} checks, {len(failures)} failures")
for f in failures:
    print("FAIL:", f)
sys.exit(1 if failures else 0)
