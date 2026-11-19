# Integration verification — 2026-11-19 (session `arena/995191cd-korea2`)

Final integration pass over the combined tree. Every claim below was checked against the
live official NFL.com page at the time of writing, or recomputed from the committed
registers. Source links are given for manual review. Nothing was inferred; where a value
could not be confirmed it is left blank and flagged on the hub's own Flagged for Review page.

## Official pages re-read (2026-11-19)

| Official source | What was checked | Result |
|---|---|---|
| [Week 10 2026 injury report](https://www.nfl.com/injuries/league/2026/reg10) | Full page read, all club tables | **Confirmed:** 347 listed rows across 28 club tables; 171 carry a game designation (Out 70, Questionable 90, Doubtful 11, blank 176). The canonical URL still serves the Week 10 report (its `<title>` says "Week 11", the in-page heading says WEEK 10 — a known title/body mismatch, not a data error). |
| Same | Kerby Joseph, Cade Mays, D.J. Reed (DET) | **Confirmed:** all three read **Out** (Did Not Participate). Closes the "three missing Lions designations" item. |
| Same | Cincinnati, Seattle row counts | **Confirmed:** CIN = 9 rows, SEA = 15 rows, matching the committed register exactly. |
| Same | Absent clubs | **Confirmed:** CHI, DEN, PHI, TB have no table; the [Week 10 schedule page](https://www.nfl.com/schedules/2026/by-week/week-10) lists all four under "Teams on Bye". |
| [Week 10 2026 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) | All fixtures and scores | **Confirmed:** 14/14 games FINAL with both scores; 4 clubs on bye. Matches `requirements-desk/data/results_2026_w10.csv` row for row. |
| [Week 11 2026 schedule](https://www.nfl.com/schedules/2026/by-week/week-11) | All fixtures, kickoffs, networks, venues | **Confirmed:** 13 fixtures; 6 clubs on bye; 1 neutral-site game (MIN@SF, Mexico City). Matches `requirements-desk/data/schedule_2026_w11.csv`. |
| [2026 division standings](https://www.nfl.com/standings/division/2026/REG) | 32 clubs, points for/against | **Confirmed:** 32 clubs; BUF 8-1 (287/199), NE 5-5 (221/242), etc., match `requirements-desk/data/standings_2026.csv`. |

## Recomputed from the committed registers

The four official correlations and the luck panel were recomputed from
`requirements-desk/data/standings_2026.csv` and reproduce `requirements-desk/data/analysis.json`
exactly (Pearson on win pct, Fisher-z 95% intervals, Pythagorean exponent 2.65):

- Win pct vs points for: **+0.657** [+0.400, +0.818], n=32
- Win pct vs points against: **−0.670** [−0.826, −0.419], n=32
- Win pct vs net points: **+0.875** [+0.758, +0.938], n=32
- Win pct vs Pythagorean expected wins: **+0.872** [+0.752, +0.936], n=32
- Luck SD: **1.076** wins across 32 clubs (one season; persistence untested)

Method reference: [NIST DATAPLOT correlation confidence limits](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm).

## Checks run (all pass on the final tree)

- `python3 tests/check_site.py` — 252 pages, 666 tables, 16,877 links; all rows source-linked.
- `python3 scripts/check_links.py` — 5,762 local references, no broken internal links.
- `python3 scripts/validate_data.py`, `python3 tests/check_data.py`, `python3 tests/check_derived.py` — pass.
- `python3 verification/recompute.py` — 52 checks, 0 mismatches; 2020 and 2026 reconciliations 32/32 teams.
- `python3 requirements-desk/scripts/verify.py` — 14 pages, 27 tables, 1,091 links, 74 requirements, 6 registers.
- `python3 line-desk/scripts/build_site.py --check` and `verify.py` — pass (16 registers, deterministic).
- `python3 price-desk/scripts/verify.py` — 20,504 checks, 0 errors; 10 unit tests OK.
- `python3 review-board/scripts/verify_all.py` — 131 checks, 0 failures (after register rebuild, see below).
- `python3 decision-desk/scripts/verify_all.py`, `verify-hub` (7 unit tests), `price-store` (9 tests),
  `availability-sweep` (2,224 checks), `injury-capture/scripts/check_against_expected.py` — pass
  (28/28 teams, 347 rows).

## Irregularities found and resolved in this pass

1. **`requirements-desk/data/analysis.json` was stale.** It had been generated before the
   `injury-capture` job's sixth successful manifest (`reg10_2026_20261118T041840Z.json`) existed,
   so it recorded 5 successful automated runs instead of 6. Re-running `analyze.py` regenerated it
   (the correlation and luck values were already correct and reproduce exactly). The injuries and
   verification pages were rebuilt to show "6 successful runs".
2. **`review-board` registers needed a rebuild.** `ingest.py` had not been re-run after sibling
   registers changed, so `reconciliation.json` and two pages were stale. Re-running `ingest.py`
   and `build_site.py` regenerated them; `verify_all.py` now reports 131 checks / 0 failures.
3. **README / EXECUTIVE_SUMMARY counts were stale.** The rendered register already showed
   37 partial / 16 blocked, but both docs still said 36 partial / 17 blocked. Updated to match.
4. **Cosmetic stamp churn (recorded, not hidden).** `data/derived/verification.json` and
   `verification/recompute.json` carry a `generated_utc` run timestamp that changes on every local
   run. The values they carry are unchanged; the timestamps were refreshed by this pass and are
   excluded from any data claim.

## Still open (published on Flagged for Review, not blocking)

- No official timestamped open/close price archive; official-only `price-store` snapshot is empty.
- No verified 32-club depth source; replacement names and string tiers are blank by policy.
- The 136-game pre-registered backtest corpus is not yet frozen with official results for every game.
- No strategy has passed validation; the reward pool is unfunded.

*Research, not betting advice.*
