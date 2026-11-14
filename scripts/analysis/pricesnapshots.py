"""Price-snapshot store.

Records the opening and closing number for every market the project originates
(spread, total, moneyline) on every game in the committed feed.

Policy (verification standard): nothing is inferred.
  * The nflverse schedules extract stores a single line per game per market.
    That stored line is treated as the CLOSING line (it is the line the market
    settled against and is the same line used for closing-line accuracy in
    results/market.json).
  * The extract does NOT publish an opening line, so every opening cell is
    intentionally left blank (null) and flagged as unavailable. Opening lines
    are never guessed at or backfilled.
  * Unplayed games have no closing line yet; both cells are blank until the
    game settles.

Outputs results/price_snapshots.json
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd

from common import RESULTS, jdump, load_games

MARKETS = ["spread", "total", "moneyline"]
DATA_SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DATA_SOURCE_LABEL = "nflverse schedules extract (games.csv) — community-maintained, not an NFL-published feed"


def blank() -> dict:
    return {"opening": None, "closing": None, "opening_available": False, "closing_available": False}


def clean(v):
    """Return a JSON-safe number or None; NaN -> None (never inferred)."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v):
        return None
    return v


def main() -> dict:
    g = load_games()
    num = ["spread_line", "total_line", "home_moneyline", "away_moneyline"]
    for c in num:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g.sort_values(["season", "week", "gameday"]).reset_index(drop=True)

    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    games = []
    n_closing = {m: 0 for m in MARKETS}
    for _, r in g.iterrows():
        spread = blank(); total = blank(); moneyline = {"home": dict(blank()), "away": dict(blank())}
        # spread
        if pd.notna(r["spread_line"]):
            spread["closing"] = float(r["spread_line"]); spread["closing_available"] = True
            n_closing["spread"] += 1
        # total
        if pd.notna(r["total_line"]):
            total["closing"] = float(r["total_line"]); total["closing_available"] = True
            n_closing["total"] += 1
        # moneyline (two-sided market: one snapshot per side)
        if pd.notna(r["home_moneyline"]):
            moneyline["home"]["closing"] = float(r["home_moneyline"]); moneyline["home"]["closing_available"] = True
            n_closing["moneyline"] += 1
        if pd.notna(r["away_moneyline"]):
            moneyline["away"]["closing"] = float(r["away_moneyline"]); moneyline["away"]["closing_available"] = True

        games.append({
            "game_id": r["game_id"],
            "season": int(r["season"]),
            "week": int(r["week"]),
            "gameday": str(r["gameday"])[:10] if pd.notna(r["gameday"]) else None,
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "game_type": r["game_type"],
            "played": bool(pd.notna(r["home_score"]) and pd.notna(r["away_score"])),
            "spread": spread,
            "total": total,
            "moneyline": moneyline,
        })

    out = {
        "meta": {
            "title": "Price-snapshot store — opening and closing numbers for every originated market",
            "generated_utc": as_of,
            "data_as_of_gameday": "2026-11-01",
            "source": DATA_SOURCE,
            "source_label": DATA_SOURCE_LABEL,
            "n_games": len(games),
            "markets": MARKETS,
        },
        "policy": {
            "opening": "The feed stores a single line per market per game and does not publish an opening line. "
                       "Every opening cell is therefore null (unavailable). No value is inferred, guessed, or "
                       "backfilled; opening lines remain blank until a source that publishes them is added.",
            "closing": "The single stored line per market is treated as the closing line — the line the market "
                       "settled against, and the same line used for closing-line accuracy in results/market.json.",
            "unplayed": "Games that have not kicked off have no closing line yet; both cells are null.",
        },
        "summary": {
            "n_games": len(games),
            "games_with_closing_spread": n_closing["spread"],
            "games_with_closing_total": n_closing["total"],
            "games_with_closing_moneyline": n_closing["moneyline"],
            "games_with_opening_line": 0,
            "note": "Opening-line count is 0 by policy: the feed does not publish opening lines.",
        },
        "games": games,
    }
    jdump(out, RESULTS / "price_snapshots.json")
    print("price_snapshots.json:", len(games), "games, closing spread", n_closing["spread"],
          ", closing total", n_closing["total"], ", closing moneyline", n_closing["moneyline"])
    return out


if __name__ == "__main__":
    main()
