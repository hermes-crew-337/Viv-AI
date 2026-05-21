import unittest


class FakeVW:
    def __init__(self):
        self.meta = {'Architecture': 'amd64', 'Platform': 'linux', 'Format': 'elf'}

    def getMeta(self, name):
        return self.meta.get(name)


class FakeAnalysisService:
    def __init__(self):
        self.calls = []

    def provider_status(self, provider_name=None):
        return {
            'provider_name': provider_name or 'ollama',
            'provider_type': 'ollama',
            'endpoint': 'http://MATRIX:11434',
            'configured_model': 'qwen2.5:72b-instruct',
            'available_models': ['qwen2.5:72b-instruct', 'gemma4:31b'],
            'issues': [],
        }

    def analyze_function(self, vw, fva, options=None):
        self.calls.append({'task': 'function', 'vw': vw, 'fva': fva, 'options': dict(options or {})})
        return {
            'task_type': 'function_summary',
            'cache_hit': False,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {
                'summary': 'main validates the header and dispatches helpers',
                'confidence': 'medium',
                'evidence': ['0x00401000'],
            },
        }

    def analyze_binary(self, vw, options=None):
        self.calls.append({'task': 'binary', 'vw': vw, 'options': dict(options or {})})
        return {
            'task_type': 'binary_summary',
            'cache_hit': True,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {
                'summary': 'ELF utility with one entry point and light import usage',
                'confidence': 'high',
                'evidence': ['imports: 2', 'functions: 4'],
            },
        }


class ErrorAnalysisService:
    def analyze_function(self, vw, fva, options=None):
        raise RuntimeError('provider offline')

    def analyze_binary(self, vw, options=None):
        raise RuntimeError('provider offline')


class McpAiToolTests(unittest.TestCase):
    def _server(self, service):
        from viv_ai.mcp.server import VivAIMcpServer

        return VivAIMcpServer(workspace_loader=lambda path: FakeVW(), analysis_service=service)

    def _open(self, server):
        return server.call_tool('workspace_open', path='/tmp/sample.bin')['data']['workspace_id']

    def test_registry_exposes_phase_j_ai_tools(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()

        self.assertIn('ai_explain_function', registry)
        self.assertIn('ai_summarize_binary', registry)
        self.assertIn('list_provider_models', registry)

    def test_ai_explain_function_reuses_analysis_service(self):
        service = FakeAnalysisService()
        server = self._server(service)
        workspace_id = self._open(server)

        result = server.call_tool('ai_explain_function', workspace_id=workspace_id, fva='0x401000', temperature=0.2)

        self.assertTrue(result['ok'])
        self.assertEqual(result['request_scope'], 'function')
        self.assertEqual(result['data']['analysis']['summary'], 'main validates the header and dispatches helpers')
        self.assertEqual(result['data']['provider']['model'], 'qwen')
        self.assertFalse(result['data']['cache_hit'])
        self.assertEqual(service.calls[0]['fva'], 0x401000)
        self.assertEqual(service.calls[0]['options']['temperature'], 0.2)
        self.assertIn('main validates the header', result['summary'])

    def test_ai_summarize_binary_reuses_analysis_service(self):
        service = FakeAnalysisService()
        server = self._server(service)
        workspace_id = self._open(server)

        result = server.call_tool('ai_summarize_binary', workspace_id=workspace_id, temperature=0.1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['request_scope'], 'binary')
        self.assertTrue(result['data']['cache_hit'])
        self.assertEqual(result['data']['analysis']['confidence'], 'high')
        self.assertEqual(service.calls[0]['task'], 'binary')
        self.assertEqual(service.calls[0]['options']['temperature'], 0.1)
        self.assertIn('ELF utility', result['summary'])

    def test_list_provider_models_reuses_analysis_service(self):
        service = FakeAnalysisService()
        server = self._server(service)

        result = server.call_tool('list_provider_models', provider_name='ollama')

        self.assertTrue(result['ok'])
        self.assertEqual(result['request_scope'], 'provider')
        self.assertEqual(result['data']['provider_name'], 'ollama')
        self.assertIn('qwen2.5:72b-instruct', result['data']['available_models'])
        self.assertEqual(result['data']['issues'], [])

    def test_ai_tools_fail_cleanly_when_service_missing(self):
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        workspace_id = self._open(server)

        result = server.call_tool('ai_explain_function', workspace_id=workspace_id, fva='0x401000')

        self.assertFalse(result['ok'])
        self.assertIn('analysis service is not configured', result['error'])

    def test_ai_tool_errors_are_returned_structurally(self):
        server = self._server(ErrorAnalysisService())
        workspace_id = self._open(server)

        result = server.call_tool('ai_explain_function', workspace_id=workspace_id, fva='0x401000')

        self.assertFalse(result['ok'])
        self.assertIn('provider offline', result['error'])


if __name__ == '__main__':
    unittest.main()
