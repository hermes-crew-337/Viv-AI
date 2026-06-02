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


class CreateProviderTests(unittest.TestCase):
    def test_create_ollama(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers import create_provider
        from viv_ai.providers.ollama import OllamaProvider

        cfg = ProviderConfig(provider_type='ollama', endpoint='http://localhost:11434', model='qwen2.5')
        provider = create_provider(cfg)
        self.assertIsInstance(provider, OllamaProvider)

    def test_create_openai_compat(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers import create_provider
        from viv_ai.providers.openai_compat import OpenAICompatProvider

        cfg = ProviderConfig(provider_type='openai_compat', endpoint='https://api.openai.com/v1', model='gpt-4o')
        provider = create_provider(cfg)
        self.assertIsInstance(provider, OpenAICompatProvider)

    def test_create_anthropic(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers import create_provider
        from viv_ai.providers.anthropic import AnthropicProvider

        cfg = ProviderConfig(provider_type='anthropic', endpoint='https://api.anthropic.com', model='claude-sonnet-4')
        provider = create_provider(cfg)
        self.assertIsInstance(provider, AnthropicProvider)

    def test_create_gemini(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers import create_provider
        from viv_ai.providers.gemini import GeminiProvider

        cfg = ProviderConfig(provider_type='gemini', endpoint='https://generativelanguage.googleapis.com', model='gemini-2.0-flash')
        provider = create_provider(cfg)
        self.assertIsInstance(provider, GeminiProvider)

    def test_create_unknown_type_raises(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers import create_provider

        cfg = ProviderConfig(provider_type='nonexistent', model='foo')
        with self.assertRaises(ValueError) as ctx:
            create_provider(cfg)
        self.assertIn('nonexistent', str(ctx.exception))


class BaseProviderTests(unittest.TestCase):
    def test_list_models_returns_configured_model(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        cfg = ProviderConfig(model='my-model')
        provider = ConcreteProvider(cfg)
        self.assertEqual(provider.list_models(), ['my-model'])

    def test_list_models_empty_when_no_model(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        provider = ConcreteProvider(ProviderConfig())
        self.assertEqual(provider.list_models(), [])

    def test_complete_structured_not_implemented(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        provider = ConcreteProvider(ProviderConfig())
        with self.assertRaises(NotImplementedError):
            provider.complete_structured('test', 'prompt', {}, {'type': 'object'})

    def test_headers_default(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        provider = ConcreteProvider(ProviderConfig())
        headers = provider._headers()
        self.assertEqual(headers['Content-Type'], 'application/json')

    def test_headers_with_extra(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        provider = ConcreteProvider(ProviderConfig())
        headers = provider._headers({'Authorization': 'Bearer test'})
        self.assertEqual(headers['Authorization'], 'Bearer test')

    def test_api_key_returns_none_when_no_env(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        provider = ConcreteProvider(ProviderConfig())
        self.assertIsNone(provider._api_key())

    def test_api_key_reads_from_env(self):
        import os
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.base import BaseProvider

        class ConcreteProvider(BaseProvider):
            def build_request(self, task_type, system_prompt, user_payload, schema, options=None):
                return {}

        os.environ['VIV_AI_PROVIDER_TEST_KEY'] = 'test-key-value'
        try:
            cfg = ProviderConfig(api_key_env='VIV_AI_PROVIDER_TEST_KEY')
            provider = ConcreteProvider(cfg)
            key = provider._api_key()
            self.assertEqual(key, 'test-key-value')
        finally:
            os.environ.pop('VIV_AI_PROVIDER_TEST_KEY', None)
