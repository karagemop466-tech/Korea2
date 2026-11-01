"""Process FiveThirtyEight NFL Elo game data into site-ready CSVs.

Source (verified, downloaded via codeload.github.com):
  https://github.com/fivethirtyeight/nfl-elo-game/blob/master/data/nfl_games.csv
  Vendored copy: data/raw/nfl-elo-game-master/data/nfl_games.csv

Notes:
- Covers NFL seasons 1920-2020 (through Super Bowl LV, played Feb 2021).
- Direct access to nfl.com is blocked in this sandbox; the GitHub mirror is the
  verified source used. See flagged-review.html for details.
- result1 = 1 if team1 won, 0 if team2 won.
"""

import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "raw", "nfl-elo-game-master", "data", "nfl_games.csv")
OUT_DIR = os.path.join(ROOT, "data")

SOURCE_URL = "https://github.com/fivethirtyeight/nfl-elo-game/blob/master/data/nfl_games.csv"


def load_games():
    games = []
    with open(SRC, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            games.append(row)
    return games


def write_games(seasons, out_name):
    games = [g for g in load_games() if int(g["season"]) in seasons]
    games.sort(key=lambda g: (g["date"], g["team1"], g["team2"]))
    path = os.path.join(OUT_DIR, out_name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date",
                "season",
                "playoff",
                "neutral",
                "team1",
                "team2",
                "score1",
                "score2",
                "winner",
                "margin",
                "elo_prob1",
                "source",
            ]
        )
        for g in games:
            s1, s2 = int(g["score1"]), int(g["score2"])
            winner = g["team1"] if g["result1"] == "1" else g["team2"]
            w.writerow(
                [
                    g["date"],
                    g["season"],
                    g["playoff"],
                    g["neutral"],
                    g["team1"],
                    g["team2"],
                    s1,
                    s2,
                    winner,
                    abs(s1 - s2),
                    g["elo_prob1"],
                    SOURCE_URL,
                ]
            )
    return path, len(games)


def standings(season):
    games = [g for g in load_games() if int(g["season"]) == season]
    rec = defaultdict(lambda: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0})
    for g in games:
        t1, t2 = g["team1"], g["team2"]
        s1, s2 = int(g["score1"]), int(g["score2"])
        rec[t1]["PF"] += s1
        rec[t1]["PA"] += s2
        rec[t2]["PF"] += s2
        rec[t2]["PA"] += s1
        if g["result1"] == "1":
            rec[t1]["W"] += 1
            rec[t2]["L"] += 1
        elif g["result1"] == "0":
            rec[t2]["W"] += 1
            rec[t1]["L"] += 1
        else:
            rec[t1]["T"] += 1
            rec[t2]["T"] += 1
    rows = []
    for t, r in rec.items():
        rows.append(
            {
                "team": t,
                "W": r["W"],
                "L": r["L"],
                "T": r["T"],
                "PF": r["PF"],
                "PA": r["PA"],
                "PD": r["PF"] - r["PA"],
                "source": SOURCE_URL,
            }
        )
    rows.sort(key=lambda r: (-(r["W"] - r["L"]), r["team"]))
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    path, n = write_games({2020}, "nfl_season_2020.csv")
    print(f"wrote {path} ({n} games)")
    path, n = write_games({2018, 2019, 2020}, "nfl_games_2018_2020.csv")
    print(f"wrote {path} ({n} games)")
    rows = standings(2020)
    path = os.path.join(OUT_DIR, "standings_2020.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["team", "W", "L", "T", "PF", "PA", "PD", "win_pct", "source"]
        )
        for r in rows:
            g = r["W"] + r["L"] + r["T"]
            pct = round(r["W"] / g, 3) if g else 0.0
            w.writerow(
                [r["team"], r["W"], r["L"], r["T"], r["PF"], r["PA"], r["PD"], pct, r["source"]]
            )
    print(f"wrote {path} ({len(rows)} teams)")
    all_g = load_games()
    seasons = sorted({int(g["season"]) for g in all_g})
    print(f"seasons in source: {seasons[0]}..{seasons[-1]} ({len(all_g)} games)")


if __name__ == "__main__":
    main()
