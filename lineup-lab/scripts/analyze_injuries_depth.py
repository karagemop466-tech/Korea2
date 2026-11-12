#!/usr/bin/env python3
"""LL-4: Ex-ante injury/backup-cascade analysis (2015-2026 Wk 8) + Week 10 live 2026 audit.

Zero leakage: starter definitions use only prior trailing games (< current game_id).
Never imputes -110 odds or defensive snap counts where source extracts are empty/zero.
Outputs lineup-lab/data/injuries_depth.json.
"""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def load_team_week_map() -> dict[tuple[str, str], dict[str, str]]:
    tw = C.load_csv_gz("team_week.csv.gz")
    out: dict[tuple[str, str], dict[str, str]] = {}
    for r in tw:
        if r["season_type"] != "REG":
            continue
        out[(r["game_id"], C.std_team(r["team"]))] = r
    return out


def analyze_qb_backups(games: list[dict[str, str]], tw_map: dict[tuple[str, str], dict[str, str]]) -> dict:
    """Identify ex-ante team QB1 vs actual starter for 2015-2026 REG played games."""
    reg_games = [
        r for r in games
        if r["game_type"] == "REG" and int(r["season"]) >= 2015
        and r["home_score"] != "" and r["away_score"] != ""
        and r["away_qb_name"] != "" and r["home_qb_name"] != ""
    ]
    reg_games.sort(key=lambda r: (int(r["season"]), int(r["week"]), r["gameday"], r["game_id"]))

    team_history: dict[tuple[int, str], list[str]] = defaultdict(list)
    qb_career_starts: dict[str, int] = defaultdict(int)

    groups = {
        "incumbent_qb1": [],
        "backup_qb_all": [],
        "backup_qb_experienced": [],  # prior_starts >= 5
        "backup_qb_inexperienced": [],  # prior_starts < 5
    }

    for g in reg_games:
        season = int(g["season"])
        week = int(g["week"])
        spread = C.fnum(g["spread_line"])  # >0 => home favored
        total_line = C.fnum(g["total_line"])
        hs = float(g["home_score"])
        aws = float(g["away_score"])
        margin_home = hs - aws
        total_pts = hs + aws

        for side in ("home", "away"):
            team = C.std_team(g[f"{side}_team"])
            qb = g[f"{side}_qb_name"].strip()
            prior_team_qbs = team_history[(season, team)]
            prior_starts = qb_career_starts[qb]
            tw = tw_map.get((g["game_id"], team), {})
            pass_epa = C.fnum(tw.get("passing_epa"))
            pts = hs if side == "home" else aws
            team_margin = margin_home if side == "home" else -margin_home
            exp_margin = (spread if side == "home" else -spread) if spread is not None else None
            margin_vs_spread = (team_margin - exp_margin) if exp_margin is not None else None
            odds = C.fnum(g[f"{side}_spread_odds"])
            spread_res = C.settle_spread(margin_home, spread, side, odds) if spread is not None else None
            over_odds = C.fnum(g["over_odds"])
            over_res = C.settle_total(total_pts, total_line, "over", over_odds) if total_line is not None else None

            # Ex-ante within-season incumbent QB1 (strictly prior starts in same season >= 2)
            is_backup = None
            if len(prior_team_qbs) >= 2:
                counts = defaultdict(int)
                for p in prior_team_qbs:
                    counts[p] += 1
                incumbent, inc_cnt = max(counts.items(), key=lambda kv: kv[1])
                if inc_cnt >= 2:
                    is_backup = (qb != incumbent)

            rec = {
                "season": season,
                "week": week,
                "game_id": g["game_id"],
                "team": team,
                "qb": qb,
                "prior_starts": prior_starts,
                "pts": pts,
                "pass_epa": pass_epa,
                "margin_vs_spread": margin_vs_spread,
                "total_vs_line": (total_pts - total_line) if total_line is not None else None,
                "spread_res": spread_res,
                "over_res": over_res,
            }
            if is_backup is False:
                groups["incumbent_qb1"].append(rec)
            elif is_backup is True:
                groups["backup_qb_all"].append(rec)
                if prior_starts >= 5:
                    groups["backup_qb_experienced"].append(rec)
                else:
                    groups["backup_qb_inexperienced"].append(rec)

        # Update histories strictly AFTER game evaluation (zero leakage)
        for side in ("home", "away"):
            team = C.std_team(g[f"{side}_team"])
            qb = g[f"{side}_qb_name"].strip()
            team_history[(season, team)].append(qb)
            qb_career_starts[qb] += 1

    def summarize(rows: list[dict], label: str) -> dict:
        n = len(rows)
        pts = [r["pts"] for r in rows]
        epas = [r["pass_epa"] for r in rows if r["pass_epa"] is not None]
        mvs = [r["margin_vs_spread"] for r in rows if r["margin_vs_spread"] is not None]
        tvl = [r["total_vs_line"] for r in rows if r["total_vs_line"] is not None]
        s_bets = [r["spread_res"] for r in rows if r["spread_res"] is not None and r["spread_res"][0] != "push"]
        s_wins = sum(1 for r in s_bets if r[0] == "win")
        s_prof = sum(r[1] for r in s_bets)
        o_bets = [r["over_res"] for r in rows if r["over_res"] is not None and r["over_res"][0] != "push"]
        o_wins = sum(1 for r in o_bets if r[0] == "win")
        return {
            "cohort": label,
            "team_starts": n,
            "avg_points": round(sum(pts) / n, 2) if n else None,
            "avg_passing_epa": round(sum(epas) / len(epas), 2) if epas else None,
            "avg_margin_vs_spread": round(sum(mvs) / len(mvs), 2) if mvs else None,
            "avg_total_vs_line": round(sum(tvl) / len(tvl), 2) if tvl else None,
            "ats_decided": len(s_bets),
            "ats_win_pct": round(s_wins / len(s_bets), 4) if s_bets else None,
            "ats_roi_stored_odds": round(s_prof / len(s_bets), 4) if s_bets else None,
            "over_win_pct": round(o_wins / len(o_bets), 4) if o_bets else None,
            "sources": ["SRC-GITHUB-REPO"],
        }

    return {
        "cohorts": [
            summarize(groups["incumbent_qb1"], "Ex-ante incumbent QB1"),
            summarize(groups["backup_qb_all"], "Backup QB starting (all)"),
            summarize(groups["backup_qb_experienced"], "Backup QB starting (>= 5 career starts)"),
            summarize(groups["backup_qb_inexperienced"], "Backup/rookie QB (< 5 career starts)"),
        ],
        "recent_examples": [
            {k: r[k] for k in ("game_id", "team", "qb", "prior_starts", "pts", "margin_vs_spread")}
            for r in groups["backup_qb_inexperienced"][-8:]
        ],
    }


