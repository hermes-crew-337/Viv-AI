"""Tests for viv_ai.mcp.security — mutation policy resolution and enforcement."""

import unittest


class ResolveMutationPolicyTests(unittest.TestCase):
    def test_none_returns_conservative_readonly(self):
        from viv_ai.mcp.security import resolve_mutation_policy
        from viv_ai.models import MutationPolicy
        self.assertEqual(resolve_mutation_policy(None), MutationPolicy.CONSERVATIVE_READONLY)

    def test_policy_passthrough(self):
        from viv_ai.mcp.security import resolve_mutation_policy
        from viv_ai.models import MutationPolicy
        policy = MutationPolicy.DIRECT_APPLY_ENABLED
        self.assertIs(resolve_mutation_policy(policy), policy)

    def test_string_conversion(self):
        from viv_ai.mcp.security import resolve_mutation_policy
        from viv_ai.models import MutationPolicy
        self.assertEqual(resolve_mutation_policy('direct_apply_enabled'), MutationPolicy.DIRECT_APPLY_ENABLED)
        self.assertEqual(resolve_mutation_policy('review_before_apply'), MutationPolicy.REVIEW_BEFORE_APPLY)
        self.assertEqual(resolve_mutation_policy('conservative_readonly'), MutationPolicy.CONSERVATIVE_READONLY)

    def test_invalid_string_raises(self):
        from viv_ai.mcp.security import resolve_mutation_policy
        with self.assertRaises(ValueError):
            resolve_mutation_policy('invalid_policy')


class AssertApplyAllowedTests(unittest.TestCase):
    def test_conservative_readonly_raises(self):
        from viv_ai.mcp.security import assert_apply_allowed
        from viv_ai.models import MutationPolicy
        with self.assertRaises(RuntimeError) as ctx:
            assert_apply_allowed(MutationPolicy.CONSERVATIVE_READONLY)
        self.assertIn('readonly', str(ctx.exception))

    def test_review_before_apply_raises(self):
        from viv_ai.mcp.security import assert_apply_allowed
        from viv_ai.models import MutationPolicy
        with self.assertRaises(RuntimeError) as ctx:
            assert_apply_allowed(MutationPolicy.REVIEW_BEFORE_APPLY)
        self.assertIn('review', str(ctx.exception))

    def test_direct_apply_enabled_passes(self):
        from viv_ai.mcp.security import assert_apply_allowed
        from viv_ai.models import MutationPolicy
        # Should not raise
        assert_apply_allowed(MutationPolicy.DIRECT_APPLY_ENABLED)


class AssertProviderAllowedTests(unittest.TestCase):
    def test_local_only_config_blocks_remote_provider(self):
        from viv_ai.mcp.security import assert_provider_allowed
        from viv_ai.config import AiConfig
        from viv_ai.models import ProviderCapabilities
        config = AiConfig(local_only=True, remote_providers_enabled=True)

        class RemoteProvider:
            capabilities = ProviderCapabilities(local_only=False)

        with self.assertRaises(RuntimeError) as ctx:
            assert_provider_allowed(config, RemoteProvider())
        self.assertIn('local-only', str(ctx.exception))

    def test_remote_disabled_blocks_remote_provider(self):
        from viv_ai.mcp.security import assert_provider_allowed
        from viv_ai.config import AiConfig
        from viv_ai.models import ProviderCapabilities
        config = AiConfig(local_only=False, remote_providers_enabled=False)

        class RemoteProvider:
            capabilities = ProviderCapabilities(local_only=False)

        with self.assertRaises(RuntimeError) as ctx:
            assert_provider_allowed(config, RemoteProvider())
        self.assertIn('disabled', str(ctx.exception))

    def test_local_provider_allowed_in_local_only_mode(self):
        from viv_ai.mcp.security import assert_provider_allowed
        from viv_ai.config import AiConfig
        from viv_ai.models import ProviderCapabilities
        config = AiConfig(local_only=True, remote_providers_enabled=True)

        class LocalProvider:
            capabilities = ProviderCapabilities(local_only=True)

        # Should not raise
        assert_provider_allowed(config, LocalProvider())

    def test_local_provider_allowed_in_remote_disabled_mode(self):
        from viv_ai.mcp.security import assert_provider_allowed
        from viv_ai.config import AiConfig
        from viv_ai.models import ProviderCapabilities
        config = AiConfig(local_only=False, remote_providers_enabled=False)

        class LocalProvider:
            capabilities = ProviderCapabilities(local_only=True)

        # Should not raise
        assert_provider_allowed(config, LocalProvider())

    def test_remote_provider_allowed_when_configured(self):
        from viv_ai.mcp.security import assert_provider_allowed
        from viv_ai.config import AiConfig
        from viv_ai.models import ProviderCapabilities
        config = AiConfig(local_only=False, remote_providers_enabled=True)

        class RemoteProvider:
            capabilities = ProviderCapabilities(local_only=False)

        # Should not raise
        assert_provider_allowed(config, RemoteProvider())
