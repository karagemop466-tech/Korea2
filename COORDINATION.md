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
