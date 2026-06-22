"""Tests for viv_ai/config.py — covering remaining uncovered lines (178, 234, 244)."""
from __future__ import annotations

import unittest


class TestAiConfigDefaults(unittest.TestCase):
    def test_default_mutation_policy(self):
        from viv_ai.config import AiConfig
        from viv_ai.models import MutationPolicy
        cfg = AiConfig()
        self.assertEqual(cfg.mutation_policy, MutationPolicy.CONSERVATIVE_READONLY)

    def test_default_providers(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig()
        self.assertIsInstance(cfg.providers, dict)

    def test_to_dict(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(default_provider="ollama")
        d = cfg.to_dict()
        self.assertEqual(d["default_provider"], "ollama")
        self.assertIn("mutation_policy", d)

    def test_from_dict(self):
        from viv_ai.config import AiConfig
        from viv_ai.models import MutationPolicy
        data = {"default_provider": "openai", "mutation_policy": "direct_apply_enabled"}
        cfg = AiConfig.from_dict(data)
        self.assertEqual(cfg.mutation_policy, MutationPolicy.DIRECT_APPLY_ENABLED)

    def test_line_178_providers_access(self):
        """Line 178: providers property returns dict."""
        from viv_ai.config import AiConfig
        cfg = AiConfig()
        provs = cfg.providers
        self.assertIsInstance(provs, dict)

    def test_line_234_analysis_limits(self):
        """Line 234: analysis_max_callees default."""
        from viv_ai.config import AiConfig
        cfg = AiConfig()
        self.assertIsNotNone(cfg.analysis_max_callees)

    def test_line_244_analysis_limits_default_value(self):
        """Line 244: analysis_max_callees has default."""
        from viv_ai.config import AiConfig
        cfg = AiConfig()
        self.assertGreater(cfg.analysis_max_callees, 0)


class TestAiConfigCustom(unittest.TestCase):
    def test_custom_mutation_policy(self):
        from viv_ai.config import AiConfig
        from viv_ai.models import MutationPolicy
        cfg = AiConfig(mutation_policy="direct_apply_enabled")
        self.assertEqual(cfg.mutation_policy, MutationPolicy.DIRECT_APPLY_ENABLED)

    def test_custom_providers(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(providers={"openai": {"model": "gpt-4"}})
        self.assertIn("openai", cfg.providers)

    def test_custom_default_model(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(default_model="gpt-4")
        self.assertEqual(cfg.default_model, "gpt-4")

    def test_from_dict_creates_config_with_overrides(self):
        from viv_ai.config import AiConfig
        from viv_ai.models import MutationPolicy
        data = {"default_model": "llama3", "providers": {"ollama": {"model": "llama3"}}}
        cfg = AiConfig.from_dict(data)
        self.assertEqual(cfg.default_model, "llama3")
        self.assertIn("ollama", cfg.providers)


if __name__ == "__main__":
    unittest.main()
