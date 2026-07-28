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
from .server_connection import _get_server_proxy, _has_server

import threading
import time
import uuid as uuid_mod

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


def _validate_server_mode(vw) -> None:
    """Raise RuntimeError if *vw* is not connected to a Vivisect Server."""
    if not _has_server(vw):
        raise RuntimeError(
            'workspace is not connected to a Vivisect Server; '
            'use server_connect first'
        )


def _validate_mode(manager: WorkspaceSessionManager, for_local: bool) -> None:
    """Raise RuntimeError if the server's mode forbids the operation.

    Args:
        manager: the session manager (carries the ``mode`` attribute).
        for_local: True when the caller wants to open a local file;
                   False when it wants a remote server connection.
    """
    mode = getattr(manager, 'mode', 'hybrid')
    if for_local and mode == 'remote':
        raise RuntimeError(f'cannot open local workspace: server is in {mode!r} mode (use --mode hybrid or --mode local)')
    if not for_local and mode == 'local':
        raise RuntimeError(f'cannot connect to remote server: server is in {mode!r} mode (use --mode hybrid or --mode remote)')


def _get_or_create_leader_uuid(session) -> str:
    """Return the active leader UUID from session metadata, or create one."""
    uid = session.metadata.get('leader_uuid')
    if uid is None:
        uid = uuid_mod.uuid4().hex
        session.metadata['leader_uuid'] = uid
    return uid


