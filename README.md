# Korea2 — NFL Line Origination & Skill-Based Strategy Research

Originate our own NFL lines from official data, validate every strategy through statistical
gates, control parlay correlation, and rank strategies on a leaderboard competition with
rewards for top performers. Covers single bets, parlays, and player-prop combos.

**Live site:** https://karagemop466-tech.github.io/Korea2/ (GitHub Pages, deployed from `main`)

## What's inside

| Path | Contents |
| --- | --- |
| `index.html`, `pages/*.html`, `assets/*` | GitHub Pages dashboard site (landing + category subpages, all tables with per-row official source links) |
| `data/*.json` | Verified data: sources registry, league facts, bet types, signals, strategies, validation gates, correlations, leaderboard, flagged items, repo review |
| `docs/EXECUTIVE_SUMMARY.md` | Executive summary |
| `docs/REPO_REVIEW.md` | Line-by-line repo review with irregularities |
| `scripts/validate_data.py` | CI gate: every table row must have official-source links; flagged values must be blank |
| `scripts/check_links.py` | CI gate: no broken internal site links |
| `.github/workflows/` | `validate.yml` (data + link checks) and `pages.yml` (Pages deploy on push to `main`) |
| `COORDINATION.md` | Shared task board for parallel sessions + session log (tasks, sources, verification, PR/deploy record) |

## Verification policy

Every table row carries official source link(s) (NFL.com / Next Gen Stats / NFL Football
Operations / licensed-sportsbook official help pages / Nevada Gaming Control Board / NIST /
Princeton-hosted Kelly 1956 / Kaggle / NOAA-NWS / NCPG), each URL checked on 2026-11-01 —
see `data/sources.json`. Any value that cannot be confirmed from an official source is left
**blank** and published on the **Flagged for Review** page (`data/flagged.json`,
`pages/flagged.html`). No inferred or hallucinated values.

Run the checks locally:

```bash
python3 scripts/validate_data.py   # data rows + official-source policy
python3 scripts/check_links.py     # internal site links
```

## Responsible gambling

Analytics research only — not a guarantee of profit. Wager only where legal and only if
21+. Free, confidential help 24/7/365 in all 50 states + U.S. territories via the National
Problem Gambling Helpline operated by the
[National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).
