# Executive summary

**Project:** originating NFL lines, researching signals, and running a gated strategy competition
**Built:** 2026-11-01 (UTC) · source data refreshed 2026-11-01T13:06Z
**Live site:** GitHub Pages from `main` / `docs` · **Task board:** `COORDINATION.md`

---

## 1. The one-paragraph version

We built our own NFL spread, total and moneyline from team ratings estimated walk-forward on 21 seasons
of priced games, tested 27 pre-registered signals and 18 strategy families (singles, parlays, same-game
combinations, teasers), and subject every one of them to seven validation gates. **No strategy qualified.**
That is the finding, not a failure of the exercise: the data says the closing line is extremely well
priced, that most apparent edges vanish once you correct for multiple testing, and that a strategy needs
roughly 6,000 settled bets before a 2% edge is even visible. The project ships the machinery, the
evidence, and a live dashboard instead of a fantasy bankroll.

## 2. What was built

| Layer | What it does | Where |
|---|---|---|
| Ingestion | 9 extracts, SHA-256 hashed, pinned to a commit | `data/manifest.json`, `docs/data.html` |
| Verification | 9 integrity / reconciliation checks | `docs/data.html` |
| Line origination | Ridge rating model → spread, total, moneyline | `docs/lines.html` |
| Signal research | 27 pre-registered signals, FDR + out-of-sample | `docs/signals.html` |
| Strategy competition | 18 families, 7 gates, leaderboard + rewards | `docs/strategies.html`, `docs/gates.html` |
| Correlation | φ coefficients with CIs, copula pricing | `docs/correlation.html` |
| Luck removal | Permutation nulls, reliability, evidence bar | `docs/luck.html` |
| Player props | Origination + calibration (unpriced) | `docs/props.html` |
| Oversight | Source registry + flagged items | `docs/sources.html`, `docs/flagged.html` |

## 3. Headline numbers

| Metric | Value | Reading |
|---|---|---|
| Game rows ingested | 7,548 (7,384 played, 1999–2026) | every game has a closing line; 5,403 have prices |
| Our margin MAE | 10.69 pts | the closing line's is 10.26 |
| Our total MAE | 10.86 pts | the closing line's is 10.61 |
| Correlation with the close | 0.769 (margin), 0.801 (total) | we agree with the market, which is a compliment to the market |
| Moneyline Brier score | 0.2246 | market 0.2115 — our probabilities are worse |
| Signals tested | 27 | 0 survived FDR + out-of-sample |
| Strategies tested | 18 | 0 passed all seven gates |
| Strongest leg correlation | φ = 0.672 (home ML × home cover) | same-game legs are not independent |
| Cross-game correlation | φ = 0.029 (CI −0.002 to 0.059) | standard parlays across games are fine |
| Sigma of a zero-edge bettor | 3.01% over 1,000 bets | luck is wide |

## 4. Findings that matter

**4.1 The closing line is beatable only at large model disagreements — and not provably at all.**
Our model's edge curve is monotone: at ≥3 points of disagreement with the close, 2,221 bets returned
+2.8% with a 53.0% hit rate; at ≥4 points, 1,533 bets returned +3.8% with 53.6%. Both are the shape of a
real signal and neither is significant (p = 0.27 and 0.17). The honest conclusion is "promising,
unproven", and the sample needed to settle it is roughly four times what history provides.

**4.2 Every popular public angle is already priced.**
Home underdogs −2.2%, divisional home dogs −4.3%, fading big home favourites −3.8%, rest advantages
−4.5%, buying cold teams −4.2%, dome overs +0.5%. Twenty-seven signals, four of which looked interesting
before correction, none of which survived. Two that looked best (low totals, cold-weather unders) actually
flipped sign out of sample.

**4.3 Parlays multiply the vig, not the edge.**
Two −110 legs need 27.4% of tickets to win to break even; two independent 52.4% legs win 27.4% of the
time. Every parlay family tested returns less than the single bets inside it. The exception worth
understanding is the same-game ticket, where correlation genuinely changes the fair price: a book that
multiplies independent leg probabilities mis-prices any pair with |φ| meaningfully above zero.

