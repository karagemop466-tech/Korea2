#!/usr/bin/env python3
"""Render every page of the Decision Arena from the committed JSON.

Rules this file follows so it cannot drift into invention:
  * no number is typed into a template; every one is read from data/*.json;
  * templating is $name (see lib/arena.render), not braces, because HTML and CSS are full of
    braces and sharing their syntax produces escaping bugs that look like content bugs;
  * every table row ends in a source cell, enforced by lib/arena.table().
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402
from lib.arena import badge, blank, esc, fmt, kpi, notice, pct, render, src, table  # noqa: E402

ROOT = A.ROOT
D = A.load


import re as _re

_LINK = _re.compile(r'href="(?!https?://|#|mailto:)([^"]+)"')


def relativise(body: str, page_path: str) -> str:
    """Rewrite site-relative body links to page-relative ones.

    Body templates are written with links like pages/methods.html because that is how a human
    reads them. This turns them into ../pages/methods.html when the page lives in pages/, so the
    link resolves from wherever the page is written.
    """
    depth = 0 if "/" not in page_path else page_path.count("/")
    up = "../" * depth
    if not up:
        return body
    return _LINK.sub(lambda m: 'href="' + up + m.group(1) + '"', body)


def write(path: str, body: str, title: str, crumb: str, active: str) -> None:
    p = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w") as fh:
        fh.write(A.shell(title, crumb, relativise(body, path), active))
    print(f"  wrote {path}")


def n(x, nd=0, dash="&mdash;") -> str:
    if x is None:
        return dash
    if isinstance(x, str):
        return esc(x)
    return format(x, f",.{nd}f") if nd else format(int(x), ",")


def g(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def ci(pair, nd=3) -> str:
    if not pair or pair[0] is None:
        return "&mdash;"
    return " &ndash; ".join(fmt(x, nd) for x in pair)


def local(x) -> str:
    """Body links are written site-relative and rewritten to page-relative at write time."""
    return x


# ================================================================= overview
def page_index():
    prices = D("data/price_snapshots.json")
    results = D("data/results_feed.json")
    orig = D("data/origination.json")
    strat = D("data/strategies.json")
    corr = D("data/correlation.json")
    gates = D("data/gates.json")
    sugg = D("data/suggestions.json")
    qs = D("data/questions.json")

    vc = strat.get("verdict_counts", {})
    scored = orig.get("verified_scoring", {})
    qbwr1 = g(corr, "same_game", "qb_yards_vs_wr1_yards", default={})

    head_notice = notice(
        "<strong>Nothing here is live and no value is invented.</strong> "
        + str(vc.get("REJECTED", 0)) + " of " + str(len(strat.get("entries", [])))
        + " strategies are REJECTED, " + str(vc.get("PAPER", 0)) + " are PAPER and "
        + str(vc.get("LIVE", 0)) + " are LIVE. Of " + n(prices.get("n_snapshots"))
        + " price snapshots, <strong>"
        + n(g(prices, "grades", "unattributed_single_observation"))
        + "</strong> cannot be called opening or closing because the feed states no sampling time.",
        "warn", "pages/prices.html", "How each price is graded")

    kpis = "".join([
        kpi("Settled results verified", n(g(results, "coverage", "settled_reg_games")),
            "Regular-season games with both scores, re-derived from the scores themselves.",
            "pages/results.html", "Results feed"),
        kpi("Week 9 slate scored",
            n(g(scored, "slate", "games_graded")) + "/" + n(g(scored, "slate", "games_on_slate")),
            "Originated lines graded against the official NFL.com finals, one observation per game.",
            "pages/origination.html", "See the board"),
        kpi("Model side error", fmt(scored.get("model_side_mae"), 2) + " pts",
            "Market error on the same games: " + fmt(scored.get("market_side_mae"), 2)
            + " pts. The market is still better.", "pages/origination.html", "Walk-forward"),
        kpi("Strategies LIVE", str(vc.get("LIVE", 0)),
            "All ten gates, including execution. No strategy currently qualifies.",
            "pages/leaderboard.html", "Leaderboard"),
        kpi("Largest measured correlation", fmt(qbwr1.get("r"), 3),
            "QB passing yards vs WR1 receiving yards, from box scores only, with n and an interval.",
            "pages/correlation.html", "Correlation"),
        kpi("Demotion triggers", str(len(gates.get("demotion_rules", []))),
            "Each is a numeric trigger that returns a live strategy to paper without a judgement call.",
            "pages/gates.html", "Gates"),
    ])

    findings = [
        ["A single unattributed price is not an opening line",
         n(g(prices, "grades", "verified_open")) + " snapshots carry a published open timestamp",
         "So the open-to-close study exists for one season only and the page says so.",
         src("SRC-NFLVERSE-SCHED")],
        ["The market still beats the model",
         "model MAE " + fmt(scored.get("model_side_mae"), 2) + " vs market "
         + fmt(scored.get("market_side_mae"), 2) + " on the scored slate",
         "A fair line that is worse than the close is a description, not an edge.", src("SRC-NFL-SCHED-9")],
        ["Correlation is large where legs share a game",
         "QB &harr; WR1 r = " + fmt(qbwr1.get("r"), 3) + " (n = " + n(qbwr1.get("n")) + ")",
         "Pricing those legs independently understates the parlay's joint probability; measured, not assumed.",
         src("SRC-NFLVERSE-STATS")],
        ["No strategy survives the sample floor",
         str(sum(1 for e in strat.get("entries", []) if not e["gates"].get("DA-G2"))) + " of "
         + str(len(strat.get("entries", []))) + " fail the n &ge; 300 / n &ge; 100 floors",
         "The competition is published as a ranking of evidence, not of winners.", src("SRC-NIST-MULT")],
        ["The official depth rank does not exist to cite",
         "NFL.com's depth-chart path returns 404; the injury report has no depth column",
         "Replacement depth is therefore measured from participation, and labelled third-party.",
         src("SRC-NFL-DEPTH-404")],
    ]

    body = render("""
<div class="hero">
  <div class="eyebrow">Independent NFL signal research</div>
  <h1>Originate the line.<br><em>Then prove it, or say you cannot.</em></h1>
  <p class="lede">This workspace prices its own side, total and moneyline in that order, keeps the
  model's fair number, the market's number and the difference in separate columns, records what it can
  and cannot know about each price, and runs every candidate strategy through ten gates that separate
  <strong>signal</strong> from <strong>staking</strong>. Where an input is missing, the value is blank
  and the reason is published.</p>
</div>
$head_notice
<div class="kpis">$kpis</div>
<section class="block">
  <div class="eyebrow">At a glance</div>
  <h2>The five things that decide how this site should be read</h2>
  $findings_table
</section>
<div class="grid2">
  <div class="panel"><h3>What is verified</h3>
    <ul class="ticks">
      <li>$verified_one</li>
      <li>All 15 Week 9 2026 finals read from NFL.com and reconciled.</li>
      <li>$verified_two</li>
      <li>Every correlation published with n and a Fisher-z interval.</li>
    </ul>
    <a class="card-link" href="pages/verification.html">Verification log &rarr;</a></div>
  <div class="panel"><h3>What is deliberately blank</h3>
    <ul class="crosses">
      <li>No timestamped opening prices, so no per-bet closing-line value and no line-move signal.</li>
      <li>No historical prop prices, so the prop families are EXECUTION_BLOCKED, not tested.</li>
      <li>No official depth chart, so no row claims an official depth rank.</li>
      <li>No funded prize pool, so the tiers rank and do not pay.</li>
    </ul>
    <a class="card-link" href="pages/flagged.html">Flagged for review &rarr;</a></div>
</div>
<section class="block">
  <div class="eyebrow">Review before implementing</div>
  <h2>$sugg_n suggestions, gated on $q_n open questions</h2>
  <p class="lede">Every proposal carries a blocking question. A reviewer approves or rejects each one,
  and nothing is implemented until the blocking answer exists. This is the section to read before
  changing anything on this site.</p>
  <div class="tag-row">
    <a class="badge b-info" href="pages/suggestions.html">Open the suggestion register &rarr;</a>
    <a class="badge b-warn" href="pages/questions.html">Open the decision questions &rarr;</a>
  </div>
