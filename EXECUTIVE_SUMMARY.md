# Executive summary — NFL line origination, measurement and validation

**Current repository status — 2026-11-15.** Research only; no candidate is approved for live use, no official timestamped market-price archive is captured, and no reward pool is funded. Do not use the committed Week 9 model lines as current recommendations.

**Live site:** <https://karagemop466-tech.github.io/Korea2/> — the latest Pages API check (2026-11-15 18:20 UTC) reported `built` for main commit `a08c249352d2be2028affa1fbb2c13d1b3d93235`; this predates and does not include the current unmerged documentation edits.

### The decision in brief

- **Skill:** the root/Line Desk lists 7 candidates plus 2 controls; **0/7 candidates qualify**. The Price Desk reports a separate 28 historical entrants, all `NEEDS_REVIEW` or `REJECTED`. Ranking rules and candidate sets differ across hubs, and the reward pool is unfunded.
- **Prices:** the Price Desk has 2,364 game-market rows: all 2,364 opening lines are blank; 1,956 closing values are `archived-unverified` (nflverse-derived); 408 are blank. Its 11,370 player-prop rows have no market open/close. The official-only `price-store` CSV is empty. Separately, Line Desk has 45 Week 9 model lines, but 0 own closes and 0 official market opens/closes. CLV and official price-based ROI are not established.
- **Results:** Line Desk lists 44 NFL.com finals for Weeks 7–9 plus the Week 10 Thursday game, with Weeks 1–6 pending. The Price Desk has a different 1,088-game feed: 22 scores marked official, 931 archived-unverified and 135 missing/unsettled; it reports 5/5 archive checks matched and 17 official scores filled blank archive rows. These registers are not yet one unified verified results corpus.
- **Correlations:** eight coefficients are built from NFL.com standings values only, with *n* and intervals. They describe team standings; they do not validate player-prop or same-game joint probabilities.
- **Availability:** Line Desk has 11 injury-report rows from four clubs and **zero verified replacement names or string tiers**. Price Desk records a one-game official Game Book demonstration for WAS@NYG (starters, Did-Not-Play, Not-Active and weather) plus a separate Game Book score check. A separate [Week 10 injury-report re-verification](injury-report-w10/index.html) records another session's 2026-11-15 fetch of the NFL report: 28 listed teams, only 3/28 tables transcribed row by row, manual counts for the rest, four clubs absent with bye status unverified, and no raw-response hash. This is partial evidence, not a full 32-team availability archive or scheduled all-week capture. nflverse depth/roster/snap data in another hub remain third-party.
- **Governance:** two repository originators differ by 1.5–9.0 points on the same 15 Week 9 games. A canonical line source remains undecided. The Review Board aggregates seven configured suggestion/question registers but omits the newer Line Desk and Price Desk registers; no suggestion is an implementation instruction.

The detailed [Line Desk](line-desk/index.html) carries per-row provenance, blank values, questions and flags. The [Line Desk source register](line-desk/pages/sources.html) and [Price Desk source register](price-desk/pages/sources.html) record NFL/NIST pages and Game Books opened by an earlier session on 2026-11-14. The merged [Week 10 injury-report page](injury-report-w10/index.html) records a different session's 2026-11-15 fetch-tool review and its partial-coverage flags. This session did not fetch those external pages. Local Price Desk validation passed (20,504 checks and 10 unit tests), which does not independently verify the linked official pages. The full current repository audit, including the information still missing and the suggested discovery path, is [here](docs/REPOSITORY_STATUS_2026-11-15.md).

**Source and freshness warning:** the root analysis inputs end on gameday 2026-11-01 and include community-maintained nflverse data. That feed is not an official sportsbook archive. The Line Desk's source register reports checks dated 2026-11-14; the separate Week 10 injury-report page records another session's partial fetch on 2026-11-15. This audit did not repeat either source review. The successful Pages build and local test suite establish build/reproducibility checks—not current source freshness, model skill, or profitability.

