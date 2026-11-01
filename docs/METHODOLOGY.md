# Methodology

Everything here is implemented in `scripts/` and reproducible from `data/derived/manifest.json`.

## 1. Data

| Item | Source | Coverage | Notes |
|---|---|---|---|
| Game results, closing spread/total, moneylines, rest, roof, wind | nflverse `schedules` release (`games.parquet`) | 7,548 games, 1999–2026 | nflverse redistributes the NFL's official feed; the lines are third-party |
| Player box scores by week | nflverse `stats_player` release | 259,678 player-weeks, 2012–2026 | includes the in-progress 2026 season through week 8 |
| Team box scores by week | nflverse `stats_team` release | 2012–2026 | EPA and efficiency columns available but not yet used |

Each file's size and SHA-256 are recorded in `data/derived/manifest.json`. `scripts/profile.py`
records column lists, per-season row counts and odds coverage so no downstream script assumes a
column that is not there.

### Sign convention — proven, not assumed

`spread_line` is the **home team's expected margin** (positive = home favoured by *n*). This was
proven three ways in `scripts/diag_signs.py`:

1. Treating it as an expected margin gives a home cover rate of **48.9%** over 6,880 decided games;
   treating it as a home handicap gives **60.0%**. A balanced two-way book produces the first.
2. Games where the home team is the moneyline favourite average **+5.67** on this field; home
   underdogs average **−4.66**.
3. `result` is exactly `home_score − away_score` in every one of 7,384 played games (max difference
   0.000), and correlates +0.43 with the field.

Getting this wrong silently inverts every against-the-spread result, so it is tested in CI rather
than trusted.

## 2. Line origination model

Two equations per game, fitted jointly by weighted least squares:

```
home_score = mu + off_home − def_away + hfa
away_score = mu + off_away − def_home
```

* Observations are weighted `0.5 ** (age_days / half_life)`.
* `off` and `def` are ridge-shrunk toward the league average (penalty on team ratings only).
* `hfa` is shrunk toward the previous ten seasons' mean home margin with 60 pseudo-observations.
  This matters: in 2026 the observed home margin is −0.43 points, and an unshrunk estimate collapsed
  home advantage to 0.2 points, which would have pushed every originated line toward the road team.
* Hyper-parameters (half-life, lambda) are chosen on **2021–2022 only** and frozen for 2023+.
* Predictions are walk-forward: for each week, the model is fitted only on games played strictly
  before that week's first kickoff.

Derived outputs: predicted margin → spread; predicted total → total; `P(home win) = Φ(margin / σ)`
with σ fitted on out-of-sample residuals (13.35 points), and fair moneylines converted from that
probability.

**Grading, not marketing:** out-of-sample MAE is 10.38 points against 9.70 for the closing line, and
in the regression `result = a + b·closing + c·model` the model coefficient is −0.02 (p = 0.85). A
model that adds nothing is reported as adding nothing.

## 3. Player-prop origination

For each qualified player (season usage above a threshold), the forecast is an exponentially
weighted mean (half-life 4 games) of that player's **prior** games only. Performance stats are
right-skewed, so the line is placed at the forecast plus the median residual, estimated on
pre-2023 games. Accuracy is compared with a season-to-date mean baseline, and calibration is
reported as the empirical over rate at the originated line.

No prop ROI is published: the feed carries no historical prop prices. See the Flagged page.

## 4. Correlation and parlay pricing

Correlations are Pearson r on same-game quantities, with Fisher-z 95% intervals, computed per
team-game (both sides of each game included). A placebo test shuffles the same legs across unrelated
games and returns r ≈ −0.01, which validates the method.

Joint probabilities are computed three ways for a 4-leg same-team parlay:

1. **Independent product** — what naive multiplication (and independent-leg pricing) implies.
2. **Empirical joint** — the observed frequency of all four legs exceeding their own medians.
3. **Gaussian copula** — multivariate-normal CDF with the measured correlation matrix and the same
   marginals.

The copula lands close to the empirical joint, which means the correlation matrix is enough to price
the combination.

## 5. Settlement and staking

| Rule | Implementation | Source |
|---|---|---|
| Spread tie after handicap | push, stake returned, excluded from denominator | operator rulebook |
| Total exactly equal to line | push, stake returned | operator rulebook |
| Prices | the quoted price for that game in the feed, else −110 | feed |
| Profit | per 1.00 unit staked | — |

## 6. Statistics

| Purpose | Method | Why |
|---|---|---|
| Win-rate CI | Wilson score interval | correct near 50% and small n |
| Win-rate test | exact two-sided binomial | no normal approximation at small n |
| ROI CI | percentile bootstrap, 10,000 resamples, fixed seed | profit distributions are skewed and heavy-tailed |
| Multiple testing | Benjamini–Hochberg, q = 0.10 across all strategies | the best of many tests looks good by chance |
| Multiple-testing bar | deflated Sharpe (Bailey–López de Prado form) | converts "best of k tries" into a threshold |
| Sample size | normal-approximation power calculation | shows why "unknown" is the honest verdict |
| Persistence | year-over-year correlation with CI | tests whether a deviation is skill or noise |

## 7. Validation gates

G1 point-in-time integrity · G2 sample size (≥1,000 settled bets or the power minimum) · G3
out-of-sample · G4 significance after multiple testing (p < 0.01 and BH q ≤ 0.10) · G5 bootstrap ROI
lower bound > 0 · G6 stability across seasons · G7 closing-line benchmark · G8 deflated-Sharpe p <
0.05 · G9 executable (price, limit, jurisdiction verified) · G10 reproducible.

A gate that cannot be evidenced is **failed**. G9 is currently unevidenced, so nothing can be
approved until verified execution data exists — which is the correct conservative default.

## 8. Known limitations

* Closing lines only; no opening lines or timestamps, so closing-line value cannot be measured. Every
  ROI here is therefore a conservative, close-to-close number.
* No injury information, no tracking data, no opponent-adjusted efficiency in the model.
* Prop calibration drifts in passing yards (54.5% over rate at the line) because the correction is
  estimated on pre-2023 games; published rather than tuned away.
* Team ratings are shrunk, so extreme disagreements with the market are dampened; this is deliberate,
  and the disagreement table shows the model does worse the further it strays.
