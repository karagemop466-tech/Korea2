# Executive summary — Line Lab (build of 2026-11-01)

Snapshot of the committed pipeline output. The live site is regenerated from
`data/derived/*.json` on every run, so the site is authoritative if this file drifts.

## Decision

**Allocate to nothing.** Seven candidate strategies were defined before testing and settled at the
closing line on 2023–2026 games. None passed the ten validation gates. The highest-ranked returned
−1.9% per unit staked, roughly the cost of the vig.

A gate system that approves nothing on its first pass is working. The rest of this page is the
evidence, and the places where the evidence stops.

## 1. The closing market is the benchmark, and it is strong

| Measure | Value | n |
|---|---|---|
| Closing spread MAE (1999–2026) | 10.25 pts | 7,087 games |
| Closing spread MAE (2023–2026) | 9.71 pts | 936 games |
| Regression slope, closing spread on actual margin | 1.049 | 7,087 |
| Home cover rate (one observation per game) | 48.91% (CI 47.73–50.09), p = 0.073 | 6,892 decided |
| Over rate | 49.53% (CI 48.36–50.70) | 6,988 decided |
| Moneyline Brier score (Shin-devigged) | 0.2111 vs 0.25 coin flip | 5,170 |
| Pooled ATS rate (arithmetic identity — not evidence) | exactly 50.0% by construction | 13,784 team-game rows |

*(Table refreshed 2026-11-13 from the committed extract by integration pass IR-2; every value is
reproduced by `verification/recompute.py` — the 2026-11-01 snapshot's counts above were stale.
The "Pooled ATS" row is an identity: each game is pooled twice, so the rate is 0.5 for any dataset
— flag FL-DH-01. The honest tilt test is the home-cover row: no significant tilt is detected, and a
small one cannot be ruled out at n = 6,892.)*

## 2. Our originated lines are worse, and the test is decisive

Walk-forward, no leakage, hyper-parameters frozen on 2021–2022:

| Forecaster | Spread MAE | Total MAE |
|---|---|---|
| Ratings model | 10.38 pts | 10.71 pts |
| Closing line | 9.70 pts | 10.16 pts |
| Blend (0.15 model) | 9.73 pts | 10.18 pts |

Accuracy alone is not the point. The question is whether the model knows anything the close does
not. In `result = a + b·closing + c·model` (HC1 errors):

* spreads: **c = −0.02** (p = 0.85)
* totals: **c = −0.16** (p = 0.22)

And when model and market disagree by 5+ points, the model's MAE is 12.43 against the market's
10.33 — the disagreement is model error, not edge.

## 3. Correlation is the part that is genuinely useful

Measured on 7,542 team-games and 248,972 player-games (2012–2026), all with Fisher-z intervals:

| Pair | r | n |
|---|---|---|
| QB passing yards ↔ WR1 receiving yards | +0.561 | 7,537 |
| QB passing yards ↔ WR2 receiving yards | +0.505 | 7,537 |
| QB passing yards ↔ own team points | +0.400 | 7,537 |
| RB1 rushing yards ↔ own team points | +0.300 | 7,542 |
| RB1 rushing yards ↔ QB passing yards | −0.127 | 7,537 |
| WR1 ↔ WR2 receiving yards | +0.119 | 7,542 |

Pricing consequence, using each leg at its own median (a 50/50 proposition):

| Parlay | Independent product | Empirical joint | Fair odds independent → actual |
|---|---|---|---|
| 2 legs (QB + WR1) | 24.7% | 34.0% | 4.05 → 2.94 |
| 4 legs (QB, WR1, RB1, team points) | 5.7% | 11.1% | 17.57 → 8.99 |

Independent-leg multiplication understates the joint probability by ~2× on the 4-leg case. The
Gaussian-copula price with the measured correlation matrix gives 12.3%, close to the empirical 11.1%,
so the matrix is sufficient to price the combination.

Placebo: shuffling the same legs across unrelated games returns r = −0.013.

## 4. Luck, removed

| Measure | Value |
|---|---|
| Variance in season win% explained by point differential | 82.9% |
| Explained by Pythagorean expectation (exponent 2.37) | 82.5% |
| Unexplained share (luck budget) | 17.5% |
| SD of luck in wins | 1.33 |
| Year-over-year correlation of luck | 0.019 (n = 827) |
| Year-over-year correlation of one-score win rate | 0.087 (p = 0.011) |

