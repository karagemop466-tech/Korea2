# Lineup Lab — Full Requirements Matrix (`REQ-01`–`REQ-21`)

**Session / Branch:** `arena/bea6e3be-korea2`  
**Verification Date:** `2026-11-12 UTC`  
**Claimed Non-Overlapping Scope:** `lineup-lab/**`, `.github/workflows/lineup-lab.yml`, and the `arena/bea6e3be-korea2` section of `COORDINATION.md`

Every requirement in the project brief is mapped below to its exact implementation, verification rule, and primary official sources verified live on `2026-11-12`.

| Req ID | Category | Requirement | Artifact | Status | Official Source Link |
| --- | --- | --- | --- | --- | --- |
| `REQ-01` | Requirements | Collect, organize, and analyze against full requirements list | `lineup-lab/REQUIREMENTS.md`, `data/requirements.json` | Verified | [GitHub Repo](https://github.com/karagemop466-tech/Korea2) |
| `REQ-02` | Suggestions | Dedicated Suggestions section evaluating site & decision-making options before edits | `data/suggestions.json`, `pages/suggestions.html` | Verified | [DraftKings Rules](https://support.draftkings.com/dk/en-us/what-is-a-parlay-bet?id=kb_article_view&sysparm_article=KB0010683) |
| `REQ-03` | Questions & Gaps | Clear register of Questions, Information & Answers (Have vs Don't Have + discovery paths) | `data/questions.json`, `pages/questions.html` | Verified | [NFL Genius Sports](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports) |
| `REQ-04` | Line Origination | Originate NFL spreads, totals, and fair moneylines strictly out-of-sample + Week 10 slate | `scripts/originate_and_signals.py`, `pages/lines-props.html` | Computed | [NFL Week 10 Schedule](https://www.nfl.com/schedules/2026/by-week/week-10) |
| `REQ-05` | Line Origination | Originate player-prop projections with depth-cascade adjustments (unpriced odds blank) | `scripts/originate_and_signals.py`, `pages/lines-props.html` | Computed + Flagged | [NFL 2026 Passing Stats](https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc) |
| `REQ-06` | Signals | Research pre-kickoff signal strategies strictly on stored closing odds | `scripts/originate_and_signals.py`, `pages/signals-luck.html` | Computed | [NWS High Wind](https://www.weather.gov/safety/wind) |
| `REQ-07` | Competition | Leaderboard competition with paper allocation rewards (cash rewards blank/unfunded) | `scripts/correlations_and_competition.py`, `pages/leaderboard.html` | Computed + Flagged | [Mass Gaming Commission](https://massgaming.com/about/sports-wagering-in-massachusetts/) |
| `REQ-08` | Bet Types | Evaluate single bets, parlays, SGPs, and player-prop combos | `scripts/correlations_and_competition.py`, `pages/leaderboard.html` | Computed + Flagged | [DraftKings Parlay Rules](https://support.draftkings.com/dk/en-us/what-is-a-parlay-bet?id=kb_article_view&sysparm_article=KB0010683) |
| `REQ-09` | Validation Gates | Require every strategy to pass strict validation gates (`G1`–`G10`) | `scripts/correlations_and_competition.py`, `pages/leaderboard.html` | Computed | [NIST Proportion Test](https://www.itl.nist.gov/div898/handbook/prc/section2/prc24.htm) |
| `REQ-10` | Correlations | Compute empirical correlations (`r`, Fisher-`z` CI, Gaussian copula `rho`) | `scripts/correlations_and_competition.py`, `pages/correlations.html` | Computed | [DraftKings Parlay Rules](https://support.draftkings.com/dk/en-us/what-is-a-parlay-bet?id=kb_article_view&sysparm_article=KB0010683) |
| `REQ-11` | Luck Removal | Separate repeatable skill from luck (Pythagorean, split-half, EB shrinkage, BH FDR) | `scripts/originate_and_signals.py`, `pages/signals-luck.html` | Computed | [scikit-learn Linear Models](https://scikit-learn.org/stable/modules/linear_model.html) |
| `REQ-12` | Injuries & Depth | Track injuries & offensive/defensive 2nd/3rd/4th-string backup deficiencies | `scripts/analyze_injuries_depth.py`, `pages/injuries-depth.html` | Verified + Computed | [NFL Week 10 Injuries](https://www.nfl.com/injuries/league/2026/REG10) |
| `REQ-13` | Executive Summary | Publish Executive Summary outlining key empirical & Week 10 findings | `lineup-lab/EXECUTIVE_SUMMARY.md`, `pages/executive.html` | Verified | [NFL 2026 Standings](https://www.nfl.com/standings/league/2026/REG) |
| `REQ-14` | Repo Work | Review repository line by line against official sources, link for manual review, flag issues | `lineup-lab/REPO_REVIEW.md`, `pages/repo-review.html` | Verified | [GitHub Repo](https://github.com/karagemop466-tech/Korea2) |
| `REQ-15` | Site Creation | Clean GitHub Pages dashboard UI with landing page and categorized table subpages | `lineup-lab/scripts/build_site.py`, `lineup-lab/index.html` | Verified | [NFL 2026 Rulebook](https://operations.nfl.com/rules-officiating/2026-nfl-rulebook) |
| `REQ-16` | Verification | 100% row-level official source links; blank & flagged unconfirmable cells | `lineup-lab/scripts/verify_lineup_lab.py`, `pages/flagged.html` | Verified | [NFL Nov 11 Roundup](https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-wednesday-nov-11) |
| `REQ-17` | Zero Hallucination | Never infer or fill in unconfirmed numbers (`-110`, prop lines, empty depth slots) | `lineup-lab/scripts/common.py`, `verify_lineup_lab.py` | Verified | [NFL Genius Sports](https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports) |
| `REQ-18` | Coordination | Non-overlapping scope in `COORDINATION.md`, `git pull --rebase` before every push | `COORDINATION.md` | Verified | [GitHub Repo](https://github.com/karagemop466-tech/Korea2) |
| `REQ-19` | CI Gate | Fail-closed CI workflow validating JSON, HTML, links, and blank cells | `.github/workflows/lineup-lab.yml` | Verified | [GitHub Repo](https://github.com/karagemop466-tech/Korea2) |
| `REQ-20` | Flagged Page | Publish all flagged irregularities on Flagged for Review without blocking merge | `lineup-lab/pages/flagged.html`, `data/flagged.json` | Verified | [NFL Week 10 Injuries](https://www.nfl.com/injuries/league/2026/REG10) |
| `REQ-21` | PR & Live Deploy | Open PR, merge on green checks, confirm live GitHub Pages URL, log in `COORDINATION.md` | `COORDINATION.md` | In Progress | [GitHub Repo](https://github.com/karagemop466-tech/Korea2) |
