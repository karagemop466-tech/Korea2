# Korea2 — NFL Line Origination & Skill-Based Strategy Research

Parallel, verified research into **originating our own NFL betting lines** from
official data, **signal generation**, **validation gates that remove luck**,
**correlation control for parlays and player-prop combos**, and a **leaderboard
design with rewards for top-performing strategies** — covering single bets,
parlays and player-prop combos.

## Live sites (GitHub Pages, served from `main`)

- **Line Lab** — root site: <https://karagemop466-tech.github.io/Korea2/>
  (`index.html`, `pages/`, `assets/`). This session (`arena/d88b794a-korea2`)
  rebuilt it into a measured, fully sourced research site.
- **NFL Line Origination Dashboard** (`arena-29806afc`):
  <https://karagemop466-tech.github.io/Korea2/dashboard/>
- Independent research from other sessions: `nfl-research/`, `research-desk/`

## Repository map

| Path | Contents |
| --- | --- |
| `index.html`, `pages/` | Line Lab site — 12 pages generated from `results/*.json` |
| `scripts/analysis/` | The quantitative pipeline: data prep, market baseline, strategy engine, correlation study, props, line origination, verification, site render |
| `data/derived/` | Committed pruned nflverse extracts (raw downloads are gitignored) |
| `data/provenance.json` | URL, row count and SHA-256 of every source file used |
| `results/` | Committed JSON outputs; the single source of truth for the site |
| `tests/check_data.py` | Statistical invariants the prose depends on |
| `tests/check_site.py` | Links, navigation, one source link per table row |
| `dashboard/` | Line-origination dashboard site from session `arena-29806afc` |
| `data/*.json` | Verified data layer from session `arena-29806afc` (source registry, league facts, signals, gates G1–G8) |
| `docs/` | `EXECUTIVE_SUMMARY.md`, `REPO_REVIEW.md` |
| `scripts/` | `validate_data.py`, `check_links.py` from other sessions |
| `.github/workflows/` | `build-verify.yml` (this session), `validate.yml` (dashboard), `fetch-nflverse.yml` (data refresh) |
| `COORDINATION.md` | Shared task board and session logs for all parallel sessions |

## Run the quantitative build

```bash
pip install pandas numpy scipy
python scripts/analysis/build.py     # regenerate results/ and every page
python tests/check_data.py           # statistical invariants
python tests/check_site.py           # links and source coverage
```

`build.py` makes no network calls and is deterministic: CI re-runs it and fails if
the committed output differs.

## Method

Every rule is fixed before outcomes are examined and only uses pre-kickoff
information. Seasons are walked forward — each season is predicted using earlier
seasons only. Bets settle at the closing price stored in the data, never an
assumed −110. A strategy enters the leaderboard only after clearing six gates:
sample size, two-sided significance, Benjamini–Hochberg correction across every
strategy tried, positive return with a bootstrap interval that excludes zero, a
permutation test against random portfolios of the same size, and a minimum
track-record length. **No strategy currently clears all six.**

## Verification policy

Two tiers of source, never blurred:

- **Official** — NFL.com standings, schedules, player stats and team stats. All
  **32 of 32** 2026 team records (W, L, T, PF, PA) reconcile exactly, as do three
  quarterback passing lines across yards, touchdowns, interceptions, completions
  and attempts.
- **Third-party** — nflverse publishes machine-readable extracts of the NFL's own
  play-by-play and box scores, including historical closing prices that no league
  source publishes. Byte sizes and SHA-256 of every file are in
  `data/provenance.json`.

Every table row on the Line Lab site carries an https source link; the build fails
if one does not. Any value that cannot be confirmed from an official source is
rendered as **unverified** and published on the **Flagged for review** page.

Other sessions' policy (see `data/sources.json`): every row carries official
source links checked on 2026-11-01; unconfirmable values are left blank and listed
on `dashboard/pages/flagged.html`.

Run the other sessions' checks too:

```bash
python3 scripts/validate_data.py   # data rows + official-source policy
python3 scripts/check_links.py     # internal site links (whole repo)
```

## Responsible gambling

Analytics research only — not a guarantee of profit. Wager only where legal and
only if 21+. Free, confidential help 24/7/365 in all 50 states and U.S.
territories via the
[National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).
