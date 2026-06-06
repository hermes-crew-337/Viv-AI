from __future__ import annotations

from typing import Any, Callable, Dict

from ..apply import apply_comment_suggestion as _apply_comment_suggestion, apply_function_rename as _apply_function_rename
from ..campaign import campaign_renames as _campaign_renames, campaign_comments as _campaign_comments
from ..extractors import extract_binary_overview, extract_function_overview, find_functions as _find_functions
from ..report import generate_report as _generate_report
from ..graphs import summarize_graph
from ..symbolik import summarize_symbolik_paths, get_symbolik_path_dicts
from .formatters import analysis_limits_from_config, paginated, pagination_meta, collect_exports, collect_imports, collect_names, collect_strings, collect_xrefs, parse_va
from .schemas import ToolResponse
from .security import assert_apply_allowed
from .session import WorkspaceSessionError, WorkspaceSessionManager

import threading
import time

ToolFn = Callable[..., Dict[str, Any]]


def _limits_from_manager(manager: WorkspaceSessionManager) -> dict:
    """Extract analysis limits from the manager's config, or return defaults."""
    service = getattr(manager, 'analysis_service', None)
    if service is None:
        return analysis_limits_from_config(None)
    config = getattr(service, 'config', None)
    return analysis_limits_from_config(config)


def _ensure_analyzed(workspace: Any, poll_seconds: float = 3.0) -> bool:
    """Ensure workspace analysis has started and wait briefly for results.
    
    If the workspace already has functions (analyzed or loaded with symbols),
    returns True immediately. Otherwise polls for up to *poll_seconds* for
    background analysis (started by the workspace_loader) to discover
    functions.
    
    Returns True if at least one function is available.
    """
    if workspace.getFunctions():
        return True
    deadline = time.monotonic() + poll_seconds
    while time.monotonic() < deadline:
        time.sleep(0.3)
        if workspace.getFunctions():
            return True
    return len(workspace.getFunctions()) > 0


def _trigger_analyze(workspace: Any, timeout: float = 60.0) -> int:
    """Run workspace.analyze() in a daemon thread with a timeout.
    
    Returns the number of functions discovered after analysis
    (may be partial if the timeout fires before analysis completes).
    """
    done = threading.Event()
    def _run():
        try:
            workspace.analyze()
        except Exception:
            pass
        finally:
            done.set()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    done.wait(timeout=timeout)
    return len(workspace.getFunctions())


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
    pagination_offset = {'type': 'integer', 'minimum': 0, 'default': 0, 'description': 'Number of results to skip (for pagination).'}
    pagination_limit = {'type': 'integer', 'minimum': 1, 'default': 32, 'description': 'Maximum results per page (for pagination).'}
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
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_imports': {
            'description': 'Return bounded imports from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_exports': {
            'description': 'Return bounded exports from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_names': {
            'description': 'Return bounded named locations from the workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_to': {
            'description': 'Return bounded cross references to an address.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id', 'va']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_from': {
            'description': 'Return bounded cross references from an address.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_results, 'offset': pagination_offset}, ['workspace_id', 'va']),
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
            'description': 'Discover functions matching optional filters (name glob, minimum caller count). Auto-triggers analysis if none found.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'name_glob': {'type': 'string', 'description': 'Optional fnmatch glob pattern (e.g. "sub_*", "*crypto*", "main").'},
                'min_callers': {'type': 'integer', 'minimum': 0, 'default': 0, 'description': 'Minimum caller count to include.'},
                'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 32, 'description': 'Maximum functions to return.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'analyze_workspace': {
            'description': 'Manually trigger Vivisect analysis on an open workspace. Useful for stripped binaries or re-analysis.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'timeout': {'type': 'integer', 'minimum': 5, 'default': 60, 'description': 'Max seconds to wait for analysis before returning partial results.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'workspace_analysis_status': {
            'description': 'Report analysis progress for an open workspace (function count, segments analyzed).',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'export_analysis_report': {
            'description': 'Generate a structured analysis report (metadata + function summaries + markdown).',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'results': {'type': 'array', 'items': {'type': 'object'}, 'default': [], 'description': 'Optional list of analysis results (fva, name, analysis keys) to include.'},
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
        'propose_campaign_renames': {
            'description': 'Batch propose function renames for multiple functions.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'renames': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'fva': hex_addr, 'new_name': {'type': 'string'}},
                    'required': ['fva', 'new_name'],
                }, 'description': 'List of (fva, new_name) pairs.'},
            }, ['workspace_id', 'renames']),
            'annotations': {'readOnlyHint': True},
        },
        'apply_campaign_renames': {
            'description': 'Batch apply function renames if server-side mutation policy permits.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'renames': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'fva': hex_addr, 'new_name': {'type': 'string'}},
                    'required': ['fva', 'new_name'],
                }, 'description': 'List of (fva, new_name) pairs.'},
            }, ['workspace_id', 'renames']),
            'annotations': {'readOnlyHint': False},
        },
        'propose_campaign_comments': {
            'description': 'Batch propose comments for multiple addresses.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'comments': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'va': hex_addr, 'comment': {'type': 'string'}},
                    'required': ['va', 'comment'],
                }, 'description': 'List of (va, comment) pairs.'},
            }, ['workspace_id', 'comments']),
            'annotations': {'readOnlyHint': True},
        },
        'apply_campaign_comments': {
            'description': 'Batch apply comments if server-side mutation policy permits.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'comments': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'va': hex_addr, 'comment': {'type': 'string'}},
                    'required': ['va', 'comment'],
                }, 'description': 'List of (va, comment) pairs.'},
            }, ['workspace_id', 'comments']),
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
    func_count = len(session.workspace.getFunctions()) if hasattr(session.workspace, 'getFunctions') else 0
    extras = {}
    if func_count > 0:
        extras['function_count'] = func_count
    return ToolResponse.ok(
        workspace_id=session.workspace_id,
        request_scope='workspace',
        data={'workspace_id': session.workspace_id, 'path': session.path, 'metadata': session.metadata, **extras},
        provenance={'tool': 'workspace_open'},
        summary=f'opened workspace {session.workspace_id} ({func_count} functions)',
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
    limits = _limits_from_manager(manager)
    overview = extract_binary_overview(workspace, analysis_limits=limits)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='binary',
        data=overview,
        provenance={'tool': 'get_binary_summary'},
        summary='binary summary ready',
    ).to_dict()


