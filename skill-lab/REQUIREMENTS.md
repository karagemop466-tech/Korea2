# NFL Skill Lab — Full Requirements & Verification Specification

**Verification Date:** `2026-11-02 UTC`  
**Session / Branch:** `arena/2b9898f7-korea2`  
**Scope:** `skill-lab/**`, `.github/workflows/skill-lab.yml`, and the `arena/2b9898f7-korea2` section of `COORDINATION.md`

---

## 1. Functional & Quantitative Requirements

| Req ID | Requirement | Implementation & Artifact | Verification Check |
| --- | --- | --- | --- |
| **REQ-01** | Collect, organize, and reconcile NFL game, team-week, and player-week data against official primary sources | `skill-lab/scripts/common.py`, `repo_audit.py`, `data/official_2026.json` | 2025 REG (`32/32`, 272 games), 2026 REG (`32/32`, 120 games thru Nov 1), and `7/7` player stat logs reconciled against live `NFL.com` |
| **REQ-02** | Originate NFL lines (spreads, totals, fair moneylines) and calibrated player-prop quantiles strictly out-of-sample | `skill-lab/scripts/originate.py`, `data/origination.json`, `pages/origination.html` | `2,247` OOS games (`2018–2026`); live ex-ante grading on 12 Nov 1 Week 8 finals (`10.54` MAE vs `10.58` market); 15 originated 2026 Week 9 lines |
| **REQ-03** | Research pre-kickoff signal-generation hypotheses with multiple-testing correction | `skill-lab/scripts/signals_and_luck.py`, `data/signals.json`, `pages/signals.html` | `10` pre-kickoff signals (`SIG-01..10`) tested on 100% real closing vig; Benjamini-Hochberg FDR (`q <= 0.10`) rejects `10/10` |
| **REQ-04** | Separate repeatable skill from mean-reverting luck across teams and strategies | `skill-lab/scripts/signals_and_luck.py`, `strategies.py`, `data/luck.json`, `pages/luck-skill.html` | Odd/even split-half + `317` YoY pairs (`2015–2025`); Empirical Bayes shrinkage collapses small-sample parlay luck spikes (`+34.88% -> -3.93%`) |
| **REQ-05** | Compute empirical correlations (with Fisher-`z` CIs & latent Gaussian-copula `rho`) for parlays, SGPs, and prop combos | `skill-lab/scripts/correlations.py`, `data/correlations.json`, `pages/correlations.html` | `14` pairs (`COR-01..14`) + `5` multi-leg copula pricing curves; proves ex-post WR1 selection inflates `r` from `+0.3723` to `+0.6135` |
| **REQ-06** | Frame Single Bets, Cross-Game Parlays, SGPs, and Player Prop Combos as a leaderboard competition with rewards | `skill-lab/scripts/strategies.py`, `data/leaderboard.json`, `pages/leaderboard.html`, `pages/strategies.html` | `16` strategies across 5 tracks competing for a `10,000`-pt paper allocation pool (`0` qualified, `0` pts awarded; cash prize cells blank) |
| **REQ-07** | Enforce strict validation gates on every strategy | `skill-lab/scripts/strategies.py`, `data/strategies.json`, `pages/gates.html` | `10` gates (`G1..G10`); `G1` auto-disqualifies `85.14%` lookahead leak (`STR-16`); `G10` holds unpriced SGP/prop combos |
| **REQ-08** | Publish an Executive Summary covering key details and findings | `skill-lab/EXECUTIVE_SUMMARY.md`, `pages/summary.html` | Reconciled word-for-word against generated JSON artifacts |
| **REQ-09** | Review the repository line-by-line against official verified sources; leave unverified values blank and flag irregularities | `skill-lab/REPO_REVIEW.md`, `data/repo_review.json`, `data/flagged.json`, `pages/repo-review.html`, `pages/flagged.html` | `14` audited repo subsystems + `12` flagged/unverified items; `77` rendered HTML blank cells verified `""` by `verify_all.py` |
| **REQ-10** | Publish a clean static GitHub Pages dashboard where every table row links to an official primary source | `skill-lab/index.html`, `skill-lab/pages/*.html`, `skill-lab/assets/style.css` | `12` HTML pages, `335` `<tbody><tr>` rows (`100%` linked to `32` verified primary sources; `0` source flags under `audit/check_site.py`) |

---

## 2. Zero-Hallucination & Blank-Value Policy

1. **No Inferred Prices:** The `1,902` pre-2018 games in `data/derived/games.csv.gz` lacking `home_spread_odds`/`away_spread_odds` are never imputed at `-110`; all priced backtests use `2018–2026` rows with 100% recorded closing odds.
2. **No Fabricated SGP or Prop Vig:** Because official `NFL.com` does not archive sportsbook prop lines or proprietary SGP correlation haircuts (`SL-SRC-16`, `SL-SRC-20`), `STR-10..STR-14` report verified box-score joint hit rates and Gaussian-copula calibration while leaving ROI cells strictly empty (`""`).
3. **No Simulated Cash Treasury:** Funded cash prize cells across all reward tiers and leaderboard rows are strictly empty (`""`).
4. **Automated Enforcement:** `skill-lab/scripts/verify_all.py` fails with exit code `1` if any `flagged.json` value is non-empty, if any `<td class="blank-cell">` contains text, if any `<tbody><tr>` lacks an official `https://` link, or if any JSON contains `NaN`/`Infinity`.
