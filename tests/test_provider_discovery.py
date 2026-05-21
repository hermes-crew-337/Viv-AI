import io
import json
import unittest
from unittest import mock


class ProviderDiscoveryTests(unittest.TestCase):
    def test_ollama_provider_lists_models_from_tags_endpoint(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.ollama import OllamaProvider

        provider = OllamaProvider(ProviderConfig(
            provider_type='ollama',
            endpoint='http://MATRIX:11434',
            model='qwen2.5:72b-instruct',
        ))

        payload = {
            'models': [
                {'name': 'qwen2.5:72b-instruct'},
                {'name': 'cas/llama-3.2-3b-instruct:latest'},
            ]
        }

        with mock.patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode('utf-8'))):
            models = provider.list_models()

        self.assertEqual(models, ['qwen2.5:72b-instruct', 'cas/llama-3.2-3b-instruct:latest'])

    def test_ai_config_validate_reports_actionable_ollama_model_guidance(self):
        from viv_ai.config import AiConfig, ProviderConfig

        cfg = AiConfig(
            default_provider='ollama',
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    endpoint='http://MATRIX:11434',
                    model='',
                )
            },
        )

        issues = cfg.validate()

        self.assertTrue(issues)
        self.assertIn('providers.ollama.model', issues[0]['field'])
        self.assertIn('/api/tags', issues[0]['hint'])
        self.assertIn('ollama list', issues[0]['hint'])

    def test_analysis_service_reports_provider_status_with_available_models(self):
        from viv_ai.config import AiConfig, ProviderConfig
        from viv_ai.service import AnalysisService

        class FakeProvider:
            def __init__(self, config):
                self.config = config

            def list_models(self):
                return ['qwen2.5:72b-instruct', 'gemma4:31b']

        cfg = AiConfig(
            default_provider='ollama',
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    endpoint='http://MATRIX:11434',
                    model='qwen2.5:72b-instruct',
                )
            },
        )
        service = AnalysisService(cfg, provider_factory=FakeProvider)

        status = service.provider_status()

        self.assertEqual(status['provider_name'], 'ollama')
        self.assertEqual(status['configured_model'], 'qwen2.5:72b-instruct')
        self.assertEqual(status['available_models'], ['qwen2.5:72b-instruct', 'gemma4:31b'])
        self.assertEqual(status['issues'], [])


if __name__ == '__main__':
    unittest.main()
