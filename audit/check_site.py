#!/usr/bin/env python3
"""Offline audit of HTML links and allowed source domains.

A recognized domain is a necessary syntax check, not proof that the page is
reachable, a claim is supported, or numerical values have been verified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', 'build', 'dist'}
PUBLISHER_ROOTS = (
    'nfl.com', 'gov', 'gov.uk', 'gov.sg', 'massgaming.com',
    'scikit-learn.org', 'draftkings.com', 'fanduel.com', 'pinnacle.com',
    'kaggle.com', 'ncpgambling.org', 'princeton.edu', 'cornell.edu',
    'docs.github.com',
)
OWN_REPOSITORY_PATH = '/karagemop466-tech/korea2'


def official_source(url: str) -> bool:
    """Accept explicitly recognized primary-publisher hosts, not arbitrary HTTPS."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').rstrip('.').lower()
        if parsed.scheme.lower() != 'https' or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
    except ValueError:
        return False
    if host == 'github.com':
        # A repository is authoritative for its own source code/issues, not NFL facts.
        path = parsed.path.lower().rstrip('/')
        return path == OWN_REPOSITORY_PATH or path.startswith(OWN_REPOSITORY_PATH + '/')
    return any(host == domain or host.endswith('.' + domain) for domain in PUBLISHER_ROOTS)


@dataclass
class Row:
    line: int
    urls: list[str] = field(default_factory=list)
    cell_tags: list[str] = field(default_factory=list)
    in_head: bool = False
    has_row_header: bool = False


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, int]] = []
        self.ids: set[str] = set()
        self.rows: list[Row] = []
        self.table_depth = 0
        self.head_depth = 0
        self.row: Row | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for ident in (values.get('id'), values.get('name') if tag == 'a' else None):
            if ident:
                self.ids.add(ident)
        if tag == 'table':
            self.table_depth += 1
        elif tag == 'thead' and self.table_depth:
            self.head_depth += 1
        elif tag == 'tr' and self.table_depth:
            self.row = Row(line=self.getpos()[0], in_head=bool(self.head_depth))
        elif tag in ('th', 'td') and self.row is not None:
            self.row.cell_tags.append(tag)
            if tag == 'th' and values.get('scope', '').lower() == 'row':
                self.row.has_row_header = True
        for attribute in ('href', 'src'):
            url = values.get(attribute)
            if url:
                self.links.append((url, self.getpos()[0]))
                if tag == 'a' and attribute == 'href' and self.row is not None:
                    self.row.urls.append(url)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'tr' and self.row is not None:
            if not self.row.in_head and ('td' in self.row.cell_tags or self.row.has_row_header):
                self.rows.append(self.row)
            self.row = None
        elif tag == 'thead' and self.head_depth:
            self.head_depth -= 1
        elif tag == 'table' and self.table_depth:
            self.table_depth -= 1


def _target(root: Path, current: Path, url: str) -> tuple[Path | None, str, str | None]:
    """Resolve local URLs, preserving fragment; None target means external URL."""
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme.lower() == 'javascript':
            return None, '', 'javascript URL is not permitted'
        return None, '', None
    fragment = unquote(parsed.fragment)
    path = unquote(parsed.path)
    if not path:
        return current, fragment, None
    if path.startswith('/'):
        parts = Path(path.lstrip('/')).parts
        if parts and parts[0].casefold() == root.name.casefold():
            parts = parts[1:]
        target = root.joinpath(*parts).resolve()
    else:
        target = (current.parent / path).resolve()
    if not target.is_relative_to(root):
        return None, fragment, 'local link escapes site root'
    if target.is_dir():
        target = target / 'index.html'
    return target, fragment, None


def audit(root: Path) -> tuple[list[str], int, int]:
    root = root.resolve()
    paths = sorted(p for p in root.rglob('*.html')
                   if not any(part in EXCLUDED_DIRS for part in p.relative_to(root).parts))
    pages: dict[Path, Page] = {}
    errors: list[str] = []
    row_count = 0
    for path in paths:
        page = Page()
        try:
            page.feed(path.read_text(encoding='utf-8'))
        except (UnicodeError, OSError) as exc:
            errors.append(f'{path.relative_to(root)}: cannot read: {exc}')
            continue
        pages[path] = page
        row_count += len(page.rows)
        for row in page.rows:
            if not any(official_source(url) for url in row.urls):
                errors.append(f'{path.relative_to(root)}:{row.line}: data row lacks a recognized official source')
    for path, page in pages.items():
        for url, line in page.links:
            try:
                target, fragment, problem = _target(root, path, url)
            except ValueError:
                errors.append(f'{path.relative_to(root)}:{line}: malformed URL {url!r}')
                continue
            if problem:
                errors.append(f'{path.relative_to(root)}:{line}: {problem}: {url}')
            elif target is not None:
                if not target.is_file():
                    errors.append(f'{path.relative_to(root)}:{line}: missing local target: {url}')
                elif fragment and target.suffix.lower() in ('.html', '.htm'):
                    destination = pages.get(target)
                    if destination is None or fragment not in destination.ids:
                        errors.append(f'{path.relative_to(root)}:{line}: missing local anchor: {url}')
    return errors, len(pages), row_count


