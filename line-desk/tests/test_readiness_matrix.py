#!/usr/bin/env python3
"""Focused checks for the Line Desk readiness matrix."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LD = ROOT / "line-desk"
sys.path.insert(0, str(LD / "scripts"))
import build_site  # noqa: E402


class ReadinessMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requirements = json.loads((LD / "data/requirements.json").read_text(encoding="utf-8"))
        cls.flagged = json.loads((LD / "data/flagged.json").read_text(encoding="utf-8"))
        cls.html = build_site.readiness_matrix(cls.requirements, cls.flagged)
        cls.index_html = build_site.build_index()
        cls.body_rows = re.findall(r"<tr>(.*?)</tr>", cls.html, re.S)[1:]

    def test_one_row_per_registered_requirement(self):
        ids = [row["id"] for row in self.requirements["rows"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(self.body_rows), len(ids))
        for requirement_id in ids:
            self.assertEqual(self.html.count(f"<b>{requirement_id}</b>"), 1)

    def test_each_row_has_a_project_proposal_and_https_source(self):
        for requirement in self.requirements["rows"]:
            self.assertTrue(requirement["proposed_clear_threshold"].startswith("Proposal:"))
            self.assertTrue(requirement["source_url"].startswith("https://"))
            self.assertIn(requirement["evidence_path"], self.html)
        for row in self.body_rows:
            cells = re.findall(r"<td>(.*?)</td>", row, re.S)
            self.assertEqual(len(cells), 5)
            self.assertRegex(cells[-1], r'<a href="https://')

    def test_unverified_observations_render_blank_and_flagged(self):
        for requirement in self.requirements["rows"]:
            row = next(row for row in self.body_rows if f"<b>{requirement['id']}</b>" in row)
            for field in requirement.get("observed_missing_fields", []):
                self.assertIn(f'{field["label"]}: &mdash; (unverified)', row)
            if requirement["observed_value"] is None:
                self.assertIn("class=\"blank\"", row)
                self.assertIn("observed_blank_reason", requirement)
                self.assertIn("title=", row)
            for flag_id in requirement["review_flags"]:
                self.assertIn(f"pages/flagged.html#{flag_id}", row)

    def test_landing_page_links_to_the_matrix_and_detailed_trace(self):
        self.assertIn('href="#readiness-matrix"', self.index_html)
        self.assertIn('id="readiness-matrix"', self.index_html)
        self.assertIn('href="pages/requirements.html"', self.index_html)

    def test_all_clear_thresholds_are_explicitly_project_proposals(self):
        self.assertIn("not official NFL or industry standards", self.html)
        self.assertTrue(all(r["proposed_clear_threshold"].startswith("Proposal:")
                            for r in self.requirements["rows"]))


if __name__ == "__main__":
    unittest.main()