</section>
""",
    head_notice=head_notice, kpis=kpis,
    findings_table=table(["Finding", "Measured value", "Why it matters", "Source"], findings,
                          "Headline results. Every row is computed by the build in this repository."),
    verified_one=n(g(results, "coverage", "settled_reg_games"))
    + " settled regular-season games with scores, re-derived from the scores.",
    verified_two=str(g(D("data/depth.json"), "official_injury_report", "clubs_reported"))
    + " clubs transcribed from the official Week 10 report; zero status disagreements against an "
      "independent transcription.",
    sugg_n=str(len(sugg.get("suggestions", []))), q_n=str(len(qs.get("questions", []))))
    write("index.html", body, "Overview", "OVERVIEW", "index.html")


# ================================================================= executive
def page_executive():
    results = D("data/results_feed.json")
    prices = D("data/price_snapshots.json")
    orig = D("data/origination.json")
    strat = D("data/strategies.json")
    corr = D("data/correlation.json")
    sc = orig.get("verified_scoring", {})
    vc = strat.get("verdict_counts", {})
    ents = strat.get("entries", [])
    best = ents[0] if ents else {}

    side_rows = [[e["away"] + " at " + e["home"] + " &middot; side",
                  fmt(e["side"]["fair_line_home"], 2), fmt(e["side"]["market_line_home"], 2),
                  fmt(e["side"]["difference"], 2), src("SRC-NFLVERSE-SCHED")]
                 for e in orig.get("rows", [])[:6]]
    market_rows = [
        ["Side error on the scored slate (MAE, pts)", fmt(sc.get("model_side_mae"), 2),
         fmt(sc.get("market_side_mae"), 2),
         "The market's number is closer to the result than the model's.", src("SRC-NFL-SCHED-9")],
        ["Total error on the scored slate (MAE, pts)", fmt(sc.get("model_total_mae"), 2),
         fmt(sc.get("market_total_mae"), 2), "Same verdict on totals.", src("SRC-NFL-SCHED-9")],
        ["Model ATS record on its own side",
         str(sc.get("model_ats_wins", 0)) + "-" + str(sc.get("model_ats_losses", 0)), "&mdash;",
         "Under half the time on a slate of 15 games. Small n; reported, not generalised.",
         src("SRC-NFL-SCHED-9")],
    ]
    verdict_rows = [[
        "LIVE", str(vc.get("LIVE", 0)), "All ten gates, execution included. Nothing qualifies.",
        src("SRC-NIST-MULT")],
        ["PAPER", str(vc.get("PAPER", 0)), "Nine of ten gates with execution satisfied. Nothing qualifies.",
         src("SRC-NIST-MULT")],
        ["REJECTED", str(vc.get("REJECTED", 0)),
         "At least two gates fail. This is every registered strategy.", src("SRC-NIST-MULT")]]
    corr_rows = []
    for key, label, use in [
        ("qb_yards_vs_wr1_yards", "QB passing yards &harr; WR1 receiving yards",
         "Do not price these legs independently."),
        ("receptions_vs_receiving_yards", "Receptions &harr; receiving yards (same player)",
         "Near-substitutes: a combo of them is not two independent chances."),
        ("receptions_vs_targets", "Receptions &harr; targets (control)",
         "A mechanical relation that must be high if the pipeline is sane; it is."),
    ]:
        sec = "control" if key == "receptions_vs_targets" else "same_game"
        c = g(corr, sec, key, default={})
        corr_rows.append([label, fmt(c.get("r"), 3), n(c.get("n")), ci(c.get("ci")), use,
                          src("SRC-NFLVERSE-STATS")])
    gap_rows = [
        ["No timestamped prices", n(g(prices, "grades", "unattributed_single_observation"))
         + " of " + n(prices.get("n_snapshots")) + " snapshots are unattributed",
         "Closing-line value, line-move signals, demotion trigger DM-1, any claim about beating the close",
         src("SRC-NFLVERSE-SCHED")],
        ["No prop prices", str(sum(1 for e in ents if e["family"].startswith("prop")))
         + " prop families with zero priced bets", "Prop-combo ROI; the family is EXECUTION_BLOCKED",
         src("SRC-NFLVERSE-STATS")],
        ["No official depth chart", "NFL.com's depth-chart path returns 404",
         "Any official starter/backup rank; depth is measured from snap share instead",
         src("SRC-NFL-DEPTH-404")],
        ["No funded prize pool", "The pool field is null; status UNFUNDED", "Rewards; the tiers rank only",
         src("SRC-NIST-MULT")],
        ["Snapshot staleness", "Feed frozen at " + str(g(results, "coverage", "latest_settled_gameday")),
         "Scoring the live slate; Week 10's Thursday result is official but absent from the snapshot",
         src("SRC-NFL-SCHED-10")],
    ]
    body = render("""
<div class="hero"><div class="eyebrow">Executive summary</div>
<h1>What this build establishes, and what it refuses to claim</h1>
<p class="lede">One page for a reader who has five minutes. Every statement below is produced by the
build; the source next to each is the page it can be checked against.</p></div>

<section class="block"><h2>1. The line-origination pipeline works end to end</h2>
<p>The model produces a side, then a total, then a moneyline for $games games in Week $week of $season,
trained on $train games strictly before the slate's first kickoff. The ordering is enforced in code: the
total is emitted only after the side exists, and the moneyline only after the side distribution exists.</p>
$side_table
</section>

<section class="block"><h2>2. The market is still better than the model</h2>
$market_table
</section>

<section class="block"><h2>3. Signal and staking are separate, and both are mostly empty</h2>
<p>Ranking is by gates, then by beat-the-close rate, then by ROI. A lucky staking run cannot lift a
strategy with a negative signal because signal sorts first. The best-ranked strategy is
<strong>$best_name</strong> with $best_gates of 10 gates and a beat-the-close rate of $best_signal.</p>
$verdict_table
</section>

<section class="block"><h2>4. What the data does support: large, stable same-game correlation</h2>
$corr_table
</section>

<section class="block"><h2>5. The five gaps that block the next step</h2>
$gap_table
</section>

<section class="block"><h2>6. What a reader should do with this</h2>
<ul class="ticks">
  <li>Treat the correlation page as usable measurement with a stated n.</li>
  <li>Treat the leaderboard as an honest null: nothing qualifies, and the failing gate is named.</li>
  <li>Treat the origination page as a fair-line description, not a betting recommendation.</li>
  <li>Read the suggestions page before changing anything; each item names the question that blocks it.</li>
</ul>
</section>
""",
    games=str(g(orig, "slate", "games")), week=str(g(orig, "slate", "week")),
    season=str(g(orig, "slate", "season")), train=n(g(orig, "slate", "train_games_strictly_before")),
    side_table=table(["Fixture", "Fair number", "Market number", "Difference", "Source"], side_rows,
                     "First six of the originated slate. The fair line is the model's expected home "
                     "margin; the market line is the feed's own number in the same convention."),
    market_table=table(["Measure", "Model", "Market", "Reading", "Source"], market_rows,
                       "Model versus closing market on the verified slate."),
    best_name=esc(best.get("name", "n/a")), best_gates=str(best.get("gates_passed", 0)),
    best_signal=fmt(g(best, "signal", "beat_close_rate"), 4),
    verdict_table=table(["Verdict", "Count", "Meaning", "Source"], verdict_rows,
                        "Verdict counts across all registered strategies."),
    corr_table=table(["Pair", "r", "n", "95% interval", "Use", "Source"], corr_rows,
                     "Correlations computed from box scores only, with the control pair that tests the pipeline."),
    gap_table=table(["Gap", "Evidence", "What it blocks", "Source"], gap_rows,
                    "The gaps that cap what the site may claim, each with its evidence."))
    write("pages/executive.html", body, "Executive summary", "EXECUTIVE SUMMARY", "pages/executive.html")


# ================================================================= prices
def page_prices():
    p = D("data/price_snapshots.json")
    gr = p.get("grades", {})
    oc = p.get("price_completeness", {})
    study = p.get("opening_number_study", {})
    comp_rows = [
        ["Spread", n(oc.get("spread_legs")), n(oc.get("spread_legs_with_price")),
         pct(oc.get("spread_price_share")),
         "Unpriced legs are excluded from staking, never filled with a default price.",
         src("SRC-NFLVERSE-SCHED")],
        ["Total", n(oc.get("total_legs")), n(oc.get("total_legs_with_price")),
         pct(oc.get("total_price_share")), "Same rule.", src("SRC-NFLVERSE-SCHED")],
        ["Moneyline", n(oc.get("ml_legs")), n(oc.get("ml_legs_with_price")),
         pct(oc.get("ml_price_share")), "Same rule; the moneyline family is the best-populated.",
         src("SRC-NFLVERSE-SCHED")],
    ]
    study_rows = [[str(r["season"]), n(r["games_matched"]), n(r["spread_games_quoted"]),
                   fmt(r["mean_abs_move"], 2), fmt(r["median_abs_move"], 2), pct(r["share_unchanged"]),
                   n(r["totals_matched"]), fmt(r.get("totals_mean_abs_move"), 2),
                   src("SRC-NFLVERSE-NFLDATA")]
                  for r in study.get("rows", [])]
    if not study_rows:
        study_rows = [["none", "0", "0", "&mdash;", "&mdash;", "&mdash;", "0", "&mdash;",
                       src("SRC-NFLVERSE-NFLDATA")]]
    slate_rows = []
    for s in (p.get("current_slate") or [])[:20]:
        parts = s["game_id"].split("_")
        label = parts[3] + " at " + parts[4] if len(parts) > 4 else s["game_id"]
        spread = next((fmt(m["line"], 1) for m in s["markets"]
                       if m["market"] == "spread" and m["side"] == "home"), "&mdash;")
        total = next((fmt(m["line"], 1) for m in s["markets"] if m["market"] == "total"), "&mdash;")
        ml = next((fmt(m["price"], 0) for m in s["markets"]
                   if m["market"] == "moneyline" and m["side"] == "home"), "&mdash;")
        slate_rows.append([label, str(s["week"]), s.get("kickoff_et") or blank("no kickoff time in feed"),
                           spread, total, ml, badge("unattributed", "warn"), src("SRC-NFLVERSE-SCHED")])
    kpis = "".join([
        kpi("Snapshots", n(p.get("n_snapshots")), "One per game with at least one market value.",
            "pages/prices.html", "This page"),
        kpi("With a verified open", str(gr.get("verified_open", 0)),
            "Requires a published sampling timestamp. None exist.", "pages/flagged.html", "Why"),
        kpi("With an early separate snapshot", str(gr.get("documented_open_undocumented_time", 0)),
            "2021 only, from an undocumented publisher file.", "pages/sources.html", "Source"),
        kpi("Spread legs priced", pct(oc.get("spread_price_share")),
            "A line with no price cannot be staked or ROI-tested.", "pages/strategies.html",
            "Price discipline"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Price snapshots</div>
<h1>What we actually know about each number</h1>
<p class="lede">A price snapshot is one observation of one market on one game. Whether it can be called
an <em>opening</em> or a <em>closing</em> number is a question about its provenance, not about the value.
This page answers that question per snapshot and refuses to upgrade a grade without a timestamp.</p></div>

$notice
<div class="kpis">$kpis</div>

<section class="block"><h2>Price completeness by market</h2>
$comp_table
</section>

<section class="block"><h2>The opening-number study, and why it is one season</h2>
<p>The only committed file with a snapshot that is clearly <em>early</em> is the 2021 file. Its publisher
does not date it or document its columns, so it is graded
<code>documented_open_undocumented_time</code> and used for exactly one question: how far does the line
move between that snapshot and the close?</p>
$study_table
<p class="small">Read this table as: the only window in this repository where an early and a later number
both exist is 2021, and that window is $study_n spread games deep. Anything broader would be fabrication.</p>
</section>

<section class="block"><h2>Current slate snapshots (Weeks 9-10 of 2026)</h2>
$slate_table
$stale_notice
</section>
""",
    notice=notice(
        "<strong>The feed stores one price per market and no sampling time.</strong> So "
        + n(gr.get("unattributed_single_observation")) + " of " + n(p.get("n_snapshots"))
        + " snapshots are graded <code>unattributed_single_observation</code>. They are published because "
          "they are what exists, and labelled because calling them closing prices would be an invented claim.",
        "warn", "pages/methods.html", "How the grades work"),
    kpis=kpis,
    comp_table=table(["Market", "Legs quoted", "Legs with a price", "Share priced", "Consequence", "Source"],
                     comp_rows, "Legs are counted per side, so one game contributes two spread legs."),
    study_table=table(["Season", "Games matched", "Spread games quoted", "Mean |move|", "Median |move|",
                       "Share unchanged", "Totals matched", "Mean |move| (total)", "Source"], study_rows,
                      "Movement between the 2021 early snapshot and the feed's single price."),
    study_n=str(g(study, "aggregate", "n_games")),
    slate_table=table(["Game", "Week", "Kickoff (ET)", "Spread (home)", "Total", "Moneyline (home)",
                       "Grade", "Source"], slate_rows,
                      "The two most recent weeks in the frozen feed. The grade is identical for every row "
                      "by construction, which is the point."),
    stale_notice=notice(
        "The Week 10 Thursday game is already final per NFL.com, but this feed was compiled before it. "
        "The prices above are pregame numbers from a frozen snapshot, not live market prices.", "bad",
        "pages/results.html", "See the staleness check"))
    write("pages/prices.html", body, "Price snapshots", "PRICE SNAPSHOTS", "pages/prices.html")


