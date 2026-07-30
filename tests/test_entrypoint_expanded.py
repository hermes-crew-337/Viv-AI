"""Tests for viv_ai/mcp/entrypoint.py — entrypoint functions. 
VivAIMcpServer is imported from .server, not .entrypoint."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestBuildArgParser(unittest.TestCase):
    def test_build_arg_parser_returns_parser(self):
        from viv_ai.mcp.entrypoint import build_arg_parser
        parser = build_arg_parser()
        self.assertIsNotNone(parser)
        self.assertTrue(hasattr(parser, 'parse_args'))

    def test_parser_has_config_flag(self):
        from viv_ai.mcp.entrypoint import build_arg_parser
        args = build_arg_parser().parse_args([])
        self.assertIsNone(args.config)


class TestParseRequest(unittest.TestCase):
    def test_parse_valid_json(self):
        from viv_ai.mcp.entrypoint import _parse_request
        request, error = _parse_request('{"method": "ping", "id": 1}')
        self.assertIsNotNone(request)
        self.assertIsNone(error)
        self.assertEqual(request["method"], "ping")

    def test_parse_invalid_json(self):
        from viv_ai.mcp.entrypoint import _parse_request
        request, error = _parse_request('not json')
        self.assertIsNone(request)
        self.assertIsNotNone(error)
        self.assertIn("parse error", error.get("error", {}).get("message", ""))

    def test_parse_non_dict_json(self):
        from viv_ai.mcp.entrypoint import _parse_request
        request, error = _parse_request('["array", "not", "object"]')
        self.assertIsNone(request)
        self.assertIsNotNone(error)
        self.assertIn("invalid request", error.get("error", {}).get("message", ""))


class TestHandleRequest(unittest.TestCase):
    def setUp(self):
        from viv_ai.mcp.server import VivAIMcpServer
        self.server = VivAIMcpServer()

    def test_ping_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "ping"})
        self.assertEqual(response["result"], {})

    def test_initialize_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "initialize"})
        self.assertIn("serverInfo", response["result"])

    def test_tools_list_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "tools/list"})
        self.assertIn("tools", response["result"])

    def test_server_info_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "server/info"})
        self.assertIn("name", response["result"])

    def test_shutdown_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        server = MagicMock()
        response, keep = _handle_request(server, {"id": 1, "method": "shutdown"})
        server.stop.assert_called_once()
        self.assertFalse(keep)

    def test_unknown_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "foobar"})
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32601)

    def test_invalid_params(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "ping", "params": "not_a_dict"})
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32602)

    def test_tools_call_method(self):
        from viv_ai.mcp.entrypoint import _handle_request
        response, keep = _handle_request(self.server, {"id": 1, "method": "tools/call", "params": {"name": "list_workspaces", "arguments": {}}})
        self.assertIn("result", response)


class TestServeOnce(unittest.TestCase):
    def test_serve_once_processes_request(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer
        import io
        server = VivAIMcpServer()
        instream = io.StringIO('{"method": "ping", "id": 1}\n')
        outstream = io.StringIO()
        result = serve_once(server, instream, outstream)
        self.assertTrue(result)
        output = outstream.getvalue()
        self.assertIn("jsonrpc", output)

    def test_serve_once_empty_line_returns_false(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer
        import io
        server = VivAIMcpServer()
        instream = io.StringIO('')
        outstream = io.StringIO()
        result = serve_once(server, instream, outstream)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
