# NFL Line Lab — research, evidence and decision readiness

**As of 2026-11-19** (final integration re-verification; previous state: 2026-11-15). This repository is a research and measurement project, not a live betting service. No candidate strategy is approved for deployment, the reward pool is unfunded, and the displayed Week 9 model lines are historical—not current recommendations.

- **Live GitHub Pages site:** [karagemop466-tech.github.io/Korea2](https://karagemop466-tech.github.io/Korea2/)
- **Current repository-level executive summary:** [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
- **Dated official re-read (2026-11-19):** [docs/OFFICIAL_REREAD_2026-11-19.md](docs/OFFICIAL_REREAD_2026-11-19.md) — the final integration session re-read the Week 10/11 injury reports, Week 10/11 schedules and 2026 standings against the committed registers (0 mismatches) and re-ran every verification suite.
- **Dated site/repository audit:** [docs/REPOSITORY_STATUS_2026-11-15.md](docs/REPOSITORY_STATUS_2026-11-15.md)
- **Flagged issues:** [root Flagged for Review](pages/flagged.html) · [Line Desk flags](line-desk/pages/flagged.html) · [Week 10 injury-report flags](injury-report-w10/index.html)

## Start here

The repository has several independently built dashboards. As of 2026-11-19 the root navigation links **all 24** hub directories that have an `index.html`, with no duplicate or dead hub links (verified programmatically during integration). These direct links are intentional; each hub keeps its own navigation and verification suite.

### Week 11 availability — new 2026-11-19 (official capture, per-club counts, flags)

- [Week 11 availability hub](availability-w11/index.html) — two official reads of the Week 11 NFL injury report on 2026-11-19 (identical raw SHA-256): **253** listed rows, **24 of 26** playing clubs with a table, CIN and WAS with **no table** (flagged, not treated as healthy), 6 byes, 13 official fixtures. Starters, depth, replacements, venues and deltas are blank and flagged. [Clubs](availability-w11/pages/clubs.html) · [Schedule & byes](availability-w11/pages/schedule.html) · [Captures](availability-w11/pages/captures.html) · [Flagged for Review (10 items)](availability-w11/pages/flagged.html).
- **Terms:** the NFL.com terms (section 1.3) prohibit systematic retrieval to build a compilation without written consent. This is an open owner decision (W11-F04) that gates any public row-level release.

### Requirements Desk — new 2026-11-18 (official capture, decision readiness, review queues)

- [Requirements Desk](requirements-desk/index.html) — landing page: one row per brief requirement with the
  gate that blocks it and the number that would clear it. 74 requirements: 13 verified, 36 partial,
  17 blocked, 8 not started.
- [Requirements register](requirements-desk/pages/requirements.html) — the same 74 rows, full width.
- [Availability register](requirements-desk/pages/injuries.html) — **347** Week 10 injury-report rows across
  28 club tables, transcribed verbatim, plus per-club counts, the game-status distribution, the four absent
  clubs and the dated news headlines the report page itself links.
- [Verified results](requirements-desk/pages/results.html) — Week 10: 14/14 games FINAL from the official
  schedule page.
- [Fixture & venue](requirements-desk/pages/schedule.html) — Week 11: 13 fixtures with kickoff, network and
  venue, 6 clubs on bye, 1 neutral-site game.
- [Standings & luck](requirements-desk/pages/standings.html) · [Removal of luck](requirements-desk/pages/luck.html) ·
  [Official correlations](requirements-desk/pages/correlations.html) — four coefficients at n=32 with
  Fisher-z 95% intervals; luck SD 1.076 wins.
- [Suggestion review queue](requirements-desk/pages/suggestions.html) — 12 prioritised proposals, each with
  the paths a reviewer can choose between. Nothing is auto-implemented.
- [Decision questions](requirements-desk/pages/questions.html) — 12 questions, each with what is known,
  what is missing, how to discover it and which decision stays blocked.
- [Brief claim audit](requirements-desk/pages/verification.html) · [Flagged for review](requirements-desk/pages/flagged.html) ·
  [Source register](requirements-desk/pages/sources.html)

Three brief claims were checked against the official page and came out differently: the three Lions rows are
**Out** (confirmed); Cincinnati has **9** listed players, not 4 (corrected); and the report holds **347** rows
with **171** game designations, not 254/279 with 6 (corrected). CHI, DEN, PHI and TB are absent because they
are on bye, which the official Week 10 schedule page confirms.

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

The Line Desk and Price Desk source registers record NFL/NIST pages and Game Books opened by earlier sessions on **2026-11-14**. The separate `injury-report-w10/` coordination record reports another session's fetch-tool read of all eight Week 10 report chunks on **2026-11-15**, with partial row transcription and no raw-response hash. This session inspected the committed registers and ran local checks but did not fetch those external pages; see [Line Desk Sources](line-desk/pages/sources.html), [Price Desk Sources](price-desk/pages/sources.html), the [Week 10 re-verification](injury-report-w10/index.html) and the dated [repository audit](docs/REPOSITORY_STATUS_2026-11-15.md). On **2026-11-19** the integration session re-fetched the Week 10 and Week 11 injury reports, both weekly schedules, the 2026 standings and the policy pages, and compared them against the committed registers with 0 mismatches; see [docs/OFFICIAL_REREAD_2026-11-19.md](docs/OFFICIAL_REREAD_2026-11-19.md). Do not treat an internal source label as a new independent verification. The root analysis still contains tables based on nflverse community data; those rows are labelled third-party, not official NFL facts. The strict requirement that every displayed value be confirmed from an official site is therefore **not yet met across the full repository**.

## Review before implementation

Suggestions are deliberately kept separate from implementation:

1. Compare the [Review Board queue](review-board/pages/suggestions.html) (seven configured source registers) with the [Line Desk queue](line-desk/pages/suggestions.html) (12 items) and [Price Desk queue](price-desk/pages/suggestions.html) (10 items). The Review Board does not yet ingest the latter two registers.
2. Read [Line Desk questions](line-desk/pages/questions.html) and [Price Desk questions](price-desk/pages/questions.html) for what is known, what is missing and how to discover it.
3. Keep unsupported values blank and visible on the [Line Desk Flagged for Review](line-desk/pages/flagged.html) and [Price Desk Flagged page](price-desk/pages/flagged.html). No item in these queues has been approved by this README update.

The principal blockers are a permitted timestamped price source, a canonical line originator, full official results history, immutable pre-kickoff availability/inactive evidence, a verified 32-club depth-source route, and an explicit reward/funding policy. These are listed—not silently decided—for review.

## Verification performed 2026-11-19 (integration re-run)

- `python3 tests/check_site.py` — pass: 252 HTML pages, 666 tables and 16,877 links; every published table row carries a source link.
- `python3 scripts/check_links.py` — pass: 5,762 local references, no broken internal links.
- `python3 scripts/validate_data.py` — pass: every data row carries official-source citations; flagged values blank.
- `python3 tests/check_data.py` — pass: 6 result files consistent, 32/32 teams verified.
- `python3 tests/check_derived.py` — pass: strict JSON, 52 recorded independent checks with 0 mismatches, 32/32 teams reconciled for 2020, generated pages linked.
- `python3 requirements-desk/scripts/verify.py` — pass: 14 pages, 27 tables, 1,090 links, 74 requirements, 6 registers; requirement summary {partial 37, blocked 16, verified 13, not started 8}.
- `python3 line-desk/scripts/build_site.py --check` and `python3 line-desk/scripts/verify.py` — pass: 15 pages byte-identical to a fresh render; 16 registers, blank policy, correlations recomputed.
- `python3 price-desk/scripts/verify.py` — pass: 20,504 checks, 0 errors. `python3 review-board/scripts/verify_all.py` — pass: 131 checks across 14 pages. `python3 decision-desk/scripts/verify_all.py` — pass (50 sources, 19 flags). `python3 verify-hub/scripts/verify.py` — pass (152 data rows, 9 pages, 181 table rows).
- `python3 scripts/build_site.py --check` and `python3 requirements-desk/scripts/build_site.py --check` — pass: deterministic renders reproduced byte-identically.

The previous session record (2026-11-15: 232 pages, 584 tables, 13,560 links; 4,637 references) is superseded by the counts above; the historical audit remains at [docs/REPOSITORY_STATUS_2026-11-15.md](docs/REPOSITORY_STATUS_2026-11-15.md).

GitHub Pages status `built` was confirmed via the GitHub API on 2026-11-19 for the legacy `main` root build. The merge that preceded it (PR #145, commit `1d56d09`) is the latest state this verification covers; the integration PR that follows this session will be recorded in `COORDINATION.md` with its own deploy confirmation.

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
