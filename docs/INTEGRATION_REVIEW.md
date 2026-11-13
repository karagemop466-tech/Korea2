# Line-by-line integration review — 2026-11-13

**Session:** `arena/dd794652-korea2` (final integration session, branch `arena/dd794652-korea2`,
base commit `007f2ed`).
**Scope:** the whole repository — every generator, every committed dataset, every published page,
every source link, plus a live re-read of the official pages the site cites.

**Rules followed.** Nothing on this page is estimated. A number is quoted only if it was read out of
a committed file in this repository or off an official page that was opened on the date shown. Where
a value could not be confirmed it is left blank and listed as an open item rather than filled in.

---

## 1. How the review was done

| Step | What it covered | Result |
|---|---|---|
| Repository inventory | 178 HTML pages, 541 files, 17 published workspaces, 12 CI workflows | every published page reachable from the root site after the navigation change (section 4) |
| Generator review | `scripts/build_site.py`, `scripts/lib/site.py`, `scripts/analysis/*`, and each sibling workspace's generator | two generators write the same root paths with the same generator marker — logged as IR-07 |
| Data review | every file in `data/`, `data/derived/`, `verification/`, and each workspace's own data folder | the committed extracts are internally consistent; one published scope claim does not match the committed file — IR-03 |
| Number review | 45 published headline figures re-derived by a second independent implementation | 41 exact matches, 4 documented differences, 0 mismatches |
| Source review | every source register in the repository and every external URL on the published pages | official pages re-read on 2026-11-13; dead links recorded in section 6 |
| Link and table review | `tests/check_site.py`, `scripts/check_links.py`, `tests/check_derived.py`, `scripts/validate_data.py` | all pass on the merged tree |

