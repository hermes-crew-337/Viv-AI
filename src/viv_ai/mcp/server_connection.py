"""Vivisect Server connection management for Viv-AI MCP.

Provides the bridge between the MCP layer and a Vivisect Server
(cobra-based remote workspace sharing).  A remote workspace connected
this way can participate in follow-the-leader sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_VIVSERVER_PORT = 0x4074  # 16500 — canonical Vivisect Server port


@dataclass
class ServerConnection:
    """Holds the cobra proxy to a remote Vivisect Server.

    Stored on each WorkspaceSession that was opened via ``server_connect``
    so that server-level operations (``listWorkspaces()``, etc.) remain
    available after the workspace is loaded.
    """

    host: str
    port: int
    server: Any          # cobra proxy -> remote VivServer instance
    wsname: str


def connect_to_server(host: str, port: int = _VIVSERVER_PORT) -> Any:
    """Connect to a Vivisect Server and return the cobra proxy.

    The returned proxy can be used to call server-level methods
    (``listWorkspaces()``, ``getServerVersion()``) and passed to
    :func:`get_remote_workspace` to open a specific workspace.

    Raises
    ------
    Exception
        If the server is unreachable or the version is incompatible.
    """
    from vivisect.remote.server import connectToServer
    return connectToServer(host, port)


def get_remote_workspace(server: Any, wsname: str) -> Any:
    """Open a named workspace *wsname* from a Vivisect Server.

    Returns a ``VivCli`` workspace that acts as a remote client —
    all events are proxied through the server and received via
    the internal ``_clientThread``.

    The resulting workspace (``vw``) has:
      - ``vw.server`` → ``VivServerClient`` instance
      - ``vw.server.server`` → the cobra proxy for server-level calls
    """
    from vivisect.remote.server import getServerWorkspace
    return getServerWorkspace(server, wsname)


def list_server_workspaces(server: Any) -> List[str]:
    """Return the list of workspace names available on *server*."""
    return server.listWorkspaces()


def _get_server_proxy(vw: Any) -> Any:
    """Extract the cobra ``VivServer`` proxy from a remote workspace.

    Returns ``vw.server.server`` — the cobra proxy that can call
    server-level methods.

    Raises
    ------
    RuntimeError
        If *vw* is not connected to a Vivisect Server.
    """
    if vw.server is None:
        raise RuntimeError(
            "workspace is not connected to a Vivisect Server; "
            "open via server_connect first"
        )
    return vw.server.server  # VivServerClient.server -> cobra proxy


def _has_server(vw: Any) -> bool:
    """Return True if *vw* is connected to a Vivisect Server."""
    return getattr(vw, "server", None) is not None


def _is_remote_session(session: Any) -> bool:
    """Return True if the session was opened via ``server_connect``."""
    path = getattr(session, "path", "") or ""
    return path.startswith("vivserver://")
