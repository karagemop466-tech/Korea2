from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
class Check(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path = path; self.in_body = False; self.row = None; self.errors = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tbody': self.in_body = True
        if tag == 'tr' and self.in_body: self.row = False
        if tag in ('a', 'link'):
            href = attrs.get('href', '')
            if self.row is not None and tag == 'a' and href.startswith('https://'): self.row = True
            if href and not urlsplit(href).scheme and not href.startswith('#'):
                if not (self.path.parent / urlsplit(href).path).is_file(): self.errors.append(f'broken local link: {href}')
    def handle_endtag(self, tag):
        if tag == 'tr' and self.row is not None:
            if not self.row: self.errors.append('table row missing source link')
            self.row = None
        if tag == 'tbody': self.in_body = False
errors = []
for path in [ROOT / 'index.html', *sorted((ROOT / 'pages').glob('*.html'))]:
    parser = Check(path); parser.feed(path.read_text()); errors += [f'{path.relative_to(ROOT)}: {e}' for e in parser.errors]
if errors: raise SystemExit('\n'.join(errors))
print('PASS: local links and table-row source links')
