"""Expanded tests for viv_ai/mcp/http_transport.py — RateLimiter and related."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestRateLimiter(unittest.TestCase):
    def test_initialization(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        self.assertEqual(rl.max_requests, 10)
        self.assertEqual(rl.window_seconds, 60)

    def test_is_allowed_first_request(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        handler = MagicMock()
        handler.headers = {"Authorization": "Bearer test-key"}
        handler.client_address = ("127.0.0.1", 12345)
        allowed, _ = rl.is_allowed(handler)
        self.assertTrue(allowed)

    def test_is_allowed_under_limit(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=5, window_seconds=60)
        handler = MagicMock()
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 12345)
        for _ in range(4):
            allowed, _ = rl.is_allowed(handler)
            self.assertTrue(allowed)

    def test_is_allowed_over_limit(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=2, window_seconds=60)
        handler = MagicMock()
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 12345)
        for _ in range(2):
            rl.is_allowed(handler)
        allowed, _ = rl.is_allowed(handler)
        self.assertFalse(allowed)

    def test_get_client_key_with_bearer(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        handler = MagicMock()
        handler.headers = {"Authorization": "Bearer sk-test123"}
        key = rl._get_client_key(handler)
        self.assertEqual(key, "key:sk-test123")

    def test_get_client_key_with_x_api_key(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        handler = MagicMock()
        handler.headers = {"X-API-Key": "apikey-123"}
        handler.client_address = ("10.0.0.1", 54321)
        key = rl._get_client_key(handler)
        self.assertEqual(key, "key:apikey-123")

    def test_get_client_key_fallback_to_ip(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        handler = MagicMock()
        handler.headers = {}
        handler.client_address = ("10.0.0.1", 54321)
        key = rl._get_client_key(handler)
        self.assertEqual(key, "ip:10.0.0.1")

    def test_get_client_key_empty_bearer_falls_back(self):
        from viv_ai.mcp.http_transport import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=60)
        handler = MagicMock()
        handler.headers = {"Authorization": "Bearer "}
        handler.client_address = ("10.0.0.1", 54321)
        key = rl._get_client_key(handler)
        self.assertEqual(key, "ip:10.0.0.1")


class TestBuildArgParser(unittest.TestCase):
    def test_parser_created(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        parser = build_arg_parser()
        self.assertIsNotNone(parser)

    def test_parser_default_host(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args([])
        self.assertEqual(args.host, "127.0.0.1")

    def test_parser_default_port(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args([])
        self.assertGreater(args.port, 0)

    def test_parser_has_config(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args([])
        self.assertIsNone(args.config)

    def test_parser_rate_limit_args(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args(["--rate-limit", "100", "--rate-limit-window", "30"])
        self.assertEqual(args.rate_limit, 100)
        self.assertEqual(args.rate_limit_window, 30)

    def test_parser_max_request_size(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args(["--max-request-size", "2097152"])
        self.assertEqual(args.max_request_size, 2097152)

    def test_parser_auth_args(self):
        from viv_ai.mcp.http_transport import build_arg_parser
        args = build_arg_parser().parse_args(["--auth-token-env", "MY_TOKEN", "--api-key-env", "MY_KEY"])
        self.assertEqual(args.auth_token_env, "MY_TOKEN")
        self.assertEqual(args.api_key_env, "MY_KEY")


class TestVivAIHttpHandler(unittest.TestCase):
    def test_handler_class_has_expected_methods(self):
        import viv_ai.mcp.http_transport as mod
        if hasattr(mod, 'VivAIHttpHandler'):
            handler = mod.VivAIHttpHandler
            self.assertTrue(hasattr(handler, 'do_POST'))
            self.assertTrue(hasattr(handler, 'log_message'))


if __name__ == "__main__":
    unittest.main()
