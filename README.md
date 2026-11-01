# Line Lab — NFL line origination research

Originate our own NFL lines, test whether they carry skill, and publish only what
survives validation. The generated site is at
**<https://karagemop466-tech.github.io/Korea2/>**.

> Research, not betting advice. Nothing in this repository is ranked for betting.

## What is in here

```
index.html, pages/        generated site (do not hand-edit; run the build)
assets/style.css          shared layout
scripts/analysis/         the whole pipeline
  common.py               loaders, odds maths, bootstrap, permutation, BH-FDR
  prepare.py              prune nflverse extracts -> data/derived, write provenance
  market.py               line calibration, blind-bet returns, 12 public angles
  strategies.py           rating model, 5 strategies, 6 gates, parlay pricing
  correlations.py         11 measured correlation pairs, SGP pricing
  props.py                player projections, median-line calibration
  originate.py            spread + total for every unplayed game
  verification.py         reconcile 2026 against NFL.com
  build_site.py           render every page from results/*.json
  build.py                run all of the above
data/derived/            committed pruned extracts (raw downloads are gitignored)
data/provenance.json     URL, row count and SHA-256 of every source file
results/                 committed JSON outputs, the single source for the site
tests/check_site.py      links, nav, one source link per table row
tests/check_data.py      statistical invariants the prose depends on
.github/workflows/       data refresh + build verification
```

## Run it

```bash
pip install pandas numpy scipy
python scripts/analysis/build.py     # regenerate results/ and the site
python tests/check_data.py           # statistical invariants
python tests/check_site.py           # links and source coverage
```

`build.py` makes no network calls. If `data/derived/` is missing, refresh it with
the `refresh-data` workflow, which downloads the nflverse releases and re-runs
`prepare.py`.

## Method in one paragraph

Every rule is fixed before outcomes are examined and only uses pre-kickoff
information. Seasons are walked forward: each season is predicted using earlier
seasons only. Bets settle at the closing price stored in the data, never an
assumed −110. A strategy enters the leaderboard only after clearing six gates:
sample size, two-sided significance, Benjamini–Hochberg correction across all
strategies tried, positive return with a bootstrap interval that excludes zero, a
permutation test against random portfolios of the same size, and a minimum
track-record length. No strategy currently clears all six.

## Sources

Two tiers, never blurred:

* **Official.** NFL.com standings, schedules, player stats and team stats. Every
  headline figure is reconciled against these. All 32 team records for 2026 match
  exactly, as do three quarterback passing lines.
* **Third-party.** nflverse publishes machine-readable extracts of the NFL's own
  play-by-play and box scores, including the historical closing prices that no
  league source publishes. It is a redistributor, not the league. Byte sizes and
  SHA-256 of every file used are recorded in `data/provenance.json`.

## Known limitations

Listed in full on the site's **Flagged for review** page. The short version:
closing prices only, no historical prop prices, incomplete weather fields, 2026
only is reconciled team by team, and the rating model loses to the market.
