from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional

from .security import resolve_mutation_policy
from .server_connection import (
    ServerConnection,
    connect_to_server,
    get_remote_workspace,
)


class WorkspaceSessionError(RuntimeError):
    pass


@dataclass
class WorkspaceSession:
    workspace_id: str
    path: str
    workspace: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    connection: Optional[ServerConnection] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'workspace_id': self.workspace_id,
            'path': self.path,
            'metadata': dict(self.metadata),
        }
        if self.connection is not None:
            d['connection'] = {
                'host': self.connection.host,
                'port': self.connection.port,
                'wsname': self.connection.wsname,
            }
        return d


class WorkspaceSessionManager:
    def __init__(self, workspace_loader=None, analysis_service=None, mutation_policy=None):
        self._sessions: Dict[str, WorkspaceSession] = {}
        self._path_index: Dict[str, str] = {}
        self.workspace_loader = workspace_loader
        self.analysis_service = analysis_service
        self.mutation_policy = resolve_mutation_policy(mutation_policy)

    def _make_workspace_id(self, path: str) -> str:
        return sha256(path.encode('utf-8')).hexdigest()[:12]

    def open_workspace(self, path: str, workspace: Any = None) -> WorkspaceSession:
        existing_id = self._path_index.get(path)
        if existing_id is not None:
            return self._sessions[existing_id]
        if workspace is None:
            if self.workspace_loader is None:
                raise WorkspaceSessionError('workspace loader is not configured')
            workspace = self.workspace_loader(path)
        workspace_id = self._make_workspace_id(path)
        session = WorkspaceSession(workspace_id=workspace_id, path=path, workspace=workspace, metadata=self._metadata_for_workspace(workspace))
        self._sessions[workspace_id] = session
        self._path_index[path] = workspace_id
        return session

    def connect_server(self, host: str, port: int, wsname: str) -> WorkspaceSession:
        """Connect to a Vivisect Server and open a named workspace.

        Returns a :class:`WorkspaceSession` whose ``connection`` field
        holds the cobra proxy for server-level operations, and whose
        ``workspace`` is a remote Vivisect workspace synchronised via
        the server's event channel.
        """
        virtual_path = f"vivserver://{host}:{port}/{wsname}"
        existing_id = self._path_index.get(virtual_path)
        if existing_id is not None:
            return self._sessions[existing_id]

        server_proxy = connect_to_server(host, port)
        vw = get_remote_workspace(server_proxy, wsname)

        conn = ServerConnection(host=host, port=port, server=server_proxy, wsname=wsname)
        workspace_id = self._make_workspace_id(virtual_path)
        metadata = self._metadata_for_workspace(vw)
        metadata.update({
            'server_host': host,
            'server_port': port,
            'server_wsname': wsname,
            'server_type': 'vivremote',
        })
        session = WorkspaceSession(
            workspace_id=workspace_id,
            path=virtual_path,
            workspace=vw,
            metadata=metadata,
            connection=conn,
        )
        self._sessions[workspace_id] = session
        self._path_index[virtual_path] = workspace_id
        return session

    def get_workspace(self, workspace_id: str) -> Any:
        session = self._sessions.get(workspace_id)
        if session is None:
            raise WorkspaceSessionError(f'unknown workspace id: {workspace_id}')
        return session.workspace

    def get_session(self, workspace_id: str) -> WorkspaceSession:
        session = self._sessions.get(workspace_id)
        if session is None:
            raise WorkspaceSessionError(f'unknown workspace id: {workspace_id}')
        return session

    def list_workspaces(self) -> List[Dict[str, Any]]:
        return [session.to_dict() for session in self._sessions.values()]

    def close_workspace(self, workspace_id: str) -> bool:
        session = self._sessions.pop(workspace_id, None)
        if session is None:
            raise WorkspaceSessionError(f'unknown workspace id: {workspace_id}')
        self._path_index.pop(session.path, None)
        return True

    def _metadata_for_workspace(self, workspace: Any) -> Dict[str, Any]:
        getter = getattr(workspace, 'getMeta', lambda name: None)
        return {
            'architecture': getter('Architecture'),
            'platform': getter('Platform'),
            'format': getter('Format'),
        }
