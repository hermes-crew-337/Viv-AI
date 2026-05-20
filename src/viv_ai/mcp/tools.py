from __future__ import annotations

from typing import Any, Callable, Dict

from ..extractors import extract_binary_overview, extract_function_overview
from ..graphs import summarize_graph
from ..symbolik import summarize_symbolik_paths
from .formatters import bounded, collect_exports, collect_imports, collect_names, collect_strings, collect_xrefs, parse_va
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


def get_strings(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_strings(workspace), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'strings': items, 'truncated': truncated}, provenance={'tool': 'get_strings'}, summary=f'{len(items)} strings returned').to_dict()


def get_imports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_imports(workspace), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'imports': items, 'truncated': truncated}, provenance={'tool': 'get_imports'}, summary=f'{len(items)} imports returned').to_dict()


def get_exports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_exports(workspace), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'exports': items, 'truncated': truncated}, provenance={'tool': 'get_exports'}, summary=f'{len(items)} exports returned').to_dict()


def get_names(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 64, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_names(workspace), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'names': items, 'truncated': truncated}, provenance={'tool': 'get_names'}, summary=f'{len(items)} names returned').to_dict()


def get_xrefs_to(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_xrefs(workspace, parse_va(va), 'to'), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': items, 'truncated': truncated}, provenance={'tool': 'get_xrefs_to'}, summary=f'{len(items)} xrefs-to returned').to_dict()


def get_xrefs_from(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    items, truncated = bounded(collect_xrefs(workspace, parse_va(va), 'from'), max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': items, 'truncated': truncated}, provenance={'tool': 'get_xrefs_from'}, summary=f'{len(items)} xrefs-from returned').to_dict()


def get_function_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    summary = extract_function_overview(workspace, parse_va(fva), **kwargs)
    name = summary.get('function', {}).get('name') or summary.get('function', {}).get('va')
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_summary'}, summary=f'function summary ready for {name}').to_dict()


def get_function_graph(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, max_nodes: int = 64, max_edges: int = 96, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    graph = workspace.getFunctionGraph(parse_va(fva))
    summary = summarize_graph(graph, max_nodes=max_nodes, max_edges=max_edges)
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_graph'}, summary='function graph ready').to_dict()


def get_symbolik_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, max_paths: int = 8, max_constraints: int = 8, max_effects: int = 8, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    getter = getattr(workspace, 'getSymbolikPaths', None)
    if getter is None:
        raise RuntimeError('symbolik path provider is unavailable')
    paths = getter(parse_va(fva))
    summary = summarize_symbolik_paths(paths, max_paths=max_paths, max_constraints=max_constraints, max_effects=max_effects)
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_symbolik_summary'}, summary='symbolik summary ready').to_dict()


def build_default_registry() -> Dict[str, ToolFn]:
    return {
        'workspace_open': workspace_open,
        'workspace_status': workspace_status,
        'workspace_close': workspace_close,
        'get_metadata': get_metadata,
        'get_binary_summary': get_binary_summary,
        'get_strings': get_strings,
        'get_imports': get_imports,
        'get_exports': get_exports,
        'get_names': get_names,
        'get_xrefs_to': get_xrefs_to,
        'get_xrefs_from': get_xrefs_from,
        'get_function_summary': get_function_summary,
        'get_function_graph': get_function_graph,
        'get_symbolik_summary': get_symbolik_summary,
    }