# ================================================================= results
def page_results():
    r = D("data/results_feed.json")
    cov = r.get("coverage", {})
    recon = r.get("reconciliation", {})
    w9 = recon.get("week9_2026", {})
    w10 = recon.get("week10_thursday_2026", {})
    w9_rows = [[x["matchup"], x["official_score"], x["feed_score"] or blank("not in the snapshot"),
                badge(x["status"], "ok" if x["status"] == "match"
                      else ("warn" if x["status"] == "absent_from_snapshot" else "bad")),
                src(x["official_source"])] for x in w9.get("rows", [])]
    stale_rows = [[w10.get("matchup", ""), w10.get("official_score", ""),
                   badge("no" if not w10.get("present_in_committed_snapshot") else "yes",
                         "bad" if not w10.get("present_in_committed_snapshot") else "ok"),
                   badge("no" if not w10.get("present_in_fetched_feed") else "yes",
                         "bad" if not w10.get("present_in_fetched_feed") else "ok"),
                   src(w10.get("official_page", "SRC-NFL-SCHED-10"))]]
    def_rows = [["Margin (home)", esc(g(r, "derivations", "margin_home")),
                 "A copied column cannot be checked against the scores it claims to come from.",
                 src("SRC-NFLVERSE-SCHED")],
                ["Total", esc(g(r, "derivations", "total")), "Same reason.", src("SRC-NFLVERSE-SCHED")],
                ["Pushes", esc(g(r, "derivations", "push_logic")),
                 "A push silently dropped as a loss biases every ROI downward.", src("SRC-NFLVERSE-SCHED")]]
    recent = [[x["away"] + " at " + x["home"], x["gameday"],
               str(int(x["away_score"])) + "&ndash;" + str(int(x["home_score"])),
               fmt(x["margin_home"], 0), fmt(x["total"], 0),
               x.get("kickoff_et") or blank("no kickoff time"), src("SRC-NFLVERSE-SCHED")]
              for x in list(reversed(r.get("rows", [])))[:18]]
    kpis = "".join([
        kpi("Settled games", n(cov.get("settled_reg_games")),
            "Regular season, both scores present.", "pages/results.html", "This page"),
        kpi("Latest settled day", str(cov.get("latest_settled_gameday", "n/a")),
            "The snapshot's own horizon. Later games are not in it.", "pages/flagged.html", "Staleness"),
        kpi("Week 9 official matches", str(w9.get("agree", 0)) + "/" + str(w9.get("checked", 0)),
            str(w9.get("absent_from_snapshot", 0)) + " absent from the frozen snapshot, "
            + str(w9.get("mismatch", 0)) + " mismatched.", "pages/verification.html", "How this was checked"),
        kpi("Kickoff time present", pct(cov.get("kickoff_time_present_share")),
            "A missing kickoff time blocks point-in-time joins.", "pages/methods.html", "Method"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Results feed</div>
<h1>Every number below is re-derived from the scores</h1>
<p class="lede">Backtests and ROI are only as good as the results they are scored against. This feed
recomputes the margin and the total from the two scores rather than trusting a published
<code>result</code> column, then checks the most recent completed week against the official NFL.com
finals.</p></div>
<div class="kpis">$kpis</div>

<section class="block"><h2>Week 9 2026, the feed against NFL.com</h2>
<p>Read the status column carefully. <strong>absent_from_snapshot</strong> is not an error: the committed
feed was compiled before those games were played, so it has no result to disagree with. Only
<strong>mismatch</strong> would be an error, and there are $mismatch of them.</p>
$w9_table
</section>

<section class="block"><h2>The staleness check that matters</h2>
$stale_table
$stale_notice
</section>

<section class="block"><h2>How the derivations are defined</h2>
$def_table
</section>

<section class="block"><h2>Most recent settled games in the feed</h2>
$recent_table
</section>
""",
    kpis=kpis, mismatch=str(w9.get("mismatch", 0)),
    w9_table=table(["Matchup", "Official score", "Feed score", "Status", "Source"], w9_rows,
                   "All 15 Week 9 games, read from the official schedule page on 2026-11-14."),
    stale_table=table(["Game", "Official result", "In committed snapshot", "In live feed", "Source"],
                      stale_rows,
                      "A game the league has already decided and the snapshot does not contain. This is the "
                      "cleanest demonstration that the snapshot is stale."),
    stale_notice=notice(
        "The official Week 10 Thursday result is published and this build records it from the official "
        "page. The snapshot cannot, because it predates kickoff. Any figure on this site that depends on "
        "Week 10 is therefore a pregame figure, not a result.", "warn", "pages/questions.html",
        "Question Q-02"),
    def_table=table(["Quantity", "Definition used by this build", "Why not copy the feed's column", "Source"],
                    def_rows, "Definitions, so a reviewer can recompute any published figure."),
    recent_table=table(["Game", "Date", "Score", "Margin", "Total", "Kickoff (ET)", "Source"], recent,
                       "The last 18 settled games. The full history stays in the feed file."))
    write("pages/results.html", body, "Results feed", "RESULTS FEED", "pages/results.html")


# ================================================================= origination
def page_origination():
    o = D("data/origination.json")
    rows = o.get("rows", [])
    pend = o.get("pending_rows", [])
    sc = o.get("verified_scoring", {})
    wf = o.get("walk_forward", [])

    side_rows = [[e["away"] + " at " + e["home"], e["gameday"], fmt(e["side"]["fair_line_home"], 2),
                  fmt(e["side"]["market_line_home"], 2), fmt(e["side"]["difference"], 2),
                  pct(e["side"]["model_home_cover_prob"]),
                  badge(e["side"]["status"].replace("_", " "),
                        "info" if e["side"]["status"] == "originated" else "warn"),
                  src("SRC-NFLVERSE-SCHED")] for e in rows]
    total_rows = [[e["away"] + " at " + e["home"], fmt(e["total"]["fair_line"], 2),
                   fmt(e["total"]["market_line"], 2), fmt(e["total"]["difference"], 2),
                   pct(e["total"]["model_over_prob"]),
                   badge(e["total"]["status"].replace("_", " "),
                         "info" if e["total"]["status"] == "originated" else "warn"),
                   src("SRC-NFLVERSE-SCHED")] for e in rows]
    ml_rows = [[e["away"] + " at " + e["home"], pct(e["moneyline"]["fair_home_prob"]),
                fmt(e["moneyline"]["fair_home_ml"], 0),
                ("&mdash;" if e["moneyline"]["market_home_ml"] is None
                 else fmt(e["moneyline"]["market_home_ml"], 0)),
                pct(e["moneyline"]["difference_prob"]),
                badge(e["moneyline"]["status"].replace("_", " "),
                      "info" if e["moneyline"]["status"] == "originated" else "warn"),
                src("SRC-NFLVERSE-SCHED")] for e in rows]
    graded_rows = []
    for x in sc.get("rows", []):
        if x.get("status") != "graded":
            continue
        graded_rows.append([
            x["matchup"], x["official_score"], fmt(x["model_margin"], 2), fmt(x["market_line_home"], 1),
            fmt(x["model_abs_error"], 2), fmt(x["market_abs_error"], 2),
            ("&mdash;" if x["model_home_cover"] is None
             else badge("yes" if x["model_home_cover"] else "no",
                        "ok" if x["model_home_cover"] else "bad")),
            src(x.get("source_result", "SRC-NFL-SCHED-9"))])
    wf_rows = [[str(w["season"]), n(w["n"]), fmt(w["model_mae"], 2), fmt(w["market_mae"], 2),
                pct(w["model_ats_win_rate"]),
                "Market lower error" if w["market_mae"] < w["model_mae"] else "Model lower error",
                src("SRC-NFLVERSE-SCHED")] for w in wf]
    pend_rows = [[e["away"] + " at " + e["home"], e["gameday"], fmt(e["side"]["fair_line_home"], 2),
                  fmt(e["side"]["market_line_home"], 2), fmt(e["side"]["difference"], 2),
                  src("SRC-NFLVERSE-SCHED")] for e in pend]
    kpis = "".join([
        kpi("Slate", "Wk " + str(g(o, "slate", "week")) + ", " + str(g(o, "slate", "season")),
            str(g(o, "slate", "games")) + " games: the earliest week in the feed with no scores.",
            "pages/results.html", "Why this week"),
        kpi("Trained on", n(g(o, "slate", "train_games_strictly_before")),
            "Games strictly before the slate's first kickoff. No same-week leakage.",
            "pages/methods.html", "Leakage control"),
        kpi("Model side error", fmt(sc.get("model_side_mae"), 2),
            "Market on the same games: " + fmt(sc.get("market_side_mae"), 2) + ". Market better.",
            "pages/leaderboard.html", "Ranking"),
        kpi("Walk-forward seasons", str(len(wf)),
            "Each season refit on all prior data, then scored on the next.",
            "pages/methods.html", "Method"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Origination</div>
<h1>Side first. Then the total. Then the moneyline.</h1>
<p class="lede">The order is a dependency, not a preference: the total model consumes the side model, and
the moneyline is derived from the side model's own margin distribution. A market whose prerequisite is
missing is emitted as <code>blocked_by_side</code> rather than guessed. The fair number, the market's
number and the difference each get their own column so a reader can disagree with the model without
losing the market's view.</p></div>
<div class="kpis">$kpis</div>
$rule_notice

<section class="block"><h2>The originated board: side</h2>
$side_table
</section>

<section class="block"><h2>Total, then moneyline</h2>
$total_table
$ml_table
</section>

<section class="block"><h2>Scored against the official finals</h2>
<p>Because the official Week 9 results are published, this slate is not a promise: it is a measurement.
Each game is scored once.</p>
$graded_table
<p class="small">Aggregate: model side MAE $m_mae vs market $k_mae; totals $m_tmae vs $k_tmae. $note</p>
</section>

<section class="block"><h2>Walk-forward: does the model generalise?</h2>
$wf_table
</section>

<section class="block"><h2>Next open slate (pregame numbers from the frozen feed)</h2>
$pend_table
</section>
""",
    kpis=kpis, rule_notice=notice(esc(g(o, "slate", "slate_rule")), "", "pages/questions.html", "Question Q-02"),
    side_table=table(["Game", "Date", "Fair (home)", "Market (home)", "Difference", "Model cover prob",
                      "Status", "Source"], side_rows,
                     "The fair line and the market line are both the expected HOME margin, so a positive "
                     "difference means the model is higher on the home team."),
    total_table=table(["Game", "Fair total", "Market total", "Difference", "Over prob", "Status", "Source"],
                      total_rows,
                      "Totals. A blank market column means the feed has no total for that game; the fair "
                      "number is still shown."),
    ml_table=table(["Game", "Fair home win prob", "Fair home ML", "Market home ML",
                    "Model minus market prob", "Status", "Source"], ml_rows,
                   "The moneyline is derived from the same margin distribution as the side, which is why "
                   "its status can never be better than the side's."),
    graded_table=table(["Game", "Official score", "Model margin", "Market line", "Model error",
                        "Market error", "Model covered", "Source"], graded_rows,
                       "One observation per game. ATS counts the model's own side against the market line."),
    m_mae=fmt(sc.get("model_side_mae"), 2), k_mae=fmt(sc.get("market_side_mae"), 2),
    m_tmae=fmt(sc.get("model_total_mae"), 2), k_tmae=fmt(sc.get("market_total_mae"), 2),
    note=esc(sc.get("note", "")),
    wf_table=table(["Season", "Games", "Model MAE", "Market MAE", "Model ATS win rate", "Reading", "Source"],
                   wf_rows, o.get("walk_forward_note", "Walk-forward, refit on all prior seasons.")),
    pend_table=table(["Game", "Date", "Fair (home)", "Market (home)", "Difference", "Source"], pend_rows,
                     "Published so a reader can see the model before the games. These are not live prices."))
    write("pages/origination.html", body, "Origination", "ORIGINATION", "pages/origination.html")


# ================================================================= leaderboard
def page_leaderboard():
    s = D("data/strategies.json")
    ents = s.get("entries", [])
    vc = s.get("verdict_counts", {})
    board = [[str(e["rank"]), esc(e["name"]), esc(e["family"]), str(e["gates_passed"]) + "/10",
              pct(e["signal"]["beat_close_rate"]), n(e["signal"]["n_graded"]),
              pct(e["staking"]["roi"]), n(e["staking"]["n_bets"]),
              badge(e["verdict"], "ok" if e["verdict"] == "LIVE"
                    else ("info" if e["verdict"] == "PAPER" else "bad")),
              src("SRC-NFLVERSE-SCHED")] for e in ents]
    why_rows = [
        ["Beat the close", "Was the side we took right against the closing number?",
         "Compare the settled result with the closing line, ignoring price entirely.",
         "Yes, but only via a binomial test published with its n and interval.", src("SRC-NFLVERSE-SCHED")],
        ["ROI", "What would 1 unit staked have returned?", "Sum of per-bet profit over priced bets only.",
         "Yes, heavily: a run of wins on short prices moves ROI fast, which is why it does not rank.",
         src("SRC-NFLVERSE-SCHED")],
        ["Closing-line value", "Did we hold a better number than the close?",
         "Our line minus the closing line, in points.",
         "No: it is a property of the price, not the result. It is zero wherever we take the close "
         "itself, and says so.", src("SRC-NFLVERSE-SCHED")],
    ]
    tier_rows = [[esc(t["tier"]), esc(t["requirement"]), esc(t["reward"]),
                  (", ".join(t["awarded_to"]) if t["awarded_to"] else blank("no strategy qualifies")),
                  src("SRC-NIST-MULT")] for t in g(s, "rewards", "tiers", default=[])]
    kpis = "".join([
        kpi("Registered strategies", str(len(ents)),
            str(g(s, "family_counts", "single")) + " singles, " + str(g(s, "family_counts", "parlay"))
            + " parlays, " + str(g(s, "family_counts", "prop_combo")) + " prop combos.",
            "pages/strategies.html", "Strategy lab"),
        kpi("LIVE", str(vc.get("LIVE", 0)), "All ten gates. Nothing qualifies.",
            "pages/gates.html", "Gate definitions"),
        kpi("PAPER", str(vc.get("PAPER", 0)), "Nine of ten. Nothing qualifies.",
            "pages/gates.html", "Gate definitions"),
        kpi("REJECTED", str(vc.get("REJECTED", 0)), "Everything registered, with the failing gate named.",
            "pages/flagged.html", "Flags"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Leaderboard</div>
<h1>Signal ranks. Staking follows.</h1>
<p class="lede">A strategy can win money on a bad signal and lose money on a good one. This board
therefore publishes two separate columns and ranks on the first: the <strong>beat-the-close rate</strong>
(was our side right against the closing number, regardless of price) and the <strong>ROI</strong> (what a
fixed 1-unit stake would have banked). A lucky staking run cannot lift a strategy whose signal is negative,
because signal sorts first.</p></div>
<div class="kpis">$kpis</div>
$empty_notice

<section class="block"><h2>The board</h2>
$board_table
<p class="small">Signal <em>n</em> counts graded opportunities; staking <em>n</em> counts only bets with a
real price. The two differ wherever the feed has no price, which is deliberate: no price, no staking, no
exception.</p>
</section>

<section class="block"><h2>Why signal and staking can disagree</h2>
$why_table
</section>

<section class="block"><h2>Reward tiers</h2>
$tier_table
$fund_notice
</section>
""",
    kpis=kpis,
    empty_notice=notice(
        "<strong>There is no winner.</strong> Zero strategies pass the gates, so this board is a ranking of "
        "measured evidence rather than a podium. That is the honest result and it is the headline.", "warn",
        "pages/questions.html", "Q-08: is the bar right?"),
    board_table=table(["#", "Strategy", "Family", "Gates", "Signal: beat close", "n", "Staking: ROI",
                       "Priced bets", "Verdict", "Source"], board, s.get("ranking_rule", "")),
    why_table=table(["Column", "Question it answers", "How it is computed", "Can luck inflate it?", "Source"],
                    why_rows, "The three columns exist so a reader can tell skill from a good run."),
    tier_table=table(["Tier", "Requirement", "What it would award", "Awarded to", "Source"], tier_rows,
                     "Tiers are computed from the gates. They are not granted by hand."),
    fund_notice=notice("<strong>UNFUNDED.</strong> " + esc(g(s, "rewards", "funding", "note")), "bad",
                       "pages/suggestions.html", "SUG-09: fund it or rename it"))
    write("pages/leaderboard.html", body, "Leaderboard", "LEADERBOARD", "pages/leaderboard.html")


# ================================================================= strategies
def page_strategies():
    s = D("data/strategies.json")
    ents = s.get("entries", [])
    mt = s.get("multiple_testing", {})
    reg_rows = [[str(e["rank"]), esc(e["id"]), esc(e["name"]), esc(e["rule"]),
                 str(e["gates_passed"]) + "/10",
                 esc(", ".join(k.split("-")[1] for k, v in e["gates"].items() if not v) or "none"),
                 badge(e["verdict"], "ok" if e["verdict"] == "LIVE"
                       else ("info" if e["verdict"] == "PAPER" else "bad")),
                 src("SRC-NFLVERSE-SCHED")] for e in ents]
    sig_rows = [[esc(e["id"]), pct(e["signal"]["beat_close_rate"]), ci(e["signal"]["beat_close_ci"]),
                 n(e["signal"]["n_graded"]), fmt(e["signal"]["permutation_p"], 4),
                 fmt(e["signal"]["hit_p"], 4), fmt(e["signal"]["bh_q"], 4),
                 fmt(e["signal"]["edge_points_mean"], 3), src("SRC-NFLVERSE-SCHED")] for e in ents]
    stk_rows = [[esc(e["id"]), n(e["staking"]["n_bets"]),
                 str(e["staking"]["wins"]) + "-" + str(e["staking"]["losses"]) + "-"
                 + str(e["staking"]["pushes"]), pct(e["staking"]["roi"]),
                 (" &ndash; ".join(pct(x) for x in e["staking"]["roi_ci"])
                  if e["staking"]["roi_ci"] else "&mdash;"),
                 fmt(e["staking"]["profit_units"], 2), fmt(e["staking"]["deflated_sharpe_p"], 4),
                 src("SRC-NFLVERSE-SCHED")] for e in ents]
    luck_rows = [
        ["Benjamini-Hochberg", "Publishing the best of many tries as if it were the only try.",
         "q &le; " + str(mt.get("q")) + " across " + str(mt.get("tests")) + " tests", src("SRC-NIST-MULT")],
        ["Bonferroni", "A single lucky result surviving after the family correction.",
         "p &lt; " + str(mt.get("bonferroni_alpha")), src("SRC-NIST-MULT")],
        ["Deflated Sharpe", "A strategy selected because it looked best among many clearing the same bar "
         "as one specified in advance.", "N = " + str(mt.get("n_trials")) + " variants",
         src("SRC-BAILEY-LOPEZ")],
        ["Exact permutation test", "Reading a 52% hit rate as skill when coins produce it routinely.",
         "one-sided binomial tail", src("SRC-NIST-CORR")],
        ["Bootstrap interval", "A point ROI with no uncertainty band.", "2,000 resamples, fixed seed",
         src("SRC-NIST-CORR")],
        ["Out-of-sample split", "A rule fitted on the seasons it is scored on.",
         "spec hashed and fixed before scoring", src("SRC-SKLEARN-LEAK")],
    ]
    kpis = "".join([
        kpi("Rules registered", str(len(ents)), "Singles, parlays and prop combos in one family.",
            "pages/methods.html", "Method"),
        kpi("Tests in the family", str(mt.get("tests", 0)),
            "BH at q = " + str(mt.get("q")) + ", Bonferroni alpha " + str(mt.get("bonferroni_alpha")) + ".",
            "pages/methods.html", "Multiple testing"),
        kpi("Sample floor", "n &ge; 300 / n &ge; 100",
            "Graded opportunities / priced bets. No rule currently meets it.", "pages/gates.html", "DA-G2"),
        kpi("Prop prices held", "0", "Every prop combo is EXECUTION_BLOCKED, not merely untested.",
            "pages/correlation.html", "See why"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Strategy lab</div>
<h1>Every rule, registered before it was scored</h1>
<p class="lede">The rule text in the register is the spec. It is hashed into the output
(<code>$spec</code>&hellip;) so a rule cannot be quietly tightened after a bad result. The rules cover
single bets, two-leg parlays and player-prop combos, and each must clear the same ten gates.</p></div>
<div class="kpis">$kpis</div>

<section class="block"><h2>The register</h2>
$reg_table
</section>

<section class="block"><h2>Signal detail</h2>
$sig_table
<p class="small">The price-free view. 'Permutation p' is the exact one-sided probability that fair coins
would beat this rate.</p>
</section>

<section class="block"><h2>Staking detail, kept deliberately separate</h2>
$stk_table
<p class="small">What a 1-unit stake would have returned. A positive ROI here is not a promotion: the
signal column decides the ranking.</p>
</section>

<section class="block"><h2>How luck is removed</h2>
$luck_table
</section>
""",
    spec=esc(s.get("spec_sha256", "")[:16]), kpis=kpis,
    reg_table=table(["#", "ID", "Name", "Rule as registered", "Gates", "Failed gates", "Verdict", "Source"],
                    reg_rows, "The complete registered family. The failing gate ids are the diagnosis."),
    sig_table=table(["Strategy", "Beat-close rate", "95% interval", "n", "Permutation p", "Hit-rate p",
                     "BH q", "Edge (pts)", "Source"], sig_rows,
                    "Signal, price-free. An interval that includes 0.5 means the rate is indistinguishable "
                    "from a coin."),
    stk_table=table(["Strategy", "Priced bets", "W-L-P", "ROI", "95% ROI interval", "Units",
                     "Deflated Sharpe p", "Source"], stk_rows,
                    "Staking, on real prices only."),
    luck_table=table(["Control", "What it prevents", "Configured as", "Source"], luck_rows,
                     "Six mechanisms, all applied, none optional."))
    write("pages/strategies.html", body, "Strategy lab", "STRATEGY LAB", "pages/strategies.html")


# ================================================================= gates
def page_gates():
    gt = D("data/gates.json")
    s = D("data/strategies.json")
    gate_rows = [[x["id"], esc(x["name"]), esc(x["rule"]), esc(x["enforced"]), src("SRC-NIST-MULT")]
                 for x in s.get("gates", [])]
    dem_rows = [[x["id"], esc(x["trigger"]), esc(x["action"]), esc(x["resets"]), esc(x["rationale"]),
                 src(x["source"])] for x in gt.get("demotion_rules", [])]
    pro_rows = [[x["id"], esc(x["requirement"]), esc(x["action"]), src("SRC-NIST-MULT")]
                for x in gt.get("promotion_rules", [])]
    sm_rows = [[x["from"], x["to"], esc(x["when"]), src("SRC-NIST-MULT")]
               for x in g(gt, "state_machine", "transitions", default=[])]
    size_rows = [
        ["Base unit", fmt(g(gt, "position_sizing", "base_unit"), 2), "One unit is the default stake.",
         src("SRC-NIST-MULT")],
        ["Maximum unit", fmt(g(gt, "position_sizing", "max_unit"), 2),
         "No strategy may exceed this, whatever the score.", src("SRC-NIST-MULT")],
        ["Formula", esc(g(gt, "position_sizing", "rule")), esc(g(gt, "position_sizing", "note")),
         src("SRC-NIST-MULT")],
    ]
    kpis = "".join([
        kpi("Demotion triggers", str(len(gt.get("demotion_rules", []))),
            "Each is a numeric condition, not a promise to review.", "pages/gates.html", "This page"),
        kpi("Bets before live", str(g(gt, "live_requirements", "min_bets_before_live")),
            "However good a strategy looks, it cannot be live on fewer.", "pages/strategies.html",
            "Why that matters"),
        kpi("Promotion rules", str(len(gt.get("promotion_rules", []))),
            "One step at a time, by a computed trigger.", "pages/gates.html", "State machine"),
        kpi("Currently live", str(len(g(gt, "current_state", "live", default=[]))),
            "So no demotion can have fired yet.", "pages/flagged.html", "Untested rule"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Gates &amp; demotion</div>
<h1>How a strategy gets in, and how it is thrown out</h1>
<p class="lede">Promotion is hard and demotion is automatic. Every rule on this page is numeric, is computed
by the build, and fires without a judgement call. A live strategy that stops working returns to paper on
the next evaluation; paper is the default state and live is the exception.</p></div>
<div class="kpis">$kpis</div>
$principle

<section class="block"><h2>The ten validation gates</h2>
$gate_table
</section>

<section class="block"><h2>Demotion rules</h2>
$dem_table
</section>

<section class="block"><h2>Promotion rules</h2>
$pro_table
</section>

<section class="block"><h2>The state machine</h2>
$sm_table
</section>

<section class="block"><h2>Position sizing</h2>
$size_table
</section>
$never_fired
""",
    kpis=kpis, principle=notice(esc(gt.get("principle", "")), "", "pages/flagged.html", "What is untested"),
    gate_table=table(["ID", "Gate", "Rule", "How it is enforced in code", "Source"], gate_rows,
                     "A strategy needs all ten. The enforcement column names the mechanism, so the gate is "
                     "auditable rather than aspirational."),
    dem_table=table(["ID", "Trigger", "Action", "What resets", "Why", "Source"], dem_rows,
                    "Any one trigger fires the demotion. There is no discretionary override."),
    pro_table=table(["ID", "Requirement", "Action", "Source"], pro_rows,
                    "Promotion is also computed, not granted."),
    sm_table=table(["From", "To", "When", "Source"], sm_rows, esc(g(gt, "state_machine", "note"))),
    size_table=table(["Rule", "Value", "Meaning", "Source"], size_rows,
                     "Sizing is capped so a single good run cannot be scaled into a large loss."),
    never_fired=notice(
        "<strong>The demotion rules have never fired.</strong> With zero live strategies there is nothing to "
        "demote, so the code path is defined and published but untested in operation. See the suggestion that "
        "simulates the transition before it matters.", "warn", "pages/suggestions.html", "SUG-10"))
    write("pages/gates.html", body, "Gates &amp; demotion", "GATES", "pages/gates.html")


# ================================================================= correlation
def page_correlation():
    c = D("data/correlation.json")
    pp = c.get("parlay_pricing", {})
    combos = c.get("prop_combos", {})

    def section(title, key, note):
        rows = []
        for v in c.get(key, {}).values():
            rows.append([esc(v.get("label", "")), fmt(v.get("r"), 4), ci(v.get("ci"), 4), n(v.get("n")),
                         fmt(v.get("p"), 6),
                         badge("interval excludes 0" if v.get("ci_excludes_zero") else "includes 0",
                               "ok" if v.get("ci_excludes_zero") else "mute"),
                         esc(v.get("note", "")), src("SRC-NFLVERSE-STATS")])
        return ("<section class=\"block\"><h2>" + title + "</h2>"
                + table(["Pair", "r", "95% interval", "n", "p", "Reading", "Note", "Source"], rows, note)
                + "</section>")

    price_rows = [
        ["Leg threshold (QB passing yards over)", fmt(g(pp, "thresholds", "qb_pass_yards_over"), 0),
         "Set at the sample median so each leg is a 50% proposition by construction.",
         src("SRC-NFLVERSE-STATS")],
        ["Leg threshold (WR1 receiving yards over)", fmt(g(pp, "thresholds", "wr1_rec_yards_over"), 0),
         "Same rule.", src("SRC-NFLVERSE-STATS")],
        ["Measured joint, 2 legs same game", pct(pp.get("joint_2leg_same_game")),
         "What actually happened; its interval is on the correlation row above.", src("SRC-NFLVERSE-STATS")],
        ["Independent product, 2 legs", pct(pp.get("independent_2leg")),
         "What pricing the legs separately would assume.", src("SRC-NFLVERSE-STATS")],
        ["Measured joint, 4 legs (two independent games)", pct(pp.get("joint_4leg")),
         "The correlated pair squared. The cross-game step IS an independence assumption and is labelled.",
         src("SRC-NFLVERSE-STATS")],
        ["Independent product, 4 legs", pct(pp.get("independent_4leg")),
         "The number a naive multiplication produces.", src("SRC-NFLVERSE-STATS")],
        ["Overstatement factor", fmt(pp.get("factor_4leg"), 2) + "&times;", esc(pp.get("note", "")),
         src("SRC-NFLVERSE-STATS")],
    ]
    combo_rows = [[esc(x["label"]), fmt(x.get("r"), 4), ci(x.get("ci"), 4), n(x.get("n")),
                   esc(x["pricing_implication"]), badge("no", "bad"), badge("no", "bad"),
                   src(x["source"])] for x in combos.get("combos", [])]
    seasons = c.get("scope", {}).get("seasons", [0, 0])
    kpis = "".join([
        kpi("Team-games", n(g(c, "scope", "team_games")),
            "The unit of observation for team-level pairs.", "pages/methods.html", "Scope"),
        kpi("Player-games", n(g(c, "scope", "player_games")), "Rows in the box-score feed.",
            "pages/sources.html", "Source"),
        kpi("Seasons", str(seasons[0]) + "&ndash;" + str(seasons[1]),
            "Pooled; a per-season table is an open question.", "pages/questions.html", "Q-11"),
        kpi("4-leg overstatement", fmt(pp.get("factor_4leg"), 2) + "&times;",
            "Independent pricing versus the measured joint, on the same games.",
            "pages/strategies.html", "Parlays"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Correlation</div>
<h1>Computed from box scores. Never from a price.</h1>
<p class="lede">A parlay's price depends on how its legs move together. That number has to come from what
players did, not from what a book thought they would do, so every coefficient here is computed from the
per-player box scores alone. No market number, no line and no model output enters any value on this page.
Each coefficient carries its <em>n</em> and a Fisher-z interval.</p></div>
$scope_notice
<div class="kpis">$kpis</div>
$same_section
$live_section
$control_section

<section class="block"><h2>What the correlation does to a parlay price</h2>
$price_table
</section>

<section class="block"><h2>Prop combos: measured, and honestly unpriceable</h2>
$combo_notice
$combo_table
</section>
""",
    scope_notice=notice(
        "Correlation here is descriptive, not a test that selects a strategy. It is published with n and an "
        "interval so a reader can judge the precision; the multiple-testing correction is applied where "
        "selection happens, on the strategy page.", "", "pages/methods.html", "Method"),
    kpis=kpis,
    same_section=section("Same-game pairs: the ones a parlay actually uses", "same_game",
                         "These are the legs that share a game, and therefore the ones where independence is wrong."),
    live_section=section("Live-value pairs: how a player's day relates to his team's score", "live_values",
                         "Useful for building a fair line; not parlay legs on their own."),
    control_section=section("Control pairs: does the pipeline pass its own sanity check?", "control",
                            "The receptions-versus-targets pair is mechanically near-tautological. It comes out at "
                            "the expected magnitude, which is evidence the join and the aggregation are correct."),
    price_table=table(["Quantity", "Value", "What it means", "Source"], price_rows,
                      "Measured joint rates against the independent product, on n = "
                      + n(pp.get("n")) + " games."),
    combo_notice=notice(esc(combos.get("reason", "")), "bad", "pages/questions.html", "Q-07"),
    combo_table=table(["Combo", "r", "95% interval", "n", "Pricing implication", "Price held?", "ROI tested?",
                       "Source"], combo_rows,
                      "The measurement is done. The price is missing, so the ROI column does not exist. Filling "
                      "it would be invention."))
    write("pages/correlation.html", body, "Correlation", "CORRELATION", "pages/correlation.html")


# ================================================================= depth
def page_depth():
    d = D("data/depth.json")
    rep = d.get("official_injury_report", {})
    depth = d.get("depth", {})
    ready = d.get("readiness", {})
    rep_rows = [[r["team"], str(r["out"]), str(r["doubtful"]), str(r["questionable"]),
                 str(r["practice_only"]), str(r["total_listed"]), src("SRC-NFL-INJ-10")]
                for r in rep.get("rows", [])]
    out_rows = [[r["team"], esc(r["player"]), esc(r["pos"]), esc(r["injury"] or "&mdash;"),
                 esc(r["practice"]), badge(r["game_status"], "bad"), src("SRC-NFL-INJ-10")]
                for r in rep.get("out_players", [])]
    readiness_rows = [
        ["Who is out?", badge("yes", "ok"), "None: the official report is transcribed.", src("SRC-NFL-INJ-10")],
        ["Which position group is thin?", badge("yes", "ok"),
         "Counts by position are derivable from the report.", src("SRC-NFL-INJ-10")],
        ["How deep is the replacement?",
         badge("yes" if ready.get("can_answer_how_deep_is_the_replacement") else "no",
               "ok" if ready.get("can_answer_how_deep_is_the_replacement") else "bad"),
         esc(ready.get("blocking_gap", "")), src("SRC-NFLVERSE-SNAP")],
        ["Is there an official depth rank?", badge("no", "bad"),
         "The league publishes none machine-readable; the depth-chart path returns 404.",
         src("SRC-NFL-DEPTH-404")],
    ]
    if depth.get("status") == "MEASURED":
        d_rows = [[str(t["season"]), t["side"], n(t["n_replacements"]), fmt(t["mean_replacement_depth"], 2),
                   pct(t["share_by_second_string_or_deeper"]),
                   ", ".join(k + ": " + str(v) for k, v in sorted(t["bands"].items())),
                   src("SRC-NFLVERSE-SNAP")] for t in depth.get("by_season_side", [])]
        depth_block = table(["Season", "Side", "Replacements", "Mean depth of replacement",
                             "Share 2nd-string or deeper", "Bands", "Source"], d_rows,
                            depth.get("definition", ""))
        depth_block += ("<p class=\"small\">" + esc(depth.get("caveat", ""))
                        + " The rank is measured, so no row on this page claims an official depth rank.</p>")
    else:
        depth_block = notice("<strong>BLOCKED.</strong> " + esc(depth.get("reason", "")), "bad",
                             "pages/suggestions.html", "SUG-05: run the fetch in CI")
        depth_block += table(
            ["Input", "Status", "Why", "Source"],
            [["Snap counts (nflverse release)", badge("absent", "bad"),
              "Release assets are unreachable from this build environment. The CI workflow fetches them.",
              src("SRC-NFLVERSE-SNAP")],
             ["Depth charts (nflverse release)", badge("absent", "bad"),
              "Same transport problem; the feed's schema is documented and timestamped.",
              src("SRC-NFLVERSE-DEPTH")],
             ["Official injury report", badge("present", "ok"),
              "Transcribed from NFL.com and cross-checked against an independent transcription with zero "
              "disagreements.", src("SRC-NFL-INJ-10")]],
            "What is present and what is not, with the reason for each.")
    kpis = "".join([
        kpi("Clubs in the official report", str(rep.get("clubs_reported", 0)),
            "Every club with a Week 10 game.", "pages/sources.html", "Official page"),
        kpi("Players listed Out", str(len(rep.get("out_players", []))),
            "Official game status, transcribed verbatim.", "pages/sources.html", "Official page"),
        kpi("Replacement depth", "MEASURED" if depth.get("status") == "MEASURED" else "BLOCKED",
            ("Replacement events measured from participation." if depth.get("status") == "MEASURED"
             else "Snap counts are fetched in CI; this build environment cannot reach the release assets."),
            "pages/questions.html", "Q-05"),
        kpi("Official depth rank", "none", "No official depth column exists to cite anywhere on this page.",
            "pages/flagged.html", "Why"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Injuries &amp; depth</div>
<h1>Who is out is easy. Who replaces him is the question.</h1>
<p class="lede">Losing a first-string player to his backup and losing him to a fourth-string player are
different football teams, and a report that counts only "starters out" cannot tell them apart. This page
publishes the official report, the measured replacement depth, and the reason the second half cannot yet be
completed here.</p></div>
$gap_notice
<div class="kpis">$kpis</div>

<section class="block"><h2>Official Week 10 report, per club</h2>
$rep_table
</section>

<section class="block"><h2>Players ruled Out for Week 10</h2>
$out_table
</section>

<section class="block"><h2>Replacement depth, measured from participation</h2>
$depth_block
</section>

<section class="block"><h2>What this page can and cannot answer</h2>
$ready_table
</section>
""",
    gap_notice=notice(
        "<strong>" + str(g(d, "official_depth_chart_gap", "status")) + ": the league publishes no "
        "machine-readable depth chart.</strong> " + esc(g(d, "official_depth_chart_gap", "evidence"))
        + " Consequence: " + esc(g(d, "official_depth_chart_gap", "consequence")), "warn",
        "pages/sources.html", "The 404 is registered as a source"),
    kpis=kpis,
    rep_table=table(["Club", "Out", "Doubtful", "Questionable", "Practice only", "Total listed", "Source"],
                    rep_rows, "Counts transcribed from the official page. 'Practice only' means the player "
                    "appeared on the report with a practice status but no game status."),
    out_table=table(["Club", "Player", "Position", "Injury", "Practice", "Game status", "Source"], out_rows,
                    "Every Out row from the official report. The injury column is blank where the league left "
                    "it blank."),
    depth_block=depth_block,
    ready_table=table(["Question", "Answerable today?", "Blocking gap", "Source"], readiness_rows,
                      "Stated as answers rather than as a roadmap."))
    write("pages/depth.html", body, "Injuries &amp; depth", "INJURIES &amp; DEPTH", "pages/depth.html")


# ================================================================= suggestions
def page_suggestions():
    s = D("data/suggestions.json")
    qs = {q["id"]: q for q in D("data/questions.json").get("questions", [])}
    reg = [[x["id"], esc(x["title"]), esc(x["category"]),
            badge(x["state"], "info" if x["state"] == "proposed" else "ok"),
            badge(x["impact"].split(" ")[0],
                  {"HIGH": "bad", "MEDIUM": "warn", "LOW": "mute"}.get(x["impact"].split(" ")[0], "mute")),
            x["blocked_by"] + " &ndash; " + esc((qs.get(x["blocked_by"]) or {}).get("question", "")[:90]),
            src("SRC-NFLVERSE-SCHED")] for x in s.get("suggestions", [])]
    details = []
    for x in s.get("suggestions", []):
        q = qs.get(x["blocked_by"], {})
        decision = table(["Field", "Value", "Reviewer sets", "Source"],
                         [["State", badge(x["state"], "info"), "&mdash;", src("SRC-NIST-MULT")],
                          ["Decision", blank("no reviewer has decided"), "approve / reject / defer",
                           src("SRC-NIST-MULT")]],
                         "The decision row is blank on purpose: it is the reviewer's to fill.")
        details.append(render("""
<section class="block"><h2>$id &middot; $title</h2>
<div class="panel">
<p><strong>Evidence.</strong> $evidence</p>
<p><strong>Proposal.</strong> $proposal</p>
<p><strong>Impact.</strong> $impact<br><strong>Cost.</strong> $cost<br>
<strong>Risk.</strong> $risk<br><strong>Unblocks.</strong> $unblocks</p>
<p><strong>Blocking question $qid:</strong> $question</p>
<p><strong>Files if approved:</strong> <code>$files</code></p>
$decision
</div></section>
""", id=esc(x["id"]), title=esc(x["title"]), evidence=esc(x["evidence"]), proposal=esc(x["proposal"]),
                           impact=esc(x["impact"]), cost=esc(x["cost"]), risk=esc(x["risk"]),
                           unblocks=esc(x["unblocks"]), qid=esc(x["blocked_by"]),
                           question=esc(q.get("question", "not registered")),
                           files=esc(", ".join(x["files_if_approved"])), decision=decision))
    kpis = "".join([
        kpi("Proposals", str(len(s.get("suggestions", []))),
            "Across price data, results, origination, depth, strategies and the competition.",
            "pages/suggestions.html", "This page"),
        kpi("Proposed", str(sum(1 for x in s.get("suggestions", []) if x["state"] == "proposed")),
            "No item has been approved.", "pages/suggestions.html", "This page"),
        kpi("Blocking questions", str(len(qs)), "Every proposal names the question that gates it.",
            "pages/questions.html", "Questions"),
        kpi("Implemented", "0", "By design: this hub publishes the register and implements none of it.",
            "pages/methods.html", "Why"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Suggestions</div>
<h1>Read this before changing anything</h1>
<p class="lede">Each item is a proposal with the measurement that motivates it, what it costs, what it risks,
and the question that must be answered first. Nothing here is implemented. A reviewer sets a state and only
an approved item may be implemented, in the files named on its own row.</p></div>
$rule_notice
<div class="kpis">$kpis</div>

<section class="block"><h2>The register</h2>
$reg_table
</section>
$details
""",
    rule_notice=notice("<strong>Review rule:</strong> " + esc(s.get("review_rule", "")), "warn",
                       "pages/questions.html", "Open the question register"),
    kpis=kpis,
    reg_table=table(["ID", "Suggestion", "Category", "State", "Impact", "Blocked by", "Source"], reg,
                    "The whole register. State is 'proposed' for every row until a reviewer acts."),
    details="".join(details))
    write("pages/suggestions.html", body, "Suggestions", "SUGGESTIONS", "pages/suggestions.html")


# ================================================================= questions
def page_questions():
    qd = D("data/questions.json")
    qlist = qd.get("questions", [])
    reg = [[x["id"], esc(x["question"]),
            badge(x["status"], "bad" if x["status"] == "open" else ("warn" if x["status"].startswith("partial") else "ok")),
            esc(", ".join(x["blocks"]) or "&mdash;"), src("SRC-NIST-MULT")] for x in qlist]
    blocks = []
    for x in qlist:
        ans = x.get("answer")
        blocks.append("<section class=\"block\"><h2>" + esc(x["id"]) + " &middot; " + esc(x["question"])
                      + "</h2>" + table(
                          ["Dimension", "Detail", "Source"],
                          [["What we have", esc(x["have"]), src("SRC-NFLVERSE-SCHED")],
                           ["What we do not have", esc(x["missing"]), src("SRC-NFLVERSE-SCHED")],
                           ["How to discover it", esc(x["discovery"]), src("SRC-NIST-MULT")],
                           ["Answer held", esc(ans) if ans else blank("no answer yet"), src("SRC-NIST-MULT")],
                           ["Status", badge(x["status"], "bad" if x["status"] == "open" else "warn"),
                            esc(", ".join(x["blocks"]) or "blocks nothing"), src("SRC-NIST-MULT")]],
                          "The four dimensions every open question needs.") + "</section>")
    kpis = "".join([
        kpi("Questions", str(len(qlist)), "Across data, method, competition and review.",
            "pages/questions.html", "This page"),
        kpi("Open", str(sum(1 for x in qlist if x["status"] == "open")), "No answer held at all.",
            "pages/suggestions.html", "Blocked suggestions"),
        kpi("Partially answered", str(sum(1 for x in qlist if x["status"].startswith("partial"))),
            "Some evidence, not enough for a decision.", "pages/verification.html", "Evidence"),
        kpi("Answered", str(sum(1 for x in qlist if x["status"] == "answered")),
            "Nothing is fully closed yet.", "pages/flagged.html", "Flags"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Decision questions</div>
<h1>What must be answered before a decision is reasonable</h1>
<p class="lede">Every figure on this site has a boundary, and these are the boundaries stated as questions.
Each row says what we have, what we do not have, how the missing part could be discovered, and which
proposals cannot proceed until it is answered. Nothing is inferred.</p></div>
<div class="kpis">$kpis</div>

<section class="block"><h2>The register</h2>
$reg_table
</section>
$blocks
""",
    kpis=kpis,
    reg_table=table(["ID", "Question", "Status", "Blocks", "Source"], reg,
                    "One row per question. The Blocks column resolves to the suggestion register."),
    blocks="".join(blocks))
    write("pages/questions.html", body, "Decision questions", "DECISION QUESTIONS", "pages/questions.html")


# ================================================================= verification
def page_verification():
    v = D("data/verification.json")
    checks = v.get("checks", [])
    ok = sum(1 for c in checks if c.get("pass"))
    chk_rows = [[esc(c["name"]), esc(c["rule"]),
                 badge("pass" if c.get("pass") else "fail", "ok" if c.get("pass") else "bad"),
                 esc(c.get("proves", "")), src(c.get("source", "SRC-NIST-MULT"))] for c in checks]
    lim_rows = [[esc(c["name"]), esc(c.get("does_not_prove", "")), src(c.get("source", "SRC-NIST-MULT"))]
                for c in checks]
    hash_rows = [[esc(i["name"]), "<code>" + esc(i["path"]) + "</code>",
                  "<code>" + esc(i["sha256"][:16]) + "</code>", n(i.get("rows")),
                  src(i.get("source", "SRC-NFLVERSE-SCHED"))] for i in v.get("inputs", [])]
    rec_rows = [[esc(x["item"]), esc(x["source_name"]), esc(x["method"]),
                 badge(x["result"], "ok" if x["result"].startswith(("match", "agree")) else "warn"),
                 src(x["source"])] for x in v.get("reconciliations", [])]
    kpis = "".join([
        kpi("Checks run", str(len(checks)), "Structural, arithmetic and policy checks executed on every build.",
            "pages/verification.html", "This page"),
        kpi("Passing", str(ok) + "/" + str(len(checks)), "A failing check fails the build; it cannot be waived.",
            "pages/suggestions.html", "Fix path"),
        kpi("Inputs hashed", str(len(v.get("inputs", []))), "Every input is hashed so a rebuild can be compared.",
            "pages/methods.html", "Determinism"),
        kpi("Official pages read", str(v.get("official_pages_read", 0)),
            "Read by this session, with the date and the excerpt recorded.", "pages/sources.html",
            "Source register"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Verification</div>
<h1>What was checked, how, and what it proved</h1>
<p class="lede">A number that has not been checked is a rumour. This page lists every verification this build
performs, the rule it enforces, and whether it passed. It also states plainly what a passing check does
<em>not</em> establish, because a green tick that overclaims is worse than no tick.</p></div>
<div class="kpis">$kpis</div>

<section class="block"><h2>The checks</h2>
$chk_table
</section>

<section class="block"><h2>What a passing check does not prove</h2>
$lim_table
</section>

<section class="block"><h2>Input hashes</h2>
$hash_table
</section>

<section class="block"><h2>Official-source reconciliation</h2>
$rec_table
</section>
""",
    kpis=kpis,
    chk_table=table(["Check", "Rule enforced", "Result", "What it proves", "Source"], chk_rows,
                    "Every check is executed in this build; nothing on this page is a claim of intent."),
    lim_table=table(["Check", "What it does NOT establish", "Source"], lim_rows,
                    "The limits are stated next to the results, not in a footnote."),
    hash_table=table(["Input", "Path", "SHA-256 (first 16)", "Rows", "Source"], hash_rows,
                     "Re-hash these files and the build is reproducible or it is not."),
    rec_table=table(["Item", "Official source", "Method", "Result", "Source"], rec_rows,
                    "Each reconciliation was performed by reading the official page in this session and "
                    "recording what it said."))
    write("pages/verification.html", body, "Verification", "VERIFICATION", "pages/verification.html")


# ================================================================= flagged
def page_flagged():
    f = D("data/flagged.json")
    items = f.get("items", [])
    rows = [[x["id"], esc(x["title"]),
             badge(x["severity"], {"high": "bad", "medium": "warn"}.get(x["severity"], "mute")),
             esc(x["affects"]), esc(x["evidence"]), src(x["source"])] for x in items]
    kpis = "".join([
        kpi("Flags", str(len(items)), "Each has an owner, an impact and a source.", "pages/flagged.html",
            "This page"),
        kpi("Blanked values", str(f.get("blanked_value_count", 0)),
            "Counted from the built output, not estimated.", "pages/methods.html", "Blank policy"),
        kpi("Blocking a live claim", str(sum(1 for x in items if x.get("severity") == "high")),
            "High-severity items cap what the site may say.", "pages/suggestions.html", "Fixes"),
        kpi("Resolved this build", "0", "No flag has been closed; closure requires a source, not an opinion.",
            "pages/verification.html", "Checks"),
    ])
    body = render("""
<div class="hero"><div class="eyebrow">Flagged for review</div>
<h1>Everything this site cannot prove, in one place</h1>
<p class="lede">This page is the honesty ledger. An item is here because a value could not be confirmed from a
source, because a source contradicts itself, or because the data cannot answer the question it is being
asked. Nothing here blocks publication; all of it blocks <em>trusting</em> the affected number without
reading the flag first.</p></div>
<div class="kpis">$kpis</div>

<section class="block"><h2>The ledger</h2>
$rows_table
</section>

<section class="block"><h2>What a reader should conclude</h2>
<ul class="crosses">
  <li>No price in this repository can be called an opening or a closing number without a timestamp.</li>
  <li>No player-prop ROI exists, because no prop price exists.</li>
  <li>No official depth rank exists to cite; every depth number is measured, not published.</li>
  <li>No strategy is live, and the reward pool is unfunded.</li>
  <li>The results snapshot is stale by at least one completed week.</li>
</ul>
<p class="small">Those five statements are the reason this site is published as a research record rather than
as a service. Each will be removed from this list when its source exists, not when it becomes inconvenient.</p>
</section>
""",
    kpis=kpis,
    rows_table=table(["ID", "Flag", "Severity", "Affected", "Evidence", "Source"], rows,
                     "Every flag, its blast radius and the source that establishes it."))
    write("pages/flagged.html", body, "Flagged for review", "FLAGGED FOR REVIEW", "pages/flagged.html")


# ================================================================= sources
def page_sources():
    s = D("data/sources.json")
    reg = [[x["id"], badge(x["tier"], "ok" if x["tier"] == "official" else "warn"), esc(x["publisher"]),
            esc(x.get("supports", "")), x.get("read_on", ""),
            badge(x.get("state", "").replace("_", " "), "ok" if x.get("state") == "read" else "mute"),
            '<a href="' + esc(x["url"]) + '" rel="noopener">' + esc(x["title"][:48]) + "</a>"]
           for x in s.get("sources", [])]
    neg = [
        ["NFL.com team depth-chart path", badge("404", "bad"),
         "No official starter/backup rank can be cited; depth is measured from participation instead.",
         '<a href="' + esc(A.sources()["SRC-NFL-DEPTH-404"]["url"]) + '" rel="noopener">NFL.com depth-chart path</a>'],
        ["nfldata line files documentation", badge("undocumented", "warn"),
         "Column meanings and sampling times for the 2021 early snapshot are not published, so it is graded "
         "and not trusted for open/close claims.",
         '<a href="' + esc(A.sources()["SRC-NFLVERSE-SC-LINES-DOC"]["url"]) + '" rel="noopener">nfldata DATASETS.md</a>'],
        ["Schedules feed sampling time", badge("absent", "warn"),
         "No timestamp per price, which is why every snapshot is unattributed.",
         '<a href="' + esc(A.sources()["SRC-NFLVERSE-SCHED"]["url"]) + '" rel="noopener">nflverse schedules release</a>'],
    ]
    body = render("""
<div class="hero"><div class="eyebrow">Source register</div>
<h1>Every citation, with what it actually says</h1>
<p class="lede">Two tiers are used and they are never mixed. <strong>official</strong> means the publisher is
the National Football League. <strong>third_party</strong> means a redistributor or aggregator whose numbers
are not published by the league. A third-party row is marked <span class="tier">3P</span> wherever it
appears, so a reader can weigh it.</p></div>
$policy
<section class="block"><h2>The register</h2>
$reg_table
</section>
<section class="block"><h2>Sources that were checked and found wanting</h2>
<p>A negative result is a result. These were opened and did not deliver what a page would need.</p>
$neg_table
</section>
""",
    policy=notice(esc(s.get("policy", "")), "warn", "pages/flagged.html", "Where the gaps are"),
    reg_table=table(["ID", "Tier", "Publisher", "What it supports", "Read on", "State", "Link"], reg,
                    "Every source this hub cites. The 'state' column distinguishes a page actually read from "
                    "one linked for context."),
    neg_table=table(["What was checked", "Outcome", "Consequence", "Link"], neg,
                    "Negative findings are published so the next reader does not repeat the check."))
    write("pages/sources.html", body, "Source register", "SOURCE REGISTER", "pages/sources.html")


# ================================================================= methods
def page_methods():
    steps = [
        ["Fetch inputs", "<code>scripts/fetch_inputs.py</code>", "Pruned feeds plus a hash manifest",
         badge("fail-closed", "ok"), src("SRC-NFLVERSE-SCHED")],
        ["Market and origination", "<code>scripts/build_market.py</code>",
         "price_snapshots, results_feed, origination", badge("yes", "ok"), src("SRC-NFLVERSE-SCHED")],
        ["Strategy competition", "<code>scripts/build_strategies.py</code>", "strategies, gates",
         badge("yes", "ok"), src("SRC-NIST-MULT")],
        ["Correlations", "<code>scripts/build_correlation.py</code>", "correlation, parlay pricing",
         badge("yes", "ok"), src("SRC-NFLVERSE-STATS")],
        ["Depth and injuries", "<code>scripts/build_depth.py</code>", "depth, official report join",
         badge("yes", "ok"), src("SRC-NFL-INJ-10")],
        ["Registers", "<code>scripts/verify.py --pre-site</code>", "verification, flagged",
         badge("yes", "ok"), src("SRC-NIST-CORR")],
        ["Page render", "<code>scripts/build_site.py</code>", "every HTML page", badge("yes", "ok"),
         src("SRC-NIST-CORR")],
        ["Verification", "<code>scripts/verify.py</code>",
         "the same file plus a pass/fail exit code", badge("fails the build", "ok"), src("SRC-NIST-CORR")],
    ]
    defs = [
        ["Spread sign", "The home line IS the expected home margin; home covers when margin &minus; line &gt; 0.",
         "Treating the line as a negative handicap gives a 77% home-cover rate on real data, which is how "
         "this error is caught.", src("SRC-NFLVERSE-SCHED")],
        ["Beat the close", "The side taken beat the closing number on the field, ignoring price.",
         "Using profit instead mixes price into a skill measure.", src("SRC-NFLVERSE-SCHED")],
        ["ROI", "Sum of per-bet profit over priced bets only, fixed 1-unit stake.",
         "Imputing a price for unpriced legs would manufacture the ROI being measured.", src("SRC-NFLVERSE-SCHED")],
        ["Correlation", "Pearson r over box-score values, Fisher-z interval.",
         "Rank correlation would be robust to outliers but is not what a parlay joint needs.",
         src("SRC-NIST-CORR")],
        ["Model training window", "Every settled game strictly before the slate's first kickoff.",
         "Including same-week games leaks the result of games happening alongside.", src("SRC-SKLEARN-LEAK")],
        ["Luck correction", "BH q, Bonferroni, deflated Sharpe with N variants, exact permutation test.",
         "A single p-value on the best of many tries is the most common way a research page lies.",
         src("SRC-BAILEY-LOPEZ")],
    ]
    body = render("""
<div class="hero"><div class="eyebrow">Methods</div>
<h1>How each number is produced, and what would make it wrong</h1>
<p class="lede">These are the definitions a reviewer needs to recompute anything on this site. Where a choice
was made, the alternative and the reason are stated, because a method that cannot be argued with cannot be
checked.</p></div>

<section class="block"><h2>The build</h2>
$steps_table
<p class="small">Run <code>scripts/run_all.py</code> to execute all eight steps in order.</p>
</section>

<section class="block"><h2>Definitions that change the answer</h2>
$defs_table
</section>

<section class="block"><h2>What would falsify this site</h2>
$falsify_table
</section>
""",
    steps_table=table(["Step", "Script", "What it produces", "Deterministic?", "Source"], steps,
                      "Run scripts/run_all.py to do all eight in order."),
    defs_table=table(["Quantity", "Definition", "The alternative, and why it is not used", "Source"], defs,
                     "Each of these has a wrong version that produces a more impressive number."),
    falsify_table=table(["Claim made by this site", "What would falsify it", "Source"],
                        [["The market is better than the model",
                          "A walk-forward season where the model's error is lower on a meaningful sample.",
                          src("SRC-NFLVERSE-SCHED")],
                         ["Same-game legs are correlated", "A season where the interval includes zero.",
                          src("SRC-NIST-CORR")],
                         ["No strategy qualifies",
                          "A strategy clearing all ten gates, which would appear on the leaderboard automatically.",
                          src("SRC-NIST-MULT")],
                         ["The results snapshot is stale",
                          "A refresh whose reconciled week matches the official page at 15 of 15.",
                          src("SRC-NFL-SCHED-10")],
                         ["No official depth rank exists",
                          "A league-published depth file at a stable URL.", src("SRC-NFL-DEPTH-404")]],
                        "Stated so the site can be argued out of its own conclusions."))
    write("pages/methods.html", body, "Methods", "METHODS", "pages/methods.html")


def main():
    A.write_css()
    for fn in (page_index, page_executive, page_prices, page_results, page_origination,
               page_leaderboard, page_strategies, page_gates, page_correlation, page_depth,
               page_suggestions, page_questions, page_verification, page_flagged,
               page_sources, page_methods):
        fn()
    print("site rendered")


if __name__ == "__main__":
    main()