def _clear_leader_uuid(session) -> None:
    """Remove leader UUID from session metadata."""
    session.metadata.pop('leader_uuid', None)


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
    max_items = {'type': 'integer', 'minimum': 1, 'default': 32, 'description': 'Maximum number of items to return.'}
    max_nodes = {'type': 'integer', 'minimum': 1, 'default': 64, 'description': 'Maximum number of nodes to include in the graph summary.'}
    max_edges = {'type': 'integer', 'minimum': 1, 'default': 96, 'description': 'Maximum number of edges to include in the graph summary.'}
    max_paths = {'type': 'integer', 'minimum': 1, 'default': 100, 'description': 'Maximum number of symbolik paths to trace.'}
    max_constraints = {'type': 'integer', 'minimum': 1, 'default': 8, 'description': 'Maximum constraints to show per symbolik path.'}
    max_effects = {'type': 'integer', 'minimum': 1, 'default': 8, 'description': 'Maximum effects to show per symbolik path.'}
    pagination_offset = {'type': 'integer', 'minimum': 0, 'default': 0, 'description': 'Number of results to skip (for pagination).'}
    pagination_limit = {'type': 'integer', 'minimum': 1, 'default': 32, 'description': 'Maximum results per page (for pagination).'}
    override_kwargs = {
        'type': 'string',
        'description': 'Extra key=value overrides for config-based analysis_limits (e.g. per_path_timeout=15, total_timeout=60, max_constraints=10, max_effects=10, model=gpt-4o). Passed directly to the analysis service. Use for per-call tweaks without modifying config.',
    }
    return {
        'workspace_open': {
            'description': 'Open a binary at a file path in a managed Vivisect workspace. Analysis starts automatically in the background.',
            'inputSchema': _schema({'path': {'type': 'string', 'description': 'Filesystem path to the binary to open.'}}, ['path']),
            'annotations': {'readOnlyHint': False},
        },
        'workspace_status': {
            'description': 'Return status and metadata for an open workspace by its workspace_id.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'workspace_close': {
            'description': 'Close a managed workspace and release its state.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'list_workspaces': {
            'description': 'List all currently open workspaces with their IDs, paths, and metadata.',
            'inputSchema': _schema({}, []),
            'annotations': {'readOnlyHint': True},
        },
        'get_metadata': {
            'description': 'Return architecture (e.g. x86-64), platform (e.g. linux), and file format (e.g. ELF64) for an open workspace.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_binary_summary': {
            'description': 'Return an overview of the binary: entry points, imports, exports, strings, and top functions (sorted by caller count). Each section is limited to configurable maximums.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_strings': {
            'description': 'Return string locations from the workspace, paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_imports': {
            'description': 'Return imports from the workspace, paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_exports': {
            'description': 'Return exports from the workspace, paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_names': {
            'description': 'Return named locations from the workspace, paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_to': {
            'description': 'Return cross-references pointing TO an address (who calls or references this address). Paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id', 'va']),
            'annotations': {'readOnlyHint': True},
        },
        'get_xrefs_from': {
            'description': 'Return cross-references FROM an address (what this address calls or references). Paginated.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'max_results': max_items, 'offset': pagination_offset}, ['workspace_id', 'va']),
            'annotations': {'readOnlyHint': True},
        },
        'get_function_summary': {
            'description': 'Return a structural summary for a function: callers, callees, cross-references to imports and strings, a disassembly slice, and graph block/link stats.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'kwargs': override_kwargs}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'get_function_graph': {
            'description': 'Return a summarised control-flow graph for a function with configurable node/edge limits.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'max_nodes': max_nodes, 'max_edges': max_edges}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'get_symbolik_summary': {
            'description': 'Return summarised symbolic-execution (symbolik) paths for a function. Vivisect traces each path through the function and reports constraints and effects. Paths are ordered longest-first.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'max_paths': max_paths, 'max_constraints': max_constraints, 'max_effects': max_effects}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'find_functions': {
            'description': 'Discover functions matching optional filters (name glob, minimum caller count). Auto-triggers analysis on stripped binaries if no functions are found yet.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'name_glob': {'type': 'string', 'description': 'Optional fnmatch glob pattern (e.g. "sub_*", "*crypto*", "main").'},
                'min_callers': {'type': 'integer', 'minimum': 0, 'default': 0, 'description': 'Minimum caller count to include.'},
                'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 32, 'description': 'Maximum functions to return.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'analyze_workspace': {
            'description': 'Manually trigger Vivisect analysis on an open workspace. Useful for stripped binaries or re-analysis after renames.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'timeout': {'type': 'integer', 'minimum': 5, 'default': 60, 'description': 'Max seconds to wait for analysis before returning partial results.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'workspace_analysis_status': {
            'description': 'Report analysis progress for an open workspace — number of functions discovered so far. Use on stripped binaries to poll for background analysis completion.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'export_analysis_report': {
            'description': 'Generate a structured analysis report with metadata, function summaries, and markdown. Optionally pass pre-computed results.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'results': {'type': 'array', 'items': {'type': 'object', 'properties': {'fva': {'type': 'string'}, 'name': {'type': 'string'}, 'summary': {'type': 'string'}}}, 'default': [], 'description': 'Optional list of result objects, each with fva, name, and summary keys.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'ai_explain_function': {
            'description': 'Run AI-backed explanation for a single function using the configured LLM provider.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'kwargs': override_kwargs}, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': True},
        },
        'ai_summarize_binary': {
            'description': 'Run AI-backed binary summarization using the configured LLM provider.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'kwargs': override_kwargs}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'ai_analyze_functions': {
            'description': 'Batch AI analysis of multiple functions in a single request. Pass an array of function VAs.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'fvas': {'type': 'array', 'items': hex_addr, 'description': 'List of function VAs to analyze (hex strings like "0x401000" or integers).'},
            }, ['workspace_id', 'fvas']),
            'annotations': {'readOnlyHint': True},
        },
        'list_provider_models': {
            'description': 'Report the configured provider, current selected model, discovered available models, and actionable configuration issues.',
            'inputSchema': _schema({'provider_name': {'type': 'string', 'description': 'Optional configured provider name. Defaults to the server default provider.'}}, []),
            'annotations': {'readOnlyHint': True},
        },
        'propose_function_rename': {
            'description': 'Create a non-mutating function rename proposal (safe to call under any mutation policy — does not modify the workspace).',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'new_name': {'type': 'string', 'description': 'Proposed function name.'}}, ['workspace_id', 'fva', 'new_name']),
            'annotations': {'readOnlyHint': True},
        },
        'propose_comment': {
            'description': 'Create a non-mutating comment proposal for an address (safe to call under any mutation policy).',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'comment': {'type': 'string', 'description': 'Proposed comment text.'}}, ['workspace_id', 'va', 'comment']),
            'annotations': {'readOnlyHint': True},
        },
        'apply_function_rename': {
            'description': 'Apply a function rename. Requires mutation policy to be `direct_apply_enabled` or `review_before_apply` with prior approval.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'fva': hex_addr, 'new_name': {'type': 'string', 'description': 'New function name to apply.'}}, ['workspace_id', 'fva', 'new_name']),
            'annotations': {'readOnlyHint': False},
        },
        'apply_comment': {
            'description': 'Apply a comment at an address. Requires mutation policy to be `direct_apply_enabled` or `review_before_apply` with prior approval.',
            'inputSchema': _schema({'workspace_id': workspace_id, 'va': hex_addr, 'comment': {'type': 'string', 'description': 'Comment text to apply.'}}, ['workspace_id', 'va', 'comment']),
            'annotations': {'readOnlyHint': False},
        },
        'propose_campaign_renames': {
            'description': 'Batch propose function renames for multiple functions (non-mutating, safe under any policy).',
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
            'description': 'Batch apply function renames. Requires mutation policy to be `direct_apply_enabled` or `review_before_apply` with prior approval.',
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
            'description': 'Batch propose comments for multiple addresses (non-mutating, safe under any policy).',
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
            'description': 'Batch apply comments. Requires mutation policy to be `direct_apply_enabled` or `review_before_apply` with prior approval.',
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
        'server_connect': {
            'description': 'Connect to a Vivisect Server and open a remote workspace by name. Returns a workspace_id that can be used with all other tools.',
            'inputSchema': _schema({
                'host': {'type': 'string', 'description': 'Vivisect Server hostname or IP.'},
                'port': {'type': 'integer', 'default': 0x4074, 'description': 'Server port (default 16500).'},
                'wsname': {'type': 'string', 'description': 'Workspace name on the server (e.g. "my_workspace.viv").'},
            }, ['host', 'wsname']),
            'annotations': {'readOnlyHint': False},
        },
        'server_disconnect': {
            'description': 'Disconnect from a remote workspace and clean up any active leader session.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'server_list_workspaces': {
            'description': 'List all workspaces available on the Vivisect Server that a remote workspace is connected to.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'leader_start': {
            'description': 'Declare this MCP session as a leader on the remote workspace. Connected followers can opt in to follow the AI analyst\'s navigation.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'session_name': {'type': 'string', 'default': 'AI Analysis Session', 'description': 'Display name followers will see in their leader menu.'},
                'initial_location': {'type': 'string', 'default': '0x0', 'description': 'Starting VA expression (e.g. "0x401000").'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_navigate': {
            'description': 'Broadcast a navigation event to all followers. Their GUI views (memory, funcgraph) will jump to the specified address.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'location_expr': {'type': 'string', 'description': 'Address expression (e.g. "0x401000", "main+5").'},
            }, ['workspace_id', 'location_expr']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_end': {
            'description': 'End the active leader session. Followers will no longer receive navigation events.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_list': {
            'description': 'Return all active leader sessions on the remote workspace (other analysts who are leading).',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'leader_get_location': {
            'description': 'Return the current navigated location of a leader session.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'session_uuid': {'type': 'string', 'description': 'Optional UUID of a specific leader session. Defaults to this session\'s own leader UUID.'},
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'leader_chat': {
            'description': 'Send a chat message to all users connected to the remote workspace. Message appears in their Vivisect chat window.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'message': {'type': 'string', 'description': 'Chat message text to broadcast.'},
            }, ['workspace_id', 'message']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_explain_and_navigate': {
            'description': 'Combined workflow: analyze a function with AI, navigate all followers to it, and deliver the explanation via chat.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'fva': hex_addr,
                'kwargs': override_kwargs,
            }, ['workspace_id', 'fva']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_annotate': {
            'description': 'Set a workspace comment at a VA as the AI leader. Followers see annotations directly in their disassembly view.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'va': hex_addr,
                'text': {'type': 'string', 'description': 'Annotation text to set as a comment on this address.'},
            }, ['workspace_id', 'va', 'text']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_status': {
            'description': 'Return aggregate status of the AI leader session: session name, current location, all leader sessions on the workspace, and chat activity.',
            'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
            'annotations': {'readOnlyHint': True},
        },
        'leader_explain_binary': {
            'description': 'Combined workflow: AI-summarize the binary, navigate followers to the entry point, and deliver the summary via chat.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'kwargs': override_kwargs,
            }, ['workspace_id']),
            'annotations': {'readOnlyHint': False},
        },
        'leader_explain_graph': {
            'description': 'Combined workflow: AI-analyze a function\'s control-flow graph, navigate followers to it, and deliver the analysis via chat.',
            'inputSchema': _schema({
                'workspace_id': workspace_id,
                'fva': hex_addr,
                'kwargs': override_kwargs,
            }, ['workspace_id', 'fva']),
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
    _validate_mode(manager, for_local=True)
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


def list_workspaces(manager: WorkspaceSessionManager, **kwargs) -> Dict[str, Any]:
    sessions = manager.list_workspaces()
    return ToolResponse.ok(
        None,
        request_scope='workspace',
        data={'workspaces': sessions},
        provenance={'tool': 'list_workspaces'},
        summary=f'{len(sessions)} open workspaces',
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
    workspace = _resolve_workspace(manager, workspace_id)
    limits = _limits_from_manager(manager)
    overview = extract_binary_overview(workspace, analysis_limits=limits)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='binary',
        data=overview,
        provenance={'tool': 'get_binary_summary'},
        summary='binary summary ready',
    ).to_dict()


def _resolve_workspace(manager: WorkspaceSessionManager, workspace_id: str | None) -> Any:
    """Look up a workspace and return it, or raise a clear error."""
    if not workspace_id:
        raise RuntimeError('workspace_id is required')
    try:
        return manager.get_workspace(workspace_id)
    except WorkspaceSessionError:
        raise RuntimeError(f'workspace not found: {workspace_id!r}')


def get_strings(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_strings(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'strings': page, 'pagination': meta}, provenance={'tool': 'get_strings'}, summary=f'{len(page)} strings returned').to_dict()


def get_imports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_imports(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'imports': page, 'pagination': meta}, provenance={'tool': 'get_imports'}, summary=f'{len(page)} imports returned').to_dict()


