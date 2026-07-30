"""Tests for validation_analysis_limits schema validator."""

import pytest
from viv_ai.mcp.formatters import validate_analysis_limits


def test_validate_defaults():
    """validate_analysis_limits with None returns all defaults."""
    result = validate_analysis_limits(None)
    assert isinstance(result, dict)
    assert 'max_nodes' in result
    assert 'max_results' in result
    assert result['max_nodes'] == 32


def test_validate_custom():
    """Custom config values are validated and returned."""
    class FakeConfig:
        analysis_max_nodes = 100
        analysis_max_paths = 5
    
    result = validate_analysis_limits(FakeConfig())
    assert result['max_nodes'] == 100
    assert result['max_paths'] == 5


def test_validate_negative_raises():
    """Negative values raise ValueError."""
    class FakeConfig:
        analysis_max_nodes = -1
    
    with pytest.raises(ValueError) as exc_info:
        validate_analysis_limits(FakeConfig())
    
    assert 'negative' in str(exc_info.value).lower()


def test_validate_non_int_raises():
    """Non-integer values raise ValueError."""
    class FakeConfig:
        analysis_max_nodes = "invalid"
    
    with pytest.raises(ValueError) as exc_info:
        validate_analysis_limits(FakeConfig())
    
    assert 'not an integer' in str(exc_info.value).lower()


def test_validate_zero_ok():
    """Zero is valid (means disabled)."""
    class FakeConfig:
        analysis_max_nodes = 0
    
    result = validate_analysis_limits(FakeConfig())
    assert result['max_nodes'] == 0
