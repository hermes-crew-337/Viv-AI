# Phase T: CI & Hardening

> **Status:** In Progress (July 28, 2026)
> **Branch target:** feat/phase-q-http-maturity (PR #3)
> **Focus:** CI pipeline, multi-model orchestration, analysis limits, pagination validation, provider discovery

**Goal:** Turn Viv-AI into a hardened, CI-validated system. Add a GitHub Actions test matrix, systematically validate pagination and analysis-limit edge cases, exercise the provider-discovery and multi-model AI tools, and add config schema validation for analysis limits.

**Architecture:** Pure additions — new CI workflow file, new tests, new config validation helpers. No changes to existing tool signatures or data shapes. The Phase T deliverables are the CI pipeline and the test-hardening layer.

---

## Requirements captured from atlas

1. CI must run on every push and PR to origin/main — Linux (Ubuntu), Python 3.11+.
2. Pagination must be validated at every boundary: empty results, single page, multi-page, last page, offset past end.
3. Analysis limits must be validated as a config schema — bad values should fail early with clear messages.
4. Multi-model orchestration tools (ai_explain_function, ai_summarize_binary, ai_analyze_functions) must work on at least one configured provider.
5. Provider discovery (list_provider_models) must return live model lists from configured providers.
6. Test suite must report total coverage metrics.

---

## Proposed MCP UX

No new MCP tools for Phase T. This is purely infrastructure and hardening.

---

## Tasks

### Task 1: GitHub Actions CI workflow

- Create `.github/workflows/ci.yml`
- Matrix: Python 3.11, 3.12, 3.13
- Steps: checkout → setup Python → cache pip → install deps → run `make test` or `pytest`
- Upload coverage report (optional, to Codecov or as artifact)
- Add `make test` if not present

### Task 2: Pagination validation suite

- **Empty pagination**: tool returning 0 results still returns valid pagination block (`total=0, offset=0, limit=32, has_more=False`)
- **Single page under limit**: fewer results than limit → no `has_more` / `next_offset`
- **Exact page**: results == limit → `has_more=True`
- **Last page**: partial results → `has_more=False`
- **Offset past end**: offset >= total → empty result set with correct pagination metadata
- **Mid-page offset**: offset in the middle of results → correct page
- **All paginated tools** (get_strings, get_imports, get_exports, get_names, get_xrefs_to, get_xrefs_from, find_functions): test at least 3 boundary cases each
- **discover_files pagination**: test via workspace_discover tool

### Task 3: Analysis limits config schema

- Add `viv_ai.config.validate_analysis_limits()` function
- Expected keys with types and bounds:
  - `max_strings`: int, ≥0, default 200
  - `max_imports`: int, ≥0, default 100
  - `max_exports`: int, ≥0, default 100
  - `max_names`: int, ≥0, default 200
  - `max_xrefs`: int, ≥0, default 200
  - `max_functions`: int, ≥0, default 100
  - `max_function_detail`: int, ≥0, default 50
  - `max_constraints`: int, ≥0, default 20
  - `max_effects`: int, ≥0, default 20
  - `per_path_timeout`: int, ≥0, default 15
  - `total_timeout`: int, ≥0, default 60
- Reject unknown keys with warning
- Reject non-int, negative values with ValueError
- Compare with `ANALYSIS_LIMITS_DEFAULTS` in formatters.py

### Task 4: Multi-model orchestration & provider discovery hardening

- `list_provider_models` smoke tests against mock provider (no live Ollama needed)
- `ai_explain_function` with no AI service → graceful error, not crash
- `ai_summarize_binary` with no AI service → graceful error
- `ai_analyze_functions` with no AI service → graceful error
- All AI tools report meaningful errors when provider is unavailable

### Task 5: CI hardening & coverage

- Add `make coverage` target
- Add `.coveragerc` or `pyproject.toml` coverage config (exclude tests, .venv, __pycache__)
- Coverage threshold gate (optional, 70%+)
- Ensure CI fails on test failures

---

## New files

```
.github/workflows/ci.yml
```

## Modified files (expected)

```
pyproject.toml          — coverage config, make targets
tests/test_mcp_tools.py — pagination boundary tests
tests/test_mcp_filesystem.py — discover pagination tests
tests/test_tools_expanded.py — analysis limits validation tests, AI tool error tests
```

---

## Verification

1. `pytest tests/` — all pass
2. `.github/workflows/ci.yml` validates with `act --dry-run` or manual review
3. Pagination tests cover all 7 boundary cases for at least 3 tools
4. `validate_analysis_limits()` rejects bad configs and accepts good ones
5. AI tool error handling tested without live Ollama

---

## References

- Existing: `src/viv_ai/mcp/formatters.py` — `analysis_limits_from_config`, `pagination_meta`
- Existing: `src/viv_ai/mcp/tools.py` — paginated tools, AI tools, list_provider_models
- Existing: `src/viv_ai/config.py` — config loading, defaults
- Existing: `tests/test_mcp_tools.py` — pagination smoke tests
- Existing: `tests/test_tools_expanded.py` — AI tool + provider tests
