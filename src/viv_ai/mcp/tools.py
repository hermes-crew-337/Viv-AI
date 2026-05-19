from __future__ import annotations

from typing import Any, Callable, Dict

from ..extractors import extract_binary_overview
from .schemas import ToolResponse
from .session import WorkspaceSessionManager


ToolFn = Callable[..., Dict[str, Any]]


def workspace_open(manager: WorkspaceSessionManager, path: str, workspace: Any = None, **kwargs) -> Dict[str, Any]:
    session = manager.open_workspace(path, workspace=workspace)
    return ToolResponse.ok(
        workspace_id=session.workspace_id,
        request_scope='workspace',
        data={'workspace_id': session.workspace_id, 'path': session.path, 'metadata': session.metadata},
        provenance={'tool': 'workspace_open'},
        summary=f'opened workspace {session.workspace_id}',
    ).to_dict()


def workspace_status(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    session = manager.get_session(workspace_id)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='workspace',
        data={'workspace': session.to_dict()},
        provenance={'tool': 'workspace_status'},
        summary=f'workspace {workspace_id} ready',
    ).to_dict()


def workspace_close(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    manager.close_workspace(workspace_id)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='workspace',
        data={'workspace_id': workspace_id, 'closed': True},
        provenance={'tool': 'workspace_close'},
        summary=f'closed workspace {workspace_id}',
    ).to_dict()


def get_metadata(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    session = manager.get_session(workspace_id)
    metadata = dict(session.metadata)
    summary = f"{metadata.get('platform')} {metadata.get('architecture')} {metadata.get('format')} workspace"
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='workspace',
        data={'metadata': metadata},
        provenance={'tool': 'get_metadata'},
        summary=summary,
    ).to_dict()


def get_binary_summary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    overview = extract_binary_overview(workspace)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='binary',
        data=overview,
        provenance={'tool': 'get_binary_summary'},
        summary='binary summary ready',
    ).to_dict()


def build_default_registry() -> Dict[str, ToolFn]:
    return {
        'workspace_open': workspace_open,
        'workspace_status': workspace_status,
        'workspace_close': workspace_close,
        'get_metadata': get_metadata,
        'get_binary_summary': get_binary_summary,
    }