def get_exports(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_exports(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'exports': page, 'pagination': meta}, provenance={'tool': 'get_exports'}, summary=f'{len(page)} exports returned').to_dict()


def get_names(manager: WorkspaceSessionManager, workspace_id: str, max_results: int = 64, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_names(workspace)
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'names': page, 'pagination': meta}, provenance={'tool': 'get_names'}, summary=f'{len(page)} names returned').to_dict()


def get_xrefs_to(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_xrefs(workspace, parse_va(va), 'to')
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': page, 'pagination': meta}, provenance={'tool': 'get_xrefs_to'}, summary=f'{len(page)} xrefs-to returned').to_dict()


def get_xrefs_from(manager: WorkspaceSessionManager, workspace_id: str, va: Any, max_results: int = 32, offset: int = 0, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    items = collect_xrefs(workspace, parse_va(va), 'from')
    page, has_more = paginated(items, offset, max_results)
    meta = pagination_meta(len(items), offset, max_results, has_more)
    return ToolResponse.ok(workspace_id, 'workspace', {'xrefs': page, 'pagination': meta}, provenance={'tool': 'get_xrefs_from'}, summary=f'{len(page)} xrefs-from returned').to_dict()


def get_function_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    limits = _limits_from_manager(manager)
    limits.update(kwargs)  # explicit per-call params override config defaults
    summary = extract_function_overview(workspace, parse_va(fva), analysis_limits=limits)
    name = summary.get('function', {}).get('name') or summary.get('function', {}).get('va')
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_summary'}, summary=f'function summary ready for {name}').to_dict()


def get_function_graph(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
    limits = _limits_from_manager(manager)
    limits.update(kwargs)  # all per-call params override config defaults
    max_nodes = limits.get('max_nodes', 64)
    max_edges = limits.get('max_edges', 96)
    graph = workspace.getFunctionGraph(parse_va(fva))
    summary = summarize_graph(graph, max_nodes=max_nodes, max_edges=max_edges)
    return ToolResponse.ok(workspace_id, 'function', summary, provenance={'tool': 'get_function_graph'}, summary='function graph ready').to_dict()


def get_symbolik_summary(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
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
    workspace = _resolve_workspace(manager, workspace_id)
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
    workspace = _resolve_workspace(manager, workspace_id)
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
    workspace = _resolve_workspace(manager, workspace_id)
    func_count = len(workspace.getFunctions())
    return ToolResponse.ok(
        workspace_id, 'workspace',
        {'function_count': func_count},
        provenance={'tool': 'workspace_analysis_status'},
        summary=f'{func_count} functions discovered',
    ).to_dict()


def export_analysis_report(manager: WorkspaceSessionManager, workspace_id: str, results: list | None = None, **kwargs) -> Dict[str, Any]:
    workspace = _resolve_workspace(manager, workspace_id)
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
    workspace = _resolve_workspace(manager, workspace_id)
    result = _analysis_service(manager).analyze_function(workspace, parse_va(fva), options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'function explanation ready')
    return ToolResponse.ok(workspace_id, 'function', result, provenance={'tool': 'ai_explain_function'}, summary=summary).to_dict()


def ai_summarize_binary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    err = _check_provider_available(manager)
    if err:
        return ToolResponse.error_response(workspace_id, 'binary', err, provenance={'tool': 'ai_summarize_binary'}).to_dict()
    workspace = _resolve_workspace(manager, workspace_id)
    result = _analysis_service(manager).analyze_binary(workspace, options=_options_from_kwargs(kwargs))
    summary = result.get('analysis', {}).get('summary', 'binary summary ready')
    return ToolResponse.ok(workspace_id, 'binary', result, provenance={'tool': 'ai_summarize_binary'}, summary=summary).to_dict()


def ai_analyze_functions(manager: WorkspaceSessionManager, workspace_id: str, fvas: list[Any], **kwargs) -> Dict[str, Any]:
    err = _check_provider_available(manager)
    if err:
        return ToolResponse.error_response(workspace_id, 'function', err, provenance={'tool': 'ai_analyze_functions'}).to_dict()
    workspace = _resolve_workspace(manager, workspace_id)
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
    workspace = _resolve_workspace(manager, workspace_id)
    result = _apply_function_rename(workspace, parse_va(fva), new_name, policy)
    if not result.get('applied'):
        return ToolResponse.error_response(workspace_id, 'function', result.get('reason', 'failed to apply function rename'), provenance={'tool': 'apply_function_rename', 'mutation_policy': policy.value}, warnings=[]).to_dict() | {'data': result}
    return ToolResponse.ok(workspace_id, 'function', result, provenance={'tool': 'apply_function_rename', 'mutation_policy': policy.value}, summary='function rename applied').to_dict()


def apply_comment(manager: WorkspaceSessionManager, workspace_id: str, va: Any, comment: str, **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = _resolve_workspace(manager, workspace_id)
    result = _apply_comment_suggestion(workspace, parse_va(va), comment, policy)
    if not result.get('applied'):
        return ToolResponse.error_response(workspace_id, 'address', result.get('reason', 'failed to apply comment'), provenance={'tool': 'apply_comment', 'mutation_policy': policy.value}, warnings=[]).to_dict() | {'data': result}
    return ToolResponse.ok(workspace_id, 'address', result, provenance={'tool': 'apply_comment', 'mutation_policy': policy.value}, summary='comment applied').to_dict()


def propose_campaign_renames(manager: WorkspaceSessionManager, workspace_id: str, renames: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    workspace = _resolve_workspace(manager, workspace_id)
    parsed = [{'fva': parse_va(item['fva']), 'new_name': str(item['new_name'])} for item in renames]
    results = _campaign_renames(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'propose_campaign_renames', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} renames proposed').to_dict()


def apply_campaign_renames(manager: WorkspaceSessionManager, workspace_id: str, renames: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = _resolve_workspace(manager, workspace_id)
    parsed = [{'fva': parse_va(item['fva']), 'new_name': str(item['new_name'])} for item in renames]
    results = _campaign_renames(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'apply_campaign_renames', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} renames applied').to_dict()


def propose_campaign_comments(manager: WorkspaceSessionManager, workspace_id: str, comments: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    workspace = _resolve_workspace(manager, workspace_id)
    parsed = [{'va': parse_va(item['va']), 'comment': str(item['comment'])} for item in comments]
    results = _campaign_comments(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'address', {'results': results}, provenance={'tool': 'propose_campaign_comments', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} comments proposed').to_dict()


def apply_campaign_comments(manager: WorkspaceSessionManager, workspace_id: str, comments: list[dict], **kwargs) -> Dict[str, Any]:
    policy = manager.mutation_policy
    assert_apply_allowed(policy)
    workspace = _resolve_workspace(manager, workspace_id)
    parsed = [{'va': parse_va(item['va']), 'comment': str(item['comment'])} for item in comments]
    results = _campaign_comments(workspace, parsed, policy)
    applied = sum(1 for r in results if r.get('applied'))
    return ToolResponse.ok(workspace_id, 'address', {'results': results}, provenance={'tool': 'apply_campaign_comments', 'mutation_policy': policy.value}, summary=f'{applied}/{len(results)} comments applied').to_dict()


# ---------------------------------------------------------------------------
# Vivisect Server connection tools
# ---------------------------------------------------------------------------


def server_connect(manager: WorkspaceSessionManager, host: str, wsname: str, port: int = 0x4074, **kwargs) -> Dict[str, Any]:
    """Connect to a Vivisect Server and open a remote workspace."""
    _validate_mode(manager, for_local=False)
    session = manager.connect_server(host, port, wsname)
    func_count = len(session.workspace.getFunctions()) if hasattr(session.workspace, 'getFunctions') else 0
    return ToolResponse.ok(
        workspace_id=session.workspace_id,
        request_scope='workspace',
        data={
            'workspace_id': session.workspace_id,
            'path': session.path,
            'metadata': session.metadata,
            'function_count': func_count,
            'connection': {
                'host': host,
                'port': port,
                'wsname': wsname,
            },
        },
        provenance={'tool': 'server_connect'},
        summary=f'connected to {host}:{port}/{wsname} — workspace {session.workspace_id} ({func_count} functions)',
    ).to_dict()


def server_disconnect(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """Disconnect from a remote workspace and clean up leader session."""
    session = manager.get_session(workspace_id)
    vw = session.workspace

    # Kill any active leader session
    if _has_server(vw):
        leader_uuid = session.metadata.get('leader_uuid')
        if leader_uuid:
            try:
                vw.killLeaderSession(leader_uuid)
            except Exception:
                pass
        _clear_leader_uuid(session)

    manager.close_workspace(workspace_id)
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='workspace',
        data={'workspace_id': workspace_id, 'disconnected': True},
        provenance={'tool': 'server_disconnect'},
        summary=f'disconnected workspace {workspace_id}',
    ).to_dict()


def server_list_workspaces(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """List workspaces available on the server a workspace is connected to."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)
    server_proxy = _get_server_proxy(vw)
    workspaces = server_proxy.listWorkspaces()
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={'workspaces': workspaces},
        provenance={'tool': 'server_list_workspaces'},
        summary=f'{len(workspaces)} workspaces available on server',
    ).to_dict()


# ---------------------------------------------------------------------------
# Follow-the-leader tools
# ---------------------------------------------------------------------------


def leader_start(manager: WorkspaceSessionManager, workspace_id: str, session_name: str = 'AI Analysis Session', initial_location: str = '0x0', **kwargs) -> Dict[str, Any]:
    """Declare this session as a leader on a remote workspace."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = _get_or_create_leader_uuid(session)
    vw.iAmLeader(leader_uuid, session_name, initial_location)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={
            'leader_uuid': leader_uuid,
            'session_name': session_name,
            'initial_location': initial_location,
            'followers_can_opt_in': True,
        },
        provenance={'tool': 'leader_start'},
        summary=f'started leader session "{session_name}" (uuid={leader_uuid[:8]}...)',
    ).to_dict()


def leader_navigate(manager: WorkspaceSessionManager, workspace_id: str, location_expr: str, **kwargs) -> Dict[str, Any]:
    """Broadcast navigation to all followers of this leader session."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_navigate'},
        ).to_dict()

    vw.followTheLeader(leader_uuid, location_expr)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={'leader_uuid': leader_uuid, 'location': location_expr},
        provenance={'tool': 'leader_navigate'},
        summary=f'navigated followers to {location_expr}',
    ).to_dict()


def leader_end(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """End the active leader session on a remote workspace."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session to end',
            provenance={'tool': 'leader_end'},
        ).to_dict()

    vw.killLeaderSession(leader_uuid)
    _clear_leader_uuid(session)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={'leader_uuid': leader_uuid, 'ended': True},
        provenance={'tool': 'leader_end'},
        summary='leader session ended',
    ).to_dict()


def leader_list(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """List all active leader sessions on the remote workspace."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    sessions = vw.getLeaderSessions()

    enriched = []
    for uuid_str, (user, fname) in sessions.items():
        loc = vw.getLeaderLoc(uuid_str)
        enriched.append({
            'uuid': uuid_str,
            'user': user,
            'session_name': fname,
            'current_location': loc,
        })

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={'sessions': enriched},
        provenance={'tool': 'leader_list'},
        summary=f'{len(enriched)} active leader sessions',
    ).to_dict()


def leader_get_location(manager: WorkspaceSessionManager, workspace_id: str, session_uuid: str | None = None, **kwargs) -> Dict[str, Any]:
    """Get a leader session's current navigated location."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    if session_uuid is None:
        session_uuid = session.metadata.get('leader_uuid')

    if not session_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no leader_uuid provided and no active leader session on this workspace',
            provenance={'tool': 'leader_get_location'},
        ).to_dict()

    loc = vw.getLeaderLoc(session_uuid) if hasattr(vw, 'getLeaderLoc') else None
    info = vw.getLeaderInfo(session_uuid) if hasattr(vw, 'getLeaderInfo') else (None, None)
    user, fname = info if info else (None, None)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={
            'leader_uuid': session_uuid,
            'user': user,
            'session_name': fname,
            'current_location': loc,
        },
        provenance={'tool': 'leader_get_location'},
        summary=f'leader {session_uuid[:8]}... at {loc}' if loc else 'leader location unknown',
    ).to_dict()


def leader_chat(manager: WorkspaceSessionManager, workspace_id: str, message: str, **kwargs) -> Dict[str, Any]:
    """Send a chat message to all users on the remote workspace."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    vw.chat(message)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={'message_sent': True, 'message_length': len(message)},
        provenance={'tool': 'leader_chat'},
        summary=f'sent chat message ({len(message)} chars)',
    ).to_dict()


def leader_explain_and_navigate(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    """Combined workflow: AI-explain a function, navigate followers, deliver via chat."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_explain_and_navigate'},
        ).to_dict()

    # 1. Navigate followers
    fva_hex = f'0x{parse_va(fva):x}' if not isinstance(fva, str) or not fva.startswith('0x') else fva
    vw.followTheLeader(leader_uuid, fva_hex)

    # 2. Run AI analysis if available
    fva_int = parse_va(fva)
    ai_result = None
    err = _check_provider_available(manager)
    if not err:
        try:
            ai_result = _analysis_service(manager).analyze_function(vw, fva_int, options=_options_from_kwargs(kwargs))
        except Exception:
            pass

    # 3. Deliver explanation
    if ai_result:
        summary_text = ai_result.get('analysis', {}).get('summary', '')
        if summary_text:
            vw.chat(f'[AI] {summary_text}')

    provenance_info = {'tool': 'leader_explain_and_navigate', 'ai_analysis': ai_result is not None}
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='function',
        data={
            'navigated_to': fva_hex,
            'ai_analysis_completed': ai_result is not None,
            'analysis': ai_result.get('analysis') if ai_result else None,
        },
        provenance=provenance_info,
        summary=f'navigated to {fva_hex}' + (', AI explanation delivered' if ai_result else ' (no AI provider)'),
    ).to_dict()


# ---------------------------------------------------------------------------
# New Phase U tools  —  leader_annotate, leader_status, explain variants
# ---------------------------------------------------------------------------


def leader_annotate(manager: WorkspaceSessionManager, workspace_id: str, va: Any, text: str, **kwargs) -> Dict[str, Any]:
    """Set a workspace comment at *va* tagged as an AI leader annotation.

    Requires an active leader session on a remote workspace.
    The comment is prefixed with ``[Viv-AI] `` so followers can distinguish
    AI annotations from manual ones.
    """
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_annotate'},
        ).to_dict()

    fva_int = parse_va(va)
    prefix = 'Viv-AI'
    full_text = f'[{prefix}] {text}'
    vw.setComment(fva_int, full_text)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='function',
        data={
            'va': f'0x{fva_int:x}',
            'comment_set': True,
            'annotation_length': len(text),
        },
        provenance={'tool': 'leader_annotate'},
        summary=f'annotation set at 0x{fva_int:x}',
    ).to_dict()


def leader_status(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """Return aggregate status of the AI leader session.

    Includes session name, current location, all leader sessions on the
    workspace, and a count of chat messages.
    """
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_status'},
        ).to_dict()

    # Current location
    current_location = None
    if hasattr(vw, 'getLeaderLoc'):
        try:
            current_location = vw.getLeaderLoc()
        except Exception:
            pass

    # Current leader info
    user = None
    session_name = None
    if hasattr(vw, 'getLeaderInfo'):
        try:
            info = vw.getLeaderInfo()
            if info and len(info) >= 2:
                user, session_name = info[0], info[1]
        except Exception:
            pass

    # All leader sessions on the workspace
    all_sessions = {}
    if hasattr(vw, 'getLeaderSessions'):
        try:
            all_sessions = {
                uid: {'user': u, 'name': n}
                for uid, (u, n) in vw.getLeaderSessions().items()
            }
        except Exception:
            pass

    # Chat count
    chat_count = 0
    chats_attr = getattr(vw, '_chats', None)
    if chats_attr is not None:
        chat_count = len(chats_attr)

    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='server',
        data={
            'leader_uuid': leader_uuid,
            'current_location': current_location,
            'user': user,
            'session_name': session_name,
            'all_sessions': all_sessions,
            'chat_count': chat_count,
        },
        provenance={'tool': 'leader_status'},
        summary=f'leader session {leader_uuid[:8]}... | {len(all_sessions)} session(s) | {chat_count} chat(s)',
    ).to_dict()


def leader_explain_binary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """AI-summarise the binary, navigate followers to the entry point,
    and deliver the summary via chat.
    """
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_explain_binary'},
        ).to_dict()

    # Find the first entry point
    entry_points = vw.getEntryPoints()
    entry_fva = entry_points[0] if entry_points else None

    # Navigate followers
    if entry_fva is not None:
        entry_hex = f'0x{entry_fva:x}'
        vw.followTheLeader(leader_uuid, entry_hex)

    # Run AI binary analysis if available
    ai_result = None
    err = _check_provider_available(manager)
    if not err:
        try:
            ai_result = _analysis_service(manager).analyze_binary(vw, options=_options_from_kwargs(kwargs))
        except Exception:
            pass

    # Deliver via chat
    if ai_result:
        summary_text = ai_result.get('analysis', {}).get('summary', '')
        if summary_text:
            vw.chat(f'[AI] Binary summary: {summary_text}')

    provenance_info = {'tool': 'leader_explain_binary', 'ai_analysis': ai_result is not None}
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='workspace',
        data={
            'entry_point': f'0x{entry_fva:x}' if entry_fva else None,
            'navigated': entry_fva is not None,
            'ai_analysis_completed': ai_result is not None,
            'analysis': ai_result.get('analysis') if ai_result else None,
        },
        provenance=provenance_info,
        summary=f'binary analysis' + (', AI summary delivered' if ai_result else ' (no AI provider)'),
    ).to_dict()


