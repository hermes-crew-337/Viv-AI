"""Tests for viv_ai/report.py — matching the actual API."""
from __future__ import annotations

from unittest.mock import MagicMock
import unittest


class TestGenerateReport(unittest.TestCase):
    def setUp(self):
        self.vw = MagicMock()
        self.vw.getMeta.side_effect = lambda key, default=None: {
            "Architecture": "x86",
            "Platform": "linux",
            "Format": "elf",
            "NumFunctions": 42,
        }.get(key, default)

    def test_report_returns_dict(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw)
        self.assertIsInstance(report, dict)

    def test_report_has_metadata(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw)
        self.assertIn("metadata", report)
        self.assertIn("architecture", report["metadata"])
        self.assertEqual(report["metadata"]["architecture"], "x86")

    def test_report_has_functions(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw, [{"va": 0x401000}])
        self.assertIn("functions", report)
        self.assertEqual(len(report["functions"]), 1)

    def test_report_empty_functions(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw, [])
        self.assertEqual(len(report["functions"]), 0)

    def test_report_no_results_gives_empty_functions(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw)
        self.assertEqual(len(report["functions"]), 0)

    def test_report_has_markdown(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw)
        self.assertIn("markdown", report)
        self.assertIn("Binary Analysis Report", report["markdown"])

    def test_report_function_count_in_metadata(self):
        from viv_ai.report import generate_report
        report = generate_report(self.vw)
        self.assertIn("function_count", report["metadata"])


if __name__ == "__main__":
    unittest.main()
