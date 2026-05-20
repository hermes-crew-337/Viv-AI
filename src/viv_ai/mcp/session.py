from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional

from .security import resolve_mutation_policy


class WorkspaceSessionError(RuntimeError):
    pass


@dataclass
class WorkspaceSession:
    workspace_id: str
    path: str
    workspace: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'workspace_id': self.workspace_id,
            'path': self.path,
            'metadata': dict(self.metadata),
        }


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