def audit_dashboard_data(root: Path) -> tuple[list[str], list[str], int, int]:
    """Check the source registry and JSON rows used by the dynamic dashboard.

    The publisher check is a review warning, not proof that a source supports
    a claim. Invalid JSON is an error because it breaks the dashboard renderer.
    """
    root = root.resolve()
    data = root / 'data'
    registry = data / 'sources.json'
    if not registry.is_file():
        return [], [], 0, 0
    errors: list[str] = []
    warnings: list[str] = []

    def read_json(path: Path):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f'{path.relative_to(root)}: cannot read JSON: {exc}')
            return None

    doc = read_json(registry)
    if doc is None:
        return errors, warnings, 0, 0
    if not isinstance(doc, dict) or not isinstance(doc.get('sources'), list):
        return [f'{registry.relative_to(root)}: expected an object with a sources array'], warnings, 0, 0
    sources = {}
    for entry in doc['sources']:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str):
            errors.append(f'{registry.relative_to(root)}: malformed source entry')
            continue
        source_id = entry['id']
        if source_id in sources:
            errors.append(f'{registry.relative_to(root)}: duplicate source ID: {source_id}')
            continue
        sources[source_id] = entry
        if not isinstance(entry.get('url'), str) or not official_source(entry['url']):
            warnings.append(f'{registry.relative_to(root)}: {source_id} has no recognized primary-publisher URL')

    row_count = 0
    for path in sorted(data.glob('*.json')):
        if path == registry:
            continue
        obj = read_json(path)
        if obj is None:
            continue
        if not isinstance(obj, dict) or 'rows' not in obj:
            continue  # not a dashboard row set
        if not isinstance(obj['rows'], list):
            errors.append(f'{path.relative_to(root)}: rows is not an array')
            continue
        for index, row in enumerate(obj['rows']):
            row_count += 1
            if not isinstance(row, dict):
                errors.append(f'{path.relative_to(root)}: row {index + 1} is not an object')
                continue
            refs = row.get('sources') or row.get('inputs') or []
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                errors.append(f'{path.relative_to(root)}: row {index + 1} has malformed source IDs')
                continue
            unknown = [ref for ref in refs if ref not in sources]
            if unknown:
                warnings.append(f'{path.relative_to(root)}: row {index + 1} references unknown sources: {", ".join(unknown)}')
            if not any(ref in sources and isinstance(sources[ref].get('url'), str)
                       and official_source(sources[ref]['url']) for ref in refs):
                warnings.append(f'{path.relative_to(root)}: row {index + 1} lacks a recognized primary-publisher URL')
    return errors, warnings, len(sources), row_count


def main() -> int:
    parser = argparse.ArgumentParser(description='Check local links and report source-domain review flags.')
    parser.add_argument('--strict-sources', action='store_true',
                        help='exit nonzero if any source-domain review flags remain')
    args = parser.parse_args()
    issues, pages, rows = audit(ROOT)
    source_suffix = 'data row lacks a recognized official source'
    source_issues = [issue for issue in issues if issue.endswith(source_suffix)]
    errors = [issue for issue in issues if not issue.endswith(source_suffix)]
    data_errors, data_warnings, sources, json_rows = audit_dashboard_data(ROOT)
    errors.extend(data_errors)
    source_issues.extend(data_warnings)
    print(f'Checked {pages} HTML pages / {rows} static rows; '
          f'{sources} registered dashboard sources / {json_rows} JSON rows.')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        print(f'FAIL: {len(errors)} local-link or data errors', file=sys.stderr)
    else:
        print('PASS: offline local targets, anchors and readable dashboard data')
    if source_issues:
        by_file = Counter(issue.split(':', 1)[0] for issue in source_issues)
        print(f'REVIEW: {len(source_issues)} source-domain/ID flags (not semantic validation):')
        for filename, count in sorted(by_file.items()):
            print(f'  {filename}: {count}')
    else:
        print('PASS: inspected rows have recognized publisher links')
    print('LIMIT: no network, runtime DOM, external availability, semantic source support, '
          'numerical accuracy or model validity was tested.')
    return 1 if errors or (args.strict_sources and source_issues) else 0


if __name__ == '__main__':
    raise SystemExit(main())
