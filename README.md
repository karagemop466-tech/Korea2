# Korea2 — NFL Line Origination & Skill-Based Strategy Research

Parallel, verified research into **originating our own NFL betting lines** from
official data, **signal generation**, **validation gates that remove luck**,
**correlation control for parlays and player-prop combos**, and a **leaderboard
design with rewards for top-performing strategies** — covering single bets,
parlays and player-prop combos.

## Live sites (GitHub Pages, served from `main`)

- **Line Lab** — root site: <https://karagemop466-tech.github.io/Korea2/>
  (`index.html`, `pages/`, `assets/`). Rebuilt by `arena/d88b794a-korea2` into a measured,
  fully sourced research site.
- **NFL Line Origination Dashboard** (`arena-29806afc`):
  <https://karagemop466-tech.github.io/Korea2/dashboard/>
- **Quant Lab** (`arena/7b140798-korea2`):
  <https://karagemop466-tech.github.io/Korea2/quant-lab/> — originated lines, 21 gated
  strategies, measured correlations, 77-check verification register (self-contained in `quant-lab/`).
- **Origination lab** (`arena/3f5af27c-korea2`):
  <https://karagemop466-tech.github.io/Korea2/origination/> — self-contained pipeline and 13-page site:
  own spread/total/moneyline for 7,548 games, 31 strategies through ten gates, prop origination,
  correlations, 18-check verification register. Everything the page shows comes from
  `origination/site_data/*.json`; run it with `python pipeline/run_all.py`.
- Independent research from other sessions: `nfl-research/`, `research-desk/`, `nfl-lines/`.

## Repository map

| Path | Contents |
| --- | --- |
| `index.html`, `pages/` | Line Lab site — 12 pages generated from `results/*.json` |
| `scripts/analysis/` | The quantitative pipeline: data prep, market baseline, strategy engine, correlation study, props, line origination, verification, site render |
| `quant-lab/` | Self-contained quant lab (session `7b140798`): pipeline, 21-strategy backtest, nine gates, correlations, 77-check verification register, 12-page site |
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
| `pipeline/`, `origination/` | Session `3f5af27c`: the origination/strategy/gating pipeline and its 13-page site |
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

## Quant Lab — originated lines, gated strategies, verification (session `7b140798`)

**Live site:** https://karagemop466-tech.github.io/Korea2/quant-lab/

An end-to-end quantitative lab that lives entirely in `quant-lab/` and touches no other
session's files:

| Path | Contents |
| --- | --- |
| `quant-lab/index.html` | landing dashboard (KPIs, headline findings, navigation) |
| `quant-lab/lines.html` | originated spread/total for Weeks 9-10 next to the market close |
| `quant-lab/props.html` | player-prop board, QB/WR correlation, same-game pricing error |
| `quant-lab/strategies.html` | 21 pre-registered strategies, discovery vs holdout |
| `quant-lab/leaderboard.html` | competition rules, scoring, rewards, results |
| `quant-lab/correlation.html` | every correlation value with n and 95% CI |
| `quant-lab/validation.html` | nine gates and the pass/fail matrix |
| `quant-lab/verification.html` | 77 line-by-line checks against nfl.com |
| `quant-lab/flagged.html` | unverified items, assumptions, 10 irregularities |
| `quant-lab/methodology.html` | model, walk-forward design, luck removal |
| `quant-lab/sources.html` | provenance, pinned commit, file hashes |
| `quant-lab/EXECUTIVE_SUMMARY.md` | one-page summary |

Reproduce (no manual input, no hand-typed values):

```bash
cd quant-lab
bash scripts/fetch_data.sh        # pinned raw data from github.com only
python3 scripts/build_dataset.py  # -> data/processed/games.json
python3 scripts/model.py          # originate lines, walk-forward
python3 scripts/backtest.py       # settle all 21 strategies
python3 scripts/props.py          # prop board + correlations
python3 scripts/validation.py     # nine gates, FDR, leaderboard
python3 scripts/verify_official.py# 77 checks vs nfl.com
python3 scripts/build_site.py     # regenerate the site + link check
```

Result: **0 of 21 strategies clear all nine gates**; the closing line is not beaten. What does
hold up is measured correlation for parlay pricing and a verification register that proves the
bulk data against official nfl.com standings, 64 team-seasons for 64.

## Responsible gambling

Analytics research only — not a guarantee of profit. Wager only where legal and
only if 21+. Free, confidential help 24/7/365 in all 50 states and U.S.
territories via the
[National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).

## Origination Lab (session `6206fba3`)

<https://karagemop466-tech.github.io/Korea2/origination-lab/> — self-contained in
`origination-lab/`: a 21-season line-origination model, 27 pre-registered signals
(Benjamini–Hochberg corrected), an 18-strategy competition behind seven validation
gates, correlation values for parlay/pricing, a luck-permutation layer, a
player-prop origination layer, and a 15-page site built from `origination-lab/data/derived/*.json`.

```bash
python origination-lab/scripts/fetch_data.py     # download + verify nflverse extracts
python origination-lab/scripts/build_all.py      # every artefact, then the site
python origination-lab/scripts/check_links.py    # internal links + external host probe
```

Headline: the model is within 10.69 points of the actual margin against the closing
line's 10.26; no strategy cleared all seven gates, so nothing is ranked as playable.
14 irregularities are published on the site's Flagged for review page.
