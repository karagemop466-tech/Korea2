# Executive summary — review of the NFL line-origination system, 2026-11-13

Scope of this review: the 89 suggestion rows and 114 decision-readiness rows published by seven sibling hubs, the
repository's committed analytical registers, the official Week 10 injury report captured today, and the source
trail behind both. Nothing in this document is an implementation order; every proposal is recorded as
`proposed — awaiting owner`. Site: `review-board/index.html`.

---

## 1. Bottom line

1. **Nothing in this repository qualifies as a betting strategy, and the site says so.** Across every hub
   leaderboard this review could read, `approved_count` and `points_awarded` are 0. The gates, not the returns,
   decide qualification — which is the correct design and the reason the scoreboard is empty.
2. **The market beats the model the site builds.** Root walk-forward figures read from
   `data/derived/model.json`: model MAE 9.70 against market MAE 9.70-ish on spreads (the registers publish the
   close-beat comparison twice, 10.38/10.39 vs 9.70/10.25 across the two evaluation windows), and the
   incremental-information coefficient is −0.02 with p = 0.85. The model adds nothing beyond the closing line.
3. **One headline statistic on the live site is an arithmetic identity.** The pooled ATS test reports
   n = 2,000 and rate 50.0% at p = 1.0 because it counts both sides of the same line twice; the honest
   one-observation-per-game figure in the same directory is home cover 48.91% (CI 47.73–50.09, p = 0.073).
   Flag RB-04.
4. **Prop profitability is unmeasurable with what is committed.** `data/derived/props.json` states its own
   limitation: accuracy is measured, prices are not, so no prop ROI claim in any hub is verifiable. Flag RB-10.
5. **Parlay legs are not independent, and the hubs disagree about by how much.** Five quantities are published
   with different values under one label across 144 registers, including the QB↔WR1 pair, where the label is
   shared and the definition is not.
6. **Availability is only knowable in the moment it is published.** Today's Friday report carries 213 rows, 66
   Out designations across 28 clubs and 14 games; the midweek sibling capture carries 6 designated players.
   Statuses arrive with the report and are not carried forward, so an archive — not a re-read — is the only
   backtestable form of this data.
7. **The weekly report is not an absence ledger.** The same day's official news reports a Baltimore quarterback
   out 6–10 weeks after thumb surgery; the Week 10 report prints no quarterback row for that club at all, and
   eight clubs printed "No Injuries Reported" midweek while their own news said otherwise. Flags RB-03, RB-05.
8. **Depth stays blank, by policy.** No official source publishes a depth string; club charts are labelled
   unofficial, several are stale, some omit a backup at a position where a starter is out. The two
   string-depth columns on `pages/depth.html` are blank for all 28 clubs and `data/flags.json` says why.
9. **The repository's own shape is now a decision problem.** 25 directories carry generated content and 17 of
   them are standalone websites; the shared navigation exposes 30 targets, so 18 directories — this hub among
   them — are reachable only by typing a path, and the label "Suggestions hub" points at two different pages.
   191 generated pages, and 12 decisions that up to seven hubs proposed independently. Cluster T11
   (reproducibility/CI/provenance, 7 hubs) and T10 (site architecture) are cheap and unblock the rest.

## 2. The path, in five decisions

Full detail, options and exit tests on `review-board/pages/path.html`; cluster counts from
`review-board/data/queue.json`.

| Phase | Decision | Settles | Cost | Exit test |
|---|---|---|---|---|
| P1 | Approve the review rules: one decision per cluster, one owner, nothing implemented by the session that proposed it | T12 | hours of review, no code | every cluster carries approve/reject/modify and a date |
| P2 | Adopt one gate set, one quantity vocabulary and one stamp, enforced by CI | T11, T07 | one workflow plus edits to each hub's build | a rebuild into a clean checkout produces byte-identical pages, and every published figure resolves to a committed file and an as-of date |
| P3 | Start the availability archive: capture Wednesday, Friday, Saturday, Sunday reports into committed files with the retrieval date | T03 | a scheduled fetch and storage, no analysis | the following week's delta recomputes from committed files alone, with no live read |
| P4 | Settle one leaderboard and reward design, with nothing awarded until gates pass, and rewrite every tier page against it | T09, T06, T08 | small, but it touches every hub's public surface | three inconsistent schedules collapse into one, no page implies cash, and parlay pricing cannot pass without a stability check |
| P5 | Then, and only then, build signals on the archived data: one hypothesis, one test, one falsifier per signal | T01, T02, T04, T05 | months | no signal ships as a tip; each links its measurement and its failure mode |

Ordered so each phase needs only what the previous one produced. Every phase is cheap to reverse and expensive
to skip.

## 3. Review queue — all twelve clusters

Ranked by independent agreement across hubs, then priority votes, then what else it unblocks.

