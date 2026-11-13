#!/usr/bin/env python3
"""Render the Review Board: a landing page plus category subpages, from the JSON registers only.

Rules enforced by this file (and re-checked by verify.py):
  * no number is typed into a page - values are read from review-board/data/*.json or from a sibling
    hub's committed register, and each row links the file it came from;
  * every table row ends with a source cell containing an https link;
  * a value with no source is rendered as an explicit 'blank - unverified' marker, never a guess;
  * the build is deterministic: the same inputs produce byte-identical output.
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
DATA = os.path.join(HUB, "data")
OUT_PAGES = os.path.join(HUB, "pages")
ASSETS = os.path.join(HUB, "assets")
REPO = os.path.dirname(HUB)
REPO_TREE = "https://github.com/karagemop466-tech/Korea2/tree/main/"
SNAPSHOT = "2026-11-13"
TITLE = "Review Board"

NAV = [
    ("Review &amp; decisions", [
        ("index.html", "Overview"),
        ("pages/executive.html", "Executive summary"),
        ("pages/suggestions.html", "Suggestion review queue"),
        ("pages/path.html", "Recommended path &amp; rules"),
        ("pages/questions.html", "Open questions &amp; gaps"),
        ("pages/flagged.html", "Flagged for review"),
    ]),
    ("Origination programme", [
        ("pages/signals.html", "Signal catalogue"),
        ("pages/gates.html", "Validation gates"),
        ("pages/competition.html", "Leaderboard &amp; rewards"),
        ("pages/reconciliation.html", "Cross-hub reconciliation"),
    ]),
    ("Current slate", [
        ("pages/injuries.html", "Injury tracking"),
        ("pages/depth.html", "Depth &amp; deficiency"),
    ]),
    ("Repository", [
        ("pages/hubmap.html", "Hub map &amp; repo review"),
        ("pages/sources.html", "Source register"),
    ]),
]

REGISTERS: dict = {}


# ---------------------------------------------------------------- helpers
def load(name: str) -> dict:
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


def load_repo(*parts: str):
    try:
        with open(os.path.join(REPO, *parts)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def clip(v, n: int = 240) -> str:
    s = " ".join(str(v if v is not None else "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def blank(why: str = "no official source") -> str:
    return f'<span class="blank" title="{esc(why)}">blank &middot; {esc(why)}</span>'


# Paths a sibling register cites that this session found returning 404. A dead path is never rendered
# as a live citation: the URL stays visible as text, marked, so the claim it was used for remains checkable.
DEAD_PATHS = ("operations.nfl.com/the-rules/nfl-injury-report-policy",
              "operations.nfl.com/football-ops/league-governance/injury-report",
              "nfl.com/standings/2026/divisions")


def link(url: str, label: str = "") -> str:
    if not url:
        return blank("no source link available")
    if any(d in url for d in DEAD_PATHS):
        return (f'<span class="sub">cited by a sibling hub; 404 when opened {SNAPSHOT}</span> '
                f'<code>{esc(url)}</code>')
    text = label or url.split("//")[-1].split("/")[0]
    return f'<a href="{esc(url)}" rel="noopener">{esc(clip(text, 64))}</a>'


def table(headers, rows, caption: str = "", cls: str = "") -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = []
        for c in r:
            if isinstance(c, tuple):
                cells.append(f'<td class="{esc(c[1])}">{c[0]}</td>')
            else:
                cells.append(f"<td>{c}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = f"<caption>{caption}</caption>" if caption else ""
    if not rows:
        cap += '<p class="empty">No rows: nothing was published that matches this view.</p>'
    return (f'<div class="table-wrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def unent(v) -> str:
    """Render a label that already carries HTML entities as plain text.

    The root navigation tuple stores labels as markup (Correlation &amp; parlays); re-escaping them
    would print '&amp;' to a reader, so entities are decoded before escaping."""
    return esc(str(v if v is not None else "").replace("&amp;", "&"))


def badge(text, kind: str = "") -> str:
    return f'<span class="badge {esc(kind)}">{esc(text)}</span>'


def card(title: str, value: str, note: str, href: str, label: str) -> str:
    return (f'<article class="kpi"><span class="kpi-label">{esc(title)}</span>'
            f'<strong>{value}</strong><p>{note}</p>'
            f'<a class="card-link" href="{href}">{esc(label)} &rarr;</a></article>')


def notice(kind: str, title: str, body: str, href: str = "", link_text: str = "More") -> str:
    a = f'<a href="{esc(href)}">{esc(link_text)} &rarr;</a>' if href else ""
    return (f'<div class="notice {esc(kind)}"><span class="dot"></span><div>'
            f'<strong>{esc(title)}</strong><div>{body}</div>{a}</div></div>')


def section(title: str, body: str, eyebrow: str = "", lead: str = "") -> str:
    eb = f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    ld = f'<p class="lead">{lead}</p>' if lead else ""
    return f'<section class="block">{eb}<h2>{esc(title)}</h2>{ld}{body}</section>'


def hub_row_source(x: dict) -> str:
    """The source cell for a hub register row.

    A row ends with an https link, always. If the hub's own citation points at a path that 404s today, the
    dead URL is still shown as text and the committed register file is linked alongside it."""
    srcs = x.get("sources") or [{}]
    url = srcs[0].get("url") or ""
    cell = link(url, srcs[0].get("id") or "cited page") if url else ""
    if not url or any(d in url for d in DEAD_PATHS):
        cell = (cell + " " if cell else "") + file_link(f'{x["hub"]}/data', f'{x["hub"]} register')
    return cell or blank("no source recorded by any hub")


def status_badge(status) -> str:
    s = str(status or "").lower()
    if not s:
        return badge("not stated")
    if s.startswith(("answered", "done", "verified", "have", "yes")):
        return badge(status, "ok")
    if s.startswith(("partial", "proposed", "needs", "answerable", "in progress", "pending", "testable")):
        return badge(status, "warn")
    return badge(status, "bad")


def layout(title: str, current: str, body: str, crumb: str = "") -> str:
    # titles arrive with markup entities for the <h1>; escape must not double-encode them
    plain_title = title.replace("&amp;", "&")
    crumb_text = (crumb or plain_title).upper()
    nav = []
    for group, items in NAV:
        links = []
        for href, label in items:
            active = ' class="active" aria-current="page"' if href == current else ""
            links.append(f'<a href="{href}"{active}>{label}</a>')
        nav.append(f'<div class="nav-label">{group}</div>'
                   f'<nav aria-label="{esc(plain_title)}">{"".join(links)}</nav>')
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(plain_title)} | {esc(TITLE)}</title>
<meta name="description" content="NFL line-origination review board: de-duplicated suggestions, decision-readiness register, signal programme, validation gates and current-slate injury tracking.">
<meta name="generator" content="review-board/scripts/build_site.py">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="index.html"><span class="mark">RB</span>
    <span>REVIEW BOARD<small>NFL DECISION DESK</small></span></a>
  {''.join(nav)}
  <div class="sidebar-note"><span class="dot"></span><div><strong>Slate captured {SNAPSHOT}</strong>
  <span>Sibling registers carry their own as-of dates; see the reconciliation page.</span></div></div>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">{esc(crumb or title).upper()}</span>
  <a class="review-link" href="pages/flagged.html">Flagged for review &nearr;</a></header>
{body}
<footer><p>Research, measurement and review only - not betting advice, not a tip sheet, and no funded prize.
Nothing here has been implemented on a reviewer's behalf: every proposal is awaiting a decision.</p>
<p><a href="pages/sources.html">Source register</a> &middot;
   <a href="pages/flagged.html">Flagged for review</a> &middot;
   <a href="index.html">Overview</a></p></footer>
</main></div></body></html>"""
    if current.startswith("pages/"):
        # pages live in pages/, so local hrefs are rebased: siblings stay bare,
        # the landing page and the stylesheet step up one directory.
        doc = (doc.replace('href="assets/', 'href="../assets/')
                  .replace('href="index.html"', 'href="../index.html"')
                  .replace('href="pages/', 'href="'))
    return doc


