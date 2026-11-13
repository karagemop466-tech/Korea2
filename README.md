# Line Lab — NFL line origination and strategy validation

A reproducible research pipeline that originates NFL spreads, totals, moneylines and player-prop
lines from community-maintained nflverse game and weekly-stat extracts, measures correlations, and
runs candidate strategies through ten validation gates. nflverse is not the NFL; selected seasons are
reconciled against NFL.com, and the precise verification limits are flagged.

**Live site:** https://karagemop466-tech.github.io/Korea2/

## Result of the committed data snapshot

The dataset is through **2026-11-01**; this repository snapshot is not current to the live Week 10 slate, re-checked on **2026-11-13**: the official NFL.com standings show 137 regular-season games played against the 120 in the committed extract, so the snapshot is **17 games behind** the live page. Do not use its Week 9/next-slate projections as current lines. See [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html).

| Question | Answer | Evidence |
|---|---|---|
| Can the closing line be beaten by this model? | No | model spread MAE 10.39 vs market 9.71; model coefficient on margin after controlling for the close = −0.019 (p = 0.881) |
| Did any strategy pass the gates? | No, 0 of 7 candidates (2 controls also fail) | see [Leaderboard](https://karagemop466-tech.github.io/Korea2/pages/leaderboard.html) |
| Are parlay legs independent? | No | QB passing yards ↔ WR1 receiving yards r = +0.562; 4-leg same-team joint 11.14% vs 5.69% under independence |
| Is a season win-loss record a signal? | Mostly luck | Pythagorean R² = 0.82; year-over-year luck correlation 0.024 (n = 842) |
| Can prop ROI be measured? | Not here | no historical prop prices in the feed — flagged, not invented |
| Do the published numbers survive an independent recomputation? | Yes | 49 checks from the verification session: 45 strict equality checks agree, 0 disagree, 11 observations; plus a second, independent implementation added on 2026-11-13 — 45 checks, 41 exact matches, 4 documented differences, 0 mismatches. The 2020 season reconciles 32/32 with NFL.com — [Verification](https://karagemop466-tech.github.io/Korea2/pages/verification.html) |

The honest headline is that the market is better than the model, and the gate system rejects
everything as a result. That is the intended behaviour of the system, not a failure of it.

## Start here

| If you want to… | Go to |
|---|---|
| see every published workspace in one map | [Workspaces](https://karagemop466-tech.github.io/Korea2/pages/workspaces.html) |
| read the one-page summary | [Executive summary](https://karagemop466-tech.github.io/Korea2/pages/executive.html) |
| decide what to do next | [Decision summary](https://karagemop466-tech.github.io/Korea2/pages/decision-summary.html) · [Open questions](https://karagemop466-tech.github.io/Korea2/pages/decision-questions.html) · [Suggestion register](https://karagemop466-tech.github.io/Korea2/pages/decision-suggestions.html) |
| check the numbers | [Verification](https://karagemop466-tech.github.io/Korea2/pages/verification.html) |
| review what is missing | [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) |
| see what this integration pass changed | [`docs/INTEGRATION_REVIEW.md`](docs/INTEGRATION_REVIEW.md) |

## Decision hub — read this before changing anything

The site answers "what is true". It did not answer "what should we do next". That layer now lives
in [`decision-hub/`](decision-hub/index.html), and it is the place to start:

| Page | What it is for |
|---|---|
| [Executive summary](decision-hub/pages/executive-summary.html) | the one-page version, every number classed |
| [Suggestions](decision-hub/pages/suggestions.html) | 14 proposals, each with impact, cost, risk and the decision it unblocks |
| [Questions & unknowns](decision-hub/pages/questions.html) | 16 questions split into what we know and what we do not, sorted by how many decisions each blocks |
| [Decisions](decision-hub/pages/decisions.html) | the three choices that gate everything else, with the evidence for each option |
| [Strategy framework](decision-hub/pages/strategies.html) | the ten gates, the leaderboard, and why nothing passes |
| [Injuries & depth](decision-hub/pages/injuries.html) | who is out and how far down the depth chart it reaches — 1st/2nd/3rd string per position |
| [Line-by-line audit](decision-hub/pages/audit.html) | every published number recomputed by an independent implementation |
| [Review workflow](decision-hub/pages/workflow.html) | how to choose a path without implementing anything first |

**One finding from that audit changes a published conclusion:** the headline "ATS coin-flip test —
50.0%, p = 1.0" is an arithmetic identity, not a test (every game is pooled twice, once per side).
The honest one-observation-per-game figure is 48.91% home covers, 95% CI 47.73–50.09%, p = 0.073.
See [FL-DH-01](decision-hub/pages/flagged.html).

### Injury and depth data

`decision-hub/data/injuries.json` is built by `.github/workflows/fetch-injuries.yml` from the
official NFL injury report plus the nflverse depth-chart, roster and snap-count releases. It runs on
a GitHub runner because release assets redirect to a host the development sandbox cannot reach.
Refresh locally with an unrestricted network:

```bash
python decision-hub/scripts/fetch_injuries.py --season 2026
python decision-hub/scripts/audit_root.py
python decision-hub/scripts/build_site.py
python decision-hub/scripts/check_site.py
```

## How it works

```
scripts/fetch_data.py   download nflverse community extracts (GitHub Actions) -> data/raw/ (gitignored)
scripts/profile.py      record columns, coverage, nulls                   -> data/derived/profile.json
scripts/diag_signs.py   prove the spread sign convention from the data    -> data/derived/diag_signs.json
scripts/analyze_*.py    market, model, correlation, luck, strategies, props -> data/derived/*.json
scripts/build_site.py   render the dashboard from that JSON               -> index.html, pages/
tests/check_site.py     link integrity + per-row source discipline
tests/check_derived.py  strict JSON, verification record, no orphan pages
verification/recompute.py  independent re-implementation of the headline numbers (imports nothing here)
verification/integration_recompute.py  second independent implementation, written by the 2026-11-13 integration pass
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
| `index.html`, `pages/` | the published dashboard (16 pages, grouped navigation) |
| `data/derived/` | committed outputs: profile, manifest, market, model, correlation, luck, strategies, props, predictions |
| `data/sources.json` | source register, each entry opened and confirmed on 2026-11-01 |
| `data/site_register.json` | the directory of every published workspace: what it holds, how many pages it publishes, where its own review page is |
| `scripts/` | fetch, profile, diagnostics, analysis, site build |
| `tests/check_site.py` | fails the build on a broken link or a table row without a source |
| `tests/check_derived.py` | fails the build on non-strict JSON, an orphan page, or a verification disagreement |
| `verification/` | two independent recomputations plus the transcribed NFL.com standings used to reconcile them |
| `docs/` | executive summary, methodology, requirements matrix, and the 2026-11-13 integration review |
| `pipeline/`, `origination/` | session `3f5af27c`: the origination/strategy/gating pipeline and its 13-page site (`origination/index.html`) |
| sibling directories | the other workspaces — decision desks, research labs, audits — each with its own data and flags (`pages/workspaces.html`) |

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

NFL primary sources and regulator/statistical references support rules, definitions and documented cross-checks.
Historical game/stat inputs come from nflverse community-maintained extracts, not an NFL-published feed;
selected seasons are reconciled against NFL.com and the limited scope is flagged. The source register is on the
[Source register page](https://karagemop466-tech.github.io/Korea2/pages/sources.html).
Unconfirmable items are on the
[Flagged for review page](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) instead of
being filled in.

## Scope and disclaimer

Research and measurement, not betting advice. No strategy is approved for capital, no reward pool is
funded, and no sportbook access, price or limit has been verified.
