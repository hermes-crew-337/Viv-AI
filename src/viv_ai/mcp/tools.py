from __future__ import annotations

from typing import Any, Callable, Dict

from ..apply import apply_comment_suggestion as _apply_comment_suggestion, apply_function_rename as _apply_function_rename
from ..extractors import extract_binary_overview, extract_function_overview, find_functions as _find_functions
from ..graphs import summarize_graph
from ..symbolik import summarize_symbolik_paths
from .formatters import bounded, collect_exports, collect_imports, collect_names, collect_strings, collect_xrefs, parse_va
from .schemas import ToolResponse
from .security import assert_apply_allowed
from .session import WorkspaceSessionManager


ToolFn = Callable[..., Dict[str, Any]]


def _schema(properties: Dict[str, Any], required: list[str] | None = None, additional_properties: bool = False) -> Dict[str, Any]:
    return {
        'type': 'object',
        'properties': properties,
        'required': list(required or []),
        'additionalProperties': additional_properties,
    }


def build_tool_metadata() -> Dict[str, Dict[str, Any]]:
    hex_addr = {'type': ['string', 'integer'], 'description': 'Address or function VA as hex string like 0x401000 or integer.'}
    workspace_id = {'type': 'string', 'description': 'Workspace ID returned by workspace_open.'}
    max_results = {'type': 'integer', 'minimum': 1, 'description': 'Maximum number of results to return.'}
    return {
        'workspace_open': {
            'description': 'Open a binary path in a managed Vivisect workspace.',
            'inputSchema': _schema({'path': {'type': 'string', 'description': 'Filesystem path to the binary to open.'}}, ['path']),
            'annotations': {'readOnlyHint': False},
        },
        'workspace_status': {
            'description': 'Return status and metadata for an open workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'workspace_close': {
            'description': 'Close a managed workspace and release its state.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'get_metadata': {
            'description': 'Return architecture, platform, and format metadata for an open workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_binary_summary': {
            'description': 'Return a bounded overview of the current binary.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_strings': {
            'description': 'Return bounded string locations from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_imports': {
            'description': 'Return bounded imports from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_exports': {
            'description': 'Return bounded exports from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_names': {
            'description': 'Return bounded named locations from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_to': {
            'description': 'Return bounded cross references to an address.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_results}, ['workspace_id', 'va']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_from': {
            'description': 'Return bounded cross references from an address.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_results}, ['workspace_id', 'va']),
            'annotations': {'readOnlyHint': True},
        },
        'get_function_summary': {
            'description': 'Return a bounded structural summary for a function.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr}, ['workspace_id', 'fva'], additional_properties=True),
            'annotations': {'readOnlyHint': True},
        },
        'get_function_graph': {
            'description': 'Return a bounded graph summary for a function.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'max_nodes': max_results, 'max_edges': max_results}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'get_symbolik_summary': {
            'description': 'Return a bounded summary of symbolik paths for a function.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'max_paths': max_results, 'max_constraints': max_results, 'max_effects': max_results}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'find_functions': {
            'description': 'Discover functions matching optional filters (name glob, minimum caller count).',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'name_glob': {'type': 'string', 'description': 'Optional fnmatch glob pattern (e.g. "sub_*", "*crypto*", "main").'},
                'min_callers': {'type': 'integer', 'minimum': 0, 'default': 0, 'description': 'Minimum caller count to include.'},
                'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 32, 'description': 'Maximum functions to return.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'ai_explain_function': {
            'description': 'Run AI-backed explanation for a function using the server-side analysis service.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr}, ['workspace_id', 'fva'], additional_properties=True),
            'annotations': {'readOnlyHint': True},
        },
        'ai_summarize_binary': {
            'description': 'Run AI-backed binary summarization using the server-side analysis service.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id'], additional_properties=True),
            'annotations': {'readOnlyHint': True},
        },
        'ai_analyze_functions': {
            'description': 'Batch AI analysis of multiple functions in one request.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'fvas': {'type': 'array', 'items': hex_addr, 'description': 'List of function VAs to analyze (hex strings or integers).'},
            }, ['workspace_id', 'fvas']),
            'annotations': {'readOnlyHint': True},
        },
        'list_provider_models': {
            'description': 'Report the configured provider, current selected model, discovered available models, and actionable configuration issues.',
            'inputSchema': _schema({'provider_name': {'type': 'string', 'description': 'Optional configured provider name. Defaults to the server default provider.'}}, []),
            'annotations': {'readOnlyHint': True},
        },
        'propose_function_rename': {
            'description': 'Create a non-mutating function rename proposal.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'new_name': {'type': 'string', 'description': 'Proposed function name.'}}, ['workspace_id', 'fva', 'new_name']),
            'annotations': {'readOnlyHint': True},
        },
        'propose_comment': {
            'description': 'Create a non-mutating comment proposal for an address.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'comment': {'type': 'string', 'description': 'Proposed comment text.'}}, ['workspace_id', 'va', 'comment']),
            'annotations': {'readOnlyHint': True},
        },
        'apply_function_rename': {
            'description': 'Apply a function rename if server-side mutation policy permits it.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'new_name': {'type': 'string', 'description': 'New function name to apply.'}}, ['workspace_id', 'fva', 'new_name']),
            'annotations': {'readOnlyHint': False},
        },
        'apply_comment': {
            'description': 'Apply a comment if server-side mutation policy permits it.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'comment': {'type': 'string', 'description': 'Comment text to apply.'}}, ['workspace_id', 'va', 'comment']),
            'annotations': {'readOnlyHint': False},
        },
    }


def _analysis_service(manager: WorkspaceSessionManager) -> Any:
    service = getattr(manager, 'analysis_service', None)
    if service is None:
        raise RuntimeError('analysis service is not configured')
    return service


def _options_from_kwargs(kwargs: Dict[str, Any], *excluded: str) -> Dict[str, Any]:
    excluded_keys = set(excluded)
    return {key: value for key, value in kwargs.items() if key not in excluded_keys}


def _proposal(applied: bool, kind: str, va: int, field_name: str, field_value: str, reason: str) -> Dict[str, Any]:
    payload = {
        'applied': applied,
        'reason': reason,
        'proposal': {
            'kind': kind,
            'va': f'0x{va:08x}',
            field_name: field_value,
        },
    }
    return payload


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


def find_functions(manager: WorkspaceSessionManager, workspace_id: str, name_glob: str | None = None, min_callers: int = 0, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    matches = _find_functions(workspace, name_glob=name_glob, min_callers=min_callers, max_results=max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'functions': matches}, provenance={'tool': 'find_functions'}, summary=f'{len(matches)} functions matched').to_dict()


def ai_explain_function(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    result = _analysis_service(manager).analyze_function(workspace, parse_va(fva), options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'function explanation ready')
    return ToolResponse.ok(workspace_id, 'function', result, provenance={'tool': 'ai_explain_function'}, summary=summary).to_dict()


def ai_summarize_binary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    result = _analysis_service(manager).analyze_binary(workspace, options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'binary summary ready')
    return ToolResponse.ok(workspace_id, 'binary', result, provenance={'tool': 'ai_summarize_binary'}, summary=summary).to_dict()


def ai_analyze_functions(manager: WorkspaceSessionManager, workspace_id: str, fvas: list[Any], **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    parsed = [parse_va(fva) for fva in fvas]
    options = _options_from_kwargs(kwargs, 'workspace_id', 'fvas')
    results = _analysis_service(manager).analyze_functions(workspace, parsed, options=options)
    succeeded = sum(1 for r in results if 'error' not in r)
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'ai_analyze_functions'}, summary=f'analyzed {succeeded}/{len(results)} functions').to_dict()


def list_provider_models(manager: WorkspaceSessionManager, provider_name: str | None = None, **kwargs) -> Dict[str, Any]:
    result = _analysis_service(manager).provider_status(provider_name=provider_name)
    summary = f"provider {result['provider_name']} has {len(result['available_models'])} discovered models"
    return ToolResponse.ok(None, 'provider', result, provenance={'tool': 'list_provider_models'}, summary=summary).to_dict()


def propose_function_rename(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, new_name: str, **kwargs) -> Dict[str, Any]:
    proposal = _proposal(False, 'function_rename', parse_va(fva), 'name', new_name, 'proposal only')
    return ToolResponse.ok(workspace_id, 'function', proposal, provenance={'tool': 'propose_function_rename', 'mutation_policy': manager.mutation_policy.value}, summary=f'proposed rename to {new_name}').to_dict()


def propose_comment(manager: WorkspaceSessionManager, workspace_id: str, va: Any, comment: str, **kwargs) -> Dict[str, Any]:
    proposal = _proposal(False, 'comment', parse_va(va), 'comment', comment, 'proposal only')
    return ToolResponse.ok(workspace_id, 'address', proposal, provenance={'tool': 'propose_comment', 'mutation_policy': manager.mutation_policy.value}, summary='proposed comment').to_dict()


def apply_function_rename(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, new_name: str, **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = manager.get_workspace(workspace_id)
    result = _apply_function_rename(workspace, parse_va(fva), new_name, policy)
    if not result.get('applied'):
        return ToolResponse.error_response(workspace_id, 'function', result.get('reason', 'failed to apply function rename'), provenance={'tool': 'apply_function_rename', 'mutation_policy': policy.value}, warnings=[]).to_dict() | {'data': result}
    return ToolResponse.ok(workspace_id, 'function', result, provenance={'tool': 'apply_function_rename', 'mutation_policy': policy.value}, summary='function rename applied').to_dict()


def apply_comment(manager: WorkspaceSessionManager, workspace_id: str, va: Any, comment: str, **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = manager.get_workspace(workspace_id)
    result = _apply_comment_suggestion(workspace, parse_va(va), comment, policy)
    if not result.get('applied'):
        return ToolResponse.error_response(workspace_id, 'address', result.get('reason', 'failed to apply comment'), provenance={'tool': 'apply_comment', 'mutation_policy': policy.value}, warnings=[]).to_dict() | {'data': result}
    return ToolResponse.ok(workspace_id, 'address', result, provenance={'tool': 'apply_comment', 'mutation_policy': policy.value}, summary='comment applied').to_dict()


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
        'find_functions': find_functions,
        'ai_explain_function': ai_explain_function,
        'ai_summarize_binary': ai_summarize_binary,
        'ai_analyze_functions': ai_analyze_functions,
        'list_provider_models': list_provider_models,
        'propose_function_rename': propose_function_rename,
        'propose_comment': propose_comment,
        'apply_function_rename': apply_function_rename,
        'apply_comment': apply_comment,
    }