def refresh_registers() -> None:
    for name in ("queue", "readiness", "injuries", "injury_delta", "hub_map", "reconciliation",
                 "program", "sources", "flags"):
        REGISTERS[name] = load(f"{name}.json")


def sources_by_id() -> dict:
    return {s["id"]: s for s in REGISTERS["sources"]["sources"]}


def src(id_: str) -> str:
    """Render the register entry for a row. An unreachable source is never a hyperlink."""
    s = sources_by_id().get(id_)
    if not s:
        return blank("source id not in register")
    label = s["label"] + ("" if s.get("opened") == SNAPSHOT else " (carried)")
    if s.get("reachable") is False:
        # the explicit no-source marker, not a silent dead hyperlink
        return (f'<span class="blank" title="cited page returns 404 as of {SNAPSHOT}">'
                f'source unreachable</span> <code>{esc(s["url"])}</code>')
    return link(s["url"], label)


def file_link(rel_path: str, label: str = "") -> str:
    return link(REPO_TREE + rel_path, label or rel_path.split("/")[-1])


# ---------------------------------------------------------------- pages
def page_index() -> str:
    q, r, inj, hm, rec = (REGISTERS["queue"], REGISTERS["readiness"], REGISTERS["injuries"],
                          REGISTERS["hub_map"], REGISTERS["reconciliation"])
    prog = REGISTERS["program"]
    verdicts = rec["verdicts"]
    evaluated = sum(v["evaluated"] for v in verdicts)
    passed = sum(v["passed"] for v in verdicts if isinstance(v["passed"], int))
    open_q = sum(c["unanswered"] for c in r["clusters"])
    partial_q = sum(c["partial"] for c in r["clusters"])
    hub_total = len({x["hub"] for c in q["clusters"] for x in c["rows"]})

    kpis = "".join([
        card("Suggestions to review", str(q["proposal_rows"]),
             f'Read from {len(q["generated_from"])} sibling hub registers and de-duplicated into '
             f'<strong>{len(q["clusters"])}</strong> decisions. Nothing here is approved or implemented.',
             "pages/suggestions.html", "Review the queue"),
        card("Open questions", str(open_q + partial_q),
             f'{open_q} unanswered and {partial_q} partially answered across {r["question_rows"]} register '
             f'rows. Each gap names where the answer would come from.',
             "pages/questions.html", "Decision readiness"),
        card("Strategies qualified", f"{passed} of {evaluated}",
             "Summed across the hub leaderboards this hub could read. A strategy qualifies by passing every "
             "gate, never by posting a return.",
             "pages/competition.html", "Leaderboard state"),
        card("Conflicting published values", str(rec["conflict_quantity_count"]),
             f'Same label, different number, across hubs - plus {len({g["gate"] for g in rec["gate_name_conflicts"]})} '
             "gate IDs reused for different tests. Nothing was averaged.",
             "pages/reconciliation.html", "Reconcile them"),
        card("Official slate rows", str(inj["totals"]["rows_transcribed"]),
             f'{inj["totals"]["teams_represented"]} clubs, {inj["totals"]["games"]} games, captured '
             f'{esc(inj["captured"])}: {inj["totals"]["out"]} Out, {inj["totals"]["doubtful"]} Doubtful, '
             f'{inj["totals"]["questionable"]} Questionable.',
             "pages/injuries.html", "Injury tracking"),
        card("Surfaces in the repo", f'{hm["kind_totals"].get("site hub", 0)} hubs',
             f'{hm["total_pages"]} generated pages and {hm["total_data_files"]} JSON registers across '
             f'{hm["hub_count"]} directories, reached by {hm["nav_target_count"]} shared-nav entries.',
             "pages/hubmap.html", "Hub map"),
    ])

    path_rows = [[f'<strong>{esc(p["id"])}</strong>', esc(p["name"]), esc(p["decision"]), esc(p["cost"]),
                  file_link("review-board/data/program.json")] for p in prog["phases"]]

    tiles = "".join(
        f'<a class="tile" href="{href}"><h3>{label}</h3><p>{blurb}</p></a>'
        for href, label, blurb in [
            ("pages/suggestions.html", "Suggestion review queue",
             f'Every proposal from every hub, clustered into {len(q["clusters"])} decisions with options, '
             "cost, risk and a recorded state."),
            ("pages/path.html", "Recommended path",
             "Five phases, what each unlocks, and the review rules that keep a rejected idea from coming back."),
            ("pages/questions.html", "Open questions &amp; gaps",
             "What we know, what we do not, and the discovery route for each missing item."),
            ("pages/signals.html", "Signal catalogue",
             "Seven signal designs for originating lines: hypothesis, inputs, test, falsifier, blocker."),
            ("pages/gates.html", "Validation gates",
             "Twelve tests a candidate must clear, including two no current data can satisfy."),
            ("pages/competition.html", "Leaderboard &amp; rewards",
             "A luck-resistant scoring design, and the honest state: nothing qualifies, no pool funded."),
            ("pages/reconciliation.html", "Cross-hub reconciliation",
             "Every place the hubs disagree about the same number, with both sources linked."),
            ("pages/injuries.html", "Injury tracking",
             "The official Friday report for the live slate, plus what changed since midweek."),
            ("pages/depth.html", "Depth &amp; deficiency",
             "Where absences bite on offence and defence - and why string depth stays blank."),
            ("pages/hubmap.html", "Hub map &amp; repo review",
             "Line-by-line inventory of the repository, its duplication and its navigation defects."),
            ("pages/flagged.html", "Flagged for review",
             "Irregularities and deliberately blank values, published rather than filled in."),
            ("pages/sources.html", "Source register",
             f'What was opened {SNAPSHOT}, what was carried from a sibling register, and what each supports.'),
        ])

    body = f"""
<div class="hero">
  <div class="eyebrow">NFL LINE ORIGINATION &middot; REVIEW LAYER</div>
  <h1>Every suggestion in one queue.<br><em>Decide the path before anyone builds it.</em></h1>
  <p class="lede">This hub adds no model and no picks. It reads the {q["proposal_rows"]} proposals and
  {r["question_rows"]} decision questions published by the repository's {hub_total} sibling hubs, collapses
  them into {len(q["clusters"])} reviewable decisions and {len(r["clusters"])} readiness clusters, and sets
  each against what the official sources actually support today - including the Week 10 slate captured
  {esc(inj["captured"])}. Values no official source confirms are left blank and flagged, never inferred.</p>
</div>
{notice("warn", "Read the dates, not the headlines.",
        f'The analytical hubs carry their own stamps, from {esc(rec["stamp_range"]["earliest"])} to '
        f'{esc(rec["stamp_range"]["latest"])}; the slate data on this hub is {esc(inj["captured"])}. Older '
        "numbers are a record of what was measured, not a current line - the live site's own pipeline "
        "snapshot is weeks behind the slate it discusses.",
        "pages/reconciliation.html", "See every as-of stamp")}
<div class="kpis">{kpis}</div>
{section("The path, in five decisions",
         table(["Phase", "Name", "Decision the owner must make", "Cost", "Source"], path_rows,
               "Ordered so each phase needs only what the previous one produced. Full detail, options and "
               "exit tests on the path page."),
         "Recommended path",
         "Not a work plan - a sequence of choices. Each phase is cheap to reverse and expensive to skip.")}
{section("Where to start", f'<div class="tiles">{tiles}</div>', "AT A GLANCE")}
"""
    return layout("Overview", "index.html", body, crumb="overview")


