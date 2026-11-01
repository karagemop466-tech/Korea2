#!/usr/bin/env python3
"""Check local links and require a source link on every body table row."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]

class Checker(HTMLParser):
    def __init__(self, file):
        super().__init__(); self.file = file; self.errors = []; self.in_body = False; self.in_row = False; self.row_source = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tbody': self.in_body = True
        if tag == 'tr' and self.in_body: self.in_row = True; self.row_source = False
        for name in ('href', 'src'):
            url = attrs.get(name)
            if not url: continue
            parsed = urlparse(url)
            if self.in_row and tag == 'a' and parsed.scheme == 'https': self.row_source = True
            if parsed.scheme or parsed.netloc or url.startswith('#'): continue
            path = (self.file.parent / unquote(parsed.path)).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file(): self.errors.append(f'{self.file.name}: missing {url}')
    def handle_endtag(self, tag):
        if tag == 'tr' and self.in_row:
            if not self.row_source: self.errors.append(f'{self.file.name}: table row missing https source')
            self.in_row = False
        if tag == 'tbody': self.in_body = False

errors=[]
for file in sorted(ROOT.glob('*.html')):
    p=Checker(file); p.feed(file.read_text(encoding='utf-8')); errors.extend(p.errors)
if errors: raise SystemExit('\n'.join(errors))
print('Local links and source links in every table row: OK')
