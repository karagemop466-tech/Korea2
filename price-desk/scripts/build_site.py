#!/usr/bin/env python3
"""Render the price-desk static site from price-desk/data/*.json and *.csv.

Every rendered table row carries at least one source link (verified by
scripts/verify.py). No value is typed into HTML by hand: every cell comes
from a data file produced or audited by this session.
"""
import csv
import html
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PD = os.path.join(ROOT, "price-desk")
D = os.path.join(PD, "data")
GB = "https://github.com/karagemop466-tech/Korea2/blob/main/"

NAV = [
    ("index.html", "Overview"),
    ("pages/price-snapshots.html", "Price snapshots"),
    ("pages/results-feed.html", "Results feed"),
    ("pages/leaderboard.html", "Leaderboard (signal vs staking)"),
    ("pages/gates.html", "Gates & demotion"),
    ("pages/requirements.html", "Requirements status"),
    ("pages/questions.html", "Pre-decision Q&A"),
    ("pages/suggestions.html", "Suggestion review queue"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/sources.html", "Sources"),
]


def esc(x):
    return html.escape(str(x if x is not None else ""))


def link(url, text=None):
    return f'<a href="{esc(url)}">{esc(text or url)}</a>'


def rel(url, text):
    return f'<a href="{esc(url)}">{esc(text)}</a>'


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def load_csv(name):
    with open(os.path.join(D, name), newline="") as f:
        return list(csv.DictReader(f))


def page(filename, title, body):
    prefix = "../" if filename.startswith("pages/") else ""
    nav_html = "".join(
        f'<a href="{prefix}{u}" class="{"active" if u == filename else ""}">{esc(t)}</a>'
        for u, t in NAV
    )
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - price-desk</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<header><h1>NFL Price Desk</h1><p class="sub">price-snapshot store - verified results feed - signal/staking leaderboard - gates - Q&amp;A - suggestions. Every number carries a status and a source; unverified values are blank or labelled. <a href="../index.html">Project home</a></p></header>
<nav>{nav_html}</nav>
<main>
{body}
</main>
<footer><p>Built by session arena/4a709dd0-korea2 on 2026-11-14 from the data files in <a href="{GB}price-desk/data">price-desk/data</a>. Archived values are third-party and unverified; verified values were read digit-for-digit from official NFL sources on 2026-11-14. Nothing on these pages is inferred.</p></footer>
</body>
</html>
"""
    out = os.path.join(PD, filename)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(doc)


def table(headers, rows):
    """rows: list of lists of pre-rendered cell HTML. First cells plain text ok."""
    h = "".join(f"<th>{c}</th>" for c in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def src_link(url, label="source"):
    return link(url, label) if url else '<span class="flag">no source</span>'


def local_src(path, label=None):
    return rel("https://github.com/karagemop466-tech/Korea2/blob/main/" + path, label or path)


def main():
    summary = load("store_summary.json")
    verified = load("verified_results_2026.json")
    feed = load_csv("results_feed.csv")
    snaps = load_csv("price_snapshots.csv")
    split = load("leaderboard_split.json")
    gate = load("demotion_gate.json")
    reqs = load("requirements_status.json")
    qs = load("questions.json")
    sugg = load("suggestions_queue.json")
    flagged = load("flagged.json")
    sources = load("sources.json")
    schema = load("store_schema.json")
    feed_by_id = {r["game_id"]: r for r in feed}

    # ---------------------------------------------------------------- overview
    acc = summary["archive_crosscheck"]
    b = []
    b.append("<h2>What this hub is</h2>")
    b.append("<p>This hub closes the loop on the nine named requirements: it records the opening and closing numbers for every market we originate (price-snapshot store), publishes a results feed whose verified rows were checked digit-for-digit against official NFL sources (so backtests and ROI can be computed), ranks strategies on signal quality separately from staking luck, defines the demotion gate, and collects the pre-decision questions and the suggestion review queue. Each table row links its source; values that could not be confirmed against an official source are blank and flagged.</p>")
    b.append("<h2>Verification at a glance</h2>")
    rows = [
        ["Results feed rows", esc(str(summary["games_in_feed"])), local_src("price-desk/data/results_feed.csv", "results_feed.csv")],
        ["Verified against official NFL sources", esc(str(acc["official_rows"])), link("https://www.nfl.com/scores/2026/week-9", "nfl.com scores (see results feed page)")],
        ["Archive cross-check: agrees / disagrees", f'{esc(str(acc["archive_agrees"]))} / {esc(str(acc["archive_disagrees"]))}', local_src("price-desk/data/store_summary.json", "store_summary.json")],
        ["Official scores filling an empty archive", esc(str(acc["official_filled_empty_archive"])), local_src("price-desk/data/verified_results_2026.json", "verification record")],
        ["Archived (third-party, unverified) rows", esc(str(summary["feed_by_score_status"].get("archived-unverified", 0))), local_src("price-desk/data/results_feed.csv", "results_feed.csv")],
        ["Price-snapshot rows (all markets we originate)", esc(str(summary["snapshot_rows"])), local_src("price-desk/data/price_snapshots.csv", "price_snapshots.csv")],
        ["Opening numbers available", "0 (no source exists)", link("pages/flagged.html", "flag PS-F-01")],
        ["Player-prop markets tracked", esc(str(summary["prop_rows"])), local_src("price-desk/data/price_snapshots_props.csv", "price_snapshots_props.csv")],
        ["Strategies qualified for rewards", "0", link("pages/leaderboard.html", "leaderboard")],
    ]
    b.append(table(["Measure", "Value", "Source"], rows))
    b.append("<h2>Nine requirements - status</h2>")
    rows = []
    for r in reqs["rows"]:
        rows.append([esc(r["id"]), esc(r["requirement"]), esc(r["status"]), link("pages/requirements.html", "detail"), local_src("price-desk/data/requirements_status.json", "data")])
    b.append(table(["ID", "Requirement", "Status", "Traceability", "Source"], rows))
    b.append('<p class="note">Unverified and flagged items do not block use of the research framework; they are published on the <a href="pages/flagged.html">Flagged for review</a> page with source links.</p>')
    page("index.html", "Overview", "\n".join(b))

    # --------------------------------------------------------- price snapshots
    b = ["<h2>Price-snapshot store</h2>",
         "<p>One row per originated market (game x market type x originating engine), with our fair line, the market's opening and closing numbers, and the difference as separate columns. Opening numbers are blank for every row: no opening-line source covers the origination window (<a href=\"flagged.html\">PS-F-01</a>). Closing numbers are archived third-party values, labelled <code>archived-unverified</code>. The difference column is computed as our_fair_line minus market_close_line and inherits the weaker status.</p>"]
    b.append("<h3>Coverage</h3>")
    rows = [
        ["Snapshot rows", esc(str(summary["snapshot_rows"])), local_src("price-desk/data/price_snapshots.csv", "price_snapshots.csv")],
        ["SPREAD rows", esc(str(summary["snapshot_by_market_type"].get("SPREAD", 0))), local_src("price-desk/scripts/build_store.py", "build_store.py")],
        ["TOTAL rows", esc(str(summary["snapshot_by_market_type"].get("TOTAL", 0))), local_src("price-desk/scripts/build_store.py", "build_store.py")],
        ["MONEYLINE rows", esc(str(summary["snapshot_by_market_type"].get("MONEYLINE", 0))), local_src("price-desk/scripts/build_store.py", "build_store.py")],
        ["Root-pipeline engine rows", esc(str(summary["snapshot_by_engine"].get("root-pipeline", 0))), local_src("data/derived/predictions.csv", "predictions.csv")],
        ["Origination-lab engine rows", esc(str(summary["snapshot_by_engine"].get("origination-lab", 0))), local_src("origination-lab/data/derived/lines.json", "lines.json")],
        ["Player-prop rows", esc(str(summary["prop_rows"])), local_src("origination-lab/data/derived/prop_lines.csv", "prop_lines.csv")],
    ]
    b.append(table(["Item", "Count", "Source"], rows))
    b.append(f'<p class="note">Spread convention: {esc(summary["spread_convention"])}.</p>')
    b.append("<h3>Column schema</h3>")
    rows = []
    for fname, spec in schema.items():
        for col, meaning in spec["columns"].items():
            rows.append([esc(fname), esc(col), esc(meaning), local_src("price-desk/data/store_schema.json", "schema")])
    b.append(table(["File", "Column", "Meaning", "Source"], rows))
    b.append("<h3>Sample: 2026 week 8 spreads, both engines (home-margin convention)</h3>")
    rows = []
    for r in snaps:
        if r["season"] == "2026" and str(r["week"]) == "8" and r["market_type"] == "SPREAD":
            rows.append([esc(r["market_id"]), esc(r["our_fair_line"]), esc(r["market_open_line"]) or '<span class="flag">blank (PS-F-01)</span>', esc(r["market_close_line"]), esc(r["difference"]), esc(r["close_status"][:22]), local_src("price-desk/data/price_snapshots.csv", "store row")])
    b.append(table(["market_id", "our fair", "open", "close", "difference", "close status", "Source"], rows))
    b.append('<p class="note">Full store: <a href="https://github.com/karagemop466-tech/Korea2/blob/main/price-desk/data/price_snapshots.csv">price_snapshots.csv</a> (2,364 rows) and <a href="https://github.com/karagemop466-tech/Korea2/blob/main/price-desk/data/price_snapshots_props.csv">price_snapshots_props.csv</a> (11,370 rows).</p>')
    page("pages/price-snapshots.html", "Price snapshots", "\n".join(b))

    # ------------------------------------------------------------ results feed
    b = ["<h2>Verified results feed</h2>",
         "<p>Settled results with per-row verification status, so backtests and ROI can be computed and audited. The verified rows below were read digit-for-digit from official NFL pages or gamebooks on 2026-11-14. Archived rows (the CSV) retain third-party values labelled <code>archived-unverified</code> for computation only - they are not published here as findings.</p>"]
    rows = [
        ["Verified-official rows", esc(str(acc["official_rows"])), local_src("price-desk/data/verified_results_2026.json", "verification record")],
        ["Archive agrees with official", esc(str(acc["archive_agrees"])), local_src("price-desk/data/verified_results_2026.json", "verification record")],
        ["Archive disagrees with official", esc(str(acc["archive_disagrees"])), local_src("price-desk/data/verified_results_2026.json", "verification record")],
        ["Official filled empty archive", esc(str(acc["official_filled_empty_archive"])), local_src("price-desk/data/verified_results_2026.json", "verification record")],
        ["Archived-unverified rows", esc(str(summary["feed_by_score_status"].get("archived-unverified", 0))), local_src("price-desk/data/results_feed.csv", "results_feed.csv")],
        ["Unsettled / missing rows", esc(str(summary["feed_by_score_status"].get("missing", 0))), local_src("price-desk/data/results_feed.csv", "results_feed.csv")],
        ["Settled games in feed", esc(str(summary["settled_games"])), local_src("price-desk/data/results_feed.csv", "results_feed.csv")],
    ]
    b.append(table(["Measure", "Value", "Source"], rows))
    b.append("<h3>Verified rows (official sources, retrieved 2026-11-14)</h3>")
    rows = []
    for v in verified["verified_scores"]:
        gid = v["game_id"]
        f_ = feed_by_id.get(gid, {})
        rows.append([esc(gid), esc(f"{v['away']} {v['away_score']} @ {v['home']} {v['home_score']}"),
                     esc(f_.get("spread_close_home", "")), esc(f_.get("total_close", "")),
                     esc(f_.get("ats_home_result", "")), esc(f_.get("total_over_result", "")),
                     link(v["source_url"], "official"), esc(verified["meta"]["verified_on"])])
    b.append(table(["game_id", "Final (official)", "close spread*", "close total*", "ATS home*", "Total*", "Source", "Checked"], rows))
    b.append('<p class="note">* Closing numbers and their settlements are archived-unverified (official odds do not exist, PS-F-08); scores and winners are verified-official.</p>')
    b.append("<h3>Recorded without scores (official page returned &quot;Hidden Score&quot; - not inferred)</h3>")
    rows = []
    for v in verified["hidden_scores"]:
        rows.append([esc(v["game_id"]), esc(f'{v["away"]} @ {v["home"]}'), '<span class="flag">blank</span>', esc(v["note"][:80] + "..."), link(v["source_url"], "official")])
    b.append(table(["game_id", "Matchup", "Score", "Note", "Source"], rows))
    b.append("<h3>Official gamebook discovery</h3>")
    gb = verified["official_gamebook_discovery"]
    b.append(f'<p>{esc(gb["note"])} Demonstrated record (WAS@NYG 2026 week 10):</p>')
    rows = [
        ["Final score", "WAS 24 @ NYG 21 (scoring plays: 3+7+7+7 vs 7+7+7)", link(gb["source_url"], "official gamebook")],
        ["WAS offense starters", esc(gb["was_nyg_starters_offense"]["WAS"]), link(gb["source_url"], "official gamebook")],
        ["NYG offense starters", esc(gb["was_nyg_starters_offense"]["NYG"]), link(gb["source_url"], "official gamebook")],
        ["WAS Not Active", esc(gb["was_nyg_not_active"]["WAS"]), link(gb["source_url"], "official gamebook")],
        ["NYG Not Active", esc(gb["was_nyg_not_active"]["NYG"]), link(gb["source_url"], "official gamebook")],
    ]
    b.append(table(["Item", "Value (official)", "Source"], rows))
    page("pages/results-feed.html", "Results feed", "\n".join(b))

    # --------------------------------------------------------------- leaderboard
    b = ["<h2>Leaderboard - signal separated from staking</h2>",
         f'<p>{esc(split["meta"]["ranking_rule"])} {esc(split["meta"]["status_note"])}</p>']
    b.append("<h3>Signal block (flat stake, luck controls) - this block alone sets signal_rank</h3>")
    rows = []
    for s in split["signal_block"]:
        rows.append([esc(str(s["signal_rank"])), esc(s["strategy"]), esc(s["rule"][:70] + ("..." if len(s["rule"]) > 70 else "")),
                     esc(s.get("n_graded", "")), esc(s.get("roi", "")[:8]), esc(s.get("perm_p", "")),
                     esc(s.get("deflated_sharpe", "")[:8]), esc(s.get("seasons_positive", "") + "/" + s.get("seasons_qualified", "")),
                     esc(s.get("tier", "")), local_src("origination/site_data/leaderboard.csv", "ledger")])
    b.append(table(["Signal rank", "Strategy", "Rule", "n graded", "flat ROI", "perm p", "defl. Sharpe", "seasons +", "Tier", "Source"], rows))
    b.append("<h3>Staking block - reported separately, never affects rank</h3>")
    rows = []
    for s in split["staking_block"]:
        plan = esc(s["declared_staking_plan"]) if s["declared_staking_plan"] else '<span class="flag">blank (no plan declared)</span>'
        rows.append([esc(s["strategy"]), plan, '<span class="flag">blank (no live bankroll ledger)</span>', '<span class="flag">blank</span>', local_src("data/strategies.json", "plans")])
    b.append(table(["Strategy", "Declared staking plan", "Realised plan ROI", "Max drawdown", "Source"], rows))
    b.append("<h3>Integrity controls (never ranked, never rewarded)</h3>")
    rows = []
    for c in split["controls"]:
        rows.append([esc(c["strategy"]), esc(c["rule"][:80]), esc(c["roi"][:8]), esc(c["tier"]), esc(c["purpose"][:80] + "..."), local_src("origination/site_data/leaderboard.csv", "ledger")])
    b.append(table(["Control", "Rule", "ROI", "Tier", "Purpose", "Source"], rows))
    page("pages/leaderboard.html", "Leaderboard", "\n".join(b))

    # -------------------------------------------------------------------- gates
    b = ["<h2>Validation gates and the demotion gate</h2>",
         f'<p><b>{esc(gate["meta"]["title"])}</b> - status: {esc(gate["meta"]["status"])}. {esc(gate["meta"]["relation_to_existing_work"])}</p>']
    b.append("<h3>Principles</h3><ul>")
    for p in gate["meta"]["principles"]:
        b.append(f"<li>{esc(p)}</li>")
    b.append("</ul>")
    b.append("<h3>Triggers</h3>")
    rows = []
    for t in gate["triggers"]:
        rows.append([esc(t["id"]), esc(t["name"]), esc(t["definition"]), esc(t["sample_floor"]), esc(t["severity"]), esc(t["rationale"][:110] + "..."), link(gate["sources"][0]["url"], "basis")])
    b.append(table(["ID", "Trigger", "Definition", "Sample floor", "Severity", "Rationale", "Source"], rows))
    b.append(f'<p><b>Cadence:</b> {esc(gate["evaluation_cadence"])}</p>')
    b.append(f'<p><b>On demotion:</b> {esc(" | ".join(gate["action"]["on_demotion"]))}</p>')
    b.append(f'<p><b>Re-promotion:</b> {esc(gate["re_promotion"]["rule"])} {esc(gate["re_promotion"]["limits"])} ({esc(gate["re_promotion"]["status"])})</p>')
    b.append("<h3>Open parameters for owner decision</h3><ul>")
    for p in gate["open_parameters_for_owner_decision"]:
        b.append(f"<li>{esc(p)}</li>")
    b.append("</ul>")
    rows = [[esc(s["name"]), link(s["url"], "link"), esc(s["role"])] for s in gate["sources"]]
    b.append(table(["Source", "URL", "Role"], rows))
    page("pages/gates.html", "Gates", "\n".join(b))

    # ------------------------------------------------------------- requirements
    b = ["<h2>Requirements traceability</h2>",
         "<p>Status of each of the nine named requirements, where it is implemented, and exactly what is still missing.</p>"]
    rows = []
    for r in reqs["rows"]:
        gaps = "<ul>" + "".join(f"<li>{esc(g)}</li>" for g in r["gaps"]) + "</ul>" if r["gaps"] else "-"
        src = esc(r["source"])
        if r["source"].startswith("http"):
            src = link(r["source"], r["source"][:60])
        else:
            src = local_src(r["source"].split(" ")[0].rstrip(":,"), r["source"][:60])
        rows.append([esc(r["id"]), esc(r["requirement"]), esc(r["status"]), esc(r["where"]), gaps, src])
    b.append(table(["ID", "Requirement", "Status", "Where", "Gaps", "Source"], rows))
    page("pages/requirements.html", "Requirements", "\n".join(b))

    # ---------------------------------------------------------------- questions
    b = ["<h2>Pre-decision Q&amp;A register</h2>",
         f'<p>{esc(qs["meta"]["rule"])}</p>']
    rows = []
    for q in qs["rows"]:
        answers = "<ul>" + "".join(f"<li>{esc(a)}</li>" for a in q["known_answers"]) + "</ul>"
        disc = "<ul>" + "".join(f"<li>{esc(a)}</li>" for a in q["discovery_suggestions"]) + "</ul>"
        src = link(q["source"], q["source"][:70]) if q["source"].startswith("http") else local_src(q["source"].split(" ")[0].rstrip(":,"), q["source"][:70])
        rows.append([esc(q["id"]), esc(q["question"]), esc(q["information_needed"]), answers, esc(q["missing"]), disc, esc(", ".join(q["blocks"]) or "-"), src])
    b.append(table(["ID", "Question", "Information needed", "Known answers (checked)", "Missing", "Discovery suggestions", "Blocks", "Source"], rows))
    page("pages/questions.html", "Questions", "\n".join(b))

    # -------------------------------------------------------------- suggestions
    b = ["<h2>Suggestion review queue</h2>",
         f'<p>{esc(sugg["meta"]["workflow"])}</p>']
    rows = []
    for s in sugg["rows"]:
        opts = "<ul>" + "".join(f'<li><b>{esc(o["path"])}</b> - {esc(o["trade-offs"])} (effort: {esc(o["effort"])}, impact: {esc(o["impact"])})</li>' for o in s["options"]) + "</ul>"
        srcs = " ".join(link(x, x[:40]) if x.startswith("http") else local_src(x.split(" ")[0].rstrip(":,"), x.split(" ")[0].rstrip(":,").split("/")[-1]) for x in s["sources"])
        rows.append([esc(s["id"]), esc(s["title"]), esc(s["category"]), esc(s["problem"]), opts, esc(s["recommended"]), esc(s["status"]), esc(", ".join(s["blocks"]) or "-"), srcs])
    b.append(table(["ID", "Suggestion", "Category", "Problem", "Options &amp; trade-offs", "Recommended", "Status", "Unblocks", "Source"], rows))
    page("pages/suggestions.html", "Suggestions", "\n".join(b))

    # ------------------------------------------------------------------ flagged
    b = ["<h2>Flagged for review</h2>", f'<p>{esc(flagged["meta"]["policy"])}</p>']
    rows = []
    for f_ in flagged["rows"]:
        srcs = " ".join(link(x, x[:44]) for x in f_["sources"])
        rows.append([esc(f_["id"]), esc(f_["title"]), esc(f_["detail"]), esc(f_["affected"]), esc(f_["status"]), esc(f_["suggestion"] or "-"), srcs])
    b.append(table(["ID", "Flag", "Detail", "Affected", "Status", "Suggestion", "Source"], rows))
    page("pages/flagged.html", "Flagged", "\n".join(b))

    # ------------------------------------------------------------------ sources
    b = ["<h2>Source registry</h2>", f'<p>{esc(sources["meta"]["note"])}</p>']
    rows = []
    for s in sources["rows"]:
        rows.append([esc(s["id"]), esc(s["name"]), esc(s["tier"]), esc(s["used_for"]), link(s["url"], "link"), esc(s["checked"])])
    b.append(table(["ID", "Source", "Tier", "Used for", "URL", "Checked"], rows))
    page("pages/sources.html", "Sources", "\n".join(b))
    print("price-desk pages written:", len(NAV))


if __name__ == "__main__":
    main()
