# Decision Desk - executive summary

Generated 2026-11-12T13:13:53Z by `site/scripts/build_site.py` from `site/data/*.json`.
Data as of 2026-11-01. Session `arena/90e4fdbe-korea2`.

## Where the project stands

* 19 independent checks of the numbers the live dashboard publishes: 16 agree, 2 disagree, 0 unverified.
* 23 candidate signals tested against ten validation gates; 0 qualified.
* 12 suggestions awaiting a reviewer's decision; 17 open questions across four groups.
* 108 players transcribed from the official NFL injury report for five 2026 Week 10 games.

## What survived verification

| Number | Published | Source |
|---|---|---|
| Closing spread MAE (all regular-season games with a line) | 10.25 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Sample size behind the closing-spread MAE | 7087 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Slope of actual margin on closing spread (1.0 = unbiased) | 1.049 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Over rate against the closing total (pushes excluded) | 0.4953 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Model spread MAE, walk-forward 2023-2026 | 10.391 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Market spread MAE on the same games (the benchmark) | 9.711 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Walk-forward test-set size | 936 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Coefficient on the model margin controlling for the closing line (HC1) | -0.0193 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| p-value on that coefficient | 0.8807 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Pearson r: QB passing yards vs WR1 receiving yards (same team-game) | 0.561643 | https://github.com/nflverse/nflverse-data/releases/tag/stats_player |
| Pythagorean expectation vs actual wins, R^2 | 0.8191 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| Year-over-year persistence of Pythagorean luck (r) | 0.023894 | https://github.com/nflverse/nflverse-data/releases/tag/schedules |

## What did not survive

* **V-04** Published pooled ATS 'cover rate' vs the home-side cover rate: published 0.5, recomputed 0.4891. Published figure is per team-game from data/derived/luck.json; this recomputation is the same population reconstructed from the extract. Pushes are excluded.
* **V-05** Published pooled ATS 'wins' vs home-team covers: published 6892, recomputed 3371. 

### Irregularities

| ID | Issue | Impact | Source |
|---|---|---|---|
| IR-01 | The 50.0% ATS coin-flip test is a tautology, not evidence | The site's 'the spread market shows no exploitable tilt' conclusion survives, but the quoted statistic behind it does not measure what it claims. Treat the p=1.0 as unverified. | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| IR-02 | Two different 'our model' MAE numbers are published on different pages | README prose is stale against the committed data. The site is correct; the README should be updated by its owner. | https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/predictions.csv |
| IR-03 | Committed data ends before the week the site is being read in | Line origination for an unplayed week cannot be scored or compared to market using this extract. The pipeline must refresh before any decision that depends on this week. | https://www.nfl.com/injuries/league/2026/reg10 |
| IR-04 | Ties are silently excluded from the Pythagorean win totals | Minor. Document the convention before the luck decomposition is used to rank anything. | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| IR-05 | No historical player-prop prices exist in any committed source | Any prop-family strategy must remain 'no price -> no result' until a licensed price source is committed. | https://github.com/nflverse/nflverse-data/releases/tag/stats_player |
| IR-06 | Injury, depth-chart and snap-count feeds are published upstream but not committed here | The injury and backup-depth requirement cannot be met from inside this environment. It needs a workflow run on GitHub-hosted runners that downloads those assets and commits the derived summaries, exactly as the existing data-pipeline does for schedules. | https://github.com/nflverse/nflverse-data/releases/tag/injuries |
| IR-07 | Gate G1 (point-in-time integrity) cannot be satisfied by the current feeds | Before any strategy is funded, the project needs a timestamped line capture and a timestamped lineup snapshot. No amount of modelling substitutes for that. | https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/strategies.json |
| IR-08 | Unfinished seasons are treated as complete team-seasons in the luck decomposition | Report the luck decomposition on completed seasons only, or label 2026 as partial. The direction of every conclusion (luck does not persist) is unchanged. | https://github.com/nflverse/nflverse-data/releases/tag/schedules |
| IR-09 | A cited official URL returns 404 (rulebook path changed) | Every rulebook citation in the repository should be re-checked. A citation that 404s is not evidence, and the settlement rules (push, overtime, final score) matter for any backtest that uses them. | https://operations.nfl.com/rules-officiating/2026-nfl-rulebook |
| IR-10 | The NFL's injury-report policy page returns no article body | The deadline facts are still officially sourced. The policy's own wording about what must be disclosed is quoted from second-hand summaries and is marked unverified. | https://www.nfl.com/news/2026-27-national-football-league-important-dates |

## The measurement the pricing decision rests on

* 5,896 team-games measured.
* QB passing yards vs WR1 receiving yards: r = 0.560384.
* Best 2-leg joint: measured 0.336, independent product 0.2431 (-27.7% error).
* No historical player-prop price exists in this repository, so no prop ROI is computed.

## Recommended sequence

1. **SG-01 Approve or reject the site's current answer before adding another model** - Approve (effort S, payoff High).
2. **SG-02 Timestamp every line, or stop calling any edge 'live'** - Approve (effort M, payoff Very high).
3. **SG-03 Commit the injury, depth-chart and snap-count feeds on a runner** - Approve (effort M, payoff High).
4. **SG-04 Fix the ATS coin-flip statistic before it is cited again** - Approve (effort S, payoff Medium).
5. **SG-05 Publish the parlay pricing gap as the headline, not correlation coefficients** - Approve (effort S, payoff High).
6. **SG-06 Give the leaderboard a reward rule that cannot be gamed by variance** - Approve (effort S, payoff High).

## What would change this conclusion

* A timestamped price series showing a repeatable gap between a captured price and the close.
* A depth-chart and snap-count history showing a measurable effect from losing a specific starter.
* A licensed prop price history that turns the measured correlation gap into a priced edge.
* A candidate that passes all ten gates out of sample, with a positive lower bound.

Until one of those exists, the correct decision is to keep researching and to fund nothing.

## Caveat

Reproducibility is not validation. These checks show the published numbers follow from the committed extract. They say nothing about whether any strategy is profitable or any price obtainable.

Every figure above is read from the committed JSON in `site/data/`. Nothing is typed by hand.
