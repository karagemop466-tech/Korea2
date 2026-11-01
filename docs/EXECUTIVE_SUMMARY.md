# Executive Summary — NFL Line Origination & Skill-Based Strategy Project

**Date:** 2026-11-01 · **Branch:** `arena/29806afc-korea2` · **Repo:** `karagemop466-tech/Korea2`
**Verification standard:** every claim below is backed by an official source (link inline and in `data/sources.json`), checked on 2026-11-01. Anything not confirmable from an official source is left blank and published on the **Flagged for Review** page (`data/flagged.json`) — no inferred values.

## 1. Goal
Originate our own NFL betting lines (bottom-up, from raw official data) instead of following market lines; develop strategies that generate useful signals; run them as a **leaderboard competition with rewards for top performers**; cover **single bets, parlays, and player-prop combos**; require every strategy to pass **validation gates**; explicitly **determine correlation values** for combo bets; and **remove luck** by requiring statistical evidence of skill before any strategy is trusted.

## 2. What “originating our own line” means (verified definition)
An *originator* is someone who generates their own predictions and **"aims to originate their own lines using raw data and their own models"**, comparing their own probability against the sportsbook's implied probability to find value ([Pinnacle — Bottom-Up Betting / Originator](https://www.pinnacle.com/betting-resources/en/educational/bottom-up-betting-explained-what-is-an-originator-and-how-do-you-build-a-basic-model)). For NFL models, the same official guide names the required inputs: **player stats, team stats, injury reports, and weather data for outdoor games** — all available from official sources:

