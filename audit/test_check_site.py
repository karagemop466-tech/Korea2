import json
import tempfile
import unittest
from pathlib import Path

from check_site import audit, audit_dashboard_data, official_source


class SourceChecks(unittest.TestCase):
    def test_official_sources(self):
        for url in (
            'https://www.nfl.com/players/bo-nix/stats/career',
            'https://www.weather.gov/example',
            'https://scikit-learn.org/stable/common_pitfalls.html',
            'https://github.com/karagemop466-tech/Korea2/blob/main/README.md',
        ):
            with self.subTest(url=url):
                self.assertTrue(official_source(url))

    def test_rejects_spoofed_non_official_or_unsafe_hosts(self):
        for url in (
            'https://nfl.com.evil.example/a', 'https://notnfl.com/a',
            'http://www.nfl.com/a', 'https://nfl.com@evil.example/a',
            'https://github.com/other/project', 'https://example.com/a',
            'https://www.nfl.com:444/a', 'javascript:alert(1)',
        ):
            with self.subTest(url=url):
                self.assertFalse(official_source(url))


class LinkChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'other.html').write_text('<h1 id="found">Target</h1>', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, text):
        (self.root / 'index.html').write_text(text, encoding='utf-8')

    def test_valid_rows_without_tbody_and_anchor(self):
        self.write('<a href="other.html#found">go</a><table><tr><th>heading</th></tr>'
                   '<tr><td>data <a href="https://www.nfl.com/a">source</a></td></tr></table>')
        errors, pages, rows = audit(self.root)
        self.assertEqual(errors, [])
        self.assertEqual((pages, rows), (2, 1))

    def test_missing_unapproved_source_fails(self):
        self.write('<table><tbody><tr><td><a href="https://example.com">x</a></td></tr></tbody></table>')
        errors, _, _ = audit(self.root)
        self.assertTrue(any('recognized official source' in e for e in errors))

    def test_row_header_only_is_still_a_data_row(self):
        self.write('<table><tbody><tr><th scope="row">data</th></tr></tbody></table>')
        errors, _, rows = audit(self.root)
        self.assertEqual(rows, 1)
        self.assertTrue(any('recognized official source' in e for e in errors))

    def test_missing_file_and_anchor_fail(self):
        self.write('<a href="missing.html">missing</a><a href="other.html#absent">bad anchor</a>')
        errors, _, _ = audit(self.root)
        self.assertTrue(any('missing local target' in e for e in errors))
        self.assertTrue(any('missing local anchor' in e for e in errors))

    def test_escape_and_javascript_fail(self):
        self.write('<a href="../escape.html">bad</a><a href="javascript:alert(1)">bad</a>')
        errors, _, _ = audit(self.root)
        self.assertTrue(any('escapes site root' in e for e in errors))
        self.assertTrue(any('javascript URL' in e for e in errors))


class DashboardDataChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.data.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, obj):
        (self.data / name).write_text(json.dumps(obj), encoding='utf-8')

    def test_source_ids_and_input_fallback(self):
        self.write('sources.json', {'sources': [{'id': 'NFL', 'url': 'https://nfl.com/'}]})
        self.write('signals.json', {'rows': [{'sources': ['NFL']}, {'inputs': ['NFL']}]})
        errors, warnings, sources, rows = audit_dashboard_data(self.root)
        self.assertEqual((errors, warnings, sources, rows), ([], [], 1, 2))

    def test_unknown_and_unrecognized_source_warnings(self):
        self.write('sources.json', {'sources': [{'id': 'third-party', 'url': 'https://example.com/'}]})
        self.write('signals.json', {'rows': [{'sources': ['missing']}, {'sources': ['third-party']}]})
        errors, warnings, _, rows = audit_dashboard_data(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(rows, 2)
        self.assertTrue(any('unknown sources' in w for w in warnings))
        self.assertTrue(any('no recognized primary-publisher URL' in w for w in warnings))
        self.assertTrue(any('row 2 lacks a recognized' in w for w in warnings))

    def test_invalid_json_and_duplicate_ids_are_errors(self):
        self.write('sources.json', {'sources': [{'id': 'NFL', 'url': 'https://nfl.com/'},
                                                {'id': 'NFL', 'url': 'https://nfl.com/'}]})
        (self.data / 'signals.json').write_text('{broken', encoding='utf-8')
        errors, _, _, _ = audit_dashboard_data(self.root)
        self.assertTrue(any('duplicate source ID' in e for e in errors))
        self.assertTrue(any('cannot read JSON' in e for e in errors))

    def test_absent_registry_is_skipped(self):
        self.assertEqual(audit_dashboard_data(self.root), ([], [], 0, 0))


if __name__ == '__main__':
    unittest.main()
