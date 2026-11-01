# Korea2 — NFL Line Origination & Skill-Based Strategy Research

This repository hosts parallel, verified research into **originating our own NFL betting
lines** (bottom-up models from official data), **signal generation**, **validation gates
that remove luck**, **correlation control for parlays/player-prop combos**, and a
**leaderboard competition design with rewards for top-performing strategies** — covering
single bets, parlays, and player-prop combos.

## Live sites (GitHub Pages, served from `main`)

- **Line Lab** — root site: https://karagemop466-tech.github.io/Korea2/ (`index.html`, `pages/`, `assets/`)
- **NFL Line Origination Dashboard** (this session, `arena-29806afc`): https://karagemop466-tech.github.io/Korea2/dashboard/ — landing dashboard + 10 category subpages (`dashboard/pages/`), every table row carrying official source-link chips
- Independent research from other sessions: `nfl-research/`, `research-desk/`

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

## Responsible gambling

Analytics research only — not a guarantee of profit. Wager only where legal and only if
21+. Free, confidential help 24/7/365 in all 50 states + U.S. territories via the National
Problem Gambling Helpline operated by the
[National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).
