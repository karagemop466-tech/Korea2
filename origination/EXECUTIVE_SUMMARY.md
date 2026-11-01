# Executive summary

**Project:** originate our own NFL lines, turn them into betting strategies, and keep only the strategies that
survive validation. **Scope executed:** 7,548 games (1999-2026, 7,384 played), 45,439 player-games (2009-2017),
31 strategies, 38,708 held-out tickets, 10 validation gates, and a published register of everything that could not
be verified. **Bottom line: no strategy cleared every gate. The bookmaker's margin was not beaten, and the report
says so with the arithmetic attached.**

---

## 1. What was built

1. **A market-free line-origination engine.** A shrunk attack/defence points model, refit for every week using
   only games played before that week's first kickoff, produces a spread, a total and a moneyline for every game
   from 1999 to 2026. Ridge penalty selected on 1999-2014 and then frozen; 2015-2026 is held out and never used
   for tuning.
2. **A strategy factory.** 31 rules across six families: model-versus-market (spread, total, moneyline),
   situational (weather, rest, bye weeks, divisional games, domes), parlays (2-leg, 3-leg, same-game),
   player props (five markets), and three controls — two no-information benchmarks plus one deliberate
   lookahead leak used to prove the integrity gate fires.
3. **A gate set that can say no.** Ten gates: lookahead audit, sample size, out-of-sample-only, bootstrap
   confidence interval, permutation test against the market's own de-vigged prices, Benjamini-Hochberg
   correction across all 31 strategies, deflated Sharpe ratio, calibration versus the market, season
   stability, and split-half consistency.
4. **A correlation engine.** Market correlations, strategy-return correlations and player-prop correlations,
   each with a bootstrap confidence interval and a sample size.
5. **A verified, reproducible data layer.** 13 files from four upstream repositories, each pinned to a commit
   SHA and hashed with SHA-256, plus 16 structural checks and three official NFL.com spot checks.

## 2. Headline findings

| # | Finding | Number | What it means |
|---|---|---|---|
| 1 | Our line is worse than the closing market | spread MAE 10.15 pts vs 9.79; total MAE 10.81 vs 10.44 | Expected, and it sets the handicap every model strategy starts from. |
| 2 | Our disagreements with the close carry no information | slope of (actual − close) on (ours − close) = +0.010, 95% CI −0.125 to +0.150, n = 3,136 | Where the engine differs from the market, it is noise. This single test predicts the failure of every model-versus-market strategy below. |
| 3 | The vig is the dominant force | control "back every home team" returns −5.40% on 3,054 tickets; the de-vigged baseline at these prices is −3.07% | Accounting is calibrated: a rule with no information lands on the margin. |
| 4 | Nothing cleared the gates | 0 gold, 0 silver, 0 bronze, 23 rejected, 8 needs-review | The competition paid 0 reward points. |
| 5 | The best raw result is a small sample | `SIT_WINDY_UNDER` +9.22% on 225 tickets, permutation p = 0.029, but BH q = 0.32 and a 95% CI of −3.6% to +21.7% | Consistent with luck at 225 tickets; published as needs-review, not as a winner. |
| 6 | The study is underpowered for small edges | per-ticket SD 1.10 units; 10,598 tickets needed to detect a 3% edge at 80% power, 3,815 for 5%; the largest strategy has 3,107 | Even a real 3% edge would not be provable with this much data. Sample-size gate failures are honest, not arbitrary. |
| 7 | Spread and total are effectively independent | cover/over r = +0.0159 (95% CI −0.006 to +0.039), n = 7,080 | Same-game spread+total parlays can be priced as a product; correlation is not the leak there. |
| 8 | Player props are where correlation bites | QB passing yards vs his leading receiver r = +0.670; ignoring it under-states the joint probability by 11.8% | Two-prop combos on the same passing game need correlation-adjusted pricing. |
| 9 | Prop models show real but modest skill against a naive line | passing yards Brier skill +8.0% (CI +6.0% to +10.2%); receptions +3.8%; receiving yards +0.5% (CI includes zero) | Forecasting is demonstrable. Beating a book is not, because no prop prices exist here. |
| 10 | The "independent" strategies are not independent | mean absolute pairwise weekly-P&L correlation 0.237; `ML_OWN_3` vs `ML_OWN_DOG` = 0.963 | The leaderboard is not 31 independent attempts, which is why the deflated Sharpe uses the full trial count. |

