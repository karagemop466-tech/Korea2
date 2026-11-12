# Lineup Lab — Executive Summary

**Repository:** `karagemop466-tech/Korea2` (`lineup-lab/`)  
**Verification Snapshot:** `2026-11-12` (committed extracts through `2026-11-01` Week 8 + live `NFL.com` reconciliation through 2026 Week 9 & Week 10 Wednesday practice reports)  
**Capital Allocation Posture:** **DO NOT DEPLOY LIVE CAPITAL (0 of 8 strategies approved across 10 validation gates)**

---

## 1. Core Empirical Conclusions

1. **Closing Markets Beat Pure Statistical Origination (`2023–2026` Walk-Forward OOS):**
   - Pure-Python Ridge ($L_2$, $\alpha=25$) trained strictly on prior seasons (`2016..(t-1)`) achieves **10.284 pts** spread MAE vs **9.737 pts** for stored closing spreads (**9.897** 50/50 blend) and **10.473 pts** total MAE vs **10.161 pts** closing totals.
   - Regressing closing-line residuals (`actual_margin - market_spread`) on model-vs-market edge yields slope **$\beta = -0.1453$** (`SE = 0.1205`, `t = -1.21`, **`p = 0.2280`**, $R^2 = 0.0017$): the statistical team-EPA model adds **no reliably exploitable information** beyond the closing spread.

2. **Zero Strategies Survive All 10 Validation Gates (`2018–2026 Wk 8`, `n = 2,247` games with 100% Stored Odds):**
   - Using strictly stored closing prices (median `-108 / -108`, mean implied probability `51.7%`; zero `-110` imputation), **0 of 6** signal strategies and **0 of 2** negative controls clear the 10-gate filter:
     - Top raw performers **`S3_HIGH_WIND_UNDER`** (`+9.20%` raw ROI, `56.58%` wins, `n = 152`) and **`S1_DIV_DOG`** (`+5.36%` raw ROI, `54.93%` wins, `n = 335`) both fail **NIST 7.2.4 z-test** (`p = 0.2205` and `p = 0.2954`), **Benjamini-Hochberg FDR** (`q = 0.4370`), and **Empirical Bayes shrinkage** (`-2.79%` and `-2.14%`).
     - Negative controls behave identically to economic theory: **`C1_CTRL_HOME_FAV`** loses **`-8.42%`** (`z = -2.80`), and **`C2_CTRL_COIN_FLIP`** wins **`49.75%`** with **`-3.81%`** ROI (matching the ~3.4% market vig).

3. **Backup QB & Skill-Absence Cascades Cause Steep Scoring Drops—Already Priced at Close:**
   - **Within-season ex-ante backup QBs (`2015–2026 Wk 8`):** Incumbent QB1 starts (`n = 4,263`) average **`23.60 PPG`** (`+2.27` passing EPA); all backup starts (`n = 976`) drop to **`19.49 PPG`** (`-4.11 PPG`); **inexperienced backups `< 5` career starts (`n = 438`) plunge to `18.13 PPG` (`-5.47 PPG`, `-4.32` passing EPA)**—yet still cover only **`48.47%` ATS** (`-1.17` margin vs spread).
   - **Ex-ante `WR1`/`RB1`/`TE1` absences:** Team scoring drops `-2.26 PPG` when `WR1` sits (`n = 292`), `-1.08 PPG` when `RB1` sits (`n = 401`, active `RB2` absorbs **`+5.85` carries/gm**), and `-0.55 PPG` when `TE1` sits (`n = 229`).
   - **Defensive/OL gap (`FL-04`):** `125,679` `DB`/`DL`/`LB`/`OL` rows in `player_week.csv.gz` are **99.75% zero/empty** (`0` snap percentages), leaving individual defender historical dropoffs strictly blank (`""`). Observable team-level trench collapses (`sacks_suffered` spike: `-5.64 PPG` scored; `def_sacks` collapse: `+3.98 PPG` allowed) quantify aggregate risk instead.

