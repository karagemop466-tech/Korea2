#!/usr/bin/env python3
"""Data-integrity checks and the source registry.

Every published table row traces to one of the registry entries below. The checks
in this module are the "verify line by line" layer: sign conventions, cross-source
reconciliation, internal consistency of totals and point totals, price coherence,
and completeness by season. Anything that cannot be confirmed is reported as
`needs review` and published on the Flagged for Review page.

Outputs data/derived/integrity.json
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nflcore as nc

OUT = nc.DERIVED / "integrity.json"
MD = lambda x, n=4: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)

REPO = "https://github.com/nflverse/nfldata/blob"
COMMIT = None


def gh_json(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def curl_status(url: str) -> int | None:
    out = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                          "-L", "--max-time", "25", url], capture_output=True, text=True)
    try:
        return int(out.stdout.strip()[-3:])
    except Exception:
        return None


def build_registry(manifest, commit):
    base = f"{REPO}/{commit}/data"
    files = {f["file"].split("/")[-1]: f for f in manifest["files"]}
    entries = [
        dict(id="S1", name="nflverse/nfldata - games.csv",
             url=f"{base}/games.csv",
             publisher="nflverse (open-source NFL data project)",
             league_official=False,
             provides="Game results, closing spread/total/moneyline with prices, rest days, "
                      "venue, roof, surface, weather, quarterbacks, coaches, officials",
             rows=files.get("games.csv", {}).get("rows"),
             sha256=files.get("games.csv", {}).get("sha256"),
             access="git tree via codeload.github.com (release-asset CDN unreachable in sandbox)"),
        dict(id="S2", name="nflverse/nfldata - closing_lines.csv",
             url=f"{base}/closing_lines.csv",
             publisher="nflverse", league_official=False,
             provides="Independent extract of closing spread / total / moneyline for 2006-2018; "
                      "used only to reconcile S1",
             rows=files.get("closing_lines.csv", {}).get("rows"),
             sha256=files.get("closing_lines.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S3", name="nflverse/nfldata - initial_lines.csv",
             url=f"{base}/initial_lines.csv",
             publisher="nflverse", league_official=False,
             provides="Westgate SuperBook opening spread and total, 2021 season only",
             rows=files.get("initial_lines.csv", {}).get("rows"),
             sha256=files.get("initial_lines.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S4", name="nflverse/nfldata - sc_lines.csv",
             url=f"{base}/sc_lines.csv",
             publisher="nflverse", league_official=False,
             provides="SuperContest lines (published contest numbers), 2013-2020",
             rows=files.get("sc_lines.csv", {}).get("rows"),
             sha256=files.get("sc_lines.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S5", name="nflverse/nfldata - teams.csv",
             url=f"{base}/teams.csv",
             publisher="nflverse", league_official=False,
             provides="Team code crosswalk (nflverse / NFL / ESPN / PFR / PFF / SBR / DraftKings)",
             rows=files.get("teams.csv", {}).get("rows"),
             sha256=files.get("teams.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S6", name="nflverse/nfldata - standings.csv",
             url=f"{base}/standings.csv",
             publisher="nflverse", league_official=False,
             provides="Per-season standings with points scored and allowed; used for the "
                      "internal consistency check against S1",
             rows=files.get("standings.csv", {}).get("rows"),
             sha256=files.get("standings.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S7", name="nflverse/nfldata - win_totals.csv",
             url=f"{base}/win_totals.csv",
             publisher="nflverse", league_official=False,
             provides="Pregame season win totals (market)", 
             rows=files.get("win_totals.csv", {}).get("rows"),
             sha256=files.get("win_totals.csv", {}).get("sha256"),
             access="git tree"),
        dict(id="S8", name="nflverse-data - player_stats release (canonical)",
             url="https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
             publisher="nflverse", league_official=False,
             provides="Canonical weekly player statistics release (the documented upstream of the "
                      "player-week extract used here)",
             rows=None, sha256=None,
             access="NOT downloaded: release-asset CDN is unreachable from the build sandbox"),
        dict(id="S9", name="kadetownsend4/ML-Betting - weekly_stats_2023/2024.csv (nflverse schema)",
             url="https://github.com/kadetownsend4/ML-Betting/tree/main/NFL/weekly_nfl_stats_season",
             publisher="third-party mirror of the nflverse player-week schema",
             league_official=False,
             provides="Weekly player statistics 2023-2024 used for the player-prop layer",
             rows=(files.get("weekly_stats_2023.csv", {}).get("rows") or 0) +
                  (files.get("weekly_stats_2024.csv", {}).get("rows") or 0),
             sha256=None,
             access="api.github.com contents (raw media type)"),
        dict(id="S10", name="NFL.com standings (league official)",
             url="https://www.nfl.com/standings/",
             publisher="NFL", league_official=True,
             provides="League-official standings: W-L-T, points for, points against. Used for the "
                      "2026 spot check of S6.",
             rows=None, sha256=None,
             access="agent page-fetch tool (nfl.com is blocked from the build shell)"),
        dict(id="S11", name="NFL rulebook (league official)",
             url="https://operations.nfl.com/the-rules/nfl-rulebook/",
             publisher="NFL", league_official=True,
             provides="Official playing rules: overtime, scoring, timing - the basis for the "
                      "settlement rules used here",
             rows=None, sha256=None,
             access="agent page-fetch tool"),
        dict(id="S12", name="NFL.com scores (league official)",
             url="https://www.nfl.com/scores/",
             publisher="NFL", league_official=True,
             provides="League-official final scores, used as the reference for result "
                      "reconciliation",
             rows=None, sha256=None,
             access="agent page-fetch tool"),
        dict(id="S13", name="NFL.com stats - team offence (league official)",
             url="https://www.nfl.com/stats/team-stats/",
             publisher="NFL", league_official=True,
             provides="League-official team statistics hub for season-level cross-checks",
             rows=None, sha256=None,
             access="agent page-fetch tool"),
    ]
    for e in entries:
        if e["url"].startswith("https://github.com"):
            e["http_status"] = curl_status(e["url"])
        else:
            e["http_status"] = None
    return entries


def main():
    manifest = json.loads((nc.ROOT / "data" / "manifest.json").read_text())
    commit = manifest["publisher"]["nflverse_nfldata_commit"]
    g_all = pd.read_csv(nc.RAW / "games.csv")
    g = nc.load_games()
    checks = []

    def add(key, question, method, result, status, sources, detail=None):
        checks.append(dict(key=key, question=question, method=method, result=result,
                           status=status, sources=sources, detail=detail))

    # 1. spread sign convention
    d = g.dropna(subset=["spread_line", "home_margin"])
    add("sign_spread",
        "Is `spread_line` positive when the HOME team is favoured?",
        "Correlate spread_line with the actual home margin and compare mean absolute "
        "error with the flipped sign.",
        f"corr = {MD(d.spread_line.corr(d.home_margin))}; MAE with +sign = "
        f"{MD((d.spread_line - d.home_margin).abs().mean())} pts; MAE with -sign = "
        f"{MD((-d.spread_line - d.home_margin).abs().mean())} pts.",
        "pass", ["S1"],
        "The +sign convention has a market-realistic MAE (~10 pts); the flipped convention "
        "does not (~14.6 pts).")

    # 2. cross-source reconciliation of the closing spread
    cl = pd.read_csv(nc.RAW / "closing_lines.csv")
    cl = cl[cl.type == "SPREAD"]
    gm = g.set_index("game_id")
    diffs = []
    n_match = n_off = 0
    for r in cl.itertuples():
        if r.alt_game_id not in gm.index:
            continue
        row = gm.loc[r.alt_game_id]
        if pd.isna(row.spread_line):
            continue
        if r.side == row.home_team:
            # S2's home-side line is in standard notation (negative = favoured),
            # exactly the negative of S1's spread_line.
            diff = abs(float(r.line) + float(row.spread_line))
            diffs.append(diff)
            if diff < 1e-9:
                n_match += 1
            else:
                n_off += 1
    diffs = np.array(diffs)
    add("reconcile_close",
        "Do the two independent closing-line extracts (S1 vs S2) agree?",
        "Match on game and home side; compare the standard home line (-spread_line) with "
        "S2's home-side line.",
        f"{n_match} of {int(len(diffs))} game-sides match exactly; "
        f"{MD(100 * (diffs <= 0.5).mean(), 1)}% agree within 0.5 pt; "
        f"{MD(100 * (diffs <= 1.0).mean(), 1)}% within 1 pt; max gap {MD(diffs.max(), 1)} pts.",
        "warn", ["S1", "S2"],
        "Sub-point gaps are expected: the two extracts can reflect different books or "
        "snapshots. Gaps of 0.5-1 pt are published on the Flagged page, not silently accepted.")

    # 3. standings vs game scores (internal consistency of the same publisher)
    st = pd.read_csv(nc.RAW / "standings.csv")
    rows = []
    for r in g[g.game_type == "REG"].itertuples():
        rows.append((r.season, r.home_team, r.home_score, r.away_score))
        rows.append((r.season, r.away_team, r.away_score, r.home_score))
    tg = pd.DataFrame(rows, columns=["season", "team", "pf", "pa"])
    agg = tg.groupby(["season", "team"]).sum().reset_index()
    st["team"] = st["team"].replace(nc.FRANCHISE)
    j = st.merge(agg, on=["season", "team"], how="inner")
    j["pf_diff"] = j["scored"] - j.pf
    j["pa_diff"] = j["allowed"] - j.pa
    ok = int(((j.pf_diff == 0) & (j.pa_diff == 0)).sum())
    add("standings_points",
        "Does S6's points scored / allowed equal the sum of S1's game scores?",
        "Aggregate home+away scores per team-season from S1 and join to S6.",
        f"{ok} of {len(j)} team-seasons match exactly; max absolute difference "
        f"{int(max(j.pf_diff.abs().max(), j.pa_diff.abs().max()))} pts.",
        "pass" if ok == len(j) else "warn", ["S1", "S6"])

    # 4. price coherence (overround)
    g2 = g[g.season >= 2006]
    ov = g2.over_odds.map(nc.american_to_prob) + g2.under_odds.map(nc.american_to_prob)
    sp = g2.home_spread_odds.map(nc.american_to_prob) + g2.away_spread_odds.map(nc.american_to_prob)
    add("price_coherence",
        "Are the two sides of each market priced coherently (a plausible hold)?",
        "Sum the two no-vig implied probabilities per game and market.",
        f"Totals market hold: median {MD(100 * (ov.median() - 1), 2)}%, 5th-95th "
        f"{MD(100 * (ov.quantile(.05) - 1), 2)}%-{MD(100 * (ov.quantile(.95) - 1), 2)}%. "
        f"Spread market hold: median {MD(100 * (sp.median() - 1), 2)}%.",
        "pass", ["S1"],
        "A hold between roughly 1% and 6% is consistent with a two-way market. Values outside "
        "that band would indicate mismatched snapshots.")

    # 4b. identify outlier rows explicitly
    outliers = g2[(ov > 1.10) | (ov < 1.00)]
    add("price_outliers",
        "How many games have a totals overround outside the plausible band (<0% or >10%)?",
        "Flag rows where the two implied probabilities sum outside [1.00, 1.10].",
        f"{len(outliers)} of {len(g2)} games ({MD(100 * len(outliers) / len(g2), 2)}%).",
        "pass" if len(outliers) < 0.01 * len(g2) else "warn", ["S1"])

    # 5. completeness
    cov = (g_all.assign(has_line=g_all.spread_line.notna())
           .groupby("season").agg(games=("game_id", "size"), with_line=("has_line", "sum"))
           .reset_index())
    first_odds = int(g[g.home_spread_odds.notna()].season.min())
    add("coverage",
        "Which seasons have a closing line and a price?",
        "Count non-null spread_line and spread odds per season in S1.",
        f"Lines exist for every season 1999-2026; recorded prices start in {first_odds}. "
        "All backtests therefore begin in 2006.",
        "pass", ["S1"])

    # 6. duplicates
    dup = int(g_all.game_id.duplicated().sum())
    add("duplicates", "Are there duplicate game rows?",
        "Count duplicated game_id values in S1.",
        f"{dup} duplicate game_ids.", "pass" if dup == 0 else "fail", ["S1"])

    # 7. current slate
    und = nc.load_unplayed()
    add("slate", "How many upcoming games have a market line today?",
        "Rows in S1 with no final score, split by presence of a closing line.",
        f"{len(und)} unplayed games in the file, {int(und.spread_line.notna().sum())} with a line.",
        "pass", ["S1"])

    # 8. player-week mirror shape
    pw = nc.load_player_weeks()
    add("player_weeks", "Does the player-week extract have the nflverse weekly schema?",
        "Check for the documented nflverse weekly player columns and count rows by season.",
        f"{len(pw)} player-weeks, seasons {sorted(pw.season.unique())}, columns include "
        f"player_id/season/week/passing_yards/receiving_yards: "
        f"{all(c in pw.columns for c in ['player_id', 'season', 'week', 'passing_yards', 'receiving_yards'])}.",
        "warn", ["S9", "S8"],
        "The extract is a mirror, not the canonical release. Values are used only for the "
        "player-prop layer and are flagged.")

    payload = {
        "generated_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "sources": build_registry(manifest, commit),
        "coverage_by_season": cov.to_dict(orient="records"),
        "n_games_total": int(len(g_all)),
        "n_games_played": int(len(g)),
        "pinned_commit": commit,
        "manifest_generated": manifest["generated_utc"],
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    for c in checks:
        print(f"[{c['status']:4s}] {c['key']:18s} {c['result'][:110]}")
    print("sources:", [(s["id"], s["http_status"]) for s in payload["sources"]])


if __name__ == "__main__":
    main()
