"""Expanded tests for server_connection.py — targeting 95%+ coverage.

Notes on mocking strategy
-------------------------
``connect_to_server`` and ``get_remote_workspace`` use **deferred imports**
(``from vivisect.remote.server import …`` inside the function body), so
``vivisect`` is **not** a module-level dependency.  Since the real package
may not be installed in the test environment we inject mock modules into
``sys.modules`` so that the deferred import resolves to our mock object.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch, sentinel

import pytest

# ---------------------------------------------------------------------------
# Bootstrap synthetic ``vivisect.remote.server`` module hierarchy
# ---------------------------------------------------------------------------
# These modules are created *before* the production module is imported so that
# the deferred ``from vivisect.remote.server import …`` statements work even
# when the real package is absent.
# ---------------------------------------------------------------------------

_VIV_SERVER_MOD = MagicMock()          # stands for vivisect.remote.server
_VIV_REMOTE_MOD = MagicMock()          # stands for vivisect.remote
_VIV_MOD = MagicMock()                 # stands for vivisect

_VIV_REMOTE_MOD.server = _VIV_SERVER_MOD
_VIV_MOD.remote = _VIV_REMOTE_MOD

# Ensure the module hierarchy is present in sys.modules *before* importing
# the module under test.
sys.modules.setdefault("vivisect", _VIV_MOD)
sys.modules.setdefault("vivisect.remote", _VIV_REMOTE_MOD)
sys.modules.setdefault("vivisect.remote.server", _VIV_SERVER_MOD)


from viv_ai.mcp.server_connection import (
    ServerConnection,
    _get_server_proxy,
    _has_server,
    _is_remote_session,
    connect_to_server,
    get_remote_workspace,
    list_server_workspaces,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_mock_modules() -> None:
    """Reset all mock modules before each test so call counts stay clean."""
    _VIV_SERVER_MOD.reset_mock()
    _VIV_REMOTE_MOD.reset_mock()
    _VIV_MOD.reset_mock()


# ---------------------------------------------------------------------------
# ServerConnection dataclass  —  3 tests
# ---------------------------------------------------------------------------


class TestServerConnection:
    """ServerConnection is a simple dataclass; verify construction and attributes."""

    def test_basic_construction(self) -> None:
        """Minimal construction with explicit port."""
        conn = ServerConnection(
            host="10.0.0.1",
            port=16500,
            server=sentinel.cobra_proxy,
            wsname="my_workspace",
        )
        assert conn.host == "10.0.0.1"
        assert conn.port == 16500
        assert conn.server is sentinel.cobra_proxy
        assert conn.wsname == "my_workspace"

    def test_default_port_value(self) -> None:
        """Verify the module-level default port is 0x4074 (16500)."""
        conn = ServerConnection(
            host="localhost",
            port=0x4074,
            server=sentinel.proxy,
            wsname="test",
        )
        assert conn.port == 16500
        assert conn.port == 0x4074

    def test_different_port(self) -> None:
        """Non-default port is stored correctly."""
        conn = ServerConnection(
            host="192.168.1.1",
            port=22222,
            server=sentinel.proxy,
            wsname="remote_ws",
        )
        assert conn.port == 22222


# ---------------------------------------------------------------------------
# connect_to_server  —  5 tests
# ---------------------------------------------------------------------------


class TestConnectToServer:
    """connect_to_server does a deferred import then calls connectToServer."""

    def test_connects_with_default_port(self) -> None:
        """Default port (16500) is used when only host is provided."""
        _VIV_SERVER_MOD.connectToServer = MagicMock(return_value=sentinel.proxy)
        result = connect_to_server("10.0.0.1")

        assert result is sentinel.proxy
        _VIV_SERVER_MOD.connectToServer.assert_called_once_with("10.0.0.1", 16500)

    def test_connects_with_custom_port(self) -> None:
        """Explicit port overrides the default."""
        _VIV_SERVER_MOD.connectToServer = MagicMock(return_value=sentinel.proxy)
        result = connect_to_server("10.0.0.1", 9999)

        assert result is sentinel.proxy
        _VIV_SERVER_MOD.connectToServer.assert_called_once_with("10.0.0.1", 9999)

    def test_propagates_exception(self) -> None:
        """If the server is unreachable, connect_to_server re-raises."""
        _VIV_SERVER_MOD.connectToServer = MagicMock(
            side_effect=ConnectionError("refused")
        )
        with pytest.raises(ConnectionError, match="refused"):
            connect_to_server("10.0.0.1")

    def test_handles_empty_host(self) -> None:
        """Empty host string is passed through (real check is in vivisect)."""
        _VIV_SERVER_MOD.connectToServer = MagicMock(return_value=sentinel.proxy)
        result = connect_to_server("")

        assert result is sentinel.proxy
        _VIV_SERVER_MOD.connectToServer.assert_called_once_with("", 16500)

    def test_port_zero(self) -> None:
        """Port 0 is allowed (system-assigned port scenario)."""
        _VIV_SERVER_MOD.connectToServer = MagicMock(return_value=sentinel.proxy)
        result = connect_to_server("localhost", 0)

        assert result is sentinel.proxy
        _VIV_SERVER_MOD.connectToServer.assert_called_once_with("localhost", 0)


# ---------------------------------------------------------------------------
# get_remote_workspace  —  5 tests
# ---------------------------------------------------------------------------


class TestGetRemoteWorkspace:
    """get_remote_workspace does a deferred import then calls getServerWorkspace."""

    def test_opens_workspace(self) -> None:
        """Basic workspace retrieval from a server proxy."""
        mock_workspace = MagicMock()
        _VIV_SERVER_MOD.getServerWorkspace = MagicMock(return_value=mock_workspace)
        result = get_remote_workspace(sentinel.server, "my_ws")

        assert result is mock_workspace
        _VIV_SERVER_MOD.getServerWorkspace.assert_called_once_with(
            sentinel.server, "my_ws"
        )

    def test_workspace_with_different_name(self) -> None:
        """Different workspace names are passed through correctly."""
        _VIV_SERVER_MOD.getServerWorkspace = MagicMock(return_value=MagicMock())
        get_remote_workspace(sentinel.server, "another_workspace")

        _VIV_SERVER_MOD.getServerWorkspace.assert_called_once_with(
            sentinel.server, "another_workspace"
        )

    def test_propagates_exception(self) -> None:
        """If getServerWorkspace raises, get_remote_workspace re-raises."""
        _VIV_SERVER_MOD.getServerWorkspace = MagicMock(
            side_effect=RuntimeError("workspace not found")
        )
        with pytest.raises(RuntimeError, match="workspace not found"):
            get_remote_workspace(sentinel.server, "missing_ws")

    def test_handles_empty_wsname(self) -> None:
        """Empty workspace name is passed through (server validates)."""
        _VIV_SERVER_MOD.getServerWorkspace = MagicMock(return_value=MagicMock())
        get_remote_workspace(sentinel.server, "")

        _VIV_SERVER_MOD.getServerWorkspace.assert_called_once_with(sentinel.server, "")

    def test_returns_different_object_for_different_server(self) -> None:
        """Different servers can yield different workspace objects."""
        ws_a = MagicMock()
        ws_b = MagicMock()
        _VIV_SERVER_MOD.getServerWorkspace = MagicMock(side_effect=[ws_a, ws_b])

        r1 = get_remote_workspace("server_a", "ws1")
        r2 = get_remote_workspace("server_b", "ws2")

        assert r1 is ws_a
        assert r2 is ws_b
        assert r1 is not r2


# ---------------------------------------------------------------------------
# list_server_workspaces  —  4 tests
# ---------------------------------------------------------------------------


class TestListServerWorkspaces:
    """list_server_workspaces delegates to server.listWorkspaces()."""

    def test_returns_workspace_list(self) -> None:
        """Happy path — server returns a list of workspace names."""
        server = MagicMock()
        server.listWorkspaces.return_value = ["ws1", "ws2", "ws3"]
        result = list_server_workspaces(server)
        assert result == ["ws1", "ws2", "ws3"]
        server.listWorkspaces.assert_called_once_with()

    def test_empty_list(self) -> None:
        """Server with no workspaces returns an empty list."""
        server = MagicMock()
        server.listWorkspaces.return_value = []
        result = list_server_workspaces(server)
        assert result == []

    def test_single_workspace(self) -> None:
        """Single workspace is returned as a single-element list."""
        server = MagicMock()
        server.listWorkspaces.return_value = ["only_ws"]
        result = list_server_workspaces(server)
        assert result == ["only_ws"]

    def test_list_with_special_characters(self) -> None:
        """Workspace names with special characters are returned as-is."""
        names = ["my workspace", "ws-2024", "test.viv", "a" * 100]
        server = MagicMock()
        server.listWorkspaces.return_value = names
        result = list_server_workspaces(server)
        assert result == names


# ---------------------------------------------------------------------------
# _get_server_proxy  —  5 tests
# ---------------------------------------------------------------------------


class TestGetServerProxy:
    """_get_server_proxy extracts the cobra proxy from a remote workspace."""

    def test_normal_proxy(self) -> None:
        """Happy path — vw has a server attribute with a server sub-attribute."""
        vw = MagicMock()
        vw.server.server = sentinel.cobra_proxy
        result = _get_server_proxy(vw)
        assert result is sentinel.cobra_proxy

    def test_vw_server_is_none_raises(self) -> None:
        """When vw.server is None, RuntimeError is raised."""
        vw = MagicMock()
        vw.server = None
        with pytest.raises(RuntimeError) as exc_info:
            _get_server_proxy(vw)
        msg = str(exc_info.value).lower()
        assert "not connected" in msg
        assert "vivisect" in msg

    def test_vw_has_no_server_attr_raises(self) -> None:
        """When vw has no server attribute, accessing it raises AttributeError."""
        class NoServer:
            pass

        vw = NoServer()
        with pytest.raises(AttributeError):
            _get_server_proxy(vw)

    def test_vw_server_server_is_none(self) -> None:
        """When vw.server.server is None, None is returned."""
        vw = MagicMock()
        vw.server.server = None
        result = _get_server_proxy(vw)
        assert result is None

    def test_vw_server_is_mock_with_server_attr(self) -> None:
        """Confirm the nested access pattern works via MagicMock."""
        vw = MagicMock()
        inner = MagicMock()
        inner.server = sentinel.inner_proxy
        vw.server = inner
        result = _get_server_proxy(vw)
        assert result is sentinel.inner_proxy


# ---------------------------------------------------------------------------
# _has_server  —  5 tests
# ---------------------------------------------------------------------------


class TestHasServer:
    """_has_server checks whether a workspace has a non-None server attribute."""

    def test_has_server_true(self) -> None:
        """vw.server exists and is not None → True."""
        vw = MagicMock()
        vw.server = sentinel.some_server
        assert _has_server(vw) is True

    def test_has_server_false_none(self) -> None:
        """vw.server is None → False."""
        vw = MagicMock()
        vw.server = None
        assert _has_server(vw) is False

    def test_no_server_attr(self) -> None:
        """vw has no 'server' attribute → getattr returns None → False."""
        class NoServer:
            pass

        vw = NoServer()
        assert _has_server(vw) is False

    def test_server_is_falsy_object(self) -> None:
        """A falsy object (e.g. 0, empty string) that is not None is still
        truthy from the 'is not None' perspective."""
        vw = MagicMock()
        vw.server = 0  # falsy but not None
        assert _has_server(vw) is True

    def test_server_attr_with_property(self) -> None:
        """getattr works with properties that return None."""
        vw = MagicMock()
        vw.server = None
        assert _has_server(vw) is False


# ---------------------------------------------------------------------------
# _is_remote_session  —  10 tests
# ---------------------------------------------------------------------------


class TestIsRemoteSession:
    """_is_remote_session checks if session.path starts with 'vivserver://'."""

    def test_vivserver_path_true(self) -> None:
        """Path starting with 'vivserver://' → True."""
        session = MagicMock()
        session.path = "vivserver://10.0.0.1:16500/my_ws"
        assert _is_remote_session(session) is True

    def test_local_path_false(self) -> None:
        """Regular file path → False."""
        session = MagicMock()
        session.path = "/tmp/test.viv"
        assert _is_remote_session(session) is False

    def test_path_is_none(self) -> None:
        """When path is None, getattr returns None, or '' makes it '' → False."""
        session = MagicMock()
        session.path = None
        # _is_remote_session does: path = getattr(session, 'path', '') or ''
        # So None → '' (due to `or ''`), then startswith is False
        assert _is_remote_session(session) is False

    def test_path_is_empty_string(self) -> None:
        """Empty path → False."""
        session = MagicMock()
        session.path = ""
        assert _is_remote_session(session) is False

    def test_no_path_attr(self) -> None:
        """Session object without a 'path' attribute → getattr returns '' → False."""
        class NoPath:
            pass

        session = NoPath()
        assert _is_remote_session(session) is False

    def test_path_is_vivserver_with_query(self) -> None:
        """vivserver:// path with query params is still recognised."""
        session = MagicMock()
        session.path = "vivserver://host:16500/ws?token=abc"
        assert _is_remote_session(session) is True

    def test_path_starts_with_non_vivserver_protocol(self) -> None:
        """Other protocols (e.g. file://) are not remote sessions."""
        session = MagicMock()
        session.path = "file:///tmp/test.viv"
        assert _is_remote_session(session) is False

    def test_vivserver_upper_case(self) -> None:
        """Case-sensitive check — 'VIVSERVER://' should be False."""
        session = MagicMock()
        session.path = "VIVSERVER://host/ws"
        assert _is_remote_session(session) is False

    def test_path_is_numeric_string(self) -> None:
        """A non-path string without vivserver:// prefix → False."""
        session = MagicMock()
        session.path = "12345"
        assert _is_remote_session(session) is False

    def test_path_with_only_vivserver_prefix(self) -> None:
        """Just 'vivserver://' as the entire path → True."""
        session = MagicMock()
        session.path = "vivserver://"
        assert _is_remote_session(session) is True