4. **Skill vs. Luck Decomposition Explains 2026 Standings Outliers (`2015–2025` Split-Half):**
   - Split-half persistence (`Weeks 1–8` vs `Weeks 9–18`, `n = 352` team-seasons) cleanly separates repeatable skill (`Net EPA/gm` **`r = 0.4908`**, `Passing EPA/gm` **`r = 0.4797`**) from pure randomness (`Fumbles lost/gm` **`r = 0.0079`**, `1-score win%` **`r = 0.0497`**, `Win% - Pythagorean Win%` **`r = 0.0593`**).
   - Entering 2026 Week 10, **`DEN` (`7-2`, `6-0` in 1-score games, `-0.32` Net EPA/gm)** runs **`+2.17` luck wins** above Pythagorean expectation, while **`TB` (`3-6`, `0-6` in 1-score games, `+3.66` Net EPA/gm)** runs **`-2.17` wins** below expectation. Yet standalone blind luck-fading (`S4_LUCK_FADE`) lost `-6.45%` ROI because market spreads already discount standings noise.

5. **Same-Game Correlations Are Real, Yet Books Price Them Into SGP Quotes:**
   - Across `4,482` team-games (`2018–2026 Wk 8`), `QB passing yards <-> WR1 receiving yards` correlates at **`r = 0.5640`** (`34.54%` bivariate Gaussian copula 2-leg joint probability = **`+190` fair** vs naive `+300`), and `RB1 rushing yards <-> team margin` correlates at **`r = 0.3372`** (`30.47%` = `+228` fair). Because sportsbooks embed correlation haircuts (`DraftKings KB0010683`), copula pricing serves as an execution price filter rather than an automatic parlay edge.

---

## 2. Live 2026-11-12 Verification & Data Hygiene Findings

- **Official Standings Reconciliation:** Adding the **16 official `NFL.com` finals** (`Week 8 MNF + 15 Week 9 games`) to the 120 played `games.csv.gz` rows matches **32 / 32** teams' exact `W-L-T` and `PF/PA` on `nfl.com/standings/league/2026/REG` (plus **32 / 32** on `2025` and `2020`).
- **Live `NFL.com` REG10 Injury Feed Omissions:** On `2026-11-12`, `/injuries/league/2026/REG10` prints `"No Injuries Reported"` for **`SEA`, `CIN`, `BAL`, and `LAC`**, contradicting the official Nov 11 `NFL.com` roundup (12 `SEA` injuries including `Sam Darnold` Out + 4 trench starters DNP; 3 `CIN` injuries) and IR wire (`BAL` QBs `Lamar Jackson` & `Tyler Huntley` on IR).
- **9-Club Depth-Chart Audit Defects:** All 9 audited club depth charts carry `"unofficial"` disclaimers and severe maintenance defects—including **`LA` listing retired `Aaron Donald` at DE1**, **`GB` omitting `Micah Parsons`**, **`DET` omitting `Kerby Joseph`**, **`BAL` omitting `Jacoby Brissett` / `Joe Fagnano`**, **`MIA` leaving `QB2–4` & `K` blank** ahead of `Kyle McCord`'s first NFL start, **`WAS` omitting `Greg Van Roten` & `Tim Patrick`**, and **`SEA` omitting `Quenton Nelson`**.
- **Repository & Pipeline Audit (`REV-01`..`REV-16`):** Documented non-destructively in `REPO_REVIEW.md`, including silent `-110` imputation in `scripts/analyze_strategies.py:50,66`, contaminated 2020 data in `data/standings_2020.csv`, broken CI path/season assertions in `.github/workflows/fetch-nflverse.yml`, and orphaned root decision pages.

---

## 3. Recommended Posture Before Any Next Step

1. **Maintain 0% live capital deployment** until an opening-line timestamped odds feed and historical player-prop closing lines (`GAP-01`, `GAP-03`) are archived.
2. **Build a dual-feed injury & roster reconciler (`SUG-01`, `SUG-02`)** uniting `REG10`, daily practice roundups, transaction/IR logs, and Rule 19-2 T-90m inactive lists rather than relying on club depth-chart HTML.
3. **Ingest weekly defensive/OL snap counts (`SUG-03`)** so future Week 10+ clusters (like `IND`'s 4 DNP defenders, `PIT` Watt/Heyward, `SF` Williams/Lenoir, `LA` McDuffie/Curl) can be modeled quantitatively instead of left blank.