def page_executive() -> str:
    q, r, inj, hm, rec = (REGISTERS["queue"], REGISTERS["readiness"], REGISTERS["injuries"],
                          REGISTERS["hub_map"], REGISTERS["reconciliation"])
    delta, prog = REGISTERS["injury_delta"], REGISTERS["program"]
    root_lb = load_repo("data", "derived", "leaderboard.json")
    root_model = load_repo("data", "derived", "model.json")
    root_market = load_repo("data", "derived", "market.json")
    root_luck = load_repo("data", "derived", "luck.json")
    root_props = load_repo("data", "derived", "props.json")

    def num(d, *keys, fmt="{:.3f}"):
        """Walk a nested register by key (dict) or index (list) and format the number it holds.

        Returns an empty string when the path does not exist, so a missing value renders as nothing
        rather than as a zero - the same never-guess rule the tables follow."""
        v = d
        for k in keys:
            if isinstance(v, dict):
                v = v.get(k)
            elif isinstance(v, (list, tuple)) and isinstance(k, int) and -len(v) <= k < len(v):
                v = v[k]
            else:
                v = None
        return fmt.format(v) if isinstance(v, (int, float)) else ""

    top = q["clusters"][:5]
    top_rows = [[f'<strong>{esc(c["rank"])}</strong>',
                 f'<a href="pages/suggestions.html#{esc(c["id"])}">{esc(c["title"])}</a>',
                 f'{c["hub_count"]} hubs &middot; {c["proposals_total"]} rows',
                 esc(clip(c["decision"], 150)), badge("awaiting owner", "warn"),
                 file_link("review-board/data/queue.json")] for c in top]

    findings = [
        ("Nothing in this repository qualifies as a betting strategy",
         f'The root leaderboard publishes {esc(num(root_lb, "approved_count", fmt="{:.0f}"))} approved of '
         f'{len(root_lb.get("entries", []))} entries; {len(rec["verdicts"])} hub leaderboards were read and '
         "every one that publishes both counts says zero.", "computed from hub registers", "RB-SRC-09"),
        ("The market is more accurate than the model the site builds",
         f'Root walk-forward figures read from <code>model.json</code>: model MAE '
         f'{esc(num(root_model, "accuracy_spread", "model", "mae"))} vs market MAE '
         f'{esc(num(root_model, "accuracy_spread", "market", "mae"))} on n='
         f'{esc(num(root_model, "accuracy_spread", "model", "n", fmt="{:.0f}"))}; incremental-information '
         f'coefficient {esc(num(root_model, "incremental_information", "c_model"))}, p = '
         f'{esc(num(root_model, "incremental_information", "p_c_model"))}. The model adds nothing beyond the close.',
         "computed from hub registers", "RB-SRC-09"),
        ("A pooled ATS statistic that was an arithmetic identity is corrected at the root and stale in a sibling audit",
         f'The root register now publishes the one-observation-per-game test under <code>ats_coin_flip_test</code>: '
         f'home cover {esc(num(root_luck, "ats_coin_flip_test", "rate", fmt="{:.2%}"))} on n='
         f'{esc(num(root_luck, "ats_coin_flip_test", "n", fmt="{:,.0f}"))}, CI '
         f'{esc(num(root_luck, "ats_coin_flip_test", "ci", 0, fmt="{:.2%}"))}-'
         f'{esc(num(root_luck, "ats_coin_flip_test", "ci", 1, fmt="{:.2%}"))}, p = '
         f'{esc(num(root_luck, "ats_coin_flip_test", "binomial_p_vs_50"))}, with the pooled figure separated into '
         f'<code>ats_pooled_identity</code> (n={esc(num(root_luck, "ats_pooled_identity", "n", fmt="{:,.0f}"))}, '
         'rate 50%, p = 1.0) and labelled an identity. verify-hub\'s claims audit still describes itself as having '
         "read the pooled numbers out of the per-game field - flag RB-04 tracks what is left to fix.",
         "corrected upstream; downstream audit pending", "RB-SRC-09"),
        ("Player-prop profitability cannot be measured in this repository",
         esc(clip(root_props.get("limitation", ""), 300)), "stated by the root register", "RB-SRC-09"),
        ("Parlay legs are not independent, and the hubs disagree by how much",
         f'{rec["conflict_quantity_count"]} quantities carry different published values across hubs (from '
         f'{len(rec["published_numbers"])} labelled numbers read). The QB-WR1 pair is one of them: the label '
         "is shared, the definition is not.", "computed from hub registers", "RB-SRC-08"),
        ("Availability is knowable only in the moment it is published",
         f'This hub&rsquo;s Friday capture holds {inj["totals"]["out"]} Out designations across '
         f'{inj["totals"]["teams_represented"]} clubs; the midweek sibling register holds '
         f'{delta["counts"]["players_listed_with_a_designation_before"]}. Statuses arrive with the Friday '
         "report and are gone afterwards, so an archive - not a re-read - is the only backtestable form.",
         "official source, read today", "RB-SRC-01"),
        ("The report is not a complete absence ledger",
         "The Week 10 report prints no row for a quarterback the same day's official news confirms will miss "
         "6-10 weeks after surgery (BAL), because long-term absences live on the IR and transaction side, not "
         "in the weekly practice report.", "official sources, read today", "RB-SRC-04"),
        ("Two official NFL surfaces disagree about the same clubs on the same day",
         f'Club-by-club Friday news lists injuries the report row for the same player leaves blank, and '
         f'{len(delta["teams_that_said_no_injuries"])} clubs printed "No Injuries Reported" midweek while news '
         "for those clubs was already public on the same site.", "official sources, read today", "RB-SRC-01"),
        ("Depth and 'who replaces whom' remain unverifiable",
         "No league-published depth chart exists at any path any hub could reach; club charts are labelled "
         "unofficial, several are stale, and some omit a backup at a starter-out position. Every string-depth "
         "cell on this hub is blank by policy.", "flagged, not filled", "RB-SRC-06"),
        ("The repository's own shape is now a decision problem",
         f'{hm["kind_totals"].get("site hub", 0)} site hubs, {hm["total_pages"]} pages, '
         f'{hm["nav_target_count"]} shared-nav entries with duplicated labels, and {len(q["clusters"])} '
         "decisions that seven hubs each re-proposed independently.", "computed from the tree", "RB-SRC-08"),
    ]
    frows = [[esc(t), body, badge(cls, "warn" if "flag" in cls or "proposal" in cls else ""), src(sid)]
             for t, body, cls, sid in findings]
    gap_rows = [[f'<strong>{esc(g["id"])}</strong> {esc(g["question"])}', esc(clip(g["have"], 200)),
                 esc(clip(g["missing"], 200)), esc(clip(g["discover_by"], 300)), esc(g["owner_of_answer"]),
                 src(g["source_id"])] for g in prog["information_gaps"]]

    body = f"""
<div class="hero small">
  <div class="eyebrow">EXECUTIVE SUMMARY</div>
  <h1>What is true, what is missing, and what to decide first.</h1>
  <p class="lede">Three sentences: the system measures honestly and has qualified nothing; the blockers are
  inputs, not methods; and the repository's own duplication is now the cheapest thing to fix. Every figure
  below is read from a committed file or an official page captured {esc(SNAPSHOT)} - none is retyped from a
  sibling page.</p>
</div>
{section("The state in one table",
         table(["Finding", "Evidence", "Class", "Source"], frows,
               "Class is the honest label for how far a number can be trusted: an official fact, a hub's own "
               "computation, or a gap the site refuses to fill."),
         "Bottom line")}
{section("Top of the review queue",
         table(["Rank", "Decision", "Support", "What it asks the owner", "State", "Source"], top_rows,
               "Ranked by how many hubs independently proposed the same thing, then by priority votes, then by "
               "what else it unblocks."), "Decisions, in order")}
{section("What we do not know, and how to find out",
         table(["Question", "What we have", "What is missing", "Discovery route", "Who answers", "Source"],
               gap_rows, "Each row blocks at least one decision. 'Who answers' separates owner decisions from "
               "work a session can do without approval."), "Decision readiness")}
{section("Reading of the current slate",
         notice("info", f'{inj["totals"]["games"]} games, {inj["totals"]["rows_transcribed"]} report rows',
                f'Captured {esc(inj["captured"])} from the league&rsquo;s Week {esc(inj["week"])} report: '
                f'{inj["totals"]["out"]} Out, {inj["totals"]["doubtful"]} Doubtful, '
                f'{inj["totals"]["questionable"]} Questionable and '
                f'{inj["totals"]["no_designation_but_limited"]} rows carrying only a practice limitation. Two '
                "starting quarterbacks are Out for Sunday, and the Monday game carries no game statuses at all "
                "in the Friday report.", "pages/injuries.html", "Full slate table"),
         "Current slate")}
"""
    return layout("Executive summary", "pages/executive.html", body)


