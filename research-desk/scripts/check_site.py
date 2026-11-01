#!/usr/bin/env python3
"""Offline sanity checks; content verification must be performed against sources separately."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'www.nfl.com', 'operations.nfl.com', 'scikit-learn.org', 'tsapps.nist.gov', 'www.weather.gov', 'www.gamblingcommission.gov.uk', 'docs.github.com'}
class Check(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path=path; self.errors=[]; self.in_tbody=False; self.in_row=False; self.source=False
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='tbody': self.in_tbody=True
        if tag=='tr' and self.in_tbody: self.in_row=True; self.source=False
        if tag=='a':
            href=attrs.get('href',''); u=urlparse(href)
            if self.in_row and u.scheme == 'https' and u.netloc in ALLOWED: self.source=True
            if not u.scheme and not u.netloc and u.path:
                target=(self.path.parent / unquote(u.path)).resolve()
                if not target.is_relative_to(ROOT) or not target.is_file(): self.errors.append(f'broken link: {href}')
        if tag=='link' and attrs.get('href'):
            if not (self.path.parent / attrs['href']).is_file(): self.errors.append(f'missing asset: {attrs["href"]}')
    def handle_endtag(self,tag):
        if tag=='tr' and self.in_row:
            if not self.source: self.errors.append('table row missing official/context source')
            self.in_row=False
        if tag=='tbody': self.in_tbody=False

pages=['index.html','strategies.html','validation.html','correlation.html','evidence.html','review.html']
before={p:(ROOT/p).read_bytes() for p in pages}
subprocess.run([sys.executable,str(ROOT/'scripts/build_site.py')],check=True,stdout=subprocess.DEVNULL)
errors=[]
for p in pages:
    if before[p] != (ROOT/p).read_bytes(): errors.append(f'{p}: generated output was stale (regenerated)')
    parser=Check(ROOT/p); parser.feed((ROOT/p).read_text()); errors.extend(f'{p}: {e}' for e in parser.errors)
if errors:
    print('\n'.join(errors)); sys.exit(1)
print('OK: generated pages current, local links/assets exist, all data rows have official/context sources.')
