"""Empirical stats computed from the verified source CSV.

Source:
  https://github.com/fivethirtyeight/nfl-elo-game/blob/master/data/nfl_games.csv
  Vendored copy: data/raw/nfl-elo-game-master/data/nfl_games.csv

All values below are PROJECT COMPUTATIONS from historical game results. They are
NOT published league values and are flagged "project-computed, unverified by an
official source" on the site.
"""

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "raw", "nfl-elo-game-master", "data", "nfl_games.csv")


def load(seasons):
    out = []
    with open(SRC, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["season"]) in seasons:
                out.append(row)
    return out


def main():
    games = load({2018, 2019, 2020})
    reg = [g for g in games if g["playoff"] == "0"]
    home = [g for g in reg if g["neutral"] == "0"]  # team1 = home per 538 convention

    home_wins = sum(1 for g in home if g["result1"] == "1")
    print(f"regular-season non-neutral games: {len(home)}")
    print(f"home-team win rate: {home_wins}/{len(home)} = {home_wins / len(home):.4f}")

    fav = [g for g in home if float(g["elo_prob1"]) > 0.5]
    fav_wins = sum(1 for g in fav if g["result1"] == "1")
    print(f"home-favorite games: {len(fav)}, won {fav_wins} = {fav_wins / len(fav):.4f}")

    dog = [g for g in home if float(g["elo_prob1"]) < 0.5]
    dog_wins = sum(1 for g in dog if g["result1"] == "0")  # team2 (road underdog) won
    print(f"road-underdog games: {len(dog)}, won {dog_wins} = {dog_wins / len(dog):.4f}")

    # Same-game leg correlation requires scoring/play-by-play data: not in CSV.
    print("same-game / prop correlation: requires play-by-play data -> NOT in source -> unverified")
    # Same-week parlay correlation requires week-level schedule: not in CSV.
    print("same-week game-pair correlation: week numbers not in source CSV -> unverified")


if __name__ == "__main__":
    main()