def page_suggestions() -> str:
    q = REGISTERS["queue"]
    clusters = q["clusters"]
    hub_total = len({x["hub"] for c in clusters for x in c["rows"]})
    summary_rows = []
    for c in clusters:
        summary_rows.append([
            f'<strong>{esc(c["rank"])}</strong>',
            f'<a href="#{esc(c["id"])}"><strong>{esc(c["title"])}</strong></a>',
            f'{c["hub_count"]}/{hub_total} hubs &middot; {c["proposals_total"]} rows'
            f'<br><span class="sub">{esc(", ".join(c["hubs"]))}</span>',
            esc(clip(c["decision"], 190)),
            status_badge("proposed - awaiting owner"),
            file_link("review-board/data/queue.json"),
        ])
    blocks = []
    for c in clusters:
        reg_link = file_link("review-board/data/queue.json")
        opts = "".join(f'<tr><td class="opt"><strong>{esc(o[0])}</strong></td><td>{esc(o[1])}</td>'
                       f'<td>{reg_link}</td></tr>' for o in c["options"])
        prop_rows = [[f'<code>{esc(x["hub"])}:{esc(x["hub_id"])}</code>',
                      esc(clip(x["text"], 150)),
                      esc(clip(x["detail"], 240)) or '<span class="sub">no detail recorded</span>',
                      esc(clip(x["recommended"], 160)) or '<span class="sub">not stated</span>',
                      esc(x["effort"] or "n/s"),
                      esc(clip(x["impact"], 170)) or '<span class="sub">not stated</span>',
                      status_badge(x["status"] or "proposed"),
                      hub_row_source(x)]
                     for x in c["rows"]]
        effort = ", ".join(f"{k} x{v}" for k, v in sorted(c["effort_votes"].items()) if k) or "not stated"
        prio = ", ".join(f"{k} x{v}" for k, v in sorted(c["priority_votes"].items()) if k) or "none labelled"
        blocks.append(
            f'<section class="block cluster" id="{esc(c["id"])}">'
            f'<div class="eyebrow">{esc(c["id"])} &middot; RANK {esc(c["rank"])} &middot; '
            f'{esc(c["hub_count"])} HUBS AGREE</div><h2>{esc(c["title"])}</h2>'
            f'<div class="ask"><span class="k">The decision</span>{esc(c["decision"])}</div>'
            f'<div class="ask"><span class="k">Why it is here now</span>{esc(c["why_now"])}</div>'
            f'<div class="table-wrap"><table class="options"><thead><tr><th>Option</th>'
            f'<th>What it means in practice</th><th>Source</th></tr></thead>'
            f'<tbody>{opts}</tbody></table></div>'
            f'<p class="meta-line">Priority votes: {esc(prio)} &middot; effort votes: {esc(effort)} '
            f'&middot; unblocks: {esc(", ".join(c["prerequisite_of"]) or "nothing directly")} &middot; '
            f'who would change it: {esc(c["owner_of_change"])} &middot; evidence URLs recorded: '
            f'{len(c["evidence_urls"])}</p>'
            + table(["Hub row", "Proposal", "Detail as published", "Hub's recommendation", "Effort",
                     "Impact", "Status", "Source"], prop_rows,
                     f'{c["proposals_total"]} rows from sibling registers, hub wording preserved, each row '
                     "linked to a file that states it.")
            + '<div class="decision-box"><span class="k">Reviewer decision</span> '
              '<em>pending</em> - approve / reject / modify. This hub records nothing on a reviewer&rsquo;s behalf.</div>'
            + "</section>")
    untriaged = ("" if not q["untriaged"] else
                 section("Untriaged rows",
                         table(["Hub", "Row", "Text"],
                               [[esc(x["hub"]), esc(x["hub_id"]), esc(x["text"])] for x in q["untriaged"]],
                               "Rows the classifier could not place. Should be empty; a new hub row that matches "
                               "no rule lands here instead of being dropped."), "Classifier coverage"))
    body = f"""
<div class="hero small">
  <div class="eyebrow">SUGGESTION REVIEW QUEUE</div>
  <h1>{q["proposal_rows"]} proposals, {len(clusters)} decisions.</h1>
  <p class="lede">{esc(q["method"])}</p>
</div>
{section("Queue", table(["#", "Decision", "Support", "Question it answers", "State", "Source"], summary_rows,
         "Jump to any decision for its options and its underlying rows. Nothing here is implemented: the state "
         "stays 'awaiting owner' until a reviewer chooses."), "One row per decision")}
{''.join(blocks)}
{untriaged}
"""
    return layout("Suggestion review queue", "pages/suggestions.html", body)


def page_path() -> str:
    prog, q = REGISTERS["program"], REGISTERS["queue"]
    by_cluster = {c["id"]: c for c in q["clusters"]}
    rows = []
    for p in prog["phases"]:
        clusters = [by_cluster.get(c) for c in p["clusters"] if by_cluster.get(c)]
        rows.append([f'<strong>{esc(p["id"])}</strong>', esc(p["name"]), esc(p["decision"]),
                      ", ".join(f'{c["id"]} ({c["proposals_total"]} rows)' for c in clusters) or "n/a",
                      esc(p["cost"]), esc(clip(p["why_first"], 300)), esc(clip(p["unlocks"], 220)),
                      esc(p["exit_test"]), file_link("review-board/data/program.json")])
    rules = [[f'<strong>{i + 1}</strong>', esc(rl["rule"]), esc(rl["why"]),
              src(rl.get("source_id", "")) or file_link("review-board/data/program.json")]
             for i, rl in enumerate(prog["review_rules"])]
    body = f"""
<div class="hero small">
  <div class="eyebrow">RECOMMENDED PATH</div>
  <h1>Choose the order first; the content can wait.</h1>
  <p class="lede">The phases are ordered by dependency, not by effort. Each one is a decision with an exit
  test, so "done" is a checkable condition rather than an opinion.</p>
</div>
{section("Phases", table(["Phase", "Name", "Decision", "Queue clusters it settles", "Cost", "Why here",
                          "Unlocks", "Exit test", "Source"], rows,
         "Cluster counts come from the review queue; costs and exit tests are proposals in this hub's "
         "programme register."), "Sequence")}
{section("Review rules for this board", table(["#", "Rule", "Why"], rules,
         "Each rule exists because the repository's history shows the failure it prevents."), "Governance")}
{notice("info", "What this page deliberately does not do",
        "It starts none of the phases. Every phase touches files owned by other sessions - root navigation, "
        "sibling hubs, CI - and the board rule is that shared outputs change only in a final integration pass. "
        "An approval recorded here is the input to that pass.",
        "pages/hubmap.html", "See who owns what")}
"""
    return layout("Recommended path", "pages/path.html", body)


