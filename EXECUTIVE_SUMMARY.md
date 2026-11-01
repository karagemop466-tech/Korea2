# Executive summary — NFL line origination, measurement and validation

**Live site:** <https://karagemop466-tech.github.io/Korea2/>
**Status:** research complete for this snapshot. **Zero strategies ranked.**
**Data as of:** gameday 2026-10-29 (108 settled 2026 games; 7,075 settled regular-season games in total, 1999–2026).

---

## 1. Bottom line

We built a complete line-origination pipeline, ran it walk-forward, and gated every
strategy. The honest result is that **nothing here should be bet**:

| Question | Answer | Evidence |
|---|---|---|
| Can we beat the closing line? | No | Rating model Brier skill vs market **−0.078** (negative = worse) |
| Do classic public angles work? | No | **0 of 12** survive Benjamini–Hochberg at q = 0.10 |
| Did any strategy clear all six gates? | No | **0 of 5**; best partial result misses FDR by 0.001 |
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

**The single most instructive case:** the wind-under angle returned **+8.65% over
649 bets** (p = 0.021, permutation p = 0.0008). It passes five of six gates. It fails
multiple-testing correction by **0.001**, and it is flat in the holdout (+8.5% pre-2018,
+12.4% 2018–22, +2.7% 2023–24, **−0.2% 2025–26**). That decay curve is what a dead
edge looks like, and it is exactly the artefact an ungated leaderboard would have
crowned as skill.

---

## 3. What we measured

### 3.1 The market is efficient in points

- Closing spread explains **18.5%** of variance in margin; slope **1.048**, residual SD **13.2 pts**.
- Home teams beat their own closing line by **+0.037 pts** on average (p = 0.81). Median error: **exactly zero**.
- Blind betting loses everywhere: home **−5.14%**, away **−0.84%**, over **−4.22%**, under **−2.20%**.
- Mean spread overround in the data: **2.7%**.

### 3.2 Totals look soft but are not

Mean total error is **+0.69 pts** with t = 4.35 — which reads like a free over. It is
not: totals are right-skewed, the median error is **0.0**, and the over cashes only
**49.5%** of non-push games. Reporting the mean alone would have produced a false
finding.

### 3.3 Correlation is the whole parlay

| Pair | r | n |
|---|---|---|
| QB passing yards vs own WR1 receiving yards | **+0.624** | 4,725 |
| Team passing yards vs WR1 receiving yards | +0.639 | 4,734 |
| WR1 vs WR2 receiving yards (same team) | +0.472 | 4,732 |
| Player's own receptions vs own receiving yards | +0.859 | 31,575 |
| Home QB vs away QB passing yards | +0.173 | 2,251 |
| Home margin vs game total | +0.018 | 7,075 |

Pricing a same-game QB + WR1 pair as independent understates the joint probability by
**×1.44** (naive 0.248 vs actual 0.358). Any same-game parlay engine that multiplies
legs is wrong, and it is wrong in the player's favour.

### 3.4 Parlay construction destroys itself

A three-leg ticket built from the model's *largest* disagreements hit **17.0%** against
an expected **42.8%** and lost money despite a positive headline ROI being within noise
(p = 0.66). The model was most confident exactly where it was most wrong.

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
including the historical closing prices no league source publishes. SHA-256 of every
file is in `data/provenance.json`.

Every one of **265** table rows on the site carries an https source link and the build
fails if one does not.

---

## 5. Flagged for review (does not block publication)

1. `spread_line` is positive when the **home** team is favoured — opposite to the
   commonly documented reading. Proved from the data (2,920/2,920 games with a
   positive line have a negative home moneyline); documentation mismatch open.
2. Wind-under angle misses BH-FDR by 0.001 and is flat in the holdout.
3. Weather fields cover ~57% of 2020–2026 games, outdoor venues only.
4. Closing prices only — no opening-line history, so CLV is unmeasurable.
5. No free official historical prop prices exist, so **no prop ROI is claimed**.
6. Only 2026 is reconciled team by team; 1999–2025 shares the pipeline but was not
   individually checked.
7. Push handling reduces a parlay ticket to its remaining legs.
8. Legal and jurisdictional status of wagering was not assessed.

---

## 6. Recommendation

1. **Do not stake money on anything here.** The model loses to the close and no
   strategy cleared the gates.
2. **Next highest-value input:** a licensed, timestamped history of player-prop and
   alternate prices. It is the only missing input that would let a prop strategy be
   priced at all; everything else is already measured.
3. **Keep the gates.** The wind-under case shows the apparatus paying for itself:
   without BH correction and a holdout, a dead angle would have topped the board.
4. **Publish the originated lines as a benchmark**, not a bet list — which is what
   the site does.

---

*Research, not betting advice. Wager only where legal and only if of age. Free,
confidential help: [National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/).*
