import unittest


class RenderTests(unittest.TestCase):
    def test_render_analysis_result_formats_summary_evidence_and_provider(self):
        from viv_ai.ui.render import render_analysis_result

        text = render_analysis_result({
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

    def test_render_analysis_result_formats_provider_status(self):
        from viv_ai.ui.render import render_analysis_result

        text = render_analysis_result({
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

    def test_render_analysis_result_formats_error_state(self):
        from viv_ai.ui.render import render_analysis_result

        text = render_analysis_result({'task_type': 'graph_summary', 'error': 'provider offline'})

        self.assertIn('Task: graph_summary', text)
        self.assertIn('Error: provider offline', text)


if __name__ == '__main__':
    unittest.main()
