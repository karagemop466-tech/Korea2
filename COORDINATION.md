# Coordination board

| Task | Status | Owner | File scope |
|---|---|---|---|
| Research, build, verify and integrate NFL dashboard | needs review | arena/97d4c0f1-korea2 | COORDINATION.md, README.md, index.html, assets/, pages/, .github/workflows/, tests/ |

## Session log
- 2026-11-01: Repository reviewed: only README.md existed; no prior coordination board. Integration session claimed the scope above. The Arena-assigned branch is fixed; separate session branches cannot be created by this session.
- 2026-11-01: Integration built as a dependency-free static site. Official source statements checked against [NFL tracking](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats/), [NFL Pro FAQ](https://support.nfl.com/hc/en-us/articles/35869706651156-NFL-Pro-FAQ-s-and-Answers), [NFL distribution announcement](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports), [Big Data Bowl](https://edge-operations.nfl.com/programs-initiatives/innovation/big-data-bowl), and [NIST](https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm). Proposals and formulas are explicitly labeled as such, not attributed as source-verified strategies. Each table row links an official source for context; local links and source-link presence checked by tests/check_site.py.
- Irregularities: no official historical odds/outcome archive, audited strategy results, measured correlations, funded prize, or verified betting access/license. The external source fetch for a historical NFL finalists article returned only a shell, so its prize claim was removed and replaced with a verified competition overview. These items are published on Flagged for Review. The site's results are a research framework, not a completed quantitative validation.
- Initial claim push: remote session branch did not exist; rebased onto main before creating it. No conflict occurred.
- Pull request: https://github.com/karagemop466-tech/Korea2/pull/2. Merge and deployment confirmation pending. Quantitative research remains unverified as described on the review page.
