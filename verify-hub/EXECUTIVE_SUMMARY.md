# Executive summary — Verify Hub (cross-lab verification & decision hub)

**Session:** arena/f1123a1a-korea2  |  **As of:** 2026-11-12  |  **Site:** verify-hub/index.html

Every number below is read from committed JSON by verify-hub/scripts/build_site.py; the HTML twin
of this file is verify-hub/pages/executive.html. Values no official source confirms are blank and
published on the Flagged page.

## 1. Bottom line

- The repository is a complete measurement apparatus: five gate systems, four labs with walk-forward results, an independent recomputation (49 checks, 0 disagreements) and official-source reconciliations (32/32 teams for 2020 and 2026 at their snapshot dates).
- No strategy has passed validation anywhere: root 0 of 9, skill-lab 0 of 16, quant-lab 0 of 21, origination-lab 0 eligible, pipeline 0 of 5. Nothing here should be bet.
- The closing market beats the model (MAE 9.71 vs 10.39; incremental coefficient -0.019, p = 0.881; Brier skill -0.038).
- Same-game parlay legs are strongly correlated (QB-WR1 r = 0.56-0.61; 4-leg joint 11.1% vs 5.7% product); independent leg pricing is wrong and favors the bettor, which is why books reprice SGPs.
- The injury/depth requirement is half-satisfiable from official data today: the weekly injury report is official and live (verified Week 10 2026), but depth strings (1st-4th) are not published by the league (404 verified).

## 2. What this hub adds

- A line-by-line cross-lab claims audit: 45 published claims, each with its evidence class (10 verified against official sources on 2026-11-12, 21 verified against committed data, 6 blank/unverified, 8 irregularities).
- A decision-readiness register: 20 questions with Have/Partial/Missing status, verified answers where they exist, and a discovery suggestion for every gap.
- A suggestion review queue (14 proposals) with trade-offs and a recommended path per proposal - nothing is implemented until a reviewer approves.
- One cross-lab consolidation of strategies, gates, correlations, luck metrics and reward schedules, with every lab's window and definition printed next to its numbers.

## 3. Decisions the owner must make before anything is implemented

- SG-01: declare one canonical site (recommended: root Line Lab) and treat the eight sibling hubs as archives.
- SG-02: adopt one injury & depth tracker design (official report + inferred usage tiers, blanks kept).
- SG-03/SG-04: adopt one gate catalog and one reward schedule (paper until funding is decided).
- Q-05/Q-06: decide whether to acquire a licensed historical odds feed - without it there can be no prop ROI and no CLV, ever.

## 4. Verification performed on 2026-11-12

- NFL.com 2026 standings page: all 32 records read; repo snapshots reconcile at 2026-11-01/02 and drift with Week 9 is documented team by team.
- NFL.com Week 10 injury report: live; team records inside it match the standings page; per-team rows transcribed as the verified sample on the Injuries page.
- nflverse release metadata via the GitHub Releases API: 28/31 manifest assets byte-match upstream; 3 rolling 2026 assets are newer upstream (expected, flagged).
- Two cited official URLs confirmed dead (operations.nfl.com injury policy; nfl.com club depth-chart) and recorded as irregularities with blank values.
- Full local suite green: tests/check_site.py, tests/check_derived.py, scripts/check_links.py, scripts/validate_data.py, audit/check_site.py, plus this hub's verify.py and unit tests.

## Status rules used throughout this hub

- verified-official — checked against an official publisher on 2026-11-12 (link in the row).
- verified-internal — read from committed repo data and matched to the published page; computed from third-party feed extracts; no official publisher of the statistic exists.
- unverified-blank — cannot be confirmed; value left blank; published on the Flagged page.
- irregularity — inconsistency, dead source or quotation hazard found by the audit.

Research and measurement, not betting advice. 0 strategies approved. Reward schedules are paper.
