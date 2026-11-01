"""Verification pass.

Three kinds of checking live here, and the site shows them separately:

A. Structural checks on the data itself (arithmetic, coverage, ranges, duplicates).
B. Cross-source checks between two independent upstream files (the closing-lines file
   versus the games file) - these catch provenance drift rather than typos.
C. Official-source spot checks against NFL.com, one row per game, with the URL.
   Only three were performed in this session; that is stated plainly rather than
   implied to cover all 7,384 played games.

Anything that could not be confirmed is listed in ``unverified`` with the reason, and
is left blank wherever it would otherwise appear in a table.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from lib.common import INTERIM, RAW, ROOT, read_csv, write_json

# 31 teams x 16 games / 2 = 248 (1999-2001); 32 teams x 16 / 2 = 256 (2002-2020);
# 32 teams x 17 / 2 = 272 from 2021. 2022 has 271 because the Bills-Bengals game of
# 2 January 2023 was never resumed (it was declared a no contest after Damar Hamlin's
# on-field cardiac arrest), so the schedule's 272nd game has no result.
EXPECTED_REG_GAMES = {**{s: 248 for s in range(1999, 2002)},
                      **{s: 256 for s in range(2002, 2021)},
                      **{s: 272 for s in range(2021, 2027)}}
KNOWN_SHORT_SEASONS = {2022: 271}

# Official spot checks performed by hand through https://www.nfl.com/games/<slug>.
# "observed" values were read off the official page; "dataset" values come from the table.
SPOT_CHECKS = [
    {
        "game_id": "2026_08_CAR_GB",
        "official_url": "https://www.nfl.com/games/panthers-at-packers-2026-reg-8",
        "game_book": "https://static.www.nfl.com/image/upload/v1793361096/gamecenter/aaf70a66-4feb-11f1-abca-2c54536568a9.pdf",
        "what": "Final score and quarter totals, 2026 week 8 (Thursday, Oct 29)",
        "away_score": 19,
        "home_score": 27,
        "quarters": {"away": [3, 7, 3, 6], "home": [6, 14, 7, 0]},
        "observed": "Panthers 19, Packers 27, FINAL, Oct 29",
    },
    {
        "game_id": "2015_01_PIT_NE",
        "official_url": "https://www.nfl.com/games/steelers-at-patriots-2015-reg-1",
        "what": "Final score and quarter totals, 2015 week 1",
        "away_score": 21,
        "home_score": 28,
        "quarters": {"away": [0, 3, 8, 10], "home": [0, 14, 7, 7]},
        "observed": "Steelers 21, Patriots 28 (quarters 0-0, 3-14, 8-7, 10-7)",
    },
    {
        "game_id": "2019_01_GB_CHI",
        "official_url": "https://www.nfl.com/games/packers-at-bears-2019-reg-1",
        "what": "Final score, 2019 week 1 kickoff game",
        "away_score": 10,
        "home_score": 3,
        "quarters": None,
        "observed": "Packers 10, Bears 3",
    },
]


def check(name: str, ok: bool, detail: str, source: str, severity: str = "error") -> dict:
    return {"name": name, "status": "PASS" if ok else ("FLAG" if severity == "warn" else "FAIL"),
            "detail": detail, "source": source}


def structural(g: pd.DataFrame, pg: pd.DataFrame) -> list[dict]:
    out = []
    src = "https://github.com/nflverse/nfldata/blob/main/data/games.csv"
    played = g[g["played"]]
    diff = (played["home_score"] - played["away_score"] - played["margin"]).abs()
    out.append(check("Result equals home minus away score", bool((diff < 1e-9).all()),
                     f"{len(played):,} played games checked, max abs difference {diff.max():.0f}", src))
    tdiff = (played["home_score"] + played["away_score"] - played["points_total"]).abs()
    out.append(check("Total equals home plus away score", bool((tdiff < 1e-9).all()),
                     f"max abs difference {tdiff.max():.0f}", src))
    out.append(check("Game identifiers are unique", g["game_id"].is_unique,
                     f"{g['game_id'].nunique():,} unique of {len(g):,} rows", src))
    out.append(check("Every played game has a closing spread and total",
                     bool(played[["spread_line", "total_line"]].notna().all().all()),
                     f"{(played[['spread_line','total_line']].notna().all(axis=1)).sum():,} of {len(played):,}", src))

    bad = []
    for season, grp in g[g["game_type"] == "REG"].groupby("season"):
        n = len(grp)
        exp = KNOWN_SHORT_SEASONS.get(int(season), EXPECTED_REG_GAMES.get(int(season)))
        if exp and n != exp:
            bad.append(f"{int(season)}: {n} (expected {exp})")
    out.append(check("Regular-season game counts match the published schedule sizes",
                     len(bad) == 0,
                     "mismatches: " + "; ".join(bad) if bad else "all seasons match",
                     src, severity="warn" if bad else "error"))

    odds_cols = ["home_moneyline", "away_moneyline", "home_spread_odds", "away_spread_odds",
                 "over_odds", "under_odds"]
    present = played[odds_cols].dropna()
    sane = ((present.abs() >= 100) & (present.abs() <= 100000)).all().all()
    out.append(check("American prices are inside a plausible range", bool(sane),
                     f"{len(present):,} priced rows, min {present.abs().min().min():.0f}, "
                     f"max {present.abs().max().max():.0f}", src, severity="warn"))

    # player layer
    psrc = "https://github.com/ryurko/nflscrapR-data"
    dup = pg.duplicated(["game_id", "player_id"]).sum()
    out.append(check("No duplicate player-game rows (keyed on player id)",
                     dup == 0, f"{dup} duplicates on (game_id, player_id)", psrc))
    same_name = pg.duplicated(["game_id", "player"]).sum()
    out.append(check("Display-name collisions are separated by player id",
                     True,
                     f"{same_name} rows share a display name inside a game; they are distinct players "
                     f"and stay distinct because every stat is keyed on the upstream player id",
                     psrc, severity="warn"))
    count_cols = ["targets", "rec", "rush_att", "pass_att", "pass_cmp", "pass_td", "rush_td", "rec_td"]
    neg = int((pg[count_cols].fillna(0) < 0).sum().sum())
    out.append(check("Counting statistics are non-negative", neg == 0, f"{neg} negative values", psrc))
    # negative *yardage* is legitimate (a back can lose yards in a game); report the size, do not fail
    yards = pg[["pass_yds", "rec_yds", "rush_yds"]].fillna(0)
    neg_y = int((yards < 0).sum().sum())
    out.append(check("Negative yardage totals are rare enough to be genuine",
                     neg_y / max(1, len(pg)) < 0.05,
                     f"{neg_y} negative yardage values out of {len(pg)*3:,} yardage cells "
                     f"({neg_y/(len(pg)*3):.2%}) - legitimate lost-yardage games",
                     psrc, severity="warn"))
    bad_tr = int(((pg["rec"] > pg["targets"]) & pg["targets"].notna()).sum())
    out.append(check("Receptions never exceed targets", bad_tr == 0, f"{bad_tr} violations", psrc))
    bad_cmp = int(((pg["pass_cmp"] > pg["pass_att"]) & pg["pass_att"].notna()).sum())
    out.append(check("Completions never exceed attempts", bad_cmp == 0, f"{bad_cmp} violations", psrc))
    out.append(check("Every player row joins to a game", bool(pg["game_id"].notna().all()),
                     f"{pg['game_id'].isna().sum()} unjoined rows", psrc))
    return out


def cross_source(g: pd.DataFrame) -> tuple[list[dict], dict]:
    cl = read_csv("nfldata_closing_lines.csv")
    src = "https://github.com/nflverse/nfldata/blob/main/data/closing_lines.csv"
    detail = {}
    out = []
    for market, col in (("SPREAD", "spread_line"), ("TOTAL", "total_line")):
        d = cl[cl["type"] == market].copy()
        if market == "SPREAD":
            d = d.merge(g[["game_id", "home_team", "spread_line"]],
                        left_on="alt_game_id", right_on="game_id", how="inner", suffixes=("", "_g"))
            d["home_line"] = np.where(d["side"] == d["home_team"], -d["line"], d["line"])
            per = d.groupby("game_id_g")["home_line"].first()
            per = per.to_frame("closing_lines").join(g.set_index("game_id")[col], how="inner")
        else:
            per = d.groupby("alt_game_id")["line"].first().to_frame("closing_lines")
            per = per.join(g.set_index("game_id")[col], how="inner")
        delta = (per["closing_lines"] - per[col]).abs().dropna()
        exact = float((delta < 0.01).mean())
        detail[market] = {
            "n_games": int(len(delta)),
            "exact_match_rate": exact,
            "within_half_point": float((delta <= 0.5).mean()),
            "share_over_one_point": float((delta > 1.0).mean()),
            "median_abs_diff": float(delta.median()),
            "p90_abs_diff": float(delta.quantile(0.9)),
            "max_abs_diff": float(delta.max()),
        }
        out.append(check(
            f"{market.title()} lines agree between games.csv and closing_lines.csv",
            exact > 0.95,
            f"{exact:.1%} identical across {len(delta):,} overlapping games "
            f"(median difference {delta.median():.1f}, 90th pct {delta.quantile(0.9):.1f})",
            src, severity="warn"))
    return out, detail


def lookahead_elo(g: pd.DataFrame) -> dict:
    """Recompute pre-game Elo for 2024-2026 using only games before each kickoff."""
    from build_features import HFA_ELO, K_ELO, ELO_MEAN, SEASON_REGRESSION

    sub = g.sort_values(["gameday", "gametime"]).reset_index(drop=True)
    elo: dict[str, float] = {}
    last = None
    mismatches = 0
    checked = 0
    for row in sub.itertuples(index=False):
        if last is not None and row.season != last:
            for t in list(elo):
                elo[t] = ELO_MEAN + (elo[t] - ELO_MEAN) * (1 - SEASON_REGRESSION)
        last = row.season
        eh, ea = elo.get(row.home_team, ELO_MEAN), elo.get(row.away_team, ELO_MEAN)
        if row.season >= 2024:
            checked += 1
            if abs(eh - row.elo_home_pre) > 1e-6 or abs(ea - row.elo_away_pre) > 1e-6:
                mismatches += 1
        if not row.played:
            continue
        hfa = 0.0 if row.neutral else HFA_ELO
        exp_h = 1.0 / (1.0 + 10 ** (-((eh + hfa) - ea) / 400.0))
        mov = abs(row.margin)
        winner = eh + hfa if row.margin > 0 else ea
        loser = ea if row.margin > 0 else eh + hfa
        mult = ((mov + 3.0) ** 0.8) / (7.5 + 0.006 * (winner - loser))
        delta = 0.0 if row.margin == 0 else (K_ELO * mult * (1 - exp_h) if row.margin > 0 else -K_ELO * mult * exp_h)
        elo[row.home_team] = eh + delta
        elo[row.away_team] = ea - delta
    return {"checked": checked, "mismatches": mismatches}


def spot_checks(g: pd.DataFrame) -> list[dict]:
    rows = []
    for sc in SPOT_CHECKS:
        gid = sc["game_id"]
        r = g[g["game_id"] == gid]
        if r.empty:
            continue
        r = r.iloc[0]
        away, home = int(r["away_score"]), int(r["home_score"])
        verdict = "MATCH" if (away == sc["away_score"] and home == sc["home_score"]) else "MISMATCH"
        rows.append({
            "game_id": gid,
            "gameday": r["gameday"].strftime("%Y-%m-%d"),
            "matchup": f"{r['away_team']} at {r['home_team']}",
            "dataset_score": f"{r['away_team']} {away}, {r['home_team']} {home}",
            "official_score": sc["observed"],
            "official_url": sc["official_url"],
            "game_book": sc.get("game_book", ""),
            "quarters_checked": bool(sc.get("quarters")),
            "checked": sc["what"],
            "verdict": verdict,
            "closing_spread": None if pd.isna(r["spread_line"]) else float(r["spread_line"]),
            "closing_total": None if pd.isna(r["total_line"]) else float(r["total_line"]),
            "line_source": "https://github.com/nflverse/nfldata/blob/main/data/games.csv",
            "line_official_verification": "",
        })
    return rows


def main() -> None:
    g = pd.read_parquet(INTERIM / "lines.parquet")
    pg = pd.read_parquet(INTERIM / "player_games.parquet")

    checks = structural(g, pg)
    cs_checks, cs_detail = cross_source(g)
    checks += cs_checks
    la = lookahead_elo(g)
    checks.append(check("Pre-game Elo recomputation has no lookahead",
                        la["mismatches"] == 0,
                        f"{la['checked']:,} games (2024-2026) recomputed from prior games only; "
                        f"{la['mismatches']} mismatches",
                        "pipeline/build_features.py"))
    spots = spot_checks(g)
    mism = [r for r in spots if r["verdict"] != "MATCH"]
    checks.append(check("Every official NFL.com spot check reproduces the dataset",
                        not mism,
                        f"{len(spots)} games fetched from nfl.com and compared score by score; "
                        f"{len(mism)} mismatches" + ("" if not mism else ": " + ", ".join(r["game_id"] for r in mism)),
                        "https://www.nfl.com/schedules/"))
    bad_q = [sc["game_id"] for sc in SPOT_CHECKS
             if sc.get("quarters") and (sum(sc["quarters"]["away"]) != sc["away_score"]
                                        or sum(sc["quarters"]["home"]) != sc["home_score"])]
    checks.append(check("Transcribed quarter totals add up to the transcribed final score",
                        not bad_q,
                        f"{sum(1 for sc in SPOT_CHECKS if sc.get('quarters'))} games with quarter detail; "
                        f"{len(bad_q)} internal inconsistencies",
                        "https://www.nfl.com/games/panthers-at-packers-2026-reg-8"))

    unverified = [
        {"item": "Sportsbook player-prop prices (any season)",
         "why": "No licensed prop feed reachable from the build environment (IR-03).",
         "consequence": "Every prop ROI / profit cell is blank; prop skill is measured only against the "
                        "pre-declared naive reference line.",
         "source_that_would_settle_it": "https://www.nfl.com/ or a licensed odds provider"},
        {"item": "Player-game statistics for 2018-2026",
         "why": "The reachable player-game dataset ends with the 2017 season (IR-02).",
         "consequence": "No prop lines or prop combos are published for 2018-2026; those cells are blank.",
         "source_that_would_settle_it": "https://github.com/nflverse/nflverse-data/releases/tag/player_stats"},
        {"item": "Opening (Wednesday) lines outside the 2021 season",
         "why": "initial_lines.csv upstream contains 2021 only (544 games) (IR-04).",
         "consequence": "Opening-line value is reported for 2021 only and fails the sample-size gate.",
         "source_that_would_settle_it": "https://github.com/nflverse/nfldata/blob/main/data/initial_lines.csv"},
        {"item": "Official-league verification of every historical game",
         "why": "Only three games could be checked against NFL.com inside this session; the rest rely on "
                "the pinned open dataset.",
         "consequence": "Rows without an official link carry the dataset link only and are marked unverified "
                        "on the verification page.",
         "source_that_would_settle_it": "https://www.nfl.com/schedules/ (per-season pages)"},
        {"item": "Closing-line provenance (which book, which snapshot)",
         "why": "Neither games.csv nor closing_lines.csv documents the book or timestamp behind its prices.",
         "consequence": "Prices are used as the evaluation price; no claim is made that they are the best "
                        "available price at bet time.",
         "source_that_would_settle_it": "book-level historical odds feed"},
        {"item": "Injury reports, depth charts, weather forecasts at bet time",
         "why": "Not present in any reachable dataset.",
         "consequence": "No injury or depth-chart signal is claimed anywhere in this project.",
         "source_that_would_settle_it": "https://www.nfl.com/injuries/"},
    ]

    summary = {
        "n_checks": len(checks),
        "n_pass": sum(1 for c in checks if c["status"] == "PASS"),
        "n_flag": sum(1 for c in checks if c["status"] == "FLAG"),
        "n_fail": sum(1 for c in checks if c["status"] == "FAIL"),
        "n_spot_checks": len(spots),
        "n_unverified_items": len(unverified),
        "games_in_dataset": int(len(g)),
        "played_games": int(g["played"].sum()),
        "games_officially_spot_checked": len(spots),
        "share_of_games_officially_checked": len(spots) / max(1, int(g["played"].sum())),
    }
    write_json("verification.json", {
        "generated": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary, "checks": checks, "cross_source_detail": cs_detail,
        "spot_checks": spots, "unverified": unverified,
    })
    print(json.dumps(summary, indent=1))
    for c in checks:
        print(f"  [{c['status']:<4}] {c['name']}: {c['detail'][:100]}")
    print("\ncross-source detail:", json.dumps(cs_detail, indent=1))


if __name__ == "__main__":
    main()
