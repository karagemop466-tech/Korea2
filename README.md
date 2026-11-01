# Korea2 — NFL Line Origination & Skill-Based Strategy Research

This repository hosts parallel, verified research into **originating our own NFL betting
lines** (bottom-up models from official data), **signal generation**, **validation gates
that remove luck**, **correlation control for parlays/player-prop combos**, and a
**leaderboard competition design with rewards for top-performing strategies** — covering
single bets, parlays, and player-prop combos.

## Live sites (GitHub Pages, served from `main`)

- **Line Lab** — root site: https://karagemop466-tech.github.io/Korea2/ (`index.html`, `pages/`, `assets/`)
- **NFL Line Origination Dashboard** (this session, `arena-29806afc`): https://karagemop466-tech.github.io/Korea2/dashboard/ — landing dashboard + 10 category subpages (`dashboard/pages/`), every table row carrying official source-link chips
- **Quant Lab** (session `arena/7b140798-korea2`): https://karagemop466-tech.github.io/Korea2/quant-lab/ — originated lines, 21 gated strategies, measured correlations, 77-check verification register
- Independent research from other sessions: `nfl-research/`, `research-desk/`, `nfl-lines/`

## Repository map

| Path | Contents |
| --- | --- |
| `dashboard/` | Line-origination dashboard site (landing + subpages: executive summary, strategies, signals, bet types, validation gates, correlations, leaderboard, data & sources, repo review, flagged for review) |
| `data/*.json` | Verified data layer: 40-source official registry, league facts, bet types, signals, strategies, gates G1–G8, correlations, leaderboard, flagged items, repo review |
| `docs/` | `EXECUTIVE_SUMMARY.md`, `REPO_REVIEW.md` |
| `scripts/` | `validate_data.py` (every row must have official-source links; flagged values must be blank), `check_links.py` (no broken internal links) |
| `tests/` | Other sessions' site checks |
| `.github/workflows/validate.yml` | CI: runs both validators on push/PR |
| `COORDINATION.md` | Shared task board + session logs for all parallel sessions, incl. conflict-resolution record and PR/deploy record |

## Verification policy

Every table row carries official source link(s) — NFL.com / media.nfl.com /
operations.nfl.com / nextgenstats.nfl.com / support.nfl.com, licensed-sportsbook official
help (DraftKings, FanDuel), Nevada Gaming Control Board Regulation 22, NIST/SEMATECH,
Princeton-hosted Kelly (1956), Pinnacle Betting Resources, Kaggle (docs + NFL Big Data
Bowl), NOAA/NWS, NCPG, github.com — each URL checked on 2026-11-01 (see `data/sources.json`).
Any value that cannot be confirmed from an official source is left **blank** and published
on the **Flagged for Review** page (`data/flagged.json`, `dashboard/pages/flagged.html`).
No inferred or hallucinated values.

Run the checks locally:

```bash
python3 scripts/validate_data.py   # data rows + official-source policy
python3 scripts/check_links.py     # internal site links (whole repo)
python3 tests/check_site.py        # other sessions' root-site checks
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

Analytics research only — not a guarantee of profit. Wager only where legal and only if
21+. Free, confidential help 24/7/365 in all 50 states + U.S. territories via the National
Problem Gambling Helpline operated by the
[National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).
