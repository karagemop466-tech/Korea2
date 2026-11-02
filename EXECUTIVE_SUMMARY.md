# Executive summary — NFL line origination, measurement and validation

**Live site:** <https://karagemop466-tech.github.io/Korea2/>
**Status:** research complete for this snapshot. **Zero strategies ranked.**
**Data as of:** gameday 2026-10-29 (108 settled 2026 games; 7,075 settled regular-season games in total, 1999–2026).
**Revision 2026-11-02 (issues #19, #34):** every price-based figure below was recomputed with
**no −110 imputation** — bets are settled only at prices the feed actually stores, and rows without
a stored price are excluded and counted (`n_excluded_missing_price` in `results/*.json`). The
road-favourite angle masks were corrected (positive `spread_line` means the *home* team is
favoured in this feed). Figures that changed carry the new value; nothing else was edited.

---

## 1. Bottom line

We built a complete line-origination pipeline, ran it walk-forward, and gated every
strategy. The honest result is that **nothing here should be bet**:

| Question | Answer | Evidence |
|---|---|---|
| Can we beat the closing line? | No | Rating model Brier skill vs market **−0.038** on the 2,675 games with both stored spread prices (negative = worse) |
| Do classic public angles work? | No | **0 of 12** survive Benjamini–Hochberg at q = 0.10 |
| Did any strategy clear all six gates? | No | **0 of 5**; the best partial result (wind-under) now fails significance outright |
| Is the closing spread biased? | No | Mean error +0.037 pts, t = 0.23, p = 0.81 |
| Can we still produce useful lines? | Yes, as a benchmark | 28 unplayed games, mean gap to market **3.82 pts**, correlation **0.81** |
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
430 bets** (p = 0.125, permutation p = 0.018) and passes **two of six gates**. The
decay curve is unchanged and decisive: +6.0% pre-2018 (277 bets), +12.4% 2018–22 (107),
+2.7% 2023–24 (27), **−0.2% 2025–26 (19)**. That is what a dead edge looks like, and it
is exactly the artefact an ungated leaderboard would have crowned as skill — the
imputed prices were propping it up.

---

## 3. What we measured

### 3.1 The market is efficient in points

- Closing spread explains **18.5%** of variance in margin; slope **1.048**, residual SD **13.2 pts**.
- Home teams beat their own closing line by **+0.037 pts** on average (p = 0.81). Median error: **exactly zero**.
- Blind betting at stored prices: home **−5.00%** (n = 5,173), away **+0.06%** (p = 0.96 — breakeven
  noise, not an edge), over **−3.35%**, under **−2.14%** (n = 5,171). 1,902 spread rows and 1,904
  total rows have no stored price and are excluded, never imputed.
- Mean spread overround in the priced games: **2.7%**.

### 3.2 Totals look soft but are not

Mean total error is **+0.69 pts** with t = 4.35 — which reads like a free over. It is
not: totals are right-skewed, the median error is **0.0**, and the over cashes only
**49.5%** of non-push games. Reporting the mean alone would have produced a false
finding.

### 3.3 Correlation is the whole parlay

| Pair | r | n |
|---|---|---|
| QB passing yards vs own top receiver's yards (ex-post game leader) | **+0.630** | 5,997 |
| Team passing yards vs top receiver's yards (ex-post leader) | +0.646 | 6,006 |
| Top-two receivers' yards, same team (ranked ex-post) | +0.473 | 6,004 |
| Player's own receptions vs own receiving yards | +0.860 | 40,273 |
| Home QB vs away QB passing yards | +0.171 | 2,871 |
| Home margin vs game total | +0.018 | 7,075 |

The receiver rows are labelled *ex-post*: "top receiver" means the yards leader **of that
game**, not a player identifiable before kickoff (issue #19). They measure how same-game
legs move together, not a pregame selection rule.

Pricing a same-game QB + WR1 pair as independent understates the joint probability by
**×1.44** (naive 0.248 vs actual 0.358). Any same-game parlay engine that multiplies
legs is wrong, and it is wrong in the player's favour.

### 3.4 Parlay construction destroys itself

A three-leg ticket built each week from the model's *largest* disagreements (all legs at
stored prices) hit **10.4%** (19 of 182 tickets) against the **27.4%** expected under the
model's own naive independent pricing, for an ROI of **−30.9%** (p = 0.045). The model was
most confident exactly where it was most wrong.

### 3.5 Prop lines must be medians, not means

| Market | Projection skill vs last-5 | Over rate at the mean | Over rate at the calibrated line |
|---|---|---|---|
| Receiving yards | +2.0% | **39.1%** | 48.7% |
| Rushing yards | +1.9% | **37.3%** | 49.4% |
| Passing yards | +2.0% | 47.9% | 50.6% |
| Receptions | +1.7% | **41.7%** | 49.0% |

A line set at the expected value is beaten well under half the time because player
output is right-skewed. The walk-forward median multiplier (0.73–0.98 depending on
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

**Third party (nflverse):** machine-readable extracts of the NFL's own play-by-play,
including the historical closing prices no league source publishes. `data/provenance.json`
records the SHA-256 of the raw games feed and the exact season list and download URL of
every per-season extract (no per-file raw hash is recorded for those, and none is claimed).

Every table row on the published site carries an https source link, and
`tests/check_site.py` fails the build if one does not.

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

*Research, not betting advice. Wager only where legal and only if of age. Free,
confidential help: [National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).*
