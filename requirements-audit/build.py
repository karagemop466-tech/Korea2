#!/usr/bin/env python3
"""Render the requirements-audit site from data/audit.json (stdlib only).

Every table row is read from the JSON. The script refuses to build when a row has no
source link, or when a value is marked verified without a verified source.
Run: python3 requirements-audit/build.py
"""
import html
import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
DATA = json.loads((HERE / "data" / "audit.json").read_text(encoding="utf8"))
SRC = {s["id"]: s for s in DATA["sources"]}


def esc(x):
    return html.escape(str(x), quote=True)


def link(url, text=None):
    text = text or url
    return f'<a href="{esc(url)}" rel="noopener">{esc(text)}</a>'


def badge(status):
    cls = {"Implemented": "ok", "Partial": "warn", "Missing": "bad",
           "Open": "warn", "Decision needed": "info"}.get(status, "info")
    return f'<span class="badge {cls}">{esc(status)}</span>'


def check_rows():
    problems = []
    for r in DATA["requirements"] + DATA["questions"]:
        if not r.get("source_url"):
            problems.append(f"{r['id']}: no source_url")
        if r.get("source_id") not in SRC:
            problems.append(f"{r['id']}: unknown source_id {r.get('source_id')}")
        if r.get("verified_value") is True and not SRC[r["source_id"]]["verified"]:
            problems.append(f"{r['id']}: marked verified without a verified source")
    for s in DATA["sources"]:
        if not s["url"].startswith("https://"):
            problems.append(f"{s['id']}: source url not https")
    return problems


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Requirements audit</title>
<style>
:root{{--ink:#1d2430;--mute:#5b6675;--line:#dfe4ec;--bg:#f6f8fb;--ok:#18794e;--warn:#9a6700;--bad:#b42318;--info:#1f4e9c}}
*{{box-sizing:border-box}} body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}}
header{{background:#fff;border-bottom:1px solid var(--line);padding:14px 22px;display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center}}
header b{{margin-right:auto}} nav a{{color:var(--info);text-decoration:none;margin-right:14px}} nav a.on{{font-weight:600;text-decoration:underline}}
main{{max-width:1180px;margin:0 auto;padding:22px}}
h1{{font-size:24px;margin:4px 0 6px}} h2{{font-size:18px;margin:26px 0 8px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}}
.card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.card .n{{font-size:26px;font-weight:700}} .card .l{{color:var(--mute);font-size:13px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}}
th,td{{text-align:left;vertical-align:top;padding:9px 10px;border-bottom:1px solid var(--line)}}
th{{background:#eef2f7;font-weight:600;font-size:13px}} tr:last-child td{{border-bottom:0}}
td.src a{{word-break:break-all}} .note{{color:var(--mute);font-size:13px;margin-top:4px}}
.badge{{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;font-weight:600;color:#fff;white-space:nowrap}}
.badge.ok{{background:var(--ok)}} .badge.warn{{background:var(--warn)}} .badge.bad{{background:var(--bad)}} .badge.info{{background:var(--info)}}
.flag{{border-left:4px solid var(--warn);background:#fff8e6;padding:10px 14px;border-radius:6px;margin:12px 0}}
.wrap{{overflow-x:auto}} footer{{color:var(--mute);font-size:12px;padding:20px 22px;text-align:center}}
</style></head><body>
<header><b>Requirements audit · Line Lab</b>
<nav>{nav}</nav></header>
<main>{body}</main>
<footer>Built from data/audit.json on {as_of}. Read-only audit; no value is inferred. Source: branch {branch}.</footer>
</body></html>
"""

PAGES = [("index.html", "Overview"), ("requirements.html", "Requirements"),
         ("questions.html", "Questions"), ("suggestions.html", "Suggestions"),
         ("flagged.html", "Flagged & sources")]


def nav(active):
    return "".join(f'<a href="{p}"{" class=on" if p == active else ""}>{esc(label)}</a>'
                   for p, label in PAGES)


def page(fname, title, body):
    text = PAGE.format(title=esc(title), nav=nav(fname), body=body,
                       as_of=esc(DATA["meta"]["as_of"]), branch=esc(DATA["meta"]["built_for_branch"]))
    (HERE / fname).write_text(text, encoding="utf8")


def overview():
    counts = Counter(r["status"] for r in DATA["requirements"])
    cards = "".join(f'<div class="card"><div class="n">{counts.get(k, 0)}</div><div class="l">{k}</div></div>'
                    for k in ("Implemented", "Partial", "Missing"))
    cards += (f'<div class="card"><div class="n">{len(DATA["questions"])}</div><div class="l">open questions</div></div>'
              f'<div class="card"><div class="n">{len(DATA["flagged"])}</div><div class="l">flagged items</div></div>')
    b = f"""<h1>Requirements audit</h1>
<p>A line-by-line map of the brief against what the repository actually contains, with the open questions and the choices
that must be made before anything is built. Nothing here is implemented or approved; every row links its source.</p>
<div class="cards">{cards}</div>
<h2>Executive summary</h2>
<ul>
<li><b>Implemented:</b> per-game fair line, market line and difference columns (R4); depth-of-replacement tracking (R6);
correlations with n published (R7, partly); a suggestions and questions queue (R10).</li>
<li><b>Missing:</b> a price-snapshot store with opening and closing numbers (R1 — openings exist for 2021 only), and a
signal-versus-staking split on the leaderboard (R5).</li>
<li><b>Partial:</b> a results feed (R2, community extract, two seasons described as reconciled), the side→total→moneyline
order (R3, output order only), the demotion gate (R8, rule text with no code), and injury tracking (R9, one week behind
the official page).</li>
<li><b>Unresolved in the data:</b> the results feed ends 2026-10-29; the injury snapshot is Week 9 while the NFL page is
Week 10; correlations are not from official numbers.</li>
<li><b>Nothing here is verified as a betting result.</b> No strategy is live, no price is verified, and no ROI is claimed.</li>
</ul>
<div class="flag"><b>Method.</b> The NFL injury page was read in this session through the page-retrieval tool. Other official links
are recorded in the sources register with a verification flag; unverified ones are not claimed as checked.</div>
<h2>Where to go next</h2>
<ul>
<li><a href="requirements.html">Requirements</a> — each brief item, its status and its evidence.</li>
<li><a href="questions.html">Questions</a> — what is known, what is not, and how to find it.</li>
<li><a href="suggestions.html">Suggestions</a> — choose a path; nothing is implemented until you choose.</li>
<li><a href="flagged.html">Flagged &amp; sources</a> — irregularities and the links for manual review.</li>
</ul>"""
    page("index.html", "Overview", b)


def requirements():
    rows = ""
    for r in DATA["requirements"]:
        rows += f"""<tr><td>{esc(r['id'])}</td><td>{esc(r['requirement'])}</td><td>{badge(r['status'])}</td>
<td>{esc(r['evidence'])}<div class="note">Where: {link(r['where_url'], r['where'])}</div></td>
<td>{esc(r['gap'])}</td>
<td class="src">{link(r['source_url'])}<div class="note">{esc(SRC[r['source_id']]['label'])} · {esc(SRC[r['source_id']]['type'])} · {'verified' if SRC[r['source_id']]['verified'] else 'NOT re-verified this session'}</div><div class="note">{esc(r['source_note'])}</div></td></tr>"""
    b = f"""<h1>Requirements</h1>
<p>Each row is one item from the brief. <b>Status</b> describes what the repository contains today. Values are never inferred:
the verified-value column is blank wherever a source was not checked.</p>
<div class="wrap"><table><thead><tr><th>ID</th><th>Brief item</th><th>Status</th><th>Evidence in the repo</th><th>Gap</th><th>Source (official where available)</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""
    page("requirements.html", "Requirements", b)


def questions():
    rows = ""
    for q in DATA["questions"]:
        rows += f"""<tr><td>{esc(q['id'])}</td><td>{esc(q['question'])}</td><td>{esc(q['known'])}</td>
<td>{esc(q['unknown'])}</td><td>{esc(q['how_to_find'])}</td><td>{esc(q['blocks'])}</td><td>{badge(q['answer_status'])}</td>
<td class="src">{link(q['source_url'])}<div class="note">{esc(SRC[q['source_id']]['label'])}</div></td></tr>"""
    b = f"""<h1>Questions and information gaps</h1>
<p>What must be answered before a decision can reasonably be made. The left column is what we already know; the next is
what we do not. Answers are written in only when a source confirms them.</p>
<div class="wrap"><table><thead><tr><th>ID</th><th>Question</th><th>Known</th><th>Unknown</th><th>How to find out</th><th>Blocks</th><th>Answer</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""
    page("questions.html", "Questions", b)


def suggestions():
    rows = ""
    for s in DATA["suggestions"]:
        opts = "".join(f"<li><b>{esc(o['label'])}</b> — {esc(o['trade_off'])}</li>" for o in s["options"])
        rows += f"""<tr><td>{esc(s['id'])}</td><td>{esc(s['title'])}</td><td><ul>{opts}</ul></td><td>{esc(s['unblocks'])}</td>
<td><span class="badge info">Awaiting choice</span></td></tr>"""
    b = f"""<h1>Suggestions — choose a path</h1>
<p>These are proposals, not changes. Nothing is implemented until a path is chosen. Each option lists its trade-off in
plain terms. The integration session will apply only the paths that are chosen.</p>
<div class="wrap"><table><thead><tr><th>ID</th><th>Item</th><th>Options</th><th>Unblocks</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""
    page("suggestions.html", "Suggestions", b)


def flagged():
    rows = ""
    for f in DATA["flagged"]:
        s = SRC[f["source_id"]]
        rows += f"""<tr><td>{esc(f['id'])}</td><td>{esc(f['item'])}</td><td>{esc(f['detail'])}</td>
<td class="src">{link(s['url'])}<div class="note">{esc(s['label'])} · {'verified' if s['verified'] else 'NOT re-verified this session'}</div></td></tr>"""
    srows = ""
    for s in DATA["sources"]:
        srows += f"""<tr><td>{esc(s['id'])}</td><td>{link(s['url'], s['label'])}</td><td>{esc(s['type'])}</td>
<td>{esc(s['checked'])}</td><td>{esc(s['result'])}</td><td>{badge('Implemented' if s['verified'] else 'Open')} {'verified' if s['verified'] else 'not re-verified'}</td></tr>"""
    b = f"""<h1>Flagged for review &amp; sources</h1>
<div class="flag"><b>For manual review.</b> Irregularities found while building this audit, each linked to its source.
Flagged items do not block anything; they are published so they can be reviewed.</div>
<h2>Flagged items</h2>
<div class="wrap"><table><thead><tr><th>ID</th><th>Item</th><th>Detail</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Source register</h2>
<div class="wrap"><table><thead><tr><th>ID</th><th>Source</th><th>Type</th><th>Checked</th><th>Result</th><th>Status</th></tr></thead><tbody>{srows}</tbody></table></div>"""
    page("flagged.html", "Flagged & sources", b)


def main():
    problems = check_rows()
    if problems:
        print("\n".join(problems))
        return 1
    overview()
    requirements()
    questions()
    suggestions()
    flagged()
    print("built", len(PAGES), "pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
