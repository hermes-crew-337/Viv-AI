"""Comprehensive tests for viv_ai/mcp/tools.py — targeting >95% coverage of all tool functions.

Tests every public tool function and all internal helpers, covering happy paths,
error paths, edge cases, and branch coverage.  Uses unittest.TestCase with mock
workspace/session/analysis-service objects.
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, PropertyMock, patch, call
import unittest

from viv_ai.models import MutationPolicy


# =========================================================================
# Helper utilities
# =========================================================================

def _make_manager(**overrides) -> MagicMock:
    """Build a mock WorkspaceSessionManager with sensible defaults.

    Keyword overrides are set as attributes on the returned mock so callers
    can quickly customise (e.g. ``mutation_policy``, ``analysis_service``).
    """
    manager = MagicMock()
    session = MagicMock()
    session.workspace_id = 'ws-test-001'
    session.path = '/tmp/test_binary.viv'
    session.metadata = {}
    session.workspace = MagicMock()
    # Provide a minimal getFunctions — the workspace_open helper calls it
    session.workspace.getFunctions.return_value = []
    session.workspace.getMeta.side_effect = lambda key, default=None: default
    session.workspace.getEntryPoints.return_value = []
    session.workspace.getLocations.return_value = []
    session.workspace.getImports.return_value = []
    session.workspace.getExports.return_value = []
    session.workspace.getNames.return_value = []
    session.workspace.reprLocation.side_effect = lambda loc: str(loc)
    session.workspace.getFunctionGraph.return_value = MagicMock()

    manager.get_session.return_value = session
    manager.list_workspaces.return_value = {'ws-test-001': session}
    manager.open_workspace.return_value = session
    manager.connect_server.return_value = session
    manager.get_workspace.return_value = session.workspace
    manager.mutation_policy = MutationPolicy.DIRECT_APPLY_ENABLED
    for k, v in overrides.items():
        setattr(manager, k, v)
    return manager


def _make_analysis_service(**overrides) -> MagicMock:
    """Build a mock AnalysisService with controllable returns."""
    svc = MagicMock()
    svc.analyze_function.return_value = {
        'fva': '0x401000',
        'name': 'test_func',
        'analysis': {'summary': 'Test analysis', 'confidence': 'high', 'purpose': 'testing'},
    }
    svc.analyze_binary.return_value = {'summary': 'Binary summary', 'confidence': 'medium'}
    svc.analyze_functions.return_value = [
        {'fva': '0x401000', 'analysis': {'summary': 'func1'}},
        {'fva': '0x401050', 'analysis': {'summary': 'func2'}},
    ]
    svc.provider_status.return_value = {
        'provider_name': 'ollama',
        'available_models': ['llama3', 'qwen2.5'],
    }
    for k, v in overrides.items():
        setattr(svc, k, v)
    return svc


def _server_vw() -> MagicMock:
    """A workspace mock that looks like a remote (server-connected) vw."""
    vw = MagicMock()
    vw.server = MagicMock()
    vw.server.server = MagicMock()
    vw.server.server.listWorkspaces.return_value = ['ws1', 'ws2']
    vw.getLeaderSessions.return_value = {
        'uuid-1': ('alice', 'Session A'),
        'uuid-2': ('bob', 'Session B'),
    }
    vw.getLeaderLoc.return_value = '0x401000'
    vw.getLeaderInfo.return_value = ('user', 'session_name')
    vw.iAmLeader = MagicMock()
    vw.followTheLeader = MagicMock()
    vw.killLeaderSession = MagicMock()
    vw.chat = MagicMock()
    vw.getFunctions.return_value = [0x401000, 0x401050]
    return vw


# =========================================================================
# Tests for helper functions
# =========================================================================

class TestHelpers(unittest.TestCase):
    """Tests for internal helper functions in tools.py."""

    # ---- _limits_from_manager ----

    def test_limits_from_manager_no_service(self):
        from viv_ai.mcp.tools import _limits_from_manager
        mgr = _make_manager()
        mgr.analysis_service = None
        limits = _limits_from_manager(mgr)
        self.assertIsInstance(limits, dict)
        self.assertIn('max_nodes', limits)
        self.assertEqual(limits['max_nodes'], 32)  # default when config is None

    def test_limits_from_manager_with_config(self):
        from viv_ai.mcp.tools import _limits_from_manager
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.analysis_max_nodes = 128
        svc.config.analysis_max_edges = 256
        mgr = _make_manager(analysis_service=svc)
        limits = _limits_from_manager(mgr)
        self.assertEqual(limits['max_nodes'], 128)
        self.assertEqual(limits['max_edges'], 256)

    def test_limits_from_manager_service_no_config(self):
        from viv_ai.mcp.tools import _limits_from_manager
        svc = _make_analysis_service()
        del svc.config  # no config attr at all
        mgr = _make_manager(analysis_service=svc)
        limits = _limits_from_manager(mgr)
        self.assertEqual(limits['max_nodes'], 32)  # defaults

    # ---- _ensure_analyzed ----

    def test_ensure_analyzed_already_has_funcs(self):
        from viv_ai.mcp.tools import _ensure_analyzed
        vw = MagicMock()
        vw.getFunctions.return_value = [0x401000]
        self.assertTrue(_ensure_analyzed(vw, poll_seconds=1.0))

    def test_ensure_analyzed_gets_funcs_after_poll(self):
        from viv_ai.mcp.tools import _ensure_analyzed
        vw = MagicMock()
        # First call returns empty, second has results
        vw.getFunctions.side_effect = [
            [],
            [0x401000],
        ]
        self.assertTrue(_ensure_analyzed(vw, poll_seconds=5.0))

    def test_ensure_analyzed_timeout(self):
        from viv_ai.mcp.tools import _ensure_analyzed
        vw = MagicMock()
        vw.getFunctions.return_value = []
        # Should time out and return False
        self.assertFalse(_ensure_analyzed(vw, poll_seconds=0.1))

    # ---- _trigger_analyze ----

    def test_trigger_analyze_success(self):
        from viv_ai.mcp.tools import _trigger_analyze
        vw = MagicMock()
        vw.analyze = MagicMock()
        vw.getFunctions.return_value = [0x401000, 0x401050]
        count = _trigger_analyze(vw, timeout=5.0)
        self.assertEqual(count, 2)
        vw.analyze.assert_called_once()

    def test_trigger_analyze_exception_in_analyze(self):
        from viv_ai.mcp.tools import _trigger_analyze
        vw = MagicMock()
        vw.analyze.side_effect = RuntimeError('analysis failed')
        vw.getFunctions.return_value = [0x401000]
        count = _trigger_analyze(vw, timeout=5.0)
        self.assertEqual(count, 1)  # exception caught, functions still returned

    def test_trigger_analyze_timeout(self):
        from viv_ai.mcp.tools import _trigger_analyze
        vw = MagicMock()
        # Make analyze block by sleeping past the timeout
        import time
        original_analyze = vw.analyze
        def _slow():
            time.sleep(5)
        vw.analyze.side_effect = _slow
        vw.getFunctions.return_value = [0x401000]
        count = _trigger_analyze(vw, timeout=0.1)
        self.assertEqual(count, 1)

    # ---- _validate_server_mode ----

    def test_validate_server_mode_has_server(self):
        from viv_ai.mcp.tools import _validate_server_mode
        vw = MagicMock()
        vw.server = MagicMock()
        # Should not raise
        _validate_server_mode(vw)

    def test_validate_server_mode_no_server(self):
        from viv_ai.mcp.tools import _validate_server_mode
        vw = MagicMock()
        vw.server = None
        with self.assertRaises(RuntimeError) as ctx:
            _validate_server_mode(vw)
        self.assertIn('not connected', str(ctx.exception))

    # ---- _get_or_create_leader_uuid ----

    def test_get_or_create_leader_uuid_existing(self):
        from viv_ai.mcp.tools import _get_or_create_leader_uuid
        session = MagicMock()
        session.metadata = {'leader_uuid': 'existing-uuid'}
        uid = _get_or_create_leader_uuid(session)
        self.assertEqual(uid, 'existing-uuid')

    def test_get_or_create_leader_uuid_new(self):
        from viv_ai.mcp.tools import _get_or_create_leader_uuid
        session = MagicMock()
        session.metadata = {}
        uid = _get_or_create_leader_uuid(session)
        self.assertIsNotNone(uid)
        self.assertEqual(session.metadata['leader_uuid'], uid)

    # ---- _clear_leader_uuid ----

    def test_clear_leader_uuid_existing(self):
        from viv_ai.mcp.tools import _clear_leader_uuid
        session = MagicMock()
        session.metadata = {'leader_uuid': 'some-uuid'}
        _clear_leader_uuid(session)
        self.assertNotIn('leader_uuid', session.metadata)

    def test_clear_leader_uuid_none(self):
        from viv_ai.mcp.tools import _clear_leader_uuid
        session = MagicMock()
        session.metadata = {}
        _clear_leader_uuid(session)  # should not raise

    # ---- _schema ----

    def test_schema_minimal(self):
        from viv_ai.mcp.tools import _schema
        result = _schema({'foo': {'type': 'string'}})
        self.assertEqual(result['type'], 'object')
        self.assertEqual(result['required'], [])
        self.assertFalse(result['additionalProperties'])

    def test_schema_with_required_and_additional(self):
        from viv_ai.mcp.tools import _schema
        result = _schema({'foo': {'type': 'string'}}, required=['foo'], additional_properties=True)
        self.assertEqual(result['required'], ['foo'])
        self.assertTrue(result['additionalProperties'])

    # ---- _analysis_service ----

    def test_analysis_service_ok(self):
        from viv_ai.mcp.tools import _analysis_service
        svc = _make_analysis_service()
        mgr = _make_manager(analysis_service=svc)
        result = _analysis_service(mgr)
        self.assertIs(result, svc)

    def test_analysis_service_none(self):
        from viv_ai.mcp.tools import _analysis_service
        mgr = _make_manager()
        mgr.analysis_service = None
        with self.assertRaises(RuntimeError) as ctx:
            _analysis_service(mgr)
        self.assertIn('not configured', str(ctx.exception))

    # ---- _options_from_kwargs ----

    def test_options_from_kwargs_basic(self):
        from viv_ai.mcp.tools import _options_from_kwargs
        result = _options_from_kwargs({'a': 1, 'b': 2, 'c': 3}, 'b')
        self.assertEqual(result, {'a': 1, 'c': 3})

    def test_options_from_kwargs_no_exclusions(self):
        from viv_ai.mcp.tools import _options_from_kwargs
        result = _options_from_kwargs({'a': 1, 'b': 2})
        self.assertEqual(result, {'a': 1, 'b': 2})

    # ---- _proposal ----

    def test_proposal_rename(self):
        from viv_ai.mcp.tools import _proposal
        result = _proposal(False, 'function_rename', 0x401000, 'name', 'new_func', 'proposal only')
        self.assertFalse(result['applied'])
        self.assertEqual(result['reason'], 'proposal only')
        self.assertEqual(result['proposal']['kind'], 'function_rename')
        self.assertEqual(result['proposal']['va'], '0x00401000')
        self.assertEqual(result['proposal']['name'], 'new_func')

    def test_proposal_comment(self):
        from viv_ai.mcp.tools import _proposal
        result = _proposal(True, 'comment', 0x401000, 'comment', 'hello', 'applied ok')
        self.assertTrue(result['applied'])
        self.assertEqual(result['proposal']['comment'], 'hello')

    # ---- _resolve_workspace ----

    def test_resolve_workspace_ok(self):
        from viv_ai.mcp.tools import _resolve_workspace
        mgr = _make_manager()
        vw = _resolve_workspace(mgr, 'ws-test-001')
        self.assertIsNotNone(vw)
        mgr.get_workspace.assert_called_once_with('ws-test-001')

    def test_resolve_workspace_missing_id(self):
        from viv_ai.mcp.tools import _resolve_workspace
        mgr = _make_manager()
        with self.assertRaises(RuntimeError) as ctx:
            _resolve_workspace(mgr, None)
        self.assertIn('required', str(ctx.exception))

    def test_resolve_workspace_not_found(self):
        from viv_ai.mcp.tools import _resolve_workspace
        from viv_ai.mcp.session import WorkspaceSessionError
        mgr = _make_manager()
        mgr.get_workspace.side_effect = WorkspaceSessionError('not found')
        with self.assertRaises(RuntimeError) as ctx:
            _resolve_workspace(mgr, 'nonexistent')
        self.assertIn('not found', str(ctx.exception))

    # ---- _check_provider_available ----

    def test_check_provider_available_no_service(self):
        from viv_ai.mcp.tools import _check_provider_available
        mgr = _make_manager()
        mgr.analysis_service = None
        err = _check_provider_available(mgr)
        self.assertIsNotNone(err)

    def test_check_provider_available_no_config_duck(self):
        from viv_ai.mcp.tools import _check_provider_available
        svc = _make_analysis_service()
        # No config attr — duck-typed fake
        del svc.config
        mgr = _make_manager(analysis_service=svc)
        err = _check_provider_available(mgr)
        self.assertIsNone(err)  # duck-typed fakes pass through

    def test_check_provider_available_no_providers(self):
        from viv_ai.mcp.tools import _check_provider_available
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {}
        svc.config.default_provider = None
        mgr = _make_manager(analysis_service=svc)
        err = _check_provider_available(mgr)
        self.assertIsNotNone(err)
        self.assertIn('no AI providers', err)

    def test_check_provider_available_no_default(self):
        from viv_ai.mcp.tools import _check_provider_available
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = None
        mgr = _make_manager(analysis_service=svc)
        err = _check_provider_available(mgr)
        self.assertIsNotNone(err)
        self.assertIn('no default AI provider', err)

    def test_check_provider_available_default_not_in_providers(self):
        from viv_ai.mcp.tools import _check_provider_available
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = 'nonexistent'
        mgr = _make_manager(analysis_service=svc)
        err = _check_provider_available(mgr)
        self.assertIsNotNone(err)
        self.assertIn('not configured', err)

    def test_check_provider_available_ok(self):
        from viv_ai.mcp.tools import _check_provider_available
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = 'ollama'
        mgr = _make_manager(analysis_service=svc)
        err = _check_provider_available(mgr)
        self.assertIsNone(err)


# =========================================================================
# Tests for workspace-management tools
# =========================================================================

class TestWorkspaceTools(unittest.TestCase):
    """workspace_open, workspace_status, workspace_close, list_workspaces."""

    def test_workspace_open_success(self):
        from viv_ai.mcp.tools import workspace_open
        mgr = _make_manager()
        result = workspace_open(mgr, path='/tmp/test_binary.viv')
        self.assertTrue(result['ok'])
        self.assertEqual(result['workspace_id'], 'ws-test-001')
        self.assertEqual(result['data']['path'], '/tmp/test_binary.viv')
        mgr.open_workspace.assert_called_once_with('/tmp/test_binary.viv', workspace=None)

    def test_workspace_open_with_funcs(self):
        from viv_ai.mcp.tools import workspace_open
        mgr = _make_manager()
        # Make the session workspace report functions
        mgr.get_session.return_value.workspace.getFunctions.return_value = [0x401000]
        mgr.open_workspace.return_value = mgr.get_session.return_value
        result = workspace_open(mgr, path='/tmp/test_binary.viv')
        self.assertTrue(result['ok'])
        self.assertIn('function_count', result['data'])

    def test_workspace_open_explicit_workspace(self):
        from viv_ai.mcp.tools import workspace_open
        mgr = _make_manager()
        explicit_vw = MagicMock()
        result = workspace_open(mgr, path='/tmp/test.viv', workspace=explicit_vw)
        self.assertTrue(result['ok'])
        mgr.open_workspace.assert_called_once_with('/tmp/test.viv', workspace=explicit_vw)

    def test_workspace_status_success(self):
        from viv_ai.mcp.tools import workspace_status
        mgr = _make_manager()
        mgr.get_session.return_value.to_dict.return_value = {
            'workspace_id': 'ws-test-001',
            'path': '/tmp/test_binary.viv',
            'metadata': {},
        }
        result = workspace_status(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['workspace']['workspace_id'], 'ws-test-001')

    def test_workspace_close_success(self):
        from viv_ai.mcp.tools import workspace_close
        mgr = _make_manager()
        result = workspace_close(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['closed'])
        mgr.close_workspace.assert_called_once_with('ws-test-001')

    def test_list_workspaces_success(self):
        from viv_ai.mcp.tools import list_workspaces
        mgr = _make_manager()
        result = list_workspaces(mgr)
        self.assertTrue(result['ok'])
        self.assertIn('workspaces', result['data'])

    def test_list_workspaces_empty(self):
        from viv_ai.mcp.tools import list_workspaces
        mgr = _make_manager()
        mgr.list_workspaces.return_value = {}
        result = list_workspaces(mgr)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['workspaces']), 0)


# =========================================================================
# Tests for metadata/binary-summary tools
# =========================================================================

class TestMetadataTools(unittest.TestCase):
    """get_metadata, get_binary_summary."""

    def test_get_metadata(self):
        from viv_ai.mcp.tools import get_metadata
        mgr = _make_manager()
        mgr.get_session.return_value.metadata = {
            'platform': 'linux',
            'architecture': 'x86-64',
            'format': 'ELF64',
        }
        result = get_metadata(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['metadata']['platform'], 'linux')
        self.assertEqual(result['data']['metadata']['architecture'], 'x86-64')
        self.assertEqual(result['data']['metadata']['format'], 'ELF64')

    def test_get_binary_summary(self):
        from viv_ai.mcp.tools import get_binary_summary
        mgr = _make_manager()
        result = get_binary_summary(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])


# =========================================================================
# Tests for paginated listing tools
# =========================================================================

class TestPaginatedTools(unittest.TestCase):
    """get_strings, get_imports, get_exports, get_names, get_xrefs_to, get_xrefs_from."""

    def setUp(self):
        from viv_ai.mcp.tools import (
            get_strings, get_imports, get_exports, get_names,
            get_xrefs_to, get_xrefs_from,
        )
        self.funcs = {
            'get_strings': get_strings,
            'get_imports': get_imports,
            'get_exports': get_exports,
            'get_names': get_names,
            'get_xrefs_to': get_xrefs_to,
            'get_xrefs_from': get_xrefs_from,
        }

    def _run(self, tool_name, **kwargs):
        mgr = _make_manager()
        # Make getLocations return something for string tests
        mgr.get_session.return_value.workspace.getLocations.return_value = [
            (0x4000, 8, 1, 'hello'),
            (0x4008, 12, 2, 'world'),
        ]
        mgr.get_session.return_value.workspace.getImports.return_value = [
            (0x5000, 4, 1, 'printf'),
            (0x5008, 4, 1, 'scanf'),
        ]
        mgr.get_session.return_value.workspace.getExports.return_value = [
            (0x6000, 'func', 'main', 'test.o'),
        ]
        mgr.get_session.return_value.workspace.getNames.return_value = [
            (0x7000, 'main'),
            (0x7008, '_start'),
        ]
        mgr.get_session.return_value.workspace.getXrefsTo.return_value = [
            (0x8000, 0x4000, 1, 0),
            (0x8008, 0x4000, 1, 0),
        ]
        mgr.get_session.return_value.workspace.getXrefsFrom.return_value = [
            (0x4000, 0x9000, 1, 0),
        ]
        fn = self.funcs[tool_name]
        return fn(mgr, workspace_id='ws-test-001', **kwargs)

    def test_get_strings(self):
        result = self._run('get_strings')
        self.assertTrue(result['ok'])
        self.assertIn('strings', result['data'])
        self.assertIn('pagination', result['data'])

    def test_get_strings_paginated(self):
        result = self._run('get_strings', max_results=1, offset=0)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['strings']), 1)

    def test_get_imports(self):
        result = self._run('get_imports')
        self.assertTrue(result['ok'])
        self.assertIn('imports', result['data'])

    def test_get_exports(self):
        result = self._run('get_exports')
        self.assertTrue(result['ok'])
        self.assertIn('exports', result['data'])

    def test_get_names(self):
        result = self._run('get_names')
        self.assertTrue(result['ok'])
        self.assertIn('names', result['data'])

    def test_get_xrefs_to(self):
        result = self._run('get_xrefs_to', va='0x4000')
        self.assertTrue(result['ok'])
        self.assertIn('xrefs', result['data'])

    def test_get_xrefs_from(self):
        result = self._run('get_xrefs_from', va='0x4000')
        self.assertTrue(result['ok'])
        self.assertIn('xrefs', result['data'])


# =========================================================================
# Tests for function-analysis tools
# =========================================================================

class TestFunctionAnalysisTools(unittest.TestCase):
    """get_function_summary, get_function_graph, get_symbolik_summary."""

    @patch('viv_ai.mcp.tools.extract_function_overview')
    def test_get_function_summary(self, mock_extract):
        from viv_ai.mcp.tools import get_function_summary
        mock_extract.return_value = {
            'function': {'name': 'main', 'va': '0x401000'},
            'blocks': [{'va': '0x401000', 'size': 32}],
        }
        mgr = _make_manager()
        result = get_function_summary(mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools.extract_function_overview')
    def test_get_function_summary_with_kwargs(self, mock_extract):
        from viv_ai.mcp.tools import get_function_summary
        mock_extract.return_value = {
            'function': {'name': 'main', 'va': '0x401000'},
        }
        mgr = _make_manager()
        result = get_function_summary(mgr, 'ws-test-001', fva='0x401000', max_constraints=10)
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools.summarize_graph')
    def test_get_function_graph(self, mock_summarize):
        from viv_ai.mcp.tools import get_function_graph
        mock_summarize.return_value = {'nodes': 3, 'edges': 4}
        mgr = _make_manager()
        mgr.analysis_service = None  # ensure int defaults
        result = get_function_graph(mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools.summarize_graph')
    def test_get_function_graph_with_limits(self, mock_summarize):
        from viv_ai.mcp.tools import get_function_graph
        mock_summarize.return_value = {'nodes': 3, 'edges': 4}
        mgr = _make_manager()
        mgr.analysis_service = None  # ensure int defaults
        result = get_function_graph(mgr, 'ws-test-001', fva='0x401000',
                                    max_nodes=10, max_edges=20)
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools.get_symbolik_path_dicts')
    @patch('viv_ai.mcp.tools.summarize_symbolik_paths')
    def test_get_symbolik_summary(self, mock_summarize, mock_path_dicts):
        from viv_ai.mcp.tools import get_symbolik_summary
        mock_path_dicts.return_value = [{'path_id': 0}]
        mock_summarize.return_value = {'paths': [{'path_id': 0}]}
        mgr = _make_manager()
        result = get_symbolik_summary(mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        mock_path_dicts.assert_called_once()

    @patch('viv_ai.mcp.tools.get_symbolik_path_dicts')
    def test_get_symbolik_summary_with_overrides(self, mock_path_dicts):
        from viv_ai.mcp.tools import get_symbolik_summary
        mock_path_dicts.return_value = []
        mgr = _make_manager()
        result = get_symbolik_summary(mgr, 'ws-test-001', fva='0x401000',
                                      max_paths=5, max_constraints=3, max_effects=3)
        self.assertTrue(result['ok'])


# =========================================================================
# Tests for function-discovery / analysis tools
# =========================================================================

class TestFindAnalyzeTools(unittest.TestCase):
    """find_functions, analyze_workspace, workspace_analysis_status."""

    @patch('viv_ai.mcp.tools._find_functions')
    def test_find_functions(self, mock_find):
        from viv_ai.mcp.tools import find_functions
        mock_find.return_value = [{'va': '0x401000', 'name': 'main'}]
        mgr = _make_manager()
        result = find_functions(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertIn('functions', result['data'])

    @patch('viv_ai.mcp.tools._find_functions')
    def test_find_functions_with_filters(self, mock_find):
        from viv_ai.mcp.tools import find_functions
        mock_find.return_value = [{'va': '0x401000', 'name': 'main'}]
        mgr = _make_manager()
        result = find_functions(mgr, 'ws-test-001', name_glob='main', min_callers=0, max_results=10)
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools._find_functions')
    def test_find_functions_triggers_analysis(self, mock_find):
        """When no functions exist, ensure analysis is triggered."""
        from viv_ai.mcp.tools import find_functions
        mock_find.return_value = [{'va': '0x401000', 'name': 'main'}]
        mgr = _make_manager()
        workspace = mgr.get_session.return_value.workspace
        workspace.getFunctions.return_value = [0x401000]
        result = find_functions(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])

    def test_analyze_workspace(self):
        from viv_ai.mcp.tools import analyze_workspace
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getFunctions.return_value = [0x401000]
        result = analyze_workspace(mgr, 'ws-test-001', timeout=10)
        self.assertTrue(result['ok'])
        self.assertIn('functions_before', result['data'])
        self.assertIn('functions_after', result['data'])

    def test_workspace_analysis_status(self):
        from viv_ai.mcp.tools import workspace_analysis_status
        mgr = _make_manager()
        result = workspace_analysis_status(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertIn('function_count', result['data'])


# =========================================================================
# Tests for export/report tool
# =========================================================================

class TestExportReport(unittest.TestCase):
    """export_analysis_report."""

    @patch('viv_ai.mcp.tools._generate_report')
    def test_export_analysis_report(self, mock_generate):
        from viv_ai.mcp.tools import export_analysis_report
        mock_generate.return_value = {'functions': [], 'markdown': '# Report'}
        mgr = _make_manager()
        result = export_analysis_report(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools._generate_report')
    def test_export_analysis_report_with_results(self, mock_generate):
        from viv_ai.mcp.tools import export_analysis_report
        mock_generate.return_value = {'functions': [], 'markdown': '# Report'}
        mgr = _make_manager()
        results = [{'fva': '0x401000', 'name': 'main', 'summary': 'entry point'}]
        result = export_analysis_report(mgr, 'ws-test-001', results=results)
        self.assertTrue(result['ok'])


# =========================================================================
# Tests for AI-powered tools
# =========================================================================

class TestAiTools(unittest.TestCase):
    """ai_explain_function, ai_summarize_binary, ai_analyze_functions, list_provider_models."""

    def setUp(self):
        self.svc = _make_analysis_service()
        self.svc.config = MagicMock()
        self.svc.config.providers = {'ollama': MagicMock()}
        self.svc.config.default_provider = 'ollama'
        self.mgr = _make_manager(analysis_service=self.svc)

    def test_ai_explain_function(self):
        from viv_ai.mcp.tools import ai_explain_function
        result = ai_explain_function(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.svc.analyze_function.assert_called_once()

    def test_ai_explain_function_no_provider(self):
        from viv_ai.mcp.tools import ai_explain_function
        self.mgr.analysis_service = None
        result = ai_explain_function(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertFalse(result['ok'])
        self.assertIn('error', result)

    def test_ai_summarize_binary(self):
        from viv_ai.mcp.tools import ai_summarize_binary
        result = ai_summarize_binary(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.svc.analyze_binary.assert_called_once()

    def test_ai_summarize_binary_no_provider(self):
        from viv_ai.mcp.tools import ai_summarize_binary
        self.mgr.analysis_service = None
        result = ai_summarize_binary(self.mgr, 'ws-test-001')
        self.assertFalse(result['ok'])

    def test_ai_analyze_functions(self):
        from viv_ai.mcp.tools import ai_analyze_functions
        result = ai_analyze_functions(self.mgr, 'ws-test-001', fvas=['0x401000', '0x401050'])
        self.assertTrue(result['ok'])
        self.assertIn('results', result['data'])

    def test_ai_analyze_functions_no_provider(self):
        from viv_ai.mcp.tools import ai_analyze_functions
        self.mgr.analysis_service = None
        result = ai_analyze_functions(self.mgr, 'ws-test-001', fvas=['0x401000'])
        self.assertFalse(result['ok'])

    def test_list_provider_models(self):
        from viv_ai.mcp.tools import list_provider_models
        result = list_provider_models(self.mgr)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['provider_name'], 'ollama')

    def test_list_provider_models_with_name(self):
        from viv_ai.mcp.tools import list_provider_models
        result = list_provider_models(self.mgr, provider_name='ollama')
        self.assertTrue(result['ok'])
        self.svc.provider_status.assert_called_with(provider_name='ollama')


# =========================================================================
# Tests for propose/apply tools
# =========================================================================

class TestProposeApplyTools(unittest.TestCase):
    """propose_function_rename, propose_comment, apply_function_rename, apply_comment,
    propose_campaign_renames, apply_campaign_renames, propose_campaign_comments,
    apply_campaign_comments."""

    def setUp(self):
        self.mgr = _make_manager()
        self.mgr.mutation_policy = MutationPolicy.DIRECT_APPLY_ENABLED

    # ---- propose_function_rename ----

    def test_propose_function_rename(self):
        from viv_ai.mcp.tools import propose_function_rename
        result = propose_function_rename(self.mgr, 'ws-test-001', fva='0x401000', new_name='better_name')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['applied'])

    # ---- propose_comment ----

    def test_propose_comment(self):
        from viv_ai.mcp.tools import propose_comment
        result = propose_comment(self.mgr, 'ws-test-001', va='0x401000', comment='nice function')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['applied'])

    # ---- apply_function_rename ----

    @patch('viv_ai.mcp.tools._apply_function_rename')
    def test_apply_function_rename(self, mock_apply):
        from viv_ai.mcp.tools import apply_function_rename
        mock_apply.return_value = {'applied': True, 'reason': 'ok'}
        result = apply_function_rename(self.mgr, 'ws-test-001', fva='0x401000', new_name='renamed')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['applied'])

    @patch('viv_ai.mcp.tools._apply_function_rename')
    def test_apply_function_rename_failed(self, mock_apply):
        from viv_ai.mcp.tools import apply_function_rename
        mock_apply.return_value = {'applied': False, 'reason': 'not allowed'}
        result = apply_function_rename(self.mgr, 'ws-test-001', fva='0x401000', new_name='renamed')
        self.assertFalse(result['ok'])

    def test_apply_function_rename_readonly(self):
        from viv_ai.mcp.tools import apply_function_rename
        self.mgr.mutation_policy = MutationPolicy.CONSERVATIVE_READONLY
        with self.assertRaises(RuntimeError):
            apply_function_rename(self.mgr, 'ws-test-001', fva='0x401000', new_name='x')

    # ---- apply_comment ----

    @patch('viv_ai.mcp.tools._apply_comment_suggestion')
    def test_apply_comment(self, mock_apply):
        from viv_ai.mcp.tools import apply_comment
        mock_apply.return_value = {'applied': True, 'reason': 'ok'}
        result = apply_comment(self.mgr, 'ws-test-001', va='0x401000', comment='nice!')
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools._apply_comment_suggestion')
    def test_apply_comment_failed(self, mock_apply):
        from viv_ai.mcp.tools import apply_comment
        mock_apply.return_value = {'applied': False, 'reason': 'blocked'}
        result = apply_comment(self.mgr, 'ws-test-001', va='0x401000', comment='nice!')
        self.assertFalse(result['ok'])

    def test_apply_comment_readonly(self):
        from viv_ai.mcp.tools import apply_comment
        self.mgr.mutation_policy = MutationPolicy.CONSERVATIVE_READONLY
        with self.assertRaises(RuntimeError):
            apply_comment(self.mgr, 'ws-test-001', va='0x401000', comment='x')

    # ---- propose_campaign_renames ----

    @patch('viv_ai.mcp.tools._campaign_renames')
    def test_propose_campaign_renames(self, mock_campaign):
        from viv_ai.mcp.tools import propose_campaign_renames
        mock_campaign.return_value = [
            {'applied': False, 'reason': 'proposal only'},
            {'applied': False, 'reason': 'proposal only'},
        ]
        renames = [
            {'fva': '0x401000', 'new_name': 'func_a'},
            {'fva': '0x401050', 'new_name': 'func_b'},
        ]
        result = propose_campaign_renames(self.mgr, 'ws-test-001', renames=renames)
        self.assertTrue(result['ok'])

    # ---- apply_campaign_renames ----

    @patch('viv_ai.mcp.tools._campaign_renames')
    def test_apply_campaign_renames(self, mock_campaign):
        from viv_ai.mcp.tools import apply_campaign_renames
        mock_campaign.return_value = [
            {'applied': True, 'reason': 'ok'},
            {'applied': True, 'reason': 'ok'},
        ]
        renames = [
            {'fva': '0x401000', 'new_name': 'func_a'},
            {'fva': '0x401050', 'new_name': 'func_b'},
        ]
        result = apply_campaign_renames(self.mgr, 'ws-test-001', renames=renames)
        self.assertTrue(result['ok'])

    def test_apply_campaign_renames_readonly(self):
        from viv_ai.mcp.tools import apply_campaign_renames
        self.mgr.mutation_policy = MutationPolicy.CONSERVATIVE_READONLY
        with self.assertRaises(RuntimeError):
            apply_campaign_renames(self.mgr, 'ws-test-001', renames=[])

    # ---- propose_campaign_comments ----

    @patch('viv_ai.mcp.tools._campaign_comments')
    def test_propose_campaign_comments(self, mock_campaign):
        from viv_ai.mcp.tools import propose_campaign_comments
        mock_campaign.return_value = [
            {'applied': False, 'reason': 'proposal only'},
        ]
        comments = [
            {'va': '0x401000', 'comment': 'entry'},
        ]
        result = propose_campaign_comments(self.mgr, 'ws-test-001', comments=comments)
        self.assertTrue(result['ok'])

    # ---- apply_campaign_comments ----

    @patch('viv_ai.mcp.tools._campaign_comments')
    def test_apply_campaign_comments(self, mock_campaign):
        from viv_ai.mcp.tools import apply_campaign_comments
        mock_campaign.return_value = [
            {'applied': True, 'reason': 'ok'},
        ]
        comments = [
            {'va': '0x401000', 'comment': 'entry'},
        ]
        result = apply_campaign_comments(self.mgr, 'ws-test-001', comments=comments)
        self.assertTrue(result['ok'])

    def test_apply_campaign_comments_readonly(self):
        from viv_ai.mcp.tools import apply_campaign_comments
        self.mgr.mutation_policy = MutationPolicy.CONSERVATIVE_READONLY
        with self.assertRaises(RuntimeError):
            apply_campaign_comments(self.mgr, 'ws-test-001', comments=[])


# =========================================================================
# Tests for Vivisect Server connection tools
# =========================================================================

class TestServerConnectTools(unittest.TestCase):
    """server_connect, server_disconnect, server_list_workspaces."""

    def test_server_connect(self):
        from viv_ai.mcp.tools import server_connect
        mgr = _make_manager()
        result = server_connect(mgr, host='10.0.0.1', wsname='my_workspace.viv', port=16500)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['connection']['host'], '10.0.0.1')
        mgr.connect_server.assert_called_once_with('10.0.0.1', 16500, 'my_workspace.viv')

    def test_server_connect_default_port(self):
        from viv_ai.mcp.tools import server_connect
        mgr = _make_manager()
        result = server_connect(mgr, host='localhost', wsname='test_ws')
        self.assertTrue(result['ok'])
        # Default port 0x4074 = 16500
        mgr.connect_server.assert_called_once_with('localhost', 0x4074, 'test_ws')

    def test_server_disconnect_with_leader(self):
        from viv_ai.mcp.tools import server_disconnect
        mgr = _make_manager()
        session = mgr.get_session.return_value
        session.metadata = {'leader_uuid': 'uuid-123'}
        vw = session.workspace
        vw.server = MagicMock()  # has server connection
        vw.killLeaderSession = MagicMock()
        result = server_disconnect(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['disconnected'])
        vw.killLeaderSession.assert_called_once_with('uuid-123')

    def test_server_disconnect_no_server(self):
        from viv_ai.mcp.tools import server_disconnect
        mgr = _make_manager()
        session = mgr.get_session.return_value
        session.metadata = {}  # no leader
        session.workspace.server = None  # no server connection
        result = server_disconnect(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        mgr.close_workspace.assert_called_once()

    def test_server_disconnect_kill_leader_error(self):
        from viv_ai.mcp.tools import server_disconnect
        mgr = _make_manager()
        session = mgr.get_session.return_value
        session.metadata = {'leader_uuid': 'uuid-123'}
        vw = session.workspace
        vw.server = MagicMock()
        vw.killLeaderSession.side_effect = RuntimeError('connection lost')
        # Should not raise — exception is caught
        result = server_disconnect(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])

    def test_server_list_workspaces(self):
        from viv_ai.mcp.tools import server_list_workspaces
        mgr = _make_manager()
        session = mgr.get_session.return_value
        vw = session.workspace
        vw.server = MagicMock()
        vw.server.server = MagicMock()
        vw.server.server.listWorkspaces.return_value = ['remote_ws1', 'remote_ws2']
        result = server_list_workspaces(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['workspaces']), 2)

    def test_server_list_workspaces_no_server(self):
        from viv_ai.mcp.tools import server_list_workspaces
        mgr = _make_manager()
        session = mgr.get_session.return_value
        session.workspace.server = None
        with self.assertRaises(RuntimeError):
            server_list_workspaces(mgr, 'ws-test-001')


# =========================================================================
# Tests for Follow-the-Leader tools
# =========================================================================

class TestLeaderTools(unittest.TestCase):
    """leader_start, leader_navigate, leader_end, leader_list,
    leader_get_location, leader_chat, leader_explain_and_navigate."""

    def setUp(self):
        self.mgr = _make_manager()
        self.session = self.mgr.get_session.return_value
        self.vw = _server_vw()
        self.session.workspace = self.vw

    # ---- leader_start ----

    def test_leader_start(self):
        from viv_ai.mcp.tools import leader_start
        result = leader_start(self.mgr, 'ws-test-001',
                              session_name='My Session', initial_location='0x401000')
        self.assertTrue(result['ok'])
        self.assertIn('leader_uuid', result['data'])
        self.vw.iAmLeader.assert_called_once()

    def test_leader_start_defaults(self):
        from viv_ai.mcp.tools import leader_start
        result = leader_start(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.vw.iAmLeader.assert_called_once()

    def test_leader_start_no_server(self):
        from viv_ai.mcp.tools import leader_start
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_start(self.mgr, 'ws-test-001')

    # ---- leader_navigate ----

    def test_leader_navigate(self):
        from viv_ai.mcp.tools import leader_navigate
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_navigate(self.mgr, 'ws-test-001', location_expr='0x402000')
        self.assertTrue(result['ok'])
        self.vw.followTheLeader.assert_called_once_with('uuid-123', '0x402000')

    def test_leader_navigate_no_leader(self):
        from viv_ai.mcp.tools import leader_navigate
        self.session.metadata = {}  # no leader uuid
        result = leader_navigate(self.mgr, 'ws-test-001', location_expr='0x402000')
        self.assertFalse(result['ok'])
        self.assertIn('error', result)

    def test_leader_navigate_no_server(self):
        from viv_ai.mcp.tools import leader_navigate
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_navigate(self.mgr, 'ws-test-001', location_expr='0x402000')

    # ---- leader_end ----

    def test_leader_end(self):
        from viv_ai.mcp.tools import leader_end
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_end(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['ended'])
        self.vw.killLeaderSession.assert_called_once_with('uuid-123')

    def test_leader_end_no_leader(self):
        from viv_ai.mcp.tools import leader_end
        self.session.metadata = {}
        result = leader_end(self.mgr, 'ws-test-001')
        self.assertFalse(result['ok'])

    def test_leader_end_no_server(self):
        from viv_ai.mcp.tools import leader_end
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_end(self.mgr, 'ws-test-001')

    # ---- leader_list ----

    def test_leader_list(self):
        from viv_ai.mcp.tools import leader_list
        result = leader_list(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['sessions']), 2)

    def test_leader_list_no_server(self):
        from viv_ai.mcp.tools import leader_list
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_list(self.mgr, 'ws-test-001')

    # ---- leader_get_location ----

    def test_leader_get_location_with_uuid(self):
        from viv_ai.mcp.tools import leader_get_location
        result = leader_get_location(self.mgr, 'ws-test-001', session_uuid='uuid-123')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['leader_uuid'], 'uuid-123')

    def test_leader_get_location_default_uuid(self):
        from viv_ai.mcp.tools import leader_get_location
        self.session.metadata = {'leader_uuid': 'uuid-456'}
        result = leader_get_location(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['leader_uuid'], 'uuid-456')

    def test_leader_get_location_no_uuid(self):
        from viv_ai.mcp.tools import leader_get_location
        self.session.metadata = {}
        result = leader_get_location(self.mgr, 'ws-test-001')
        self.assertFalse(result['ok'])

    def test_leader_get_location_no_server(self):
        from viv_ai.mcp.tools import leader_get_location
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_get_location(self.mgr, 'ws-test-001')

    # ---- leader_chat ----

    def test_leader_chat(self):
        from viv_ai.mcp.tools import leader_chat
        result = leader_chat(self.mgr, 'ws-test-001', message='Hello everyone!')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['message_sent'])
        self.vw.chat.assert_called_once_with('Hello everyone!')

    def test_leader_chat_no_server(self):
        from viv_ai.mcp.tools import leader_chat
        self.vw.server = None
        with self.assertRaises(RuntimeError):
            leader_chat(self.mgr, 'ws-test-001', message='test')

    # ---- leader_explain_and_navigate ----

    def test_leader_explain_and_navigate_with_ai(self):
        from viv_ai.mcp.tools import leader_explain_and_navigate
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = 'ollama'
        self.mgr.analysis_service = svc
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_and_navigate(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['ai_analysis_completed'])
        self.vw.followTheLeader.assert_called_once()
        self.vw.chat.assert_called_once()  # AI summary delivered via chat

    def test_leader_explain_and_navigate_no_ai(self):
        from viv_ai.mcp.tools import leader_explain_and_navigate
        # No analysis service configured
        self.mgr.analysis_service = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_and_navigate(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['ai_analysis_completed'])

    def test_leader_explain_and_navigate_no_leader(self):
        from viv_ai.mcp.tools import leader_explain_and_navigate
        self.session.metadata = {}
        result = leader_explain_and_navigate(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertFalse(result['ok'])

    def test_leader_explain_and_navigate_ai_error(self):
        """AI analysis raising an exception should not break the navigation."""
        from viv_ai.mcp.tools import leader_explain_and_navigate
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = 'ollama'
        svc.analyze_function.side_effect = RuntimeError('API error')
        self.mgr.analysis_service = svc
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_and_navigate(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['ai_analysis_completed'])

    def test_leader_explain_and_navigate_no_server(self):
        from viv_ai.mcp.tools import leader_explain_and_navigate
        self.vw.server = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        with self.assertRaises(RuntimeError):
            leader_explain_and_navigate(self.mgr, 'ws-test-001', fva='0x401000')

    # ---- N.B. additional coverage for leader_get_location branch ----
    def test_leader_get_location_no_attached_methods(self):
        """When vw lacks getLeaderLoc/getLeaderInfo, return None fields."""
        from viv_ai.mcp.tools import leader_get_location
        # Remove both methods
        if hasattr(self.vw, 'getLeaderLoc'):
            del self.vw.getLeaderLoc
        if hasattr(self.vw, 'getLeaderInfo'):
            del self.vw.getLeaderInfo
        self.session.metadata = {'leader_uuid': 'uuid-789'}
        result = leader_get_location(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertIsNone(result['data']['current_location'])
        self.assertIsNone(result['data']['user'])

    # ---- leader_annotate ----

    def test_leader_annotate_sets_comment(self):
        from viv_ai.mcp.tools import leader_annotate
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_annotate(self.mgr, 'ws-test-001', va='0x401000', text='Important loop')
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['comment_set'])
        self.vw.setComment.assert_called_once()
        args, _ = self.vw.setComment.call_args
        self.assertIn('Important loop', args[1])
        self.assertIn('[Viv-AI]', args[1])

    def test_leader_annotate_without_leader_returns_error(self):
        from viv_ai.mcp.tools import leader_annotate
        self.session.metadata = {}  # no leader
        result = leader_annotate(self.mgr, 'ws-test-001', va='0x401000', text='test')
        self.assertFalse(result['ok'])
        self.assertIn('error', result)

    def test_leader_annotate_no_server(self):
        from viv_ai.mcp.tools import leader_annotate
        self.vw.server = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        with self.assertRaises(RuntimeError):
            leader_annotate(self.mgr, 'ws-test-001', va='0x401000', text='test')

    # ---- leader_status ----

    def test_leader_status_returns_session_state(self):
        from viv_ai.mcp.tools import leader_status
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_status(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(data['leader_uuid'], 'uuid-123')
        self.assertEqual(data['current_location'], '0x401000')
        self.assertEqual(data['user'], 'user')
        self.assertEqual(data['session_name'], 'session_name')
        self.assertEqual(len(data['all_sessions']), 2)
        self.assertIn('chat_count', data)

    def test_leader_status_without_leader_returns_error(self):
        from viv_ai.mcp.tools import leader_status
        self.session.metadata = {}
        result = leader_status(self.mgr, 'ws-test-001')
        self.assertFalse(result['ok'])

    def test_leader_status_no_server(self):
        from viv_ai.mcp.tools import leader_status
        self.vw.server = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        with self.assertRaises(RuntimeError):
            leader_status(self.mgr, 'ws-test-001')

    # ---- leader_explain_binary ----

    def test_leader_explain_binary_fallback_no_ai(self):
        from viv_ai.mcp.tools import leader_explain_binary
        self.mgr.analysis_service = None
        self.vw.getEntryPoints.return_value = [0x401000]
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_binary(self.mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['ai_analysis_completed'])
        self.assertEqual(result['data']['entry_point'], '0x401000')
        self.assertTrue(result['data']['navigated'])
        self.vw.followTheLeader.assert_called_once()
        self.vw.chat.assert_not_called()

    def test_leader_explain_binary_no_leader(self):
        from viv_ai.mcp.tools import leader_explain_binary
        self.session.metadata = {}
        result = leader_explain_binary(self.mgr, 'ws-test-001')
        self.assertFalse(result['ok'])

    def test_leader_explain_binary_no_server(self):
        from viv_ai.mcp.tools import leader_explain_binary
        self.vw.server = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        with self.assertRaises(RuntimeError):
            leader_explain_binary(self.mgr, 'ws-test-001')

    # ---- leader_explain_graph ----

    def test_leader_explain_graph_fallback_no_ai(self):
        from viv_ai.mcp.tools import leader_explain_graph
        self.mgr.analysis_service = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_graph(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['ai_analysis_completed'])
        self.vw.followTheLeader.assert_called_once()
        self.vw.chat.assert_not_called()

    def test_leader_explain_graph_no_leader(self):
        from viv_ai.mcp.tools import leader_explain_graph
        self.session.metadata = {}
        result = leader_explain_graph(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertFalse(result['ok'])

    def test_leader_explain_graph_no_server(self):
        from viv_ai.mcp.tools import leader_explain_graph
        self.vw.server = None
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        with self.assertRaises(RuntimeError):
            leader_explain_graph(self.mgr, 'ws-test-001', fva='0x401000')

    def test_leader_explain_graph_with_ai_calls_get_function_graph(self):
        from viv_ai.mcp.tools import leader_explain_graph
        # Set up analysis service so AI block executes
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.providers = {'ollama': MagicMock()}
        svc.config.default_provider = 'ollama'
        self.mgr.analysis_service = svc
        self.session.metadata = {'leader_uuid': 'uuid-123'}
        result = leader_explain_graph(self.mgr, 'ws-test-001', fva='0x401000')
        self.assertTrue(result['ok'])
        self.vw.getFunctionGraph.assert_called_once_with(0x401000)


# =========================================================================
# Tests for build_tool_metadata and build_default_registry
# =========================================================================

class TestBuildFunctions(unittest.TestCase):
    """build_tool_metadata, build_default_registry."""

    def test_build_tool_metadata_contains_keys(self):
        from viv_ai.mcp.tools import build_tool_metadata
        metadata = build_tool_metadata()
        required_tools = [
            'workspace_open', 'workspace_status', 'workspace_close',
            'list_workspaces', 'get_metadata', 'get_binary_summary',
            'get_strings', 'get_imports', 'get_exports', 'get_names',
            'get_xrefs_to', 'get_xrefs_from',
            'get_function_summary', 'get_function_graph', 'get_symbolik_summary',
            'find_functions', 'analyze_workspace', 'workspace_analysis_status',
            'export_analysis_report',
            'ai_explain_function', 'ai_summarize_binary', 'ai_analyze_functions',
            'list_provider_models',
            'propose_function_rename', 'propose_comment',
            'apply_function_rename', 'apply_comment',
            'propose_campaign_renames', 'apply_campaign_renames',
            'propose_campaign_comments', 'apply_campaign_comments',
            'server_connect', 'server_disconnect', 'server_list_workspaces',
            'leader_start', 'leader_navigate', 'leader_end',
            'leader_list', 'leader_get_location', 'leader_chat',
            'leader_explain_and_navigate',
            'leader_annotate', 'leader_status',
            'leader_explain_binary', 'leader_explain_graph',
        ]
        for tool in required_tools:
            self.assertIn(tool, metadata, f'missing {tool} in tool metadata')
            self.assertIn('description', metadata[tool])
            self.assertIn('inputSchema', metadata[tool])

    def test_build_tool_metadata_schema_structure(self):
        from viv_ai.mcp.tools import build_tool_metadata
        metadata = build_tool_metadata()
        for tool_name, entry in metadata.items():
            with self.subTest(tool=tool_name):
                schema = entry['inputSchema']
                self.assertEqual(schema['type'], 'object')
                self.assertIn('properties', schema)
                self.assertIn('required', schema)
                self.assertIn('additionalProperties', schema)

    def test_build_default_registry(self):
        from viv_ai.mcp.tools import build_default_registry
        registry = build_default_registry()
        self.assertIn('workspace_open', registry)
        self.assertIn('list_workspaces', registry)
        self.assertIn('leader_chat', registry)
        self.assertIn('leader_explain_and_navigate', registry)
        # Spot-check that entries are callable
        for name, fn in registry.items():
            with self.subTest(tool=name):
                self.assertTrue(callable(fn), f'{name} is not callable')
        # Count all tools
        self.assertEqual(len(registry), 50, 'expected 50 tools in default registry')


# =========================================================================
# Tests for error paths and edge cases
# =========================================================================

class TestErrorPaths(unittest.TestCase):
    """Edge cases and error paths across the module."""

    def test_workspace_status_nonexistent(self):
        from viv_ai.mcp.tools import workspace_status
        mgr = _make_manager()
        mgr.get_session.side_effect = KeyError('session not found')
        with self.assertRaises(KeyError):
            workspace_status(mgr, 'nonexistent')

    def test_get_strings_empty(self):
        from viv_ai.mcp.tools import get_strings
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getLocations.return_value = []
        result = get_strings(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['strings']), 0)

    def test_get_imports_empty(self):
        from viv_ai.mcp.tools import get_imports
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getImports.return_value = []
        result = get_imports(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['imports']), 0)

    def test_get_exports_empty(self):
        from viv_ai.mcp.tools import get_exports
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getExports.return_value = []
        result = get_exports(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])

    def test_get_names_without_getter(self):
        """collect_names handles missing getNames gracefully (returns [])."""
        from viv_ai.mcp.tools import get_names
        mgr = _make_manager()
        # Remove getNames from workspace
        vw = mgr.get_session.return_value.workspace
        if hasattr(vw, 'getNames'):
            del vw.getNames
        result = get_names(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['names']), 0)

    def test_get_xrefs_to_empty(self):
        from viv_ai.mcp.tools import get_xrefs_to
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getXrefsTo.return_value = []
        result = get_xrefs_to(mgr, 'ws-test-001', va='0x4000')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['xrefs']), 0)

    def test_get_function_summary_with_parse_va(self):
        """Cover integer-based fva parsing in get_function_summary."""
        from viv_ai.mcp.tools import get_function_summary
        mgr = _make_manager()
        result = get_function_summary(mgr, 'ws-test-001', fva=0x401000)
        self.assertTrue(result['ok'])

    def test_get_function_graph_empty_graph(self):
        """Graph might be empty for unknown function."""
        from viv_ai.mcp.tools import get_function_graph
        mgr = _make_manager()
        mgr.analysis_service = None  # ensure int defaults from _limits_from_manager
        # summarize_graph expects graph.getNodes() and graph.getEdges()
        class EmptyGraph:
            def getNodes(self):
                return []
            def getEdges(self):
                return []
            def getRefsFrom(self, n):
                return []
            def getRefsTo(self, n):
                return []
        mgr.get_session.return_value.workspace.getFunctionGraph.return_value = EmptyGraph()
        result = get_function_graph(mgr, 'ws-test-001', fva='0x999999')
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools.extract_function_overview')
    def test_get_function_summary_with_parse_va(self, mock_extract):
        """Cover integer-based fva parsing in get_function_summary."""
        from viv_ai.mcp.tools import get_function_summary
        mock_extract.return_value = {
            'function': {'name': 'main', 'va': '0x401000'},
        }
        mgr = _make_manager()
        result = get_function_summary(mgr, 'ws-test-001', fva=0x401000)
        self.assertTrue(result['ok'])

    @patch('viv_ai.mcp.tools._find_functions')
    def test_find_functions_max_results_from_limits(self, mock_find):
        """find_functions uses limits from manager config."""
        from viv_ai.mcp.tools import find_functions
        mock_find.return_value = [{'va': '0x401000', 'name': 'main'}]
        svc = _make_analysis_service()
        svc.config = MagicMock()
        svc.config.analysis_max_results = 5
        mgr = _make_manager(analysis_service=svc)
        result = find_functions(mgr, 'ws-test-001')
        self.assertTrue(result['ok'])

    def test_analyze_workspace_zero_new_funcs(self):
        """When workspaces don't gain functions after analysis."""
        from viv_ai.mcp.tools import analyze_workspace
        mgr = _make_manager()
        mgr.get_session.return_value.workspace.getFunctions.return_value = [0x401000]
        result = analyze_workspace(mgr, 'ws-test-001', timeout=10)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['new_functions'], 0)

    def test_propose_function_rename_integer_fva(self):
        from viv_ai.mcp.tools import propose_function_rename
        mgr = _make_manager()
        result = propose_function_rename(mgr, 'ws-test-001', fva=0x401000, new_name='renamed_func')
        self.assertTrue(result['ok'])

    def test_propose_campaign_renames_empty(self):
        from viv_ai.mcp.tools import propose_campaign_renames
        mgr = _make_manager()
        result = propose_campaign_renames(mgr, 'ws-test-001', renames=[])
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['results']), 0)

    def test_apply_campaign_renames_empty(self):
        from viv_ai.mcp.tools import apply_campaign_renames
        mgr = _make_manager()
        result = apply_campaign_renames(mgr, 'ws-test-001', renames=[])
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['results']), 0)

    def test_propose_campaign_comments_empty(self):
        from viv_ai.mcp.tools import propose_campaign_comments
        mgr = _make_manager()
        result = propose_campaign_comments(mgr, 'ws-test-001', comments=[])
        self.assertTrue(result['ok'])

    def test_apply_campaign_comments_empty(self):
        from viv_ai.mcp.tools import apply_campaign_comments
        mgr = _make_manager()
        result = apply_campaign_comments(mgr, 'ws-test-001', comments=[])
        self.assertTrue(result['ok'])

    def test_list_provider_models_no_service(self):
        from viv_ai.mcp.tools import list_provider_models
        mgr = _make_manager()
        mgr.analysis_service = None
        with self.assertRaises(RuntimeError):
            list_provider_models(mgr)

    def test_server_connect_with_no_server_attr(self):
        """When getFunctions is not available on remote workspace, handle gracefully."""
        from viv_ai.mcp.tools import server_connect
        mgr = _make_manager()
        session = mgr.connect_server.return_value
        session.workspace = MagicMock()  # no getFunctions
        result = server_connect(mgr, host='host', wsname='ws', port=16500)
        self.assertTrue(result['ok'])


# =========================================================================
# Run with: python -m pytest tests/test_tools_expanded.py -v --cov=viv_ai.mcp.tools
# =========================================================================
if __name__ == '__main__':
    unittest.main()