---

## Archived root-model analysis — snapshot through 2026-11-01

The report below is retained for reproducibility and historical context. It describes the `pipeline/` + `results/` analysis, not the current project-wide status. Its figures are historical claims from the committed analysis record; this 2026-11-15 audit did not fetch the underlying external NFL pages or independently re-run every calculation. Do not read them as current lines, as fresh official-source verification, or as official-price evidence.

> **Which build this historical section describes.** It covers the `pipeline/` + `results/` build of
> 2026-11-01 (six gates, five strategies). The published root dashboard is the integrated build (ten
> gates, seven candidate strategies plus two controls); its historical summary is
> [`docs/EXECUTIVE_SUMMARY.md`](docs/EXECUTIVE_SUMMARY.md). The independent recomputation is on the
> [Verification page](https://karagemop466-tech.github.io/Korea2/pages/verification.html) and its
> committed data register.

---

## 1. Bottom line

We built a complete line-origination pipeline, ran it walk-forward, and gated every
strategy. The honest result is that **nothing here should be bet**:

| Question | Answer | Evidence |
|---|---|---|
| Can we beat the closing line? | No | Rating model Brier skill vs market **−0.038** on the 2,687 games with both stored spread prices (negative = worse) |
| Do classic public angles work? | No | **0 of 12** survive Benjamini–Hochberg at q = 0.10 |
| Did any strategy clear all six gates? | No | **0 of 5**; the best partial result (wind-under) now fails significance outright |
| Is the closing spread biased? | No | Mean error +0.037 pts, t = 0.23, p = 0.81 |
| Can we still produce useful lines? | Yes, as a benchmark | 16 unplayed games with a market line, mean gap to market **3.66 pts**, correlation **0.84** |
| Is our data trustworthy? | Yes | **32/32** team records and **3/3** QB lines match NFL.com exactly |

The value of the project is not a winning system. It is a **measurement apparatus**
that can price a strategy, detect luck, and refuse to promote noise.

---

## 2. What "removing luck" actually means here

Luck cannot be deleted from sport. It can be *priced*, and that is what the gates do.
Every strategy faces six pre-registered tests:

1. **Sample size** — at least 300 settled bets.
2. **Significance** — two-sided p < 0.05.
3. **Multiple testing** — must survive Benjamini–Hochberg across every strategy tried.
4. **Positive after vig** — ROI > 0 *and* the 95% bootstrap interval excludes zero.
5. **Luck permutation** — thousands of random portfolios of the same size, at the
   same prices, must lose to it more than 95% of the time.
6. **Track-record length** — enough bets for the observed effect to be detectable.

Then temporal stability is reported separately across develop (2018–22), validate
(2023–24) and **holdout (2025–26)**, touched once.

**The single most instructive case:** the wind-under angle. Before the issue-#19 fix it
returned +8.65% over 649 bets and passed five of six gates, missing multiple-testing
correction by 0.001 — but 219 of those bets had no stored price and were silently
settled at an assumed −110. Settled **only at stored prices** it returns **+7.14% over
430 bets** (p = 0.125, permutation p = 0.017) and passes **two of six gates**. The
decay curve is unchanged and decisive: +6.0% pre-2018 (277 bets), +12.4% 2018–22 (107),
+2.7% 2023–24 (27), **−0.2% 2025–26 (19)**. That is what a dead edge looks like, and it
is exactly the artefact an ungated leaderboard would have crowned as skill — the
imputed prices were propping it up.

---

## 3. What we measured

### 3.1 The market is efficient in points

- Closing spread explains **18.5%** of variance in margin; slope **1.048**, residual SD **13.2 pts**.
- Home teams beat their own closing line by **+0.037 pts** on average (p = 0.81). Median error: **exactly zero**.
- Blind betting at stored prices: home **−4.89%** (n = 5,185), away **−0.06%** (breakeven noise, not an
  edge), over **−3.35%**, under **−2.15%** (n = 5,183). 1,902 spread rows and 1,904 total rows have no
  stored price and are excluded, never imputed.
- Mean spread overround in the priced games: **2.7%**.

### 3.2 Totals look soft but are not

Mean total error is **+0.69 pts** with t = 4.35 — which reads like a free over. It is
not: totals are right-skewed, the median error is **0.0**, and the over cashes only
**49.5%** of non-push games. Reporting the mean alone would have produced a false
finding.

### 3.3 Correlation is the whole parlay

| Pair | r | n |
|---|---|---|
| QB passing yards vs own top receiver's yards (ex-post game leader) | **+0.631** | 7,549 |
| Team passing yards vs top receiver's yards (ex-post leader) | +0.650 | 7,566 |
| Top-two receivers' yards, same team (ranked ex-post) | +0.464 | 7,563 |
| Player's own receptions vs own receiving yards | +0.860 | 50,319 |
| Home QB vs away QB passing yards | +0.173 | 3,515 |
| Home margin vs game total | +0.017 | 7,087 |

The receiver rows are labelled *ex-post*: "top receiver" means the yards leader **of that
game**, not a player identifiable before kickoff (issue #19). They measure how same-game
legs move together, not a pregame selection rule.

Pricing a same-game QB + top-receiver pair as independent understates the joint probability by
**×1.45** (naive 0.247 vs actual 0.358). Any same-game parlay engine that multiplies
legs is wrong, and it is wrong in the player's favour.

### 3.4 Parlay construction destroys itself

A three-leg ticket built each week from the model's *largest* disagreements (all legs at
stored prices) hit **10.4%** (19 of 183 tickets) against the **27.4%** expected under the
model's own naive independent pricing, for an ROI of **−31.3%** (p = 0.042). The model was
most confident exactly where it was most wrong.

### 3.5 Prop lines must be medians, not means

| Market | Projection skill vs last-5 | Over rate at the mean | Over rate at the calibrated line |
|---|---|---|---|
| Receiving yards | +1.9% | **39.1%** | 49.0% |
| Rushing yards | +1.9% | **37.3%** | 50.0% |
| Passing yards | +1.9% | 48.1% | 49.9% |
| Receptions | +1.7% | **41.8%** | 49.3% |

A line set at the expected value is beaten well under half the time because player
output is right-skewed. The walk-forward median multiplier (0.72–0.98 depending on
market) corrects it. **This is the core line-origination insight** and it applies to
anyone quoting "projected yards" as a line.

Projection skill itself is modest: **+2%** over a naive last-five average. That is the
ceiling on any prop strategy built on public data.

---

## 4. Verification

Two tiers of source, never blurred.

**Official (NFL.com):**
- All **32 of 32** 2026 team records — W, L, T, points for, points against — reconcile
  exactly across 108 settled games.
- **3 of 3** quarterback passing lines (yards, TD, INT, completions, attempts)
  rebuild exactly from the player feed.
- <https://www.nfl.com/standings/division/2026/REG>
- <https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc>

**Data refresh 2026-11-02 (`95bbd78`):** the automated refresh brought Week 9's partially settled games
into the extracts; every figure above was regenerated from them deterministically. That commit was produced by
the pre-fix workflow, which pushed straight to `main` with `[skip ci]` — the fail-closed, pull-request-based
replacement for it is in this pull request (issue #20).

**Third party (nflverse):** machine-readable extracts of the NFL's own play-by-play,
including the historical closing prices no league source publishes. `data/provenance.json`
records the SHA-256 of the raw games feed and the exact season list and download URL of
every per-season extract (no per-file raw hash is recorded for those, and none is claimed).

The archived report claimed every root-site table row had an HTTPS source link. The current audit found that `tests/check_site.py` checks 231 HTML pages, but 33 pages outside the root build do not carry the root table-source column; the checker also does not verify external publisher tier or current page content. See the [2026-11-15 repository audit](docs/REPOSITORY_STATUS_2026-11-15.md).

---

## 5. Flagged for review (does not block publication)

1. `spread_line` is positive when the **home** team is favoured — opposite to the
   commonly documented reading. Proved from the data (2,920/2,920 games with a
   positive line have a negative home moneyline); documentation mismatch open.
2. Wind-under angle, recomputed at stored prices only: +7.14% over 430 bets, p = 0.125 —
   it now fails significance and BH-FDR outright, and is still flat in the holdout.
3. Weather fields cover ~57% of 2020–2026 games, outdoor venues only.
4. Closing prices only — no opening-line history, so CLV is unmeasurable.
5. No free official historical prop prices exist, so **no prop ROI is claimed**.
6. Only 2026 is reconciled team by team; 1999–2025 shares the pipeline but was not
   individually checked.
7. Push handling reduces a parlay ticket to its remaining legs.
8. Legal and jurisdictional status of wagering was not assessed.
9. 1,902 of 7,075 settled games carry no stored spread price (1,904 no total price).
   Earlier revisions of this pipeline imputed −110 there; since the 2026-11-02 revision
   those rows are excluded from every price-based figure and the counts are published
   in `results/*.json` (`n_excluded_missing_price`).

---

## 6. Recommendation

1. **Do not stake money on anything here.** The model loses to the close and no
   strategy cleared the gates.
2. **Next highest-value input:** a licensed, timestamped history of player-prop and
   alternate prices. It is the only missing input that would let a prop strategy be
   priced at all; everything else is already measured.
3. **Keep the gates — and keep the price hygiene.** The wind-under case shows the
   apparatus paying for itself twice: without BH correction and a holdout a dead angle
   would have topped the board, and without the stored-price-only rule it would still
   look significant (p = 0.021 imputed vs p = 0.125 honest).
4. **Publish the originated lines as a benchmark**, not a bet list — which is what
   the site does.

---

## 7. Earlier additions and verification record (arena/cb5b61a7-korea2, 2026-11-12)

An earlier session recorded three reviewable pages added to keep decisions honest and reversible, without altering the
underlying pipeline or any previously published number:

- **Suggestions** (`pages/suggestions.html`) — a review board of improvement ideas (depth-chart
  source, CLV tracker, licensed prop prices, injury adjustments, correlation-aware parlays,
  holdout-only leaderboard, jurisdiction gating, source monitoring, fractional-Kelly staking).
  Each row has a recommended path and a status the reviewer sets before anything is built.
- **Decision questions** (`pages/decision-questions.html`) — what we know (verified against
  official sources), what we don't (left blank by policy), the questions that must be answered
  before any capital decision, and a concrete discovery suggestion for each gap.
- **Injury & depth** (`pages/injuries-depth.html`) — an official NFL injury-report view and a documented depth-data gap. A subsequent source review confirmed that one Colts team-published chart lists ordered players but labels its weekly chart unofficial. It is not an NFL-wide historical source; no complete dated chart archive or replacement-value model is ingested, so depth adjustments remain blocked and values blank. The earlier broad statement that the chart source was absent because of a 404 is superseded.

**Earlier-session verification record (reported live retrieval 2026-11-12; not repeated in this audit):** the earlier session reported reviewing NFL.com 2026 standings, Week 10 injury report and schedule, the Colts team-published depth chart, DraftKings parlay rules and nflverse documentation. Its log describes the Colts page as unofficial/team-specific and nflverse as community-maintained. It also recorded passing site/rebase checks at that time. This audit did not re-fetch those sources; statistical pipeline values were not refreshed here. See the historical [verification page](pages/verification.html), [repository review](docs/REPO_REVIEW.md) and site's Flagged for Review page for the original scope.

---

*Research, not betting advice. Wager only where legal and only if of age. Free,
confidential help: [National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).*
