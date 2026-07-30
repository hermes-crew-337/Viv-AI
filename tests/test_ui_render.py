"""Tests for Viv-AI UI result rendering — Phase R HTML format."""

import unittest


class RenderTests(unittest.TestCase):
    """Tests for the primary HTML renderer."""

    maxDiff = None

    def test_render_analysis_result_html_summary_evidence_and_provider(self):
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': True,
            'analysis': {
                'summary': 'input parsing loop',
                'confidence': 'high',
                'evidence': ['calls ReadFile', 'names buffer_count'],
            },
        })

        # HTML structure checks
        self.assertIn('function_summary', html)
        self.assertIn('input parsing loop', html)
        self.assertIn('ollama/qwen', html)
        self.assertIn('CACHED', html)
        self.assertIn('HIGH', html)
        self.assertIn('calls ReadFile', html)
        self.assertIn('names buffer_count', html)
        self.assertIn('margin-bottom:4px;">function_summary', html)
        self.assertIn('<ul', html)
        self.assertIn('<li', html)

    def test_render_analysis_result_html_fresh(self):
        """Fresh (non-cached) results show FRESH badge."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen2'},
            'cache_hit': False,
            'analysis': {
                'summary': 'decryption routine',
                'confidence': 'medium',
                'evidence': ['XOR loop', 'constant table at 0x401200'],
            },
        })

        self.assertIn('FRESH', html)
        self.assertIn('decryption routine', html)
        self.assertIn('MEDIUM', html)
        self.assertIn('ollama/qwen2', html)
        self.assertIn('#e65100', html)  # medium confidence color

    def test_render_analysis_result_html_low_confidence(self):
        """Low confidence gets red styling."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'graph_summary',
            'provider': {'type': 'ollama', 'model': 'default'},
            'cache_hit': False,
            'analysis': {
                'summary': 'possible dispatcher',
                'confidence': 'low',
                'evidence': [],
            },
        })

        self.assertIn('LOW', html)
        self.assertIn('#b71c1c', html)  # low confidence color

    def test_render_analysis_result_html_no_evidence_no_confidence(self):
        """Empty evidence and no confidence should still render."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': False,
            'analysis': {
                'summary': 'stub function',
                'evidence': [],
            },
        })

        self.assertIn('stub function', html)
        self.assertIn('FRESH', html)
        # No confidence badge, no evidence list
        self.assertNotIn('EVIDENCE', html)

    def test_render_analysis_result_html_provider_status(self):
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'ollama',
                'provider_type': 'ollama',
                'endpoint': 'http://MATRIX:11434',
                'configured_model': 'qwen2.5:72b-instruct',
                'available_models': ['qwen2.5:72b-instruct', 'gemma4:31b'],
                'issues': [],
            },
        })

        self.assertIn('Provider Status', html)
        self.assertIn('ollama', html)
        self.assertIn('qwen2.5:72b-instruct', html)
        self.assertIn('gemma4:31b', html)

    def test_render_analysis_result_html_error_state(self):
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'graph_summary',
            'error': 'provider offline',
        })

        self.assertIn('Error — graph_summary', html)
        self.assertIn('provider offline', html)
        self.assertIn('#ffebee', html)  # error background
        self.assertIn('#ef5350', html)  # error border

    def test_render_analysis_result_html_special_chars_escaped(self):
        """HTML injection through summary/evidence values is prevented."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': False,
            'analysis': {
                'summary': '<script>alert("xss")</script>',
                'evidence': ['<b>bold</b>'],
            },
        })

        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;b&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>', html)

    def test_render_analysis_result_html_no_analysis_no_provider(self):
        """Minimal result with no analysis or provider still renders gracefully."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'cache_hit': False,
        })

        self.assertIn('function_summary', html)
        # No crash, no traceback in output
        self.assertNotIn('Traceback', html)

    def test_render_analysis_result_html_escaping_in_provider(self):
        """Provider type/model strings are HTML-escaped."""
        from viv_ai.ui.render import render_analysis_result

        html = render_analysis_result({
            'task_type': 'function_summary',
            'provider': {'type': '<custom>', 'model': 'test&model'},
            'cache_hit': False,
            'analysis': {'summary': 'test', 'evidence': []},
        })

        self.assertIn('&lt;custom&gt;', html)
        self.assertIn('test&amp;model', html)


class PlainTextFallbackTests(unittest.TestCase):
    """Tests for render_plain_text_fallback (backward-compat format)."""

    def test_plain_text_summary_evidence_and_provider(self):
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'function_summary',
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'cache_hit': True,
            'analysis': {
                'summary': 'input parsing loop',
                'confidence': 'high',
                'evidence': ['calls ReadFile', 'names buffer_count'],
            },
        })

        self.assertIn('Task: function_summary', text)
        self.assertIn('Provider: ollama/qwen', text)
        self.assertIn('Cache: hit', text)
        self.assertIn('Summary: input parsing loop', text)
        self.assertIn('- calls ReadFile', text)
        self.assertIn('- names buffer_count', text)

    def test_plain_text_provider_status(self):
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'provider_status',
            'status': {
                'provider_name': 'ollama',
                'provider_type': 'ollama',
                'endpoint': 'http://MATRIX:11434',
                'configured_model': 'qwen2.5:72b-instruct',
                'available_models': ['qwen2.5:72b-instruct', 'gemma4:31b'],
                'issues': [],
            },
        })

        self.assertIn('Task: provider_status', text)
        self.assertIn('Provider name: ollama', text)
        self.assertIn('Configured model: qwen2.5:72b-instruct', text)
        self.assertIn('- gemma4:31b', text)

    def test_plain_text_error_state(self):
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'graph_summary',
            'error': 'provider offline',
        })

        self.assertIn('Task: graph_summary', text)
        self.assertIn('Error: provider offline', text)

    def test_plain_text_minimal(self):
        """Minimal result with no analysis renders without crash."""
        from viv_ai.ui.render import render_plain_text_fallback

        text = render_plain_text_fallback({
            'task_type': 'function_summary',
            'cache_hit': False,
        })

        self.assertIn('Task: function_summary', text)


if __name__ == '__main__':
    unittest.main()