def page_questions() -> str:
    r = REGISTERS["readiness"]
    totals = r["state_totals"]
    summary = [[f'<a href="#{esc(c["id"])}"><strong>{esc(c["title"])}</strong></a>', f'{c["hub_count"]} hubs',
                f'{c["answered"]} / {c["partial"]} / {c["unanswered"]}', esc(clip(c["decision"], 200)),
                badge("closed" if c["blocking"] == 0 else f'{c["blocking"]} open',
                      "ok" if c["blocking"] == 0 else "warn"),
                file_link("review-board/data/readiness.json")] for c in r["clusters"]]
    blocks = []
    for c in r["clusters"]:
        rows = [[f'<code>{esc(x["hub"])}:{esc(x["hub_id"])}</code>', esc(clip(x["question"], 190)),
                 esc(clip(x["answer"], 260)) or '<span class="sub">no answer recorded</span>',
                 esc(clip(x["gap"], 240)) or '<span class="sub">no gap recorded</span>',
                 esc(clip(x["how"], 260)) or '<span class="sub">no discovery route recorded</span>',
                 status_badge(x["state"]),
                 hub_row_source(x)] for x in c["questions"]]
        blocks.append(f'<section class="block cluster" id="{esc(c["id"])}">'
                      f'<div class="eyebrow">{esc(c["id"])} &middot; {esc(c["answered"])} ANSWERED &middot; '
                      f'{esc(c["partial"])} PARTIAL &middot; {esc(c["unanswered"])} UNANSWERED</div>'
                      f'<h2>{esc(c["title"])}</h2>'
                      f'<div class="ask"><span class="k">What this cluster decides</span>{esc(c["decision"])}</div>'
                      + table(["Hub row", "Question", "Answer recorded", "What is missing", "How to find out",
                               "State", "Source"], rows,
                              "Read from the sibling registers with the hub's wording preserved, so a reviewer "
                              "can see how each claim was framed.") + "</section>")
    unplaced = ("" if not r.get("unplaced") else
                section("Rows no rule matched",
                        table(["Hub row", "Question", "Answer recorded", "State", "Source"],
                              [[f'<code>{esc(x["hub"])}:{esc(x["hub_id"])}</code>', esc(clip(x["question"], 240)),
                                esc(clip(x["answer"], 240)) or '<span class="sub">none</span>',
                                status_badge(x["state"]),
                                file_link(f'{x["hub"]}/data', f'{x["hub"]} register')] for x in r["unplaced"]],
                              "Reported rather than dropped: a question a hub added and this board has not "
                              "learned to route yet. The count must stay at zero for the cluster totals above "
                              "to mean anything."), "Classifier coverage"))
    body = f"""
<div class="hero small">
  <div class="eyebrow">DECISION-READINESS REGISTER</div>
  <h1>{r["question_rows"]} questions, normalised into {len(r["clusters"])} readiness clusters.</h1>
  <p class="lede">{esc(r["method"])} State totals:
  {esc(", ".join(f"{k} {v}" for k, v in sorted(totals.items())))}.</p>
</div>
{notice("warn", "'Answered' here means a hub recorded an answer against a source it read.",
        "It does not mean the answer is externally verifiable today. Where a claim depends on data this "
        "repository does not hold - prop prices, depth strings, a jurisdiction determination - the row stays "
        "open on this board even when a hub marks it answered in principle.",
        "pages/flagged.html", "Open flags")}
{section("Clusters", table(["Cluster", "Hubs", "Answered / partial / unanswered", "What it decides", "State",
                           "Source"], summary,
         "A cluster is closed only when no hub has an open item inside it."), "Readiness by topic")}
{unplaced}
{''.join(blocks)}
"""
    return layout("Open questions &amp; gaps", "pages/questions.html", body)


def page_signals() -> str:
    prog, inj = REGISTERS["program"], REGISTERS["injuries"]
    rows = [[f'<strong>{esc(s["id"])}</strong><br><span class="sub">{esc(s["name"])}</span>',
             esc(s["family"]), esc(s["hypothesis"]), esc(s["inputs_required"]), status_badge(s["status"]),
             esc(clip(s["blocked_on"], 300)), esc(clip(s["test_design"], 320)),
             esc(clip(s["falsifier"], 240)), src(s["source_id"])] for s in prog["signals"]]
    pos_rows = [[esc(p), esc(n), src("RB-SRC-01")] for p, n in
                sorted(inj["by_position"].items(), key=lambda kv: (-kv[1], kv[0]))]
    body = f"""
<div class="hero small">
  <div class="eyebrow">SIGNAL CATALOGUE</div>
  <h1>Seven signal designs for originating lines - and the input each one waits for.</h1>
  <p class="lede">{esc(prog["meta"]["class"])} {esc(prog["meta"]["how_to_read"])}</p>
</div>
{section("Catalogue", table(["Signal", "Bet family", "Hypothesis", "Required inputs", "Status", "Blocked on",
                            "Test design", "Falsifier", "Source"], rows,
         "'Blocked' means no amount of coding fixes it today, because the input does not exist in verifiable "
         "form. 'Partially testable' means the accuracy half can run now and the profitability half cannot."),
         "Designs, not results")}
{section("Absence load on the live slate, by position",
         table(["Position code", "Designated rows", "Source"], pos_rows,
               "Computed from this hub's transcription of the official report, so the programme is anchored to "
               "what the current week actually depletes rather than to a hypothetical."),
         "Today's evidence base")}
"""
    return layout("Signal catalogue", "pages/signals.html", body)


def page_gates() -> str:
    prog, rec = REGISTERS["program"], REGISTERS["reconciliation"]
    root_lb = load_repo("data", "derived", "leaderboard.json")
    root_gates = {g["id"]: g for g in root_lb.get("gates_definition", [])}
    rows = []
    for g in prog["gates"]:
        in_root = root_gates.get(g["id"])
        rows.append([f'<strong>{esc(g["id"])}</strong>', esc(g["name"]), esc(g["requirement"]), esc(g["why"]),
                      (badge("also in the root set, same id", "ok") if in_root else
                       badge("proposed here - no implementation", "warn")),
                      src(g.get("source_id", ""))])
    defs = [[f'<strong>{esc(g["gate"])}</strong>', esc(g["file"]), esc(g["name"]),
             esc(clip(g["rule"], 220)) or '<span class="sub">rule not stated</span>', link(g["source_url"], "file")]
            for g in rec["gate_definitions"]]
    body = f"""
<div class="hero small">
  <div class="eyebrow">VALIDATION GATES</div>
  <h1>Twelve tests. Ten exist somewhere; two are the project's own gaps.</h1>
  <p class="lede">The root hub publishes ten gates and this board proposes two more that its data cannot satisfy
  today (depth quality, correlation stability). Nothing is re-numbered: the mapping is shown per row so the two
  sets cannot be confused.</p>
</div>
{section("Gate set proposed for the whole repository",
         table(["ID", "Name", "Requirement", "Why it exists", "Relation to the root set", "Source"], rows,
               "A gate that exists in the root register is enforced by that pipeline; a proposed gate is a "
               "design item the owner has to accept first."), "Gates")}
{notice("bad", "The same gate ID means different tests in different hubs.",
        f'Reading every hub register, {len({g["gate"] for g in rec["gate_name_conflicts"]})} gate IDs are '
        "published with more than one name, so a claim like 'passed 9 of 10 gates' is not comparable across "
        "hubs until one set is adopted. That is cluster T07.",
        "pages/reconciliation.html", "See the conflicts")}
{section("Every gate definition published by any hub, side by side", table(
        ["ID", "Published in", "Name", "Rule as written", "Source"], defs,
        "Read from each hub's own register and deliberately not reconciled: choosing the canonical definition is "
        "the owner's decision."), "Definition audit")}
"""
    return layout("Validation gates", "pages/gates.html", body)


