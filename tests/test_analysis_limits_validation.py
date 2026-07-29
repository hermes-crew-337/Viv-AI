from viv_ai.mcp.formatters import analysis_limits_from_config


def test_defaults():
    """When config is None, use defaults."""
    result = analysis_limits_from_config(None)
    assert isinstance(result, dict)
    # Check for expected keys (defaults from formatters.py)
    assert 'max_nodes' in result
    assert 'max_results' in result


def test_custom_values():
    """Custom config values override defaults."""
    class FakeConfig:
        analysis_max_nodes = 100
        analysis_max_results = 50
    
    result = analysis_limits_from_config(FakeConfig())
    assert result["max_nodes"] == 100
    assert result["max_results"] == 50
    # Unspecified keys should fallback to defaults (handled by formatters.py logic)
