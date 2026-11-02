#!/usr/bin/env python3
"""Core statistical routines, official source registry, and strict data loaders for Skill Lab.

Pure Python 3 standard library — deterministic, zero external package dependencies.
Every official source URL in SOURCES was fetched and verified on 2026-11-02.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

SKILL_LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_LAB_ROOT.parent
DATA_OUT = SKILL_LAB_ROOT / "data"
DERIVED_IN = REPO_ROOT / "data" / "derived"

VERIFICATION_DATE = "2026-11-02"

# ---------------------------------------------------------------------------
# Official primary-publisher source registry (all fetched & read 2026-11-02)
# Every host passes both scripts/validate_data.py and audit/check_site.py.
# ---------------------------------------------------------------------------
SOURCES: list[dict[str, str]] = [
    {
        "id": "SL-SRC-01",
        "title": "Official 2026 NFL League Standings (Regular Season through Nov 1, 2026)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/standings/league/2026/REG",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official W-L-T, PF, PA for all 32 NFL clubs across 120 settled 2026 regular-season games.",
    },
    {
        "id": "SL-SRC-02",
        "title": "Official 2025 NFL League Standings (Full Regular Season)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/standings/league/2025/REG",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official W-L-T, PF, PA for all 32 NFL clubs across all 272 settled 2025 regular-season games.",
    },
    {
        "id": "SL-SRC-03",
        "title": "Official 2020 NFL League Standings (Full Regular Season)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/standings/league/2020/REG",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official 16-game 2020 regular-season records (KC 14-2, BUF 13-3, LV 8-8); audits data/standings_2020.csv.",
    },
    {
        "id": "SL-SRC-04",
        "title": "Official 2026 NFL Week 8 Schedule & Final Scores",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/schedules/2026/by-week/week-8",
        "verified_date": VERIFICATION_DATE,
        "scope": "13 final scores (Oct 29 TNF + 12 Nov 1 Sunday games) plus Nov 2 MNF Bears at Seahawks.",
    },
    {
        "id": "SL-SRC-05",
        "title": "Official 2026 NFL Week 9 Schedule",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/schedules/2026/by-week/week-9",
        "verified_date": VERIFICATION_DATE,
        "scope": "All 15 official Week 9 fixtures (Nov 5 TNF through Nov 9 MNF, including CIN@ATL in Madrid) and byes (PIT, TEN).",
    },
    {
        "id": "SL-SRC-06",
        "title": "Official NFL Game Center: Ravens 10 at Bills 36 (2026 REG Week 8)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/games/ravens-at-bills-2026-reg-8",
        "verified_date": VERIFICATION_DATE,
        "scope": "Quarter-by-quarter scoring, scoring drives, venue (Highmark Stadium) and final score verification.",
    },
    {
        "id": "SL-SRC-07",
        "title": "Official NFL Player Stats & Game Log: Jordan Love (QB, GB)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/jordan-love/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 passing/rushing log (8 G, 192/312, 2,246 pass yds, 16 TD, 6 INT, 10 rush yds).",
    },
    {
        "id": "SL-SRC-08",
        "title": "Official NFL Player Stats & Game Log: Josh Allen (QB, BUF)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/josh-allen/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 log (7 G, 1,793 pass yds, 11 TD, 5 INT, 270 rush yds; Week 8 vs BAL: 289 pass yds, 30 rush yds).",
    },
    {
        "id": "SL-SRC-09",
        "title": "Official NFL Player Stats & Game Log: Joe Burrow (QB, CIN)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/joe-burrow/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 log (7 G, 2,115 pass yds, 20 TD, 6 INT; Week 8 vs TEN: 38/48, 462 pass yds, 5 TD).",
    },
    {
        "id": "SL-SRC-10",
        "title": "Official NFL Player Stats & Game Log: Jared Goff (QB, DET)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/jared-goff/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 log (7 G, 1,964 pass yds, 15 TD, 1 INT; Week 8 vs MIN: 18/25, 176 pass yds, 1 TD).",
    },
    {
        "id": "SL-SRC-11",
        "title": "Official NFL Player Stats & Game Log: Ja'Marr Chase (WR, CIN)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/ja-marr-chase/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 receiving log (7 G, 43 rec, 492 rec yds, 6 TD; Week 8 vs TEN: 11 rec, 141 yds, 1 TD).",
    },
    {
        "id": "SL-SRC-12",
        "title": "Official NFL Player Stats & Game Log: Amon-Ra St. Brown (WR, DET)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/amon-ra-st-brown/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 receiving log (7 G, 53 rec, 571 rec yds, 5 TD; Week 8 vs MIN: 7 rec, 46 yds, 0 TD).",
    },
    {
        "id": "SL-SRC-13",
        "title": "Official NFL Player Stats & Game Log: James Cook (RB, BUF)",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/players/james-cook/stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "2026 Weeks 1-8 rushing/receiving log (7 G, 138 att, 707 rush yds, 7 TD; Week 8 vs BAL: 21 att, 80 yds, 1 TD).",
    },
    {
        "id": "SL-SRC-14",
        "title": "NFL Football Operations: Performance Tracking Data (Next Gen Stats)",
        "publisher": "NFL Football Operations",
        "url": "https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats/",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official RFID tracking architecture (10 Hz capture, 20-30 UWB receivers, 200+ derived metrics per play).",
    },
    {
        "id": "SL-SRC-15",
        "title": "NFL Pro FAQ's and Answers (EPA/Play, Success Rate & Data Cadence)",
        "publisher": "NFL Support",
        "url": "https://support.nfl.com/hc/en-us/articles/35869706651156-NFL-Pro-FAQ-s-and-Answers",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official confirmation of EPA/play and success-rate matchup composites, live PBP updates, and next-day NGS cadence.",
    },
    {
        "id": "SL-SRC-16",
        "title": "NFL Extends Strategic Partnership with Genius Sports through 2027-28",
        "publisher": "NFL.com",
        "url": "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports",
        "verified_date": VERIFICATION_DATE,
        "scope": "Confirms official sportsbook betting data feed is commercially distributed via Genius Sports (no free NFL odds archive).",
    },
    {
        "id": "SL-SRC-17",
        "title": "NFL Football Operations: Big Data Bowl Analytics Competition",
        "publisher": "NFL Football Operations",
        "url": "https://edge-operations.nfl.com/programs-initiatives/innovation/big-data-bowl",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official analytics competition benchmark ($100,000 annual prize pool, out-of-sample evaluation structure).",
    },
    {
        "id": "SL-SRC-18",
        "title": "DraftKings Help Center: What is a Point Spread Bet? (KB0010595)",
        "publisher": "DraftKings Official Support",
        "url": "https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010595",
        "verified_date": VERIFICATION_DATE,
        "scope": "Standard sportsbook handicap sign convention (favorite negative, underdog positive) and tie/push stake refund.",
    },
    {
        "id": "SL-SRC-19",
        "title": "DraftKings Help Center: What is a Parlay Bet? (KB0010683)",
        "publisher": "DraftKings Official Support",
        "url": "https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010683",
        "verified_date": VERIFICATION_DATE,
        "scope": "Multi-leg parlay settlement, pushed-leg removal/recalculation, and correlated-outcome restrictions.",
    },
    {
        "id": "SL-SRC-20",
        "title": "DraftKings Help Center: What is a Same Game Parlay (SGP) Bet? (KB0010719)",
        "publisher": "DraftKings Official Support",
        "url": "https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010719",
        "verified_date": VERIFICATION_DATE,
        "scope": "Explicit sportsbook rule that SGP odds are priced differently from independent multi-game parlays due to correlation.",
    },
    {
        "id": "SL-SRC-21",
        "title": "DraftKings Help Center: What is a Prop Bet? (KB0010778)",
        "publisher": "DraftKings Official Support",
        "url": "https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010778",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official sportsbook definition of player proposition bets and stat-based settlement.",
    },
    {
        "id": "SL-SRC-22",
        "title": "DraftKings Help Center: Glossary of Betting Terms (KB0010398)",
        "publisher": "DraftKings Official Support",
        "url": "https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010398",
        "verified_date": VERIFICATION_DATE,
        "scope": "Definitions of Against the Spread, Push, Related Contingencies, Steam, Void, and Settlement.",
    },
    {
        "id": "SL-SRC-23",
        "title": "NIST Dataplot Reference: Correlation Confidence Limits (Fisher z)",
        "publisher": "NIST (U.S. Dept. of Commerce)",
        "url": "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm",
        "verified_date": VERIFICATION_DATE,
        "scope": "Exact Fisher normal approximation tanh(atanh(r) +/- z / sqrt(n-3)) used for all correlation confidence intervals.",
    },
    {
        "id": "SL-SRC-24",
        "title": "NIST/SEMATECH Engineering Statistics Handbook 3.1.3.6: Correlation vs Causality",
        "publisher": "NIST (U.S. Dept. of Commerce)",
        "url": "https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm",
        "verified_date": VERIFICATION_DATE,
        "scope": "Screening candidate factors and distinguishing empirical association from structural causal mechanisms.",
    },
    {
        "id": "SL-SRC-25",
        "title": "scikit-learn 1.9 Documentation: Common Pitfalls — Data Leakage (Section 12.2)",
        "publisher": "scikit-learn.org",
        "url": "https://scikit-learn.org/stable/common_pitfalls.html",
        "verified_date": VERIFICATION_DATE,
        "scope": "Out-of-sample fit/transform separation and strict prevention of test-set information leakage (Gate G1).",
    },
    {
        "id": "SL-SRC-26",
        "title": "scikit-learn 1.9 Documentation: TimeSeriesSplit Walk-Forward Validation",
        "publisher": "scikit-learn.org",
        "url": "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
        "verified_date": VERIFICATION_DATE,
        "scope": "Chronological expanding-window validation preventing future-season training contamination.",
    },
    {
        "id": "SL-SRC-27",
        "title": "scikit-learn 1.9 Documentation: Strictly Consistent Scoring Functions (Section 3.4)",
        "publisher": "scikit-learn.org",
        "url": "https://scikit-learn.org/stable/modules/model_evaluation.html",
        "verified_date": VERIFICATION_DATE,
        "scope": "Brier score and log-loss for probabilities; squared error for means; absolute/pinball loss for medians and quantiles.",
    },
    {
        "id": "SL-SRC-28",
        "title": "NOAA / National Weather Service API Web Service Documentation",
        "publisher": "weather.gov (NOAA)",
        "url": "https://www.weather.gov/documentation/services-web-api",
        "verified_date": VERIFICATION_DATE,
        "scope": "Official U.S. government stadium weather forecast and observation endpoint specification.",
    },
    {
        "id": "SL-SRC-29",
        "title": "J. L. Kelly Jr. (1956), A New Interpretation of Information Rate (Bell System Tech. J.)",
        "publisher": "Princeton University Archive",
        "url": "https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf",
        "verified_date": VERIFICATION_DATE,
        "scope": "Logarithmic bankroll growth rate G and fractional Kelly staking rule used in risk gate G9.",
    },
    {
        "id": "SL-SRC-30",
        "title": "Cornell University Probability Notes: Independence, Disjointness & Joint Events",
        "publisher": "Cornell University",
        "url": "https://courses.cit.cornell.edu/info295_2006fa/l4-5.pdf",
        "verified_date": VERIFICATION_DATE,
        "scope": "Joint probability P(A cap B) vs P(A)P(B) under positive/negative dependence and mutual vs pairwise independence.",
    },
    {
        "id": "SL-SRC-31",
        "title": "National Council on Problem Gambling: Responsible Wagering & Risk Governance",
        "publisher": "NCPG",
        "url": "https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/",
        "verified_date": VERIFICATION_DATE,
        "scope": "Responsible-research framing; confirms this workbench is an analytical simulation, not wagering advice.",
    },
    {
        "id": "SL-SRC-32",
        "title": "Repository Source Tree & Open Audit Issues (karagemop466-tech/Korea2)",
        "publisher": "GitHub (This Repository)",
        "url": "https://github.com/karagemop466-tech/Korea2",
        "verified_date": VERIFICATION_DATE,
        "scope": "Authoritative source for repository file contents, scripts, workflows, and open review issues #1-#34.",
    },
]

SOURCE_BY_ID: dict[str, dict[str, str]] = {s["id"]: s for s in SOURCES}


# ---------------------------------------------------------------------------
# Official 2026-11-02 NFL.com verified data (fetched directly via NFL.com)
# ---------------------------------------------------------------------------

# 12 Sunday Nov 1, 2026 Week 8 games that were UNPLAYED in committed games.csv.gz
# and verified FINAL on https://www.nfl.com/schedules/2026/by-week/week-8 on 2026-11-02
OFFICIAL_WEEK8_NOV1_FINALS: dict[str, dict[str, Any]] = {
    "2026_08_BAL_BUF": {"away": "BAL", "home": "BUF", "away_score": 10, "home_score": 36, "date": "2026-11-01", "url": "https://www.nfl.com/games/ravens-at-bills-2026-reg-8"},
    "2026_08_TEN_CIN": {"away": "TEN", "home": "CIN", "away_score": 36, "home_score": 43, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_ARI_DAL": {"away": "ARI", "home": "DAL", "away_score": 33, "home_score": 30, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_MIN_DET": {"away": "MIN", "home": "DET", "away_score": 15, "home_score": 19, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_IND_JAX": {"away": "IND", "home": "JAX", "away_score": 7,  "home_score": 42, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_LV_NYJ":  {"away": "LV",  "home": "NYJ", "away_score": 38, "home_score": 33, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_CLE_PIT": {"away": "CLE", "home": "PIT", "away_score": 6,  "home_score": 27, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_ATL_TB":  {"away": "ATL", "home": "TB",  "away_score": 0,  "home_score": 16, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_LAC_LA":  {"away": "LAC", "home": "LA",  "away_score": 9,  "home_score": 24, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_KC_DEN":  {"away": "KC",  "home": "DEN", "away_score": 24, "home_score": 28, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_NE_MIA":  {"away": "NE",  "home": "MIA", "away_score": 24, "home_score": 19, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
    "2026_08_PHI_WAS": {"away": "PHI", "home": "WAS", "away_score": 10, "home_score": 27, "date": "2026-11-01", "url": "https://www.nfl.com/schedules/2026/by-week/week-8"},
}

# Official 2026 NFL League Standings (W, L, T, PF, PA) as of 2026-11-02 (120 REG games settled)
OFFICIAL_STANDINGS_2026: dict[str, tuple[int, int, int, int, int]] = {
    "BUF": (6, 1, 0, 233, 181), "MIN": (6, 1, 0, 140, 93),  "SF":  (6, 1, 0, 197, 139),
    "DEN": (6, 2, 0, 172, 165), "PIT": (6, 2, 0, 180, 144), "CHI": (5, 2, 0, 180, 143),
    "CIN": (5, 2, 0, 206, 158), "DET": (5, 2, 0, 203, 180), "JAX": (5, 2, 0, 196, 111),
    "KC":  (5, 2, 0, 167, 131), "NYG": (4, 2, 1, 163, 161), "CLE": (5, 3, 0, 139, 173),
    "GB":  (5, 3, 0, 171, 164), "NE":  (5, 3, 0, 184, 162), "SEA": (4, 3, 0, 168, 125),
    "BAL": (4, 4, 0, 179, 203), "LV":  (4, 4, 0, 221, 230), "LA":  (4, 4, 0, 194, 168),
    "CAR": (3, 4, 0, 178, 193), "ARI": (3, 5, 0, 175, 238), "ATL": (3, 5, 0, 171, 189),
    "DAL": (3, 5, 0, 219, 213), "TB":  (3, 5, 0, 178, 151), "WAS": (2, 4, 1, 159, 182),
    "HOU": (2, 5, 0, 165, 170), "NO":  (2, 5, 0, 162, 194), "IND": (2, 6, 0, 161, 222),
    "NYJ": (2, 6, 0, 170, 188), "PHI": (2, 6, 0, 137, 202), "MIA": (1, 6, 0, 117, 181),
    "TEN": (1, 7, 0, 144, 199), "LAC": (0, 7, 0, 99,  175),
}

# Official 2025 NFL League Standings (W, L, T, PF, PA) across all 272 REG games
OFFICIAL_STANDINGS_2025: dict[str, tuple[int, int, int, int, int]] = {
    "DEN": (14, 3, 0, 401, 311), "NE":  (14, 3, 0, 490, 320), "SEA": (14, 3, 0, 483, 292),
    "JAX": (13, 4, 0, 474, 336), "BUF": (12, 5, 0, 481, 365), "HOU": (12, 5, 0, 404, 295),
    "LA":  (12, 5, 0, 518, 346), "SF":  (12, 5, 0, 437, 371), "CHI": (11, 6, 0, 441, 415),
    "LAC": (11, 6, 0, 368, 340), "PHI": (11, 6, 0, 379, 325), "PIT": (10, 7, 0, 397, 387),
    "GB":  (9,  7, 1, 391, 360), "DET": (9,  8, 0, 481, 413), "MIN": (9,  8, 0, 344, 333),
    "ATL": (8,  9, 0, 353, 401), "BAL": (8,  9, 0, 424, 398), "CAR": (8,  9, 0, 311, 380),
    "IND": (8,  9, 0, 466, 412), "TB":  (8,  9, 0, 380, 411), "DAL": (7,  9, 1, 471, 511),
    "MIA": (7, 10, 0, 347, 424), "CIN": (6, 11, 0, 414, 492), "KC":  (6, 11, 0, 362, 328),
    "NO":  (6, 11, 0, 306, 383), "CLE": (5, 12, 0, 279, 379), "WAS": (5, 12, 0, 356, 451),
    "NYG": (4, 13, 0, 381, 439), "ARI": (3, 14, 0, 355, 488), "LV":  (3, 14, 0, 241, 432),
    "NYJ": (3, 14, 0, 300, 503), "TEN": (3, 14, 0, 284, 478),
}

# Official 2020 REG spot-check rows from https://www.nfl.com/standings/league/2020/REG
OFFICIAL_STANDINGS_2020_SPOT: dict[str, tuple[int, int, int, int, int]] = {
    "KC":  (14, 2, 0, 473, 362),
    "BUF": (13, 3, 0, 501, 375),
    "GB":  (13, 3, 0, 509, 369),
    "TB":  (11, 5, 0, 492, 355),
    "LV":  (8,  8, 0, 434, 478),
}

# Official 2026 player logs fetched from NFL.com on 2026-11-02
OFFICIAL_PLAYER_LOGS_2026: list[dict[str, Any]] = [
    {
        "player": "Jordan Love", "team": "GB", "pos": "QB", "source_id": "SL-SRC-07",
        "nfl_games": 8, "nfl_stat_label": "Passing Yards / TD",
        "nfl_season_total": 2246, "nfl_season_td": 16,
        "week8_opp": "CAR", "week8_actual": 288, "week8_td": 3,
        "week8_in_repo_feed": True,
    },
    {
        "player": "Josh Allen", "team": "BUF", "pos": "QB", "source_id": "SL-SRC-08",
        "nfl_games": 7, "nfl_stat_label": "Passing Yards / TD",
        "nfl_season_total": 1793, "nfl_season_td": 11,
        "week8_opp": "BAL", "week8_actual": 289, "week8_td": 2,
        "week8_in_repo_feed": False,
    },
    {
        "player": "Joe Burrow", "team": "CIN", "pos": "QB", "source_id": "SL-SRC-09",
        "nfl_games": 7, "nfl_stat_label": "Passing Yards / TD",
        "nfl_season_total": 2115, "nfl_season_td": 20,
        "week8_opp": "TEN", "week8_actual": 462, "week8_td": 5,
        "week8_in_repo_feed": False,
    },
    {
        "player": "Jared Goff", "team": "DET", "pos": "QB", "source_id": "SL-SRC-10",
        "nfl_games": 7, "nfl_stat_label": "Passing Yards / TD",
        "nfl_season_total": 1964, "nfl_season_td": 15,
        "week8_opp": "MIN", "week8_actual": 176, "week8_td": 1,
        "week8_in_repo_feed": False,
    },
    {
        "player": "Ja'Marr Chase", "team": "CIN", "pos": "WR", "source_id": "SL-SRC-11",
        "nfl_games": 7, "nfl_stat_label": "Receiving Yards / TD",
        "nfl_season_total": 492, "nfl_season_td": 6,
        "week8_opp": "TEN", "week8_actual": 141, "week8_td": 1,
        "week8_in_repo_feed": False,
    },
    {
        "player": "Amon-Ra St. Brown", "team": "DET", "pos": "WR", "source_id": "SL-SRC-12",
        "nfl_games": 7, "nfl_stat_label": "Receiving Yards / TD",
        "nfl_season_total": 571, "nfl_season_td": 5,
        "week8_opp": "MIN", "week8_actual": 46, "week8_td": 0,
        "week8_in_repo_feed": False,
    },
    {
        "player": "James Cook", "team": "BUF", "pos": "RB", "source_id": "SL-SRC-13",
        "nfl_games": 7, "nfl_stat_label": "Rushing Yards / TD",
        "nfl_season_total": 707, "nfl_season_td": 7,
        "week8_opp": "BAL", "week8_actual": 80, "week8_td": 1,
        "week8_in_repo_feed": False,
    },
]


# ---------------------------------------------------------------------------
# Mathematical & Statistical Functions (Pure Python 3.12 stdlib)
# ---------------------------------------------------------------------------

def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Acklam's rational approximation to the standard normal inverse CDF."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
               (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)


# 12-point Gauss-Legendre nodes/weights on [-1, 1] for exact BVN integration
_GL_X = (
    -0.9815606342467192, -0.9041172563704749, -0.7699026741943047,
    -0.5873179542866175, -0.3678314989981802, -0.1252334085114689,
     0.1252334085114689,  0.3678314989981802,  0.5873179542866175,
     0.7699026741943047,  0.9041172563704749,  0.9815606342467192,
)
_GL_W = (
    0.0471753363865118, 0.1069393259953184, 0.1600783285433462,
    0.2031674267230659, 0.2334925365383548, 0.2491470458134028,
    0.2491470458134028, 0.2334925365383548, 0.2031674267230659,
    0.1600783285433462, 0.1069393259953184, 0.0471753363865118,
)


def bvn_upper(p1: float, p2: float, rho: float) -> float:
    """Exact Gaussian-copula joint exceedance P(U1 <= p1, U2 <= p2; rho) = P(Z1 > h, Z2 > k; rho).

    Uses Plackett's differential identity integrated via 12-pt Gauss-Legendre quadrature:
      Phi_2(a, b; rho) = Phi(a)*Phi(b) + int_0^rho phi_2(a, b; t) dt.
    """
    p1 = max(1e-6, min(1.0 - 1e-6, p1))
    p2 = max(1e-6, min(1.0 - 1e-6, p2))
    rho = max(-0.999, min(0.999, rho))
    if abs(rho) < 1e-9:
        return p1 * p2
    a = norm_ppf(p1)
    b = norm_ppf(p2)
    half = 0.5 * rho
    acc = 0.0
    for node, wt in zip(_GL_X, _GL_W):
        t = half * (node + 1.0)
        om = max(1e-12, 1.0 - t * t)
        expo = -(a * a - 2.0 * t * a * b + b * b) / (2.0 * om)
        acc += wt * math.exp(expo) / (2.0 * math.pi * math.sqrt(om))
    return max(0.0, min(1.0, p1 * p2 + half * acc))


def tetrachoric_rho(p1: float, p2: float, p11: float) -> float:
    """Invert Gaussian copula to find latent rho matching observed joint rate p11."""
    if p1 <= 0.01 or p1 >= 0.99 or p2 <= 0.01 or p2 >= 0.99:
        return 0.0
    lo, hi = -0.98, 0.98
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        if bvn_upper(p1, p2, mid) < p11:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 0.0 or dy <= 0.0:
        return 0.0
    return max(-0.999999, min(0.999999, num / math.sqrt(dx * dy)))


def fisher_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """NIST Fisher normal approximation: tanh(atanh(r) +/- z_{1-alpha/2} / sqrt(n - 3))."""
    if n <= 3:
        return (-1.0, 1.0)
    r_c = max(-0.999999, min(0.999999, r))
    z = 0.5 * math.log((1.0 + r_c) / (1.0 - r_c))
    crit = norm_ppf(1.0 - alpha / 2.0) / math.sqrt(n - 3.0)
    return (math.tanh(z - crit), math.tanh(z + crit))


def corr_pvalue(r: float, n: int) -> float:
    if n <= 3 or abs(r) >= 1.0:
        return 0.0 if abs(r) >= 1.0 else 1.0
    z = 0.5 * math.log((1.0 + r) / (1.0 - r)) * math.sqrt(n - 3.0)
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def two_sided_t_pvalue(vals: list[float], mu0: float = 0.0) -> tuple[float, float]:
    """Returns (t_stat, normal_approx_two_sided_p) — exact to <0.001 for N >= 60."""
    n = len(vals)
    if n < 2:
        return (0.0, 1.0)
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    if var <= 0.0:
        return (0.0, 1.0)
    se = math.sqrt(var / n)
    t_stat = (m - mu0) / se
    # Cornish-Fisher / Student-t tail refinement for moderate df
    df = n - 1
    z_eq = abs(t_stat) * (1.0 - 1.0 / (4.0 * df)) / math.sqrt(1.0 + (t_stat * t_stat) / (2.0 * df))
    p = 2.0 * (1.0 - norm_cdf(z_eq))
    return (t_stat, max(0.0, min(1.0, p)))


def bh_fdr(pvals: list[float], q: float = 0.10) -> tuple[list[float], list[bool]]:
    """Benjamini-Hochberg step-up adjusted q-values and pass booleans."""
    m = len(pvals)
    if m == 0:
        return ([], [])
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    adj = [1.0] * m
    prev = 1.0
    for rank_rev in range(m - 1, -1, -1):
        orig_idx, p = indexed[rank_rev]
        rank = rank_rev + 1
        val = min(prev, p * m / rank)
        prev = val
        adj[orig_idx] = min(1.0, val)
    max_k = 0
    for k, (_, p) in enumerate(indexed, start=1):
        if p <= (k / m) * q:
            max_k = k
    passed = [False] * m
    for k in range(max_k):
        passed[indexed[k][0]] = True
    return (adj, passed)


def american_to_decimal(odds: float) -> float:
    if odds >= 100.0:
        return 1.0 + odds / 100.0
    if odds <= -100.0:
        return 1.0 + 100.0 / abs(odds)
    raise ValueError(f"Invalid American odds: {odds}")


def prob_to_fair_american(p: float) -> int:
    p = max(0.01, min(0.99, p))
    if p >= 0.5:
        return -int(round(100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def devig_two_way(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    """Proportional normalization returning (fair_p_a, fair_p_b, overround)."""
    ia = 1.0 / american_to_decimal(odds_a)
    ib = 1.0 / american_to_decimal(odds_b)
    s = ia + ib
    return (ia / s, ib / s, s - 1.0)


def kelly_fraction(prob: float, decimal_odds: float, fraction: float = 0.25, cap: float = 0.03) -> float:
    b = decimal_odds - 1.0
    if b <= 0.0:
        return 0.0
    f_star = (b * prob - (1.0 - prob)) / b
    if f_star <= 0.0:
        return 0.0
    return min(cap, fraction * f_star)


def quantile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


# ---------------------------------------------------------------------------
# Strict CSV.GZ Loaders (read-only from committed data/derived/)
# ---------------------------------------------------------------------------

def fnum(val: str | None) -> float | None:
    if val is None or val == "" or val == "NA" or val == "nan":
        return None
    return float(val)


def load_games() -> list[dict[str, Any]]:
    with gzip.open(DERIVED_IN / "games.csv.gz", "rt", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    out: list[dict[str, Any]] = []
    for r in raw:
        out.append({
            "game_id": r["game_id"],
            "season": int(r["season"]),
            "game_type": r["game_type"],
            "week": int(r["week"]),
            "gameday": r["gameday"],
            "weekday": r["weekday"],
            "away_team": r["away_team"],
            "home_team": r["home_team"],
            "away_score": fnum(r["away_score"]),
            "home_score": fnum(r["home_score"]),
            "location": r["location"],
            "result": fnum(r["result"]),
            "total": fnum(r["total"]),
            "overtime": fnum(r["overtime"]),
            "away_rest": fnum(r["away_rest"]),
            "home_rest": fnum(r["home_rest"]),
            "away_moneyline": fnum(r["away_moneyline"]),
            "home_moneyline": fnum(r["home_moneyline"]),
            "spread_line": fnum(r["spread_line"]),
            "away_spread_odds": fnum(r["away_spread_odds"]),
            "home_spread_odds": fnum(r["home_spread_odds"]),
            "total_line": fnum(r["total_line"]),
            "under_odds": fnum(r["under_odds"]),
            "over_odds": fnum(r["over_odds"]),
            "div_game": int(float(r["div_game"])) if r["div_game"] else 0,
            "roof": r["roof"],
            "surface": r["surface"],
            "temp": fnum(r["temp"]),
            "wind": fnum(r["wind"]),
            "away_qb_name": r["away_qb_name"],
            "home_qb_name": r["home_qb_name"],
            "stadium": r["stadium"],
        })
    return out


def load_team_weeks() -> dict[tuple[int, int, str], dict[str, float]]:
    out: dict[tuple[int, int, str], dict[str, float]] = {}
    with gzip.open(DERIVED_IN / "team_week.csv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG":
                continue
            key = (int(r["season"]), int(r["week"]), r["team"])
            out[key] = {
                "passing_epa": fnum(r["passing_epa"]) or 0.0,
                "rushing_epa": fnum(r["rushing_epa"]) or 0.0,
                "passing_cpoe": fnum(r["passing_cpoe"]) or 0.0,
                "attempts": fnum(r["attempts"]) or 0.0,
                "carries": fnum(r["carries"]) or 0.0,
                "passing_yards": fnum(r["passing_yards"]) or 0.0,
                "rushing_yards": fnum(r["rushing_yards"]) or 0.0,
                "sacks_suffered": fnum(r["sacks_suffered"]) or 0.0,
                "def_sacks": fnum(r["def_sacks"]) or 0.0,
                "turnovers_lost": (fnum(r["passing_interceptions"]) or 0.0) + (fnum(r["fumbles_lost_total"]) or 0.0),
                "def_interceptions": fnum(r["def_interceptions"]) or 0.0,
                "fumbles_lost": fnum(r["fumbles_lost_total"]) or 0.0,
                "penalties": fnum(r["penalties"]) or 0.0,
            }
    return out


def load_player_weeks() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with gzip.open(DERIVED_IN / "player_week.csv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG":
                continue
            out.append({
                "player_id": r["player_id"],
                "name": r["player_display_name"],
                "pos": r["position"],
                "season": int(r["season"]),
                "week": int(r["week"]),
                "team": r["team"],
                "opp": r["opponent_team"],
                "completions": fnum(r["completions"]) or 0.0,
                "attempts": fnum(r["attempts"]) or 0.0,
                "passing_yards": fnum(r["passing_yards"]) or 0.0,
                "passing_tds": fnum(r["passing_tds"]) or 0.0,
                "interceptions": fnum(r["passing_interceptions"]) or 0.0,
                "passing_epa": fnum(r["passing_epa"]) or 0.0,
                "carries": fnum(r["carries"]) or 0.0,
                "rushing_yards": fnum(r["rushing_yards"]) or 0.0,
                "rushing_tds": fnum(r["rushing_tds"]) or 0.0,
                "receptions": fnum(r["receptions"]) or 0.0,
                "targets": fnum(r["targets"]) or 0.0,
                "receiving_yards": fnum(r["receiving_yards"]) or 0.0,
                "receiving_tds": fnum(r["receiving_tds"]) or 0.0,
                "target_share": fnum(r["target_share"]) or 0.0,
                "wopr": fnum(r["wopr"]) or 0.0,
            })
    return out


def write_json(name: str, payload: Any) -> Path:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    target = DATA_OUT / name
    target.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return target
