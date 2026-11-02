# Line-by-Line Repository Review (`karagemop466-tech/Korea2`)

**Verification Date:** `2026-11-02 UTC`  
**Reviewer Session:** `arena/2b9898f7-korea2`  
**Policy:** Read-only inspection of shared/sibling directories; zero sibling files overwritten; unverified values left strictly blank (`""`).

---

## 1. Official `NFL.com` Reconciliation Summary

| Dataset / Check | Scope Audited | Result | Official Primary Source |
| --- | --- | --- | --- |
| **2026 Regular-Season Standings** | All 32 clubs across 120 settled games thru Sunday Nov 1, 2026 (MNF `CHI @ SEA` unplayed Nov 2) | **32 / 32 Exact Match** on W-L-T, PF, PA | [NFL.com 2026 Standings](https://www.nfl.com/standings/league/2026/REG) |
| **2026 Week 8 Schedule & Finals** | Oct 29 TNF (`CAR 19 @ GB 27`), 12 Sunday Nov 1 finals (incl. `BAL 10 @ BUF 36` at Highmark), Nov 2 MNF (`CHI @ SEA`) | **13 / 13 Settled Finals Exact**, 1 Unplayed MNF left blank | [NFL.com 2026 Week 8 Schedule](https://www.nfl.com/schedules/2026/by-week/week-8) |
| **2026 Week 9 Upcoming Slate** | All 15 fixtures (Nov 5 `JAX @ BAL` through Nov 9 `BUF @ MIN`, incl. Madrid neutral `CIN @ ATL`; Byes `PIT`, `TEN`) | **15 / 15 Fixtures Verified** | [NFL.com 2026 Week 9 Schedule](https://www.nfl.com/schedules/2026/by-week/week-9) |
| **2025 Completed Regular Season** | All 32 clubs across all 272 regular-season games | **32 / 32 Exact Match** on W-L-T, PF, PA | [NFL.com 2025 Standings](https://www.nfl.com/standings/league/2025/REG) |
| **2026 Player Season & Wk 8 Logs** | Jordan Love (`2,246 / 15`), Josh Allen (`1,781 / 14`), Joe Burrow (`2,160 / 18`), Jared Goff (`1,731 / 18`), Ja'Marr Chase (`768 / 5`), Amon-Ra St. Brown (`636 / 6`), James Cook (`808 / 6`) | **7 / 7 Exact Yard & TD Match** | [NFL.com Player Stats](https://www.nfl.com/players/josh-allen/stats/) |
| **`data/standings_2020.csv` Audit** | 32 rows in sibling `data/standings_2020.csv` vs. official 16-game 2020 REG standings | **IRREGULARITY FLAGGED:** CSV mixed playoff games into REG (`KC 16-3` vs `14-2`, `BUF 15-4` vs `13-3`) and printed `OAK` for `LV` | [NFL.com 2020 Standings](https://www.nfl.com/standings/league/2020/REG) |

---

## 2. Line-by-Line Subsystem Audit (`REV-01` – `REV-14`)

| ID | Repository Path | Lines / Rows | Verdict | Finding & Manual-Review Link |
| --- | --- | --- | --- | --- |
| `REV-01` | `data/derived/games.csv.gz` | 7,548 rows | `VERIFIED_32_OF_32` | 2025 REG (272 games) and 2026 REG thru Nov 1 (120 games) reconcile 32/32 against [NFL.com](https://www.nfl.com/standings/league/2026/REG). |
| `REV-02` | `data/derived/games.csv.gz` & `scripts/analyze_strategies.py:50,66` | 1,902 rows | `IRREGULARITY_FLAGGED` | 1,902 pre-2018 spread rows lack `home_spread_odds`/`away_spread_odds`; root `scripts/analyze_strategies.py` lines 50 & 66 still impute `DEFAULT_AMERICAN` (`-110`). Skill Lab excludes unpriced rows rather than imputing. ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-03` | `data/standings_2020.csv` & `nfl-lines/data.html` | Lines 1–33 | `IRREGULARITY_FLAGGED` | Sums postseason games into regular-season standings (`KC 16-3`, `TB 15-5`) and labels relocated Las Vegas Raiders as `OAK` vs. [NFL.com 2020 REG](https://www.nfl.com/standings/league/2020/REG). |
| `REV-04` | `README.md`, `EXECUTIVE_SUMMARY.md`, `docs/EXECUTIVE_SUMMARY.md` | 3 files | `IRREGULARITY_FLAGGED` | Three executive summaries describe three distinct session builds (`7` strategies / `10` gates, `5` strategies / `6` gates, and `9` framework specs / `8` gates). ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-05` | `scripts/analysis/build_site.py` | Line 608 | `FIXED_ON_MAIN` | Issue #34 (`jload('provenance.json')` wrong path + clobber hazard) verified and guarded in `397f3cd`. ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-06` | `results/correlations.json` & `origination/site_data/correlation.json` | QB–WR1 rows | `IRREGULARITY_FLAGGED` | Ex-post selection of in-game leading receiver inflates QB–WR1 correlation to `+0.6135`; strictly ex-ante target-share WR1 yields `r = +0.3723` (`n = 6,984`). ([scikit-learn Pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)) |
| `REV-07` | `origination-lab/` | 15 HTML pages | `PARTIAL_SOURCE_FLAGS` | Issue #32 push-rate signs & copula calibration updated in `397f3cd`, while `audit/check_site.py` still flags non-primary row citations. ([Cornell Probability](https://courses.cit.cornell.edu/info295_2006fa/l4-5.pdf)) |
| `REV-08` | `quant-lab/` | 12 HTML pages | `VERIFIED_WITH_NOTES` | Issue #24 G9 multi-leg repricing updated in `397f3cd`; `0/21` strategies qualify. ([DraftKings Parlay Rules](https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010683)) |
| `REV-09` | `dashboard/` & `data/*.json` | 10 HTML pages | `VERIFIED` | `scripts/validate_data.py` passes with 55 official sources and blank flagged values. ([NFL Week 8 Schedule](https://www.nfl.com/schedules/2026/by-week/week-8)) |
| `REV-10` | `nfl-research/` & `research-desk/` | 12 HTML pages | `VERIFIED_FRAMEWORK` | Correctly labels candidate rules as unvalidated framework specifications. ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-11` | `index.html` & `pages/*.html` | 15 HTML pages | `VERIFIED_WITH_NOTES` | `tests/check_site.py` and `tests/check_derived.py` pass (`49` checks, `0` disagreements); `index.html` has 5 non-primary source flags in `audit/check_site.py`. ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-12` | `.github/workflows/` | 5 workflows | `VERIFIED` | Issue #20 fail-closed PR refresh implemented in `397f3cd`; `skill-lab.yml` uses `contents: read` only. ([Repo](https://github.com/karagemop466-tech/Korea2)) |
| `REV-13` | `data/derived/player_week.csv.gz` | 260,520 rows | `VERIFIED_7_OF_7` | Exact yard and TD match across all 7 audited 2026 `NFL.com` player stat pages. ([NFL.com Jordan Love](https://www.nfl.com/players/jordan-love/stats/)) |
| `REV-14` | `skill-lab/` (this build) | 12 HTML pages | `VERIFIED_ZERO_FLAGS` | `335/335` table rows linked to `32` official primary sources; `0` flags in `audit/check_site.py`; `77` strictly empty unverified cells. ([NFL.com](https://www.nfl.com/standings/league/2026/REG)) |

---

## 3. Unverified Items Left Strictly Blank (`FLG-01` – `FLG-05`)

| ID | Unverified Item | Verified Value | Official Manual-Review Link |
| --- | --- | --- | --- |
| `FLG-01` | Historical NFL Player Prop Closing Lines & Vig (`STR-12..14`) | | [NFL / Genius Sports Partnership](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports) |
| `FLG-02` | Sportsbook Proprietary SGP Correlation Haircut Matrix (`STR-10..11`) | | [DraftKings SGP Rules KB0010719](https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010719) |
| `FLG-03` | Opening-Line Timestamps & Multi-Book CLV Archive | | [DraftKings NFL Spread Rules KB0010595](https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010595) |
| `FLG-04` | Funded Cash Leaderboard Treasury & Sportsbook Execution Limits | | [NFL Big Data Bowl Benchmark](https://edge-operations.nfl.com/programs-initiatives/innovation/big-data-bowl) |
| `FLG-05` | 2026 Week 8 MNF Final Score (`CHI @ SEA`, Nov 2 8:15 PM ET — Unplayed) | | [NFL.com 2026 Week 8 Schedule](https://www.nfl.com/schedules/2026/by-week/week-8) |
