"""Live integration tests against Ollama on MATRIX.

These tests make real HTTP calls to an actual Ollama server.
Enable with: VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1

Environment variables (with defaults):
  VIV_AI_OLLAMA_ENDPOINT = http://MATRIX:11434
  VIV_AI_OLLAMA_MODEL    = gemma4:31b
  VIV_AI_OLLAMA_TIMEOUT  = 120
"""

import os
import unittest


@unittest.skipUnless(os.getenv('VIV_AI_ENABLE_LIVE_OLLAMA_TEST') == '1', 'set VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1 to run live Ollama test')
class OllamaLiveSmokeTests(unittest.TestCase):

    def _make_provider(self):
        from viv_ai.config import ProviderConfig
        from viv_ai.providers.ollama import OllamaProvider

        endpoint = os.getenv('VIV_AI_OLLAMA_ENDPOINT', 'http://MATRIX:11434')
        model = os.getenv('VIV_AI_OLLAMA_MODEL', 'gemma4:31b')
        timeout = int(os.getenv('VIV_AI_OLLAMA_TIMEOUT', '120'))
        return OllamaProvider(ProviderConfig(
            provider_type='ollama',
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout,
        ))

    def test_live_list_models(self):
        """Verify we can reach Ollama and list available models."""
        provider = self._make_provider()
        models = provider.list_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0)

    def test_live_structured_completion(self):
        """Verify we can send a structured completion request and get a valid response."""
        provider = self._make_provider()

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

        self.assertIsInstance(result, dict)
        self.assertIn('status', result)
        self.assertIsInstance(result['status'], str)
        self.assertGreater(len(result['status']), 0)