**4.4 Correlation values, measured not assumed.**
Home moneyline × home cover ATS: **φ = 0.672** (95% CI 0.657–0.686). Spread × total in the same game:
**φ = 0.025** (CI −0.002 to 0.051) — effectively independent. QB passing yards over our line × team total
over: **φ = 0.198**. RB rushing × team total: **0.073**. Receiver yards × team total: **0.074**.
QB passing × his top receiver's yards: **0.157**. Different games, same week: **0.029**, so the classic
parlay independence assumption is sound across games and only questionable within them.

**4.5 Luck can be measured and mostly explains everything.**
Twenty thousand simulated zero-edge bettors placing 1,000 bets each at −110 produce a return standard
deviation of 3.01%; the 95th percentile is +0.4% and the best of every hundred such bettors averages
+3.1%. Team-season ATS dispersion does not exceed a permutation null that preserves the one-winner-per-
game constraint (observed 0.01301 vs null 0.01521 ± 0.00085), team ATS split-half reliability is
−0.058, and year-over-year reliability is −0.035. There is no detectable team-level ATS skill to exploit.

**4.6 Teaser "edges" do not survive this data.**
The classic Wong construction (6-point teasers on +1.5/+2.5 dogs and −7.5/−8.5 favourites) covers 68.7%
and 67.8% per leg after the six points in this sample, so a two-team ticket at −110 wins about 46% — a
loss of 13.5% per ticket. Whatever edge existed in earlier eras is not present in 2006–2026 as recorded
here.

**4.7 Player props: we can originate a line, but not cash it.**
Our prop line is well calibrated out of sample (48.6%–50.9% over rates on 2024, against 42.6%–56.6% for
the recency baseline), which is the thing that actually matters for setting a fair number. But there is
no sportsbook prop price in any verified source, so a prop strategy cannot be settled against a market,
cannot pass the significance or price-shock gates, and is published as unpriced research rather than as a
leaderboard entry. This is the largest gap in the brief and it is flagged as F3.

## 5. What passed validation

Nothing. Of 18 strategy families, the best cleared 3 of 7 gates.

| Strategy | Bets | ROI (all) | ROI 2016+ | p (2016+) | Gates |
|---|---|---|---|---|---|
| Wind ≥ 15 mph unders | 449 | +9.29% | +8.12% | 0.117 | 3/7 |
| 2-leg parlay, top-2 model edges | 2,225 | +4.20% | +1.16% | 0.400 | 3/7 |
| Model spread edge ≥ 2 pts | 3,094 | −0.18% | −1.11% | 0.681 | 2/7 |

The wind signal fails on sample size, multiple-testing correction and drawdown; the parlay fails
consistency and significance; everything else fails significance outright. The reward pool is therefore
unallocated this cycle — the schedule, tiers and scoring formula are published so the next cycle can pay
somebody, but it will only pay a strategy that clears all seven gates.

## 6. Verification status

* **9 integrity checks**: 7 pass, 2 `needs review` (closing-line reconciliation gap, player-week mirror).
* **Internal reconciliation**: points scored/allowed from the game file equal the standings file for
  **800 of 800** team-seasons.
* **Cross-extract reconciliation**: two independent closing-line extracts agree exactly on **2,095 of
  3,096** home sides, within 0.5 pt on 91.3%, within 1 pt on 97.2%, max gap 5.5 pts.
* **League-official spot check**: 2026 NFL.com standings matched the nflverse standings file on
  **24 of 24** published teams (W-L-T, points for, points against).
* **13 sources** registered with URL, HTTP status, row count and SHA-256.
* **14 items on the Flagged for review page**, none of which blocks release.

## 7. Decisons requested from you

1. **Provide a licensed odds history** with a named sportsbook and explicit open/close timestamps (F1),
   and a player-prop odds history (F3). Both would convert the prop and CLV layers from research to
   testable strategies.
2. **Confirm the teaser price convention** you actually bet at (F4) and the parlay push rule of your book
   (F5); both are currently stated assumptions.
3. **Tell me whether relocated franchises should keep their rating history** (F10); the current mapping
   carries it forward.
4. **Accept or reject the zero-payout outcome.** The alternative is to loosen gate G2, which would raise
   the chance of paying a lucky strategy — the exact thing this project set out to avoid.

## 8. Limitations in one place

Odds provenance is undocumented by the publisher (single source, no line shopping, no live prices). Player
data covers two seasons and comes from a mirror. There is no injury, practice, roster or travel data, and
the weather fields have no documented measurement protocol. League-official verification is a spot check,
not an automated diff. Full detail: `docs/flagged.html`, `docs/methods.html`.