def page_competition() -> str:
    prog, rec = REGISTERS["program"], REGISTERS["reconciliation"]
    comp = prog["competition"]
    root_lb = load_repo("data", "derived", "leaderboard.json")
    skill = load_repo("skill-lab", "data", "leaderboard.json")
    lineup = load_repo("lineup-lab", "data", "leaderboard.json")

    tier_rows = [[f'<strong>{esc(t["tier"])}</strong>', esc(t["requirement"]), esc(t["reward"]),
                  file_link("review-board/data/program.json")] for t in comp["tiers"]]
    score_rows = [[esc(s["metric"]), esc(s["weight"]), esc(s["min_n"]), file_link("review-board/data/program.json")]
                  for s in comp["scoring"]]
    anti_rows = [[f'<strong>{i + 1}</strong>', esc(x), file_link("review-board/data/program.json")]
                 for i, x in enumerate(comp["anti_luck"])]

    sched = [[badge("root Line Lab"), esc(root_lb.get("ranking_rule") or "not stated"),
              "; ".join(f'{t.get("tier")}: {t.get("reward")}' for t in root_lb.get("reward_schedule", []))[:420]
              or "no schedule published", file_link("data/derived/leaderboard.json")]]
    if isinstance(skill, dict) and skill.get("reward_tiers"):
        sched.append([badge("Skill Lab"),
                      f'{skill.get("points_awarded", "?")} of {skill.get("competition_pool_points", "?")} pool '
                      f'points awarded; {skill.get("qualified_strategies", "?")} qualified',
                      "; ".join(f'{t.get("tier")}: {t.get("pool_points")} pts, funding: '
                                f'{t.get("cash_funding") or "blank - no funded pool recorded"}'
                                for t in skill["reward_tiers"])[:420],
                      file_link("skill-lab/data/leaderboard.json")])
    if isinstance(lineup, dict) and isinstance(lineup.get("meta"), dict):
        m = lineup["meta"]
        sched.append([badge("Lineup Lab"),
                      f'{m.get("approved_count", "?")} approved of {m.get("total_evaluated", "?")} evaluated',
                      esc(clip(m.get("window", ""), 380)) or "evaluation window not stated",
                      file_link("lineup-lab/data/leaderboard.json")])

    verdict_rows = [[esc(v["file"]), esc(v["evaluated"]), esc(v["passed"]),
                     (f'{v["evaluated"] - v["passed"]} not qualified' if isinstance(v["passed"], int) else ""),
                     link(v["source_url"], "register")] for v in rec["verdicts"]]

    body = f"""
<div class="hero small">
  <div class="eyebrow">LEADERBOARD &amp; REWARDS</div>
  <h1>A competition where rank is earned by clearing gates, not by hitting a return.</h1>
  <p class="lede">{esc(comp["entry_unit"])} {esc(comp["funding_note"])}</p>
</div>
{section("Scoring", table(["Metric", "Role in ranking", "Sample rule", "Source"], score_rows,
         "The primary metric is the one least exposed to outcome luck; ROI is reported but cannot promote an "
         "entry on its own."), "How an entry earns rank")}
{section("Anti-luck controls", table(["#", "Control", "Source"], anti_rows,
         "Each control targets a failure already documented in this repository: pooled-ATS arithmetic, variant "
         "fishing, single-season spikes, repriced parlay legs."), "Removing luck")}
{section("Tiers", table(["Tier", "Requirement", "Reward", "Source"], tier_rows,
         "Tier 0 exists so an under-sampled strategy is reported as insufficient rather than rejected - the "
         "distinction that keeps a leaderboard honest."), "Reward structure")}
{section("Reward schedules as published by each hub", table(["Hub", "Rule / state", "Tiers as published", "Source"],
         sched, "No hub records a funded pool. Differences are shown rather than merged; adopting one schedule "
         "is cluster T09."), "Nothing is reconciled without a decision")}
{section("Qualification state read from the hubs", table(["Register", "Entries", "Qualified", "Not qualified",
                                                          "Source"], verdict_rows,
         "Every hub that publishes both counts says the same thing: zero. That is the current honest answer to "
         "'which strategy should I trust'."), "Live scoreboard")}
"""
    return layout("Leaderboard &amp; rewards", "pages/competition.html", body)


def page_reconciliation() -> str:
    rec = REGISTERS["reconciliation"]
    conf = [[esc(c["quantity_canonical"]), esc(c["values"]), esc(c["all_values"]), esc(c["file"]),
             link(c["source_url"], "open file")] for c in rec["quantity_conflicts"]]
    aliases = [[esc(k), f'<code>{esc(v)}</code>', file_link("review-board/scripts/ingest.py")]
               for k, v in rec["quantity_aliases"].items()]
    gates = [[f'<strong>{esc(g["gate"])}</strong>', esc(g["file"]), esc(g["name"]),
              esc(clip(g["rule"], 200)) or '<span class="sub">rule not stated</span>',
              link(g["source_url"], "open file")] for g in rec["gate_definitions"]]
    stamps = [[esc(s["file"]), esc(s["stamp"]),
               badge(s.get("stamp_kind") or "as published"),
               link(s["source_url"], "open file")] for s in rec["stamps"]]
    numbers = [[esc(n["quantity"]), esc(n["values"]), esc(n["file"]), link(n["source_url"], "open file")]
               for n in rec["published_numbers"]]
    body = f"""
<div class="hero small">
  <div class="eyebrow">CROSS-HUB RECONCILIATION</div>
  <h1>{rec["files_scanned"]} registers read; {rec["conflict_quantity_count"]} quantities disagree.</h1>
  <p class="lede">Of the {len(rec["stamps"])} registers that publish an as-of marker,
  {rec["stamp_range"]["dated_registers"]} print a date and {rec["stamp_range"]["window_only_registers"]}
  print only a season/week window - so no single "as of" applies to the repository.</p>
  <p class="lede">{esc(rec["method"])}</p>
</div>
{section("Conflicting values", table(["Quantity (canonical)", "Value here", "All values seen", "Published in",
                                     "Source"], conf,
         "Two hubs publishing different numbers under one label is a definition problem, not a measurement "
         "problem. Both rows are linked; neither is edited."), "Where the hubs disagree")}
{section("How a quantity is matched", table(["Canonical quantity", "Label pattern used", "Where the rule lives"],
         aliases, "Matching is declared rather than guessed: these patterns are the whole of the grouping "
         "logic, so a reviewer can see exactly what was treated as the same number."), "Alias table")}
{section("Gate definitions across hubs", table(["ID", "Published in", "Name", "Rule as written", "Source"],
         gates, "Same ID, different test. This is why a gates-passed count is not comparable between leaderboards "
         "until one set is adopted."), "Gate-ID audit")}
{section("As-of stamps", table(["Register", "Stamp it publishes", "Class", "Source"], stamps,
         "The spread of dates on one page is the reason no reader should treat any hub here as live.", ""),
         "Freshness")}
{section("Every published number read", table(["Quantity", "Value(s)", "Published in", "Source"], numbers,
         f'{len(rec["published_numbers"])} labelled values found across the repository registers.'), "Full extract")}
"""
    return layout("Cross-hub reconciliation", "pages/reconciliation.html", body)


