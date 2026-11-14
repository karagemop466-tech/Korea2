# Signal Desk — executive summary

Nine requirements, built one line at a time. Every number on the site is rendered from
`signal-desk/data/*.json`; every row names the page or file it came from, and a value that could not
be confirmed from a source is published **blank** with the reason, never inferred.

**Live pages:** `signal-desk/index.html` (landing) and `signal-desk/pages/*.html` (13 category pages,
all in the shared navigation).

## What was built

| # | Requirement | Where it lives | What it actually delivers |
|---|---|---|---|
| 1 | Price-snapshot store, opening and closing per market | `pages/prices.html` | A record per market per game **only where a source publishes the number**. Closing coverage 2014–2026. Opening coverage: one season, one book, and no moneyline at all. |
| 2 | Verified results feed | `pages/results.html` | **32 of 32 teams** reconcile exactly on W/L/T/PF/PA against NFL.com once the official scores the snapshot was missing are added; 2020 and 2025 also reconcile 32/32. |
| 3 | Side, then total, then moneyline | `pages/order.html` | Enforced and re-tested on every build: the published P(home win) reproduces Φ(side/σ) to within 0.0014 on every game, and the build fails above 0.002. |
| 4 | Fair, market and difference as separate columns | `pages/gap.html` | Three numeric columns per market plus the sign convention and the mean two-way hold (4.22%). No cell says "edge" without its two parents beside it. |
| 5 | Signal separated from staking | `pages/leaderboard.html` | Two tables with different orderings. **2 of 9** strategies show a positive ROI their own significance test does not support; **0** rewards are paid. |
| 6 | Depth of the replacement, not just the fact | `pages/depth.html` | Depth tracked to the **10th string**, 614 of 636 absences carrying a rank. The page also proves that **no official page publishes a depth ordinal**, so every 1st/2nd/3rd-string figure is labelled third-party. |
| 7 | Correlations from official numbers, with n | `pages/correlations.html` | Four team-level values at n=32 with 95% intervals. The per-game QB-to-receiver pair the parlay pricing needs is **blank** because the official pages cannot produce that join. |
| 8 | A demotion gate | `pages/demotion.html` | Eight rules, explicit triggers, an explicit state machine, and no direct route back from demoted to live. Four rules cannot fire yet, and the page says which. |
| 9 | Suggestions, questions, decision paths | `pages/suggestions.html`, `pages/questions.html` | 8 suggestions, 12 questions, 3 gating decisions. **Nothing is implemented**; each suggestion names the question it waits on. |

## The findings that change decisions

1. **The results are real.** The committed data does not merely pass its own checks — it reproduces
   the league's own standings table for all 32 teams, and for two completed seasons as well. This is
   the foundation everything else stands on.
2. **The committed snapshot is about a week and a half stale.** 15 finished games were absent from
   it. They are listed as absent and were not back-filled. Any backtest run on this snapshot silently
   drops those games.
3. **There is no season with both an opening and a closing number.** The opening file covers 2021
   only; the closing file stops at 2018. A per-bet open-to-close move — the number a demotion rule
   needs — cannot be computed for a single game from these files.
4. **No opening moneyline exists anywhere on file.** Every opening moneyline cell is blank, not zero.
5. **Depth is the one input the league does not publish.** The injury report and the roster were both
   opened and read: neither has a depth column. The depth work is therefore useful and permanently
   third-party until another source is found.
6. **Nothing is live, so nothing has been demoted.** Zero strategies cleared the ten static gates and
   zero rewards were paid. The demotion gate is published pre-armed.

## What has to be decided before anything else is built

| Question | Why it blocks work | Who can close it |
|---|---|---|
| Is there any official or licensed price source? | Every price on the site is third-party; CLV can never be called official without one | you (sourcing) |
| Can an opening moneyline be recorded at all? | Markets 1 and 4 are incomplete without it | you (sourcing) |
| Does any source publish depth-chart order? | Requirement 6 stays third-party forever otherwise | you (sourcing) |
| Which book, jurisdiction and limits are real? | The executable gate has never passed, which is why nothing is live | you (fact only you have) |
| Signal-first or staking-first leaderboard? | The data now supports either; the choice is editorial | you (preference) |

The rest of the twelve questions are on `pages/questions.html`, sorted by how many decisions each one
blocks.

## Verification performed for this build

* **Official pages read on 2026-11-14** (transcribed into `scripts/transcripts.py`, quoted on
  `pages/sources.html`): NFL.com division standings for 2026, 2025 and 2020; scores for weeks 8, 9 and
  10; the passing and receiving leader tables; the current injury report, the week-9 injury report, and
  one team roster.
* **32/32 team reconciliation** on all five standings columns, plus 32/32 for 2020 and 2025.
* **30 games** read game-by-game from the official scores pages, 13 of which matched the committed
  data and 17 of which were legitimately new.
* **Upstream file integrity:** the fetched opening and closing files hash to the SHA-256 prefixes
  recorded in `data/PROVENANCE.md` (`654770173d11…` and `3571e1c9fc8d…`), which is an independent
  confirmation that the pinned files are the ones this build used.
* **18 automated tests** (`signal-desk/tests/`), including a rebuild that must reproduce the committed
  JSON byte for byte, a test that an `unverified` value never carries a number, and a test that
  nothing from nflverse is ever classed as official.
* **Structural checks** (`scripts/check.py`): 14 pages, 31 tables, 291 table rows, every row with a
  source link, no broken internal links, no off-allowlist external hosts.

## What this build does not claim

No strategy is approved for capital. No reward pool is funded. No sportsbook, licence, limit or
jurisdiction has been verified. Nothing here is betting advice. The model's originated side and total
are both **worse** than the market closing line on the same games (spread MAE 10.39 vs 9.71), and the
honest headline of the project is unchanged: the market is better than the model.

## Reproduce

```bash
python signal-desk/scripts/fetch_prices.py     # optional; reports failure instead of guessing
SD_INITIAL_LINES=signal-desk/data/raw/initial_lines.csv \
SD_CLOSING_LINES=signal-desk/data/raw/closing_lines.csv \
  python signal-desk/scripts/analysis.py
python signal-desk/scripts/build.py
python signal-desk/scripts/check.py
python -m unittest discover -s signal-desk/tests -t signal-desk/tests -v
```
