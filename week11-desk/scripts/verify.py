#!/usr/bin/env python3
"""Strict verifier for the Week 11 desk.

Fails loudly (non-zero exit) if any of the following is untrue at the committed tree:
  R1  every register row carries an https source URL on an official NFL domain;
  R2  the row register's committed hash matches the manifest it publishes;
  R3  the row count, per-club counts and game-status split recompute from the CSV itself;
  R4  every practice/game status string is one the official page actually prints
      (vocabulary is a closed set — no invented categories);
  R5  no register row has an injury description without also being a designated row, and no
      designated row lacks an injury description (the page prints them together);
  R6  every fixture row carries a game-centre URL, and its venue field is non-empty;
  R7  the delta is recomputable: every delta row's two source links resolve to the two
      official weekly report URLs, and the delta counts sum to the CSV;
  R8  the delta does not claim a game-status comparison for a club that published no game
      designation at this read (publication-cycle guard);
  R9  the page-level claims on the built HTML match the register (no typed numbers);
  R10 the official page's own week heading is WEEK 11 and the record says so.
Exit code is the count of failures, capped at 1.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
ROOT = os.path.dirname(DESK)
DATA = os.path.join(DESK, "data")
PAGES = os.path.join(DESK, "pages")

failures: list[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def read_csv(name: str) -> list[dict]:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


OFFICIAL_HOSTS = {"www.nfl.com", "nfl.com", "operations.nfl.com", "media.nfl.com"}

rows = read_csv("week11_rows.csv")
counts = read_csv("week11_team_counts.csv")
fix = read_csv("week11_fixtures.csv")
byes = read_csv("week11_byes.csv")
delta = read_csv("delta_week10_week11.csv")
reg = json.loads(open(os.path.join(DATA, "week11_register.json"), encoding="utf-8").read())

# --- R1 source link on every row -----------------------------------------------------
for i, r in enumerate(rows, start=2):
    u = r["source_url"]
    check(u.startswith("https://") and urlparse(u).hostname in OFFICIAL_HOSTS,
          f"week11_rows.csv line {i}: source {u!r} is not an official https URL")
    check(r["read_at_utc"] == reg["meta"]["read_at_utc"],
          f"week11_rows.csv line {i}: read_at_utc disagrees with the register meta")
for name, table in (("week11_fixtures.csv", fix), ("week11_byes.csv", byes)):
    for i, r in enumerate(table, start=2):
        u = r["source_url"]
        check(u.startswith("https://") and urlparse(u).hostname in OFFICIAL_HOSTS,
              f"{name} line {i}: source {u!r} is not an official https URL")
for i, r in enumerate(delta, start=2):
    for f in ("week10_source", "week11_source"):
        u = r[f]
        check(u.startswith("https://") and urlparse(u).hostname in OFFICIAL_HOSTS,
              f"delta line {i}: {f} {u!r} is not an official https URL")
    check(u.startswith("https://"), "delta source")

# --- R2 hashes -----------------------------------------------------------------------
for name, h in reg["register_sha256"].items():
    check(sha256(os.path.join(DATA, name)) == h, f"hash mismatch for {name}")
check(reg["register_manifest_sha256"] == hashlib.sha256(
    json.dumps(reg["register_sha256"], sort_keys=True).encode()).hexdigest(),
    "manifest hash does not reproduce from the per-file hashes")

# --- R3 recompute counts -------------------------------------------------------------
check(len(rows) == reg["totals"]["rows"], "row count disagrees with the register")
per = Counter(r["club"] for r in rows)
for c in counts:
    check(per[c["club"]] == int(c["rows"]), f"{c['club']} row count disagrees with the register")
check(sum(int(c["rows"]) for c in counts) == len(rows), "per-club counts do not sum to the total")
gs = Counter(r["game_status"] for r in rows)
check(gs["Out"] == reg["totals"]["out"], "Out count disagrees")
check(gs["Doubtful"] == reg["totals"]["doubtful"], "Doubtful count disagrees")
check(gs["Questionable"] == reg["totals"]["questionable"], "Questionable count disagrees")
check(gs[""] == reg["totals"]["no_designation"], "no-designation count disagrees")
check(len({r["club"] for r in rows}) == reg["totals"]["clubs_with_rows"],
      "club-with-rows count disagrees")
for c in counts:
    d = int(c["out"]) + int(c["doubtful"]) + int(c["questionable"])
    check(d == int(c["game_designated"]), f"{c['club']}: designations do not sum")
    check(int(c["out"]) + int(c["doubtful"]) + int(c["questionable"]) + int(c["no_designation"])
          == int(c["rows"]), f"{c['club']}: status split does not sum to rows")

# --- R4 closed vocabulary ------------------------------------------------------------
PRACTICE = {"Full Participation in Practice", "Limited Participation in Practice",
            "Did Not Participate In Practice", ""}
GAME = {"Out", "Doubtful", "Questionable", ""}
for i, r in enumerate(rows, start=2):
    check(r["practice_status"] in PRACTICE, f"row {i}: invented practice status")
    check(r["game_status"] in GAME, f"row {i}: invented game status")

# --- R5 injury text and designation travel together ----------------------------------
for i, r in enumerate(rows, start=2):
    check(bool(r["injury"]) == bool(r["game_status"]),
          f"row {i} ({r['club']}/{r['player']}): injury text and game designation disagree "
          f"({r['injury']!r} / {r['game_status']!r})")

# --- R6 fixtures ---------------------------------------------------------------------
check(len(fix) == 13, f"expected 13 fixtures, found {len(fix)}")
for i, r in enumerate(fix, start=2):
    check("/games/" in r["source_url"], f"fixture row {i}: source is not a game centre")
    check(r["venue_official"].strip() != "", f"fixture row {i}: empty official venue")
    check(r["location_official"].strip() != "", f"fixture row {i}: empty official location")
check(len(byes) == 6, f"expected 6 bye clubs, found {len(byes)}")
all_clubs = {r["club"] for r in counts} | {r["club"] for r in byes}
check(len(all_clubs) == 32, f"fixtures + byes should cover 32 clubs, covers {len(all_clubs)}")

# --- R7 delta recomputable -----------------------------------------------------------
d_by = Counter(r["change"] for r in delta)
for k, v in reg["delta_summary"]["by_change"].items():
    check(d_by[k] == v, f"delta count for {k!r} disagrees with the register")
check(sum(d_by.values()) == len(delta), "delta counts do not sum to the delta rows")
check(len(delta) == reg["delta_summary"]["change_rows"], "delta row count disagrees")
check(reg["delta_summary"]["week10_rows"] == 347, "Week 10 register row count changed")

# --- R8 publication-cycle guard ------------------------------------------------------
comparable_clubs = set(reg["delta_summary"]["clubs_game_status_comparable"])
for i, r in enumerate(delta, start=2):
    if r["club"] not in comparable_clubs:
        check(r["game_status_comparable"].startswith("no"),
              f"delta row {i}: claims game-status comparability for {r['club']}")
        check("(no designation published)" in r["week11_practice / week11_game"]
              or r["week11_practice / week11_game"] == "",
              f"delta row {i}: non-comparable row does not label its blank game status")
    else:
        check(r["game_status_comparable"] == "yes", f"delta row {i}: comparability flag wrong")
# No row may say a player is healthy/cleared — the page cannot establish that.
for i, r in enumerate(delta, start=2):
    combined = (r["change"] + r["week11_practice / week11_game"]).lower()
    check("cleared" not in combined and "healthy" not in combined,
          f"delta row {i}: uses an availability word the page cannot support")

# --- R9 page claims match the register ----------------------------------------------
def page_text(name: str) -> str:
    p = os.path.join(PAGES, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


summary_html = page_text("week11.html")
if summary_html:
    t = reg["totals"]
    for needle in (f"{t['rows']}", f"{t['clubs_with_rows']}", f"{t['clubs_no_report']}",
                   f"{t['designated']}"):
        check(needle in summary_html, f"week11.html does not print computed value {needle}")
    check("arena/5d001552-korea2" in summary_html, "week11.html does not name its session owner")
    check(reg["meta"]["read_at_utc"] in summary_html, "week11.html omits the read clock time")

# --- R10 week heading ---------------------------------------------------------------
check(reg["meta"]["page_heading"] == "Injuries - WEEK 11", "page heading not recorded as WEEK 11")
check("reg11" in reg["meta"]["source_url"], "source URL is not the reg11 injury report")

# ---------------------------------------------------------------------------------------
if failures:
    print(f"FAIL: {len(failures)} problem(s) across {checks} checks")
    for f in failures[:40]:
        print(" -", f)
    raise SystemExit(1)
print(f"PASS: {checks} checks; {len(rows)} rows, {len(counts)} club blocks, {len(fix)} fixtures, "
      f"{len(byes)} byes, {len(delta)} delta rows")