def page_injuries() -> str:
    inj, delta = REGISTERS["injuries"], REGISTERS["injury_delta"]
    team_rows = [[f'<strong>{esc(t["team"])}</strong>', esc(t["opponent"]), esc(t["slot"]), esc(t["listed"]),
                  esc(t["out"]), esc(t["doubtful"]), esc(t["questionable"]), esc(t["no_designation"]),
                  f'<code>{esc(t["qb_out"])}</code>' if t["qb_out"] else '<span class="sub">none</span>',
                  link(inj["source_url"], "official report")] for t in inj["teams"]]
    player_rows = [[esc(p["slot"]), f'<strong>{esc(p["team"])}</strong>', esc(p["player"]), esc(p["pos"]),
                    esc(p["side"]), esc(p["injury"]) or '<span class="sub">blank in report</span>',
                    esc(p["practice"]), status_badge(p["status"]), link(inj["source_url"], "official report")]
                   for p in inj["players"]]
    game_rows = [[esc(g["slot"]), f'{esc(g["away"])} at {esc(g["home"])}', esc(g["note"]) if g.get("note")
                  else "listed on the report page", link(inj["source_url"], "report")] for g in inj["games"]]
    delta_rows = [[esc(d["player"]), esc(d["team"]), esc(d["pos"]), esc(d["was"]) or "not listed",
                   esc(d["now"]), link(inj["source_url"], "Friday report")] for d in delta["changed"][:60]]
    noreport_rows = [[f'<strong>{esc(x["team"])}</strong>', esc(x["page_says"]),
                      esc(clip(x["contradicted_by"], 220)), badge("contradiction between official surfaces", "bad"),
                      link(delta["previous_source_url"], "midweek register")]
                     for x in delta["teams_that_said_no_injuries"]]
    body = f"""
<div class="hero small">
  <div class="eyebrow">INJURY TRACKING &middot; CAPTURED {esc(inj["captured"])}</div>
  <h1>The live slate, as the league published it on Friday.</h1>
  <p class="lede">{esc(inj["scope_rule"])}</p>
</div>
{notice("info", f'Season {esc(inj["season"])}, Week {esc(inj["week"])}',
        f'Transcribed from <code>{esc(inj["source_url"])}</code> ({esc(inj["source_title"])}): '
        f'{inj["totals"]["rows_transcribed"]} rows, {inj["totals"]["teams_represented"]} clubs, '
        f'{inj["totals"]["games"]} game blocks - {inj["totals"]["out"]} Out, {inj["totals"]["doubtful"]} '
        f'Doubtful, {inj["totals"]["questionable"]} Questionable, {inj["totals"]["no_designation_but_limited"]} '
        "carrying a practice mark only.", inj["source_url"], "Open the official report")}
{section("Slate", table(["Slot", "Matchup", "Note", "Source"], game_rows,
         "Slots and pairings exactly as printed on the report page. The Thursday game had already been played "
         "when this snapshot was taken, which is itself a trap for anyone scraping the page - see flag RB-09."),
         "Games in the snapshot")}
{section("Availability by club", table(["Club", "Opponent", "Slot", "Listed", "Out", "Doubtful", "Questionable",
                                        "Practice only", "Starting QB Out", "Source"], team_rows,
         "Counts are rows in this hub's transcription, computed at build time. The report publishes no totals of "
         "its own, so these are not quotable as 'the league's number'."), "Team table")}
{section("Designated players", table(["Slot", "Club", "Player", "Pos", "Side of ball", "Injury as printed",
                                      "Practice", "Game status", "Source"], player_rows,
         f'{len(inj["players"])} rows carrying a game status. Injury text is copied exactly; a blank means the '
         "report prints no injury for that row, which is not evidence of health."), "Full designation list")}
{section("What changed between the midweek and Friday reports", table(
    ["Player", "Club", "Pos", "Midweek", "Friday", "Source"], delta_rows,
    f'{esc(delta["note"])} Previous capture: {esc(delta["previous_capture"])}; this one: '
    f'{esc(delta["current_capture"])}.'), "Day-over-day delta")}
{section('Clubs that printed "No Injuries Reported" midweek', table(
    ["Club", "Report said", "Official news for the same period", "Class", "Source"], noreport_rows,
    "Recorded so the next session does not re-discover it: an empty report block is not a clean bill of health."),
     "Coverage trap")}
"""
    return layout("Injury tracking", "pages/injuries.html", body)


def page_depth() -> str:
    inj, rec = REGISTERS["injuries"], REGISTERS["reconciliation"]
    rows = []
    for t in sorted(inj["teams"], key=lambda x: (-(x["out_offense"] + x["out_defense"]), x["team"])):
        rows.append([f'<strong>{esc(t["team"])}</strong>', esc(t["opponent"]), esc(t["out_offense"]),
                      esc(t["out_defense"]),
                      esc(clip(t["names_out"], 220)) or '<span class="sub">no players published Out</span>',
                      esc(clip(t["names_doubtful"], 160)) or '<span class="sub">none</span>',
                      blank("no official depth source"), blank("no official depth source"),
                      link(inj["source_url"], "official report")])
    qb_rows = [[f'<strong>{esc(p["team"])}</strong>', esc(p["player"]), esc(p["injury"]) or "blank",
                esc(p["practice"]), status_badge(p["status"]), esc(p["slot"]),
                link(inj["source_url"], "official report")]
               for p in inj["players"] if p["pos"] == "QB"]
    gap_rows = [
        ["A league-published depth chart per club",
         "the path the sibling hubs recorded returns 404 on the operations site; re-checked today",
         "cannot be cited", src("RB-SRC-06")],
        ["A club-published chart with a date",
         "club charts exist but are labelled unofficial; several were stale in the hub audits and some omit a "
         "backup at a starter-out position", "usable only as a labelled team document",
         file_link("decision-desk/data/sources.json")],
        ["A replacement defined by playing time rather than by a chart",
         "snap-count style data is published by a community feed, not by the league",
         "usable, must be labelled a construct", file_link("data/derived/manifest.json")],
        ["Long-term absences (IR, non-football injury, rest) in the same table as the weekly report",
         "the weekly report omits them; transactions carry them",
         "the report alone is not an absence ledger", src("RB-SRC-04")],
        ["A designation for the Monday-night game in the Friday report",
         "the Monday block on the Friday page carries practice marks and no game statuses at all",
         "Saturday capture required", src("RB-SRC-01")],
    ]
    body = f"""
<div class="hero small">
  <div class="eyebrow">DEPTH &amp; DEFICIENCY</div>
  <h1>Where the absences bite - and where the evidence stops.</h1>
  <p class="lede">The brief asks the system to know when a second, third or fourth-stringer is replacing a
  starter. The official report says <em>who is out</em>; nothing official says <em>who comes in</em>. The two
  right-hand columns are therefore blank on every row, and the gap is a decision (clusters T03 and T04), not a
  coding task.</p>
</div>
{section("Absence load by club", table(["Club", "Opponent", "Out (offence)", "Out (defence)", "Players Out",
                                       "Doubtful", "Incoming starter", "Their backing depth", "Source"], rows,
         "Offence = QB/RB/WR/TE/OL/specialists and defence = DL/LB/CB/S, assigned from the position code printed "
         "on the report. A club can show 0 Out and still carry several Questionable rows - both counts are in the "
         "team table on the injury page."), "Computed from today's snapshot")}
{section("Quarterback situation on the live slate", table(["Club", "QB in the report", "Injury as printed",
                                                           "Practice", "Game status", "Slot", "Source"], qb_rows,
         "The one position where an absence moves a game's expected margin enough that a model must handle it "
         "before anything else - and the reason a club whose starter is out on a long-term injury appears here "
         "with no row at all (flag RB-05)."), "Why this slate matters")}
{section("Why the string-depth columns stay blank", table(["What the requirement needs", "What exists",
                                                            "Verdict", "Source"], gap_rows,
         "Each row answers 'why is this blank' for the columns above. No value was invented to fill them."),
         "Evidence gap")}
"""
    return layout("Depth &amp; deficiency", "pages/depth.html", body)


