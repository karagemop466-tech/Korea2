# Coordination board

| Task | Status | Owner | File scope |
|---|---|---|---|
| Research, build, verify and integrate NFL dashboard | needs review | arena/97d4c0f1-korea2 | COORDINATION.md, README.md, index.html, assets/, pages/, .github/workflows/, tests/ |

## Session log
- 2026-11-01: Repository reviewed: only README.md existed; no prior coordination board. Integration session claimed the scope above. The Arena-assigned branch is fixed; separate session branches cannot be created by this session.
- 2026-11-01: Integration built as a dependency-free static site. Official source statements checked against [NFL tracking](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats/), [NFL Pro FAQ](https://support.nfl.com/hc/en-us/articles/35869706651156-NFL-Pro-FAQ-s-and-Answers), [NFL distribution announcement](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports), [Big Data Bowl](https://edge-operations.nfl.com/programs-initiatives/innovation/big-data-bowl), and [NIST](https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm). Proposals and formulas are explicitly labeled as such, not attributed as source-verified strategies. Each table row links an official source for context; local links and source-link presence checked by tests/check_site.py.
- Irregularities: no official historical odds/outcome archive, audited strategy results, measured correlations, funded prize, or verified betting access/license. The external source fetch for a historical NFL finalists article returned only a shell, so its prize claim was removed and replaced with a verified competition overview. These items are published on Flagged for Review. The site's results are a research framework, not a completed quantitative validation.
- Initial claim push: remote session branch did not exist; rebased onto main before creating it. No conflict occurred.
- Pull request: https://github.com/karagemop466-tech/Korea2/pull/2. Merged on 2026-11-01 (merge commit 597e815d6361e5419653d9773f945d90bab1050c). GitHub Pages deployment run https://github.com/karagemop466-tech/Korea2/actions/runs/41310946433 succeeded. Quantitative research remains unverified as described on the review page.
- Deployment warning: GitHub-managed Pages build reported a Node.js 20 action deprecation warning; the deployment succeeded. Monitor the managed workflow.

## Independent session e0d506a4 / non-overlapping research

| Task | Status | Owner | File scope |
|---|---|---|---|
| Additional research brief and arithmetic checks | needs review | arena/e0d506a4-korea2 | nfl-research/ |

# Coordination board

Sessions must claim non-overlapping file scopes here before starting work. The Arena session is restricted to its assigned branch, `arena/e0d506a4-korea2`.

| Task | Status | Owner | File scope |
| --- | --- | --- | --- |
| Repository review, research, static dashboard, verification and integration | needs review | e0d506a4 | `nfl-research/` (original overlapping claim superseded; see log) |

## Log
- 2026-11-01 13:20 UTC — e0d506a4: Initial inspection: repository contains only `README.md`; this board did not exist. Claiming the integration scope. Other sessions: please log requests here before changing files in this scope.

## Integration and verification — e0d506a4
- 2026-11-01 UTC — Research and dashboard implementation complete as a **research specification**, not a functioning betting system. Task status: needs review for the missing inputs below; this does not block publication. No strategy has passed validation.
- Reviewed primary sources directly: [NFL Next Gen tracking](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats), [NFL passing metrics](https://www.nfl.com/news/next-gen-stats-intro-to-passing-score-metric), [NFL injury report](https://www.nfl.com/injuries/league/2025/reg1), [NFL player statistics](https://www.nfl.com/players/justin-fields/stats/), [NWS weather FAQ](https://www.weather.gov/climateservices/nowdatafaq), [DraftKings parlay rules](https://help.draftkings.com/hc/en-us/articles/4405235694739-What-is-a-parlay-bet-US), [DraftKings prop definition](https://help.draftkings.com/hc/en-us/articles/4405232143507-What-is-a-prop-bet-US), [DraftKings SGP example](https://dknetwork.draftkings.com/2026/02/06/how-to-build-super-bowl-lx-same-game-parlay-draftkings/), [scikit-learn leakage](https://scikit-learn.org/stable/common_pitfalls.html), [scoring](https://scikit-learn.org/stable/modules/model_evaluation.html), [NIST correlation](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm), [dependence](https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht), and [multiple comparisons](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/onewayan.htm). Each site table row links to a relevant primary source; proposals are explicitly labeled and are not presented as source-verified results.
- Reviewed original repository: only a one-line `README.md`, no existing NFL entries or prior analysis. Site builds with Python; local targets and each table row's source link checked; three synthetic arithmetic tests pass. External sources were reviewed with the page retrieval tool; source availability can change.
- Irregularities: NFL injury page for `2025/reg1` identifies Week 1 in its body but Week 8 in its title; the archived page includes records that should not be treated as point-in-time features. NOWData may be preliminary. Same-game settlement requires sport-specific rules. Missing historical point-in-time odds, outcomes, permissions and matchup data mean no verified lines, correlations, backtests, rewards or live signal are available. All are published on the Flagged for Review page.
- 2026-11-01 UTC — Concurrent integration detected after fetching `main`: session arena/97d4c0f1-korea2 has merged a separate dashboard and owns overlapping root files. Claiming additional non-overlapping scope `nfl-research/` to preserve this session's dashboard there. Request to root-site owner: link `nfl-research/index.html` from shared navigation after review; do not overwrite the existing root site. Both independent boards were created from the initially empty repository before either session's claim reached main.
- Conflict resolution: `main` changed concurrently after this session's initial claim, resulting in add/add or content conflicts in COORDINATION.md, README.md, index.html and assets/style.css. Retained the root-site owner's versions of README, index and stylesheet, retained both coordination logs, and preserved this session's independent site and tools under `nfl-research/`. Request to root-site owner: add a navigation link to `nfl-research/index.html` after reviewing it; this session did not modify their navigation.

- Integration PR: https://github.com/karagemop466-tech/Korea2/pull/4. After merging main, a regular `pull --rebase` attempted to replay the other session’s commits and conflicted on the board; the rebase was aborted without discarding work. `pull --rebase=merges` then succeeded, preserving the merge and both histories.


## Independent session arena-1955d40e / additional research desk

# Coordination board

Session ID: arena-1955d40e (integration session; branch name fixed by environment).

| Task | Status | Owner | File scope |
|---|---|---|---|
| Repository review, source research, strategy framework, site integration and publication | in progress | arena-1955d40e | COORDINATION.md, README.md, site files, .github/workflows/*, scripts/* |

No other claims were present when this board was created. Other sessions should avoid this scope and record requests here. Last claim: 2026-11-01 UTC.

## Integration log — 2026-11-01 UTC

- Repository review: initial `README.md` contained only `# Korea2`; no existing data, models, tasks, or site. No parallel claims existed at intake. Environment requires the fixed `arena/1955d40e-korea2` branch rather than session-named branches.
- Claim push: the requested branch did not yet exist on the remote, so the initial `pull --rebase` from that branch failed; rebased against `origin/main`, then pushed the claim. No conflict occurred.
- Research verification: checked the NFL's [Bo Nix career table](https://www.nfl.com/players/bo-nix/stats/career), [Hurts Super Bowl report](https://www.nfl.com/news/eagles-qb-jalen-hurts-named-super-bowl-lix-most-valuable-player), and [Kelce Super Bowl report](https://www.nfl.com/news/travis-kelce-non-factor-in-chiefs-super-bowl-lix-loss-we-haven-t-played-that-bad-all-year) against each displayed extract. Checked [NFL injury report](https://www.nfl.com/injuries/league/2026/reg7), [scikit-learn leakage](https://scikit-learn.org/stable/common_pitfalls.html), [scoring](https://scikit-learn.org/stable/modules/model_evaluation.html), [time splitting](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [NWS API](https://www.weather.gov/documentation/services-web-api), and [NIST correlation/forecast caution](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=921446). The source links on proposed methods are context, not endorsement of proposed gates or results.
- Irregularities: the injury page title says Week 8 but its in-page heading says WEEK 7 and URL says reg7. Official historic odds, as-of snapshots, correlations, trained models and performance evidence were not obtained. All corresponding values or rankings are blank or pending. Items are published on Flagged for Review.
- Built six static pages and ran `python3 scripts/check_site.py`: local links/assets exist, generated pages match source, and every table row links to an official/context source. External source content was reviewed individually using web retrieval; no claim of automated external link checking is made.
- Site work is complete for this research snapshot; the broad task remains in progress until the pull request and deployment result are recorded. No strategy is represented as validated or live.
- Integration pull request: https://github.com/karagemop466-tech/Korea2/pull/5 — merge and deployment pending.
- Concurrent integration discovered when PR #5 could not merge: sessions arena/97d4c0f1-korea2 and arena/e0d506a4-korea2 independently claimed overlapping scopes from the initially empty repository, and their work reached main first. Their root dashboard and `nfl-research/` scope must not be overwritten. This session is relocating its independent dashboard and tools to `research-desk/`, and requests that the root-site owner add a link to it after review. The integration task scope is now `research-desk/` and this log in COORDINATION.md. Reconciling conflicts while preserving both published sites and logs.
- Merge conflict resolution: retained main's root README and dashboard, and retained both versions of the coordination board in full. The independently built dashboard was moved to `research-desk/` before merging; no other session's files were overwritten. This claim is needs review because inputs and quantitative validation remain missing. PR #5 remains the integration PR for this independent research addition.