Past luck does not repeat, so win-loss record cannot be a feature. The one-score record carries a
small, marginally significant carry-over, which is reported rather than used.

## 5. Strategies and why they failed

| Strategy | Family | Bets | ROI | Gates |
|---|---|---|---|---|
| Divisional home underdog | single | 133 | −1.9% | 5/10 |
| Bye-week team (13+ days rest) | single | 81 | −8.2% | 5/10 |
| Wind ≥ 15 mph → under | single (total) | 45 | +1.5% | 4/10 |
| Rest advantage ≥ 3 days | single | 195 | −0.2% | 4/10 |
| Model spread edge ≥ 2 / ≥ 3 | single | 550 / 390 | −5.1% / −8.2% | 4/10 |
| Model total edge ≥ 3 | single (total) | 357 | −3.8% | 4/10 |
| Controls (all home / all under) | control | 899 / 919 | −5.8% / −6.0% | 4/10 |

Common failures: G2 (underpowered — detecting a 52.4% edge at 80% power needs ~6,800 bets), G4
(not significant after Benjamini–Hochberg), G5 (ROI lower bound below zero), G8 (fails
deflated-Sharpe), G9 (no verified executable price).

## 6. Player props: measured, not priceable

Prop forecasts beat a season-to-date mean by 0.0–0.9% MAE depending on the stat, and the originated
lines are calibrated within a few points of 50% — except passing yards, where the over rate is 54.5%
because the pre-2023 correction is stale. That drift is published, not tuned away.

No prop ROI is published. The committed nflverse game/player-stat extracts contain no historical prop prices, and the NFL's
official distributor is the entity that supplies prop and same-game-parlay pricing to operators. A
computed ROI would require a price archive that does not exist here.

## 7. What would change the conclusion

1. A strategy beating the close out of sample on 1,000+ settled bets with a bootstrap ROI lower bound
   above zero, surviving BH correction across all tests.
2. Verified executable prices with timestamps, enabling closing-line-value measurement.
3. A historical prop price archive, converting prop calibration into a testable strategy.
4. Historical point-in-time injury / active-inactive snapshots and a verified source for exact depth order; the official live report exists, but the project does not ingest it as an as-of-game feature.

## 8. Verification status

* 11 sources opened and confirmed on 2026-11-01; each site table row links to one.
* The spread sign convention is proven from the data, not assumed.
* 71 HTML pages, 152 tables, 2,252 links checked; no broken links.
* Nine open items published on the Flagged for Review page, including the missing prop prices,
  closing-line value, execution access, prize funding, parlay ladder, injury/depth snapshots, model
  underperformance and the 2026 home-field anomaly.

## 9. Independent verification, 2026-11-02

Added by the integration/verification session `arena/652b0095-korea2`. The full per-row record is on the
site's [Verification page](https://karagemop466-tech.github.io/Korea2/pages/verification.html) and in
`verification/recompute.json`.

**What was done.** Every headline number was recomputed from the committed extracts
(`data/derived/games.csv.gz`, `player_week.csv.gz`) by `verification/recompute.py`, which imports nothing
from `scripts/` or `pipeline/`. A completed season was reconciled team by team against NFL.com, and eight
official pages were re-read on 2026-11-02.

| Result | Value |
|---|---|
| Independent checks | 53 |
| Agree with the published value | 52 |
| Material disagreements | 0 |
| Observations (informational rows, not equality tests) | 11, all consistent |
| 2020 regular season vs NFL.com | 32/32 teams match on W-L-T, PF and PA |
| 2026 live standings vs committed extract | 32/32 match, on data through 2026-11-01 |
| Upstream release assets re-checked | 28 of 31 byte-size identical; the three current-season files moved upstream on 2026-11-02 |

**Defects found and fixed in this pass**

1. A validation-page cell rendered `n/a` because the generator read `..._ml_dog` while the data field is
   `..._ml_underdog`. The measured value (−4.658) now renders.
