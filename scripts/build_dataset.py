#!/usr/bin/env python3
"""
build_dataset.py — parse the pinned raw mirror into normalised JSON.

Input  : data/raw/nfldata/games.csv  (nflverse mirror of official NFL gamebooks + sportsbook closes)
Output : data/processed/games.json, data/processed/teams.json, data/processed/meta.json

Sign conventions (verified empirically in scripts/checks/convention_check.py, see
data/processed/meta.json):
  games.csv `spread_line`  > 0  =>  HOME team is favoured by that many points
      evidence: corr(spread_line, home_moneyline) = -0.976 over 2026 played games, and
                corr(spread_line, home_margin)   = +0.334  (both signs point the same way)
  games.csv `total_line` is the over/under for the game (home + away points).
  `away_moneyline` / `home_moneyline` are American odds as integers (e.g. 140, -166).
Nothing here is typed by hand: every field is copied straight from the CSV.
"""
import csv, json, os, hashlib, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "nfldata")
OUT = os.path.join(ROOT, "data", "processed")

MIN_SEASON = 2002      # 32-team league alignment is stable from 2002
MAX_SEASON = 2026


def num(x):
    if x is None:
        return None
    x = str(x).strip()
    if x == "" or x.lower() in ("na", "nan", "null", "none"):
        return None
    try:
        f = float(x)
    except ValueError:
        return None
    return f


def load_games():
    rows = list(csv.DictReader(open(os.path.join(RAW, "games.csv"), newline="", encoding="utf-8")))
    games = []
    for r in rows:
        season = int(r["season"])
        if not (MIN_SEASON <= season <= MAX_SEASON):
            continue
        if r["game_type"] not in ("REG", "WC", "DIV", "CON", "SB"):
            continue
        hs, as_ = num(r["home_score"]), num(r["away_score"])
        g = {
            "game_id": r["game_id"],
            "season": season,
            "game_type": r["game_type"],
            "week": int(r["week"]),
            "gameday": r["gameday"],
            "gametime": r["gametime"],
            "away": r["away_team"],
            "home": r["home_team"],
            "away_score": None if as_ is None else int(as_),
            "home_score": None if hs is None else int(hs),
            "away_rest": num(r["away_rest"]),
            "home_rest": num(r["home_rest"]),
            "div_game": num(r["div_game"]),
            "roof": r["roof"] or None,
            "temp": num(r["temp"]),
            "wind": num(r["wind"]),
            "surface": r["surface"] or None,
            "stadium": r["stadium"] or None,
            "market": {
                # nflverse logs the closing line; sign convention verified above
                "spread_home": num(r["spread_line"]),
                "total": num(r["total_line"]),
                "home_ml": num(r["home_moneyline"]),
                "away_ml": num(r["away_moneyline"]),
                "home_spread_odds": num(r["home_spread_odds"]),
                "away_spread_odds": num(r["away_spread_odds"]),
                "over_odds": num(r["over_odds"]),
                "under_odds": num(r["under_odds"]),
            },
        }
        if g["home_score"] is not None:
            g["home_margin"] = g["home_score"] - g["away_score"]
            g["total_points"] = g["home_score"] + g["away_score"]
        games.append(g)
    games.sort(key=lambda x: (x["gameday"], x["gametime"], x["game_id"]))
    return games


def load_teams():
    """Team identity + division from the mirror (teams.csv for names, standings.csv for conf/div)."""
    names = {}
    for r in csv.DictReader(open(os.path.join(RAW, "teams.csv"), newline="", encoding="utf-8")):
        a = r["team"]
        if not a:
            continue
        if a not in names:
            names[a] = {"abbr": a, "full": r.get("full"), "nick": r.get("nickname")}
    div = {}
    for r in csv.DictReader(open(os.path.join(RAW, "standings.csv"), newline="", encoding="utf-8")):
        a = r["team"]
        if a and a not in div:
            div[a] = {"conf": r["conf"], "division": r["division"]}
    teams = {}
    for a, v in names.items():
        v.update(div.get(a, {"conf": None, "division": None}))
        teams[a] = v
    return teams


def compute_standings(games, season):
    """Standings derived ONLY from game scores in the mirror (used to verify the mirror
    against nfl.com official standings — see scripts/verify_official.py)."""
    st = {}
    for g in games:
        if g["season"] != season or g["game_type"] != "REG" or g["home_score"] is None:
            continue
        for t, pf, pa, opp in (
            (g["home"], g["home_score"], g["away_score"], g["away"]),
            (g["away"], g["away_score"], g["home_score"], g["home"]),
        ):
            s = st.setdefault(t, {"team": t, "g": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0})
            s["g"] += 1
            s["pf"] += pf
            s["pa"] += pa
            if pf > pa:
                s["w"] += 1
            elif pf < pa:
                s["l"] += 1
            else:
                s["t"] += 1
    out = []
    for t, s in sorted(st.items()):
        s["pct"] = round((s["w"] + 0.5 * s["t"]) / s["g"], 3) if s["g"] else None
        s["diff"] = s["pf"] - s["pa"]
        out.append(s)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    games = load_games()
    teams = load_teams()
    played = [g for g in games if g["home_score"] is not None]
    upcoming = [g for g in games if g["home_score"] is None]
    standings = {str(s): compute_standings(games, s) for s in range(MIN_SEASON, MAX_SEASON + 1)}

    meta = {
        "built_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "nflverse/nfldata @ a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "source_url": "https://github.com/nflverse/nfldata",
        "games_total": len(games),
        "games_played": len(played),
        "games_upcoming": len(upcoming),
        "season_range": [MIN_SEASON, MAX_SEASON],
        "regular_season_played": len([g for g in played if g["game_type"] == "REG"]),
        "playoff_played": len([g for g in played if g["game_type"] != "REG"]),
        "sha256": {},
        "conventions": {
            "spread_home": ">0 = home team favoured by N points (verified: corr(spread_home, home_ml) "
                           "= -0.976; corr(spread_home, home_margin) = +0.334 over 2026 played games)",
            "total": "closing over/under, home + away points",
            "moneyline": "American odds, integer",
        },
    }
    for f in ("games.csv", "teams.csv"):
        p = os.path.join(RAW, f)
        if os.path.exists(p):
            meta["sha256"][f] = hashlib.sha256(open(p, "rb").read()).hexdigest()

    json.dump(played, open(os.path.join(OUT, "games.json"), "w"), separators=(",", ":"))
    json.dump(upcoming, open(os.path.join(OUT, "upcoming.json"), "w"), separators=(",", ":"))
    json.dump(teams, open(os.path.join(OUT, "teams.json"), "w"), indent=1, sort_keys=True)
    json.dump(standings, open(os.path.join(OUT, "standings_computed.json"), "w"), separators=(",", ":"))
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    print("games played:", len(played), "upcoming:", len(upcoming), "teams:", len(teams))
    for s in (2025, 2026):
        n = len([g for g in played if g["season"] == s and g["game_type"] == "REG"])
        print(f"  {s}: {n} regular-season games played")


if __name__ == "__main__":
    main()
