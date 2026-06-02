"""Tests for viv_ai.report — analysis report generation."""

import unittest


class _MockVW:
    def getMeta(self, key, default=None):
        return {'Architecture': 'amd64', 'Platform': 'windows', 'Format': 'pe'}.get(key, default)

    def getEntryPoints(self):
        return [0x401000]

    def getFunctions(self):
        return [0x401000, 0x402000]


class ReportTests(unittest.TestCase):
    def test_generate_report_without_results(self):
        from viv_ai.report import generate_report

        report = generate_report(_MockVW())

        self.assertEqual(report['metadata']['architecture'], 'amd64')
        self.assertEqual(report['metadata']['function_count'], 2)
        self.assertEqual(report['functions'], [])
        self.assertIn('Binary Analysis Report', report['markdown'])
        self.assertIn('amd64', report['markdown'])

    def test_generate_report_with_results(self):
        from viv_ai.report import generate_report

        report = generate_report(_MockVW(), results=[
            {'fva': 0x401000, 'name': 'main', 'analysis': {'summary': 'entry point'}},
            {'fva': 0x402000, 'name': 'helper', 'analysis': {'summary': 'utility function'}},
        ])

        self.assertEqual(len(report['functions']), 2)
        self.assertEqual(report['functions'][0]['fva'], '0x00401000')
        self.assertEqual(report['functions'][0]['name'], 'main')
        self.assertEqual(report['functions'][1]['analysis']['summary'], 'utility function')
        self.assertIn('main', report['markdown'])
        self.assertIn('entry point', report['markdown'])

    def test_generate_report_fva_defaults_to_str(self):
        from viv_ai.report import generate_report

        report = generate_report(_MockVW(), results=[
            {'fva': '0x1234', 'name': 'test'},
        ])

        self.assertEqual(report['functions'][0]['fva'], '0x1234')

    def test_generate_report_handles_empty_results_safely(self):
        from viv_ai.report import generate_report

        report = generate_report(_MockVW(), results=[])

        self.assertEqual(report['functions'], [])