- Official player & team stats: [nfl.com/stats/player-stats](https://www.nfl.com/stats/player-stats/) · [nfl.com/stats/team-stats](https://www.nfl.com/stats/team-stats/)
- Official Next Gen Stats tracking (speed, separation, CPOE, EPA/success-rate explainers): [nextgenstats.nfl.com](https://nextgenstats.nfl.com/) · [operations.nfl.com NGS technology](https://operations.nfl.com/gameday/technology/nfl-next-gen-stats) · [NFL Pro FAQ](https://support.nfl.com/hc/en-us/articles/35869706651156-NFL-Pro-FAQ-s-and-Answers) (the NFL itself builds matchup-advantage scores from **success rate and EPA per play**)
- Official weekly injury report + policy deadlines: [nfl.com/injuries](https://www.nfl.com/injuries/) · [injury report policy](https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693) · [important dates](https://www.nfl.com/news/2026-27-national-football-league-important-dates)
- Official schedule/standings/rosters: [2026 schedule announcement](https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced) · [Week 9 schedule](https://www.nfl.com/schedules/2026/by-week/week-9) · [standings](https://www.nfl.com/standings/league/2026/reg) · [teams](https://www.nfl.com/teams/)
- Official weather (NOAA/NWS point forecasts): [forecast.weather.gov](https://forecast.weather.gov/MapClick.php?lat=40.7128&lon=-74.006)

## 3. Market mechanics we rely on (all verified against official sportsbook help / regulator)
- **Spread / moneyline / total / props / parlay / SGP / teaser definitions**: [DraftKings glossary](https://support.draftkings.com/dk/en-us/glossary-of-betting-terms?id=kb_article_view&sysparm_article=KB0010398) · [DraftKings parlay rules](https://support.draftkings.com/dk/en-us/what-is-a-parlay-bet?id=kb_article_view&sysparm_article=KB0010683) · [DraftKings prop definition](https://support.draftkings.com/dk/en-us/what-is-a-prop-bet?id=kb_article_view&sysparm_article=KB0010778) · [FanDuel terms](https://support.fanduel.com/s/article/Sports-Betting-Terms) (spread usually 11-to-10 = -110)
- **Parlay rule**: all legs must win; a push leg is removed and odds recalculated; correlated/"too closely related" selections may be restricted ([DraftKings](https://support.draftkings.com/dk/en-us/what-is-a-parlay-bet?id=kb_article_view&sysparm_article=KB0010683)); regulator definition of parlay card wager = 2+ games/contingencies ([Nevada Reg 22](https://www.gaming.nv.gov/siteassets/content/regs/regulation-22-as-of-1-26.pdf))
- **Grading**: wagers must be gradeable from official league records ([Nevada Reg 22](https://www.gaming.nv.gov/siteassets/content/regs/regulation-22-as-of-1-26.pdf)) → NFL official stats are the settlement source of truth
- **Odds → probability**: American odds conversion formulas and margin removal ([Pinnacle implied probability](https://www.pinnacle.com/en/esports-hub/betting-articles/educational/implied-probability-odds-conversion/72m2z3g3g22m5tps); [Pinnacle odds/margin](https://www.pinnacle.com/betting-resources/en/betting-strategy/betting-odds-explained-how-do-odds-work/qen2dcqrvncnv4jf)). At the standard -110, each side implies 110/210 = **52.38%** — the break-even win rate.

## 4. Removing luck — validation gates (all strategies must pass G1–G8)
1. **G1 Data integrity** — official sources only; unverifiable values blank + flagged.
2. **G2 Out-of-sample holdout** — train on past seasons, validate on a never-tuned future window; mirrors Kaggle's public/private leaderboard split and anti-leakage rules ([Kaggle docs](https://www.kaggle.com/docs/competitions)).
3. **G3 Skill-vs-luck significance** — one-proportion binomial z-test of win rate vs the price-implied break-even (52.38% at -110), p < 0.05 one-sided, N > 30 with min{N·p0, N(1−p0)} ≥ 5 ([NIST 7.2.4](https://www.itl.nist.gov/div898/handbook/prc/section2/prc24.htm)).
4. **G4 Minimum sample size** — N from the NIST proportion sample-size formula for the claimed edge ([NIST 7.2.4.2](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm)).
5. **G5 CLV gate** — positive average closing-line value on holdout; CLV is the accepted fast-converging skill metric ([Pinnacle CLV](https://www.pinnacle.com/betting-resources/en/educational/what-is-closing-line-value-clv-in-sports-betting)).
6. **G6 Multiple-comparison correction** — Bonferroni α/g across all tested candidate signals ([NIST 7.4.7.3](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm)).
7. **G7 Correlation & bankroll** — Pearson r (NIST formula + F(1,N−2) significance test) between parlay-leg signals; reject high-|r| or book-restricted (related contingency) pairs; fractional-Kelly staking ([Kelly 1956, Princeton-hosted original](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf); [Pinnacle Kelly article](https://www.pinnacle.com/betting-resources/en/betting-strategy/the-kelly-criterion-a-stock-trader-and-betting-experts-perspective/h8k2p3f2r8b7rzdp)).
8. **G8 Execution & settlement** — licensed books, posted propositions, settlement audited against official NFL stats ([Nevada Reg 22](https://www.gaming.nv.gov/siteassets/content/regs/regulation-22-as-of-1-26.pdf)).

## 5. Leaderboard competition with rewards
Modeled directly on official precedents: **Kaggle's public/private leaderboard** ([docs](https://www.kaggle.com/docs/competitions)) and the **NFL Big Data Bowl on Kaggle — $100,000 prize pool, judged by analytics staff of the 32 NFL clubs** ([Big Data Bowl 2027](https://www.kaggle.com/competitions/nfl-big-data-bowl-2027); [NFL announcement](https://media.nfl.com/news-and-releases/corporate-communications/national-football-league-announces-seventh-annual-big-data-bowl-)). Our leaderboard: public in-season scoreboard (mean CLV + ROI) for feedback, **private final ranking on a held-out window determines rewards** (top-3 tiers + most-improved-CLV award); entry requires passing G1–G8; anti-leakage rules enforced.

## 6. Strategy portfolio (designs; performance intentionally blank until gates pass)
| ID | Strategy | Bet type |
| --- | --- | --- |
| ST-01 | Bottom-up power-rating spread (EPA/success-rate + team stats + injuries) | Single — spread |
| ST-02 | Matchup-adjusted total (expected points + opponent + weather) | Single — total |
| ST-03 | Moneyline value vs own win probability | Single — ML |
| ST-04 | Player-prop fair-line model (official stats + NGS + depth chart) | Player prop |
| ST-05 | Cross-game parlay of gate-validated singles (diversified legs) | Parlay |
| ST-06 | Player-prop combo with hard correlation gate | Prop combo |
| ST-07 | SGP only where joint probability is modelable | SGP |
| ST-08 | CLV harvesting / early-line originator (execution overlay) | All |
| ST-09 | Teaser / round-robin only with positive-EV legs | Parlay variants |

Full details: `data/strategies.json` and the **Strategies** page of the site.

## 7. Correlation determination
Pearson r via the NIST-published formula with F(1, N−2) significance testing; parlay legs screened pairwise, high-correlation and book-restricted pairs rejected; SGP legs require explicit joint-probability modeling. **Numeric r values are not published by any official source, so they are left blank and computed from our own logged data** — flagged, not invented (FL-01).

## 8. Repo review result
Base commit `414eeca` contained only `README.md` (one line, `# Korea2`). Line-by-line review found **0 irregularities**. See `docs/REPO_REVIEW.md` / **Repo Review** page.

## 9. Flagged for review (do not block, but need your eyes)
10 items in `data/flagged.json` / **Flagged for Review** page — e.g., proprietary SGP correlation matrices (FL-01), HFA constant (FL-02), all strategy performance numbers until computed (FL-03), per-market vig (FL-04), a dead legacy NFL operations URL (FL-09), helpline number presentation (FL-10).

## 10. Responsible gambling
This project is analytics research, not a promise of profit. Only bet what you can afford to lose, in a state where sports wagering is legal and you are 21+. Free, confidential help 24/7/365 in all 50 states + territories via the National Problem Gambling Helpline operated by the [National Council on Problem Gambling](https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/) (page lists 1-800-MY-RESET; legacy 1-800-GAMBLER also documented on state pages).
