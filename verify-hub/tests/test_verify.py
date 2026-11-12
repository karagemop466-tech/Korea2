#!/usr/bin/env python3
"""Unit tests for the verify-hub checker (run in CI: python -m unittest discover -s verify-hub/tests)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("vh_verify", ROOT / "scripts" / "verify.py")
vh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vh)


class SourceDisciplineTests(unittest.TestCase):
    def test_row_without_sources_is_rejected(self):
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "sources.json").write_text(
                '{"sources": [{"id": "S1", "url": "https://www.nfl.com/x"}]}')
            (data / "rows.json").write_text(
                '{"rows": [{"id": "R1", "value": "1", "sources": []}]}')
            old = vh.DATA
            vh.DATA = data
            try:
                vh.check_data(errors)
            finally:
                vh.DATA = old
        self.assertTrue(any("missing sources array" in e for e in errors))

    def test_flagged_value_must_stay_blank(self):
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "sources.json").write_text(
                '{"sources": [{"id": "S1", "url": "https://www.nfl.com/x"}]}')
            (data / "flagged.json").write_text(
                '{"rows": [{"id": "F1", "value": "42", "reason": "r", "sources": ["S1"]}]}')
            old = vh.DATA
            vh.DATA = data
            try:
                vh.check_data(errors)
            finally:
                vh.DATA = old
        self.assertTrue(any("must stay blank" in e for e in errors))

    def test_depth_string_must_stay_blank(self):
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "sources.json").write_text(
                '{"sources": [{"id": "S1", "url": "https://www.nfl.com/x"}]}')
            (data / "injuries_gap.json").write_text(
                '{"verified_week10_sample": {"rows": [{"player": "P", "string": "2nd", "sources": ["S1"]}]}}')
            old = vh.DATA
            vh.DATA = data
            try:
                vh.check_data(errors)
            finally:
                vh.DATA = old
        self.assertTrue(any("depth string must stay blank" in e for e in errors))


class TableSourceTests(unittest.TestCase):
    def test_table_row_without_link_is_rejected(self):
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "ok.html").write_text(
                "<table><tbody><tr><td>a</td><td><a href='https://www.nfl.com/x'>src</a></td></tr>"
                "<tr><td>b</td><td>c</td></tr></tbody></table>")
            old = vh.ROOT
            vh.ROOT = base
            try:
                vh.check_html(errors)
            finally:
                vh.ROOT = old
        self.assertTrue(any("without a source link" in e for e in errors))

    def test_http_link_is_rejected(self):
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "insecure.html").write_text(
                "<table><tbody><tr><td>a</td>"
                "<td><a href='http://www.nfl.com/x'>src</a></td></tr></tbody></table>")
            old = vh.ROOT
            vh.ROOT = base
            try:
                vh.check_html(errors)
            finally:
                vh.ROOT = old
        self.assertTrue(any("insecure link" in e for e in errors))


class RealDataTests(unittest.TestCase):
    def test_committed_data_passes(self):
        errors: list[str] = []
        vh.check_data(errors)
        self.assertEqual([], errors)

    def test_committed_site_passes(self):
        errors: list[str] = []
        vh.check_html(errors)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
