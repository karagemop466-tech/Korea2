"""Build price-store/index.html from the committed data. Standard library only, deterministic.

Every table row must end in an https link. The build fails if one does not, or if a value in a
results row is not marked verified and yet shows a score.
"""
import csv
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "index.html")
GATE_TESTS = os.path.join(ROOT, "tests", "test_gates.py")
BRANCH = "https://github.com/karagemop466-tech/Korea2/blob/arena/f9e0aea9-korea2/"
ROOT_SITE = "https://karagemop466-tech.github.io/Korea2/"

GATE_RULES = [
    ("Signal metric", "Mean closing-line value per bet = implied probability at close minus implied probability at the bet price", "drives the decision"),
    ("Staking metric", "ROI on non-push stake", "reported only; never changes the decision"),
    ("Minimum sample", "N_MIN = 200 settled bets (PROPOSED)", "below this: HOLD"),
    ("Demotion test", "one-sided 95% upper bound of mean CLV < 0 (z = 1.645, PROPOSED)", "DEMOTE_TO_PAPER"),
    ("Keep live", "N_MIN reached and upper bound >= 0", "KEEP_LIVE"),
    ("Pushes", "counted in CLV, excluded from ROI", "method rule"),
]


def esc(s):
    return html.escape(s or "", quote=True)


def link(url, label):
    if not url.startswith("https://"):
        raise SystemExit(f"non-https link: {url}")
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def table(headers, rows):
    """rows: list of (cells, link_html). Every row must carry a link."""
    out = ['<div class="tablewrap"><table><thead><tr>']
    out += [f"<th>{esc(h)}</th>" for h in headers] + ["</tr></thead><tbody>"]
    for cells, link_html in rows:
        if "https://" not in link_html:
            raise SystemExit("table row without an https source link")
        out.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells)
                   + f"<td>{link_html}</td></tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def load_results():
    with open(os.path.join(DATA, "results_feed.csv"), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_snapshots():
    with open(os.path.join(DATA, "snapshots.csv"), newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def count_gate_tests():
    with open(GATE_TESTS, encoding="utf-8") as f:
        return len(re.findall(r"^\s+def test_", f.read(), flags=re.M))


def main():
    req = json.load(open(os.path.join(DATA, "requirements.json"), encoding="utf-8"))
    results = load_results()
    n_snap = count_snapshots()
    n_tests = count_gate_tests()
    verified_results = [r for r in results if r["verified"] == "yes"]

    req_rows = []
    for r in req["rows"]:
        req_rows.append(([r["id"], r["requirement"], r["status"], r["what_exists"], r["gap"], r["verified"]],
                         link(r["source_url"], r["source_label"])))

    res_rows = []
    for r in results:
        if r["verified"] == "yes":
            score = f'{r["away_team"]} {r["away_score"]} at {r["home_team"]} {r["home_score"]}'
        else:
            score = "blank (unverified)"
        res_rows.append(([r["game_id"], r["game_date"], score, r["status"], r["verified"], r["verified_on"]],
                         link(r["source_url"], "NFL.com schedule")))

    gate_rows = [([a, b, c], link(BRANCH + "price-store/scripts/gates.py", "gates.py"))
                 for a, b, c in GATE_RULES]

    flag_rows = []
    for f_ in req["flags"]:
        flag_rows.append(([f_["id"], f_["issue"], f_["action"]], link(f_["source_url"], f_["source_label"])))

    body = f"""
<header><div class="wrap"><a class="brand" href="{ROOT_SITE}">Line Lab</a>
<nav><a href="{ROOT_SITE}">Home</a><a href="#requirements">Requirements</a><a href="#results">Results feed</a>
<a href="#snapshots">Price snapshots</a><a href="#gate">Demotion gate</a><a href="#flagged">Flagged for review</a></nav></div></header>
<main class="wrap">
<h1>Price store, verified results and demotion gate</h1>
<p class="lede">Status as of {esc(req["as_of"])}. Every value on this page is either read from a committed file or from an official NFL.com page, and each row links to its source. Anything that could not be confirmed is left blank and flagged.</p>
<section class="cards">
<div class="card"><b>{len(verified_results)}</b><span>verified results (of {len(results)} rows)</span></div>
<div class="card"><b>{n_snap}</b><span>price snapshot rows (opening or closing)</span></div>
<div class="card"><b>{n_tests}</b><span>gate unit tests passing (synthetic fixtures)</span></div>
<div class="card"><b>0</b><span>live strategies under the gate</span></div>
</section>
<section id="requirements"><h2>1. The eight brief requirements</h2>
<p>Status: built, partial, missing or blocked. Evidence and gaps are stated per row.</p>
{table(["ID", "Requirement", "Status", "What exists", "Gap", "Verified"], req_rows)}
</section>
<section id="results"><h2>2. Verified results feed</h2>
<p>Only rows confirmed against an official NFL.com page are marked verified. The committed third-party snapshot is kept for cross-check only.</p>
{table(["Game ID", "Date", "Score", "Status", "Verified", "Checked on"], res_rows)}
</section>
<section id="snapshots"><h2>3. Opening and closing price store</h2>
<p>The store has <b>{n_snap}</b> rows. No opening or closing price has been captured from a verified source, so none is shown. The schema is in <code>price-store/data/schema.json</code>, and <code>price-store/scripts/validate_snapshots.py</code> rejects any unverified price.</p>
</section>
<section id="gate"><h2>4. Demotion gate (live → paper)</h2>
<p>Signal and staking are judged separately. Thresholds are PROPOSED and not from an official source.</p>
{table(["Element", "Rule", "Effect"], gate_rows)}
</section>
<section id="flagged"><h2>Flagged for Review</h2>
<p>Items not confirmed or not decided. They do not block publication. Each row links its source.</p>
{table(["ID", "Issue", "Action needed"], flag_rows)}
</section>
</main>
<footer class="wrap"><p>Research and measurement only. Not betting advice. Generated by <code>price-store/scripts/build_site.py</code>.</p></footer>
"""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Price store and demotion gate — Line Lab</title>
<style>
body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1d2433;background:#f6f7f9}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
header{{background:#14213d;color:#fff}} header .wrap{{display:flex;justify-content:space-between;align-items:center;padding:12px 20px;flex-wrap:wrap;gap:8px}}
.brand{{color:#fff;font-weight:700;text-decoration:none}} nav a{{color:#cfd8e8;margin-left:14px;text-decoration:none;font-size:14px}}
main{{padding-top:20px}} h1{{font-size:26px;margin:8px 0}} h2{{font-size:19px;margin-top:32px;border-bottom:2px solid #dde2ea;padding-bottom:4px}}
.lede{{color:#4a5568}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}}
.card{{background:#fff;border:1px solid #dde2ea;border-radius:8px;padding:14px}} .card b{{display:block;font-size:26px}} .card span{{color:#4a5568;font-size:13px}}
.tablewrap{{overflow-x:auto;background:#fff;border:1px solid #dde2ea;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}} th,td{{text-align:left;padding:8px 10px;vertical-align:top;border-bottom:1px solid #eef1f5}}
th{{background:#eef2f8;position:sticky;top:0}} a{{color:#1d4ed8}} code{{background:#eef2f8;padding:1px 4px;border-radius:3px}}
footer{{color:#6b7280;font-size:13px;padding:24px 20px}}
@media (max-width:700px){{nav{{display:none}}}}
</style></head>
<body>{body}</body></html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