def analyze_skill_absences(games: list[dict[str, str]], tw_map: dict[tuple[str, str], dict[str, str]]) -> list[dict]:
    """Measure ex-ante WR1/RB1/TE1 absence dropoff and next-man-up absorption (2015-2026 Wk 8)."""
    pw = C.load_csv_gz("player_week.csv.gz")
    game_lookup = {g["game_id"]: g for g in games if g["game_type"] == "REG" and int(g["season"]) >= 2015}

    # Index team-week player records by (season, week, team) -> {player_id: row}
    tw_players: dict[tuple[int, int, str], dict[str, dict]] = defaultdict(dict)
    team_games_ordered: dict[tuple[int, str], list[tuple[int, str]]] = defaultdict(list)
    seen_tg = set()
    for r in pw:
        if r["season_type"] != "REG" or int(r["season"]) < 2015:
            continue
        pos = r["position"]
        if pos not in ("WR", "RB", "TE"):
            continue
        season = int(r["season"])
        week = int(r["week"])
        team = C.std_team(r["team"])
        tg_key = (season, week, team)
        tw_players[tg_key][r["player_id"]] = {
            "name": r["player_display_name"],
            "pos": pos,
            "targets": float(r["targets"] or 0),
            "carries": float(r["carries"] or 0),
            "rec_yds": float(r["receiving_yards"] or 0),
            "rush_yds": float(r["rushing_yards"] or 0),
        }
        if (season, week, team) not in seen_tg:
            seen_tg.add((season, week, team))
            team_games_ordered[(season, team)].append((week, r["opponent_team"]))

    # Map (season, week, team) -> game_id from tw_map
    sw_to_gid = {}
    for (gid, team), r in tw_map.items():
        sw_to_gid[(int(r["season"]), int(r["week"]), team)] = gid

    results = []
    for pos, metric in (("WR", "targets"), ("RB", "carries"), ("TE", "targets")):
        out_rows = []
        present_rows = []
        backup_gains = []
        for (season, team), wk_list in sorted(team_games_ordered.items()):
            wk_list = sorted(set(wk_list))
            for idx in range(3, len(wk_list)):
                week = wk_list[idx][0]
                gid = sw_to_gid.get((season, week, team))
                if not gid or gid not in game_lookup:
                    continue
                g = game_lookup[gid]
                if g["home_score"] == "" or g["away_score"] == "":
                    continue
                # Prior 3 team games strictly < week
                prior_wks = [wk_list[j][0] for j in range(idx - 3, idx)]
                vol: dict[str, float] = defaultdict(float)
                appear: dict[str, int] = defaultdict(int)
                for pw_wk in prior_wks:
                    for pid, pinfo in tw_players[(season, pw_wk, team)].items():
                        if pinfo["pos"] == pos and pinfo[metric] > 0:
                            vol[pid] += pinfo[metric]
                            appear[pid] += 1
                eligible = [(pid, v) for pid, v in vol.items() if appear[pid] >= 2]
                eligible.sort(key=lambda x: -x[1])
                if len(eligible) < 2:
                    continue
                star_id, star_prior = eligible[0]
                bak_id, bak_prior = eligible[1]
                star_avg_prior = star_prior / appear[star_id]
                bak_avg_prior = bak_prior / appear[bak_id]
                # Require true alpha role
                if pos == "WR" and star_avg_prior < 6.0:
                    continue
                if pos == "RB" and star_avg_prior < 10.0:
                    continue
                if pos == "TE" and star_avg_prior < 4.5:
                    continue

                cur_map = tw_players[(season, week, team)]
                star_cur = cur_map.get(star_id, {}).get(metric, 0.0)
                bak_cur = cur_map.get(bak_id, {}).get(metric, 0.0)

                side = "home" if C.std_team(g["home_team"]) == team else "away"
                hs = float(g["home_score"])
                aws = float(g["away_score"])
                margin_home = hs - aws
                pts = hs if side == "home" else aws
                spread = C.fnum(g["spread_line"])
                exp_margin = (spread if side == "home" else -spread) if spread is not None else None
                team_margin = margin_home if side == "home" else -margin_home
                mvs = (team_margin - exp_margin) if exp_margin is not None else None
                tw = tw_map.get((gid, team), {})
                off_epa = (C.fnum(tw.get("passing_epa")) or 0.0) + (C.fnum(tw.get("rushing_epa")) or 0.0)
                spread_res = C.settle_spread(margin_home, spread, side, C.fnum(g[f"{side}_spread_odds"])) if spread is not None else None

                row_obj = {"pts": pts, "mvs": mvs, "off_epa": off_epa, "spread_res": spread_res}
                if star_cur == 0.0:
                    out_rows.append(row_obj)
                    if bak_cur > 0.0:
                        backup_gains.append(bak_cur - bak_avg_prior)
                else:
                    present_rows.append(row_obj)

        def mean_of(lst, k):
            vals = [x[k] for x in lst if x[k] is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        s_bets = [x["spread_res"] for x in out_rows if x["spread_res"] is not None and x["spread_res"][0] != "push"]
        s_wins = sum(1 for r in s_bets if r[0] == "win")
        s_prof = sum(r[1] for r in s_bets)
        results.append({
            "role": f"Ex-ante {pos}1",
            "threshold": f">= {6.0 if pos=='WR' else (10.0 if pos=='RB' else 4.5)} trailing {metric}/gm",
            "absent_games": len(out_rows),
            "present_games": len(present_rows),
            "pts_when_absent": mean_of(out_rows, "pts"),
            "pts_when_present": mean_of(present_rows, "pts"),
            "pts_delta": round((mean_of(out_rows, "pts") or 0) - (mean_of(present_rows, "pts") or 0), 2),
            "epa_delta": round((mean_of(out_rows, "off_epa") or 0) - (mean_of(present_rows, "off_epa") or 0), 2),
            "avg_margin_vs_spread_when_absent": mean_of(out_rows, "mvs"),
            "ats_win_pct_when_absent": round(s_wins / len(s_bets), 4) if s_bets else None,
            "ats_roi_stored_odds": round(s_prof / len(s_bets), 4) if s_bets else None,
            "backup_avg_volume_gain": round(sum(backup_gains) / len(backup_gains), 2) if backup_gains else None,
            "sources": ["SRC-GITHUB-REPO"],
        })
    return results


def analyze_def_ol_extract_sparsity(tw_map: dict[tuple[str, str], dict[str, str]], games: list[dict[str, str]]) -> dict:
    """Prove defensive/OL player extract emptiness and compute observable team-level sack shock."""
    pw = C.load_csv_gz("player_week.csv.gz")
    pos_counts = defaultdict(int)
    nonzero_counts = defaultdict(int)
    numeric_cols = [
        "completions", "attempts", "passing_yards", "passing_tds",
        "carries", "rushing_yards", "receptions", "targets", "receiving_yards",
    ]
    for r in pw:
        pg = r["position_group"]
        if pg in ("DB", "DL", "LB", "OL"):
            pos_counts[pg] += 1
            if any(float(r[c] or 0) != 0.0 for c in numeric_cols):
                nonzero_counts[pg] += 1

    # Team-level observable sack shock (def_sacks drop >= 2 vs prior 4 gms OR sacks_suffered jump >= 2)
    game_lookup = {g["game_id"]: g for g in games if g["game_type"] == "REG" and int(g["season"]) >= 2015}
    team_series: dict[tuple[int, str], list[tuple[int, str, dict[str, str]]]] = defaultdict(list)
    for (gid, team), r in tw_map.items():
        if gid in game_lookup:
            team_series[(int(r["season"]), team)].append((int(r["week"]), gid, r))

    ol_shock_pts_allowed = []
    ol_normal_pts_allowed = []
    ol_shock_pts_scored = []
    ol_normal_pts_scored = []
    for (season, team), rows in team_series.items():
        rows.sort(key=lambda x: x[0])
        for i in range(4, len(rows)):
            wk, gid, cur = rows[i]
            g = game_lookup[gid]
            if g["home_score"] == "" or g["away_score"] == "":
                continue
            prior_sacks_suf = [float(rows[j][2]["sacks_suffered"] or 0) for j in range(i - 4, i)]
            avg_ss = sum(prior_sacks_suf) / 4.0
            cur_ss = float(cur["sacks_suffered"] or 0)
            side = "home" if C.std_team(g["home_team"]) == team else "away"
            pts_for = float(g["home_score"]) if side == "home" else float(g["away_score"])
            pts_ag = float(g["away_score"]) if side == "home" else float(g["home_score"])
            if cur_ss - avg_ss >= 2.5:
                ol_shock_pts_scored.append(pts_for)
            else:
                ol_normal_pts_scored.append(pts_for)
            prior_def_sacks = [float(rows[j][2]["def_sacks"] or 0) for j in range(i - 4, i)]
            avg_ds = sum(prior_def_sacks) / 4.0
            cur_ds = float(cur["def_sacks"] or 0)
            if avg_ds - cur_ds >= 2.0:
                ol_shock_pts_allowed.append(pts_ag)
            else:
                ol_normal_pts_allowed.append(pts_ag)

    return {
        "player_week_def_ol_rows": dict(sorted(pos_counts.items())),
        "player_week_def_ol_nonzero_stat_rows": dict(sorted(nonzero_counts.items())),
        "historical_def_snap_dropoff": "",
        "historical_ol_snap_dropoff": "",
        "team_level_pass_protection_collapse": {
            "definition": "sacks_suffered >= trailing 4-gm mean + 2.5 (proxy for OT/OL breakdown)",
            "shock_games": len(ol_shock_pts_scored),
            "avg_pts_scored_shock": round(sum(ol_shock_pts_scored) / len(ol_shock_pts_scored), 2),
            "avg_pts_scored_normal": round(sum(ol_normal_pts_scored) / len(ol_normal_pts_scored), 2),
        },
        "team_level_pass_rush_collapse": {
            "definition": "def_sacks <= trailing 4-gm mean - 2.0 (proxy for EDGE/DT absence)",
            "shock_games": len(ol_shock_pts_allowed),
            "avg_pts_allowed_shock": round(sum(ol_shock_pts_allowed) / len(ol_shock_pts_allowed), 2),
            "avg_pts_allowed_normal": round(sum(ol_normal_pts_allowed) / len(ol_normal_pts_allowed), 2),
        },
            "sources": ["SRC-GITHUB-REPO", "SRC-NFL-GENIUS"],
    }


def build_week10_live_audit() -> dict:
    """Verified Week 10 (2026-11-12) official injury clusters + 9-club depth-chart cascade audit."""
    reg10_discrepancies = [
        {
            "team": "SEA",
            "reg10_page_status": "Says 'No Injuries Reported'",
            "official_nov11_roundup_fact": "12 players listed on official Nov 11 practice report: QB1 Sam Darnold (Out), QB2 Drew Lock (LP), LT Charles Cross (DNP), G Quenton Nelson (DNP), DT Leonard Williams (DNP), DT Jarran Reed (DNP), WR Cooper Kupp (DNP), RB Kenneth Walker III (LP) + 4 more.",
            "action_impact": "CRITICAL feed discrepancy: an automated scraper reading only /injuries/league/2026/REG10 misses QB1 Out and 4 trench starters DNP.",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-SEA-DARNOLD"],
        },
        {
            "team": "CIN",
            "reg10_page_status": "Says 'No Injuries Reported'",
            "official_nov11_roundup_fact": "3 injured players reported in Nov 11 roundup ahead of PIT @ CIN.",
            "action_impact": "Feed lag/omission between team Wed report and REG10 league table.",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-ROUNDUP-NOV11"],
        },
        {
            "team": "BAL",
            "reg10_page_status": "Says 'No Injuries Reported' (IR omitted)",
            "official_nov11_roundup_fact": "QB1 Lamar Jackson (elbow, IR 6-9 wks) and QB2 Tyler Huntley (turf toe, IR) omitted from active game status table; 3rd-string QB Joe Fagnano started Wk 9 TNF; BAL acquired QB Jacoby Brissett from AZ.",
            "action_impact": "Severe starter downgrade invisible if scraping only weekly REG10 active injury status without IR/transactions.",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-BAL-JACKSON", "SRC-CLUB-BAL-DC"],
        },
        {
            "team": "LAC",
            "reg10_page_status": "Says 'No Injuries Reported'",
            "official_nov11_roundup_fact": "0-8 LAC enters Week 10 MNF at BAL with blank REG10 table while Thursday injury practice begins Nov 12.",
            "action_impact": "MNF teams release first official report Thursday — Wednesday blank is normal schedule cadence, unlike Sun/TNF games.",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-SCHED-W10"],
        },
    ]

    week10_matchup_impacts = [
        {
            "matchup": "WAS @ NYG (Thu)",
            "key_injuries": "WAS: Colson Yankoff (Out), C Lucas Patrick (Out); NYG: Marcus Harrison (Q).",
            "cascade_cluster": "WAS interior OL/TE depth tested without C Lucas Patrick (omitted on club DC) and TE Colson Yankoff.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-INJURY-ARTICLE-W10", "SRC-CLUB-WAS-DC"],
        },
        {
            "matchup": "NE @ DET (Munich)",
            "key_injuries": "NE: C Ben Brown (Out), CB Carlton Davis (Out), RB TreVeyon Henderson (Out), G Greg Van Roten (LP, omitted on club DC); DET: CB D.J. Reed (DNP), C/G Cade Mays (DNP), QB Jared Goff (LP), WR Amon-Ra St. Brown (LP), S Brian Branch (LP), S Kerby Joseph (LP).",
            "cascade_cluster": "NE loses starting C + CB1 + RB depth while G Van Roten is LP; DET secondary cluster (Reed DNP + Branch LP + Joseph LP) + interior OL Mays DNP.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-INJURY-ARTICLE-W10", "SRC-NFL-INJURIES-W10", "SRC-CLUB-NE-DC", "SRC-CLUB-DET-DC"],
        },
        {
            "matchup": "MIA @ IND",
            "key_injuries": "MIA: QB1 Malik Willis (groin, IR Wks 10-13) -> rookie/backup Kyle McCord 1st NFL start; MIA club DC leaves QB2-QB4 & K blank; IND: LB Jaylon Carlies (DNP), LB Germaine Pratt/Akeem Davis-Gaither (DNP), S Genesis Haulcy (DNP), CB Xavier Rhodes (DNP).",
            "cascade_cluster": "Dual-side vulnerability: MIA raw backup QB McCord vs IND depleted CB/LB second level (4 defensive starters DNP).",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-MIA-WILLIS", "SRC-CLUB-MIA-DC", "SRC-NFL-INJURIES-W10", "SRC-CLUB-IND-DC"],
        },
        {
            "matchup": "SEA @ LV",
            "key_injuries": "SEA: QB1 Sam Darnold (Out) -> QB2 Drew Lock (LP) -> QB3 Jalen Milroe; LT Charles Cross (DNP), G Quenton Nelson (DNP), DT Leonard Williams (DNP), DT Jarran Reed (DNP), WR Cooper Kupp (DNP); LV: traded QB1 Kirk Cousins to MIN Nov 10.",
            "cascade_cluster": "Major two-way QB & trench shock: Darnold Out + left-side OL Cross/Nelson DNP + DL Williams/Reed DNP vs LV post-Cousins QB uncertainty.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-SEA-DARNOLD", "SRC-NFL-ROUNDUP-NOV11", "SRC-CLUB-SEA-DC"],
        },
        {
            "matchup": "LA @ ARI",
            "key_injuries": "LA: WR1 Puka Nacua (DNP, likely IR), CB Trent McDuffie (DNP), S Kamren Curl (DNP), LG Steve Avila (DNP), DE Myles Garrett (LP); ARI: rookie 3rd-rounder Carson Beck starts after Jacoby Brissett traded to BAL; S Budda Baker (DNP), C Hjalte Froholdt (DNP), EDGE Josh Sweat (DNP).",
            "cascade_cluster": "WR1 + secondary shock on LA (Davante Adams/Tutu Atwell absorb targets) vs rookie QB3 Carson Beck behind C1 Froholdt DNP + defensive anchors Baker/Sweat DNP.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-LAR-NACUA", "SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-INJURIES-W10", "SRC-CLUB-LAR-DC"],
        },
        {
            "matchup": "MIN @ GB",
            "key_injuries": "MIN: newly acquired Kirk Cousins (Nov 10 trade), QB Carson Wentz (LP), RB Kenneth Murray/TE T.J. Hockenson (DNP); GB: RB1 Josh Jacobs (Out -> Emanuel Wilson/Chris Brooks), EDGE Micah Parsons (LP, omitted on club DC), EDGE Lukas Van Ness (DNP), LB Zaire Franklin (DNP), S Javon Bullard (DNP).",
            "cascade_cluster": "MIN short-week playbook integration for Cousins vs GB missing RB1 Jacobs Out and pass-rush/LB rotation thin.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-INJURIES-W10", "SRC-CLUB-GB-DC"],
        },
        {
            "matchup": "SF @ DAL & PIT @ CIN & LAC @ BAL",
            "key_injuries": "SF: LT Trent Williams (DNP), CB Deommodore Lenoir (DNP), WR Deebo Samuel (LP); DAL: TE Jake Ferguson (DNP), S Malik Hooker (DNP), EDGE Von Miller (DNP); PIT: EDGE T.J. Watt (DNP), DT Cam Heyward (DNP); BAL: Jackson/Huntley IR -> Brissett/Fagnano.",
            "cascade_cluster": "Elite pass-rusher/LT cluster status: Trent Williams, T.J. Watt, Cam Heyward, and Von Miller all DNP Wednesday ahead of pivotal Sunday/Monday matchups.",
            "snap_share_verified": "",
            "sources": ["SRC-NFL-INJURIES-W10", "SRC-NFL-BAL-JACKSON", "SRC-CLUB-BAL-DC"],
        },
    ]

    club_depth_audit = [
        {
            "team": "NE",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Drake Maye -> QB2 Joshua Dobbs -> QB3 Tommy DeVito; RB1 Rhamondre Stevenson -> RB2 TreVeyon Henderson (OUT Wk 10).",
            "defense_ol_cascade": "LT1 Will Campbell -> LT2 Marcus Bryant; C1 Ben Brown (OUT Wk 10) -> Jared Wilson; G Greg Van Roten (LP); CB1 Christian Gonzalez -> CB2 Carlton Davis (OUT Wk 10).",
            "audit_gap": "Several 3rd/4th-string OL/DB slots left blank; active G Greg Van Roten omitted from depth table while LP on REG10.",
            "sources": ["SRC-CLUB-NE-DC", "SRC-NFL-INJURY-ARTICLE-W10", "SRC-NFL-INJURIES-W10"],
        },
        {
            "team": "IND",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Daniel Jones -> QB2 Riley Leonard; RB1 Jonathan Taylor -> RB2 DJ Giddens; WR1 Michael Pittman Jr. / Josh Downs.",
            "defense_ol_cascade": "CB/LB starter tiers (Carlies, Davis-Gaither, Haulcy, Rhodes all DNP Wed).",
            "audit_gap": "LS2-LS4 and CB3-4 empty; backup LB/CB snap distribution unverifiable in extracts.",
            "sources": ["SRC-CLUB-IND-DC", "SRC-NFL-INJURIES-W10"],
        },
        {
            "team": "WAS",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Jayden Daniels -> QB2 Marcus Mariota -> QB3 Sam Hartman; WR1 Terry McLaurin / Deebo Samuel.",
            "defense_ol_cascade": "LT1 Laremy Tunsil; RT1 Josh Conerly Jr.; C/G Lucas Patrick (OUT Wk 10, concussion).",
            "audit_gap": "Active C/G Lucas Patrick omitted from club depth table while ruled Out on official TNF injury report.",
            "sources": ["SRC-CLUB-WAS-DC", "SRC-NFL-INJURY-ARTICLE-W10", "SRC-NFL-INJURIES-W10"],
        },
        {
            "team": "MIA",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Malik Willis (IR Wks 10-13) -> rookie/backup Kyle McCord (1st NFL start); RB1 De'Von Achane.",
            "defense_ol_cascade": "OL/DB depth cascades thinned by blank secondary slots.",
            "audit_gap": "QB2, QB3, QB4, and K slots completely blank on live club depth chart during QB1 IR transition.",
            "sources": ["SRC-CLUB-MIA-DC", "SRC-NFL-MIA-WILLIS"],
        },
        {
            "team": "SEA",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Sam Darnold (OUT Wk 10) -> QB2 Drew Lock (LP) -> QB3 Jalen Milroe; WR1 Jaxon Smith-Njigba / Cooper Kupp (DNP).",
            "defense_ol_cascade": "LT1 Charles Cross (DNP), LG Quenton Nelson (DNP, omitted on club DC), DT1 Leonard Williams (DNP), DT2 Jarran Reed (DNP).",
            "audit_gap": "Club DC omits Quenton Nelson despite Wed DNP; official REG10 league table falsely prints 'No Injuries Reported'.",
            "sources": ["SRC-CLUB-SEA-DC", "SRC-NFL-ROUNDUP-NOV11", "SRC-NFL-SEA-DARNOLD"],
        },
        {
            "team": "BAL",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Lamar Jackson (IR) -> QB2 Tyler Huntley (IR) -> QB3 Joe Fagnano (Wk 9 TNF starter) / newly traded Jacoby Brissett.",
            "defense_ol_cascade": "Tyler Linderbaum C1; Kyle Hamilton S1 / Roquan Smith LB1.",
            "audit_gap": "Stale depth chart still lists injured Huntley & retired/former K Tyler Loop while omitting Fagnano and Brissett.",
            "sources": ["SRC-CLUB-BAL-DC", "SRC-NFL-BAL-JACKSON", "SRC-NFL-ROUNDUP-NOV11"],
        },
        {
            "team": "LA",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Matthew Stafford; WR1 Puka Nacua (DNP, likely IR) -> Davante Adams / Jordan Whittington / Tutu Atwell; LG1 Steve Avila (DNP).",
            "defense_ol_cascade": "EDGE Myles Garrett (LP); CB Trent McDuffie (DNP); S Kamren Curl (DNP).",
            "audit_gap": "CRITICAL STALE ROSTER ARTIFACT: club depth chart still prints Aaron Donald at DE1 despite retirement/Myles Garrett era.",
            "sources": ["SRC-CLUB-LAR-DC", "SRC-NFL-LAR-NACUA", "SRC-NFL-INJURIES-W10"],
        },
        {
            "team": "DET",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Jared Goff (LP); WR1 Amon-Ra St. Brown (LP) -> Jameson Williams -> Kalif Raymond; C/G Cade Mays (DNP).",
            "defense_ol_cascade": "CB1 D.J. Reed (DNP) -> Terrion Arnold / Amik Robertson; S1 Brian Branch (LP); S Kerby Joseph (LP, omitted on club DC).",
            "audit_gap": "Omits S Kerby Joseph while listing him LP on Wed injury report; secondary depth heavily stressed before Munich kickoff.",
            "sources": ["SRC-CLUB-DET-DC", "SRC-NFL-INJURIES-W10"],
        },
        {
            "team": "GB",
            "unofficial_banner": True,
            "offense_cascade": "QB1 Jordan Love; RB1 Josh Jacobs (OUT Wk 10) -> RB2 Emanuel Wilson -> RB3 Chris Brooks; WR Romeo Doubs / Jayden Reed / Matthew Golden.",
            "defense_ol_cascade": "EDGE Lukas Van Ness (DNP), LB Zaire Franklin (DNP), S Javon Bullard (DNP), EDGE Micah Parsons (LP).",
            "audit_gap": "Club depth chart omits superstar EDGE Micah Parsons despite LP listing on official NFL.com REG10 injury report.",
            "sources": ["SRC-CLUB-GB-DC", "SRC-NFL-INJURIES-W10"],
        },
    ]

    return {
        "reg10_discrepancies": reg10_discrepancies,
        "week10_matchup_impacts": week10_matchup_impacts,
        "club_depth_audit": club_depth_audit,
    }


