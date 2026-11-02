# Line Lab — NFL line origination and strategy validation

A working research pipeline that originates its own NFL spreads, totals, moneylines and player-prop
lines from the official play-by-play feed, measures the correlations that decide parlay prices, and
runs every candidate strategy through ten validation gates before it can earn anything.

**Live site:** https://karagemop466-tech.github.io/Korea2/

## Result of the current build

| Question | Answer | Evidence |
|---|---|---|
| Can the closing line be beaten by this model? | No | model spread MAE 10.38 vs market 9.70; model coefficient on margin after controlling for the close = −0.02 (p = 0.85) |
| Did any strategy pass the gates? | No, 0 of 7 candidates (2 controls also fail) | see [Leaderboard](https://karagemop466-tech.github.io/Korea2/pages/leaderboard.html) |
| Are parlay legs independent? | No | QB passing yards ↔ WR1 receiving yards r = +0.561; 4-leg same-team joint 11.1% vs 5.7% under independence |
| Is a season win-loss record a signal? | Mostly luck | Pythagorean R² = 0.83; year-over-year luck correlation 0.019 |
| Can prop ROI be measured? | Not here | no historical prop prices in the feed — flagged, not invented |
| Do the published numbers survive an independent recomputation? | Yes | 45 of 49 checks agree, 0 material disagreements; 2020 season reconciles 32/32 teams with NFL.com — [Verification](https://karagemop466-tech.github.io/Korea2/pages/verification.html) |

The honest headline is that the market is better than the model, and the gate system rejects
everything as a result. That is the intended behaviour of the system, not a failure of it.

## How it works

```
scripts/fetch_data.py   download official feeds (runs on GitHub Actions)  -> data/raw/  (gitignored)
scripts/profile.py      record columns, coverage, nulls                   -> data/derived/profile.json
scripts/diag_signs.py   prove the spread sign convention from the data    -> data/derived/diag_signs.json
scripts/analyze_*.py    market, model, correlation, luck, strategies, props -> data/derived/*.json
scripts/build_site.py   render the dashboard from that JSON               -> index.html, pages/
tests/check_site.py     link integrity + per-row source discipline
tests/check_derived.py  strict JSON, verification record, no orphan pages
verification/recompute.py  independent re-implementation of the headline numbers (imports nothing here)
```

Nothing on the site is typed by hand; every number is read from the committed JSON. Re-running the
pipeline changes the numbers, not the prose.

### Why the pipeline downloads on Actions

The development sandbox's shell can only reach a small allowlist of hosts, and GitHub **release
assets** redirect to `objects.githubusercontent.com`, which is blocked there. The download therefore
runs on GitHub-hosted runners (`.github/workflows/data-pipeline.yml`) and commits the derived
artefacts back to the branch. Every published number is reproducible from committed code plus
`data/derived/manifest.json`, which records each source file's size and SHA-256.

### Measured pipeline

Bets are settled at the **closing line** reported by the feed, so nothing can hide behind a stale or
soft price. Spread pushes and total pushes follow the operator rulebook (a tie after the handicap is
a push and the stake is returned), and pushes are removed from the win-rate denominator.

## Repository layout

| Path | Contents |
|---|---|
| `index.html`, `pages/` | the published dashboard (14 pages) |
| `data/derived/` | committed outputs: profile, manifest, market, model, correlation, luck, strategies, props, predictions |
| `data/sources.json` | source register, each entry opened and confirmed on 2026-11-01 |
| `scripts/` | fetch, profile, diagnostics, analysis, site build |
| `tests/check_site.py` | fails the build on a broken link or a table row without a source |
| `tests/check_derived.py` | fails the build on non-strict JSON, an orphan page, or a verification disagreement |
| `verification/` | independent recomputation plus the transcribed NFL.com standings used to reconcile them |
| `docs/` | executive summary, methodology, requirements matrix |
| `pipeline/`, `origination/` | session `3f5af27c`: the origination/strategy/gating pipeline and its 13-page site (`origination/index.html`) |
| sibling directories | earlier parallel-session dashboards, preserved unchanged (`pages/archive.html`) |

## Running it

```bash
pip install -r requirements.txt
python scripts/fetch_data.py     # needs unrestricted outbound HTTPS
python scripts/profile.py
python scripts/diag_signs.py
for s in analyze_market analyze_model analyze_correlation analyze_luck analyze_strategies analyze_props; do python scripts/$s.py; done
python scripts/build_site.py     # requires Python 3.12+
python tests/check_site.py
```

## Sources

Official NFL documents (rules, statistician guide, data-distribution partnership), a regulator-filed
operator rulebook, and statistical literature (Kelly 1956, Benjamini–Hochberg 1995, NIST). Every
claim on the site links to one of them; the register with confirmation notes is on the
[Source register page](https://karagemop466-tech.github.io/Korea2/pages/sources.html).
Unconfirmable items are on the
[Flagged for review page](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) instead of
being filled in.

## Scope and disclaimer

Research and measurement, not betting advice. No strategy is approved for capital, no reward pool is
funded, and no sportbook access, price or limit has been verified.
