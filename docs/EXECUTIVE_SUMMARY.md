# Executive summary — Line Lab (build of 2026-11-01, revised 2026-11-13)

Snapshot of the committed pipeline output. The live site is regenerated from
`data/derived/*.json` on every run, so the site is authoritative if this file drifts.

> **Revision 2026-11-13 (final integration session `arena/dd794652-korea2`).** Every figure in
> sections 1–9 was re-read from the committed `data/derived/*.json` and corrected where it had
> drifted; the corrections are listed in section 11 and in `docs/INTEGRATION_REVIEW.md`. No
> measured value was changed — only stale copies of it, one mislabelled claim, and the
> navigation, landing page and whole-site review queue.

## Decision

**Allocate to nothing.** Seven candidate strategies were defined before testing and settled at the
closing line on 2023–2026 games, with two controls. None passed the ten validation gates. The
highest-ranked candidate returned −1.2% per unit staked on 137 bets, roughly the cost of the vig;
the best raw ROI in the table (+1.5%) rests on 46 bets and fails the sample-size gate.

A gate system that approves nothing on its first pass is working. The rest of this page is the
evidence, and the places where the evidence stops.

## 1. The closing market is the benchmark, and it is strong

| Measure | Value | n |
|---|---|---|
| Closing spread MAE (1999–2026) | 10.25 pts | 7,087 games |
| Closing spread MAE (2023–2026) | 9.71 pts | 936 games |
| Regression slope, closing spread on actual margin | 1.049 | 7,087 |
| Home cover rate (one observation per game) | 48.91% (CI 47.73–50.09), p = 0.073 | 6,892 decided |
| Over rate | 49.53% (CI 48.36–50.70), p = 0.437 | 6,988 decided |
| Moneyline Brier score (Shin-devigged) | 0.2111 vs 0.25 coin flip | 5,170 |
| Pooled team-game ATS rate (an identity, not a test) | 50.0%, p = 1.00 | 13,784 rows |

The spread market shows no exploitable tilt — home teams covered 48.91% of 6,892 decided games
(95% CI 47.73–50.09%, p = 0.073 against 50%) — and its moneylines are essentially perfectly
calibrated. The pooled 50.0% row above is **not** a second finding: it counts each game once per
side, so 50% is its arithmetic identity, not a measurement. It was presented as evidence until the
2026-11-13 integration pass corrected it (see section 11).

## 2. Our originated lines are worse, and the test is decisive

Walk-forward, no leakage, hyper-parameters frozen on 2021–2022:

| Forecaster | Spread MAE | Total MAE |
|---|---|---|
| Ratings model | 10.39 pts | 10.74 pts |
| Closing line | 9.71 pts | 10.20 pts |
| Blend (0.15 model) | 9.74 pts | 10.21 pts |

Accuracy alone is not the point. The question is whether the model knows anything the close does
not. In `result = a + b·closing + c·model` (HC1 errors):

* spreads: **c = −0.019** (p = 0.881)
* totals: **c = −0.149** (p = 0.247)

And when model and market disagree by 5+ points, the model's MAE is 12.39 against the market's
10.31 — the disagreement is model error, not edge.

## 3. Correlation is the part that is genuinely useful

Measured on 7,566 team-games and 249,814 player-games (2012–2026), all with Fisher-z intervals:

| Pair | r | n |
|---|---|---|
| QB passing yards ↔ WR1 receiving yards | +0.562 | 7,560 |
| QB passing yards ↔ WR2 receiving yards | +0.506 | 7,560 |
| QB passing yards ↔ own team points | +0.400 | 7,560 |
| RB1 rushing yards ↔ own team points | +0.300 | 7,566 |
| RB1 rushing yards ↔ QB passing yards | −0.127 | 7,560 |
| WR1 ↔ WR2 receiving yards | +0.120 | 7,566 |

Pricing consequence, using each leg at its own median (a 50/50 proposition):

| Parlay | Independent product | Empirical joint | Fair odds independent → actual |
|---|---|---|---|
| 2 legs (QB + WR1) | 24.66% | 34.02% | 4.06 → 2.94 |
| 4 legs (QB, WR1, RB1, team points) | 5.69% | 11.14% | 17.58 → 8.98 |

Independent-leg multiplication understates the joint probability by ~2× on the 4-leg case. The
Gaussian-copula price with the measured correlation matrix gives 12.3%, close to the empirical 11.1%,
so the matrix is sufficient to price the combination.

Placebo: shuffling the same legs across unrelated games returns r = −0.030 (n = 7,560).

## 4. Luck, removed

