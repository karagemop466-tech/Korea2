# Executive summary — Decision Hub

**Live site:** <https://karagemop466-tech.github.io/Korea2/decision-hub/>
**Session:** `arena/7dbbeba6-korea2` · **Date:** 2026-11-12 · **Data as of:** gameday 2026-11-01 (games),
injury report snapshot 2026-11-12

This session did two things: it **audited the existing site line by line** from an independent
implementation, and it added the **decision layer the project was missing** — a suggestion register,
a questions register that separates what is known from what is assumed, the three decisions that
gate everything else, and the **first injury/depth tracker** in the repository.

---

## 1. Bottom line

| Question | Answer | Evidence |
|---|---|---|
| Does the model beat the closing line? | **No** | increment coefficient −0.019 (p = 0.881); MAE 10.39 vs 10.25 |
| Did any strategy pass the ten gates? | **No — 0 of 7** (and both controls fail) | `data/derived/leaderboard.json` |
| Are the published numbers reproducible? | **Mostly — 22 of 24 audit checks** | `decision-hub/data/root_audit.json` |
| Is the headline ATS result real? | **No — it is an arithmetic identity** | FL-DH-01, this session |
| Is injury/depth now tracked? | **Yes — 636 absences ranked** | `decision-hub/data/injuries.json` |
| Does depth loss move the line? | **Not measured** | Q-04 blocked on price data |
| What should be done first? | Fix the ATS statistic, class every row, then decide D-01 | suggestions S-02, S-01, decisions |

**The single most important finding of this session:** the site's headline "ATS coin-flip test —
50.0%, p = 1.0" is not a test. The sample pools every game twice, once as `+x` and once as `−x`, so
exactly half the rows are positive for *any* dataset. The rate and the p-value are identities. It is
presented on the overview, the luck page and the executive summary as evidence that the spread
market cannot be beaten. The honest one-observation-per-game number is **48.91% home covers, 95% CI
47.73–50.09%, p = 0.073 on 6,892 decided games** — inconclusive, not zero.

---

## 2. What was verified, and how

`decision-hub/scripts/audit_root.py` is a second implementation that **imports nothing from the
root pipeline**. For each published number it records the published value, its own recomputation,
the tolerance, and a verdict.

| Result | Count |
|---|---|
| Checks | 24 |
| Reproduced exactly | 22 |
| Failed | 0 |
| Unverifiable with committed data | 2 |
| Flags raised | 7 (1 high, 4 medium, 2 low) |
| Table rows on the published site | 862 across 25 pages |
| Rows without a source link | 7 (all on the archive index) |

Reproduced: game counts (7,548 / 7,396 / 7,087), as-of date, closing spread MAE (10.25), total MAE
(10.62), 2023+ MAE (9.71), regression slope (1.049 vs a published 1.05), the sign-convention cover
rates (0.4891 and 0.6003), leaderboard counts, and the project's own 49-check verification record
(0 failures, 0 mismatches).

Unverifiable from committed data: the one-sided ATS rate (not published at all) and the walk-forward
prediction count (936 rows exist; no published value to compare against).

---

## 3. The flags

| ID | Severity | Item |
|---|---|---|
| FL-DH-01 | **high** | The ATS coin-flip test cannot fail — pooled ±x construction |
| FL-DH-02 | medium | The sign diagnostic compares two formulae, not two hypotheses |
| FL-DH-04 | low | Published correlation sample (n=7,560) does not reproduce (6,024) |
| FL-DH-05 | medium | The cited injury-policy URL returns 404; the *data* source is fine |
| FL-DH-06 | medium | No code anywhere joined injuries to a depth chart (fixed this session) |
| FL-DH-03 | low | Leaderboard gate-detail completeness |
| FL-DH-07 | low | Rewards are a schedule, not a funded pool |

FL-DH-01 is the one that changes a conclusion. The others are disclosure and maintenance.

---

## 4. The injury and depth tracker (new)

The requirement — *know when a defence or offence is on its 2nd, 3rd or 4th string* — was described
in prose but implemented nowhere. It is now built from two sources and refreshed by a scheduled
workflow:

* **Official injury report** (`nfl.com/injuries/`, read 2026-11-12: Week 10 of the 2026 season),
  mirrored in a stable CSV by nflverse: 3,075 rows for 2026.
* **Club depth charts** (nflverse 2026 release, 74 MB, 777,815 rows, 291 snapshots; newest snapshot
  used: `2026-11-12T07:01:31Z`).
* **Snap counts and weekly rosters** to show how much the next man up actually plays.

