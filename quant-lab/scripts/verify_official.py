#!/usr/bin/env python3
"""
verify_official.py — line-by-line verification against official nfl.com pages.

What it proves
  1. The nflverse mirror's game results reproduce the official NFL standings exactly
     (W, L, T, PF, PA for all 32 teams, 2025 full season and 2026 to date).
  2. The player game logs transcribed from nfl.com sum to the season totals nfl.com publishes
     on the same page (a transcription audit that does not rely on trust).
  3. An independent cross-source score check: the 2026 Week 8 Panthers-Packers final appears
     identically in the mirror and inside two separate nfl.com player game logs.

Anything that cannot be checked against an official page is written to data/processed/flags.json
and published on flagged.html. Nothing is filled in by inference.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OFF = os.path.join(ROOT, "data", "official")


# nfl.com and the mirror use different abbreviations for one club: nfl.com prints "AZ",
# the mirror prints "ARI". Recorded as a mapping, not silently guessed.
ABBR_ALIAS = {"AZ": "ARI", "ARZ": "ARI", "LAR": "LA", "WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC",
              "STL": "LA"}


def canon(abbr):
    return ABBR_ALIAS.get(abbr, abbr)


def main():
    computed = json.load(open(os.path.join(PROC, "standings_computed.json")))
    checks = []
    flags = []

    for season in (2025, 2026):
        off = json.load(open(os.path.join(OFF, f"standings_{season}.json")))
        comp = {r["team"]: r for r in computed[str(season)]}
        url = off["source_url"]
        # transcription audit on the official side: wins must equal losses, PF must equal PA
        wsum = sum(v[0] for v in off["teams"].values())
        lsum = sum(v[1] for v in off["teams"].values())
        pfsum = sum(v[3] for v in off["teams"].values())
        pasum = sum(v[4] for v in off["teams"].values())
        checks.append({"check": f"official_{season}_internal_balance", "scope": "official capture",
                       "detail": {"sum_w": wsum, "sum_l": lsum, "sum_pf": pfsum, "sum_pa": pasum},
                       "status": "pass" if (wsum == lsum and pfsum == pasum) else "fail",
                       "source_url": url})
        if wsum != lsum or pfsum != pasum:
            flags.append({"item": f"{season} official standings capture does not balance",
                          "why": "transcription error suspected", "source_url": url})
        # team by team
        for team, (w, l, t, pf, pa) in sorted(off["teams"].items()):
            c = comp.get(canon(team))
            ok = c is not None and (c["w"], c["l"], c["t"], c["pf"], c["pa"]) == (w, l, t, pf, pa)
            checks.append({
                "check": f"standings_{season}_{team}", "scope": "mirror vs nfl.com",
                "computed": None if c is None else {"w": c["w"], "l": c["l"], "t": c["t"], "pf": c["pf"], "pa": c["pa"]},
                "official": {"w": w, "l": l, "t": t, "pf": pf, "pa": pa},
                "status": "pass" if ok else "fail", "source_url": url})
            if not ok:
                flags.append({"item": f"{season} {team} standings mismatch",
                              "why": f"mirror {None if c is None else (c['w'],c['l'],c['t'],c['pf'],c['pa'])} "
                                     f"vs nfl.com {(w,l,t,pf,pa)}", "source_url": url})

    # ---------------- player transcription audit ------------------------------
    pdoc = json.load(open(os.path.join(OFF, "players_2026.json")))
    for p in pdoc["players"]:
        tot = p["season_total"]
        vals = [g["value"] for g in p["games"]]
        checks.append({"check": f"player_sum_{p['slug']}", "scope": "nfl.com page internal consistency",
                       "detail": {"games": len(p["games"]), "official_games": tot["g"],
                                  "sum_weekly_yards": sum(vals), "official_season_yards": tot["yds"]},
                       "status": "pass" if (sum(vals) == tot["yds"] and len(p["games"]) == tot["g"]) else "fail",
                       "source_url": p["source_url"]})
        if sum(vals) != tot["yds"] or len(p["games"]) != tot["g"]:
            flags.append({"item": f"player log {p['name']} does not sum to the official season total",
                          "why": "transcription error suspected", "source_url": p["source_url"]})
        for k in ("rec", "att"):
            if k in tot and any(k in g["extra"] for g in p["games"]):
                s = sum(g["extra"].get(k, 0) for g in p["games"])
                checks.append({"check": f"player_sum_{p['slug']}_{k}", "scope": "nfl.com page internal consistency",
                               "detail": {"sum_weekly": s, "official_season": tot[k]},
                               "status": "pass" if s == tot[k] else "fail", "source_url": p["source_url"]})
                if s != tot[k]:
                    flags.append({"item": f"player log {p['name']} {k} does not sum", "why": "transcription",
                                  "source_url": p["source_url"]})

    # ---------------- cross-source score check --------------------------------
    games = json.load(open(os.path.join(PROC, "games.json")))
    g = next((x for x in games if x["season"] == 2026 and x["home"] == "GB" and x["away"] == "CAR"), None)
    love = next(p for p in pdoc["players"] if p["slug"] == "jordan-love")
    watson = next(p for p in pdoc["players"] if p["slug"] == "christian-watson")
    lg = next(x for x in love["games"] if x["week"] == 8)
    wg = next(x for x in watson["games"] if x["week"] == 8)
    cross_ok = (g is not None and g["home_score"] == lg["team_pts"] == wg["team_pts"]
                and g["away_score"] == lg["opp_pts"] == wg["opp_pts"])
    checks.append({"check": "cross_source_2026_W08_CAR_at_GB", "scope": "mirror vs two nfl.com player logs",
                   "detail": {"mirror": None if g is None else f"{g['away']} {g['away_score']} - {g['home']} {g['home_score']}",
                              "love_log": f"CAR {lg['opp_pts']} - GB {lg['team_pts']}",
                              "watson_log": f"CAR {wg['opp_pts']} - GB {wg['team_pts']}"},
                   "status": "pass" if cross_ok else "fail",
                   "source_url": love["source_url"]})
    if not cross_ok:
        flags.append({"item": "Week 8 score disagreement between mirror and nfl.com player logs",
                      "why": "cannot reconcile", "source_url": love["source_url"]})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = [c for c in checks if c["status"] == "fail"]
    summary = {
        "checks_total": len(checks), "passed": passed, "failed": len(failed),
        "flags": flags,
        "generated_from": {
            "official": ["https://www.nfl.com/standings/league/2025/REG",
                         "https://www.nfl.com/standings/league/2026/REG"] +
                        [p["source_url"] for p in pdoc["players"]],
            "mirror": ["https://github.com/nflverse/nfldata (pinned commit a270278f3ac4e937295fe6a27814b3c4a2b62645)"],
        },
    }
    json.dump({"summary": summary, "checks": checks}, open(os.path.join(PROC, "verification.json"), "w"), indent=1)
    json.dump(flags, open(os.path.join(PROC, "flags.json"), "w"), indent=1)
    print(f"checks: {len(checks)}  pass: {passed}  fail: {len(failed)}  flags: {len(flags)}")
    for c in failed[:10]:
        print("  FAIL", c["check"], c.get("computed"), "vs", c.get("official"))


if __name__ == "__main__":
    main()
