"""Shared pytest fixtures for Viv-AI tests.

Provides mock workspace objects, config instances, and factory functions
used across multiple test modules.  All fixtures are scoped to function
(default) unless noted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Mock vivisect workspace helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vw() -> MagicMock:
    """A generic vivisect workspace with stubs for common methods.

    Default behaviour:
    - getMeta(key, default) returns default.
    - getFunctions() returns [].
    - getEntryPoints() returns [].
    - getLocations(ltype) returns [].
    - getImports() returns [].
    - getExports() returns [].
    - getNames() returns [].
    - reprLocation(loc) returns str(loc).
    """
    vw = MagicMock()
    vw.getMeta.side_effect = lambda key, default=None: default
    vw.getFunctions.return_value = []
    vw.getEntryPoints.return_value = []
    vw.getLocations.return_value = []
    vw.getImports.return_value = []
    vw.getExports.return_value = []
    vw.getNames.return_value = []
    vw.reprLocation.side_effect = lambda loc: str(loc)
    vw.getFunctionGraph.return_value = MagicMock()
    return vw


@pytest.fixture
def mock_vw_with_funcs(mock_vw) -> MagicMock:
    """A workspace with a few named functions."""
    mock_vw.getFunctions.return_value = [
        0x401000, 0x401050, 0x401100,
    ]
    mock_vw.getFunctionMetaDict.return_value = {
        0x401000: {'Name': 'main', 'Size': 128},
        0x401050: {'Name': 'helper', 'Size': 64},
        0x401100: {'Name': 'parse_input', 'Size': 256},
    }
    return mock_vw


@pytest.fixture
def mock_manager() -> MagicMock:
    """A WorkspaceSessionManager with auto-created sessions."""
    manager = MagicMock()
    session = MagicMock()
    session.workspace_id = 'ws-test-001'
    session.path = '/tmp/test.viv'
    session.workspace = MagicMock()
    session.metadata = {}
    manager.get_session.return_value = session
    manager.list_sessions.return_value = {'ws-test-001': session}
    return manager


@pytest.fixture
def mock_analysis_service() -> MagicMock:
    """A mock AnalysisService with a controllable analyze_function."""
    service = MagicMock()
    service.analyze_function.return_value = {
        'fva': '0x401000',
        'name': 'test_func',
        'analysis': {
            'summary': 'Test analysis summary',
            'confidence': 'high',
            'purpose': 'testing',
        },
    }
    service.analyze_binary.return_value = {
        'summary': 'Binary summary',
        'confidence': 'medium',
    }
    service.analyze_functions.return_value = [
        {'fva': '0x401000', 'analysis': {'summary': 'func1'}},
        {'fva': '0x401050', 'analysis': {'summary': 'func2'}},
    ]
    service.provider_status.return_value = {
        'provider_name': 'ollama',
        'available_models': ['llama3', 'qwen2.5'],
    }
    return service


@pytest.fixture
def mock_manager_with_service(mock_manager, mock_analysis_service) -> MagicMock:
    """Manager with a real-like analysis_service attached."""
    mock_manager.analysis_service = mock_analysis_service
    return mock_manager
