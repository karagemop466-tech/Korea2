# Line-by-Line Repository Review (`karagemop466-tech/Korea2`)

**Reviewed On:** `2026-11-12 UTC`  
**Reviewer Session / Branch:** `arena/bea6e3be-korea2`  
**Scope Policy:** Read-only audit of shared/sibling directories; zero edits to files outside `lineup-lab/**`, `.github/workflows/lineup-lab.yml`, and our `COORDINATION.md` section.

---

## 1. Live Official `NFL.com` Reconciliation Summary

| Dataset / Season | Audited Scope | Result | Official Primary Source |
| --- | --- | --- | --- |
| **2020 Regular Season (Completed Control)** | All 32 teams (256 games) in `data/derived/games.csv.gz` | **32 / 32 Exact Match** (exposures in `data/standings_2020.csv` flagged below) | [NFL.com 2020 Standings](https://www.nfl.com/standings/league/2020/REG) |
| **2025 Regular Season (Completed Season)** | All 32 teams (272 games) in `data/derived/games.csv.gz` | **32 / 32 Exact Match** | [NFL.com 2025 Standings](https://www.nfl.com/standings/division/2025/REG) |
| **2026 Regular Season through Week 9** | 120 committed games in `games.csv.gz` + 16 official Week 8 MNF & Week 9 finals (`136` total) | **32 / 32 Exact Match** on W-L-T, PF, PA as of `2026-11-12` | [NFL.com 2026 Standings](https://www.nfl.com/standings/league/2026/REG) |
| **2026 Week 10 Slate & Injury Feed** | All 14 fixtures (`WAS@NYG` TNF through `LAC@BAL` MNF) + 9 club depth charts | **14 / 14 Fixtures Verified**; feed discrepancy & omissions flagged | [NFL.com Week 10 Injuries](https://www.nfl.com/injuries/league/2026/REG10) |

---

## 2. Line-by-Line Findings (`REV-01`–`REV-16`)

1. **`REV-03` & `REV-04` (`data/derived/games.csv.gz`, 2026 Weeks 8–10):** Snapshot ends `2026-11-01` (120 games played; Week 8 MNF `CHI 34 @ SEA 17` and all 15 Week 9 games unplayed). Moreover, committed Week 9 QB fields list `Tyler Huntley` (`BAL`, out for season on IR — 3rd-string `Joe Fagnano` actually started), `Deshaun Watson` (`CLE`, `Shedeur Sanders` started Week 9), and `Kirk Cousins` (`LV`, traded Nov 10 to `MIN`), while all 14 Week 10 lines/QBs are blank.
2. **`REV-05` (`data/derived/player_week.csv.gz` & `scripts/export_extracts.py:46-53`):** Contains `115,078` defensive player rows (`DB`/`DL`/`LB`) and `10,601` `OL` rows (`58.4%` of all `208,231` rows) whose numeric columns are strictly empty/zero because `export_extracts.py` pruned all defensive box stats and snap counts. Cumulative 2026 passing yards stop at Week 8 (`Jordan Love 2,246` vs live Week 9 NFL.com `2,618`).
3. **`REV-06` (`.github/workflows/fetch-nflverse.yml:43,65-72,84,87,93`):** Active workflow bug: downloads `.csv` files for `12` seasons (`2015–2026`, line 43), runs `scripts/export_extracts.py` (line 84) which calls `pd.read_parquet()` looking for `.parquet` files (line 88), and asserts `need_seasons = list(range(2012, 2027))` (`15` seasons, line 93) despite comment `"all twelve seasons"` (line 87).
4. **`REV-07` (`scripts/analyze_strategies.py:50,66`):** Silently substitutes `DEFAULT_AMERICAN = -110` on `1,902` pre-2018 spread rows and `1,904` total rows lacking stored prices. `lineup-lab` uses exact stored odds only.
5. **`REV-08` (`data/standings_2020.csv:1-33`):** Mixes playoff games into 2020 regular season (`KC 16-3`, `BUF 15-4`) and retains `OAK` instead of `LV`.
6. **`REV-09` & `REV-10` (`scripts/build_site.py`, `pages/*.html`, `audit/check_site.py`):** PR #66 added `pages/suggestions.html`, `pages/decision-questions.html`, and `pages/injuries-depth.html` claiming `<meta name="generator" content="line-lab/scripts/build_site.py">`, yet `scripts/build_site.py` contains zero references to them; `audit/check_site.py` records `2,142` flags on older directories while `lineup-lab/` records `0` flags.
7. **`REV-12` & `REV-13` (Live Official Feed Gaps on `2026-11-12`):** `nfl.com/injuries/league/2026/REG10` lists `"No Injuries Reported"` for `SEA` and `CIN` while NFL.com's Nov 11 league roundup details 12 `SEA` injuries (incl. QB1 `Sam Darnold` Out) and 3 `CIN` injuries; club depth charts (`patriots.com`, `colts.com`, `commanders.com`, `miamidolphins.com`, `seahawks.com`, `baltimoreravens.com`, `therams.com`, `detroitlions.com`, `packers.com`) explicitly disclaim being unofficial, omit active injured players (`Lucas Patrick`, `Greg Van Roten`, `Kerby Joseph`, `Micah Parsons`), and leave empty backup slots blank.
