"""Expanded tests for Viv-AI UI result rendering — covering edge cases for 95%+ coverage.

Targets uncovered lines: 141–151 (_status_html issues+hints),
204 (va field in render_analysis_result), 242–248 (plain text issues+hints).
"""

from __future__ import annotations

import unittest


class RenderExpandedTests(unittest.TestCase):
    """Tests covering remaining uncovered lines and additional edge cases."""

    maxDiff = None

    # ------------------------------------------------------------------ #
    # Lines 141-151: _status_html issues rendering with hints
    # ------------------------------------------------------------------ #

    def test_status_html_with_issues_and_hints(self):
        """Cover lines 141-151: status rendering with issues including hints."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'test_provider',
                'provider_type': 'ollama',
                'endpoint': 'http://test:11434',
                'configured_model': 'test-model',
                'available_models': ['model-a'],
                'issues': [
                    {
                        'field': 'endpoint',
                        'message': 'Connection refused',
                        'hint': 'Check if service is running',
                    },
                    {
                        'field': 'model',
                        'message': 'Model not found',
                        # no hint – covers the if-hint-else path
                    },
                ],
            },
        })

        # First issue — has hint
        self.assertIn('⚠ endpoint', html)
        self.assertIn('Connection refused', html)
        self.assertIn('Check if service is running', html)

        # Second issue — no hint
        self.assertIn('⚠ model', html)
        self.assertIn('Model not found', html)

        # Verify the structure is sound
        self.assertIn('Provider Status', html)
        self.assertIn('test_provider', html)

    def test_status_html_without_available_models(self):
        """Cover status path where available_models is empty/missing."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'minimal',
                'provider_type': 'test',
                'issues': [
                    {'field': 'api', 'message': 'timeout'},
                ],
            },
        })

        self.assertIn('Provider Status', html)
        self.assertIn('⚠ api', html)
        self.assertIn('timeout', html)
        # No available models section
        self.assertNotIn('Available Models', html)

    def test_status_html_issue_missing_fields(self):
        """Cover issue items with missing field/message keys (uses defaults)."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'test',
                'provider_type': 'test',
                'issues': [
                    {},  # completely empty issue
                    {'field': 'ok', 'message': 'fine'},
                ],
            },
        })

        # Empty issue should use defaults: field='?', message=''
        self.assertIn('⚠ ?', html)
        # Normal issue still renders
        self.assertIn('⚠ ok', html)
        self.assertIn('fine', html)

    # ------------------------------------------------------------------ #
    # Line 204: render_analysis_result with va field
    # ------------------------------------------------------------------ #

    def test_render_analysis_result_with_va(self):
        """Cover line 204: render result with va field in task header."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'va': '0x401000',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': False,
            'analysis': {
                'summary': 'test summary',
                'confidence': 'high',
                'evidence': ['item1'],
            },
        })

        self.assertIn('function_summary — 0x401000', html)
        self.assertIn('test summary', html)
        self.assertIn('FRESH', html)

    def test_render_analysis_result_with_va_special_chars(self):
        """Cover line 204 with va containing special characters."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'va': '<script>',
            'provider': {'type': 'test', 'model': 'test'},
            'cache_hit': False,
            'analysis': {
                'summary': 'test',
                'evidence': [],
            },
        })

        # va_str is escaped via _escape_html
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)

    # ------------------------------------------------------------------ #
    # Lines 242-248: render_plain_text_fallback issues + hints
    # ------------------------------------------------------------------ #

    def test_plain_text_fallback_with_issues_and_hints(self):
        """Cover lines 242-248: plain text status with issues including hints."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'test_provider',
                'provider_type': 'ollama',
                'endpoint': 'http://test:11434',
                'configured_model': 'test-model',
                'available_models': ['model-a'],
                'issues': [
                    {
                        'field': 'endpoint',
                        'message': 'Connection refused',
                        'hint': 'Check if service is running',
                    },
                    {
                        'field': 'model',
                        'message': 'Model not found',
                        # no hint – covers else branch of line 248
                    },
                ],
            },
        })

        self.assertIn('- endpoint: Connection refused', text)
        self.assertIn('hint: Check if service is running', text)
        self.assertIn('- model: Model not found', text)
        self.assertNotIn('hint: Model not found', text)

    def test_plain_text_fallback_issues_only(self):
        """Cover plain text with issues but no other status fields."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'provider_status',
            'status': {
                'issues': [
                    {'field': 'api', 'message': 'timeout'},
                ],
            },
        })

        self.assertIn('- api: timeout', text)

    def test_plain_text_fallback_issues_missing_fields(self):
        """Cover plain text issue items with missing field/message (defaults)."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'provider_status',
            'status': {
                'issues': [
                    {},  # completely empty – uses defaults 'unknown' / 'unknown issue'
                ],
            },
        })

        self.assertIn('- unknown: unknown issue', text)

    # ------------------------------------------------------------------ #
    # Additional edge cases for robustness
    # ------------------------------------------------------------------ #

    def test_error_html_with_va(self):
        """Cover error path with va field present (line 99 addr rendering)."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'graph_summary',
            'va': '0x401000',
            'error': 'provider offline',
        })

        self.assertIn('Error — graph_summary at 0x401000', html)
        self.assertIn('provider offline', html)

    def test_confidence_html_unknown_value(self):
        """Cover confidence value not in _CONFIDENCE_COLORS -> default gray."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'test', 'model': 'test'},
            'cache_hit': False,
            'analysis': {
                'summary': 'test',
                'confidence': 'unknown_val',
                'evidence': [],
            },
        })

        self.assertIn('UNKNOWN_VAL', html)
        self.assertIn('#757575', html)  # default gray fallback colour

    def test_provenance_badge_with_provider_in_analysis(self):
        """Cover provenance badge using nested provider from analysis dict."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'top-level', 'model': 'top-model'},
            'cache_hit': True,
            'analysis': {
                'summary': 'test',
                'confidence': 'high',
                'evidence': [],
                'provider': {'type': 'analysis-provider', 'model': 'analysis-model'},
            },
        })

        # Footer uses top-level provider
        self.assertIn('top-level/top-model', html)
        # Provenance badge uses analysis.get('provider', {})
        self.assertIn('analysis-provider/analysis-model', html)
        self.assertIn('CACHED', html)

    def test_evidence_html_non_string_items(self):
        """Cover evidence with non-string items (str() conversion)."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'test', 'model': 'test'},
            'cache_hit': False,
            'analysis': {
                'summary': 'test',
                'confidence': 'high',
                'evidence': [42, 3.14, True, None],
            },
        })

        self.assertIn('42', html)
        self.assertIn('3.14', html)
        self.assertIn('True', html)
        self.assertIn('None', html)

    def test_escape_html_double_quote(self):
        """Cover double-quote escaping in _escape_html (the \" replace)."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'test"model', 'model': 'test"model'},
            'cache_hit': False,
            'analysis': {
                'summary': 'test "quoted" text',
                'evidence': [],
            },
        })

        self.assertIn('&quot;', html)
        # No raw double-quotes should remain unescaped in rendered content
        # (the HTML attributes are safely using single-quotes in the template)
        self.assertNotIn('"quoted"', html)

    def test_render_analysis_result_empty_analysis_dict(self):
        """Cover empty analysis dict (falsy) — no provenance badge."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'test', 'model': 'test'},
            'cache_hit': False,
            'analysis': {},
        })

        self.assertIn('function_summary', html)
        self.assertIn('test/test', html)  # footer still rendered
        # analysis={} is falsy → provenance = ''
        self.assertNotIn('FRESH', html)
        # No summary, no confidence, no evidence
        self.assertNotIn('<ul', html)

    def test_render_analysis_result_no_summary(self):
        """Cover result without summary field."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'test', 'model': 'test'},
            'cache_hit': False,
            'analysis': {
                'confidence': 'low',
                'evidence': ['some evidence'],
            },
        })

        self.assertIn('function_summary', html)
        self.assertIn('LOW', html)
        self.assertIn('some evidence', html)
        self.assertIn('FRESH', html)

    def test_plain_text_fallback_without_status_keys(self):
        """Cover plain text status with missing optional keys (endpoint, etc.)."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'minimal',
                'provider_type': 'test',
                # no endpoint, no configured_model, no available_models
            },
        })

        self.assertIn('Provider name: minimal', text)
        self.assertIn('Provider type: test', text)
        # No endpoint line, no configured model line
        self.assertNotIn('Endpoint:', text)
        self.assertNotIn('Configured model:', text)

    def test_plain_text_fallback_with_cache_hit(self):
        """Cover plain text with cache hit and all analysis fields."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': True,
            'analysis': {
                'summary': 'test summary',
                'confidence': 'high',
                'evidence': ['item1', 'item2'],
            },
        })

        self.assertIn('Cache: hit', text)
        self.assertIn('Summary: test summary', text)
        self.assertIn('Confidence: high', text)
        self.assertIn('- item1', text)
        self.assertIn('- item2', text)

    def test_plain_text_fallback_error_state(self):
        """Cover lines 224-225: plain text error path."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'graph_summary',
            'error': 'timeout connecting to provider',
        })

        self.assertIn('Task: graph_summary', text)
        self.assertIn('Error: timeout connecting to provider', text)
        # Error path returns early, no status/analysis lines
        self.assertNotIn('Provider name:', text)
        self.assertNotIn('Cache:', text)

    def test_plain_text_fallback_no_analysis(self):
        """Cover plain text with no analysis at all."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'function_summary',
        })

        self.assertIn('Task: function_summary', text)
        self.assertIn('Cache: miss', text)
        # No provider, no summary, no evidence
        self.assertNotIn('Provider:', text)


if __name__ == '__main__':
    unittest.main()