| Measure | Value |
|---|---|
| Variance in season win% explained by point differential | 82.1% |
| Explained by Pythagorean expectation (exponent 2.37) | 81.9% |
| Unexplained share (luck budget) | 18.1% |
| SD of luck in wins | 1.32 |
| Year-over-year correlation of luck | 0.024 (n = 842) |
| Year-over-year correlation of one-score win rate | 0.082 (p = 0.017) |

Past luck does not repeat, so win-loss record cannot be a feature. The one-score record carries a
small, marginally significant carry-over, which is reported rather than used.

## 5. Strategies and why they failed

| Strategy | Family | Bets | ROI | Gates |
|---|---|---|---|---|
| Divisional home underdog (S6) | single | 137 | −1.2% | 5/10 |
| Bye-week team, 13+ days rest (S5) | single | 86 | −5.9% | 5/10 |
| Wind ≥ 15 mph → under (S7) | single (total) | 46 | +1.5% | 4/10 |
| Rest advantage ≥ 3 days (S4) | single | 204 | +0.1% | 4/10 |
| Model spread edge ≥ 2 / ≥ 3 (S1 / S2) | single | 572 / 409 | −5.3% / −8.2% | 4/10 |
| Model total edge ≥ 3 (S3) | single (total) | 370 | −3.5% | 4/10 |
| Controls: all home / all under (C1 / C2) | control | 936 / 936 | −5.2% / −6.0% | 4/10 |

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
* 178 HTML pages, 430 tables, 10,574 links checked; no broken links (2026-11-13).
* Open items published on the Flagged for Review page, including the missing prop prices,
  closing-line value, execution access, prize funding, parlay ladder, injury/depth snapshots, model
  underperformance and the 2026 home-field anomaly. The page also carries the whole-site review
  queue: the open-item count of every workspace that keeps its own register.

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
| Independent checks | 49 |
| Strict equality checks that agree | 45 |
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

---

## 11. Final integration review — 2026-11-13 (session `arena/dd794652-korea2`)

This is the integration pass: the repository was reviewed line by line, the published numbers were
recomputed by a second independent implementation, the official sources were re-read live, and the
shared index, navigation and review queue were rebuilt. Full detail:
[`docs/INTEGRATION_REVIEW.md`](INTEGRATION_REVIEW.md).

### What changed in the published numbers

Nothing was edited by hand. One published *claim* was corrected, because it attached an
interpretation to a number that was correct but was not evidence:

| Item | Before | After |
|---|---|---|
| Overview card and Removing luck page | "ATS coin-flip test — 50.0%, p = 1.0 against 50%" | "Home spread cover rate — 48.91%, 95% CI 47.73–50.09%, p = 0.073, n = 6,892 decided games", with the pooled 50% row relabelled as an arithmetic identity |

The underlying figures are unchanged. The pooled figure counts each game once per side, so 50% is
its arithmetic identity; the one-observation-per-game test was already in the committed data.

### What the independent recomputation found

`verification/integration_recompute.py` re-derives the published numbers from the committed extracts
with code that imports nothing from the pipeline:

| Result | Count |
|---|---|
| Checks | 45 |
| Match the published value exactly | 41 |
| Documented differences (explained on the Verification page) | 4 |
| Mismatches | 0 |

The four documented differences are all the same root cause: the committed player-week extract
covers 2015–2026 while the published correlation scope says 2012–2026, so the sample sizes differ
(7,566 published team-games vs 5,782 recomputed; 7,560 vs 5,776 for the QB↔WR1 pair) while the
coefficients reproduce — QB passing yards vs WR1 receiving yards recomputes to r = 0.5618 against
the published 0.5616.

### Live re-check against official sources (2026-11-13)

| Check | Result |
|---|---|
| NFL.com injury report | Week 10 of the 2026 season, Thursday 2026-11-12 through Sunday 2026-11-15 |
| NFL.com Week 10 schedule | Commanders 24, Giants 21 final on Thursday 2026-11-12; the rest of the slate is Sunday 2026-11-15 |
| NFL.com 2026 division standings | 137 regular-season games played to date |
| Committed extract | 120 regular-season games, last gameday 2026-11-01 |
| Measured staleness | **17 games behind the live page** (2 teams 2 games behind, 28 teams 1, 2 teams level) |
| 2020 completed season | still reconciles 32/32 against NFL.com |

### What did not change

No strategy passed. The reward tiers are still a proposal with no funded pool, no price feed, no
verified execution access, no historical prop prices and no timestamped lines exist. The
injury/depth feature is still blocked on a point-in-time snapshot and an official depth order. The
research snapshot is still not current to the live slate, and the site says so on every page.