## 3. The competition and its rewards

The rubric pays for evidence, not for returns: **gold** (all gates pass) 10 points, **silver** (one gate missed)
5, **bronze** (positive ROI interval, other gates missed) 2, needs-review and rejected 0. Ranking is by deflated
Sharpe among strategies that have a rank at all.

**Payout this run: 0 points.** The closest entry, `SIT_WINDY_UNDER` (under in games with wind of 15 mph or more),
passes the permutation gate individually (p = 0.029) but fails six others, including the sample-size gate and the
multiple-testing correction (q = 0.32). If a later run wants a genuine gold, it needs either far more tickets or a
signal that survives at a materially larger effect size — and the power analysis above says exactly how many
tickets that means.

## 4. What is verified, and what is not

**Verified.** Every arithmetic identity in the dataset (result = home − away, total = home + away, across 7,384
games, zero violations). Unique identifiers. Complete spread and total coverage. Eight player-layer checks
(no duplicate player-games once keyed on the upstream id, counting stats non-negative, receptions never exceed
targets, completions never exceed attempts). A recomputation of 842 pre-game Elo values from prior games only,
with zero mismatches. Three games checked by hand against NFL.com, all matching.

**Not verified, and therefore blank.** Every player-prop ROI (no prop price feed exists), every player-prop value
for 2018-2026 (the player data stops at 2017), opening-line value outside 2021 (544 games only), official
verification of historical closing lines (no official line feed exists at all), and official verification of the
bulk of historical results (3 of 7,384 games checked). Six items are listed on the Flagged page with the source
that would settle each one.

**Two irregularities worth your attention.** (a) The two upstream odds files — both labelled "closing" — agree on
only 67.3% of spreads and 61.7% of totals across the 3,368 games they share, with differences up to 5.5 points.
They are snapshots of different books or different times. (b) The canonical `nflverse-data` release assets are
unreachable from this environment, so the historical bulk rests on the same feeds as committed inside
`nflverse/nfldata` and `ryurko/nflscrapR-data`, pinned and hashed.

## 5. What would change the answer

1. **A licensed prop-price feed.** Prop models already beat a naive line on passing yards, receptions and anytime
   touchdown. Pricing them is the only way to know whether that skill survives a bookmaker's margin.
2. **Player data for 2018-2026.** Current player form is the binding constraint on any live prop product.
3. **More seasons of priced tickets.** To prove a 3% edge you need roughly 10,600 tickets, which is about 27
   NFL seasons of betting one rule per game. Anything less than that is a hypothesis, not a result.
4. **Better inputs than public box scores.** Injuries, depth charts, snap counts, pressure rates and travel are
   not in any dataset reachable here. A model built only on scores and weather should not be expected to beat a
   market that prices all of it.

## 6. Where to look

- Landing page and dashboard: the repository root `index.html` (live on GitHub Pages).
- Strategy leaderboard with every gate: `pages/strategies.html`.
- Our own lines and this week's board: `pages/origination.html`.
- Correlation values: `pages/correlation.html`.
- Verification and the unverified register: `pages/verification.html`.
- Flagged for review: `pages/flagged.html`.
- Requirements, line by line: `REQUIREMENTS.md` and `pages/requirements.html`.
- Reproduce: `python pipeline/fetch_data.py`, `python pipeline/fetch_data.py --check`, `python pipeline/run_all.py`.

## 7. Honest assessment

The framework is sound and the arithmetic is checked: settlement, pricing, pushes, vig and parlay chaining all
reproduce a known baseline when applied to a rule with no information. The strategies are the weak part, and not
because they were badly chosen — they cover the families that the public literature says are worth testing, and
they were all rejected by tests that were fixed before the results were seen. The most useful output of this
project is not a betting system. It is a reusable, auditable machine for killing ideas quickly, plus the two or
three places (prop pricing, correlated combos) where a real edge could still hide.
