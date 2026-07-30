"""Comprehensive tests for viv_ai/mcp/session.py — WorkspaceSession and WorkspaceSessionManager."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch
import unittest


class TestWorkspaceSession(unittest.TestCase):
    def test_session_creation(self):
        from viv_ai.mcp.session import WorkspaceSession
        session = WorkspaceSession(
            workspace_id="test-001",
            path="/tmp/test.viv",
            workspace=MagicMock(),
        )
        self.assertEqual(session.workspace_id, "test-001")
        self.assertEqual(session.path, "/tmp/test.viv")

    def test_session_to_dict(self):
        from viv_ai.mcp.session import WorkspaceSession
        session = WorkspaceSession(
            workspace_id="test-001",
            path="/tmp/test.viv",
            workspace=MagicMock(),
        )
        d = session.to_dict()
        self.assertEqual(d["workspace_id"], "test-001")
        self.assertEqual(d["path"], "/tmp/test.viv")
        self.assertIsInstance(d["metadata"], dict)
        self.assertNotIn("connection", d)  # no connection

    def test_session_to_dict_with_connection(self):
        from viv_ai.mcp.session import WorkspaceSession
        from unittest.mock import MagicMock
        conn = MagicMock()
        conn.host = "localhost"
        conn.port = 16500
        conn.wsname = "test_ws"
        session = WorkspaceSession(
            workspace_id="test-001",
            path="/tmp/test.viv",
            workspace=MagicMock(),
            connection=conn,
        )
        d = session.to_dict()
        self.assertIn("connection", d)
        self.assertEqual(d["connection"]["host"], "localhost")


class TestWorkspaceSessionManager(unittest.TestCase):
    def setUp(self):
        from viv_ai.mcp.session import WorkspaceSessionManager
        self.manager = WorkspaceSessionManager()

    def test_init_sets_defaults(self):
        self.assertIsNone(self.manager.workspace_loader)
        self.assertIsNone(self.manager.analysis_service)

    def test_open_workspace_new(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        session = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        self.assertEqual(session.path, "/tmp/test.viv")

    def test_open_workspace_duplicate_returns_existing(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        session1 = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        session2 = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        self.assertEqual(session1.workspace_id, session2.workspace_id)

    def test_open_workspace_no_workspace_and_no_loader_raises(self):
        from viv_ai.mcp.session import WorkspaceSessionError
        with self.assertRaises(WorkspaceSessionError):
            self.manager.open_workspace("/tmp/nonexistent.viv")

    def test_open_workspace_with_workspace_loader(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        self.manager.workspace_loader = MagicMock(return_value=vw)
        session = self.manager.open_workspace("/tmp/test.viv")
        self.assertIsNotNone(session)

    def test_get_workspace_existing(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        session = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        got = self.manager.get_workspace(session.workspace_id)
        self.assertIs(got, vw)

    def test_get_workspace_unknown(self):
        from viv_ai.mcp.session import WorkspaceSessionError
        with self.assertRaises(WorkspaceSessionError):
            self.manager.get_workspace("nonexistent")

    def test_get_session_existing(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        session = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        got = self.manager.get_session(session.workspace_id)
        self.assertIs(got, session)

    def test_get_session_unknown(self):
        from viv_ai.mcp.session import WorkspaceSessionError
        with self.assertRaises(WorkspaceSessionError):
            self.manager.get_session("nonexistent")

    def test_list_workspaces_empty(self):
        workspaces = self.manager.list_workspaces()
        self.assertEqual(workspaces, [])

    def test_list_workspaces_with_sessions(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        workspaces = self.manager.list_workspaces()
        self.assertEqual(len(workspaces), 1)

    def test_close_workspace(self):
        vw = MagicMock()
        vw.getMeta.return_value = None
        session = self.manager.open_workspace("/tmp/test.viv", workspace=vw)
        result = self.manager.close_workspace(session.workspace_id)
        self.assertTrue(result)
        self.assertEqual(len(self.manager._sessions), 0)

    def test_close_workspace_unknown(self):
        from viv_ai.mcp.session import WorkspaceSessionError
        with self.assertRaises(WorkspaceSessionError):
            self.manager.close_workspace("nonexistent")

    def test_make_workspace_id_consistent(self):
        """Same path should produce same ID."""
        id1 = self.manager._make_workspace_id("/tmp/test.viv")
        id2 = self.manager._make_workspace_id("/tmp/test.viv")
        self.assertEqual(id1, id2)

    def test_make_workspace_id_different(self):
        id1 = self.manager._make_workspace_id("/tmp/a.viv")
        id2 = self.manager._make_workspace_id("/tmp/b.viv")
        self.assertNotEqual(id1, id2)

    def test_metadata_for_workspace(self):
        vw = MagicMock()
        def get_meta(key):
            return {"Architecture": "x86", "Platform": "linux", "Format": "elf"}.get(key)
        vw.getMeta.side_effect = get_meta
        meta = self.manager._metadata_for_workspace(vw)
        self.assertEqual(meta.get("architecture"), "x86")
        self.assertEqual(meta.get("platform"), "linux")

    def test_metadata_for_workspace_no_getmeta(self):
        """Workspace without getMeta should not crash."""
        vw = MagicMock()
        del vw.getMeta  # remove getMeta entirely
        meta = self.manager._metadata_for_workspace(vw)
        self.assertIn("architecture", meta)
        self.assertIsNone(meta["architecture"])


class TestWorkspaceSessionManagerConnectServer(unittest.TestCase):
    """Tests for connect_server method (lines 67-101)."""

    def setUp(self):
        from viv_ai.mcp.session import WorkspaceSessionManager
        self.manager = WorkspaceSessionManager()

    @patch('viv_ai.mcp.session.connect_to_server')
    @patch('viv_ai.mcp.session.get_remote_workspace')
    def test_connect_server_new(self, mock_get_ws, mock_connect):
        mock_connect.return_value = MagicMock()
        mock_ws = MagicMock()
        mock_ws.getMeta.return_value = None
        mock_get_ws.return_value = mock_ws
        session = self.manager.connect_server("localhost", 16500, "test_ws")
        self.assertIsNotNone(session)
        self.assertEqual(session.path, "vivserver://localhost:16500/test_ws")
        mock_connect.assert_called_once_with("localhost", 16500)

    @patch('viv_ai.mcp.session.connect_to_server')
    @patch('viv_ai.mcp.session.get_remote_workspace')
    def test_connect_server_duplicate_returns_existing(self, mock_get_ws, mock_connect):
        mock_connect.return_value = MagicMock()
        mock_ws = MagicMock()
        mock_ws.getMeta.return_value = None
        mock_get_ws.return_value = mock_ws
        s1 = self.manager.connect_server("localhost", 16500, "test_ws")
        s2 = self.manager.connect_server("localhost", 16500, "test_ws")
        self.assertEqual(s1.workspace_id, s2.workspace_id)
        mock_connect.assert_called_once()  # only called once

    @patch('viv_ai.mcp.session.connect_to_server')
    @patch('viv_ai.mcp.session.get_remote_workspace')
    def test_connect_server_stores_connection(self, mock_get_ws, mock_connect):
        mock_connect.return_value = MagicMock()
        mock_ws = MagicMock()
        mock_ws.getMeta.return_value = None
        mock_get_ws.return_value = mock_ws
        session = self.manager.connect_server("localhost", 16500, "test_ws")
        self.assertIsNotNone(session.connection)
        self.assertEqual(session.connection.host, "localhost")

    @patch('viv_ai.mcp.session.connect_to_server')
    @patch('viv_ai.mcp.session.get_remote_workspace')
    def test_connect_server_metadata_includes_server_info(self, mock_get_ws, mock_connect):
        mock_connect.return_value = MagicMock()
        mock_ws = MagicMock()
        mock_ws.getMeta.return_value = None
        mock_get_ws.return_value = mock_ws
        session = self.manager.connect_server("localhost", 16500, "test_ws")
        self.assertEqual(session.metadata.get("server_host"), "localhost")
        self.assertEqual(session.metadata.get("server_type"), "vivremote")

    @patch('viv_ai.mcp.session.connect_to_server')
    def test_connect_server_failure_raises(self, mock_connect):
        mock_connect.side_effect = ConnectionError("server unreachable")
        with self.assertRaises(ConnectionError):
            self.manager.connect_server("localhost", 16500, "test_ws")


if __name__ == "__main__":
    unittest.main()
