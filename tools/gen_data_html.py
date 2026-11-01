"""Generate data.html tables from processed CSVs. Every row carries a source link."""

import csv
import os
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SRC = "https://github.com/fivethirtyeight/nfl-elo-game/blob/master/data/nfl_games.csv"
SRC_REPO = "https://github.com/fivethirtyeight/nfl-elo-game"


def load(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def src_cell():
    return f'<td class="source"><a href="{escape(SRC)}" target="_blank" rel="noopener">nfl_games.csv</a></td>'


def season_counts(games):
    counts = {}
    for g in games:
        counts[g["season"]] = counts.get(g["season"], 0) + 1
    return counts


def build():
    season2020 = load("nfl_season_2020.csv")
    standings = load("standings_2020.csv")
    all_games = load("nfl_games_2018_2020.csv")
    counts = season_counts(load("nfl_games_2018_2020.csv"))
    # full source coverage from raw file
    raw = os.path.join(ROOT, "data", "raw", "nfl-elo-game-master", "data", "nfl_games.csv")
    all_counts = {}
    with open(raw, newline="") as f:
        for row in csv.DictReader(f):
            all_counts[row["season"]] = all_counts.get(row["season"], 0) + 1

    games_rows = []
    for g in season2020:
        playoff = "Postseason" if g["playoff"] == "1" else "Regular"
        games_rows.append(
            f"<tr><td>{g['date']}</td><td>{g['team1']}</td><td class='num'>{g['score1']}</td>"
            f"<td>{g['team2']}</td><td class='num'>{g['score2']}</td><td>{g['winner']}</td>"
            f"<td class='num'>{g['margin']}</td><td class='num'>{float(g['elo_prob1']):.4f}</td>"
            f"<td class='cen'>{playoff}</td>{src_cell()}</tr>"
        )

    stand_rows = []
    for s in standings:
        stand_rows.append(
            f"<tr><td>{s['team']}</td><td class='num'>{int(s['W'])}</td><td class='num'>{int(s['L'])}</td>"
            f"<td class='num'>{int(s['T'])}</td><td class='num'>{int(s['PF'])}</td><td class='num'>{int(s['PA'])}</td>"
            f"<td class='num'>{int(s['PD'])}</td><td class='num'>{float(s['win_pct']):.3f}</td>{src_cell()}</tr>"
        )

    idx_rows = []
    for season in sorted(all_counts, key=int):
        idx_rows.append(
            f"<tr><td class='num'>{season}</td><td class='num'>{all_counts[season]}</td>"
            f"<td class='source'><a href='{escape(SRC)}' target='_blank' rel='noopener'>nfl_games.csv (row filter season={season})</a></td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NFL Data — Korea2</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header>
  <div class="wrap">
    <h1>Korea2</h1>
    <span class="tag">NFL Data</span>
  </div>
</header>
<nav>
  <ul>
    <li><a href="index.html">Dashboard</a></li>
    <li><a href="data.html" class="active">NFL Data</a></li>
    <li><a href="strategies.html">Strategies</a></li>
    <li><a href="correlations.html">Correlations</a></li>
    <li><a href="executive-summary.html">Executive Summary</a></li>
    <li><a href="flagged-review.html">Flagged for Review</a></li>
  </ul>
</nav>
<main>
  <div class="section">
    <h2>NFL Game Results — Source Data</h2>
    <p class="kicker">Source: <code>{escape(SRC)}</code> (FiveThirtyEight NFL Elo game repository; mirror of NFL game records, seasons 1920&ndash;2020). Direct access to nfl.com is blocked in this build environment — see <a href="flagged-review.html">Flagged for Review</a>. Every row links to the source file. No values are inferred or filled in.</p>
    <p><strong>Coverage:</strong> {len(all_counts)} seasons (1920&ndash;2020), {sum(all_counts.values())} games. <strong>2020 season:</strong> {len(season2020)} games (256 regular season + 13 postseason).</p>
    <p><strong>Files:</strong></p>
    <ul>
      <li><a href="data/nfl_season_2020.csv" download>nfl_season_2020.csv</a> — 2020 season, all games, with source column ({len(season2020)} rows)</li>
      <li><a href="data/nfl_games_2018_2020.csv" download>nfl_games_2018_2020.csv</a> — 2018&ndash;2020 seasons ({len(all_games)} rows)</li>
      <li><a href="data/standings_2020.csv" download>standings_2020.csv</a> — 2020 W-L-T standings computed from source scores (32 teams)</li>
    </ul>
  </div>

  <div class="section">
    <h2>2020 Season — All Games (269 rows)</h2>
    <table>
      <thead>
        <tr><th>Date</th><th>Team 1</th><th>Score 1</th><th>Team 2</th><th>Score 2</th><th>Winner</th><th>Margin</th><th>Elo prob (team 1)</th><th>Game type</th><th class="source">Source</th></tr>
      </thead>
      <tbody>
        {''.join(games_rows)}
      </tbody>
    </table>
    <p class="footnote">Team abbreviations exactly as published by the source (e.g. “OAK” for the Raiders in the 2020 season — flagged on the Flagged for Review page).</p>
  </div>

  <div class="section">
    <h2>2020 Season — Standings (computed from source scores, 32 teams)</h2>
    <p class="kicker">W/L/T and points computed by this project from the source CSV; not copied from a standings publisher.</p>
    <table>
      <thead>
        <tr><th>Team</th><th>W</th><th>L</th><th>T</th><th>PF</th><th>PA</th><th>PD</th><th>Win %</th><th class="source">Source</th></tr>
      </thead>
      <tbody>
        {''.join(stand_rows)}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Seasons Index (1920&ndash;2020)</h2>
    <p class="kicker">Game counts per season, computed from the verified source file.</p>
    <table>
      <thead>
        <tr><th>Season</th><th>Games</th><th class="source">Source</th></tr>
      </thead>
      <tbody>
        {''.join(idx_rows)}
      </tbody>
    </table>
  </div>
</main>
<footer>
  Korea2 — NFL Lines Origination. Source: <a href="{escape(SRC_REPO)}" target="_blank" rel="noopener">fivethirtyeight/nfl-elo-game</a>.
</footer>
</body>
</html>
"""
    out = os.path.join(ROOT, "data.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"wrote {out} ({len(games_rows)} game rows, {len(stand_rows)} standings, {len(idx_rows)} seasons)")


if __name__ == "__main__":
    build()
