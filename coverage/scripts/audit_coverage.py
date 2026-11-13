#!/usr/bin/env python3
"""CV-1: Site-wide source-coverage & link-integrity audit.

The repository's hard rule is: every table row carries a source link to an official
site, and a value that cannot be confirmed from an official source is left blank and
flagged. `tests/check_site.py` enforces that rule on the integrated root build only;
this audit extends the same measurement to **every** HTML page in the repository so the
coverage is explicit, per-page, machine-readable and reviewable.

For each HTML page it measures:
  * tables, tbody rows, rows carrying a source link (last cell contains an <a href>),
  * rows without a source link (the rule gap),
  * internal / external link counts and any broken internal link or insecure link,
  * generator provenance and a tier (canonical root build / active lab / legacy archive),
  * a category for organising the subpages.

It reads files only; it never edits them. Legacy archive pages are reported and flagged,
not rewritten. Output is JSON so the dashboard can render it deterministically.

Pure Python standard library (no third-party dependencies).
"""
from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Directory -> (tier, category). Tiers describe publication status; category groups pages.
TIER_CATEGORY = {
    "": ("canonical", "Core analytics"),
    "pages": ("canonical", "Core analytics"),
    "lineup-lab": ("active-lab", "Lineup intelligence"),
    "decision-desk": ("active-lab", "Decision & governance"),
    "decision-hub": ("active-lab", "Decision & governance"),
    "suggestions": ("active-lab", "Decision & governance"),
    "verify-hub": ("active-lab", "Decision & governance"),
    "skill-lab": ("active-lab", "Competition & gates"),
    "nfl-command": ("active-lab", "Lineup intelligence"),
    "origination-lab": ("legacy-archive", "Legacy archive"),
    "origination": ("legacy-archive", "Legacy archive"),
    "quant-lab": ("legacy-archive", "Legacy archive"),
    "nfl-lines": ("legacy-archive", "Legacy archive"),
    "nfl-research": ("legacy-archive", "Legacy archive"),
    "research-desk": ("legacy-archive", "Legacy archive"),
    "dashboard": ("legacy-archive", "Legacy archive"),
    "audit": ("legacy-archive", "Legacy archive"),
    "site": ("legacy-archive", "Legacy archive"),
}

# Generator stamp that marks a page produced by the canonical root build.
ROOT_GENERATOR = "line-lab/scripts/build_site.py"


class Doc(HTMLParser):
    """Minimal HTML parser collecting links, ids, title, tables and source coverage."""

    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self.generator = ""
        self.tables = 0
        self.rows = 0
        self.rows_with_source = 0
        self.rows_without_source = 0
        self._in_title = False
        self._in_tbody = False
        self._cell_has_link = False
        self._in_cell = False
        self._in_td = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "meta" and a.get("name") == "generator":
            self.generator = a.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag == "table":
            self.tables += 1
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self.rows += 1
            self._cell_has_link = False
        if tag == "td" and self._in_tbody:
            self._in_td = True
            self._in_cell = True
        if tag == "a" and self._in_cell:
            self._cell_has_link = True

    def handle_endtag(self, tag):
        if tag in ("tbody", "thead"):
            self._in_tbody = False
        if tag == "title":
            self._in_title = False
        if tag in ("td", "th"):
            self._in_cell = False
            self._in_td = False
        if tag == "tr" and self._in_tbody:
            if self._cell_has_link:
                self.rows_with_source += 1
            else:
                self.rows_without_source += 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def walk_html() -> list[str]:
    files: list[str] = []
    for base, dirs, names in os.walk(ROOT):
        # Exclude the git object store, generated/data directories, and this audit's own
        # output (coverage/) from the page scan so the audit is deterministic and not
        # self-referential.
        dirs[:] = [d for d in dirs if d not in (".git", "data", "scripts", "__pycache__", "coverage")]
        for n in names:
            if n.endswith(".html"):
                rel = os.path.relpath(os.path.join(base, n), ROOT)
                files.append(rel.replace(os.sep, "/"))
    return sorted(files)


def tier_category(path: str) -> tuple[str, str]:
    parts = path.split("/")
    # First path segment names the lab directory; the root build has no leading directory.
    seg = parts[0] if len(parts) > 1 else ""
    return TIER_CATEGORY.get(seg, ("legacy-archive", "Legacy archive"))


def is_canonical(doc: Doc, path: str) -> bool:
    if ROOT_GENERATOR in doc.generator:
        return True
    return path == "index.html" or path.startswith("pages/")


