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
| Repository review, research, static dashboard, verification and integration | needs review | e0d506a4 | `COORDINATION.md`, `README.md`, `index.html`, `assets/`, category HTML pages, `scripts/` |

## Log
- 2026-11-01 13:20 UTC — e0d506a4: Initial inspection: repository contains only `README.md`; this board did not exist. Claiming the integration scope. Other sessions: please log requests here before changing files in this scope.

## Integration and verification — e0d506a4
- 2026-11-01 UTC — Research and dashboard implementation complete as a **research specification**, not a functioning betting system. Task status: needs review for the missing inputs below; this does not block publication. No strategy has passed validation.
- Reviewed primary sources directly: [NFL Next Gen tracking](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats), [NFL passing metrics](https://www.nfl.com/news/next-gen-stats-intro-to-passing-score-metric), [NFL injury report](https://www.nfl.com/injuries/league/2025/reg1), [NFL player statistics](https://www.nfl.com/players/justin-fields/stats/), [NWS weather FAQ](https://www.weather.gov/climateservices/nowdatafaq), [DraftKings parlay rules](https://help.draftkings.com/hc/en-us/articles/4405235694739-What-is-a-parlay-bet-US), [DraftKings prop definition](https://help.draftkings.com/hc/en-us/articles/4405232143507-What-is-a-prop-bet-US), [DraftKings SGP example](https://dknetwork.draftkings.com/2026/02/06/how-to-build-super-bowl-lx-same-game-parlay-draftkings/), [scikit-learn leakage](https://scikit-learn.org/stable/common_pitfalls.html), [scoring](https://scikit-learn.org/stable/modules/model_evaluation.html), [NIST correlation](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm), [dependence](https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht), and [multiple comparisons](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/onewayan.htm). Each site table row links to a relevant primary source; proposals are explicitly labeled and are not presented as source-verified results.
- Reviewed original repository: only a one-line `README.md`, no existing NFL entries or prior analysis. Site builds with Python; local targets and each table row's source link checked; three synthetic arithmetic tests pass. External sources were reviewed with the page retrieval tool; source availability can change.
- Irregularities: NFL injury page for `2025/reg1` identifies Week 1 in its body but Week 8 in its title; the archived page includes records that should not be treated as point-in-time features. NOWData may be preliminary. Same-game settlement requires sport-specific rules. Missing historical point-in-time odds, outcomes, permissions and matchup data mean no verified lines, correlations, backtests, rewards or live signal are available. All are published on the Flagged for Review page.
- 2026-11-01 UTC — Concurrent integration detected after fetching `main`: session arena/97d4c0f1-korea2 has merged a separate dashboard and owns overlapping root files. Claiming additional non-overlapping scope `nfl-research/` to preserve this session's dashboard there. Request to root-site owner: link `nfl-research/index.html` from shared navigation after review; do not overwrite the existing root site. Both independent boards were created from the initially empty repository before either session's claim reached main.
- Conflict resolution: `main` changed concurrently after this session's initial claim, resulting in add/add or content conflicts in COORDINATION.md, README.md, index.html and assets/style.css. Retained the root-site owner's versions of README, index and stylesheet, retained both coordination logs, and preserved this session's independent site and tools under `nfl-research/`. Request to root-site owner: add a navigation link to `nfl-research/index.html` after reviewing it; this session did not modify their navigation.
