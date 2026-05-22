import unittest


class PhaseARemoteProviderShapeTests(unittest.TestCase):
    def test_openai_compat_request_shape(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(ProviderConfig(
            provider_type='openai_compat',
            endpoint='https://api.example.test/v1',
            model='gpt-test',
            api_key_env='OPENAI_API_KEY',
        ))

        request = provider.build_request(
            task_type='function_summary',
            system_prompt='system prompt',
            user_payload={'function_va': '0x401000'},
            schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
            options={'temperature': 0.2},
        )

        self.assertEqual(request['model'], 'gpt-test')
        self.assertEqual(request['response_format']['type'], 'json_schema')
        self.assertEqual(request['temperature'], 0.2)
        self.assertEqual(request['messages'][0]['role'], 'system')

    def test_anthropic_request_shape(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(ProviderConfig(
            provider_type='anthropic',
            endpoint='https://api.anthropic.com',
            model='claude-sonnet-test',
            api_key_env='ANTHROPIC_API_KEY',
        ))

        request = provider.build_request(
            task_type='graph_summary',
            system_prompt='system prompt',
            user_payload={'fva': '0x401000'},
            schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
            options={'max_tokens': 2048},
        )

        self.assertEqual(request['model'], 'claude-sonnet-test')
        self.assertEqual(request['max_tokens'], 2048)
        self.assertIn('schema', request['system'])
        self.assertEqual(request['messages'][0]['role'], 'user')

    def test_gemini_request_shape(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.gemini import GeminiProvider

        provider = GeminiProvider(ProviderConfig(
            provider_type='gemini',
            endpoint='https://generativelanguage.googleapis.com',
            model='gemini-test',
            api_key_env='GEMINI_API_KEY',
        ))

        request = provider.build_request(
            task_type='binary_summary',
            system_prompt='system prompt',
            user_payload={'file': 'sample.bin'},
            schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
            options={'temperature': 0.3},
        )

        self.assertEqual(request['generationConfig']['temperature'], 0.3)
        self.assertEqual(request['generationConfig']['responseMimeType'], 'application/json')
        self.assertEqual(request['generationConfig']['responseSchema']['type'], 'object')
        self.assertEqual(request['contents'][0]['role'], 'user')
