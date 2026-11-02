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
| Closing spread MAE (1999–2026) | 10.25 pts | 7,075 games |
| Closing spread MAE (2023–2026) | 9.70 pts | 924 games |
| Regression slope, closing spread on actual margin | 1.048 | 7,075 |
| Home cover rate | 48.9% (CI 47.7–50.1) | 6,880 decided |
| Over rate | 49.5% (CI 48.4–50.7) | 6,976 decided |
| Moneyline Brier score (Shin-devigged) | 0.2112 vs 0.25 coin flip | 5,158 |
| Pooled ATS win rate | 50.0%, p = 1.00 | 13,760 |

The spread market shows no exploitable tilt, and its moneylines are essentially perfectly calibrated.

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

No prop ROI is published. The official feed contains no historical prop prices, and the NFL's
official distributor is the entity that supplies prop and same-game-parlay pricing to operators. A
computed ROI would require a price archive that does not exist here.

## 7. What would change the conclusion

1. A strategy beating the close out of sample on 1,000+ settled bets with a bootstrap ROI lower bound
   above zero, surviving BH correction across all tests.
2. Verified executable prices with timestamps, enabling closing-line-value measurement.
3. A historical prop price archive, converting prop calibration into a testable strategy.
4. A confirmed official injury-report policy, unblocking injury-based signals.

## 8. Verification status

* 11 sources opened and confirmed on 2026-11-01; each site table row links to one.
* The spread sign convention is proven from the data, not assumed.
* 71 HTML pages, 152 tables, 2,252 links checked; no broken links.
* Nine open items published on the Flagged for Review page, including the missing prop prices,
  closing-line value, execution access, prize funding, parlay ladder, injury policy, model
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
| Independent checks | 49 |
| Agree with the published value | 45 |
| Material disagreements | 0 |
| Observations expected to differ (windows, live pages) | 11 recorded, 0 hidden |
| 2020 regular season vs NFL.com | 32/32 teams match on W-L-T, PF and PA |
| 2026 live standings vs committed extract | 8/32 match — the extract ends 2026-10-29 |
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

**What the verification does not establish.** That a strategy is profitable, that a price is obtainable, or
that the player-level coefficients reproduce exactly from the pruned extract: the published coefficients were
measured on a 2012–2026 download, the committed pruned extract starts in 2015, and the recomputation
reproduces every sign and magnitude to within 0.02 with a smaller n. That gap is published rather than
papered over, and it is the one item that a data refresh (plus committing the pruned extracts from the same
download) would close.
