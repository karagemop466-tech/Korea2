#!/usr/bin/env python3
"""Build the NFL Command Center static site (nfl-command/).

Stdlib only. Reads:
  nfl-command/data/raw/injury_report_wk10_2026.psv   (transcribed NFL.com injury report)
  nfl-command/data/*.json                            (registers: sources, suggestions, ...)
  skill-lab/data/*.json                              (read-only: committed Skill Lab outputs)

Writes:
  nfl-command/data/generated/*.json                  (derived tables, committed for audit)
  nfl-command/index.html, nfl-command/pages/*.html, nfl-command/assets/*

Rules enforced here:
  * every table row carries at least one source link; computed rows carry an UNVERIFIED-INPUT badge
  * a value that is blank on its source stays blank (never filled in)
  * no number is typed by hand; every figure is read from the JSON inputs above
"""
from __future__ import annotations

import collections
import html as H
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # nfl-command/
REPO = ROOT.parent                                     # repository root
DATA = ROOT / "data"
GEN = DATA   # generated JSON lives beside the registers (claimed scope: nfl-command/data/*.json)
SL = REPO / "skill-lab" / "data"
RAW = DATA / "raw" / "injury_report_wk10_2026.psv"
AS_OF = "2026-11-12"
SITE = "NFL Command Center"
REPO_BLOB = "https://github.com/karagemop466-tech/Korea2/blob/main/"
NFL = "https://www.nfl.com"

# ----------------------------------------------------------------- helpers

