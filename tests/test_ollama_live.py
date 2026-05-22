import os
import unittest


@unittest.skipUnless(os.getenv('VIV_AI_ENABLE_LIVE_OLLAMA_TEST') == '1', 'set VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1 to run live Ollama test')
class OllamaLiveSmokeTests(unittest.TestCase):
    def test_live_ollama_structured_completion(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.ollama import OllamaProvider

        endpoint = os.getenv('VIV_AI_OLLAMA_ENDPOINT', 'http://MATRIX:11434')
        model = os.getenv('VIV_AI_OLLAMA_MODEL', 'qwen2.5:72b-instruct')
        provider = OllamaProvider(ProviderConfig(
            provider_type='ollama',
            endpoint=endpoint,
            model=model,
            timeout_seconds=int(os.getenv('VIV_AI_OLLAMA_TIMEOUT', '120')),
        ))

        result = provider.complete_structured(
            task_type='connectivity_probe',
            system_prompt='Return a minimal JSON object confirming connectivity.',
            user_payload={'probe': 'viv_ai_live_test'},
            schema={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'model': {'type': 'string'},
                },
                'required': ['status'],
            },
            options={'temperature': 0},
        )

        self.assertIn('status', result)
