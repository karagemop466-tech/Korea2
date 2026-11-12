#!/usr/bin/env python3
"""Reconcile committed extracts against official NFL.com standings (2020, 2025, 2026 thru Wk 9)
and official NFL.com 2026 passing leaders / Week 9 QB starter changes.

Outputs lineup-lab/data/official_reconciliation.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

# Official NFL.com 2020 REG standings (verified 2026-11-12 from https://www.nfl.com/standings/league/2020/REG)
OFFICIAL_2020 = {
    "KC":  (14, 2, 0, 473, 362), "BUF": (13, 3, 0, 501, 375), "GB":  (13, 3, 0, 509, 369), "NO":  (12, 4, 0, 482, 337),
    "PIT": (12, 4, 0, 416, 312), "SEA": (12, 4, 0, 459, 371), "BAL": (11, 5, 0, 468, 303), "CLE": (11, 5, 0, 408, 419),
    "IND": (11, 5, 0, 451, 362), "TB":  (11, 5, 0, 492, 355), "TEN": (11, 5, 0, 491, 439), "LA":  (10, 6, 0, 372, 296),
    "MIA": (10, 6, 0, 404, 338), "ARI": (8,  8, 0, 410, 367), "CHI": (8,  8, 0, 372, 370), "LV":  (8,  8, 0, 434, 478),
    "LAC": (7,  9, 0, 384, 426), "MIN": (7,  9, 0, 430, 475), "NE":  (7,  9, 0, 326, 353), "WAS": (7,  9, 0, 335, 329),
    "DAL": (6, 10, 0, 395, 473), "NYG": (6, 10, 0, 280, 357), "SF":  (6, 10, 0, 376, 390), "CAR": (5, 11, 0, 350, 402),
    "DEN": (5, 11, 0, 323, 446), "DET": (5, 11, 0, 377, 519), "CIN": (4, 11, 1, 311, 424), "PHI": (4, 11, 1, 334, 418),
    "ATL": (4, 12, 0, 396, 414), "HOU": (4, 12, 0, 384, 464), "NYJ": (2, 14, 0, 243, 457), "JAX": (1, 15, 0, 306, 492),
}

# Official NFL.com 2025 REG standings (verified 2026-11-12 from https://www.nfl.com/standings/division/2025/REG)
OFFICIAL_2025 = {
    "DEN": (14, 3, 0, 401, 311), "NE":  (14, 3, 0, 490, 320), "SEA": (14, 3, 0, 483, 292), "JAX": (13, 4, 0, 474, 336),
    "BUF": (12, 5, 0, 481, 365), "HOU": (12, 5, 0, 404, 295), "LA":  (12, 5, 0, 518, 346), "SF":  (12, 5, 0, 437, 371),
    "CHI": (11, 6, 0, 441, 415), "LAC": (11, 6, 0, 368, 340), "PHI": (11, 6, 0, 379, 325), "PIT": (10, 7, 0, 397, 387),
    "GB":  (9,  7, 1, 391, 360), "DET": (9,  8, 0, 481, 413), "MIN": (9,  8, 0, 344, 333), "ATL": (8,  9, 0, 353, 401),
    "BAL": (8,  9, 0, 424, 398), "CAR": (8,  9, 0, 311, 380), "IND": (8,  9, 0, 466, 412), "TB":  (8,  9, 0, 380, 411),
    "DAL": (7,  9, 1, 471, 511), "MIA": (7, 10, 0, 347, 424), "CIN": (6, 11, 0, 414, 492), "KC":  (6, 11, 0, 362, 328),
    "NO":  (6, 11, 0, 306, 383), "CLE": (5, 12, 0, 279, 379), "WAS": (5, 12, 0, 356, 451), "NYG": (4, 13, 0, 381, 439),
    "ARI": (3, 14, 0, 355, 488), "LV":  (3, 14, 0, 241, 432), "NYJ": (3, 14, 0, 300, 503), "TEN": (3, 14, 0, 284, 478),
}

# Official NFL.com 2026 REG standings through Week 9 (verified 2026-11-12 from https://www.nfl.com/standings/league/2026/REG)
OFFICIAL_2026_W9 = {
    "BUF": (7, 1, 0, 256, 187), "SF":  (7, 1, 0, 235, 156), "CHI": (7, 2, 0, 241, 184), "DEN": (7, 2, 0, 198, 186),
    "CIN": (6, 2, 0, 240, 175), "DET": (6, 2, 0, 222, 189), "JAX": (6, 2, 0, 229, 121), "KC":  (6, 2, 0, 202, 143),
    "MIN": (6, 2, 0, 146, 116), "PIT": (6, 2, 0, 180, 144), "NYG": (5, 2, 1, 182, 172), "GB":  (6, 3, 0, 216, 191),
    "CLE": (5, 4, 0, 161, 196), "LA":  (5, 4, 0, 214, 181), "NE":  (5, 4, 0, 211, 207), "SEA": (5, 4, 0, 202, 162),
    "BAL": (4, 5, 0, 189, 236), "DAL": (4, 5, 0, 246, 236), "LV":  (4, 5, 0, 238, 268), "CAR": (3, 5, 0, 199, 219),
    "HOU": (3, 5, 0, 209, 192), "NO":  (3, 5, 0, 185, 216), "ARI": (3, 6, 0, 178, 255), "ATL": (3, 6, 0, 188, 223),
    "TB":  (3, 6, 0, 202, 178), "WAS": (2, 5, 1, 172, 202), "IND": (2, 7, 0, 184, 249), "NYJ": (2, 7, 0, 182, 223),
    "PHI": (2, 7, 0, 148, 221), "MIA": (1, 7, 0, 126, 200), "TEN": (1, 7, 0, 144, 199), "LAC": (0, 8, 0, 121, 219),
}

# Verified live NFL.com 2026 passing leaders thru Week 9 (https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc)
NFLCOM_PASSING_W9 = [
    {"player": "Jordan Love", "team_wk8": "GB", "live_w9_yds": 2618, "live_w9_td": 19},
    {"player": "Joe Burrow", "team_wk8": "CIN", "live_w9_yds": 2386, "live_w9_td": 23},
    {"player": "Dak Prescott", "team_wk8": "DAL", "live_w9_yds": 2381, "live_w9_td": 16},
    {"player": "Matthew Stafford", "team_wk8": "LA", "live_w9_yds": 2374, "live_w9_td": 16},
    {"player": "Kirk Cousins", "team_wk8": "LV", "live_w9_yds": 2340, "live_w9_td": 20},
    {"player": "Drake Maye", "team_wk8": "NE", "live_w9_yds": 2282, "live_w9_td": 18},
    {"player": "C.J. Stroud", "team_wk8": "HOU", "live_w9_yds": 2251, "live_w9_td": 16},
    {"player": "Bryce Young", "team_wk8": "CAR", "live_w9_yds": 2197, "live_w9_td": 16},
    {"player": "Jared Goff", "team_wk8": "DET", "live_w9_yds": 2134, "live_w9_td": 15},
    {"player": "Patrick Mahomes", "team_wk8": "KC", "live_w9_yds": 2037, "live_w9_td": 14},
    {"player": "Josh Allen", "team_wk8": "BUF", "live_w9_yds": 2027, "live_w9_td": 12},
    {"player": "Sam Darnold", "team_wk8": "SEA", "live_w9_yds": 1478, "live_w9_td": 10},
]


def compute_season_standings(games: list[dict[str, str]], season: str, extra: list[dict] | None = None) -> dict[str, tuple[int, int, int, int, int]]:
    tbl: dict[str, list[int]] = {t: [0, 0, 0, 0, 0] for t in OFFICIAL_2026_W9}

    def add(away: str, a_pts: int, home: str, h_pts: int) -> None:
        a = C.std_team(away)
        h = C.std_team(home)
        tbl[a][3] += a_pts
        tbl[a][4] += h_pts
        tbl[h][3] += h_pts
        tbl[h][4] += a_pts
        if a_pts > h_pts:
            tbl[a][0] += 1
            tbl[h][1] += 1
        elif h_pts > a_pts:
            tbl[h][0] += 1
            tbl[a][1] += 1
        else:
            tbl[a][2] += 1
            tbl[h][2] += 1

    for r in games:
        if r["season"] == season and r["game_type"] == "REG" and r["home_score"] != "" and r["away_score"] != "":
            add(r["away_team"], int(float(r["away_score"])), r["home_team"], int(float(r["home_score"])))
    if extra:
        for e in extra:
            add(e["away_team"], int(e["away_score"]), e["home_team"], int(e["home_score"]))
    return {k: tuple(v) for k, v in tbl.items()}


def main() -> int:
    games = C.load_csv_gz("games.csv.gz")
    pw = C.load_csv_gz("player_week.csv.gz")

    s2020 = compute_season_standings(games, "2020")
    s2025 = compute_season_standings(games, "2025")
    s2026_nov1 = compute_season_standings(games, "2026")
    s2026_w9 = compute_season_standings(games, "2026", C.OFFICIAL_2026_POST_NOV1_FINALS)

    m2020 = sum(1 for t, v in OFFICIAL_2020.items() if s2020[t] == v)
    m2025 = sum(1 for t, v in OFFICIAL_2025.items() if s2025[t] == v)
    m2026_w9 = sum(1 for t, v in OFFICIAL_2026_W9.items() if s2026_w9[t] == v)

    # Check Week 8 extract QB totals vs Week 9 live NFL.com passing leaders
    qb_wk8: dict[str, dict[str, int]] = {}
    for r in pw:
        if r["season"] == "2026" and r["season_type"] == "REG" and r["position"] == "QB":
            nm = r["player_display_name"]
            d = qb_wk8.setdefault(nm, {"yds": 0, "td": 0, "weeks": 0})
            d["yds"] += int(float(r["passing_yards"] or 0))
            d["td"] += int(float(r["passing_tds"] or 0))
            if float(r["attempts"] or 0) > 0:
                d["weeks"] += 1

    qb_comparison = []
    for row in NFLCOM_PASSING_W9:
        wk8 = qb_wk8.get(row["player"], {"yds": 0, "td": 0, "weeks": 0})
        qb_comparison.append({
            "player": row["player"],
            "team_wk8": row["team_wk8"],
            "extract_wk8_yds": wk8["yds"],
            "extract_wk8_td": wk8["td"],
            "live_w9_yds": row["live_w9_yds"],
            "live_w9_td": row["live_w9_td"],
            "week9_delta_yds": row["live_w9_yds"] - wk8["yds"],
            "week9_delta_td": row["live_w9_td"] - wk8["td"],
            "sources": ["SRC-NFL-PASSING-2026", "SRC-GITHUB-REPO"],
        })

    # Week 9 projected QBs in games.csv.gz vs actual/live Week 9-10 events
    wk9_qb_discrepancies = [
        {
            "game_id": "2026_09_JAX_BAL",
            "committed_away_qb": "Trevor Lawrence",
            "committed_home_qb": "Tyler Huntley",
            "official_fact": "Tyler Huntley suffered season-ending turf toe IR; 3rd-string QB Joe Fagnano started Week 9 TNF (JAX 33, BAL 10); BAL traded for Jacoby Brissett.",
            "sources": ["SRC-NFL-BAL-JACKSON", "SRC-NFL-SCHED-W9"],
        },
        {
            "game_id": "2026_09_CLE_NO",
            "committed_away_qb": "Deshaun Watson",
            "committed_home_qb": "Tyler Shough",
            "official_fact": "Deshaun Watson was inactive in concussion protocol for Week 9; Shedeur Sanders started Week 9 (CLE 22, NO 23); Watson cleared to start Week 10 vs HOU.",
            "sources": ["SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-SCHED-W9"],
        },
        {
            "game_id": "2026_09_LV_SF",
            "committed_away_qb": "Kirk Cousins",
            "committed_home_qb": "Brock Purdy",
            "official_fact": "Kirk Cousins played Week 9 for LV (LV 17, SF 38) and was traded Nov 10 to MIN for a 2027 3rd-round pick; MIN Week 10 starter unconfirmed.",
            "sources": ["SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-SCHED-W9"],
        },
        {
            "game_id": "2026_09_DET_MIA",
            "committed_away_qb": "Jared Goff",
            "committed_home_qb": "Malik Willis",
            "official_fact": "Malik Willis (groin) placed on IR for Weeks 10-13; backup Kyle McCord in line for first NFL start in Week 10 at IND.",
            "sources": ["SRC-NFL-MIA-WILLIS", "SRC-CLUB-MIA-DC"],
        },
        {
            "game_id": "2026_09_ARI_SEA",
            "committed_away_qb": "Jacoby Brissett",
            "committed_home_qb": "Sam Darnold",
            "official_fact": "Brissett traded to BAL (rookie 3rd-rounder Carson Beck starts Week 10 for AZ); SEA QB1 Sam Darnold ruled OUT Week 10 (QB2 Drew Lock starts).",
            "sources": ["SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-SEA-DARNOLD"],
        },
    ]

    team_2026_rows = []
    for t in sorted(OFFICIAL_2026_W9):
        off = OFFICIAL_2026_W9[t]
        reb = s2026_w9[t]
        nov1 = s2026_nov1[t]
        team_2026_rows.append({
            "team": t,
            "extract_nov1_record": f"{nov1[0]}-{nov1[1]}-{nov1[2]}",
            "rebuilt_w9_record": f"{reb[0]}-{reb[1]}-{reb[2]}",
            "official_w9_record": f"{off[0]}-{off[1]}-{off[2]}",
            "rebuilt_w9_pf_pa": f"{reb[3]}/{reb[4]}",
            "official_w9_pf_pa": f"{off[3]}/{off[4]}",
            "exact_match": (reb == off),
            "sources": ["SRC-NFL-STANDINGS-2026", "SRC-NFL-SCHED-W8", "SRC-NFL-SCHED-W9"],
        })

    out = {
        "meta": {
            "verified_on": C.VERIFIED_DATE,
            "summary": {
                "teams_2020_matched": m2020,
                "teams_2020_total": 32,
                "teams_2025_matched": m2025,
                "teams_2025_total": 32,
                "teams_2026_w9_matched": m2026_w9,
                "teams_2026_w9_total": 32,
                "committed_2026_played": 120,
                "official_post_nov1_added": len(C.OFFICIAL_2026_POST_NOV1_FINALS),
                "total_2026_played_through_w9": 136,
            },
        },
        "team_2026_rows": team_2026_rows,
        "qb_comparison": qb_comparison,
        "wk9_qb_discrepancies": wk9_qb_discrepancies,
    }
    C.write_strict_json(C.DATA_DIR / "official_reconciliation.json", out)
    print(f"Reconciled: 2020={m2020}/32, 2025={m2025}/32, 2026_thru_W9={m2026_w9}/32; QBs={len(qb_comparison)}")
    if m2020 != 32 or m2025 != 32 or m2026_w9 != 32:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