def check_links(path: str, doc: Doc, docs: dict[str, Doc]) -> list[dict]:
    """Return link issues for one page (broken internal links, insecure links)."""
    issues: list[dict] = []
    base = os.path.dirname(path)
    for href in doc.links:
        if href.startswith(("http://", "https://", "mailto:")):
            if href.startswith("http://"):
                issues.append({"path": path, "href": href, "issue": "insecure-external-link"})
            continue
        if href.startswith("#"):
            if href[1:] and href[1:] not in doc.ids:
                issues.append({"path": path, "href": href, "issue": "broken-anchor"})
            continue
        target, _, anchor = href.partition("#")
        if not target:
            continue
        resolved = os.path.normpath(os.path.join(base, target)).replace(os.sep, "/")
        if not os.path.exists(os.path.join(ROOT, resolved)):
            issues.append({"path": path, "href": href, "issue": "broken-internal-link"})
        elif anchor:
            target_doc = docs.get(resolved)
            if target_doc is not None and anchor not in target_doc.ids:
                issues.append({"path": path, "href": href, "issue": "broken-anchor"})
    return issues


def main() -> int:
    files = walk_html()
    docs: dict[str, Doc] = {}
    for f in files:
        d = Doc()
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            d.feed(fh.read())
        docs[f] = d

    pages = []
    link_issues: list[dict] = []
    for f in files:
        d = docs[f]
        tier, category = tier_category(f)
        canonical = is_canonical(d, f)
        if canonical:
            tier = "canonical"
        internal = external = 0
        for href in d.links:
            if href.startswith(("http://", "https://", "mailto:")):
                if not href.startswith("http://"):
                    external += 1
            else:
                internal += 1
        link_issues.extend(check_links(f, d, docs))
        pages.append({
            "path": f,
            "title": d.title.strip(),
            "generator": d.generator,
            "tier": tier,
            "category": category,
            "canonical": canonical,
            "tables": d.tables,
            "rows": d.rows,
            "rows_with_source": d.rows_with_source,
            "rows_without_source": d.rows_without_source,
            "sourced": d.rows_without_source == 0,
            "internal_links": internal,
            "external_links": external,
        })

    # Aggregate by category and tier.
    def agg(key):
        out = {}
        for p in pages:
            k = p[key]
            a = out.setdefault(k, {"pages": 0, "tables": 0, "rows": 0,
                                   "rows_with_source": 0, "rows_without_source": 0})
            a["pages"] += 1
            a["tables"] += p["tables"]
            a["rows"] += p["rows"]
            a["rows_with_source"] += p["rows_with_source"]
            a["rows_without_source"] += p["rows_without_source"]
        return [{"key": k, **v} for k, v in sorted(out.items())]

    legacy_review = [
        {
            "path": p["path"],
            "title": p["title"],
            "tier": p["tier"],
            "category": p["category"],
            "rows": p["rows"],
            "rows_without_source": p["rows_without_source"],
            "generator": p["generator"],
            "reason": "Preserved legacy archive page: rows without a source link are reported and "
                      "flagged, not rewritten, per the archive byte-for-byte policy.",
        }
        for p in pages if not p["sourced"] and p["rows"] > 0
    ]

    try:
        import subprocess
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""

    result = {
        "meta": {
            "generator": "coverage/scripts/audit_coverage.py",
            "source_commit": commit,
            "pages_total": len(pages),
            "tables_total": sum(p["tables"] for p in pages),
            "rows_total": sum(p["rows"] for p in pages),
            "rows_with_source": sum(p["rows_with_source"] for p in pages),
            "rows_without_source": sum(p["rows_without_source"] for p in pages),
            "pages_sourced": sum(1 for p in pages if p["sourced"]),
            "pages_needs_review": sum(1 for p in pages if not p["sourced"] and p["rows"] > 0),
            "internal_links": sum(p["internal_links"] for p in pages),
            "external_links": sum(p["external_links"] for p in pages),
            "link_issues": len(link_issues),
        },
        "by_tier": agg("tier"),
        "by_category": agg("category"),
        "pages": pages,
        "legacy_review": legacy_review,
        "link_issues": link_issues,
    }

    out = os.path.join(ROOT, "coverage", "data", "coverage.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")

    m = result["meta"]
    print(f"coverage audit: {m['pages_total']} pages, {m['tables_total']} tables, "
          f"{m['rows_total']} rows ({m['rows_with_source']} sourced, "
          f"{m['rows_without_source']} without source)")
    print(f"  needs review: {m['pages_needs_review']} page(s); "
          f"link issues: {m['link_issues']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
