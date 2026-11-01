#!/usr/bin/env python3
"""Offline audit of HTML links and allowed source domains.

A recognized domain is a necessary syntax check, not proof that the page is
reachable, a claim is supported, or numerical values have been verified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', 'build', 'dist'}
PUBLISHER_ROOTS = (
    'nfl.com', 'gov', 'gov.uk', 'gov.sg', 'massgaming.com',
    'scikit-learn.org', 'draftkings.com', 'docs.github.com',
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


def main() -> int:
    errors, pages, rows = audit(ROOT)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        print(f'FAIL: {len(errors)} issue(s) in {pages} pages / {rows} data rows', file=sys.stderr)
        return 1
    print(f'PASS: {pages} HTML pages, {rows} data rows; local targets/anchors and source-domain allowlist')
    print('LIMIT: no network, external availability, semantic source support, or numerical verification was tested.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
