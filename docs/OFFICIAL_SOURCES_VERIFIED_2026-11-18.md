# Official sources verified — 2026-11-18

**Session:** `arena/b41401cb-korea2` (branch `arena/b41401cb-korea2`, base `f7b8e8f` of `main`).
**Date:** 2026-11-18 (local timezone UTC, Amsterdam).

Each source below was opened and read directly during this session. These reads confirm that the official source exists and publishes the described structure. They do **not** confirm that any committed model value, line, probability, correlation or strategy result is correct. No committed table value was changed as a result of these reads.

## 1. NFL 2026 division standings

- URL: https://www.nfl.com/standings/division/2026/REG
- Title observed: "2026 NFL Division Standings"
- Confirmed: page lists all 32 NFL clubs across AFC and NFC divisions with W, L, T, win percentage, points for, points against, point differential, division record, conference record, conference rank, home/away records, last-10 and streak.
- Sample rows observed (AFC East): Buffalo 8-1-0 (287-199), New England 5-5-0 (221-242), NY Jets 2-8-0 (194-254), Miami 1-8-0 (148-224).
- Limitation: standings only. No odds, lines, injury, depth, snap or starter data.

## 2. NFL Week 10 injury report (2026 season)

- URL: https://www.nfl.com/injuries/league/2026/reg10
- Title observed: "Official NFL Injury Report for Players - Week 10 of the 2026 Season | NFL.com"
- Confirmed: official per-club injury tables with columns Player, Position, Injuries, Practice Status, Game Status.
  - Thursday Nov 12: Commanders (3-5-1) vs Giants (5-3-1). Example rows: Lucas Patrick (C, Concussion, DNP, Out), Colson Yankoff (TE, Knee, DNP, Out); Giants Malik Harrison (LB, Groin, Limited, Questionable).
  - Sunday Nov 15: Patriots (5-5) vs Lions (7-2). Lions: Kerby Joseph (S, Knee, DNP, Out), Cade Mays (C, Ankle, DNP, Out), D.J. Reed (CB, Hip, DNP, Out), Amon-Ra St. Brown (WR, Rib, Limited, Questionable). Patriots: Ben Brown (C, Knee, DNP, Out), Carlton Davis III (CB, Knee, DNP, Out), TreVeyon Henderson (RB, Illness, DNP, Out), A.J. Brown (WR, Ankle/Knee, Limited, Questionable).
- Limitation: single weekly capture. No raw-response hash retained, no historical archive, no depth-rank, starter or snap-share evidence. Practice status and game status are blank for many rows; blanks are preserved, not inferred.

## 3. NFL Week 10 schedule / results (2026 season)

- URL: https://www.nfl.com/schedules/2026/by-week/week-10
- Title observed: "NFL Week 10 Schedule 2026: Games, Times, Matchups & Tickets"
- Confirmed official Week 10 final results:
  - Commanders 24, Giants 21 (Thu Nov 12, 8:15 PM, Prime Video)
  - Patriots 10, Lions 35 (Sun Nov 15, Munich international game)
  - Chiefs 35, Falcons 13
  - Texans 24, Browns 27
  - Vikings 30, Packers 10
  - Dolphins 22, Colts 24
  - Panthers 20, Saints 17
  - Bills 31, Jets 12
  - Jaguars 40, Titans 23
  - Rams 34, Cardinals 6
  - Seahawks 21, Raiders 13
  - 49ers 46, Cowboys 40
- Limitation: final scores only. No opening/closing lines, no player props, no venue weather data.

## Policy applied

- Every table row that depends on an external value must carry a source link to an official site.
- If a value cannot be confirmed from an official source, it is left blank and flagged unverified.
- Nothing is inferred: no starter status, string depth, inactives, snap share, missing injury designation or price is filled in.
- Third-party data (e.g. nflverse community releases) is labelled third-party and is not presented as officially verified.

## Verification performed in this session

- `python3 scripts/check_links.py` — PASS: 4,637 local references across 232 HTML pages + 1 JS file; no broken internal links.
- `python3 tests/check_site.py` — PASS: 232 pages, 584 tables, 13,560 links (33 non-root-build pages lack the root table-source column; link-checked only).
- `python3 scripts/validate_data.py` — PASS for root data-validation scope.

## Sources for manual review

All three official URLs above are live and readable. Commit hash for this session's claim: to be recorded on push/merge.
