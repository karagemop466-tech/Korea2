# Requirements matrix

Every requirement in the brief, where it is addressed, and whether it is verified, computed, or
flagged. "Computed" means produced by committed code from the documented data source; "flagged" means
it could not be established and is published on the Flagged for Review page instead of being guessed.

| # | Requirement (from the brief) | Where it is addressed | Status | Evidence |
|---|---|---|---|---|
| 1 | Collect and organize a full list of requirements | this file | Done | requirement-by-requirement matrix |
| 2 | Originate own NFL lines | `pages/lines.html`; `scripts/analyze_model.py` | Computed | Week 9 2026: 15 games with model spread, total, home win probability and fair moneyline |
| 3 | Originate player-prop lines | `pages/props.html`; `scripts/analyze_props.py` | Computed | 4 stat families, per-player lines with P(over) for the next slate |
| 4 | Research strategies that generate useful signals | `pages/strategies.html`; `scripts/analyze_strategies.py` | Computed | 7 registered hypotheses with pre-declared definitions |
| 5 | Leaderboard competition with rewards for top strategies | `pages/leaderboard.html` | Computed + proposal | Ranking by gates then ROI; reward tiers are a design proposal (unfunded) |
| 6 | Single bets | `pages/validation.html` | Computed | S1, S2, S3, S4, S5, S6, S7 |
| 7 | Parlays | `pages/correlation.html`, `pages/strategies.html` | Computed | Correlation-aware joint pricing, independence error, parlay EV table |
| 8 | Player-prop bet combos | `pages/correlation.html`, `pages/props.html` | Partly computed | Leg correlations measured; combo pricing derived; market comparison flagged (no prop prices) |
| 9 | Each strategy must pass validation gates | `pages/validation.html` | Computed | 10 gates, 0 strategies approved, exact failing gate listed per strategy |
| 10 | Determine correlation values | `pages/correlation.html` | Computed | 15 pairs with r, 95% Fisher-z CI, n; 4-leg correlation matrix and copula price |
| 11 | Remove luck from the equation | `pages/luck.html` | Computed | Pythagorean R², luck persistence r = 0.019, one-score persistence, ATS coin-flip test, sample-size table |
| 12 | Selectively skill-based strategies | `pages/validation.html`, `pages/leaderboard.html` | Computed | Gates G4 (BH-adjusted significance), G8 (deflated Sharpe) reject luck-driven results |
| 13 | Executive summary | `docs/EXECUTIVE_SUMMARY.md`, `pages/executive.html` | Done | one-page summary with numbers and limits |
| 14 | Review the repo line by line, flag irregularities | `pages/flagged.html`, `COORDINATION.md` | Done | 9 open items with severity and handling |
| 15 | Provide links for manual review | `pages/sources.html`, `data/sources.json` | Done | 11 sources, each opened and confirmed 2026-11-01, with what was confirmed |
| 16 | GitHub Pages live site | root `index.html`, `pages/` | Done | published from `main`; deploy run recorded in `COORDINATION.md` |
| 17 | Clean landing page and category subpages | `index.html` + 13 subpages | Done | sidebar navigation, dashboard layout, no JS required |
| 18 | Every table row links to an official source | all published pages | Enforced | `tests/check_site.py` fails the build if a row lacks a source cell |
| 19 | Unconfirmable values left blank and flagged | `pages/flagged.html` | Done | prop ROI, CLV, execution access, prize pool, parlay ladder, point-in-time injury/depth snapshots |
| 20 | No manual input from the user | `.github/workflows/data-pipeline.yml` | Done | fetch → analyse → build → verify → commit, runs unattended |
| 21 | Parallel-session coordination | `COORDINATION.md`, `pages/archive.html` | Done | claim, handoff under the 60-minute rule, sibling artefacts preserved |
| 22 | Pull request and merge without waiting for approval | PR linked in `COORDINATION.md` | Done | summary, sources and irregularities in the PR body |
| 23 | Dedicated, source-linked suggestions queue and decision questions, separating known facts from missing evidence | `pages/suggestions.html`; `scripts/build_site.py` | Done as a review proposal | Six prioritized proposals, seven decision questions, explicit current answers, blockers and acceptance conditions; no unverified estimates |

## Values deliberately left blank

These are the places a less careful build would have produced a number:

| Value | Why it is blank | Where the gap is recorded |
|---|---|---|
| Player-prop ROI | no historical prop prices exist in the committed nflverse community extracts | `pages/flagged.html` |
| Closing-line value | only closing prices are available, no timestamps or opens | `pages/flagged.html` |
| Fixed-odds parlay payout ladder | operator-specific; not confirmed in the rulebook that was read | `pages/strategies.html`, `pages/flagged.html` |
| Injury-based signals | NFL.com has a live report; historical injury snapshots and all-team depth history are absent. A single Colts team-published chart is labeled unofficial | `pages/flagged.html`; `data/flagged.json` FL-12 |
| Prize money | no funded pool exists | `pages/leaderboard.html` |
| Executable access, limits, jurisdiction | nothing verified | Gate G9 fails by design |
