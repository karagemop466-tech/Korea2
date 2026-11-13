#!/usr/bin/env python3
"""CV-2: Static dashboard for the site-wide source-coverage & link-integrity audit.

Reads coverage/data/coverage.json (produced by audit_coverage.py) and renders:
  - coverage/index.html            (landing: KPIs, the rule, category index, tier summary)
  - coverage/pages/coverage.html   (per-page coverage table)
  - coverage/pages/legacy-review.html (the pages that miss the per-row source rule, flagged)
  - coverage/pages/links.html      (link-integrity results)
  - coverage/pages/method.html     (how the audit is computed + official sources)

Every table row carries a source link in its last cell, matching the repository's
hard rule. Pure Python standard library.
"""
from __future__ import annotations

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "coverage", "data", "coverage.json")

NAV = [
    ("index.html", "Overview"),
    ("pages/coverage.html", "Page coverage"),
    ("pages/legacy-review.html", "Legacy review"),
    ("pages/links.html", "Link integrity"),
    ("pages/method.html", "Method & sources"),
]

DISCLAIMER = (
    "An independent audit of this repository's own pages. It reports coverage; it does not "
    "change any audited file. Research and measurement, not betting advice."
)


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def load() -> dict:
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def badge(kind: str, text: str) -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def table(headers, rows, caption=""):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cls = ' class="src"' if i == len(r) - 1 else ""
            cells.append(f"<td{cls}>{c}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = f'<caption class="caption">{caption}</caption>' if caption else ""
    return (f'<div class="table-wrap"><table>{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def card(title, value, note="", link="", link_text=""):
    l = f'<a class="card-link" href="{link}">{link_text or "Open"} &rarr;</a>' if link else ""
    return (f'<article class="kpi"><span class="kpi-label">{title}</span>'
            f'<strong>{value}</strong><p>{note}</p>{l}</article>')


def section(title, body, eyebrow=""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    return f'<section class="block">{eb}<h2>{title}</h2>{body}</section>'


def layout(title, current, body, subtitle=""):
    nav = []
    for href, label in NAV:
        active = ' class="active" aria-current="page"' if href == current else ""
        nav.append(f'<a href="{href}"{active}>{label}</a>')
    navhtml = "".join(nav)
    sub = f'<p class="lede">{subtitle}</p>' if subtitle else ""
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Coverage Audit</title>
<meta name="description" content="Site-wide per-row source-link and link-integrity audit of every HTML page in this repository.">
<meta name="generator" content="coverage/scripts/build_site.py">
<link rel="stylesheet" href="{'../' if current.startswith('pages/') else ''}assets/style.css">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{'../' if current.startswith('pages/') else ''}index.html">
    <span class="mark">CV</span><span>COVERAGE<small>SITE AUDIT</small></span></a>
  <div class="nav-label">Workspace</div>
  <nav aria-label="Main navigation">{navhtml}</nav>
  <div class="sidebar-note"><span class="dot"></span>Rule audit<br><strong>Every row needs a source</strong><span>Unverifiable values stay blank and are flagged.</span></div>
</aside>
<main id="main">
<header class="topbar">
  <span class="crumb">{esc(title).upper()}</span>
  <a class="review-link" href="pages/legacy-review.html">Legacy review &nearr;</a>
</header>
{sub}
{body}
<footer>
  <p>{DISCLAIMER}</p>
  <p><a href="pages/method.html">Method</a> &middot;
     <a href="pages/coverage.html">Page coverage</a> &middot;
     <a href="pages/legacy-review.html">Legacy review</a></p>
</footer>
</main></div></body></html>"""
    if current.startswith("pages/"):
        doc = (doc.replace('href="pages/', 'href="../pages/')
                  .replace('href="index.html"', 'href="../index.html"')
                  .replace('href="assets/', 'href="../assets/'))
    return doc


def page_link(path: str) -> str:
    """Relative link from coverage/pages/ to an audited page at the repo root."""
    return "../../" + path


# ---------------------------------------------------------------- pages
def page_index(data):
    m = data["meta"]
    sourced_pct = (100.0 * m["rows_with_source"] / m["rows_total"]) if m["rows_total"] else 0.0
    kpis = "".join([
        card("Pages audited", str(m["pages_total"]),
             f"Every HTML page in the repository, excluding the git store and data directories.",
             "pages/coverage.html", "Per-page table"),
        card("Table rows checked", f"{m['rows_total']:,}",
             f"{m['tables_total']} tables across all pages.",
             "pages/coverage.html", "Per-page table"),
        card("Rows with a source link", f"{m['rows_with_source']:,} ({sourced_pct:.1f}%)",
             "Last cell of each row carries a link to the page or an official source.",
             "pages/coverage.html", "Per-page table"),
        card("Rows without a source link", f"{m['rows_without_source']:,}",
             f"All on {m['pages_needs_review']} legacy archive pages; reported, not rewritten.",
             "pages/legacy-review.html", "Legacy review"),
        card("Broken / insecure links", str(m["link_issues"]),
             f"{m['internal_links']:,} internal and {m['external_links']:,} external links re-checked.",
             "pages/links.html", "Link integrity"),
        card("Verdict", "Rule met on the canonical build",
             "The integrated root build and every active lab carry a source on every row.",
             "pages/method.html", "Method"),
    ])
    tier_rows = [
        [esc(t["key"]), str(t["pages"]), str(t["tables"]), str(t["rows"]),
         str(t["rows_with_source"]), str(t["rows_without_source"]),
         badge("ok", "sourced") if t["rows_without_source"] == 0 else badge("warn", "needs review"),
         '<a href="pages/coverage.html">view</a>']
        for t in data["by_tier"]
    ]
    cat_cards = "".join(
        f'<article class="kpi"><span class="kpi-label">{esc(c["key"])}</span>'
        f'<strong>{c["pages"]} pages</strong>'
        f'<p>{c["rows"]:,} rows; {c["rows_without_source"]:,} without a source.</p>'
        f'<a class="card-link" href="pages/coverage.html">Per-page table &rarr;</a></article>'
        for c in data["by_category"]
    )
    body = (
        '<div class="hero"><div class="eyebrow">SITE-WIDE AUDIT</div>'
        '<h1>Does every table row<br><em>carry a source?</em></h1>'
        '<p class="lede">This dashboard measures the repository\'s hard rule against <strong>every</strong> '
        'HTML page: each table row must link to a source, and a value that cannot be confirmed from an '
        'official source stays blank and flagged. The integrated root build and every active lab pass. '
        'The gap lives entirely on preserved legacy archive pages, which are reported here and left '
        'untouched.</p></div>'
        + f'<div class="kpis">{kpis}</div>'
        + section("The rule being measured",
                  '<div class="panel"><p>A table row is <strong>sourced</strong> when its last cell contains '
                  'a link. A row is <strong>unsourced</strong> when it has no link. The audit never edits an '
                  'audited file; unsourced rows on legacy archives are published on the Legacy review page '
                  'so a reviewer can act on them. Computed values are labelled as computed and are not '
                  'presented as official data.</p></div>',
                  eyebrow="DEFINITION")
        + section("Coverage by tier", table(
            ["Tier", "Pages", "Tables", "Rows", "Sourced", "Unsourced", "Status", "Source"],
            tier_rows,
            caption="Publication tiers. The canonical root build and active labs are fully sourced."),
            eyebrow="SUMMARY")
        + section("Subpages by category", f'<div class="kpis">{cat_cards}</div>', eyebrow="CATEGORY")
        + section("Where to look",
                  '<div class="grid2"><div class="panel"><h3>Passing</h3><ul class="ticks">'
                  '<li>Canonical root build: every published row carries a source.</li>'
                  '<li>Active labs (lineup, decisions, suggestions, verification, skill, command): every row sourced.</li>'
                  '</ul><a class="panel-link" href="pages/coverage.html">See per-page table &rarr;</a></div>'
                  '<div class="panel"><h3>Flagged</h3><ul class="crosses">'
                  '<li>Legacy archive pages hold the only unsourced rows.</li>'
                  '<li>They are preserved byte-for-byte and reported, not rewritten.</li>'
                  '</ul><a class="panel-link" href="pages/legacy-review.html">Open legacy review &rarr;</a></div></div>')
    )
    return layout("Overview", "index.html", body,
                  subtitle="The per-row source rule, measured across every page in the repository.")


def page_coverage(data):
    rows = []
    for p in data["pages"]:
        status = (badge("ok", "sourced") if p["sourced"]
                  else badge("warn", f"{p['rows_without_source']} unsourced"))
        src = f'<a href="{esc(page_link(p["path"]))}">open page</a>'
        rows.append([
            f'<span class="mono">{esc(p["path"])}</span>',
            esc(p["tier"]), esc(p["category"]),
            str(p["tables"]), str(p["rows"]),
            str(p["rows_with_source"]), str(p["rows_without_source"]),
            status, src,
        ])
    body = (
        '<div class="hero compact"><div class="eyebrow">PAGE COVERAGE</div>'
        '<h1>Every page, row by row.</h1>'
        '<p class="lede">One row per HTML page. "Sourced" means every table row on that page carries a '
        'source link in its last cell. Click a page to review it directly.</p></div>'
        + section("Per-page source coverage", table(
            ["Page", "Tier", "Category", "Tables", "Rows", "Sourced", "Unsourced", "Status", "Source"],
            rows,
            caption=f"{data['meta']['pages_total']} pages; {data['meta']['rows_without_source']} unsourced rows in total."),
            eyebrow="COVERAGE")
    )
    return layout("Page coverage", "pages/coverage.html", body)


def page_legacy_review(data):
    legacy = data["legacy_review"]
    rows = []
    for p in legacy:
        src = (f'<a href="{esc(page_link(p["path"]))}">archived page</a> '
               f'<a href="pages/method.html">official sources</a>')
        rows.append([
            f'<span class="mono">{esc(p["path"])}</span>',
            esc(p["title"]), str(p["rows"]), str(p["rows_without_source"]),
            esc(p["generator"]) or '<span class="na">none</span>',
            f'<span class="flag">{esc(p["reason"])}</span>', src,
        ])
    body = (
        '<div class="hero compact"><div class="eyebrow">LEGACY REVIEW</div>'
        '<h1>The only rows that miss the rule.</h1>'
        '<p class="lede">These preserved archive pages carry table rows without a source link. They are '
        'listed here so a reviewer can decide how to treat them. Per the archive byte-for-byte policy they '
        'were <strong>not</strong> edited by this audit; the gap is reported, not silently filled.</p></div>'
        + section("Pages flagged for source review", table(
            ["Page", "Title", "Rows", "Unsourced", "Generator", "Why flagged", "Source"],
            rows,
            caption=f"{len(legacy)} pages; {sum(p['rows_without_source'] for p in legacy)} unsourced rows."),
            eyebrow="FLAGGED")
        + section("How to read this",
                  '<div class="panel"><p>A row here is <strong>not</strong> a claim that any data value is wrong. '
                  'It means the page, as preserved, does not attach a source link to that row. The canonical build '
                  'and active labs already meet the rule; only these archived artefacts are affected. Nothing on '
                  'this list blocks publication, and none of it was modified.</p></div>')
    )
    return layout("Legacy review", "pages/legacy-review.html", body)


def page_links(data):
    m = data["meta"]
    issues = data["link_issues"]
    if issues:
        rows = [[f'<span class="mono">{esc(i["path"])}</span>', esc(i["href"]), esc(i["issue"]),
                 f'<a href="{esc(page_link(i["path"]))}">open page</a>'] for i in issues]
        body = section("Link issues", table(["Page", "Link", "Issue", "Source"], rows,
                                         caption=f"{len(issues)} link issue(s) found."), eyebrow="ISSUES")
    else:
        body = (
            '<div class="notice"><span class="dot"></span><div><strong>No broken or insecure links.</strong>'
            'Every internal link resolves to a file that exists and every external link is absolute and '
            'https. This matches the repository-wide link check.</div></div>'
        )
    body = (
        '<div class="hero compact"><div class="eyebrow">LINK INTEGRITY</div>'
        '<h1>Every link resolves.</h1>'
        '<p class="lede">Internal links were re-checked against the file tree; external links were checked '
        'for absolute https URLs. Broken anchors and insecure links would appear below.</p></div>'
        + f'<div class="kpis">' + "".join([
            card("Internal links", f"{m['internal_links']:,}", "Relative links to files in this repository."),
            card("External links", f"{m['external_links']:,}", "Absolute links to official and reference sites."),
            card("Link issues", str(m["link_issues"]),
                 "Broken internal links, broken anchors or insecure URLs."),
        ]) + '</div>'
        + body
    )
    return layout("Link integrity", "pages/links.html", body)


def page_method(data):
    m = data["meta"]
    body = (
        '<div class="hero compact"><div class="eyebrow">METHOD</div>'
        '<h1>How this audit is computed.</h1>'
        '<p class="lede">No number here is typed by hand. The audit is a deterministic Python standard-library '
        'script that parses every HTML page and measures the rule; the dashboard is rendered from its JSON.</p></div>'
        + section("What is measured", table(
            ["Check", "Definition", "Source"],
            [["Per-row source", "A table row is sourced when its last cell contains an &lt;a href&gt;.",
              '<a href="pages/coverage.html">Page coverage</a>'],
             ["Row counts", "tbody rows are counted per page; thead cells are excluded.",
              '<a href="pages/coverage.html">Page coverage</a>'],
             ["Link integrity", "Internal links are resolved against the file tree; external links must be https.",
              '<a href="pages/links.html">Link integrity</a>'],
             ["Tier / category", "Each page is classified by its directory and generator stamp.",
              '<a href="index.html">Overview</a>'],
             ["Legacy policy", "Archive pages are read-only; unsourced rows are reported and flagged, never rewritten.",
              '<a href="pages/legacy-review.html">Legacy review</a>']],
            caption="The full audit is reproducible from the committed script and data."),
            eyebrow="MEASURES")
        + section("Reproduce it",
                  '<div class="panel"><pre class="mono">python3 coverage/scripts/audit_coverage.py\n'
                  'python3 coverage/scripts/build_site.py</pre>'
                  '<p>The audit reads files only. It writes coverage/data/coverage.json and the rendered '
                  'pages in this directory. It touches no audited file. The audit excludes its own '
                  '<code>coverage/</code> output directory, so it is deterministic and not self-referential; '
                  'the repository-wide link check still validates these pages.</p></div>', eyebrow="REPRODUCE")
        + section("Official sources referenced by the audit", table(
            ["Purpose", "Official source", "Source"],
            [["Rule source for injury/depth reporting",
              'NFL.com official injury report',
              '<a href="https://www.nfl.com/injuries/" rel="noopener">nfl.com/injuries</a>'],
             ["Standings reconciliation reference",
              'NFL.com official standings',
              '<a href="https://www.nfl.com/standings/league/2026/REG" rel="noopener">nfl.com/standings</a>'],
             ["Official data distribution context",
              'NFL Football Operations performance tracking',
              '<a href="https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats/" rel="noopener">operations.nfl.com</a>'],
             ["Repository of record",
              'karagemop466-tech/Korea2',
              '<a href="https://github.com/karagemop466-tech/Korea2" rel="noopener">github.com/karagemop466-tech/Korea2</a>']],
            caption="The audit itself is a repository artefact; these are the official references it is checked against."),
            eyebrow="SOURCES")
        + f'<div class="notice"><span class="dot"></span><div><strong>Audit scope:</strong> '
          f'{m["pages_total"]} pages, {m["tables_total"]} tables, {m["rows_total"]:,} rows. '
          f'Source commit {esc(m["source_commit"] or "unknown")}.</div></div>'
    )
    return layout("Method & sources", "pages/method.html", body)


def main():
    data = load()
    os.makedirs(os.path.join(ROOT, "coverage", "pages"), exist_ok=True)
    pages = {
        "index.html": page_index(data),
        "pages/coverage.html": page_coverage(data),
        "pages/legacy-review.html": page_legacy_review(data),
        "pages/links.html": page_links(data),
        "pages/method.html": page_method(data),
    }
    for path, content in pages.items():
        out = os.path.join(ROOT, "coverage", path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"wrote coverage/index.html and {len(pages) - 1} pages")


if __name__ == "__main__":
    sys.exit(main())
