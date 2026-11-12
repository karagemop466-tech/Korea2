# Executive summary — Decision Desk (injuries, decisions, competition state)

**Session:** `arena/aa66ed82-korea2` · **Branch:** `arena/aa66ed82-korea2` · **Captured:** 2026-11-12
**Data as of:** injury/depth snapshot 2026-11-12 (Week 10 Wednesday); root results snapshot 2026-11-01 (Week 9).

## Bottom line

| Question | Answer | Evidence |
|---|---|---|
| Should any strategy receive allocation today? | **No** — 0 of 108 evaluations across 7 labs qualified | [Leaderboard](pages/leaderboard.html) |
| Does the model beat the market? | **No** — Brier skill −0.038 on 2,687 priced games | [Q-02](pages/questions.html#Q-02) |
| Are parlay legs independent? | **No** — QB–WR1 r = 0.5616 (n = 7,560) | [Q-03](pages/questions.html#Q-03) |
| Is the upstream injury data trustworthy? | **Partially** — the official page's “No Injuries Reported” is contradicted by NFL.com's own news for SEA/CIN (FL-DD-01) | [Flagged](pages/flagged.html) |
| Which Week 10 lineups are most deficient? | NE LG, PIT LOLB/DT, TEN LG/LB, SF LCB have **no listed backup**; MIN/BAL QB1 unverified; 92 chains tracked | [Injuries & depth](pages/injuries.html) |
| What blocks a real decision? | 4 items: status-quo call, pool funding, legal review, prop-price feed | [Suggestions](pages/suggestions.html) |

## What this session produced

- **Injuries & depth** — 254 rows from the official Week 10 report + 16 supplemental rows, 92
  starter→backup chains pairing an official status with the team-chart order (24 flagged),
  and 4 exposed “No Injuries Reported” contradictions. Blanks mean “no official source”, never a guess.
- **Questions** — 22 decision-readiness rows: 16 answered, 4 partial, 2 unanswered; every gap names
  the suggestion that would close it.
- **Suggestions** — 15 proposals, all `proposed` / `(awaiting reviewer)`. Nothing implemented;
  the reviewer sets the decision first.
- **Leaderboard** — 108 evaluations aggregated from the seven lab boards under one rule
  (gates passed, then ROI), plus 12 measured correlation rows quoted from committed JSON.
- **Flags** — 19 published (8 high severity), none blocking, each with handling + suggested fix.
- **Repo review** — all runnable gates green locally (check_site 106 pages/5,148 links,
  check_links 1,695 refs, validate_data, check_data, check_derived); numpy-dependent recompute
  left to CI (pinned in requirements.txt).

## Decisions required before anything moves

1. Accept the no-bet status quo or set a new bar (**S-01 / Q-01**).
2. Fund or defer the 10,000-point reward pool (**S-03 / Q-05**).
3. Commission or skip the Calgary jurisdiction legal review (**S-04 / Q-06**).
4. Acquire or defer a historical prop-price feed (**S-02 / Q-04**).

Recommended sequence: one reviewer pass — **[S-15](pages/suggestions.html#S-15)** — over all four.

## Trust statement

No number on this site was estimated. Every table row links to one of the
[49 registered sources](pages/sources.html), all fetched 2026-11-12. Unverified values are
blank and carried as [flags](pages/flagged.html). Rebuild is deterministic and enforced by
`decision-desk/scripts/verify_all.py` in CI.
