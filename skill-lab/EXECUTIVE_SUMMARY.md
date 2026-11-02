# NFL Skill Lab — Executive Summary

**Verification Date:** `2026-11-02 UTC`  
**Live Dashboard:** `skill-lab/index.html` (`https://karagemop466-tech.github.io/Korea2/skill-lab/`)  
**Scope:** NFL Line & Prop Origination · Signal Discovery · Skill vs. Luck Decomposition · Gaussian-Copula Parlay/SGP Pricing · 10-Gate Strategy Competition · Line-by-Line Repository Audit

---

## 1. Bottom-Line Verdict

Across **2,247 out-of-sample regular-season NFL games with 100% recorded closing odds (`2018–2026`)**, **260,520 player-week logs**, **10 candidate pre-kickoff signals**, **14 empirical correlation pairs**, and **16 tournament strategies** spanning Single Bets, Cross-Game Parlays, Same-Game Parlays (SGPs), and Ex-Ante Player Prop Combos:

- **0 of 16 strategies pass all 10 validation gates (`G1–G10`)**, and **0 of 10,000 paper competition points** are awarded.
- **Why apparent raw winners fail:** High-wind outdoor unders (`STR-04` / `SIG-08`, `56.58%` win rate, `+9.20%` raw ROI, `n = 152`) and 2-leg wind-under parlays (`STR-08`, `+34.88%` raw ROI, `n = 63`) do not survive Benjamini-Hochberg False Discovery Rate (`q = 0.4786` across 10 tested signals) and shrink to **`-3.13%`** and **`-3.93%`** after Empirical Bayes luck removal.
- **Why positive controls prove gate integrity:** Our deliberate in-game turnover leak control (`STR-16`, `85.14%` hit rate, `+64.81%` ROI) passes 8 statistical gates on brute return alone—and is **automatically disqualified (`score = 0.0`, Rank `#16`) by Gate `G1` (Point-in-Time / Zero-Lookahead Audit)**.
- **Zero-hallucination enforcement:** Because no free official archive of historical sportsbook player-prop odds or proprietary SGP correlation haircuts exists (`SL-SRC-16`, `SL-SRC-20`), `STR-10..STR-14` report verified box-score joint hit rates and Gaussian-copula calibration while leaving ROI cells **strictly blank (`""`)** and holding at Gate `G10`.

---

## 2. Key Quantitative Findings

### A. Official `NFL.com` Data Verification (`64/64` Team-Seasons + `7/7` Players Exact)
- **2025 Regular Season (272 games):** `32/32` teams match official [NFL.com 2025 Standings](https://www.nfl.com/standings/league/2025/REG) on W-L-T, PF, and PA.
- **2026 Regular Season through Nov 1 Week 8 (120 settled games; MNF `CHI @ SEA` unplayed Nov 2):** `32/32` teams match official [NFL.com 2026 Standings](https://www.nfl.com/standings/league/2026/REG) (`BUF`, `MIN`, `SF` at `6-1`; `LAC` at `0-7`), and `7/7` audited player stat pages (`Love`, `Allen`, `Burrow`, `Goff`, `Chase`, `St. Brown`, `Cook`) reconcile to the single yard and touchdown.

### B. Walk-Forward NFL Line & Player-Prop Origination (`originate.py`)
- **Team Spreads, Totals & Moneylines (`2018–2026`, `N = 2,247`):** Expanding-window opponent-adjusted power ratings blended with turnover-shrunk play-by-play EPA achieve **`10.265` spread MAE** vs. closing market **`9.825`**, **`10.428` total MAE** vs. **`10.262`**, and **`0.2202` Brier** vs. **`0.2116`**.
- **Live Ex-Ante Grading on 12 Official Nov 1, 2026 Week 8 Finals:** Originated spreads achieved **`10.54` MAE** vs. closing market **`10.58`** (`7–5` directional leans; explicitly treated as `N = 12` single-Sunday noise, `p > 0.50`).
- **2026 Week 9 Originated Slate & Player Props:** Publishes fair spreads, totals, and moneylines for all 15 official Week 9 fixtures (plus Week 8 MNF `CHI @ SEA`) and quantile-calibrated (`P25 / P50 / P75`) QB/WR1/RB1 prop lines achieving `49.1%–50.6%` out-of-sample median symmetry across `5,494` player-games.

### C. Separating Skill from Luck (`signals_and_luck.py`)
- **Year-over-Year Persistence (`317` consecutive club pairs, `2015–2025`):**
  - **Repeatable Skill:** Point Differential/Game (`r = +0.4097`), Passing EPA/Dropback (`r = +0.4016`), CPOE (`r = +0.3890`), Offensive EPA/Play (`r = +0.3774`).
  - **Mean-Reverting Luck:** Net Turnovers/Game (`r = +0.1524`, **`84.8%` luck shrinkage**), One-Score Win % (`r = +0.0810`, `p = 0.150`, **`91.9%` luck**), Pythagorean Luck (`r = +0.0232`, `p = 0.681`, **`97.7%` luck**), Team ATS Cover % (`r = -0.0142`, `p = 0.802`, **`100.0%` luck**).
- **2025 → 2026 Realized Proof:** Severe 2025 close-game bad-luck clubs **`KC`** (`6-11`, `-3.49` luck wins) and **`NYG`** (`4-13`, `-3.09` luck wins) rebounded to **`5-2`** and **`4-2-1`** through Week 8 on official `NFL.com` 2026 standings.

### D. Empirical Correlations & Ex-Post WR1 Selection Bias (`correlations.py`)
- **Ex-Post vs. Ex-Ante Discovery (`N = 6,984` team-games):** Defining WR1 *ex-ante* by prior target share yields within-player residual correlation **`r = +0.3723`** (`copula rho = +0.4001`, `1.237x` joint-hit boost). Defining WR1 *ex-post* by who led the game in receiving yards inflates correlation to **`r = +0.6135`** (**`+0.2412` lookahead bias**).
- **Key SGP & Prop Pairs:** QB 2+ Pass TDs ↔ Ex-Ante WR1 Anytime TD (`r = +0.4571`, `copula rho = +0.5584`, `1.570x`), QB1 Pass Yds ↔ Game Over (`r = +0.2968`, `1.196x`), RB1 Rush Yds ↔ Team Cover (`r = +0.2811`, `1.202x`), RB1 Rush Yds ↔ QB1 Pass Attempts (**`r = -0.1672`**, anti-correlated `0.885x` trap), Cross-Game Same-Week ATS (`r = +0.0104`, independent).
- **Out-of-Sample 3-Leg Copula Calibration (`STR-14`, `N = 389` games):** Realized joint hit rate for `Team QB1 + Team WR1 + Opposing QB1` passing/receiving overs is **`16.71%`** vs. **`16.20%`** Gaussian-copula forecast (`0.51%` calibration error) and `12.50%` naive independence.

### E. Line-by-Line Repository Review Takeaways (`repo_audit.py`)
- Flagged and documented `data/standings_2020.csv` conflating regular-season and playoff games (`KC 16-3` vs official `14-2` REG) + `OAK` code, `1,902` pre-2018 unpriced spread rows where root `scripts/analyze_strategies.py:50,66` still imputes `-110`, triple executive-summary drift across root/docs, and ex-post WR1 inflation—preserving every sibling file untouched per `COORDINATION.md` rules.
