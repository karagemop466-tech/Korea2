# Coordination board

Multiple agent sessions work in this repository at the same time. This file is the
shared task board. Claim a task by writing your session id and file scope, commit
and push the claim, and never start a task another session has claimed.

| Task | Status | Owner | File scope |
|---|---|---|---|
| Research, build, verify and integrate NFL dashboard (v1 shell) | done | `arena/97d4c0f1-korea2` | `index.html`, `assets/`, `pages/`, `tests/check_site.py` |
| Quantitative build: data pipeline, market baseline, strategy engine, correlations, props, line origination | done | `arena/d88b794a-korea2` | `scripts/`, `data/`, `results/`, `.github/workflows/fetch-nflverse.yml`, `tests/check_data.py`, `tests/check_site.py` |
| Official-source verification against NFL.com (32 teams + 3 player lines) | done | `arena/d88b794a-korea2` | `scripts/analysis/verification.py`, `results/verification.json` |
| Rebuild site pages from measured results | needs review | `arena/d88b794a-korea2` | `index.html`, `pages/`, `assets/style.css` (appended rules only) |
| Final integration and GitHub Pages publish | in progress | `arena/d88b794a-korea2` | `README.md`, `COORDINATION.md`, `.github/workflows/build-verify.yml` |

## Branch policy note

The Arena runtime fixes each session to one branch. This session therefore works
only on `arena/d88b794a-korea2` and cannot create `session-<id>/<task>` branches;
the branch name is the session id. Two sessions cannot edit the same file without a
pull-rebase conflict, so scopes above are kept disjoint: this session did **not**
rewrite the v1 page bodies of `pages/*.html` until it owned the whole render, and it
appended to `assets/style.css` rather than replacing it.

## Session log

### `arena/97d4c0f1-korea2` — v1 shell (merged, PR #2)

- Built a dependency-free static site with a clean sidebar layout and a
  four-column table format.
- Deliberately published **no numbers**: every value was `—` and every strategy was
  "not eligible; gates not run". No data pipeline existed.
- Recorded its own irregularities on the Flagged for Review page.
- Merged to `main` as `597e815`; GitHub Pages deployed successfully.

### `arena/d88b794a-korea2` — this session

**Claimed:** quantitative build, official verification, site render, final integration.

**What was added**

| Area | Detail |
|---|---|
| Data pipeline | `.github/workflows/fetch-nflverse.yml` downloads nflverse releases and commits pruned extracts plus `data/provenance.json` (row counts, seasons, SHA-256 of the raw source). Raw downloads are gitignored. |
| Market baseline | `scripts/analysis/market.py` — line calibration, blind-bet returns at the stored price, 12 public angles with Benjamini–Hochberg correction. |
| Strategy engine | `scripts/analysis/strategies.py` — opponent-adjusted ratings solved by least squares, refitted before every week, five pre-registered strategies, six validation gates, permutation luck test. |
| Correlation study | `scripts/analysis/correlations.py` — 11 measured pairs with Fisher-z intervals, plus same-game parlay pricing versus independence. |
| Player props | `scripts/analysis/props.py` — walk-forward projections with no leakage, median line calibration, per-season skill. |
| Line origination | `scripts/analysis/originate.py` — spread and total for every unplayed game, published beside the market number. |
| Verification | `scripts/analysis/verification.py` — 2026 standings rebuilt and reconciled against NFL.com, plus a three-quarterback passing spot check. |
| Site | `scripts/analysis/build_site.py` renders all 12 pages from `results/*.json`. |

**Sources used**

- NFL.com division standings, 2026 regular season —
  <https://www.nfl.com/standings/division/2026/REG>
- NFL.com player passing stats, 2026 —
  <https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc>
- NFL.com team stats, 2026 — <https://www.nfl.com/stats/team-stats/>
- NFL.com schedules — <https://www.nfl.com/schedules/2026/by-week/week-8>
- nflverse data releases (third-party redistributor of NFL play-by-play) —
  <https://github.com/nflverse/nflverse-data/releases>

**Verification performed**

- Sign convention of `spread_line` proved from the data itself before any
  settlement: 2,920 games with a positive line all have a negative home moneyline
  (100.0%), and 1,553 games with a negative line have a positive home moneyline
  (0.0% negative). Home covers when `result - spread_line > 0`.
- All 32 teams' 2026 wins, losses, ties, points for and points against match
  NFL.com exactly across 108 settled games.
- Three quarterback passing lines (yards, touchdowns, interceptions, completions,
  attempts) rebuilt from the player feed match NFL.com exactly.
- Every external link used by the site was fetched during this session and
  returned content; no link is inferred from a pattern alone.
- `tests/check_site.py` fails the build on a broken local link, a table row
  without an https source link, a missing nav entry, or an unrendered value.
- `tests/check_data.py` asserts that no strategy is ranked without clearing every
  gate, that no prop ROI exists, and that the verification counts match their rows.

**Irregularities logged**

1. The source file's `spread_line` is positive when the home team is favoured,
   which is the opposite of the commonly documented reading. Resolved by proof, but
   the documentation mismatch is unresolved and is on the review page.
2. The wind-under angle misses Benjamini–Hochberg by 0.001 (p = 0.021 against a
   0.020 threshold with five tests) and is flat in the holdout. Unresolved.
3. Weather fields cover roughly 57% of 2020–2026 games and only outdoor venues; if
   missingness is not random the weather result is biased. Untested.
4. Everything is settled at the closing price. A real bettor cannot reliably get
   the close, so realised returns would be worse. No opening-line history exists in
   the data to quantify it.
5. No free official source publishes historical player-prop prices, so the props
   page reports projection skill only and claims no prop ROI.
6. Only the 2026 season is reconciled team by team against NFL.com; 1999–2025
   shares the pipeline but was not individually checked.
7. Push handling reduces a parlay ticket to its remaining legs, which not every
   book does.
8. Seven other session branches existed during this work
   (`00966de7`, `1955d40e`, `70a33596`, `97d4c0f1`, `9e0420bd`, `e0d506a4`,
   `7b140798`). Only `97d4c0f1` published content before this session; its shell
   was rebased onto rather than replaced. Session `70a33596` was independently
   running a sign-convention test at the time of writing — duplicate work, noted
   rather than merged, because it did not publish a branch with content.

**Handoff / conflict log**

- No merge conflict occurred. This session rebased onto `main` at `597e815` and
  built on top of the v1 shell, keeping its navigation, layout, footer disclaimer
  and `tests/check_site.py` contract.
- Where the v1 shell said "no values available", this session replaced the value
  with a measurement and a source link; where a value still cannot be confirmed it
  is rendered as `unverified`.
