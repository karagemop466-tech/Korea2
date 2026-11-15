# Live-site readiness audit — 2026-11-15

## Bottom line

GitHub Pages is currently built from `main` at `5da59c96072a7dd856a55a45ac3d7ce754e01907` (Pages API checked 2026-11-15 18:40:38 UTC). The repository's local structural and-link checks pass. That establishes that a static site was published, **not** that current NFL data or every displayed number is official, complete, or suitable for a wager. The public root page itself says its model snapshot is through 2026-11-01 and not current to the live slate. The most important readiness blockers remain official timestamped prices, full point-in-time availability/depth evidence, one canonical model/leaderboard, and a complete official results corpus.

This is a dated, repository/GitHub-state audit only. I did not fetch NFL, NIST, NWS, venue or operator pages and do not claim new source verification. For NFL-facing facts and evidence, follow the row-level sources and prior-session verification records linked below. Internal calculations and repository records are not official-source evidence.

## Site state checked

| Check | Observed result | Decision meaning | Evidence |
|---|---|---|---|
| GitHub Pages configuration | `status=built`, legacy build, source `main:/` | The public site is deployed; this alone does not certify its data freshness or correctness. | [Pages API](https://api.github.com/repos/karagemop466-tech/Korea2/pages) |
| Latest Pages build | `status=built`, commit `5da59c96072a7dd856a55a45ac3d7ce754e01907`, updated `2026-11-15T18:40:38Z` | Confirms deployment of that commit, not any unmerged pull request. | [Latest Pages build](https://api.github.com/repos/karagemop466-tech/Korea2/pages/builds/latest) |
| Root freshness notice | The checked-in homepage states “Research snapshot through 2026-11-01 — not current to the live slate.” | The homepage itself discloses that its model outputs are stale for current-week decisions. Keep current-week bets disabled until updated. | [Root homepage source](../index.html); [published homepage](https://karagemop466-tech.github.io/Korea2/) |
| Root navigation | The sidebar has 30+ destinations, including several sibling dashboards and repeated suggestion/decision links. | This conflicts with the requested simple dashboard experience; consolidate navigation only after the owners of shared root files integrate their work. | [Root homepage source](../index.html) |
| Root analysis data provenance | Homepage findings cite nflverse community-maintained data, which the page expressly says is not an NFL-published feed. | Those derived numbers may support exploratory research, but must not be described as official NFL facts. | [Root homepage source](../index.html); [data provenance](../data/PROVENANCE.md); [NFLverse repository](https://github.com/nflverse/nflverse-data) (community-maintained, not official NFL) |
| Local structural checks | `python3 tests/check_site.py`: 232 pages, 584 tables, 13,560 links; pass. It notes 33 pages outside the published build do not carry per-row source columns. | Link integrity and HTML structure pass; neither checks external URL validity, official-source status, or numerical truth. | [Site checker](../tests/check_site.py) |
| Local internal-link check | `python3 scripts/check_links.py`: 4,637 local references; pass. | No broken local links were detected in this checkout. | [Link checker](../scripts/check_links.py) |

## Integration readiness at the audit timestamp

Open pull requests are not part of the currently deployed `main` build. These statuses are an API snapshot taken at 2026-11-15 18:42 UTC; GitHub checks and mergeability can change. Do not infer any result in a pull request is live until the merge and a matching Pages build are confirmed.

| PR | Scope indicated by title | API state when checked | Review gate / action |
|---|---|---|---|
| [#126](https://github.com/karagemop466-tech/Korea2/pull/126) | Reviewer decision-readiness register | Mergeable; checks were still queued/in progress in the API response. | Wait for all required checks to finish successfully; ensure it remains an audit register rather than a claim that the listed evidence exists. |
| [#125](https://github.com/karagemop466-tech/Korea2/pull/125) | Coordination record for PR #124 merge and deployment | Mergeable; checks were still in progress. | It changes documentation/coordination; confirm checks and merge as an ordinary documentation change if the owning integration session does so. |
| [#112](https://github.com/karagemop466-tech/Korea2/pull/112) | Decision Arena: prices, results, line order, strategy competition | Conflicting with `main`; no checks were reported in the queried status response. | Do not merge until rebased/integrated, checks pass, and the new store's evidence grades are reconciled with existing Price Desk and official-only Price Store records. The PR body itself describes many market snapshots as lacking timestamps and does not claim them as official open/close quotes. |
| [#109](https://github.com/karagemop466-tech/Korea2/pull/109) | Signal Desk fixes and regression tests | `UNSTABLE`; several checks reported failures, others succeeded. | Re-run after reconciling with current `main`; require all required checks green. |
| [#102](https://github.com/karagemop466-tech/Korea2/pull/102) | Requirements traceability, questions, suggestions and flags | Conflicting with `main`; checks included failures and successes. | Rebase and review data/page overlaps with later requirement/readiness work; require all checks green. |
| [#99](https://github.com/karagemop466-tech/Korea2/pull/99) | Review Board provenance and column-mismatch checks | Conflicting with `main`; checks included failures and successes. | Rebase and regenerate only via the Review Board's documented generator; require all checks green. |
| [#97](https://github.com/karagemop466-tech/Korea2/pull/97) | Root integration, nav cleanup and site-review queue | Conflicting with `main`; checks included failures and successes. | Resolve shared-site overlap with PR #93 and current main; verify generated pages and every inbound link before merge. |
| [#93](https://github.com/karagemop466-tech/Korea2/pull/93) | Site-wide source/link dashboard and root navigation | Conflicting with `main`; checks included failures and successes. | Resolve root-navigation overlap with PR #97 and current main; keep unverified-source labels and rerun the full site/link checks. |

The cited states are from `gh pr view` / the open-PR API at the time of this audit. This document does not merge, close, or modify any of those PRs and does not replace their owners' coordination logs.

## Decision-readiness findings

| Decision | Current evidence in the committed repository | Missing evidence / measurable gate before use | Manual-review source |
|---|---|---|---|
| Can the site recommend a current NFL bet? | No. The root homepage says the model snapshot is through Nov 1, 2026; the site presents research outputs, not live verified execution. | A fresh, point-in-time schedule, prices, results feed, and availability capture for the exact slate; canonical model run and successful validation before kickoff. No current bet should be produced from the stale root snapshot. | [NFL schedule](https://www.nfl.com/schedules/); [root flagged page](../pages/flagged.html) |
| Are official opening/closing lines stored? | Prior repository records report `price-store/data/snapshots.csv` has 0 rows; other price records distinguish third-party/unverified archives from official quotes. | Authorized source and policy, quote timestamp and immutable capture per market, complete coverage thresholds, source hash, and audit/replay tests. | [Price Store](../price-store/data/snapshots.csv); [NFL–Genius Sports announcement](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports) |
| Can player replacement string/depth be determined? | Prior records report 0 verified replacement names/string tiers in the Line Desk sample; Game Books show starters and inactive evidence, not an official depth-string number. | Verify a source route for all 32 clubs; preserve shared/empty slots; reconcile roster transactions; use only published depth ranks or label rank unknown. A complete sweep and raw, timestamped snapshots are gates, not assumptions. | [Line Desk depth record](../line-desk/pages/depth.html); [NFL injury report](https://www.nfl.com/injuries/league/2026/REG10); [NFL Game Books](https://www.nfl.com/gamecenter/) |
| Can strategies be ranked or rewarded? | Prior session records report zero strategies approved and unfunded rewards; several repositories have non-identical candidate sets/ranking definitions. | Freeze a single registration/leaderboard policy, eligibility divisions and controls; require chronological holdouts, proper scores, uncertainty and multiplicity handling; validate prospective CLV/ROI from permitted prices; fund and publish any reward terms before competition. | [Root leaderboard](../pages/leaderboard.html); [Line Desk leaderboard](../line-desk/pages/leaderboard.html); [Price Desk leaderboard](../price-desk/pages/leaderboard.html) |
| Can parlays/prop combos be priced? | Existing official-only correlations concern team standings, while other player-level calculations use community-maintained data; marginal correlations are not a validated joint probability. | Validate joint probabilities directly on held-out games with sample size, uncertainty, calibration, and operator push/void rules. A combo remains ineligible until that gate passes. | [Line Desk correlations](../line-desk/pages/correlations.html); [NIST correlation intervals](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm) |

The source URLs in this table are supplied for manual review. Their presence does not establish that this audit opened them today or that each linked page contains every requested data field.

## Recommendations for the next integration owner

1. Keep the main site visibly **research-only / stale-snapshot** until the current-slate data and source checks are complete. Avoid a “Pipeline live” badge that could be read as a live NFL data feed; the current checked-in homepage does show that label while also displaying the stale date.
2. Merge only after each open PR is rebased against current `main`, required checks pass, and overlapping file ownership is reconciled. The site can be live while many review PRs remain open; “live” must not be confused with “all requirements complete.”
3. Keep the decision-readiness register and the Flags page explicit about unknowns. Do not promote proposed gates to observed facts and do not fill blanks by inference.
4. Do not combine counts, ranks or results across the root analysis, Line Desk, Price Desk, Price Store and Decision Arena unless a canonical shared schema and reconciliation test explicitly justify it.
5. Before enabling model outputs for current decisions, resolve the canonical originator discrepancy and add automated freshness alarms for each data source.

## Verification record

- Checkout/branch inspected: `arena/8e7c6dd3-korea2` at base commit `5da59c96072a7dd856a55a45ac3d7ce754e01907`; the only local change during the audit was the coordination claim and this report.
- `python3 tests/check_site.py`: pass (232 pages, 584 tables, 13,560 links; 33 non-root pages lack a per-row source column).
- `python3 scripts/check_links.py`: pass (4,637 local references).
- GitHub Pages API: `built`, commit `5da59c96072a7dd856a55a45ac3d7ce754e01907`, updated 2026-11-15 18:40:38 UTC.
- Open PR list/status: queried via GitHub CLI at approximately 18:42 UTC; statuses can change after this snapshot.
- No NFL, NIST, NWS or operator source was freshly fetched in this audit. No numeric model outputs were recomputed, and no bet, strategy, prize or source claim is certified by this report.