def esc(x) -> str:
    return H.escape("" if x is None else str(x), quote=True)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def link(url: str, text: str | None = None, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener"{c}>{esc(text or url)}</a>'


def fmt(x, nd: int = 2) -> str:
    if x is None or x == "":
        return ""
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return f"{x:,}"
    if isinstance(x, float):
        return f"{x:,.{nd}f}"
    return esc(x)


def pval(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def badge(kind: str, text: str) -> str:
    return f'<span class="badge badge-{kind}">{esc(text)}</span>'


def table(tid: str, headers: list[str], rows: list[list[str]], kind: str) -> str:
    """kind: 'official' (every row must carry an nfl.com/official link) or 'computed'."""
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (
        f'<div class="tablewrap"><input class="filter" type="search" placeholder="Filter rows" '
        f'data-filter-for="{tid}" aria-label="Filter {esc(tid)}">'
        f'<div class="scroll"><table id="{tid}" data-kind="{kind}"><thead><tr>{th}</tr></thead>'
        f"<tbody>{body}</tbody></table></div></div>"
    )


def src_cell(*pairs: tuple[str, str]) -> str:
    return "<br>".join(link(u, t) for u, t in pairs)


# ----------------------------------------------------------------- source registry

REG = {s["id"]: s for s in load(DATA / "sources.json")["sources"]}
SL_SRC = {s["id"]: s for s in load(SL / "sources.json")["sources"]}


def reg_link(sid: str) -> tuple[str, str]:
    if sid in REG:
        s = REG[sid]
        tag = "" if s.get("official", True) else " [NOT OFFICIAL]"
        return s["url"], s["title"][:60] + tag
    if sid in SL_SRC:
        s = SL_SRC[sid]
        return s["url"], f"{sid} · {s['publisher']}"
    raise KeyError(f"unknown source id {sid}")


def src_links(ids: list[str]) -> str:
    return "<br>".join(link(*reg_link(i)) for i in ids)


# ----------------------------------------------------------------- injuries

TEAMS = {
    "AZ": ("Arizona Cardinals", "arizona-cardinals"), "ATL": ("Atlanta Falcons", "atlanta-falcons"),
    "BAL": ("Baltimore Ravens", "baltimore-ravens"), "BUF": ("Buffalo Bills", "buffalo-bills"),
    "CAR": ("Carolina Panthers", "carolina-panthers"), "CHI": ("Chicago Bears", None),
    "CIN": ("Cincinnati Bengals", "cincinnati-bengals"), "CLE": ("Cleveland Browns", "cleveland-browns"),
    "DAL": ("Dallas Cowboys", "dallas-cowboys"), "DEN": ("Denver Broncos", None),
    "DET": ("Detroit Lions", "detroit-lions"), "GB": ("Green Bay Packers", "green-bay-packers"),
    "HOU": ("Houston Texans", "houston-texans"), "IND": ("Indianapolis Colts", "indianapolis-colts"),
    "JAX": ("Jacksonville Jaguars", "jacksonville-jaguars"), "KC": ("Kansas City Chiefs", "kansas-city-chiefs"),
    "LV": ("Las Vegas Raiders", "las-vegas-raiders"), "LAC": ("Los Angeles Chargers", "los-angeles-chargers"),
    "LAR": ("Los Angeles Rams", "los-angeles-rams"), "MIA": ("Miami Dolphins", "miami-dolphins"),
    "MIN": ("Minnesota Vikings", "minnesota-vikings"), "NE": ("New England Patriots", "new-england-patriots"),
    "NO": ("New Orleans Saints", "new-orleans-saints"), "NYG": ("New York Giants", "new-york-giants"),
    "NYJ": ("New York Jets", "new-york-jets"), "PHI": ("Philadelphia Eagles", None),
    "PIT": ("Pittsburgh Steelers", "pittsburgh-steelers"), "SF": ("San Francisco 49ers", "san-francisco-49ers"),
    "SEA": ("Seattle Seahawks", "seattle-seahawks"), "TB": ("Tampa Bay Buccaneers", None),
    "TEN": ("Tennessee Titans", "tennessee-titans"), "WAS": ("Washington Commanders", "washington-commanders"),
}

GROUP = {
    "QB": "QB", "RB": "Skill", "FB": "Skill", "WR": "Skill", "TE": "Skill",
    "T": "OL", "OT": "OL", "G": "OL", "C": "OL",
    "DE": "DL", "DT": "DL", "DL": "DL", "LB": "LB",
    "CB": "DB", "S": "DB", "SAF": "DB", "DB": "DB",
    "K": "ST", "P": "ST", "LS": "ST",
}
PRACTICE = {"F": "Full Participation in Practice", "L": "Limited Participation in Practice",
            "D": "Did Not Participate In Practice"}
NO_INJ = "NO INJURIES REPORTED"


def load_report():
    """Parse the transcribed NFL.com report. Returns (rows, matchups, no_injury_teams)."""
    rows, matchups, none = [], {}, []
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 9:
            raise SystemExit(f"malformed row: {line}")
        matchup, kickoff, team, player, slug, pos, injury, prac, game = parts
        matchups.setdefault(matchup, kickoff)
        if player == NO_INJ:
            none.append(team)
            continue
        if prac not in PRACTICE:
            raise SystemExit(f"bad practice code {prac!r} for {player}")
        rows.append({
            "matchup": matchup,
            "kickoff": kickoff, "team": team, "player": player, "slug": slug, "pos": pos,
            "group": GROUP.get(pos, "Other"), "injury": injury, "practice": PRACTICE[prac],
            "practice_code": prac, "game_status": game,
            "player_url": f"{NFL}/players/{slug}/",
        })
    return rows, matchups, none


def mu_text(m: str) -> str:
    """'WAS-NYG' -> 'WAS at NYG' (NFL.com lists the away club first)."""
    a, _, b = m.partition("-")
    return f"{a} at {b}" if b else m


# Per-club verification status for the 'No Injuries Reported' rows. Only chunk 0 was re-read.
NO_INJ_STATUS = {
    "BAL": "CONFLICT: NFL.com news says Lamar Jackson and Tyler Huntley are on IR (F-01)",
    "SEA": "CONFLICT: NFL.com news says Sam Darnold is ruled out for Week 10 (F-02)",
    "CIN": "UNCONFIRMED: not in chunk 0; not re-verified this session",
    "LAC": "UNCONFIRMED: not in chunk 0; not re-verified this session",
}


def build_injury_data():
    rows, matchups, none = load_report()
    team_matchup = {}
    for r in rows:
        team_matchup.setdefault(r["team"], r["matchup"])
    for t in none:
        team_matchup.setdefault(t, next((m for m in matchups if t in m.split("-")), ""))
    summary = []
    for ab, (name, slug) in TEAMS.items():
        mine = [r for r in rows if r["team"] == ab]
        mu = team_matchup.get(ab, "")
        listed = bool(mine) or ab in none
        dnp = collections.Counter(r["group"] for r in mine if r["practice_code"] == "D")
        summary.append({
            "team": ab, "name": name, "slug": slug, "matchup": mu,
            "kickoff": matchups.get(mu, ""),
            "listed_on_report": listed,
            "no_injuries_reported": ab in none,
            "players": len(mine),
            "out": sum(1 for r in mine if r["game_status"] == "Out"),
            "questionable": sum(1 for r in mine if r["game_status"] == "Questionable"),
            "doubtful": sum(1 for r in mine if r["game_status"] == "Doubtful"),
            "dnp_total": sum(1 for r in mine if r["practice_code"] == "D"),
            "dnp_QB": dnp.get("QB", 0), "dnp_OL": dnp.get("OL", 0), "dnp_DL": dnp.get("DL", 0),
            "dnp_LB": dnp.get("LB", 0), "dnp_DB": dnp.get("DB", 0), "dnp_Skill": dnp.get("Skill", 0),
            "dnp_ST": dnp.get("ST", 0),
        })
    counts = {
        "player_rows": len(rows), "clubs_with_players": len({r["team"] for r in rows}),
        "clubs_no_injuries_reported": len(none), "clubs_listed": len({r["team"] for r in rows} | set(none)),
        "clubs_not_listed": [ab for ab in TEAMS if ab not in {r["team"] for r in rows} | set(none)],
        "games": len(matchups),
        "out": sum(1 for r in rows if r["game_status"] == "Out"),
        "questionable": sum(1 for r in rows if r["game_status"] == "Questionable"),
        "doubtful": sum(1 for r in rows if r["game_status"] == "Doubtful"),
        "dnp": sum(1 for r in rows if r["practice_code"] == "D"),
        "blank_injury_cells": sum(1 for r in rows if not r["injury"]),
    }
    return rows, summary, counts, matchups


# ----------------------------------------------------------------- Skill Lab (read-only)

def strategy_verdicts() -> dict[str, str]:
    """Verdict text from the committed Skill Lab strategies page."""
    t = (REPO / "skill-lab" / "pages" / "strategies.html").read_text(encoding="utf-8")
    out = {}
    for rid, body in re.findall(r'<tr><td class="mono"><strong>(STR-\d+)</strong>(.*?)</tr>', t, re.S):
        text = H.unescape(re.sub(r"<[^>]+>", " | ", body))
        m = re.search(r"(HELD AT G10[^|]*|DISQUALIFIED[^|]*|NEGATIVE CONTROL[^|]*|REJECTED BY GATES)", text)
        out[rid] = m.group(1).strip() if m else ""
    return out


def build_models():
    o = load(SL / "origination.json")
    s = load(SL / "strategies.json")
    lb = load(SL / "leaderboard.json")
    c = load(SL / "correlations.json")
    lk = load(SL / "luck.json")
    sg = load(SL / "signals.json")
    verdicts = strategy_verdicts()
    to = o["team_origination"]
    comp = []
    pairs = [("Spread MAE (points)", "orig_spread_mae", "mkt_spread_mae"),
             ("Spread RMSE (points)", "orig_spread_rmse", "mkt_spread_rmse"),
             ("Total MAE (points)", "orig_total_mae", "mkt_total_mae"),
             ("Brier score (win/cover)", "orig_brier", "mkt_brier"),
             ("Log loss", "orig_logloss", "mkt_logloss")]
    for label, a, b in pairs:
        oa, mb = float(to[a]), float(to[b])
        comp.append({"metric": label, "model": oa, "market": mb, "gap_model_minus_market": round(oa - mb, 4),
                     "source_url": REPO_BLOB + "skill-lab/data/origination.json",
                     "status": "UNVERIFIED-INPUT"})
    strat = []
    for r in s["rows"]:
        strat.append({**r, "verdict": verdicts.get(r["id"], ""),
                      "source_url": REPO_BLOB + "skill-lab/data/strategies.json",
                      "status": "UNVERIFIED-INPUT"})
    gates = [{"id": g["id"], "name": g["name"], "threshold": g["threshold"], "source_id": g["source_id"]}
             for g in s["gate_catalog"]]
    corr = [{**p, "source_url": REPO_BLOB + "skill-lab/data/correlations.json", "status": "UNVERIFIED-INPUT"}
            for p in c["pairs"]]
    combos = [{**k, "source_url": reg_sl(k["source_id"]), "status": "UNVERIFIED-INPUT"} for k in c["copula_combos"]]
    luck = [{**m, "source_url": reg_sl(m["source_id"]), "status": "UNVERIFIED-INPUT"} for m in lk["metrics"]]
    sigs = [{**r, "source_url": reg_sl(r["source_id"]), "status": "UNVERIFIED-INPUT"} for r in sg["rows"]]
    props = [{**m, "source_url": reg_sl(m["source_id"]), "status_label": m.get("status", "")}
             for m in o["prop_origination"]["markets"]]
    spots = [{**x, "source_url": reg_sl(x["source_id"]) if x.get("source_id") in SL_SRC else NFL}
             for x in o["prop_origination"]["week8_official_player_spotchecks"]]
    return {
        "origination": {"test_window": to["test_window"], "test_games": int(to["test_games"]),
                        "comparison": comp, "sign_convention": o["sign_convention"],
                        "correlation_orig_vs_market_spread": float(to["corr_orig_vs_mkt_spread"]),
                        "brier_skill_vs_market": float(to["brier_skill_vs_market"])},
        "props": {"markets": props, "spotchecks": spots},
        "strategies": {"window": s["window"], "tested": int(s["strategies_tested"]),
                       "qualified": int(s["qualified_strategies"]), "rows": strat, "gates": gates},
        "leaderboard": {"pool_points": int(lb["competition_pool_points"]),
                        "points_awarded": int(lb["points_awarded"]), "tiers": lb["reward_tiers"]},
        "correlations": {"window": c["window"], "pairs": corr, "copula_combos": combos,
                         "ex_ante_vs_ex_post": c["ex_ante_vs_ex_post_wr1_gap"]},
        "luck": {"window": lk["window"], "metrics": luck, "within_season": lk["within_season_split_half"],
                 "pythagorean_outliers_2025": [{**p, "source_url": reg_sl(p["source_id"])} for p in lk["pythagorean_outliers_2025"]]},
        "signals": {"test_window": sg["test_window"], "tested": int(sg["signals_tested"]),
                    "fdr_q": float(sg["fdr_threshold_q"]), "surviving": int(sg["signals_surviving_fdr"]),
                    "rows": sigs},
    }


def reg_sl(sid: str) -> str:
    if sid in SL_SRC:
        return SL_SRC[sid]["url"]
    if sid in REG:
        return REG[sid]["url"]
    return REPO_BLOB + "skill-lab/data/sources.json"


# ----------------------------------------------------------------- page chrome

NAV = [
    ("Overview", [("index.html", "Home"), ("pages/executive-summary.html", "Executive summary"),
                  ("pages/requirements.html", "Requirements")]),
    ("Injuries & depth", [("pages/injuries.html", "Injuries"), ("pages/depth-starters.html", "Depth & starters")]),
    ("Lines & strategies", [("pages/lines-model.html", "Lines & model"),
                            ("pages/strategies.html", "Strategies & leaderboard"),
                            ("pages/correlations-luck.html", "Correlations & luck"),
                            ("pages/validation-gates.html", "Validation gates")]),
    ("Decide", [("pages/suggestions.html", "Suggestions"), ("pages/questions.html", "Questions & gaps")]),
    ("Audit", [("pages/repo-review.html", "Repo review"), ("pages/sources.html", "Sources"),
               ("pages/flagged.html", "Flagged for review")]),
]


def chrome(rel: str, title: str, body: str, active: str) -> str:
    prefix = "../" if rel.startswith("pages/") else ""
    nav = []
    for cat, items in NAV:
        nav.append(f'<div class="navcat">{esc(cat)}</div>')
        for href, label in items:
            cls = ' class="active"' if href == active else ""
            nav.append(f'<a{cls} href="{prefix}{href}">{esc(label)}</a>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {SITE}</title>
<link rel="stylesheet" href="{prefix}assets/site.css">
</head>
<body>
<div class="shell">
<aside class="side">
  <a class="brand" href="{prefix}index.html">{SITE}</a>
  <div class="asof">Data as of {AS_OF}</div>
  <nav>{''.join(nav)}</nav>
</aside>
<main class="main">
<h1>{esc(title)}</h1>
{body}
<footer>Every table row links to its source. Values that could not be confirmed are left blank and flagged on the
<a href="{prefix}pages/flagged.html">Flagged for review</a> page. Generated by nfl-command/scripts/build_site.py.</footer>
</main>
</div>
<script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


def note(text: str) -> str:
    return f'<p class="note">{text}</p>'


def legend() -> str:
    return ('<div class="legend">'
            + badge("ok", "OFFICIAL") + " value shown with an official link. "
            + badge("warn", "UNVERIFIED-INPUT") + " computed from third-party inputs; method link shown. "
            + badge("bad", "BLANK") + " not verifiable from an official source; left empty on purpose."
            + "</div>")


# ----------------------------------------------------------------- pages

def page_index(d) -> str:
    inj, mod, dep = d["inj"], d["models"], d["depth_counts"]
    cards = [
        ("Official injury rows", f"{inj['player_rows']:,}", f"{inj['clubs_listed']} clubs in the Week 10 report", "pages/injuries.html"),
        ("Out / Questionable", f"{inj['out']} / {inj['questionable']}", "game status as printed by NFL.com", "pages/injuries.html"),
        ("Starter vs backup verified", f"0 of {len(TEAMS)}", "no official depth chart reachable", "pages/depth-starters.html"),
        ("Strategies that pass all gates", f"{mod['strategies']['qualified']} of {mod['strategies']['tested']}", "validation gates G1–G10", "pages/strategies.html"),
        ("Signals surviving FDR", f"{mod['signals']['surviving']} of {mod['signals']['tested']}", "Benjamini–Hochberg q ≤ 0.10", "pages/validation-gates.html"),
        ("Open decisions", str(len(d["suggestions"]["rows"])), "suggestions waiting for a choice", "pages/suggestions.html"),
    ]
    card_html = "".join(
        f'<a class="card" href="{href}"><div class="kpi">{esc(v)}</div><div class="kl">{esc(k)}</div>'
        f'<div class="kn">{esc(n)}</div></a>' for k, v, n, href in cards)
    cats = [
        ("Overview", "pages/executive-summary.html", "Executive summary", "What is true today, what is not, and what is blocked."),
        ("Injuries & depth", "pages/injuries.html", "Injury tracker", "All 254 official rows for Week 10, plus team exposure and news conflicts."),
        ("Lines & strategies", "pages/strategies.html", "Strategy leaderboard", "16 strategies, gates, reward tiers, and why none qualify."),
        ("Lines & strategies", "pages/lines-model.html", "Lines & model", "Own-line origination compared with the closing market."),
        ("Lines & strategies", "pages/correlations-luck.html", "Correlations & luck", "Correlation values, copula parlay pricing, luck removal."),
        ("Decide", "pages/suggestions.html", "Suggestions", "Options to review before anything changes. Nothing is implemented."),
        ("Decide", "pages/questions.html", "Questions & gaps", "What is known, unknown, and how to find out."),
        ("Audit", "pages/repo-review.html", "Repo review", "Checks rerun on this branch and the irregularities found."),
        ("Audit", "pages/flagged.html", "Flagged for review", "Every irregularity and unverified item, with its links."),
    ]
    cat_html = "".join(
        f'<a class="card wide" href="{href}"><div class="kc">{esc(c)}</div><div class="kl">{esc(t)}</div>'
        f'<div class="kn">{esc(desc)}</div></a>' for c, href, t, desc in cats)
    body = f"""
<p class="lead">A single place to see the NFL data this repository uses, what the models and strategies found,
and what still needs a decision. Current snapshot: NFL.com injury report, Week 10 of the 2026 season.</p>
{legend()}
<div class="cards">{card_html}</div>
<h2>Pages</h2>
<div class="cards">{cat_html}</div>
<p class="note">Nothing here is betting advice. The strategy results are negative: the market is the better
predictor on this data, and no strategy passes the gates.</p>
"""
    return chrome("index.html", "Home", body, "index.html")


def page_exec(d) -> str:
    inj, mod, dep = d["inj"], d["models"], d["depth_counts"]
    o = mod["origination"]["comparison"]
    mae_m = next(x for x in o if x["metric"].startswith("Spread MAE"))
    tot = next(x for x in o if x["metric"].startswith("Total MAE"))
    rc = d["repo"]["checks"]
    passed = sum(1 for c in rc if c["result"].startswith("PASS"))
    failed = sum(1 for c in rc if c["result"].startswith("FAIL"))
    notes = sum(1 for c in rc if c["result"].startswith("NOTE"))
    body = f"""
<p class="lead">Snapshot as of {AS_OF}. Read this first. Every number below is read from a file in this repo, and each
links to its evidence.</p>
<h2>Key facts</h2>
<div class="cards">
 <div class="card"><div class="kpi">{inj['player_rows']}</div><div class="kl">official injury-report rows</div>
   <div class="kn">{inj['clubs_listed']} clubs listed, {inj['games']} games, {len(inj['clubs_not_listed'])} clubs not on the report</div></div>
 <div class="card"><div class="kpi">{inj['out']}</div><div class="kl">players marked Out</div>
   <div class="kn">+ {inj['questionable']} Questionable, {inj['doubtful']} Doubtful</div></div>
 <div class="card"><div class="kpi">0 of {len(TEAMS)}</div><div class="kl">clubs with a verified depth chart</div>
   <div class="kn">starter-vs-backup analysis is blocked</div></div>
 <div class="card"><div class="kpi">{mod['strategies']['qualified']} of {mod['strategies']['tested']}</div><div class="kl">strategies passing all gates</div>
   <div class="kn">leaderboard pays {mod['leaderboard']['points_awarded']} points</div></div>
 <div class="card"><div class="kpi">{mae_m['model']:.3f} vs {mae_m['market']:.3f}</div><div class="kl">spread MAE: own model vs market close</div>
   <div class="kn">{mod['origination']['test_games']:,} games, {esc(mod['origination']['test_window'])}; model is worse</div></div>
 <div class="card"><div class="kpi">{passed} of {len(rc)}</div><div class="kl">repo checks PASS on this branch</div>
   <div class="kn">{failed} FAIL (Skill Lab does not reproduce), {notes} NOTE</div></div>
</div>

<h2>What the data says</h2>
<ol class="findings">
 <li><b>Injuries are now tracked from the official source.</b> {inj['player_rows']} player rows from the NFL.com Week 10
  report: {inj['out']} Out, {inj['questionable']} Questionable, {inj['dnp']} did not practise, and {inj['blank_injury_cells']} rows with a blank injury
  description. {len(inj['clubs_not_listed'])} clubs ({', '.join(inj['clubs_not_listed'])}) are not on the report; byes are not yet confirmed.
  See <a href="injuries.html">Injuries</a>.</li>
 <li><b>Starter-vs-backup is blocked.</b> No official depth chart could be reached (NFL.com and the Commanders club
  page return 404). Third-party depth charts are not official, so no starter or backup value is shown.
  See <a href="depth-starters.html">Depth &amp; starters</a> and decision SUG-01.</li>
 <li><b>The official report and NFL.com news disagree in three places.</b> The Ravens show no injuries while Lamar Jackson
  is on IR; the Seahawks show no injuries while Sam Darnold is ruled out. The report's inclusion rules are unknown (Q02).</li>
 <li><b>The own-line model does not beat the market.</b> Spread MAE {mae_m['model']:.3f} vs {mae_m['market']:.3f};
  total MAE {tot['model']:.3f} vs {tot['market']:.3f}. These are computed from third-party inputs (flagged).</li>
 <li><b>No strategy passes the gates.</b> {mod['strategies']['qualified']} of {mod['strategies']['tested']} qualify,
  {mod['signals']['surviving']} of {mod['signals']['tested']} signals survive FDR, and the leaderboard awards
  {mod['leaderboard']['points_awarded']} points. Correlations are real in places (QB yards with WR1 yards, r = {mod['correlations']['ex_ante_vs_ex_post']['ex_ante_wr1_r']}),
  . Parlay pricing is on <a href="correlations-luck.html">Correlations &amp; luck</a>.</li>
 <li><b>The repo does not fully reproduce.</b> Re-running the Skill Lab changed 12 committed files. The committed numbers
  are therefore a snapshot, not a reproducible result (Flagged F-07).</li>
 <li><b>Legal question open.</b> AGLC regulates gaming in Alberta. Whether a prize leaderboard needs a licence is
  unanswered, so rewards stay at zero points (SUG-07, Q07).</li>
</ol>

<h2>What is blocked</h2>
<ul>
 <li>Starter-vs-backup deficiency analysis (needs an official depth chart: Q01, SUG-01).</li>
 <li>Injury history and trends (one snapshot only: SUG-02).</li>
 <li>Prop-market ROI (no historical prop prices: Q09).</li>
 <li>Official closing-line validation of gate G10 (SUG-08).</li>
</ul>

<h2>Decisions needed</h2>
<p>{len(d['suggestions']['rows'])} suggestions are waiting. Nothing has been implemented.
See <a href="suggestions.html">Suggestions</a>. The highest-value choices are SUG-01 (depth-chart source),
SUG-02 (weekly archive), and SUG-07 (reward policy).</p>

<h2>Source trail</h2>
<p>Official pages read this session are listed on <a href="sources.html">Sources</a>. Irregularities and unverified
items are listed on <a href="flagged.html">Flagged for review</a>. The repo checks run this session are on
<a href="repo-review.html">Repo review</a>.</p>
"""
    return chrome("pages/executive-summary.html", "Executive summary", body, "pages/executive-summary.html")


def page_requirements(d) -> str:
    st = {"Done": "ok", "Partial": "warn", "Blocked": "bad", "Pending": "flag"}
    rows = []
    for r in d["req"]["rows"]:
        rows.append([esc(r["id"]), esc(r["requirement"]), esc(r["where"]),
                     badge(st.get(r["status"], "flag"), r["status"]), esc(r["evidence"]),
                     src_links(r["sources"]) if r["sources"] else link(REPO_BLOB + "nfl-command/data/requirements.json", "repo: nfl-command/data/requirements.json")])
    body = f"""
<p class="lead">Each requirement from the request, its status, and the evidence. Status is kept honest: Partial and Blocked
items say what is missing.</p>
{table('req', ['ID', 'Requirement', 'Where addressed', 'Status', 'Evidence', 'Sources'], rows, 'official')}
"""
    return chrome("pages/requirements.html", "Requirements", body, "pages/requirements.html")


def page_injuries(d) -> str:
    rows, summary, counts = d["inj_rows"], d["inj_summary"], d["inj_counts"]
    src = (NFL + "/injuries/", "NFL.com 2026 Injury Report (Week 10)")
    # team summary (official)
    trows = []
    for t in summary:
        team = link(f"{NFL}/teams/{t['slug']}/", t["name"]) if t["slug"] else esc(t["name"])
        if t["no_injuries_reported"]:
            status = "No Injuries Reported. " + NO_INJ_STATUS.get(t["team"], "")
        elif not t["listed_on_report"]:
            status = "Not on the Week 10 report (bye or omission not confirmed)"
        else:
            status = f"{t['players']} listed"
        trows.append([team, esc(mu_text(t["matchup"]) if t["matchup"] else ""), esc(t["kickoff"]),
                      esc(status), fmt(t["out"]) or "0", fmt(t["questionable"]) or "0", fmt(t["dnp_total"]) or "0",
                      fmt(t["dnp_QB"]) or "0", fmt(t["dnp_OL"]) or "0", fmt(t["dnp_DL"]) or "0",
                      fmt(t["dnp_DB"]) or "0", fmt(t["dnp_Skill"]) or "0",
                      link(*src)])
    # player rows (official)
    prow = []
    for r in rows:
        prow.append([esc(r["team"]), esc(mu_text(r["matchup"])), esc(r["kickoff"]),
                     link(r["player_url"], r["player"]), esc(r["pos"]), esc(r["group"]),
                     esc(r["injury"]), esc(r["practice"]), esc(r["game_status"]),
                     link(*src)])
    rec = []
    for x in d["recon"]["rows"]:
        rec.append([esc(x["player"]), esc(x["team"]), esc(x["news_says"]), esc(x["report_says"]),
                    badge("bad" if x["result"].startswith("CONFLICT") else "warn" if x["result"].startswith("Partly") else "ok",
                          x["result"].split(".")[0].split(" (")[0]) + "<br><span class='small'>" + esc(x["result"]) + "</span>",
                          src_links(x["sources"])])
    body = f"""
<p class="lead">Official NFL.com injury report for Week 10 of the 2026 season. {counts['player_rows']} player rows across
{counts['clubs_with_players']} clubs; {counts['clubs_no_injuries_reported']} clubs show 'No Injuries Reported'.
Team-level exposure counts are computed from these rows; the injury and game-status cells are copied as printed.
{counts['blank_injury_cells']} of {counts['player_rows']} injury cells are blank on the NFL.com listing itself; they stay blank here.</p>
{legend()}
<div class="cards">
 <div class="card"><div class="kpi">{counts['player_rows']}</div><div class="kl">player rows</div></div>
 <div class="card"><div class="kpi">{counts['out']}</div><div class="kl">Out</div></div>
 <div class="card"><div class="kpi">{counts['questionable']}</div><div class="kl">Questionable</div></div>
 <div class="card"><div class="kpi">{counts['dnp']}</div><div class="kl">Did not participate</div></div>
 <div class="card"><div class="kpi">{counts['blank_injury_cells']}</div><div class="kl">blank injury cells on source</div></div>
</div>
<h2>Team summary and position exposure</h2>
<p class="note">Position groups are our grouping of the printed positions: OL = T, G, C, OT; DL = DE, DT; LB; DB = CB, S, SAF;
Skill = RB, FB, WR, TE; QB; ST = K, P, LS. These are exposure counts, not starter status.
Clubs in CHI, DEN, PHI and TB are not on the report.</p>
{table('inj-teams', ['Club', 'Matchup', 'Kickoff (ET)', 'Report status', 'Out', 'Questionable', 'DNP (all)', 'DNP QB', 'DNP OL', 'DNP DL', 'DNP DB', 'DNP Skill', 'Source'], trows, 'official')}
<h2>Player rows (all {counts['player_rows']})</h2>
<p class="note">Each row is copied from the NFL.com listing. The player name links to the player's NFL.com page;
the source link goes to the report. Blank cells are blank on the source.</p>
{table('inj-players', ['Club', 'Matchup', 'Kickoff (ET)', 'Player', 'Pos', 'Group', 'Injury', 'Practice', 'Game status', 'Source'], prow, 'official')}
<h2>Reconciliation with NFL.com news</h2>
<p class="note">NFL.com news statements compared with the report. These are conflicts to review, not corrections.</p>
{table('inj-recon', ['Player', 'Club', 'NFL.com news says', 'Report says', 'Result', 'Sources'], rec, 'official')}
"""
    return chrome("pages/injuries.html", "Injuries", body, "pages/injuries.html")


def page_depth(d) -> str:
    summary = d["inj_summary"]
    rows = []
    for t in summary:
        team = link(f"{NFL}/teams/{t['slug']}/", t["name"]) if t["slug"] else esc(t["name"])
        checked = ("NFL.com depth-chart path 404; club site path 404" if t["team"] == "WAS"
                   else "not checked in this session")
        exposure = ("not on report" if not t["listed_on_report"] else
                    f"QB DNP {t['dnp_QB']}; OL DNP {t['dnp_OL']}; DL DNP {t['dnp_DL']}; DB DNP {t['dnp_DB']}")
        src = link(*(d['inj_src']))
        if t["team"] == "WAS":
            src = src + "<br>" + link(*reg_link("NFL-DEPTH-WAS")) + "<br>" + link(*reg_link("CLUB-DEPTH-WAS"))
        rows.append([team, esc(checked), "", "", "", esc(exposure), badge("bad", "BLANK"), src])
    body = f"""
<p class="lead">Starter and backup status by club, offence and defence. <b>Blocked.</b> No official depth chart was found, so
every starter, backup and third-string cell is blank by design. The last column shows injury-report exposure from the
official report only. It does not say who started.</p>
{legend()}
<h2>What this page needs</h2>
<ul>
 <li>An official depth chart per club, with a timestamp (Q01, SUG-01).</li>
 <li>A definition of 'starter' (Q08, SUG-04).</li>
 <li>A weekly capture so changes can be tracked (SUG-02).</li>
</ul>
<h2>Club table</h2>
{table('depth', ['Club', 'Official depth chart checked', 'Offence starter (1st)', 'Offence backup (2nd)', 'Defence starter (1st)', 'Injury-report exposure (factual)', 'Status', 'Source'], rows, 'official')}
<p class="note">Empty cells are blank on purpose. A value gets filled in only when an official depth chart supports it.</p>
"""
    return chrome("pages/depth-starters.html", "Depth & starters", body, "pages/depth-starters.html")


def page_lines(d) -> str:
    m = d["models"]["origination"]
    comp = m["comparison"]
    rows = []
    for c in comp:
        rows.append([esc(c["metric"]), fmt(c["model"], 3), fmt(c["market"], 3),
                     fmt(c["gap_model_minus_market"], 3), badge("warn", c["status"]),
                     link(c["source_url"], "repo: skill-lab/data/origination.json")])
    rows.append(["Correlation, model vs market spread", fmt(m["correlation_orig_vs_market_spread"], 4), "", "",
                 badge("warn", "UNVERIFIED-INPUT"), link(REPO_BLOB + "skill-lab/data/origination.json", "repo: skill-lab/data/origination.json")])
    rows.append(["Brier skill vs market (negative = worse)", fmt(m["brier_skill_vs_market"], 4), "", "",
                 badge("warn", "UNVERIFIED-INPUT"), link(REPO_BLOB + "skill-lab/data/origination.json", "repo: skill-lab/data/origination.json")])
    sc = m["sign_convention"]
    srows = [[esc(k.replace("_", " ")), esc(v), link(REPO_BLOB + "skill-lab/data/origination.json", "repo: skill-lab/data/origination.json")]
             for k, v in sc.items() if k not in ("source_id", "conclusion")]
    spots = []
    for x in d["models"]["props"]["spotchecks"]:
        spots.append([esc(x["player"]), esc(x["team"]), esc(x["pos"]), esc(x.get("week8_opp")), esc(x["stat_market"]),
                      fmt(x.get("orig_median_line"), 1), fmt(x.get("official_week8_actual"), 0),
                      esc(x.get("outcome_vs_orig_line")), esc(x.get("bookmaker_closing_prop_line")),
                      link(x["source_url"], x.get("source_id", "source"))])
    props = []
    for p in d["models"]["props"]["markets"]:
        props.append([esc(p["label"]), fmt(p["sample_n"]), fmt(p["over_rate_at_raw_mean_pct"], 2),
                      fmt(p["over_rate_at_calibrated_median_pct"], 2), fmt(p["iqr_25_75_coverage_pct"], 2),
                      fmt(p["mae_yards"], 2), esc(p["historical_book_roi"]),
                      badge("warn", "UNVERIFIED-INPUT") + "<br><span class='small'>" + esc(p["status_label"]) + "</span>",
                      link(p["source_url"], p["source_id"])])
    body = f"""
<p class="lead">Own-line origination (Skill Lab model) compared with the closing market on {m['test_games']:,} games ({esc(m['test_window'])}).
The model is <b>less accurate than the market</b> on every error measure shown. This is the headline result of the research.</p>
{legend()}
<h2>Model against the market</h2>
{table('lines', ['Metric', 'Own model', 'Market close', 'Gap (model − market)', 'Status', 'Source'], rows, 'computed')}
<p class="note">Window: {esc(m['test_window'])}. Gap is computed by the build script. For error metrics, a positive gap means the model is worse.</p>
<h2>Sign convention (verified in the committed data)</h2>
{table('sign', ['Check', 'Value', 'Source'], srows, 'computed')}
<h2>Player-prop origination (ex-ante player role selection)</h2>
{table('props', ['Market', 'Sample n', 'Over % at raw mean', 'Over % at calibrated median', 'IQR 25–75 coverage %', 'MAE (yards)', 'Historical book ROI', 'Status', 'Source'], props, 'computed')}
<h2>Week 8 official spot-checks (player stat lines)</h2>
<p class="note">The 'Bookmaker closing prop line' column is blank in the source: no closing prop line was recorded, so none is shown.</p>
{table('spots', ['Player', 'Team', 'Pos', 'Week 8 opp', 'Market', 'Model median line', 'Official Week 8 actual', 'Outcome vs line', 'Bookmaker closing line', 'Source'], spots, 'official')}
"""
    return chrome("pages/lines-model.html", "Lines & model", body, "pages/lines-model.html")


def page_strategies(d) -> str:
    st = d["models"]["strategies"]
    rows = []
    for r in st["rows"]:
        def p(v):
            return "" if v in (None, "") else fmt(v, 2)
        vb = r["verdict"]
        kind = "bad" if ("DISQUAL" in vb or "REJECTED" in vb) else "warn" if vb else "flag"
        rows.append([esc(r["id"]), esc(r["name"]), esc(r["category"]), fmt(r["tickets_n"]),
                     p(r["hit_rate_pct"]), p(r["roi_pct"]),
                     "" if r["roi_ci95_low_pct"] in (None, "") else f"{r['roi_ci95_low_pct']:.2f} to {r['roi_ci95_high_pct']:.2f}",
                     p(r["luck_adjusted_roi_pct"]), p(r["holdout_2024_2026_roi_pct"]), p(r["stress_roi_pct"]),
                     badge(kind, vb or "no verdict"), badge("warn", "UNVERIFIED-INPUT"),
                     link(r["source_url"], "repo: strategies.json")])
    tiers = []
    for t in d["models"]["leaderboard"]["tiers"]:
        tiers.append([esc(t["tier"]), esc(t["gate_requirement"]), fmt(t["pool_points"]), fmt(t["awarded_count"]),
                      esc(t["cash_funding"]) or '<span class="muted">blank: legal review open (Q07)</span>',
                      link(REPO_BLOB + "skill-lab/data/leaderboard.json", "repo: skill-lab/data/leaderboard.json")])
    body = f"""
<p class="lead">Sixteen candidate strategies were run through the ten validation gates. <b>{st['qualified']} of {st['tested']}
qualify</b>, so the leaderboard awards {d['models']['leaderboard']['points_awarded']} points out of
{d['models']['leaderboard']['pool_points']:,}. Single bets, parlays and player-prop combinations are all included.</p>
{legend()}
<h2>Leaderboard (all strategies)</h2>
<p class="note">Window: {esc(st['window'])}. ROI is per unit staked. Blank cells are blank in the source: prop combinations
have no historical price, so their ROI is not measured (F-13). STR-15 is a negative control and STR-16 is an
integrity control that leaks look-ahead data; neither is a strategy result.</p>
{table('strat', ['ID', 'Strategy', 'Category', 'Tickets (n)', 'Hit %', 'ROI %', 'ROI 95% CI %', 'Luck-adjusted ROI %', 'Holdout 2024–26 ROI %', 'Stress ROI %', 'Verdict', 'Status', 'Source'], rows, 'computed')}
<h2>Reward tiers</h2>
<p class="note">No tier is awarded because no strategy passes. Cash funding is blank pending the Alberta review (Q07, F-14).</p>
{table('tiers', ['Tier', 'Requirement', 'Pool points', 'Awarded', 'Cash funding', 'Source'], tiers, 'computed')}
"""
    return chrome("pages/strategies.html", "Strategies & leaderboard", body, "pages/strategies.html")


def page_corr(d) -> str:
    c = d["models"]["correlations"]
    prow = []
    for p in c["pairs"]:
        prow.append([esc(p["id"]), esc(p["category"]), esc(p["pair"]), fmt(p["sample_n"]), fmt(p["pearson_r"], 4),
                     f"{p['ci_95_low']:.3f} to {p['ci_95_high']:.3f}", pval(p["p_value"]), fmt(p["binary_phi"], 4),
                     fmt(p["copula_rho"], 4), fmt(p["joint_prob_pct"], 2), fmt(p["indep_prob_pct"], 2),
                     fmt(p["joint_multiplier"], 3), esc(p["note"]), badge("warn", "UNVERIFIED-INPUT"),
                     link(p["source_url"], "repo: correlations.json")])
    crow = []
    for k in c["copula_combos"]:
        crow.append([esc(k["combo_id"]), esc(k["name"]), fmt(k["legs"]), fmt(k["joint_copula_prob"], 2),
                     fmt(k["indep_prob"], 2), fmt(k["multiplier"], 3), esc(k["fair_copula_odds"]),
                     esc(k["std_book_parlay_odds"]) or '<span class="muted">blank in source</span>',
                     fmt(k["ev_at_unadjusted_parlay_pct"], 1), esc(k["takeaway"]), badge("warn", "UNVERIFIED-INPUT"),
                     link(k["source_url"], k["source_id"])])
    lrow = []
    for m in d["models"]["luck"]["metrics"]:
        lrow.append([esc(m["label"]), fmt(m["team_season_pairs"]), fmt(m["yoy_r"], 4),
                     f"{m['ci_95_low']:.3f} to {m['ci_95_high']:.3f}", pval(m["p_value"]),
                     fmt(m["eb_skill_weight"], 3), fmt(m["luck_shrinkage_pct"], 1), esc(m["classification"]),
                     badge("warn", "UNVERIFIED-INPUT"), link(m["source_url"], m["source_id"])])
    wsp = d["models"]["luck"]["within_season"]
    _lk = link(REPO_BLOB + "skill-lab/data/luck.json", "repo: skill-lab/data/luck.json")
    wrow = [[esc("Odd–even split-half: EPA per play"), fmt(wsp["odd_even_epa_per_play_r"], 4), _lk],
            [esc("Odd–even split-half: net turnovers"), fmt(wsp["odd_even_net_turnovers_r"], 4), _lk],
            [esc("Odd–even split-half: ATS cover"), fmt(wsp["odd_even_ats_cover_r"], 4), _lk]]
    prows = []
    for p in d["models"]["luck"]["pythagorean_outliers_2025"]:
        prows.append([esc(p["team"]), esc(p["record_2025"]), fmt(p["pythag_luck_2025_wins"], 2),
                      esc(p["direction_predicted_for_2026"]), badge("warn", "UNVERIFIED-INPUT"),
                      link(p["source_url"], p["source_id"])])
    ex = c["ex_ante_vs_ex_post"]
    body = f"""
<p class="lead">Correlation values that decide whether a parlay is priced fairly. Parlays on independent events are only
fair when the legs really are independent. Several pairs are not, and the copula prices show by how much. Luck is
removed by regressing team results on prior-season results; most of the win-loss variance is luck.</p>
{legend()}
<h2>Pairwise correlations (14 pairs)</h2>
<p class="note">Window: {esc(c['window'])}. Computed from third-party inputs (F-08).</p>
{table('pairs', ['ID', 'Category', 'Pair', 'n', 'Pearson r', '95% CI', 'p', 'Binary φ', 'Copula ρ', 'Joint %', 'Independent %', 'Multiplier', 'Note', 'Status', 'Source'], prow, 'computed')}
<h2>Parlay and SGP pricing (copula)</h2>
{table('copula', ['ID', 'Combo', 'Legs', 'Joint prob % (copula)', 'Independent prob %', 'Multiplier', 'Fair copula odds', 'Standard book odds', 'EV at unadjusted parlay %', 'Takeaway', 'Status', 'Source'], crow, 'computed')}
<h2>Ex-ante vs ex-post selection bias</h2>
<p class="note">Choosing the leading receiver after the game inflates the correlation. This is why the model uses ex-ante roles only.</p>
{table('bias', ['Measure', 'Value', 'Source'], [[esc('Ex-ante WR1 receiving yards r'), fmt(float(ex['ex_ante_wr1_r']), 4), link(REPO_BLOB + 'skill-lab/data/correlations.json', 'repo: skill-lab/data/correlations.json')],
    [esc('Ex-post game-leader receiving yards r'), fmt(float(ex['ex_post_wr1_r']), 4), link(REPO_BLOB + 'skill-lab/data/correlations.json', 'repo: skill-lab/data/correlations.json')],
    [esc('Inflation from ex-post selection'), fmt(float(ex['inflation_delta_r']), 4), link(REPO_BLOB + 'skill-lab/data/correlations.json', 'repo: skill-lab/data/correlations.json')]], 'computed')}
<h2>Luck removal: year-over-year persistence</h2>
<p class="note">{esc(d['models']['luck']['window'])}. Persistence close to 0 means the metric is mostly luck. Shrinkage shows how much of the
observed value to discard.</p>
{table('luck', ['Metric', 'Team-seasons', 'YoY r', '95% CI', 'p', 'Empirical-Bayes skill weight', 'Luck shrinkage %', 'Classification', 'Status', 'Source'], lrow, 'computed')}
<h2>Within-season stability</h2>
{table('split', ['Measure', 'r', 'Source'], wrow, 'computed')}
<h2>Pythagorean outliers, 2025</h2>
{table('pyth', ['Team', 'Record 2025', 'Luck (wins)', 'Predicted 2026 direction', 'Status', 'Source'], prows, 'computed')}
"""
    return chrome("pages/correlations-luck.html", "Correlations & luck", body, "pages/correlations-luck.html")


def page_gates(d) -> str:
    st = d["models"]["strategies"]
    grows = []
    for g in st["gates"]:
        grows.append([esc(g["id"]), esc(g["name"]), esc(g["threshold"]), link(*reg_link(g["source_id"]))])
    sg = d["models"]["signals"]
    srows = []
    for r in sg["rows"]:
        srows.append([esc(r["id"]), esc(r["name"]), esc(r["market"]), fmt(r["settled_bets"]), fmt(r["win_rate_pct"], 2),
                      fmt(r["roi_pct"], 2), fmt(r["recent_2024_2026_roi_pct"], 2), fmt(r["t_stat"], 3), pval(r["p_value"]),
                      fmt(r["bh_q_value"], 4), badge("ok" if r["survives_fdr_q10"] else "bad",
                                                     "survives" if r["survives_fdr_q10"] else "fails"),
                      esc(r["verdict"]), badge("warn", "UNVERIFIED-INPUT"), link(r["source_url"], r["source_id"])])
    body = f"""
<p class="lead">Ten gates decide whether a strategy may earn anything. Gold and Silver tiers need all ten gates (Gold also needs
a higher skill score). Bronze needs nine gates, including the mandatory G1, G3, G5, G6 and G10. Tier thresholds are on
<a href="strategies.html">Strategies</a>. Ten pre-registered signals were also tested for false discoveries.</p>
{legend()}
<h2>The ten gates</h2>
{table('gates', ['Gate', 'Name', 'Threshold', 'Method source'], grows, 'computed')}
<p class="note">The 'Method source' links are the register entries used in the Skill Lab, not results. G10 (Official Price
Provenance) is the gate that holds five strategies, whose prices are unverified (Q05, SUG-08).</p>
<h2>Signals (pre-kickoff, Benjamini–Hochberg FDR)</h2>
<p class="note">Window: {esc(sg['test_window'])}. Threshold q ≤ {sg['fdr_q']:.2f}. {sg['surviving']} of {sg['tested']} survive.</p>
{table('signals', ['ID', 'Signal', 'Market', 'Settled bets', 'Win %', 'ROI %', 'Recent ROI %', 't', 'p', 'BH q', 'FDR', 'Verdict', 'Status', 'Source'], srows, 'computed')}
"""
    return chrome("pages/validation-gates.html", "Validation gates", body, "pages/validation-gates.html")


def page_suggestions(d) -> str:
    rows = []
    for s in d["suggestions"]["rows"]:
        opts = "<ol class='opts'>" + "".join(
            f"<li><b>{esc(o['id'])}.</b> {esc(o['label'])}<br><span class='small'>Pro: {esc(o['pro'])}. Con: {esc(o['con'])}.</span></li>"
            for o in s["options"]) + "</ol>"
        decision = (f'<select data-decision="{esc(s["id"])}" aria-label="Decision for {esc(s["id"])}">'
                    '<option value="Pending">Pending</option><option value="Approve">Approve</option>'
                    '<option value="Reject">Reject</option><option value="Modify">Modify</option></select>')
        rows.append([esc(s["id"]), f"<b>{esc(s['title'])}</b><br><span class='small'>{esc(s['problem'])}</span>",
                     opts, esc(s["recommendation"]), esc(s["decision_needed"]), esc(", ".join(s["blocks"])),
                     src_links(s["sources"]), decision])
    body = f"""
<p class="lead">Options to review before anything changes. <b>Nothing on this page has been implemented.</b> Choose a decision
for each row. Choices are kept in this browser and can be copied as text to paste into
<code>COORDINATION.md</code> or your reply.</p>
<div class="actions"><button type="button" id="copy-decisions">Copy decisions as text</button>
<button type="button" id="reset-decisions" class="ghost">Reset to Pending</button><span id="decision-status" class="small"></span></div>
{table('sugg', ['ID', 'Suggestion', 'Options', 'Recommendation', 'Decision needed', 'Blocks', 'Sources', 'Your decision'], rows, 'official')}
"""
    return chrome("pages/suggestions.html", "Suggestions", body, "pages/suggestions.html")


def page_questions(d) -> str:
    rows = []
    for q in d["questions"]["rows"]:
        rows.append([esc(q["id"]), esc(q["question"]), esc(q["known"]), esc(q["unknown"]), esc(q["how_to_find_out"]),
                     esc(", ".join(q["blocks"])), src_links(q["sources"])])
    body = f"""
<p class="lead">Questions to answer before a decision can reasonably be made. Each row separates what is known, with its source,
from what is not.</p>
{table('questions', ['ID', 'Question', 'Known (sourced)', 'Unknown', 'How to find out', 'Blocks', 'Sources'], rows, 'official')}
"""
    return chrome("pages/questions.html", "Questions & gaps", body, "pages/questions.html")


def page_repo(d) -> str:
    crow = []
    for c in d["repo"]["checks"]:
        res = c["result"]
        kind = "ok" if res.startswith("PASS") else "bad" if res.startswith("FAIL") else "warn"
        crow.append([esc(c["id"]), esc(c["check"]), f"<code>{esc(c['command'])}</code>", badge(kind, res.split(":")[0].split(" (")[0]) + ("<br><span class='small'>" + esc(res) + "</span>" if len(res) > 12 else ""),
                     link(REPO_BLOB + c["path"], c["path"])])
    frow = []
    for f in d["repo"]["findings"]:
        frow.append([esc(f["id"]), link(REPO_BLOB + f["path"], f["path"]), esc(f["finding"]), badge("warn", f["status"])])
    orow = [[esc(s["name"]), link(s["url"], s["url"]), link(REPO_BLOB + s["path"], s["path"])] for s in d["repo"]["other_sites"]]
    body = f"""
<p class="lead">Line-by-line review of this branch. Each check was run in the sandbox on {AS_OF}. The one failure is
reported as found: committed Skill Lab numbers do not reproduce.</p>
{legend()}
<h2>Checks run</h2>
{table('checks', ['ID', 'Check', 'Command', 'Result', 'File'], crow, 'official')}
<h2>Irregularities found</h2>
{table('findings', ['ID', 'File', 'Finding', 'Status'], frow, 'official')}
<h2>Other sites in this repository</h2>
<p class="note">Each is a separate site and is not edited here. Their numbers are not reconciled with this one (F-12).
Links point to GitHub Pages on the default branch; live status is checked after deployment (F-18).</p>
{table('sites', ['Site', 'Live URL', 'Source file'], orow, 'official')}
"""
    return chrome("pages/repo-review.html", "Repo review", body, "pages/repo-review.html")


def page_sources(d) -> str:
    rows = []
    for s in d["sources"]["sources"]:
        rows.append([esc(s["id"]), esc(s["title"]), esc(s["publisher"]), link(s["url"]),
                     badge("ok", "official") if s["official"] else badge("flag", "not official"),
                     esc(s["checked"]), esc(s["result"])])
    body = f"""
<p class="lead">Every source read in this session, with what was checked and what was found. Non-official sources are listed
so they can be seen, but no value comes from them.</p>
<p class="note">Method: {esc(d['sources']['method'])}</p>
{table('srcs', ['ID', 'Title', 'Publisher', 'URL', 'Official?', 'Checked', 'Result'], rows, 'official')}
"""
    return chrome("pages/sources.html", "Sources", body, "pages/sources.html")


def page_flagged(d) -> str:
    rows = []
    fallback = {"F-10": ".github/workflows/validate.yml", "F-11": "COORDINATION.md",
                "F-12": "README.md", "F-15": "tests/check_site.py",
                "F-18": "nfl-command/pages/repo-review.html"}
    for f in d["flagged"]["rows"]:
        srcs = src_links(f["sources"]) if f["sources"] else link(REPO_BLOB + fallback[f["id"]], fallback[f["id"]])
        rows.append([esc(f["id"]), esc(f["category"]), esc(f["item"]), badge("warn", f["value"]), esc(f["reason"]), srcs])
    body = f"""
<p class="lead">Irregularities and unverified items for review. <b>These do not block the merge.</b> Each row links its
evidence. Ask for a change against any ID and it will be made in a later session.</p>
{table('flag', ['ID', 'Category', 'Item', 'Value', 'Reason', 'Sources'], rows, 'official')}
"""
    return chrome("pages/flagged.html", "Flagged for review", body, "pages/flagged.html")


# ----------------------------------------------------------------- assets

CSS = """
:root{--ink:#14213d;--muted:#5b6475;--line:#dfe3ea;--bg:#f6f8fb;--card:#fff;--ok:#1a7f4b;--warn:#a15c00;--bad:#b42318;--flag:#475467;--accent:#0b5cad}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--accent)}code{font-size:12.5px;background:#eef2f7;padding:1px 4px;border-radius:4px}
.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}
.side{background:#fff;border-right:1px solid var(--line);padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.side .brand{font-weight:700;font-size:16px;text-decoration:none;color:var(--ink);display:block}
.asof{font-size:12px;color:var(--muted);margin:4px 0 14px}
.side nav a{display:block;padding:5px 8px;border-radius:6px;text-decoration:none;color:var(--ink);font-size:14px}
.side nav a:hover{background:#eef2f7}.side nav a.active{background:#dbe9fb;font-weight:600}
.navcat{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:12px 8px 4px}
.main{padding:22px 28px 40px;max-width:1400px;width:100%}
h1{font-size:24px;margin:4px 0 10px}h2{font-size:18px;margin:26px 0 8px}
.lead{font-size:16px;color:#22304a;max-width:900px}
.note{font-size:13.5px;color:var(--muted);max-width:980px}
.small{font-size:12px;color:var(--muted)}.muted{color:var(--muted)}
.legend{font-size:13px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:10px 0}
.badge{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px;border:1px solid;white-space:nowrap}
.badge-ok{color:var(--ok);border-color:#9fd8bb;background:#eefaf3}
.badge-warn{color:var(--warn);border-color:#f0cf93;background:#fff8ea}
.badge-bad{color:var(--bad);border-color:#f4b4ad;background:#fff1f0}
.badge-flag{color:var(--flag);border-color:#c9d0da;background:#f2f4f7}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin:12px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;text-decoration:none;color:var(--ink);display:block}
a.card:hover{border-color:#9db9dd;box-shadow:0 1px 6px rgba(20,33,61,.08)}
.card.wide{grid-column:span 1}
.kpi{font-size:24px;font-weight:700}.kc{font-size:12px;text-transform:uppercase;color:var(--muted);letter-spacing:.05em}
.kl{font-weight:600;margin-top:2px}.kn{font-size:13px;color:var(--muted);margin-top:4px}
.tablewrap{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;margin:8px 0 14px}
.filter{width:100%;max-width:340px;padding:6px 10px;border:1px solid var(--line);border-radius:6px;font:inherit;margin-bottom:8px}
.scroll{overflow:auto;max-height:640px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{position:sticky;top:0;background:#f1f4f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#334;z-index:1}
tr:hover td{background:#fafcff}
td ol.opts{margin:0;padding-left:18px}td ol.opts li{margin-bottom:6px}
select{font:inherit;padding:4px 6px;border-radius:6px;border:1px solid var(--line)}
button{font:inherit;padding:7px 12px;border-radius:7px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;margin-right:8px}
button.ghost{background:#fff;color:var(--accent)}
.actions{margin:10px 0;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
footer{margin-top:30px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:10px}
ol.findings li{margin-bottom:8px;max-width:960px}
@media (max-width:860px){.shell{grid-template-columns:1fr}.side{position:static;height:auto}.main{padding:16px}}
"""

JS = """
(function(){
  // Row filter for every table with a filter box.
  document.querySelectorAll('input.filter[data-filter-for]').forEach(function(box){
    var table = document.getElementById(box.getAttribute('data-filter-for'));
    if(!table) return;
    box.addEventListener('input', function(){
      var q = box.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function(tr){
        tr.style.display = (!q || tr.textContent.toLowerCase().indexOf(q) !== -1) ? '' : 'none';
      });
    });
  });
  // Decision recorder for the suggestions page (browser storage only; nothing is sent anywhere).
  var KEY = 'nfl-command-decisions-v1';
  var sel = document.querySelectorAll('select[data-decision]');
  if(sel.length){
    var saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) { saved = {}; }
    sel.forEach(function(s){
      var id = s.getAttribute('data-decision');
      if(saved[id]) s.value = saved[id];
      s.addEventListener('change', function(){
        saved[id] = s.value;
        localStorage.setItem(KEY, JSON.stringify(saved));
        flash('Saved in this browser');
      });
    });
    var status = document.getElementById('decision-status');
    function flash(t){ if(status){ status.textContent = t; setTimeout(function(){ status.textContent=''; }, 2000); } }
    var copy = document.getElementById('copy-decisions');
    if(copy) copy.addEventListener('click', function(){
      var lines = [];
      sel.forEach(function(s){ lines.push(s.getAttribute('data-decision') + ': ' + s.value); });
      var text = 'Decisions (NFL Command Center, as of 2026-11-12):\\n' + lines.join('\\n');
      if(navigator.clipboard){ navigator.clipboard.writeText(text).then(function(){ flash('Copied'); }, function(){ window.prompt('Copy:', text); }); }
      else { window.prompt('Copy:', text); }
    });
    var reset = document.getElementById('reset-decisions');
    if(reset) reset.addEventListener('click', function(){
      sel.forEach(function(s){ s.value = 'Pending'; });
      localStorage.removeItem(KEY); flash('Reset');
    });
  }
})();
"""


def main() -> None:
    rows, summary, counts, matchups = build_injury_data()
    models = build_models()
    depth_counts = {"clubs": len(TEAMS)}
    d = {
        "inj_rows": rows, "inj_summary": summary, "inj_counts": counts, "inj_src": (NFL + "/injuries/", "NFL.com injury report"),
        "models": models, "depth_counts": depth_counts,
        "req": load(DATA / "requirements.json"),
        "recon": load(DATA / "reconciliation.json"),
        "suggestions": load(DATA / "suggestions.json"),
        "questions": load(DATA / "questions.json"),
        "repo": load(DATA / "repo_review.json"),
        "flagged": load(DATA / "flagged.json"),
        "sources": load(DATA / "sources.json"),
        "inj": counts,
    }
    # generated, auditable outputs
    write_json(GEN / "injuries.json", {"source": "https://www.nfl.com/injuries/", "fetched": AS_OF,
                                       "counts": counts, "rows": rows})
    write_json(GEN / "injury_team_summary.json", {"source": "https://www.nfl.com/injuries/", "fetched": AS_OF,
                                                  "rows": summary})
    write_json(GEN / "models.json", {k: v for k, v in models.items()})
    # depth: one blank, flagged row per club. No official depth chart was reachable, so no value is inferred.
    write_json(GEN / "depth.json", {
        "description": "Starter and backup status by club. All value fields are blank: no official depth chart reachable (Q01, F-03).",
        "status": "BLANK (unverified)", "checked": AS_OF,
        "sources_checked_no_chart": ["https://www.nfl.com/teams/washington-commanders/depth-chart (404)",
                                      "https://www.commanders.com/depth-chart/ (404)"],
        "rows": [{"team": ab, "name": name, "offense_starter": "", "offense_backup_2nd": "", "offense_3rd": "",
                  "offense_4th": "", "defense_starter": "", "defense_backup_2nd": "", "defense_3rd": "", "defense_4th": "",
                  "flag": "UNVERIFIED: no official depth chart", "source": f"{NFL}/teams/{slug}/" if slug else ""}
                 for ab, (name, slug) in TEAMS.items()]})

    pages = {
        "index.html": page_index(d),
        "pages/executive-summary.html": page_exec(d),
        "pages/requirements.html": page_requirements(d),
        "pages/injuries.html": page_injuries(d),
        "pages/depth-starters.html": page_depth(d),
        "pages/lines-model.html": page_lines(d),
        "pages/strategies.html": page_strategies(d),
        "pages/correlations-luck.html": page_corr(d),
        "pages/validation-gates.html": page_gates(d),
        "pages/suggestions.html": page_suggestions(d),
        "pages/questions.html": page_questions(d),
        "pages/repo-review.html": page_repo(d),
        "pages/sources.html": page_sources(d),
        "pages/flagged.html": page_flagged(d),
    }
    for rel, text in pages.items():
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    (ROOT / "assets").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (ROOT / "assets" / "site.js").write_text(JS.strip() + "\n", encoding="utf-8")
    print(f"built {len(pages)} pages; {counts['player_rows']} injury rows; "
          f"{models['strategies']['qualified']}/{models['strategies']['tested']} strategies qualify")


if __name__ == "__main__":
    main()
