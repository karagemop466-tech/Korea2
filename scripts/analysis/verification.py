"""Verification against official NFL.com sources.

The whole project rests on one redistributed file. Before any model runs, the
2026 season computed from that file is reconciled, team by team, against the
standings NFL.com publishes. Every row carries the official URL so a reader can
repeat the check by hand.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from common import RESULTS, jdump, load_games, load_player_week

STANDINGS_URL = "https://www.nfl.com/standings/division/2026/REG"
PLAYER_STATS_URL = "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc"

# Transcribed from the NFL.com 2026 passing leaderboard on 2026-11-01 and re-read
# on 2026-11-02 (Stafford's Week 8 game had not been posted at the first read).
# Columns: player, passing_yards, passing_tds, interceptions, completions, attempts
OFFICIAL_PASSING_2026 = [
    ("Jordan Love", 2246, 16, 6, 192, 312),
    # Re-read on 2026-11-02: the 2026-11-01 transcription predated the official
    # posting of Stafford's Week 8 game (157 yards), exactly the difference.
    ("Matthew Stafford", 2146, 15, 8, 204, 303),
    ("Bryce Young", 1921, 13, 5, 158, 269),
]
RETRIEVED = "2026-11-02"

# Re-read from https://www.nfl.com/standings/division/2026/REG on 2026-11-02
# (maintenance session arena/cacf6153-korea2) after the automated data refresh
# moved the committed games file from 108 to 120 settled 2026 games. Every value
# below was read on the official page on that date; the previous transcription
# was a 2026-11-01 snapshot and no longer described the same set of games.
# Columns: team, W, L, T, PF, PA
OFFICIAL_2026 = [
    ("BUF", 6, 1, 0, 233, 181), ("NE", 5, 3, 0, 184, 162),
    ("NYJ", 2, 6, 0, 170, 188), ("MIA", 1, 6, 0, 117, 181),
    ("CLE", 5, 3, 0, 139, 173), ("PIT", 6, 2, 0, 180, 144),
    ("CIN", 5, 2, 0, 206, 158), ("BAL", 4, 4, 0, 179, 203),
    ("JAX", 5, 2, 0, 196, 111), ("IND", 2, 6, 0, 161, 222),
    ("HOU", 2, 5, 0, 165, 170), ("TEN", 1, 7, 0, 144, 199),
    ("KC", 5, 2, 0, 167, 131), ("DEN", 6, 2, 0, 172, 165),
    ("LV", 4, 4, 0, 221, 230), ("LAC", 0, 7, 0, 99, 175),
    ("NYG", 4, 2, 1, 163, 161), ("DAL", 3, 5, 0, 219, 213),
    ("PHI", 2, 6, 0, 137, 202), ("WAS", 2, 4, 1, 159, 182),
    ("MIN", 6, 1, 0, 140, 93), ("CHI", 5, 2, 0, 180, 143),
    ("DET", 5, 2, 0, 203, 180), ("GB", 5, 3, 0, 171, 164),
    ("CAR", 3, 4, 0, 178, 193), ("ATL", 3, 5, 0, 171, 189),
    ("TB", 3, 5, 0, 178, 151), ("NO", 2, 5, 0, 162, 194),
    ("SF", 6, 1, 0, 197, 139), ("SEA", 4, 3, 0, 168, 125),
    ("LA", 4, 4, 0, 194, 168), ("AZ", 3, 5, 0, 175, 238),
]


# NFL.com displays the Cardinals as ARI; the nflverse schedule file uses AZ for the
# same franchise. Documented alias, not a data difference.
TEAM_ALIASES = {"ARI": "AZ"}   # nflverse schedule code -> NFL.com display code


def computed_standings() -> pd.DataFrame:
    g = load_games()
    for c in ["home_score", "away_score"]:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    s = g[(g.season == 2026) & (g.game_type == "REG") & g.home_score.notna()]
    recs = []
    for _, r in s.iterrows():
        recs.append({"team": r.home_team, "win": r.home_score > r.away_score,
                     "tie": r.home_score == r.away_score, "pf": r.home_score, "pa": r.away_score})
        recs.append({"team": r.away_team, "win": r.away_score > r.home_score,
                     "tie": r.home_score == r.away_score, "pf": r.away_score, "pa": r.home_score})
    d = pd.DataFrame(recs)
    out = []
    for team, grp in d.groupby("team"):
        w = int(grp.win.sum())
        t = int(grp.tie.sum())
        gp = int(len(grp))
        out.append({"team": team, "W": w, "L": gp - w - t, "T": t,
                    "PF": int(grp.pf.sum()), "PA": int(grp.pa.sum()), "GP": gp})
    return pd.DataFrame(out).sort_values("team").reset_index(drop=True)


def player_spot_check() -> list[dict]:
    """Rebuild three quarterbacks' 2026 passing lines and compare to NFL.com."""
    p = load_player_week(seasons=[2026])
    p = p[p.season_type == "REG"]
    for c in ["passing_yards", "passing_tds", "passing_interceptions", "completions", "attempts"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
    qb = (p[p.position == "QB"].groupby("player_display_name")
          .agg(yards=("passing_yards", "sum"), tds=("passing_tds", "sum"),
               ints=("passing_interceptions", "sum"), comp=("completions", "sum"),
               att=("attempts", "sum")))
    rows = []
    for name, yds, td, ints, comp, att in OFFICIAL_PASSING_2026:
        got = qb.loc[name] if name in qb.index else None
        ok = bool(got is not None and int(got.yards) == yds and int(got.tds) == td
                  and int(got.ints) == ints and int(got.comp) == comp and int(got.att) == att)
        rows.append({
            "player": name,
            "nfl_yards_td_int": f"{yds} / {td} / {ints}",
            "rebuilt_yards_td_int": (f"{int(got.yards)} / {int(got.tds)} / {int(got.ints)}"
                                     if got is not None else "missing"),
            "nfl_comp_att": f"{comp}/{att}",
            "rebuilt_comp_att": f"{int(got.comp)}/{int(got.att)}" if got is not None else "missing",
            "match": ok,
            "source": PLAYER_STATS_URL,
        })
    return rows


def main() -> dict:
    comp = computed_standings()
    pcheck = player_spot_check()
    off = pd.DataFrame(OFFICIAL_2026, columns=["team", "W", "L", "T", "PF", "PA"])
    comp["team"] = comp.team.replace(TEAM_ALIASES)
    m = off.merge(comp, on="team", how="outer", suffixes=("_nfl", "_computed"), indicator=True)
    rows = []
    for _, r in m.sort_values("team").iterrows():
        if r["_merge"] != "both":
            rows.append({"team": r.team, "status": "MISSING SIDE",
                         "nfl": "present" if r["_merge"] == "left_only" else "-",
                         "computed": "present" if r["_merge"] == "right_only" else "-"})
            continue
        diffs = []
        for f in ["W", "L", "T", "PF", "PA"]:
            if int(r[f"{f}_nfl"]) != int(r[f"{f}_computed"]):
                diffs.append(f)
        rows.append({
            "team": r.team,
            "nfl_record": f"{int(r.W_nfl)}-{int(r.L_nfl)}-{int(r.T_nfl)}",
            "computed_record": f"{int(r.W_computed)}-{int(r.L_computed)}-{int(r.T_computed)}",
            "nfl_pf_pa": f"{int(r.PF_nfl)}/{int(r.PA_nfl)}",
            "computed_pf_pa": f"{int(r.PF_computed)}/{int(r.PA_computed)}",
            "match": len(diffs) == 0,
            "mismatched_fields": ",".join(diffs) if diffs else "",
            "source": STANDINGS_URL,
        })
    matched = sum(1 for r in rows if r.get("match"))
    total_nfl_wins = int(off.W.sum())
    total_comp_wins = int(comp.W.sum())
    out = {
        "season": 2026,
        "retrieved": RETRIEVED,
        "official_source": STANDINGS_URL,
        "official_source_note": ("NFL.com does not expose a stable per-team deep link for "
                                 "this table; the division standings view at this URL is the "
                                 "canonical page, select 2026 / Regular season."),
        "teams_checked": len(rows),
        "teams_matched": matched,
        "teams_failed": len(rows) - matched,
        "all_matched": matched == len(rows),
        "games_settled": int(comp.GP.sum() // 2),
        "wins_reconcile": total_nfl_wins == total_comp_wins,
        "rows": rows,
        "player_spot_check": pcheck,
        "player_spot_check_matched": sum(1 for r in pcheck if r["match"]),
        "player_source": PLAYER_STATS_URL,
        "team_aliases": TEAM_ALIASES,
        "method": ("Standings are rebuilt from data/derived/games.csv.gz by counting wins, "
                   "losses, ties and points for/against per team, then compared field by "
                   "field with the NFL.com division standings."),
    }
    jdump(out, RESULTS / "verification.json")
    print(f"verification: {matched}/{len(rows)} teams match NFL.com; "
          f"{out['games_settled']} games settled; player spot check "
          f"{out['player_spot_check_matched']}/{len(pcheck)}")
    for r in rows:
        if not r.get("match"):
            print("  MISMATCH", r)
    return out


if __name__ == "__main__":
    main()