def main() -> int:
    games = C.load_csv_gz("games.csv.gz")
    tw_map = load_team_week_map()

    qb_res = analyze_qb_backups(games, tw_map)
    skill_res = analyze_skill_absences(games, tw_map)
    def_ol = analyze_def_ol_extract_sparsity(tw_map, games)
    live_w10 = build_week10_live_audit()

    out = {
        "meta": {
            "verified_on": C.VERIFIED_DATE,
            "scope": "2015-2026 Wk 8 ex-ante historical cascades + 2026 Wk 10 live injury/depth audit",
            "no_imputation": "Defensive/OL individual snap-share dropoffs left blank ('') where extracts have 0/empty values.",
        },
        "qb_backups": qb_res,
        "skill_absences": skill_res,
        "def_ol_extract_audit": def_ol,
        "live_week10": live_w10,
    }
    C.write_strict_json(C.DATA_DIR / "injuries_depth.json", out)

    print("QB Cohorts:")
    for c in qb_res["cohorts"]:
        print(" ", c["cohort"], "n=", c["team_starts"], "pts=", c["avg_points"], "epa=", c["avg_passing_epa"], "mvs=", c["avg_margin_vs_spread"], "ats=", c["ats_win_pct"])
    print("Skill Absences:")
    for s in skill_res:
        print(" ", s["role"], "out=", s["absent_games"], "pts_delta=", s["pts_delta"], "mvs_out=", s["avg_margin_vs_spread_when_absent"], "bak_gain=", s["backup_avg_volume_gain"])
    print("Def/OL extract rows:", def_ol["player_week_def_ol_rows"], "nonzero=", def_ol["player_week_def_ol_nonzero_stat_rows"])
    print("Team OL sack shock:", def_ol["team_level_pass_protection_collapse"])
    print("Team Def pass-rush shock:", def_ol["team_level_pass_rush_collapse"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
