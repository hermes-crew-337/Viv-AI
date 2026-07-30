"""Tests for viv_ai.models — model dataclasses and enums."""

import unittest


class MutationPolicyTests(unittest.TestCase):
    def test_enum_values(self):
        from viv_ai.models import MutationPolicy
        self.assertEqual(MutationPolicy.CONSERVATIVE_READONLY.value, 'conservative_readonly')
        self.assertEqual(MutationPolicy.REVIEW_BEFORE_APPLY.value, 'review_before_apply')
        self.assertEqual(MutationPolicy.DIRECT_APPLY_ENABLED.value, 'direct_apply_enabled')

    def test_enum_members_are_distinct(self):
        from viv_ai.models import MutationPolicy
        members = list(MutationPolicy)
        self.assertEqual(len(members), 3)


class ProviderCapabilitiesTests(unittest.TestCase):
    def test_default_values(self):
        from viv_ai.models import ProviderCapabilities
        caps = ProviderCapabilities()
        self.assertTrue(caps.supports_json_mode)
        self.assertFalse(caps.supports_tools)
        self.assertFalse(caps.local_only)
        self.assertIsNone(caps.max_context)

    def test_custom_values(self):
        from viv_ai.models import ProviderCapabilities
        caps = ProviderCapabilities(supports_json_mode=False, supports_tools=True, local_only=True, max_context=8192)
        self.assertFalse(caps.supports_json_mode)
        self.assertTrue(caps.supports_tools)
        self.assertTrue(caps.local_only)
        self.assertEqual(caps.max_context, 8192)


class ProviderConfigTests(unittest.TestCase):
    def test_default_values(self):
        from viv_ai.models import ProviderConfig
        cfg = ProviderConfig()
        self.assertEqual(cfg.provider_type, 'ollama')
        self.assertEqual(cfg.model, '')
        self.assertEqual(cfg.endpoint, '')
        self.assertIsNone(cfg.api_key_env)
        self.assertEqual(cfg.timeout_seconds, 60)
        self.assertEqual(cfg.extra, {})

    def test_to_dict_roundtrip(self):
        from viv_ai.models import ProviderConfig
        cfg = ProviderConfig(
            provider_type='anthropic',
            model='claude-sonnet-4',
            endpoint='https://api.anthropic.com',
            api_key_env='ANTHROPIC_API_KEY',
            timeout_seconds=120,
            extra={'temperature': 0},
        )
        d = cfg.to_dict()
        self.assertEqual(d['provider_type'], 'anthropic')
        self.assertEqual(d['model'], 'claude-sonnet-4')
        self.assertEqual(d['endpoint'], 'https://api.anthropic.com')
        self.assertEqual(d['api_key_env'], 'ANTHROPIC_API_KEY')
        self.assertEqual(d['timeout_seconds'], 120)
        self.assertEqual(d['extra'], {'temperature': 0})

    def test_from_dict_full(self):
        from viv_ai.models import ProviderConfig
        data = {
            'provider_type': 'openai_compat',
            'model': 'gpt-4o',
            'endpoint': 'https://api.openai.com/v1',
            'api_key_env': 'OPENAI_API_KEY',
            'timeout_seconds': 90,
            'extra': {'organization_id': 'org-123'},
        }
        cfg = ProviderConfig.from_dict(data)
        self.assertEqual(cfg.provider_type, 'openai_compat')
        self.assertEqual(cfg.endpoint, 'https://api.openai.com/v1')
        self.assertEqual(cfg.api_key_env, 'OPENAI_API_KEY')
        self.assertEqual(cfg.extra, {'organization_id': 'org-123'})

    def test_from_dict_minimal(self):
        from viv_ai.models import ProviderConfig
        cfg = ProviderConfig.from_dict({})
        self.assertEqual(cfg.provider_type, 'ollama')
        self.assertEqual(cfg.model, '')
        self.assertEqual(cfg.timeout_seconds, 60)
        self.assertEqual(cfg.extra, {})

    def test_from_dict_none(self):
        from viv_ai.models import ProviderConfig
        cfg = ProviderConfig.from_dict(None)
        self.assertEqual(cfg.provider_type, 'ollama')


class StructuredCompletionRequestTests(unittest.TestCase):
    def test_fields(self):
        from viv_ai.models import StructuredCompletionRequest
        req = StructuredCompletionRequest(
            task_type='fn_summary',
            system_prompt='analyze this',
            user_payload={'va': 0x401000},
            schema={'type': 'object'},
            options={'temperature': 0},
        )
        self.assertEqual(req.task_type, 'fn_summary')
        self.assertEqual(req.system_prompt, 'analyze this')
        self.assertEqual(req.user_payload, {'va': 0x401000})
        self.assertEqual(req.schema, {'type': 'object'})
        self.assertEqual(req.options, {'temperature': 0})


class StructuredCompletionResultTests(unittest.TestCase):
    def test_fields(self):
        from viv_ai.models import StructuredCompletionResult
        result = StructuredCompletionResult(
            content={'summary': 'hello'},
            raw_response={'model': 'test', 'usage': {}},
        )
        self.assertEqual(result.content, {'summary': 'hello'})
        self.assertEqual(result.raw_response['model'], 'test')