`pos_rank` in the depth-chart feed is documented as *rank grouped by pos_slot*, so it is used
directly as the depth rank (1st string = 1, 2nd = 2 …). Two players who share the same slot and
rank are labelled a tie rather than given an invented order. Everything else is a measurement:

* 636 reported absences (Out or Doubtful) in 2026; 614 with a depth rank; 22 with none, counted as
  `rank_unknown` rather than guessed.
* 296 team-weeks; 32 teams; 24 teams have a week-10 report at the snapshot, the rest are on week 9
  or have not filed — published per team, not imputed.
* **Weighted depth lost** = Σ 1/rank over absences with a known rank. Seattle leads the current
  report (6.00: 5 starters out, including QB Sam Darnold → Drew Lock at 2nd string).
* Positions where the best available player is a backup: RG at New England (3rd string), LCB at
  New England (2nd string), QB at Seattle (2nd string), SLB at Seattle (2nd string).

**What it does not claim:** that a backup will play, or that he is worse. The effect on the line has
never been measured here (Q-04), and the depth chart can lag a transaction.

---

## 5. Suggestions — the reviewable list

Fourteen suggestions, each with impact, cost, risk and the decision it unblocks. The low-cost,
high-impact set to do first:

1. **S-02** (1 day) — replace the ATS identity with the one-sided test. Fixes a headline that
   cannot fail.
2. **S-01** (2 days) — class every table row as *official fact / computed / proposal*. The site
   already classifies its sources; only the per-row label is missing.
3. **S-05** (done) — this questions register.

Then the medium-cost work, in the order the evidence supports:

* **S-03** (15 days, blocked on Q-05) — closing-line value as the headline skill metric. ROI needs
  ~300 bets to say anything; CLV needs far fewer.
* **S-04** (in progress) — the depth tracker, followed by the only test that matters: does depth
  loss predict the residual of the result on the close, out of sample?
* **S-07** (3 days) — make the build fail when a published number does not reproduce. Five values
  currently "differ as expected"; that should be a red check.

---

## 6. What must be answered before deciding

Sixteen questions, sorted by how many decisions each blocks. The blocked ones are the honest gaps:

| Question | What is missing | Cost to answer |
|---|---|---|
| Q-05 Timestamped price | No opening line, no timestamp, no prop price; no licensed access | vendor quote unknown |
| Q-06 Injury policy text | cited URL 404s | 1 hour to check, unbounded to obtain |
| Q-12 Prop ROI | no historical prop prices | vendor quote unknown |
| Q-04 Effect of a missing starter | needs Q-05 first | 5 days after Q-05 |
| Q-14 Does depth rank match who plays? | data now exists to test it | 3 days |
| Q-15 Cost of acquisition | no quotes requested | 3 hours to request |

The three decisions that gate everything: **D-01** measurement vs picks, **D-02** rank vs cash
prize, **D-03** which weakness to attack first. Each has the evidence for and against, and the
recommendation the measurements point to — measurement only, rank only, and price data first.

---

## 7. Sources

Official: the NFL injury report (live and the dated week-10 URL), the NFL rulebook, NFL.com
standings. Regulator: Massachusetts Gaming Commission filings for the operator rulebook. Statistics:
NIST handbooks for correlation, sample size, and multiple comparisons; Benjamini–Hochberg 1995;
Kelly 1956. Community mirror: nflverse releases, used with SHA-256 hashes recorded, and never called
an official NFL publication.

Full register with confirmation notes: `decision-hub/pages/sources.html`.
Unconfirmable items: `decision-hub/pages/flagged.html`.

---

## 8. Verification performed in this session

* `python3 decision-hub/scripts/audit_root.py` → 24 checks, 22 pass, 0 fail, 2 blank, 7 flags.
* `python3 decision-hub/scripts/build_site.py` → 12 pages, byte-stable on re-run.
* `python3 decision-hub/scripts/check_site.py` → 12 pages, 39 tables, **714 of 714 rows carry a
  source link**, every internal link and anchor resolves.
* `python3 scripts/build_site.py` → root site rebuild unchanged except the added nav entry.
* `python3 tests/check_site.py` → 109 pages, 290 tables, 5,124 links, all pass.
* `python3 tests/check_derived.py` → 11 strict-JSON files, 49 verification checks, 0 disagreements.
* Injury data built by GitHub Actions run `43225084442` (fetch-injuries) from four release assets,
  each hashed in the committed JSON.

**No value on the decision hub is typed by hand.** Every number is read from a committed JSON file
that a script produced.
