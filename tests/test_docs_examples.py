"""Phase P Task 7: Validate doc example configs deserialize and validate correctly.

Extracts representative JSON config snippets matching docs/provider-configuration.md
and verifies they produce valid AiConfig objects.
"""

import json
import unittest
import tempfile
from pathlib import Path


# Inline canonical examples matching docs/provider-configuration.md
DOC_EXAMPLES = {
    "minimal-ollama": {
        "default_provider": "ollama",
        "default_model": "qwen2.5:72b-instruct",
        "providers": {
            "ollama": {
                "provider_type": "ollama",
                "endpoint": "http://127.0.0.1:11434",
                "model": "qwen2.5:72b-instruct",
            }
        },
    },
    "openrouter": {
        "default_provider": "openrouter",
        "default_model": "anthropic/claude-3.7-sonnet",
        "providers": {
            "openrouter": {
                "provider_type": "openai",
                "endpoint": "https://openrouter.ai/api/v1",
                "model": "anthropic/claude-3.7-sonnet",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        },
    },
    "anthropic": {
        "default_provider": "anthropic",
        "default_model": "claude-sonnet-4-20250514",
        "providers": {
            "anthropic": {
                "provider_type": "anthropic",
                "endpoint": "https://api.anthropic.com/v1",
                "model": "claude-sonnet-4-20250514",
                "api_key_env": "ANTHROPIC_API_KEY",
            }
        },
    },
    "gemini": {
        "default_provider": "gemini",
        "default_model": "gemini-2.5-pro",
        "providers": {
            "gemini": {
                "provider_type": "google",
                "endpoint": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.5-pro",
                "api_key_env": "GEMINI_API_KEY",
            }
        },
    },
    "safe-local-setup": {
        "local_only": True,
        "remote_providers_enabled": False,
    },
    "remote-enabled-setup": {
        "local_only": False,
        "remote_providers_enabled": True,
    },
}


class DocExampleValidationTests(unittest.TestCase):
    """Validate that documented JSON config examples are valid AiConfig inputs."""

    def test_all_examples_deserialize_successfully(self):
        from viv_ai.config import AiConfig

        for name, data in DOC_EXAMPLES.items():
            with self.subTest(name=name):
                cfg = AiConfig.from_dict(data)
                self.assertIsInstance(cfg, AiConfig)
                if "default_provider" in data:
                    self.assertEqual(cfg.default_provider, data["default_provider"],
                                     f"{name}: default_provider mismatch")
                if "default_model" in data:
                    self.assertEqual(cfg.default_model, data["default_model"],
                                     f"{name}: default_model mismatch")

    def test_minimal_ollama_config_parses_providers(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["minimal-ollama"])
        self.assertIn("ollama", cfg.providers)
        ollama = cfg.providers["ollama"]
        self.assertEqual(ollama.provider_type, "ollama")
        self.assertEqual(ollama.endpoint, "http://127.0.0.1:11434")
        self.assertEqual(ollama.model, "qwen2.5:72b-instruct")

    def test_openrouter_config_has_api_key_env(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["openrouter"])
        self.assertIn("openrouter", cfg.providers)
        self.assertEqual(cfg.providers["openrouter"].api_key_env, "OPENROUTER_API_KEY")

    def test_anthropic_config_has_api_key_env(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["anthropic"])
        self.assertIn("anthropic", cfg.providers)
        self.assertEqual(cfg.providers["anthropic"].api_key_env, "ANTHROPIC_API_KEY")

    def test_gemini_config_has_api_key_env(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["gemini"])
        self.assertIn("gemini", cfg.providers)
        self.assertEqual(cfg.providers["gemini"].api_key_env, "GEMINI_API_KEY")

    def test_safe_local_setup_disables_remote(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["safe-local-setup"])
        self.assertTrue(cfg.local_only)
        self.assertFalse(cfg.remote_providers_enabled)

    def test_remote_enabled_setup_allows_remote(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict(DOC_EXAMPLES["remote-enabled-setup"])
        self.assertFalse(cfg.local_only)
        self.assertTrue(cfg.remote_providers_enabled)

    def test_examples_round_trip_through_file(self):
        """Write example to disk, load via AiConfig.load(), verify fidelity."""
        from viv_ai.config import AiConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            for name, data in DOC_EXAMPLES.items():
                if not data:
                    continue
                with self.subTest(name=name):
                    path = Path(tmpdir) / f"{name}.json"
                    cfg1 = AiConfig.from_dict(data)
                    cfg1.save(path)
                    cfg2 = AiConfig.load(path)
                    self.assertEqual(cfg1.default_provider, cfg2.default_provider)
                    self.assertEqual(cfg1.default_model, cfg2.default_model)
                    self.assertEqual(cfg1.local_only, cfg2.local_only)
                    self.assertEqual(cfg1.remote_providers_enabled, cfg2.remote_providers_enabled)
                    if data.get("providers"):
                        for pname in data["providers"]:
                            self.assertIn(pname, cfg2.providers)
                            self.assertEqual(
                                cfg1.providers[pname].endpoint,
                                cfg2.providers[pname].endpoint,
                            )