**The second implementation** is [`verification/integration_recompute.py`](../verification/integration_recompute.py).
It imports nothing from `scripts/` or `pipeline/`, reads only committed files
(`data/derived/games.csv.gz`, `data/derived/predictions.csv`, `data/derived/player_week.csv.gz`),
and exits non-zero if a published value disagrees. Its record is committed at
[`verification/integration_recompute.json`](../verification/integration_recompute.json) and is
rendered on the [Verification page](https://karagemop466-tech.github.io/Korea2/pages/verification.html).

---

## 2. What the published numbers are made of

| File | Rows | What it holds |
|---|---|---|
| `data/derived/games.csv.gz` | 7,548 rows (7,396 played) | every game 1999-2026 with the closing line. 152 rows are the 2026 schedule with no score yet (through 2027-01-10) |
| `data/derived/predictions.csv` | 936 rows | the out-of-sample model and market margin for 2023-2026 |
| `data/derived/player_week.csv.gz` | 208,231 player-weeks | player-level rows, **2015-2026** (this is the window that matters for IR-03) |
| `data/derived/team_week.csv.gz` | team-weeks | team-level aggregates |
| `data/derived/market.json`, `model.json`, `correlation.json`, `luck.json`, `strategies.json`, `leaderboard.json`, `props.json` | — | every figure the site prints |
| `data/derived/verification.json` | 49 checks | the 2026-11-02 verification session's record |

---

## 3. Findings and the corrections made

### IR-01 — The ATS "coin-flip test" was an arithmetic identity presented as a finding *(fixed)*

**What the site said.** The overview card read "ATS coin-flip test — 50.0%, p = 1.0 against 50%
… The spread market shows no exploitable tilt", and the Removing luck page listed "Pooled ATS win
rate 50.0%".

**Why that is not evidence.** `data/derived/luck.json` builds the sample from team-game rows: each
game contributes one cover and one non-cover, so the rate is 50% by construction and the binomial
p-value is 1.0 for any input. The independent recomputation confirms it: 13,784 rows, 6,892
positive, rate exactly 0.5.

**What is true.** `data/derived/market.json` already holds the one-observation-per-game test:
`ats_home_cover` — 6,892 decided games, 3,371 home covers, **48.91%**, 95% Wilson CI
**47.73–50.09%**, exact binomial **p = 0.0727**, 195 pushes. The independent recomputation
reproduces every one of those numbers from the committed extract.

**Correction.** The overview card and the Removing luck page now publish the one-sided test as the
result and label the pooled 50% row explicitly as an identity. The measured values did not change.

**Source of the correction:** the decision-hub workspace had already recorded the same problem as
FL-DH-01, and asked the root-site owner to fix it; this session owns the root site.

### IR-02 — Stale copies of the headline numbers in the README and the executive summary *(fixed)*

`docs/EXECUTIVE_SUMMARY.md` and `README.md` quoted figures from the pre-refresh window. 28 figures
were checked one by one against the committed JSON; every drift was corrected:

| Figure | Was | Now (committed value) |
|---|---|---|
| Closing spread MAE sample | 7,075 | 7,087 |
| Closing spread MAE 2023+ | 9.70 pts / 924 games | 9.71 pts / 936 games |
| Spread regression slope | 1.048 | 1.049 |
| Home cover rate | 48.9% on 6,880 | 48.91% on 6,892 |
| Over rate | 49.5% on 6,976 | 49.53% on 6,988 |
| Moneyline Brier / n | 0.2112 / 5,158 | 0.2111 / 5,170 |
| Model spread MAE | 10.38 | 10.39 |
| Model total MAE | 10.71 | 10.74 |
| Incremental-information c and p (spreads) | −0.02, p = 0.85 | −0.019, p = 0.881 |
| Incremental-information c and p (totals) | −0.16, p = 0.22 | −0.149, p = 0.247 |
| Pythagorean R² / luck budget | 82.5% / 17.5% | 81.9% / 18.1% |
| Luck persistence r and n | 0.019 (n = 827) | 0.024 (n = 842) |
| One-score persistence r and p | 0.087, p = 0.011 | 0.082, p = 0.017 |
| Correlation sample | 7,542 team-games / 248,972 player-games | 7,566 team-games / 249,814 player-games |
| Placebo cross-game r | −0.013 | −0.030 |
| Strategy bets and ROI (7 candidates + 2 controls) | 133 / 81 / 45 / 195 / 550 / 390 / 357 | 137 / 86 / 46 / 204 / 572 / 409 / 370 (ROI re-read from `leaderboard.json`) |
| Verification record | "48 of 49 checks agree" | 49 checks: 45 strict equality checks agree, 0 disagree, 11 observations |
| Site check counts | 71 pages / 152 tables / 2,252 links | 178 pages / 430 tables / 10,574 links |

### IR-03 — The published correlation scope does not match the committed extract *(open — published)*

`data/derived/correlation.json` states `scope.seasons = [2012, 2026]`. The committed
`data/derived/player_week.csv.gz` covers **2015–2026**. The consequence, measured by the
independent recomputation:

| Quantity | Published | Recomputed from the committed file |
|---|---|---|
| Team-games | 7,566 | 5,782 |
| QB ↔ WR1 pair n | 7,560 | 5,776 |
| QB ↔ WR1 r | 0.5616 | **0.5618** (reproduces) |
| WR1 ↔ WR2 r | 0.1199 | 0.1294 (gap 0.0095, inside one standard error of the published estimate, 0.0129) |
| 4-leg parlay joint | 11.14% | recomputed and published as a documented difference |

This is the same window problem the root flagged page already described; this session quantified it
and published it as a documented difference rather than a pass. Fixing it properly means re-running
the pipeline against a 2012-2026 extract.

### IR-04 — The published snapshot is behind the live page *(open — published)*

Checked on **2026-11-13** against the official pages:

| Source | What it returned |
|---|---|
| [NFL.com injury report](https://www.nfl.com/injuries/) | "Week 10 of the 2026 Season", games dated Thursday 2026-11-12 to Sunday 2026-11-15 |
| [NFL.com Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) | Commanders 24, Giants 21 (final, Thursday 2026-11-12); the rest of the slate Sunday 2026-11-15 |
| [NFL.com 2026 division standings](https://www.nfl.com/standings/division/2026/REG) | 137 regular-season games played; transcribed in `verification/nfl_standings_2026-11-13.json` |
| Committed extract | 120 regular-season games, last gameday 2026-11-01 |

**17 games behind.** Two teams (Washington, New York Giants) are two games behind because they played
on Thursday 2026-11-12; two (Pittsburgh, Tennessee) are level because they were on bye; the other 28
are one game behind. The 32/32 reconciliation against NFL.com recorded on 2026-11-02 remains valid
for its own snapshot; it is simply no longer the current page.

### IR-05 — The navigation listed 28 flat entries, with duplicates, and reached 4 of 17 workspaces *(fixed)*

The sidebar contained two entries labelled "Suggestions hub" and three different labels for the same
decision layer ("Decision Desk", "Decision hub", "Decision desk"). Thirteen published workspaces —
`audit/`, `dashboard/`, `lineup-lab/`, `nfl-command/`, `nfl-lines/`, `nfl-research/`, `origination/`,
`origination-lab/`, `quant-lab/`, `research-desk/`, `skill-lab/`, `site/`, `verify-hub/` — were not
linked from the root site at all; they were reachable only by typing a URL.

**Correction.** The navigation is now grouped (Research / Decide / Evidence), the duplicates are
gone, and a new **Workspaces** page
([`pages/workspaces.html`](https://karagemop466-tech.github.io/Korea2/pages/workspaces.html))
lists every workspace with what it contains, how many pages it publishes, where its own review page
is, and how many open items its own flag register carries. The landing page carries the same
directory plus the decision-support entries.

### IR-06 — The review queue only showed the root site's own items *(fixed)*

Each workspace keeps its own flag register (`decision-desk`, `lineup-lab`, `nfl-command`,
`skill-lab`, `suggestions`, `verify-hub`, and the root's own `data/flagged.json`). The root
"Flagged for review" page listed only the root's items, so a reviewer working from the landing page
could not see the other registers.

**Correction.** The flagged page now carries a **whole-site review queue**: one row per workspace
with its open-item count, its highest severity, its entry point, its review page and a link to its
folder in the repository. The counts are read from each workspace's own register file at build
time, so the queue cannot drift away from the workspaces it summarises.

### IR-07 — Two generators write the same root paths with the same marker *(open — noted)*

`scripts/build_site.py` and `site/scripts/build_site.py` both write files under `pages/` and both
stamp `<meta name="generator" content="line-lab/scripts/build_site.py">`. `tests/check_site.py`
decides what is "published" by reading that marker, and `tests/check_derived.py` applies its orphan
rule to every page carrying it. The practical effect is that the 9 root-level decision pages written
by the second generator are checked as published pages — which is why they must keep a source link in
every table row and stay linked from the navigation.

**Not changed by this session** (different owners): the marker should name the generator that wrote
the page. Logged here as a cross-session request.

### IR-08 — 28 pages outside the published build have no per-row source column *(open — carried forward)*

`tests/check_site.py` reports 28 pages that are link-checked only. They are sibling workspaces whose
generators were not rewritten by their owners. This is the same item as FL-DD-16 in the Decision
Desk register; it is listed again here so the integration view is complete.

### IR-09 — Two independent builds of the same decision desk, and two of the same suggestions hub *(open — carried forward)*

`site/` (the generator of the root `pages/decision-*` set), `decision-desk/`, `decision-hub/` and
`suggestions/` all answer "what do we know and what is missing", and `pages/suggestions.html` and
`pages/decision-hub.html` duplicate the `suggestions/` and `decision-hub/` hubs. This session linked
all of them from the Workspaces page and did not delete, merge or edit any of them; choosing one
canonical desk is a decision for the reviewer (carried in the decision-hub register as S-13).

### IR-10 — The committed game file contains the unplayed 2026 schedule *(open — noted)*

`data/derived/games.csv.gz` has 7,548 rows, of which 152 are 2026 games with no score (the
schedule through 2027-01-10). The site discloses the split ("7,548 games, 7,396 played"), and every
model figure filters to played games, so no number is affected. It is recorded because a reader who
counts rows in the file will get 7,548 rather than the 7,396 the analyses use.

---

## 4. The site after the integration pass

| Page | Purpose |
|---|---|
| `index.html` | landing page: six headline cards, the five findings, the workspace directory, the decision-support entries |
| `pages/workspaces.html` | **new** — the map of all 17 workspaces, their contents, page counts, review pages and open-item counts |
| `pages/executive.html` | one-page summary with every number classed |
| `pages/lines.html`, `pages/props.html`, `pages/correlation.html` | the originated lines, the player props, the measured correlations |
| `pages/strategies.html`, `pages/validation.html`, `pages/leaderboard.html` | the strategies, the ten gates, the leaderboard and the reward schedule |
| `pages/luck.html` | the luck decomposition, with the identity relabelled (IR-01) |
| `pages/market.html` | the closing-market benchmark every strategy is judged against |
| `pages/verification.html` | the 2026-11-02 verification record **and** the 2026-11-13 integration recomputation |
| `pages/method.html`, `pages/sources.html` | method and the source register |
| `pages/flagged.html` | the root items, the whole-site review queue (IR-06) and the unverified-values policy |
| `pages/decision-*.html` | the decision layer: summary, questions, suggestions, injury and depth, signal lab, parlay pricing, re-verification |
| `pages/archive.html` | the earlier drafts, preserved |

Navigation groups: **Research** (10 entries) → **Decide** (8) → **Evidence** (6).

---

## 5. Live re-checks against official sources (2026-11-13)

| # | Official page | What was read | Verdict |
|---|---|---|---|
| 1 | [NFL.com — 2026 division standings](https://www.nfl.com/standings/division/2026/REG) | W-L-T and PF-PA for all 32 teams | transcribed in full; 137 games played |
| 2 | [NFL.com — official injury report](https://www.nfl.com/injuries/) | page title and week selector: Week 10; games dated 2026-11-12 and 2026-11-15; the report shows Washington 3-5-1 and New York 5-3-1, matching the standings rows | confirmed |
| 3 | [NFL.com — Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) | Commanders 24, Giants 21 final on Thursday 2026-11-12; the remaining games Sunday 2026-11-15 | confirmed |
| 4 | [NFL.com — 2026 schedule announcement](https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced) | 18-week, 272-game regular season | confirmed (source register entry `SRC-NFL-SCHED-2026`) |
| 5 | [NFL.com — rules and officiating, 2026 rulebook](https://operations.nfl.com/rules-officiating/2026-nfl-rulebook) | current rulebook URL | confirmed; the 2025 URL that 404s is named in the flag register |

The full official source register for the site is
[data/sources.json](../data/sources.json); each entry states who opened it and when.

---

## 6. Open items this session could not close

| Item | Why it is still open | Where it is published |
|---|---|---|
| Historical prop prices, opening lines with timestamps, verified execution access, funded reward pool | no official source provides them | [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) |
| Injury/depth feature | no official depth order, and no point-in-time injury history is ingested | [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html), decision-hub injury pages |
| The 2012-2026 extract window (IR-03) | needs a pipeline re-run against the wider extract | [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) |
| The stale snapshot (IR-04) | needs a pipeline refresh; the committed data ends 2026-11-01 | [Flagged for review](https://karagemop466-tech.github.io/Korea2/pages/flagged.html) |
| Generator marker (IR-07) and duplicate desks (IR-09) | owned by other sessions | this document, and the review queues of those sessions |

---

## 7. Cross-session requests (logged, not edited)

1. **`site/scripts/build_site.py`** — stamp the pages it writes with its own generator marker
   (IR-07), so ownership is unambiguous.
2. **`site/` and `decision-desk/`** — the two decision-desk builds publish overlapping questions and
   suggestions; pick one canonical desk or state the difference (IR-09).
3. **The `suggestions/` and `decision-hub/` hubs** — they duplicate `pages/suggestions.html` and
   `pages/decision-hub.html`; the duplicate rows are flagged for the reviewer (IR-09).
4. **`docs/EXECUTIVE_SUMMARY.md` owners** — the "48 of 49" and "45 PASS + 3 expected + 1 INFO"
   phrasings across the workspaces are now unified to "49 checks: 45 strict equality checks agree,
   0 disagree, 11 observations" (this is the FL-DD-19 item).
5. **Sibling generators** — add a per-row source column to the 28 pages that do not have one
   (IR-08 / FL-DD-16).

---

## 8. Checks run on the merged tree

```
python3 scripts/build_site.py              # 16 pages written from data/derived/*.json
python3 tests/check_site.py                 # 178 pages, 430 tables, 10,574 links - all checks passed
python3 scripts/check_links.py              # 3,633 local references - no broken internal links
python3 tests/check_derived.py              # 11 derived JSON files strict; 49 checks, 0 disagreements; 26 generated pages all linked
python3 scripts/validate_data.py            # 16 data files, all rows sourced, official domains only - PASS
python3 tests/check_data.py                 # 6 result files consistent; 32/32 teams verified; 0 of 5 strategies ranked
python3 verification/integration_recompute.py  # 45 checks: 41 match, 4 documented differences, 0 mismatches
```
