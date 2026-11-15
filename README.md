# NFL Line Lab — research, evidence and decision readiness

**As of 2026-11-15.** This repository is a research and measurement project, not a live betting service. No candidate strategy is approved for deployment, the reward pool is unfunded, and the displayed Week 9 model lines are historical—not current recommendations.

- **Live GitHub Pages site:** [karagemop466-tech.github.io/Korea2](https://karagemop466-tech.github.io/Korea2/)
- **Current repository-level executive summary:** [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
- **Dated site/repository audit:** [docs/REPOSITORY_STATUS_2026-11-15.md](docs/REPOSITORY_STATUS_2026-11-15.md)
- **Flagged issues:** [root Flagged for Review](pages/flagged.html) · [Line Desk flags](line-desk/pages/flagged.html) · [Week 10 injury-report flags](injury-report-w10/index.html)

## Start here

The repository has several independently built dashboards. They do not yet form one canonical site; the root navigation omits some recent hubs and repeats the “Suggestions hub” link. These direct links are intentional until the shared-navigation owner integrates them.

### Decision and requirements review

- [Line Desk](line-desk/index.html) — latest committed requirements view (as of 2026-11-14): price-snapshot coverage, official results, origination order, signal versus staking, official-only standings correlations, replacement-depth gaps, gates, questions and suggestions.
- [Line Desk: Requirements](line-desk/pages/requirements.html) — 19 traced requirements; 11 reported built, 5 partial, 3 carried/existing/in-progress.
- [Line Desk: Questions & answers](line-desk/pages/questions.html) — known information, missing information, discovery route and blocked decision.
- [Line Desk: Suggestions](line-desk/pages/suggestions.html) — 12 proposed items; all await review. No proposal is auto-implemented.
- [Price Desk](price-desk/index.html) — larger historical price/result registers, with official rows separated from archive-only values; includes the Game Book demonstration and its own review questions/suggestions.
- [Price Desk: Results](price-desk/pages/results-feed.html) · [Price snapshots](price-desk/pages/price-snapshots.html) · [Game Book/source register](price-desk/pages/sources.html) · [Suggestions](price-desk/pages/suggestions.html) · [Questions](price-desk/pages/questions.html)
- [Price Store](price-store/index.html) — strict official-source schema and gate tests; the committed official-price snapshot CSV is empty.
- [Review Board](review-board/index.html) — cross-hub review queue generated from **seven configured registers**. It does not currently ingest the newer Line Desk or Price Desk suggestion/question registers.
- [Review Board: Suggestions](review-board/pages/suggestions.html) · [Questions](review-board/pages/questions.html) · [Reconciliation](review-board/pages/reconciliation.html) · [Flagged](review-board/pages/flagged.html) · [Hub map](review-board/pages/hubmap.html)

### Analysis and validation

- [Root analysis dashboard](index.html) — historical analysis snapshot; the root model inputs end on 2026-11-01.
- [Originated lines](pages/lines.html) · [Player props](pages/props.html) · [Correlation & parlays](pages/correlation.html) · [Removing luck](pages/luck.html)
- [Strategy leaderboard](pages/leaderboard.html) · [Validation gates](pages/validation.html) · [Independent verification](pages/verification.html)
- [Source register](pages/sources.html) · [Archive of sibling dashboards](pages/archive.html)

### Injury and replacement evidence

- [Official-only sample and depth limitations](line-desk/pages/depth.html) — 11 Week 10 report rows across four clubs; replacement identity and string tier are blank because this source does not state them.
- [Week 10 NFL injury-report re-verification](injury-report-w10/index.html) — a different session's 2026-11-15 fetch record covers 14 games/28 listed teams. Only DET/SEA/CIN (3/28 team tables) were transcribed row by row; other counts are manual, four clubs are absent with bye status unverified, and no raw-response hash exists. See its seven flags; this is not a complete 32-team point-in-time archive or a depth source.
- [Injury/depth research hub](decision-hub/pages/injuries.html) — a separate analysis built partly from nflverse community releases. Treat its depth and snap fields as third-party data, not as official NFL starter or inactive evidence.
- [Decision Desk injury view](decision-desk/pages/injuries.html) — another independently sourced/compiled view; its flags document chart, roster and report conflicts.

## Current evidence snapshot

Dates below are not interchangeable. The root analysis and the requirements desk use different snapshots; neither provides current live-slate lines.

- **Root model data:** the committed analysis snapshot ends on gameday **2026-11-01**. The source manifest identifies nflverse as a community-maintained source and notes that its sportsbook-derived market lines are not an official sportsbook archive. The root result is therefore reproducible research, not an official market feed. See [`data/derived/manifest.json`](data/derived/manifest.json) and the [verification page](pages/verification.html).
- **Requirement desk:** the Line Desk registers 19 requirements. It reports **11 built, 5 partial and 3 carried/existing/in-progress**; see the status and evidence per row on [Requirements](line-desk/pages/requirements.html).
- **Results:** two separate registers have different scopes. The Line Desk marks **44 NFL.com finals** for Weeks 7–9 plus Week 10 Thursday; 27 compare with the older snapshot and match, while 17 later finals had blank scores there. The Price Desk has a 1,088-game 2023–2026 feed: 22 scores marked official, 931 archived-unverified and 135 missing/unsettled; of the 22 official scores, 5 could be cross-checked against the archive and matched, while 17 filled blank archive rows. Do not add these counts together or treat the archive-only rows as official. See [Line Desk Results](line-desk/pages/results-feed.html), [Price Desk Results](price-desk/pages/results-feed.html) and the [Price Desk verified-results record](price-desk/data/verified_results_2026.json).
- **Prices:** there is no official open/close archive. The Price Desk has 2,364 game-market rows: all 2,364 opening fields are blank; 1,956 closing-line values are explicitly `archived-unverified` (nflverse-derived) and 408 are blank. Its 11,370 prop rows have no market open/close. The separate `price-store` official-only snapshot file has 0 rows. The Line Desk's 45 Week 9 model-line rows capture 45/45 of its own initial lines but 0 own closes, 0 official market opens and 0 official market closes. These are different stores, not official quotes; CLV and official price-based ROI are not established. See [Price Desk snapshots](price-desk/pages/price-snapshots.html), [Line Desk snapshots](line-desk/pages/price-snapshots.html), [empty official-only store](price-store/data/snapshots.csv) and the [NFL–Genius Sports announcement](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports).
- **Leaderboard:** no strategy is qualified for deployment and no reward is funded. The root/Line Desk lists 7 candidates plus 2 controls; the Price Desk also reports 28 historical entrants, all `NEEDS_REVIEW` or `REJECTED`. Its results use third-party archived closing prices, not official odds. The root leaderboard page, Line Desk and Price Desk do not share one ranking rule or candidate set; do not compare their ranks as if they were a single competition. See [root leaderboard](pages/leaderboard.html), [Line Desk signal/staking](line-desk/pages/leaderboard.html) and [Price Desk leaderboard](price-desk/pages/leaderboard.html).
- **Official-only correlations:** eight coefficients are calculated from NFL.com 2025/2026 standings transcriptions, each with *n* and an interval (six values have n=32; two pooled values have n=64). This is team-standings evidence, not a verified player-prop or same-game joint-probability matrix. See [Correlations](line-desk/pages/correlations.html), the [2025 standings](https://www.nfl.com/standings/division/2025/REG), the [2026 standings](https://www.nfl.com/standings/division/2026/REG) and [NIST's correlation interval reference](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm).
- **Availability/depth:** the Line Desk has 11 official-report rows from four clubs, with **0 replacement names and 0 string tiers**. A Price Desk proof-of-concept records one official NFL Game Book (WAS@NYG) for starting lineups, Did-Not-Play, Not-Active and weather, and cites a second Game Book for a score check; a scheduled, all-week ingestion pipeline is not built. The Game Book identifies who started, not an official 2nd/3rd/4th-string depth rank. Another hub uses nflverse depth/roster/snap releases; those remain third-party and do not replace Game Book evidence. See [Line Desk Depth](line-desk/pages/depth.html), [Price Desk results](price-desk/pages/results-feed.html), the [WAS@NYG Game Book PDF](https://static.www.nfl.com/image/upload/v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf) and the [NFL injury report](https://www.nfl.com/injuries/league/2026/reg10).
- **Model governance:** two committed originators disagree by 1.5–9.0 points on each of the same 15 Week 9 games. The project has not selected a canonical originator. This is an internal-repository discrepancy, not an NFL fact; see [Origination](line-desk/pages/origination.html).

The Line Desk and Price Desk source registers record NFL/NIST pages and Game Books opened by earlier sessions on **2026-11-14**. The separate `injury-report-w10/` coordination record reports another session's fetch-tool read of all eight Week 10 report chunks on **2026-11-15**, with partial row transcription and no raw-response hash. This session inspected the committed registers and ran local checks but did not fetch those external pages; see [Line Desk Sources](line-desk/pages/sources.html), [Price Desk Sources](price-desk/pages/sources.html), the [Week 10 re-verification](injury-report-w10/index.html) and the dated [repository audit](docs/REPOSITORY_STATUS_2026-11-15.md). Do not treat an internal source label as a new independent verification. The root analysis still contains tables based on nflverse community data; those rows are labelled third-party, not official NFL facts. The strict requirement that every displayed value be confirmed from an official site is therefore **not yet met across the full repository**.

## Review before implementation

Suggestions are deliberately kept separate from implementation:

1. Compare the [Review Board queue](review-board/pages/suggestions.html) (seven configured source registers) with the [Line Desk queue](line-desk/pages/suggestions.html) (12 items) and [Price Desk queue](price-desk/pages/suggestions.html) (10 items). The Review Board does not yet ingest the latter two registers.
2. Read [Line Desk questions](line-desk/pages/questions.html) and [Price Desk questions](price-desk/pages/questions.html) for what is known, what is missing and how to discover it.
3. Keep unsupported values blank and visible on the [Line Desk Flagged for Review](line-desk/pages/flagged.html) and [Price Desk Flagged page](price-desk/pages/flagged.html). No item in these queues has been approved by this README update.

The principal blockers are a permitted timestamped price source, a canonical line originator, full official results history, immutable pre-kickoff availability/inactive evidence, a verified 32-club depth-source route, and an explicit reward/funding policy. These are listed—not silently decided—for review.

## Verification performed in this session

- `python3 tests/check_site.py` — pass: 232 HTML pages, 584 tables and 13,560 links; 33 pages outside the root published build are link-checked but do not carry the root table-source column.
- `python3 scripts/check_links.py` — pass: 4,637 local references, no broken internal links.
- `python3 scripts/validate_data.py` and `python3 tests/check_data.py` — pass for the root data-validation scope.
- `python3 tests/check_derived.py` — pass: strict JSON, 52 recorded independent checks with 0 mismatches, 32/32 teams reconciled for 2020, and 25 generated root pages linked.
- `python3 line-desk/scripts/build_site.py --check` and `python3 line-desk/scripts/verify.py` — pass for the Line Desk deterministic render, blank policy, source links and correlations.
- `python3 price-desk/scripts/verify.py` and `python3 -m unittest discover -s price-desk/tests -v` — pass: 20,504 register checks, 0 errors; 10 unit tests passed. These check committed records, not external page contents.
- `python3 review-board/scripts/verify_all.py`, `python3 decision-desk/scripts/verify_all.py`, `python3 verify-hub/scripts/verify.py`, the Verify Hub unit tests and `price-store` tests — pass.

The latest GitHub Pages API check on 2026-11-15 18:20 UTC reported `built` for main commit `a08c249352d2be2028affa1fbb2c13d1b3d93235`. That deployment predates and does not include these unmerged documentation edits; it confirms only the prior site build, not source freshness or correctness.

## Repository and data policy

- Public pages should contain derived analysis and links to official source pages; raw captures should be retained with capture time, source URL, hash and conflict status in a governed store.
- nflverse is community-maintained, not the NFL. Values derived from it are labelled third-party and must not be described as officially verified unless a row is separately reconciled against an official source.
- Never infer starter status, string depth, inactives, snap share, a missing injury designation or price. Preserve blanks and flag the missing source.
- Parlays and prop combos require directly validated joint probabilities and explicit settlement/void rules; multiplying marginals is not evidence of a joint probability.
- Strategy registration must precede the evaluation window. Rank skill with proper scores, uncertainty, chronological holdouts and multiplicity controls; report staking outcomes separately.

## Running the reproducible checks

Install the repository's pinned dependencies in a clean virtual environment, then run the relevant checkers. The system Python in the development sandbox does not include NumPy; `verification/recompute.py` requires the analysis dependencies from `requirements.txt`.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python tests/check_site.py
python scripts/check_links.py
python scripts/validate_data.py
python tests/check_data.py
python tests/check_derived.py
python verification/recompute.py
python line-desk/scripts/build_site.py --check
python line-desk/scripts/verify.py
python review-board/scripts/verify_all.py
```

For the complete repository inventory, see the [root archive](pages/archive.html) and [Review Board hub map](review-board/pages/hubmap.html).
