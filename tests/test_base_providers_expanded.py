"""Tests for viv_ai/providers/base.py — using mocking instead of concrete subclass."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestBaseProviderListModels(unittest.TestCase):
    def test_list_models_with_model(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        # Patch the abstract method so we can instantiate
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            p = BaseProvider(ProviderConfig(model="gpt-4"))
            models = p.list_models()
            self.assertEqual(models, ["gpt-4"])

    def test_list_models_without_model(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            p = BaseProvider(ProviderConfig())
            models = p.list_models()
            self.assertEqual(models, [])


class TestBaseProviderApiKey(unittest.TestCase):
    def test_api_key_from_env(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            p = BaseProvider(ProviderConfig(api_key_env="TEST_API_KEY"))
            with patch.dict('os.environ', {"TEST_API_KEY": "sk-test"}):
                key = p._api_key()
                self.assertEqual(key, "sk-test")

    def test_api_key_no_env_configured(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            p = BaseProvider(ProviderConfig())
            key = p._api_key()
            self.assertIsNone(key)

    def test_api_key_env_var_missing(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            p = BaseProvider(ProviderConfig(api_key_env="MISSING_VAR"))
            key = p._api_key()
            self.assertIsNone(key)


class TestBaseProviderHeaders(unittest.TestCase):
    def setUp(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        with patch.object(BaseProvider, '__abstractmethods__', new=set()):
            self.p = BaseProvider(ProviderConfig())

    def test_default_content_type(self):
        headers = self.p._headers()
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_extra_headers_included(self):
        headers = self.p._headers({"Authorization": "Bearer token123"})
        self.assertEqual(headers["Authorization"], "Bearer token123")

    def test_extra_overrides_content_type(self):
        headers = self.p._headers({"Content-Type": "text/plain"})
        self.assertEqual(headers["Content-Type"], "text/plain")


class TestBaseProviderCapabilities(unittest.TestCase):
    def test_default_capabilities(self):
        from viv_ai.providers.base import BaseProvider
        caps = BaseProvider.capabilities
        self.assertIsNotNone(caps)

    def test_capabilities_has_fields(self):
        from viv_ai.providers.base import BaseProvider
        import dataclasses
        caps = BaseProvider.capabilities
        fields = dataclasses.fields(caps)
        self.assertGreater(len(fields), 0)


if __name__ == "__main__":
    unittest.main()