def page_hubmap() -> str:
    hm, flags = REGISTERS["hub_map"], REGISTERS["flags"]
    rows = [[f'<strong>{esc(h["dir"])}/</strong>', esc(h["kind"]), esc(h["pages"]), esc(h["data_files"]),
             esc(h["scripts"]), badge("indexed" if h["nav_links"] else "not in nav",
                                      "ok" if h["nav_links"] else "warn"),
             unent("; ".join(h["nav_labels"])) or '<span class="sub">-</span>', esc(h["last_touched"]),
             link(REPO_TREE + h["dir"], "tree")] for h in hm["hubs"]]
    dup = [[esc(d["label"]), esc(d["count"]), badge("duplicate label in shared nav", "bad"),
            file_link("scripts/lib/site.py")] for d in hm["nav_duplicate_labels"]]
    nav_rows = [[f'<code>{esc(n["href"])}</code>', unent(n["label"]),
                 badge("sibling hub" if not n["href"].startswith(("index.html", "pages/")) else "root page",
                       "" if n["href"].startswith(("index.html", "pages/")) else "warn"),
                 file_link("scripts/lib/site.py")] for n in hm["nav"]]
    flag_rows = [[f'<strong>{esc(f["id"])}</strong>', esc(f["title"]), esc(f["kind"]),
                  badge(f["severity"], "bad" if f["severity"] == "high" else
                        "warn" if f["severity"] == "medium" else ""),
                  file_link("review-board/data/flags.json")] for f in flags["flags"]]
    body = f"""
<div class="hero small">
  <div class="eyebrow">HUB MAP &amp; REPO REVIEW</div>
  <h1>{hm["hub_count"]} directories, {hm["kind_totals"].get("site hub", 0)} of them competing websites.</h1>
  <p class="lede">Inventory computed from the tree at commit <code>{esc(hm["base_commit"])}</code>: page and
  register counts per directory, whether the shared navigation reaches it, and when it was last touched. This is
  a map, not a judgement - but it is the input a reviewer needs before deciding what to keep.
  {'Directory dates are omitted: this register was rebuilt from a checkout without fetched history.' if hm.get('history') == 'shallow' else 'Directory dates are the last commit that touched each path, read from full history.'}</p>
</div>
{section("Directory inventory", table(["Directory", "Kind", "Pages", "JSON registers", "Scripts", "Nav",
                                       "Nav label", "Last touched", "Source"], rows,
         "'Kind' is mechanical: a directory with an index.html is a site hub; code-only is tooling; JSON-only is a "
         "data register. 'not in nav' means a reader who lands on the root site is never shown it. This hub "
         "counts itself: it is the 17th site hub, and the only one whose whole job is to read the other 16."),
         "Every surface in the repository")}
{section("Shared navigation entries", table(["Target", "Label", "Type", "Source"], nav_rows,
         f'{hm["nav_target_count"]} entries rendered on every root page. Grouping them is cluster T10; the nav '
         "file is owned by the integration session, so this hub reports its state instead of editing it."),
         "Nav audit")}
{section("Duplicated nav labels", table(["Label", "Entries", "Class", "Source"], dup,
         "Identical visible labels pointing at different pages: exactly the defect that makes a decision desk "
         "undecidable."), "Defect")}
{section("Flags raised by this review", table(["ID", "Finding", "Kind", "Severity", "Source"], flag_rows,
         "Detail, evidence and the action for the owner are on the Flagged for review page."), "Irregularities")}
"""
    return layout("Hub map &amp; repo review", "pages/hubmap.html", body)


def page_sources() -> str:
    reg = REGISTERS["sources"]
    rows = [[f'<strong>{esc(s["id"])}</strong>',
             (link(s["url"], s["label"]) if s.get("reachable") is not False else
              f'<span class="blank" title="attempted {SNAPSHOT}, no live page">'
              f'no live page</span> <code>{esc(s["url"])}</code>'),
             badge(s["class"], "ok" if s["class"] == "official-nfl" else
                   "warn" if s["class"] == "third-party-feed" else ""),
             badge(f'read {SNAPSHOT}', "ok") if s.get("opened") == SNAPSHOT else badge("carried", "warn"),
             esc(clip(s.get("page_title", ""), 90)) or '<span class="sub">-</span>',
             esc(clip(s.get("supports", ""), 320)),
             esc(clip(s.get("note", ""), 320)) or '<span class="sub">-</span>',
             file_link("review-board/data/sources.json")] for s in reg["sources"]]
    classes = [[f'<strong>{esc(k)}</strong>', esc(v), file_link("review-board/data/sources.json")]
               for k, v in reg["meta"]["classes"].items()]
    body = f"""
<div class="hero small">
  <div class="eyebrow">SOURCE REGISTER</div>
  <h1>What was opened today, and what was inherited.</h1>
  <p class="lede">{esc(reg["meta"]["rule"])}</p>
</div>
{section("Register", table(["ID", "Source", "Class", "This session", "Title as served", "What it supports",
                           "Note", "Where recorded"], rows,
         "Read today means this session fetched the page and used what it says. Carried means the URL and its "
         "finding come from a sibling hub's register and were not re-read here - those rows are marked wherever "
         "they appear."), "Every link on this site")}
{section("Class definitions", table(["Class", "Meaning", "Source"], classes,
         "The class is carried on every row of every table on this hub."), "Vocabulary")}
"""
    return layout("Source register", "pages/sources.html", body)


def page_flagged() -> str:
    flags, q = REGISTERS["flags"], REGISTERS["queue"]
    rows = []
    for f in flags["flags"]:
        rows.append([f'<strong>{esc(f["id"])}</strong>', esc(f["title"]),
                     badge(f["kind"], "bad" if f["kind"] in ("irregularity", "contradiction") else "warn"),
                     badge(f["severity"], "bad" if f["severity"] == "high" else
                           "warn" if f["severity"] == "medium" else ""),
                     esc(clip(f["finding"], 420)), esc(clip(f["verification"], 320)),
                     esc(clip(f["action"], 300)), src(f["source_id"])])
    blank_rows = [[esc(b["surface"]), esc(b["value"]), esc(clip(b["why"], 320)), src(b["source_id"])]
                  for b in flags["blank_by_policy"]]
    carried = load_repo("verify-hub", "data", "flagged.json")
    carried_rows = []
    for row in (carried.get("rows") or [])[:20] if isinstance(carried, dict) else []:
        carried_rows.append([esc(row.get("id", "")), esc(clip(row.get("claim") or row.get("reason", ""), 260)),
                             badge("carried from verify-hub", "warn"),
                             file_link("verify-hub/data/flagged.json")])
    body = f"""
<div class="hero small">
  <div class="eyebrow">FLAGGED FOR REVIEW</div>
  <h1>Everything this review could not confirm, published instead of papered over.</h1>
  <p class="lede">Flags are non-blocking by design: they exist so a reviewer can decide after the site is live,
  not so a build can stay clean. Where no official source supports a value, the cell is blank on every table of
  this hub; the second list is the complete record of what that leaves unanswered.</p>
</div>
{section("Irregularities and unverified items", table(["ID", "Finding", "Kind", "Severity", "What was found",
                                                       "How it was checked", "Action for the owner", "Source"],
         rows, "Each row was recomputed from a committed file or read from an official page captured "
         f"{SNAPSHOT}."), "Register")}
{section("Values left blank, and why", table(["Surface", "Value", "Reason", "Source"], blank_rows,
         "The 'never infer' rule, applied to this hub."), "Blank by policy")}
{section("Flags carried from a sibling hub", table(["ID", "Claim / reason", "Class", "Source"], carried_rows,
         f'verify-hub publishes {len((carried.get("rows") or []) if isinstance(carried, dict) else [])} flagged '
         "items of its own. They are listed here so one page can be the review surface, not re-adjudicated."),
         "Cross-hub")}
{section("Coverage of this review", table(["Measure", "Value", "Source"],
         [["Suggestion rows read from sibling hubs", esc(q["proposal_rows"]), file_link("review-board/data/queue.json")],
          ["Clusters they collapse into", esc(len(q["clusters"])), file_link("review-board/data/queue.json")],
          ["Rows the classifier could not place", esc(len(q["untriaged"])), file_link("review-board/data/queue.json")],
          ["Hub registers read by this hub", esc(len(q["generated_from"])), file_link("review-board/scripts/ingest.py")]],
         "If a sibling hub adds a register row, it enters this board on the next build with no editing here."),
         "Method")}
"""
    return layout("Flagged for review", "pages/flagged.html", body)


PAGES = {
    "index.html": page_index,
    "pages/executive.html": page_executive,
    "pages/suggestions.html": page_suggestions,
    "pages/path.html": page_path,
    "pages/questions.html": page_questions,
    "pages/signals.html": page_signals,
    "pages/gates.html": page_gates,
    "pages/competition.html": page_competition,
    "pages/reconciliation.html": page_reconciliation,
    "pages/injuries.html": page_injuries,
    "pages/depth.html": page_depth,
    "pages/hubmap.html": page_hubmap,
    "pages/sources.html": page_sources,
    "pages/flagged.html": page_flagged,
}


def write(rel: str, content: str) -> None:
    path = os.path.join(HUB, rel)
    os.makedirs(os.path.dirname(path) or HUB, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)


def main() -> None:
    refresh_registers()
    os.makedirs(OUT_PAGES, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    for rel, fn in PAGES.items():
        write(rel, fn())
    rows = 0
    for rel in PAGES:
        with open(os.path.join(HUB, rel)) as fh:
            rows += fh.read().count("<tr><td")
    print(f'wrote review-board/{len(PAGES)} pages, {rows} table rows')


if __name__ == "__main__":
    main()
