"""Tests for viv_ai/mcp/server.py — matching the actual ToolResponse format."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestVivAIMcpServerInit(unittest.TestCase):
    def test_init_defaults(self):
        from viv_ai.mcp.server import VivAIMcpServer
        server = VivAIMcpServer()
        self.assertFalse(server.running)
        self.assertGreater(len(server.tool_registry), 0)
        self.assertIsNotNone(server.session_manager)

    def test_init_with_session_manager(self):
        from viv_ai.mcp.server import VivAIMcpServer
        from viv_ai.mcp.session import WorkspaceSessionManager
        sm = WorkspaceSessionManager()
        server = VivAIMcpServer(session_manager=sm)
        self.assertIs(server.session_manager, sm)

    def test_init_with_tool_registry(self):
        from viv_ai.mcp.server import VivAIMcpServer
        fn = MagicMock(return_value={"ok": True, "data": {}})
        registry = {"test_tool": fn}
        server = VivAIMcpServer(tool_registry=registry)
        self.assertIn("test_tool", server.tool_registry)

    def test_init_with_read_only_true(self):
        from viv_ai.mcp.server import VivAIMcpServer
        from viv_ai.models import MutationPolicy
        server = VivAIMcpServer(read_only=True)
        self.assertEqual(server.session_manager.mutation_policy, MutationPolicy.CONSERVATIVE_READONLY)

    def test_init_with_read_only_false(self):
        from viv_ai.mcp.server import VivAIMcpServer
        from viv_ai.models import MutationPolicy
        server = VivAIMcpServer(read_only=False)
        self.assertEqual(server.session_manager.mutation_policy, MutationPolicy.DIRECT_APPLY_ENABLED)

    def test_init_with_max_concurrent_tools(self):
        from viv_ai.mcp.server import VivAIMcpServer
        server = VivAIMcpServer(max_concurrent_tools=8)
        self.assertEqual(server.max_concurrent_tools, 8)

    def test_init_with_max_tool_seconds(self):
        from viv_ai.mcp.server import VivAIMcpServer
        server = VivAIMcpServer(max_tool_seconds=120.0)
        self.assertEqual(server.max_tool_seconds, 120.0)


class TestVivAIMcpServerLifecycle(unittest.TestCase):
    def setUp(self):
        from viv_ai.mcp.server import VivAIMcpServer
        self.server = VivAIMcpServer()

    def test_start_sets_running(self):
        info = self.server.start()
        self.assertTrue(self.server.running)
        self.assertIn("tools", info)

    def test_stop_clears_running(self):
        self.server.start()
        info = self.server.stop()
        self.assertFalse(self.server.running)
        self.assertIn("tools", info)

    def test_server_info_returns_dict(self):
        info = self.server.server_info()
        self.assertIn("name", info)
        self.assertEqual(info["name"], "viv_ai_mcp")
        self.assertIn("tools", info)
        self.assertIn("tool_metadata", info)
        self.assertIn("limits", info)

    def test_server_info_includes_mutation_policy(self):
        info = self.server.server_info()
        self.assertIn("mutation_policy", info)
        self.assertIn("read_only", info)


class TestVivAIMcpServerCallTool(unittest.TestCase):
    def setUp(self):
        from viv_ai.mcp.server import VivAIMcpServer
        self.server = VivAIMcpServer(max_tool_seconds=30)

    def test_call_known_tool(self):
        """Known tool returns its result as-is."""
        fn = MagicMock(return_value={"ok": True, "data": {"result": "works"}})
        self.server.tool_registry["my_tool"] = fn
        result = self.server.call_tool("my_tool")
        self.assertTrue(result["ok"])

    def test_call_unknown_tool_returns_error_dict(self):
        result = self.server.call_tool("nonexistent")
        self.assertIn("error", result)
        self.assertFalse(result["ok"])

    def test_call_tool_with_arguments(self):
        fn = MagicMock(return_value={"ok": True, "data": {}})
        self.server.tool_registry["greet"] = fn
        self.server.call_tool("greet", name="world")
        fn.assert_called_once()
        _, kwargs = fn.call_args
        self.assertIn("name", kwargs)


class TestVivAIMcpServerToolErrorHandling(unittest.TestCase):
    def setUp(self):
        from viv_ai.mcp.server import VivAIMcpServer
        self.server = VivAIMcpServer(max_tool_seconds=30)

    def test_tool_raises_exception_returns_error_dict(self):
        fn = MagicMock(side_effect=ValueError("bad data"))
        self.server.tool_registry["failing"] = fn
        result = self.server.call_tool("failing")
        self.assertIn("error", result)
        self.assertFalse(result["ok"])

    def test_tool_returns_none(self):
        """When tool returns None, result is None (no post-check in sync path)."""
        fn = MagicMock(return_value=None)
        self.server.tool_registry["null_tool"] = fn
        result = self.server.call_tool("null_tool")
        self.assertIsNone(result)


class TestToolTimeout(unittest.TestCase):
    def test_time_limit_context_manager_no_sigalrm(self):
        """On systems without SIGALRM, _time_limit is a no-op."""
        from viv_ai.mcp.server import _time_limit
        with _time_limit(30.0):
            result = "worked"
        self.assertEqual(result, "worked")


if __name__ == "__main__":
    unittest.main()