| Rank | Decision | Hubs | Rows |
|---|---|---|---|
| 1 | T11 Reproducibility, CI and provenance | 7 | 10 |
| 2 | T03 Injury and availability data | 6 | 14 |
| 3 | T07 Gates and rigour | 6 | 15 |
| 4 | T10 Site architecture and integration | 5 | 7 |
| 5 | T06 Correlation and parlay pricing | 5 | 5 |
| 6 | T12 Review workflow and disclosure | 5 | 8 |
| 7 | T02 Price data and timestamps | 4 | 6 |
| 8 | T04 Depth and starter definition | 4 | 6 |
| 9 | T09 Leaderboard and rewards | 4 | 4 |
| 10 | T01 Execution, jurisdiction and tax | 3 | 4 |
| 11 | T05 Origination model direction | 3 | 3 |
| 12 | T08 Skill versus luck and sizing | 2 | 3 |

## 4. Signal programme

Seven designs, each with a hypothesis, required inputs, a test, a falsifier and its blocker
(`review-board/pages/signals.html`). Statuses are honest about what cannot start today:

- **SIG-01 availability shock** — blocked on a citable replacement definition (T04) and on the archive (T03);
  the current-slate test it would have used is falsified before it starts, because a long-term absence never
  appears in the weekly report.
- **SIG-02 market-versus-model** — testable now against the root model output, and today's answer is negative.
- **SIG-03 line movement under a shared public constraint** — blocked on price history and on a game-level
  join (T02).
- **SIG-04 correlated legs** — partially testable; the accuracy half runs, the profitability half cannot, and
  the coefficient each hub quotes was measured on a different leg definition than the one being bet.
- **SIG-05 situational splits** — testable but weak by default: split-sample floors are not met.
- **SIG-06 schedule and rest asymmetry** — testable from committed data, and the international-slot variant is
  confounded with travel.
- **SIG-07 market microstructure** — not runnable from this repository at all.

Twelve gates, ten of which exist in some hub's implementation and two (depth/opponent adjustment,
correlation stability) that exist because the data cannot currently satisfy them
(`review-board/pages/gates.html`). Ten gate IDs are reused across hubs for different tests — flag RB-06.

## 5. Competition

Scoring ranks on skill and sample, not on return: calibration and Brier against the de-vig market as the primary
metric, accuracy, sample floor, stability across seasons and split halves, realised volatility as an over-fit
detector; ROI is reported and never promotes an entry on its own. Six anti-luck controls target failures
already documented in this repository (pooled-ATS arithmetic, variant fishing, single-season spikes, repriced
parlay legs). Tier 0 reports an under-sampled entry as "insufficient" rather than "rejected"
(`review-board/pages/competition.html`).

State: 0 of 9 root entries approved, 0 of 16 skill-hub entries qualified, 0 pool points awarded, and no funded
prize anywhere. Three inconsistent reward schedules are published at once, one of which lists $100,000 prizes
against an empty `cash_funding` field — flag RB-08.

## 6. Current-slate snapshot, 2026-11-13

Week 10 report: 213 transcribed rows, 28 clubs, 14 games in 7 kick-off slots; 66 Out, 10 Doubtful,
84 Questionable, 53 rows carrying a practice mark only (`review-board/pages/injuries.html`).

- Two starting quarterbacks are Out for Sunday (Seattle, Minnesota) and a third club's starter is out on a
  long-term injury the weekly report does not list at all.
- The Monday game carries **no** game statuses in the Friday report: 21 rows, all practice-only. Any model that
  treats a missing row as availability is wrong about that game before it starts.
- Offence/defence split of Out designations is computed per club on `pages/depth.html`; the two string-depth
  columns beside it are blank for all 28 rows.
- Day-over-day: the midweek sibling register listed 254 rows with 6 designations; this capture holds 160
  rows-with-a-status view of the same slate, 31 players appear who were absent midweek, 123 changed — that is
  what a live feed looks like, and it is why the archive in P3 matters more than any new model.

## 7. What is missing and how to find it

Eight information gaps (`review-board/pages/questions.html`), each naming what we have, what is missing, the
discovery route and who must answer: prop price history (licensing, not code), depth strings (a policy decision,
not a scraping task), a jurisdiction determination for any real-market feature (owner plus counsel), a
reachable official injury-report policy document (the cited path 404s — flag RB-13), independent recomputation
of published numbers (a CI task, cluster T11), a canonical gate set (owner decision), a funded prize if one is
ever intended (owner), and an archive of point-in-time availability (a scheduled fetch).

## 8. Flags

Seventeen items are on `review-board/pages/flagged.html` — irregularities, contradictions between official
surfaces, method defects and governance conflicts, each with what was found, how it was checked and the action
for the owner — plus eight surfaces deliberately left blank with the reason. None blocks the deploy; every one
of them is something a reader would otherwise have to discover alone.

## 9. Provenance

Twelve register entries on `review-board/pages/sources.html`: four official NFL pages read today, two NFL
Football Operations pages (one reachable, one 404 and marked as such), the league's injury hub, three committed
files in this repository, one third-party feed carried from sibling registers, and this hub's own programme
register for material that is authored rather than measured. Rows marked `carried` were not re-read by this
session and say so on every table where they appear.

*Research, measurement and review only — not betting advice, not a tip sheet, and no funded prize.*
