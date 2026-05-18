import unittest
from unittest import mock


class PhaseAServiceTests(unittest.TestCase):
    def test_ollama_request_shape_uses_raw_schema_format_compatible_with_matrix_ollama(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.ollama import OllamaProvider

        provider = OllamaProvider(ProviderConfig(
            provider_type='ollama',
            endpoint='http://MATRIX:11434',
            model='qwen2.5:72b-instruct',
        ))

        request = provider.build_request(
            task_type='function_summary',
            system_prompt='system prompt',
            user_payload={'function_va': '0x401000'},
            schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
            options={'temperature': 0.1},
        )

        self.assertEqual(request['model'], 'qwen2.5:72b-instruct')
        self.assertEqual(request['format']['type'], 'object')
        self.assertEqual(request['format']['properties']['summary']['type'], 'string')
        self.assertEqual(request['options']['temperature'], 0.1)
        self.assertIn('system prompt', request['messages'][0]['content'])

    def test_ollama_complete_structured_parses_json_response(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.ollama import OllamaProvider

        provider = OllamaProvider(ProviderConfig(
            provider_type='ollama',
            endpoint='http://MATRIX:11434',
            model='qwen2.5:72b-instruct',
        ))

        fake_json = b'{"message": {"content": "{\\"summary\\": \\"ok\\"}"}, "done": true}'

        with mock.patch.object(provider, '_post_json_bytes', return_value=fake_json):
            result = provider.complete_structured(
                task_type='function_summary',
                system_prompt='system prompt',
                user_payload={'function_va': '0x401000'},
                schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
                options={},
            )

        self.assertEqual(result['summary'], 'ok')