2. `data/derived/luck.json` contained `-Infinity` for the k = 1 multiple-testing row — invalid JSON and
   displayed as "-inf". The expected maximum of one draw is 0; generator and data corrected.
3. Two correlation notes described the opposite sign to the number they sat next to (r = −0.031 called
   "positive"; r = +0.119 called "the one common negative pair"). Notes rewritten; coefficients unchanged.
4. A model-spec string said ridge λ = 8 while the code applies λ = 4.0, the value chosen on validation.
   Corrected.
5. A second generator (`scripts/analysis/build_site.py`) writes the same `index.html` / `pages/*` paths,
   which left a stale, unreachable `pages/verification.html` on the live site. The integrated generator now
   owns those paths and publishes a real Verification page in the navigation; `tests/check_derived.py`
   fails the build on an orphan page, on non-strict JSON, or on any verification disagreement.

**The reproducibility gap, and its fix.** On the first pass the published player-level coefficients could not be
reproduced from a checkout: the analysis read a 2012–2026 download while the committed pruned extract started in
2015 (same signs and magnitudes within 0.02, smaller n). The refresh workflow then rewrote every figure, which
widened the gap to 21 disagreements on 48 comparable checks. `scripts/export_extracts.py` now rebuilds the
committed extracts from the same parquet files the analysis reads, the pipeline runs it on every refresh, and
the verifier is back to 0 disagreements with every player-level sample size matching exactly.

**What the verification does not establish.** That a strategy is profitable, that a price is obtainable at any
size, or that results will persist. Reproducibility is not validation.


## 10. Integration review update — 2026-11-12

- Historical game and player-stat inputs are from the community-maintained nflverse archive, not an NFL-published feed. The source register now labels this correctly; NFL.com reconciliation is limited to the exact seasons/fields documented on Verification, and the full historic archive is flagged as not independently NFL-confirmed.
- NFL.com has a live weekly injury report and a policy explainer; the former missing legacy operations URL is a separate broken link. The repository does not capture historical pregame injury/active-inactive snapshots or league-wide depth charts. The reviewed NFL.com roster page lacks depth ordering; a Colts team-published chart exists but is explicitly unofficial and covers only one team. No replacement level or 2nd/3rd/4th-string label is ingested into the model.
- The committed data snapshot ends 2026-11-01. The official NFL Week 10 schedule was read on 2026-11-12; old Week 9/next-slate projections are stale and must not be presented as current.
- The new [Suggestions & decisions page](https://karagemop466-tech.github.io/Korea2/pages/suggestions.html) provides seven proposals and explicit decision questions. All remain pending; current recommendation is research-only, with no approved strategies or funded reward.

## 11. Integration review update — 2026-11-13 (IR-2, FL-DH-01 remediation)

- The pooled "ATS coin-flip" statistic (n = 13,784 team-game rows, rate exactly 50.0%, p = 1.0) was
  published as evidence that "the spread market shows no exploitable tilt". It is an arithmetic
  identity — each game is pooled as +x and −x, so exactly one of each pair covers — and can never
  fail for any dataset (flag FL-DH-01, decision-hub audit).
- **Remediated in this pass.** The pooled figure is now labelled `is_identity` in
  `data/derived/luck.json` and rendered as "arithmetic identity — not evidence" everywhere it
  appears. The site's headline ATS statistic is the one-observation-per-game test from
  `market.json → ats_home_cover`: **48.91% home covers (3,371 of 6,892 decided games), 95% CI
  47.73–50.09, two-sided exact binomial p = 0.0727**. The conclusion is now "no significant tilt
  detected, and none ruled out", not "no tilt exists".
- The independent record grew to **53 checks (52 agree, 0 material disagreements)**: the four new
  `market.ats_home_*` checks recompute the tilt test from the committed extract by a separate
  implementation (`verification/recompute.py` imports nothing from `scripts/`).
- Reproducibility proof for this change: `scripts/analyze_luck.py` was re-run against the committed
  extract `data/derived/games.csv.gz` and reproduced `data/derived/luck.json` byte-for-byte apart
  from the intended relabel (2 insertions, 1 deletion in the JSON diff).
- No strategy is approved, no reward is funded, and no operator/licence/limit is verified. The
  remediation changes how a null result is presented; it does not change the null result.
