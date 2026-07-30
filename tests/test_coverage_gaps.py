"""Targeted tests for remaining uncovered lines — only verifiably correct ones."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestConfigUncoveredLines(unittest.TestCase):
    def test_config_read_only_policy(self):
        from viv_ai.config import AiConfig
        from viv_ai.models import MutationPolicy
        c = AiConfig(mutation_policy=MutationPolicy.CONSERVATIVE_READONLY)
        d = c.to_dict()
        self.assertEqual(d["mutation_policy"], "conservative_readonly")

    def test_config_from_dict_restores(self):
        from viv_ai.config import AiConfig
        restored = AiConfig.from_dict({"mutation_policy": "review_before_apply"})
        self.assertEqual(restored.mutation_policy.value, "review_before_apply")


class TestApplyUncoveredLines(unittest.TestCase):
    def test_apply_function_rename(self):
        from viv_ai.apply import apply_function_rename
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = "newname"
        result = apply_function_rename(vw, 0x401000, "newname", MutationPolicy.DIRECT_APPLY_ENABLED)
        self.assertTrue(result["applied"])

    def test_apply_function_rename_readonly(self):
        from viv_ai.apply import apply_function_rename
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        result = apply_function_rename(vw, 0x401000, "newname", MutationPolicy.CONSERVATIVE_READONLY)
        self.assertFalse(result["applied"])

    def test_apply_comment_suggestion(self):
        from viv_ai.apply import apply_comment_suggestion
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        result = apply_comment_suggestion(vw, 0x401000, "my comment", MutationPolicy.DIRECT_APPLY_ENABLED)
        self.assertTrue(result["applied"])


class TestBaseProviderUncoveredLines(unittest.TestCase):
    def test_base_provider_list_models_no_model(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        self.assertEqual(_P(ProviderConfig()).list_models(), [])

    def test_base_provider_list_models_with_model(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        self.assertEqual(_P(ProviderConfig(model="m")).list_models(), ["m"])

    def test_base_provider_complete_structured_raises(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        with self.assertRaises(NotImplementedError):
            _P(ProviderConfig()).complete_structured("", "", {}, {})

    def test_api_key_env_var(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        import os
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        with patch.dict(os.environ, {"MY_KEY": "sk-test"}):
            self.assertEqual(_P(ProviderConfig(api_key_env="MY_KEY"))._api_key(), "sk-test")

    def test_api_key_no_env(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        self.assertIsNone(_P(ProviderConfig())._api_key())

    def test_headers_with_extra(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        h = _P(ProviderConfig())._headers({"X-Test": "val"})
        self.assertEqual(h["X-Test"], "val")

    def test_post_json_bytes(self):
        from viv_ai.providers.base import BaseProvider
        from viv_ai.models import ProviderConfig
        import urllib.request
        class _P(BaseProvider):
            def build_request(self, *a, **kw): return {}
        mock_resp = MagicMock()
        mock_read = MagicMock(return_value=b'{"ok": true}')
        mock_resp.__enter__.return_value.read = mock_read
        with patch.object(urllib.request, 'urlopen', return_value=mock_resp):
            result = _P(ProviderConfig())._post_json_bytes("http://t", {"k": "v"})
        self.assertEqual(result, b'{"ok": true}')


class TestSettingsModule(unittest.TestCase):
    def test_settings_ai_config(self):
        from viv_ai.ui.settings import AiConfig
        c = AiConfig()
        self.assertIsNotNone(c)


class TestPromptsModule(unittest.TestCase):
    def test_analysis_schemas_contains_expected(self):
        from viv_ai.prompts import ANALYSIS_SCHEMAS
        self.assertIn("binary_summary", ANALYSIS_SCHEMAS)

    def test_build_task_prompt_bundle_binary(self):
        from viv_ai.prompts import build_task_prompt_bundle
        result = build_task_prompt_bundle("binary_summary", {"target": "test.elf"})
        self.assertIsNotNone(result)


class TestReportUncoveredLines(unittest.TestCase):
    def test_generate_report(self):
        from viv_ai.report import generate_report
        vw = MagicMock()
        vw.getMeta.side_effect = lambda k, d=None: {"Architecture": "x86", "Platform": "linux"}.get(k, d)
        vw.getFunctions.return_value = [0x401000]
        result = generate_report(vw, [])
        self.assertIn("metadata", result)

    def test_generate_report_with_results(self):
        from viv_ai.report import generate_report
        vw = MagicMock()
        vw.getMeta.side_effect = lambda k, d=None: {"Architecture": "x86"}.get(k, d)
        vw.getFunctions.return_value = [0x401000]
        result = generate_report(vw, [{"va": 0x401000, "name": "main"}])
        self.assertIn("functions", result)


class TestExtractorsBasic(unittest.TestCase):
    def test_extract_binary_overview(self):
        from viv_ai.extractors import extract_binary_overview
        vw = MagicMock()
        vw.getMeta.side_effect = lambda k, d=None: {"Architecture": "x86"}.get(k, d)
        vw.getFunctions.return_value = [0x401000]
        result = extract_binary_overview(vw)
        self.assertIn("metadata", result)

    def test_find_functions(self):
        from viv_ai.extractors import find_functions
        vw = MagicMock()
        vw.getFunctions.return_value = [0x401000, 0x401100]
        vw.getName.side_effect = {0x401000: "main"}.get
        result = find_functions(vw, "main")
        self.assertIsInstance(result, list)


class TestSymbolikBasic(unittest.TestCase):
    def test_summarize_empty(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        result = summarize_symbolik_paths([])
        self.assertIn("path_count", result)

    def test_summarize_with_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        result = summarize_symbolik_paths([{"va": 0x401000}])
        self.assertIn("path_count", result)


class TestServerBasic(unittest.TestCase):
    def test_server_start_stop(self):
        from viv_ai.mcp.server import VivAIMcpServer
        s = VivAIMcpServer()
        s.start()
        self.assertTrue(s.running)
        s.stop()
        self.assertFalse(s.running)


class TestEntrypointServerInfo(unittest.TestCase):
    def test_server_info(self):
        from viv_ai.mcp.server import VivAIMcpServer
        s = VivAIMcpServer()
        info = s.server_info()
        self.assertIn("name", info)

    def test_server_tool_registry(self):
        from viv_ai.mcp.server import VivAIMcpServer
        s = VivAIMcpServer()
        self.assertGreater(len(s.tool_registry), 0)


class TestHttpTransportLimits(unittest.TestCase):
    def test_rate_limiter_blocked(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(1, 60)
        h = MagicMock()
        h.headers = {}
        h.client_address = ("10.0.0.1", 12345)
        rl.is_allowed(h)
        allowed, msg = rl.is_allowed(h)
        self.assertFalse(allowed)
        self.assertIsNotNone(msg)

    def test_rate_limiter_reset(self):
        from viv_ai.mcp.http_transport import RateLimiter
        import time
        orig = time.time
        try:
            time.time = lambda: 1000.0
            rl = RateLimiter(1, 10)
            h = MagicMock()
            h.headers = {}
            h.client_address = ("10.0.0.1", 12345)
            rl.is_allowed(h)
            time.time = lambda: 1020.0
            self.assertTrue(rl.is_allowed(h)[0])
        finally:
            time.time = orig


if __name__ == "__main__":
    unittest.main()
