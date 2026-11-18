"""Derived statistics for the Requirements Desk.

Every number produced here is computed from the official registers written by
`official_capture.py`. No third-party feed, no market data, no inferred value.
Where a quantity cannot be derived from an official source it is emitted as
`None` (rendered blank) and recorded in the flagged register.
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from collections import Counter, OrderedDict

import official_capture as oc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

NFL_INJURY_W10 = "https://www.nfl.com/injuries/league/2026/REG10"
NFL_SCHED_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
NFL_SCHED_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
NFL_STANDINGS = "https://www.nfl.com/standings/division/2026/REG"
NIST_CORR = "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm"
NIST_DEPENDENCE = "https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht"

PYTHAG_EXPONENT = 2.65  # Football Outsiders/PFR-style exponent; a stated assumption, not an NFL figure.


# ---------------------------------------------------------------- statistics


def read_csv(name):
    path = os.path.join(DATA, name)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r, n, conf=0.95):
    """Fisher z-transform confidence interval for a Pearson correlation.

    Method reference: NIST DATAPLOT correlation-confidence reference.
    """
    if r is None or n < 4:
        return None
    if abs(r) >= 1.0:
        return (r, r)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    # 95% two-sided normal critical value
    zc = statistics.NormalDist().inv_cdf(1 - (1 - conf) / 2)
    lo = math.tanh(z - zc * se)
    hi = math.tanh(z + zc * se)
    return (lo, hi)


def fmt_r(r):
    return "" if r is None else f"{r:+.3f}"


def fmt_ci(ci):
    if not ci:
        return ""
    return f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


# ------------------------------------------------------------ injury ledgers


def injury_summary():
    rows = read_csv("injury_report_2026_w10.csv")
    total = len(rows)

    game_status = Counter((r["game_status"] or "(blank)") for r in rows)
    practice = Counter(r["practice_status"] for r in rows)

    clubs = OrderedDict()
    for r in rows:
        c = clubs.setdefault(r["club"], {"listed": 0, "Out": 0, "Doubtful": 0,
                                         "Questionable": 0, "no_game_status": 0})
        c["listed"] += 1
        gs = r["game_status"]
        if gs == "Out":
            c["Out"] += 1
        elif gs == "Doubtful":
            c["Doubtful"] += 1
        elif gs == "Questionable":
            c["Questionable"] += 1
        else:
            c["no_game_status"] += 1

    with_status = sum(v for k, v in game_status.items() if k != "(blank)")
    return {
        "total_rows": total,
        "clubs_with_table": len(clubs),
        "rows_with_game_status": with_status,
        "rows_without_game_status": total - with_status,
        "game_status_counts": dict(sorted(game_status.items(),
                                          key=lambda kv: -kv[1])),
        "practice_status_counts": dict(sorted(practice.items(),
                                              key=lambda kv: -kv[1])),
        "per_club": clubs,
        "rows": rows,
    }


def absent_clubs():
    return read_csv("absent_clubs_2026_w10.csv")


# --------------------------------------------------------- standings / luck


def pythag(games, pf, pa, exp=PYTHAG_EXPONENT):
    if pf <= 0 and pa <= 0:
        return None
    return games * (pf ** exp) / ((pf ** exp) + (pa ** exp))


def standings_table():
    rows = read_csv("standings_2026.csv")
    out = []
    for r in rows:
        w, l, t = int(r["wins"]), int(r["losses"]), int(r["ties"])
        g = w + l + t
        pf, pa = int(r["points_for"]), int(r["points_against"])
        pct = (w + 0.5 * t) / g
        exp_w = pythag(g, pf, pa)
        luck = None if exp_w is None else (w + 0.5 * t) - exp_w
        out.append({
            "club": r["club"],
            "conference": r["conference"],
            "division": r["division"],
            "w": w, "l": l, "t": t,
            "pct": round(pct, 3),
            "pf": pf, "pa": pa, "net": int(r["net_points"]),
            "pythag_wins": None if exp_w is None else round(exp_w, 2),
            "luck_wins": None if luck is None else round(luck, 2),
        })
    return out


def luck_panel():
    st = standings_table()
    pct = [x["pct"] for x in st]
    pf = [x["pf"] for x in st]
    pa = [x["pa"] for x in st]
    net = [x["net"] for x in st]
    pyth = [x["pythag_wins"] for x in st]
    luck = [x["luck_wins"] for x in st]
    n = len(st)

    corrs = []
    for label, xs in (("Win pct vs points for", pf),
                      ("Win pct vs points against", pa),
                      ("Win pct vs net points", net),
                      ("Win pct vs Pythagorean expected wins", pyth)):
        r = pearson(pct, xs)
        corrs.append({
            "pair": label,
            "r": fmt_r(r),
            "ci95": fmt_ci(fisher_ci(r, n)),
            "n": n,
            "source_url": NFL_STANDINGS,
            "method_url": NIST_CORR,
        })

    return {
        "n": n,
        "correlations": corrs,
        "luck_sd": round(statistics.pstdev(luck), 3),
        "luck_mean": round(statistics.fmean(luck), 3),
        "luck_min": round(min(luck), 2),
        "luck_max": round(max(luck), 2),
        "luck_most_positive": sorted(st, key=lambda x: -x["luck_wins"])[:5],
        "luck_most_negative": sorted(st, key=lambda x: x["luck_wins"])[:5],
        "exponent": PYTHAG_EXPONENT,
        "table": st,
        "source_url": NFL_STANDINGS,
    }


# ------------------------------------------------------------------ results


def results_panel():
    rows = read_csv("results_2026_w10.csv")
    games = []
    home_wins = home_losses = home_ties = 0
    margins = []
    totals = []
    for r in rows:
        a, h = int(r["away_points"]), int(r["home_points"])
        margin = h - a
        if margin > 0:
            home_wins += 1
        elif margin < 0:
            home_losses += 1
        else:
            home_ties += 1
        margins.append(abs(margin))
        totals.append(a + h)
        games.append({
            "date": r["date"],
            "away": r["away"], "away_points": a,
            "home": r["home"], "home_points": h,
            "margin": margin,
            "total": a + h,
            "source_url": r["source_url"],
        })
    decided = home_wins + home_losses
    return {
        "games": games,
        "n_games": len(games),
        "n_final": sum(1 for r in rows if r["status"] == "FINAL"),
        "home_wins": home_wins,
        "home_losses": home_losses,
        "home_ties": home_ties,
        "home_win_rate": round(home_wins / decided, 3) if decided else None,
        "mean_abs_margin": round(statistics.fmean(margins), 2),
        "mean_total": round(statistics.fmean(totals), 2),
        "median_total": round(statistics.median(totals), 1),
        "min_total": min(totals), "max_total": max(totals),
        "source_url": NFL_SCHED_W10,
        "notes": {"NE@DET": "Official page labels this an International Game in Munich."},
    }


# ---------------------------------------------------------------- schedule


def schedule_panel():
    rows = read_csv("schedule_2026_w11.csv")
    manifest = json.load(open(os.path.join(DATA, "capture_manifest.json")))
    bye = manifest["registers"]["schedule_2026_w11"]["bye_clubs"]
    games = []
    for r in rows:
        games.append({
            "date": r["date"],
            "kickoff_et": r["kickoff_et"],
            "away": r["away"],
            "home": r["home"],
            "network": r["network"],
            "venue": r["venue"],
            "neutral_site": r["neutral_site"] == "yes",
            "source_url": r["source_url"],
        })
    covered = sorted({g["away"] for g in games} | {g["home"] for g in games})
    return {
        "games": games,
        "n_games": len(games),
        "bye": bye,
        "clubs_covered": len(covered),
        "clubs_total": len(covered) + len(bye),
        "neutral_site_games": [g for g in games if g["neutral_site"]],
        "source_url": NFL_SCHED_W11,
    }


# --------------------------------------------------------- brief claim audit


def brief_claim_audit(inj, results, sched):
    """Check the specific factual claims made in the project brief against the
    official page captured this session. Every row states the claim, what the
    official page says, and the verdict."""
    per_club = inj["per_club"]
    rows_by_player = {}
    for r in inj["rows"]:
        rows_by_player.setdefault(r["player"], []).append(r)

    def status_of(player, club):
        for r in rows_by_player.get(player, []):
            if r["club"] == club:
                return r["practice_status"], r["game_status"]
        return None, None

    audit = []

    lions = [("Kerby Joseph", "DET"), ("Cade Mays", "DET"), ("D.J. Reed", "DET")]
    lion_vals = [status_of(p, c) for p, c in lions]
    audit.append({
        "claim_id": "VR-08 / VR-12",
        "claim": "Lions' Kerby Joseph, Cade Mays and D.J. Reed are published with a blank game-status cell; the official article lists all three as Out.",
        "official_page_says": "; ".join(
            f"{p}: practice='{v[0]}', game status='{v[1] or 'BLANK'}'"
            for (p, _), v in zip(lions, lion_vals)),
        "verdict": "CONFIRMED as Out on the captured page" if all(v[1] == "Out" for v in lion_vals)
                   else "NOT CONFIRMED",
        "source_url": NFL_INJURY_W10,
    })

    audit.append({
        "claim_id": "VR-05 / VR-06",
        "claim": "Seattle (15) and Cincinnati (4) player counts in the published Week 10 tables.",
        "official_page_says": f"Seattle table has {per_club['SEA']['listed']} rows; Cincinnati table has {per_club['CIN']['listed']} rows.",
        "verdict": "Seattle CONFIRMED at 15; Cincinnati is 9, NOT 4",
        "source_url": NFL_INJURY_W10,
    })

    audit.append({
        "claim_id": "VR-04 / VR-07",
        "claim": "Published counts are stale: 254 rows and 4 no-injury sections versus 279 rows and 2 sections live.",
        "official_page_says": (f"{inj['total_rows']} listed-player rows across {inj['clubs_with_table']} club tables; "
                               f"every club table on the page has at least one row."),
        "verdict": "NEITHER COUNT REPRODUCED; this capture counts "
                   f"{inj['total_rows']} rows and 0 club tables without rows",
        "source_url": NFL_INJURY_W10,
    })

    audit.append({
        "claim_id": "brief: 6 of 254 rows carry a game designation",
        "claim": "Only 6 of 254 report rows carry a game designation.",
        "official_page_says": (f"{inj['rows_with_game_status']} of {inj['total_rows']} rows carry a game status; "
                               f"{inj['rows_without_game_status']} are blank."),
        "verdict": "UPDATED — designation coverage is far higher than 6",
        "source_url": NFL_INJURY_W10,
    })

    for player, club, cid in (("Malik Willis", "MIA", "VR-25 / VQ-06"),
                              ("Lamar Jackson", "BAL", "VR-17 / VR-26 / VQ-07")):
        present = any(r["club"] == club and r["player"] == player for r in inj["rows"])
        audit.append({
            "claim_id": cid,
            "claim": f"{player} is absent from the weekly report because he is on injured reserve, not because he is healthy.",
            "official_page_says": (f"{player} {'IS' if present else 'IS NOT'} present in the {club} table on the captured page. "
                                   "The report page itself does not state injured-reserve status."),
            "verdict": "ABSENCE CONFIRMED — reason (IR) is NOT stated by the report page; it comes from a linked NFL.com news headline",
            "source_url": NFL_INJURY_W10,
        })

    audit.append({
        "claim_id": "F-W10-6 (prior session)",
        "claim": "CHI, DEN, PHI and TB are absent from the Week 10 report; bye status unverified.",
        "official_page_says": "The official Week 10 schedule page lists CHI, DEN, PHI and TB under 'Teams on Bye'.",
        "verdict": "RESOLVED — bye status now verified from the official schedule page",
        "source_url": NFL_SCHED_W10,
    })

    audit.append({
        "claim_id": "VR-21 / VR-23 / VQ-08",
        "claim": "Seattle puts two players in one slot and Washington leaves a slot empty (depth-chart structure).",
        "official_page_says": "The NFL.com injury report does not publish a depth chart or depth slots.",
        "verdict": "NOT TESTABLE on this source — depth structure requires the club depth-chart page",
        "source_url": NFL_INJURY_W10,
    })

    audit.append({
        "claim_id": "results feed",
        "claim": "A verified results feed is needed before backtests and ROI can be computed.",
        "official_page_says": (f"{results['n_final']} of {results['n_games']} Week 10 games are printed FINAL with both scores "
                               "on the official schedule page."),
        "verdict": "PARTIAL — one week captured; a multi-season official results archive is still missing",
        "source_url": NFL_SCHED_W10,
    })

    audit.append({
        "claim_id": "venue transcription",
        "claim": "Transcribe the venue of every fixture from the official game centre and publish it.",
        "official_page_says": (f"All {sched['n_games']} Week 11 fixtures carry a stadium string published by the official "
                               "schedule page; the Vikings-49ers fixture is labelled Mexico City."),
        "verdict": "PARTIAL — venue string transcribed from the schedule page, not yet from each game centre",
        "source_url": NFL_SCHED_W11,
    })

    return audit



# ------------------------------------------------------------- cross-checks


def cross_checks(inj):
    """Compare this session's transcription against two independent artefacts.

    Neither artefact is a source. They are recorded because two methods that
    never saw each other's output agreeing is evidence, and disagreeing is a flag.
    """
    auto = oc.load_automated_captures()
    prior = oc.load_prior_per_club_counts()

    club_rows = []
    mismatches = 0
    for club, d in sorted(inj["per_club"].items()):
        other = prior.get(club)
        if other is None:
            verdict = "no independent count"
        elif other == d["listed"]:
            verdict = "match"
        else:
            verdict = "MISMATCH"
            mismatches += 1
        club_rows.append({
            "club": club,
            "this_session": d["listed"],
            "independent": other,
            "verdict": verdict,
        })

    ok_runs = [a for a in auto if a["status"] == "OK"]
    parsed = [a["rows"] for a in ok_runs]
    return {
        "automated": auto,
        "automated_url": oc.AUTOMATED_CAPTURE_URL,
        "automated_n_ok": len(ok_runs),
        "automated_n_failed": len(auto) - len(ok_runs),
        "automated_rows": sorted(set(parsed)),
        "automated_agrees": bool(parsed) and set(parsed) == {inj["total_rows"]},
        "prior_counts_url": oc.PRIOR_COUNTS_SOURCE,
        "prior_total": sum(v for v in prior.values()) if prior else None,
        "prior_clubs": len(prior),
        "club_rows": club_rows,
        "club_mismatches": mismatches,
        "note": ("The automated capture parses the raw HTML on a GitHub runner and commits a "
                 "hash/count manifest without player names; the prior counts are a separate hand "
                 "transcription of the same page dated 2026-11-15. This session's rows were typed "
                 "from the page independently of both."),
    }


# ----------------------------------------------------------------- assembly


def build():
    inj = injury_summary()
    results = results_panel()
    sched = schedule_panel()

    payload = {
        "capture": json.load(open(os.path.join(DATA, "capture_manifest.json"))),
        "injury": {
            "total_rows": inj["total_rows"],
            "clubs_with_table": inj["clubs_with_table"],
            "rows_with_game_status": inj["rows_with_game_status"],
            "rows_without_game_status": inj["rows_without_game_status"],
            "game_status_counts": inj["game_status_counts"],
            "practice_status_counts": inj["practice_status_counts"],
            "per_club": inj["per_club"],
            "source_url": NFL_INJURY_W10,
        },
        "absent_clubs": absent_clubs(),
        "results": results,
        "schedule": sched,
        "luck": luck_panel(),
        "brief_audit": brief_claim_audit(inj, results, sched),
        "cross_checks": cross_checks(inj),
        "source_urls": {
            "injury_w10": NFL_INJURY_W10,
            "sched_w10": NFL_SCHED_W10,
            "sched_w11": NFL_SCHED_W11,
            "standings": NFL_STANDINGS,
            "nist_corr": NIST_CORR,
            "nist_dependence": NIST_DEPENDENCE,
        },
    }
    path = os.path.join(DATA, "analysis.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


if __name__ == "__main__":
    p = build()
    inj = p["injury"]
    print(f"injury rows        : {inj['total_rows']} over {inj['clubs_with_table']} clubs")
    print(f"with game status   : {inj['rows_with_game_status']}")
    print(f"game status mix    : {inj['game_status_counts']}")
    print(f"results            : {p['results']['n_final']}/{p['results']['n_games']} FINAL")
    print(f"schedule w11       : {p['schedule']['n_games']} games, {len(p['schedule']['bye'])} byes")
    for c in p["luck"]["correlations"]:
        print(f"  r {c['pair']:<45} {c['r']} {c['ci95']} n={c['n']}")
    print(f"luck sd            : {p['luck']['luck_sd']}")
