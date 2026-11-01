# COORDINATION.md — Shared task board

This file is the shared task board for every agent session working in this repository.
Read it before starting any work. Update it before you start, and when you finish.

## Session registry

| Session ID | Branch | Role | Started (UTC) | Last commit (UTC) | Status |
|---|---|---|---|---|---|
| `arena-3f5af27c` | `arena/3f5af27c-korea2` | Sole session in this run: claims all tasks, acts as integration session | 2026-11-01T13:2x | see `git log` | active |

**Branch-lock note.** This run is pinned by the platform to branch `arena/3f5af27c-korea2`
(the session branch may not be renamed and no other branch may be created or pushed by this
session). The generic convention `session-<id>/<task>` is therefore satisfied by the single
session branch above; the per-task scopes below are enforced by directory instead, which keeps
every scope non-overlapping and reviewable.

## Task board

Status values: `unclaimed` · `in progress` · `done` · `needs review` (published on the
Flagged-for-Review page, does not block anything).

| ID | Task | Status | Owner | File scope |
|---|---|---|---|---|
| T01 | Data acquisition, provenance, checksums, dataset coverage audit | done | arena-3f5af27c | `pipeline/fetch_data.py`, `data/raw/`, `data/PROVENANCE.md` |
| T02 | Game-level feature build (no-lookahead ratings, Elo, situational) | done | arena-3f5af27c | `pipeline/build_features.py`, `pipeline/lib/` |
| T03 | Line origination model (own spread / total / moneyline) | done | arena-3f5af27c | `pipeline/originate.py` |
| T04 | Strategy generation (single bets, parlays, prop combos) | done | arena-3f5af27c | `pipeline/strategies.py` |
| T05 | Validation gates + luck removal (bootstrap, permutation, DSR, CLV) | done | arena-3f5af27c | `pipeline/gates.py` |
| T06 | Correlation engine (market, leg, prop correlations) | done | arena-3f5af27c | `pipeline/correlation.py` |
| T07 | Player-prop line origination + calibration (unpriced) | done | arena-3f5af27c | `pipeline/props.py` |
| T08 | Verification pass: official-source cross-checks, unverified flagging | done | arena-3f5af27c | `pipeline/verify.py`, `verification/` |
| T09 | Requirements register (line-by-line, status per requirement) | done | arena-3f5af27c | `REQUIREMENTS.md` |
| T10 | Static site (landing page + category subpages) | done | arena-3f5af27c | `index.html`, `assets/`, `pages/`, `site_data/` |
| T11 | Executive summary | done | arena-3f5af27c | `EXECUTIVE_SUMMARY.md`, `pages/summary.html` |
| T12 | Integration: re-verify combined data, link check, PR to `main`, merge, Pages deploy | done | arena-3f5af27c | `.github/workflows/`, PR |

## Change log

| UTC | Session | Event |
|---|---|---|
| 2026-11-01T13:26 | arena-3f5af27c | Board created. Data-reachability probe completed: outbound network from this sandbox allows only `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`. GitHub release assets (`release-assets.githubusercontent.com`) and `raw.githubusercontent.com` are **not** reachable from the shell; `codeload.github.com` tarballs of data repositories **are**. Consequence: `nflverse/nflverse-data` release CSVs could not be downloaded; the repo's own committed data (mirrors of the same upstream feeds) were used instead. Recorded as irregularity IR-01. |
| 2026-11-01T13:26 | arena-3f5af27c | Claims recorded for T01–T12. Scopes are non-overlapping by directory; no other session is active. |

## Source log (what was used, and why)

| ID | Source | Official? | Used for | Link |
|---|---|---|---|---|
| S1 | NFL.com schedules / game pages | official league site | cross-verification of scheduled and final scores | https://www.nfl.com/schedules/ and `https://www.nfl.com/games/<slug>` |
| S2 | `nflverse/nfldata` (mirror of `leesharpe/nfldata`) `data/games.csv` | open dataset (third-party, maintained) | historical results, closing spread/total/moneylines, rest, roof, weather, officials | https://github.com/nflverse/nfldata/blob/main/data/games.csv |
| S3 | `nflverse/nfldata` `data/closing_lines.csv` | third-party | closing prices + outcomes 2006–2018 | https://github.com/nflverse/nfldata/blob/main/data/closing_lines.csv |
| S4 | `nflverse/nfldata` `data/initial_lines.csv` | third-party | opening (Wednesday) lines, 2021 only | https://github.com/nflverse/nfldata/blob/main/data/initial_lines.csv |
| S5 | `ryurko/nflscrapR-data` `legacy_data/game_player_stats/*.csv` | third-party, derived from NFL play-by-play | player-game box statistics 2009–2019 | https://github.com/ryurko/nflscrapR-data |
| S6 | `nflverse/nflverse-pfr` `data/adv_stats/*_season.csv` | third-party aggregation of Pro-Football-Reference | cross-check of player aggregate statistics | https://github.com/nflverse/nflverse-pfr |
| S7 | Pro-Football-Reference | trusted stats aggregator (not the league) | spot verification of lines/scores | https://www.pro-football-reference.com/ |

## Irregularities / requests

| ID | Type | Detail | Handling |
|---|---|---|---|
| IR-01 | data-access | GitHub release assets and `raw.githubusercontent.com` unreachable from the sandbox shell, so the canonical `nflverse-data` release CSVs (`player_stats`, `pbp`, `schedules`) could not be pulled. | Used the same feeds as committed in `nflverse/nfldata` and `ryurko/nflscrapR-data`, both pinned by commit SHA and SHA-256 in `data/PROVENANCE.md`. Published on the Flagged-for-Review page. |
| IR-02 | data-gap | Player-level game data reachable in this environment ends at the 2019 season (nflscrapR) / 2022 (nflverse-pfr advanced stats). No 2023–2026 player-game feed was reachable. | Player-prop lines are validated on 2009–2019 only; 2023–2026 prop cells are left **blank** and flagged unverified. No value is inferred. |
| IR-03 | data-gap | No licensed sportsbook player-prop price feed is reachable, so prop strategies carry **no market price**. | Prop skill is measured against a pre-declared naive reference line, not against a book. ROI for props is left blank and flagged. |
| IR-04 | data-gap | Opening lines (`initial_lines.csv`) exist for 2021 only (544 games, one book, spread+total, no moneylines). | Opening-line strategies are reported as sample-limited and fail the sample-size gate; flagged, not silently dropped. |