def _resolve_workspace(manager: WorkspaceSessionManager, workspace_id: str | None, tool_name: str) -> Any:
    """Look up a workspace and return it, or raise a clear error."""
    if not workspace_id:
        raise RuntimeError(f'{tool_name}: workspace_id is required')
    try:
        return manager.get_workspace(workspace_id)
    except WorkspaceSessionError:
        raise RuntimeError(f'{tool_name}: workspace not found or not specified: {workspace_id!r}')


def get_strings(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_strings')
    items = collect_strings(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'strings': page, 'pagination': meta}, provenance={'tool': 'get_strings'}, summary=f'{len(page)} strings returned').to_dict()


def get_imports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_imports')
    items = collect_imports(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'imports': page, 'pagination': meta}, provenance={'tool': 'get_imports'}, summary=f'{len(page)} imports returned').to_dict()


def get_exports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_exports')
    items = collect_exports(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'exports': page, 'pagination': meta}, provenance={'tool': 'get_exports'}, summary=f'{len(page)} exports returned').to_dict()


def get_names(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 64, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_names')
    items = collect_names(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'names': page, 'pagination': meta}, provenance={'tool': 'get_names'}, summary=f'{len(page)} names returned').to_dict()


def get_xrefs_to(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_xrefs_to')
    items = collect_xrefs(workspace, parse_va(va), 'to')
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': page, 'pagination': meta}, provenance={'tool': 'get_xrefs_to'}, summary=f'{len(page)} xrefs-to returned').to_dict()


def get_xrefs_from(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id, 'get_xrefs_from')
    items = collect_xrefs(workspace, parse_va(va), 'from')
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': page, 'pagination': meta}, provenance={'tool': 'get_xrefs_from'}, summary=f'{len(page)} xrefs-from returned').to_dict()


def get_function_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    limits = _limits_from_manager(manager)
    limits.update(kwargs)  # explicit per-call params override config defaults
    summary = extract_function_overview(workspace, parse_va(fva), analysis_limits=limits)
    name = summary.get('function', {}).get('name') or summary.get('function', {}).get('va')
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_summary'}, summary=f'function summary ready for {name}').to_dict()


def get_function_graph(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    limits = _limits_from_manager(manager)
    limits.update(kwargs)  # all per-call params override config defaults
    max_nodes = limits.get('max_nodes', 64)
    max_edges = limits.get('max_edges', 96)
    graph = workspace.getFunctionGraph(parse_va(fva))
    summary = summarize_graph(graph, max_nodes=max_nodes, max_edges=max_edges)
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_graph'}, summary='function graph ready').to_dict()


def get_symbolik_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    limits = _limits_from_manager(manager)
    limits.update(kwargs)  # all per-call params override config defaults
    max_paths = limits.get('max_paths', 100)
    per_path_timeout = limits.get('per_path_timeout', 30.0)
    total_timeout = limits.get('total_timeout', 120.0)
    path_dicts = get_symbolik_path_dicts(
        workspace, parse_va(fva),
        max_paths=max_paths,
        per_path_timeout=per_path_timeout,
        total_timeout=total_timeout,
    )
    max_constraints = limits.get('max_constraints', 8)
    max_effects = limits.get('max_effects', 8)
    summary = summarize_symbolik_paths(
        path_dicts,
        max_paths=max_paths,
        max_constraints=max_constraints,
        max_effects=max_effects,
    )
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_symbolik_summary'}, summary='symbolik summary ready').to_dict()


def find_functions(manager: WorkspaceSessionManager, workspace_id: str, name_glob: str | None = None, min_callers: int = 0, max_results: int = 32, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    # Auto-ensure analysis for stripped binaries: poll briefly, then
    # fall through to foreground analysis with a timeout if needed.
    if not _ensure_analyzed(workspace, poll_seconds=3.0):
        _trigger_analyze(workspace, timeout=20.0)  # fits in 30s max_tool_seconds
    limits = _limits_from_manager(manager)
    max_results = limits.get('max_results', max_results)
    matches = _find_functions(workspace, name_glob=name_glob, min_callers=min_callers, max_results=max_results)
    return ToolResponse.ok(workspace_id, 'workspace', {'functions': matches}, provenance={'tool': 'find_functions'}, summary=f'{len(matches)} functions matched').to_dict()


def analyze_workspace(manager: WorkspaceSessionManager, workspace_id: str, timeout: int = 60, **kwargs) -> Dict[str, Any]:
    """Manually trigger Vivisect analysis on an open workspace.
    
    Runs vw.analyze() with a configurable timeout in a worker thread.
    Useful for stripped binaries where the initial background analysis
    may not have completed, or when re-analysis is desired after renames.
    """
    workspace = manager.get_workspace(workspace_id)
    func_before = len(workspace.getFunctions())
    func_after = _trigger_analyze(workspace, timeout=float(timeout))
    new_funcs = func_after - func_before
    return ToolResponse.ok(
        workspace_id, 'workspace',
        {'functions_before': func_before, 'functions_after': func_after, 'new_functions': max(0, new_funcs)},
        provenance={'tool': 'analyze_workspace'},
        summary=f'analysis completed: {func_after} functions (discovered {new_funcs} new)',
    ).to_dict()


def workspace_analysis_status(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """Report analysis status for an open workspace.
    
    Returns the number of functions discovered so far (useful for
    checking background analysis progress on stripped binaries).
    """
    workspace = manager.get_workspace(workspace_id)
    func_count = len(workspace.getFunctions())
    return ToolResponse.ok(
        workspace_id, 'workspace',
        {'function_count': func_count},
        provenance={'tool': 'workspace_analysis_status'},
        summary=f'{func_count} functions discovered',
    ).to_dict()


def export_analysis_report(manager: WorkspaceSessionManager, workspace_id: str, results: list | None = None, **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    report = _generate_report(workspace, results=results or [])
    return ToolResponse.ok(workspace_id, 'workspace', report, provenance={'tool': 'export_analysis_report'}, summary='analysis report ready').to_dict()


def _check_provider_available(manager: WorkspaceSessionManager) -> str | None:
    """Check if an AI provider is configured and usable.

    Only validates when the service carries a real ``AiConfig`` with a
    ``providers`` dict.  Duck-typed test fakes (no ``config`` attr) are
    let through — they will fail on their own if they need a provider.

    Returns None if OK, or a user-facing error message string if not.
    """
    service = getattr(manager, 'analysis_service', None)
    if service is None:
        return 'analysis service is not configured'
    config = getattr(service, 'config', None)
    if config is None:
        return None  # duck-typed fake — let it fail naturally if needed
    if not config.providers:
        return 'no AI providers configured. Set up Ollama or an API provider in config.'
    name = config.default_provider
    if not name:
        return 'no default AI provider configured. Set default_provider in config.'
    if name not in config.providers:
        return f'default provider {name!r} is not configured. Check provider definitions in config.'
    return None


def ai_explain_function(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    err = _check_provider_available(manager)
    if err:
        return ToolResponse.error_response(workspace_id, 'function', err, provenance={'tool': 'ai_explain_function'}).to_dict()
    workspace = manager.get_workspace(workspace_id)
    result = _analysis_service(manager).analyze_function(workspace, parse_va(fva), options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'function explanation ready')
    return ToolResponse.ok(workspace_id, 'function', result, provenance={'tool': 'ai_explain_function'}, summary=summary).to_dict()


def ai_summarize_binary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    err = _check_provider_available(manager)
    if err:
        return ToolResponse.error_response(workspace_id, 'binary', err, provenance={'tool': 'ai_summarize_binary'}).to_dict()
    workspace = manager.get_workspace(workspace_id)
    result = _analysis_service(manager).analyze_binary(workspace, options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'binary summary ready')
    return ToolResponse.ok(workspace_id, 'binary', result, provenance={'tool': 'ai_summarize_binary'}, summary=summary).to_dict()


def ai_analyze_functions(manager: WorkspaceSessionManager, workspace_id: str, fvas: list[Any], **kwargs) -> Dict[str, Any]:
    err = _check_provider_available(manager)
    if err:
        return ToolResponse.error_response(workspace_id, 'function', err, provenance={'tool': 'ai_analyze_functions'}).to_dict()
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


def propose_campaign_renames(manager: WorkspaceSessionManager, workspace_id: str, renames: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    workspace = manager.get_workspace(workspace_id)
    parsed = [{'fva': parse_va(item['fva']), 'new_name': str(item['new_name'])} for item in renames]
    results = _campaign_renames(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'propose_campaign_renames', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} renames proposed').to_dict()


def apply_campaign_renames(manager: WorkspaceSessionManager, workspace_id: str, renames: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = manager.get_workspace(workspace_id)
    parsed = [{'fva': parse_va(item['fva']), 'new_name': str(item['new_name'])} for item in renames]
    results = _campaign_renames(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'apply_campaign_renames', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} renames applied').to_dict()


def propose_campaign_comments(manager: WorkspaceSessionManager, workspace_id: str, comments: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    workspace = manager.get_workspace(workspace_id)
    parsed = [{'va': parse_va(item['va']), 'comment': str(item['comment'])} for item in comments]
    results = _campaign_comments(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'address', {'results': results}, provenance={'tool': 'propose_campaign_comments', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} comments proposed').to_dict()


def apply_campaign_comments(manager: WorkspaceSessionManager, workspace_id: str, comments: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = manager.get_workspace(workspace_id)
    parsed = [{'va': parse_va(item['va']), 'comment': str(item['comment'])} for item in comments]
    results = _campaign_comments(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'address', {'results': results}, provenance={'tool': 'apply_campaign_comments', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} comments applied').to_dict()


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
        'analyze_workspace': analyze_workspace,
        'workspace_analysis_status': workspace_analysis_status,
        'export_analysis_report': export_analysis_report,
        'ai_explain_function': ai_explain_function,
        'ai_summarize_binary': ai_summarize_binary,
        'ai_analyze_functions': ai_analyze_functions,
        'list_provider_models': list_provider_models,
        'propose_function_rename': propose_function_rename,
        'propose_comment': propose_comment,
        'apply_function_rename': apply_function_rename,
        'apply_comment': apply_comment,
        'propose_campaign_renames': propose_campaign_renames,
        'apply_campaign_renames': apply_campaign_renames,
        'propose_campaign_comments': propose_campaign_comments,
        'apply_campaign_comments': apply_campaign_comments,
    }