def leader_explain_graph(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    """AI-analyse a function's control-flow graph, navigate followers to it,
    and deliver the analysis via chat.
    """
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_explain_graph'},
        ).to_dict()

    fva_hex = f'0x{parse_va(fva):x}' if not isinstance(fva, str) or not fva.startswith('0x') else fva
    fva_int = parse_va(fva)
    vw.followTheLeader(leader_uuid, fva_hex)

    # Run AI graph analysis if available
    ai_result = None
    err = _check_provider_available(manager)
    if not err:
        try:
            graph = vw.getFunctionGraph(fva_int)
            ai_result = _analysis_service(manager).analyze_graph(graph, options=_options_from_kwargs(kwargs))
        except Exception:
            pass

    if ai_result:
        summary_text = ai_result.get('analysis', {}).get('summary', '')
        if summary_text:
            vw.chat(f'[AI] Graph analysis: {summary_text}')

    provenance_info = {'tool': 'leader_explain_graph', 'ai_analysis': ai_result is not None}
    return ToolResponse.ok(
        workspace_id=workspace_id,
        request_scope='function',
        data={
            'navigated_to': fva_hex,
            'ai_analysis_completed': ai_result is not None,
            'analysis': ai_result.get('analysis') if ai_result else None,
        },
        provenance=provenance_info,
        summary=f'graph analysed at {fva_hex}' + (', AI summary delivered' if ai_result else ' (no AI provider)'),
    ).to_dict()


def build_default_registry() -> Dict[str, ToolFn]:
    return {
        'workspace_open': workspace_open,
        'workspace_status': workspace_status,
        'workspace_close': workspace_close,
        'list_workspaces': list_workspaces,
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
        # Vivisect Server connection tools
        'server_connect': server_connect,
        'server_disconnect': server_disconnect,
        'server_list_workspaces': server_list_workspaces,
        # Follow-the-leader tools
        'leader_start': leader_start,
        'leader_navigate': leader_navigate,
        'leader_end': leader_end,
        'leader_list': leader_list,
        'leader_get_location': leader_get_location,
        'leader_chat': leader_chat,
        'leader_explain_and_navigate': leader_explain_and_navigate,
        'leader_annotate': leader_annotate,
        'leader_status': leader_status,
        'leader_explain_binary': leader_explain_binary,
        'leader_explain_graph': leader_explain_graph,
    }
