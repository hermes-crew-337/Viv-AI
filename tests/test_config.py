import unittest


class PhaseAConfigTests(unittest.TestCase):
    def test_default_config_uses_conservative_readonly_policy(self):
        from viv_ai.config import AiConfig, MutationPolicy

        cfg = AiConfig()

        self.assertEqual(cfg.mutation_policy, MutationPolicy.CONSERVATIVE_READONLY)
        self.assertTrue(cfg.local_only)
        self.assertFalse(cfg.remote_providers_enabled)

    def test_config_round_trip_preserves_provider_and_policy(self):
        from viv_ai.config import AiConfig, MutationPolicy, ProviderConfig

        cfg = AiConfig(
            default_provider='ollama',
            default_model='qwen2.5-coder:32b-instruct',
            mutation_policy=MutationPolicy.REVIEW_BEFORE_APPLY,
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    model='qwen2.5-coder:32b-instruct',
                    endpoint='http://MATRIX:11434',
                )
            },
        )

        clone = AiConfig.from_dict(cfg.to_dict())

        self.assertEqual(clone.default_provider, 'ollama')
        self.assertEqual(clone.default_model, 'qwen2.5-coder:32b-instruct')
        self.assertEqual(clone.mutation_policy, MutationPolicy.REVIEW_BEFORE_APPLY)
        self.assertIn('ollama', clone.providers)
        self.assertEqual(clone.providers['ollama'].endpoint, 'http://MATRIX:11434')

    def test_invalid_mutation_policy_is_rejected(self):
        from viv_ai.config import AiConfig

        with self.assertRaises(ValueError):
            AiConfig.from_dict({'mutation_policy': 'definitely-not-valid'})

    def test_config_round_trip_preserves_mcp_operational_limits(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict({
            'mcp_max_concurrent_tools': 3,
            'mcp_max_tool_seconds': 17,
        })

        clone = AiConfig.from_dict(cfg.to_dict())

        self.assertEqual(clone.mcp_max_concurrent_tools, 3)
        self.assertEqual(clone.mcp_max_tool_seconds, 17)
