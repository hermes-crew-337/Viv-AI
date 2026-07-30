# Phase S: Advanced Reasoning and Batch Workflows

> **Status:** Active
> **Branch:** `feat/phase-q-http-maturity` (continues on same branch)
> **Tests:** 317 baseline → target ~360+

**Goal:** Increase analysis power and throughput with batch function analysis, rename/comment campaigns, richer graph/symbolik cross-linking, export/report generation, and hardened bounded-output controls.

---

### Task 1: Add `ai_analyze_functions` batch MCP tool

**Objective:** Allow the MCP client to request AI analysis of multiple functions at once.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py` — add `ai_analyze_functions` handler + metadata
- Modify: `src/viv_ai/service.py` — add `analyze_functions()` method
- Test: `tests/test_tools.py` — add tests (mock workspace)

**Step 1: Add `analyze_functions` to `AnalysisService`**

Add to `service.py` after `analyze_function`:

```python
def analyze_functions(self, vw: Any, fvas: list[int], options: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
    results = []
    for fva in fvas:
        try:
            result = self.analyze_function(vw, fva, options)
            result['fva'] = f'0x{fva:08x}'
            results.append(result)
        except AnalysisError as exc:
            results.append({
                'fva': f'0x{fva:08x}',
                'error': str(exc),
                'task_type': 'function_summary',
            })
    return results
```

**Step 2: Register metadata and handler in `tools.py`**

Add to `build_tool_metadata()`:
```python
'ai_analyze_functions': {
    'description': 'Batch AI analysis of multiple functions in one request.',
    'inputSchema': _schema({
        'workspace_id': workspace_id,
        'fvas': {'type': 'array', 'items': hex_addr, 'description': 'List of function VAs to analyze.'},
        'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10},
    }, ['workspace_id', 'fvas']),
    'annotations': {'readOnlyHint': True},
},
```

Add handler:
```python
def ai_analyze_functions(manager: WorkspaceSessionManager, workspace_id: str, fvas: list[Any], **kwargs) -> Dict[str, Any]:
    workspace = manager.get_workspace(workspace_id)
    parsed = [parse_va(fva) for fva in fvas]
    options = _options_from_kwargs(kwargs, 'workspace_id', 'fvas')
    results = _analysis_service(manager).analyze_functions(workspace, parsed, options=options)
    succeeded = sum(1 for r in results if 'error' not in r)
    return ToolResponse.ok(workspace_id, 'function', {'results': results}, provenance={'tool': 'ai_analyze_functions'}, summary=f'analyzed {succeeded}/{len(results)} functions').to_dict()
```

**Step 3: Register in `build_default_registry()`**

**Step 4: Write tests and verify**

---

### Task 2: Add function discovery/filtering tool

**Objective:** Allow MCP clients to discover functions matching criteria (by name pattern, caller count, size, etc.).

**Files:**
- Modify: `src/viv_ai/extractors.py` — add `find_functions()`  
- Modify: `src/viv_ai/mcp/tools.py` — add `find_functions` tool
- Test: `tests/test_tools.py` or new `tests/test_extractors.py`  

**New function in `extractors.py`:**
```python
def find_functions(vw: Any, name_glob: str | None = None, min_callers: int = 0, max_results: int = 32) -> list[Dict[str, Any]]:
    matches = []
    for fva in vw.getFunctions():
        name = _safe_get_name(vw, fva)
        if name_glob and not _glob_match(name, name_glob):
            continue
        stats = _collect_function_stats(vw, fva)
        if min_callers > 0 and stats['caller_count'] < min_callers:
            continue
        matches.append(stats)
        if len(matches) >= max_results:
            break
    return matches
```

Where `_glob_match` is a simple fnmatch check.

**New MCP tool metadata:**
```python
'find_functions': {
    'description': 'Discover functions matching optional filters (name pattern, minimum caller count).',
    'inputSchema': _schema({
        'workspace_id': workspace_id,
        'name_glob': {'type': 'string', 'description': 'Optional name glob pattern (e.g. "sub_*", "*crypto*").'},
        'min_callers': {'type': 'integer', 'minimum': 0, 'default': 0},
        'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 32},
    }, ['workspace_id']),
    'annotations': {'readOnlyHint': True},
},
```

---

### Task 3: Rename/comment campaign tool

**Objective:** Batch proposal and application of AI-suggested names/comments across a set of functions.

**Files:**
- Create: `src/viv_ai/campaign.py` — campaign logic
- Modify: `src/viv_ai/mcp/tools.py` — add `propose_campaign_renames` / `apply_campaign_renames`
- Test: `tests/test_campaign.py`, `tests/test_tools.py`

**`campaign.py`:**
```python
from typing import Any, Dict, List, Optional
from .apply import apply_function_rename, apply_comment_suggestion
from .models import MutationPolicy

def campaign_rename_function(vw: Any, fva: int, new_name: str, policy: MutationPolicy) -> Dict[str, Any]:
    return apply_function_rename(vw, fva, new_name, policy)

def campaign_comment_function(vw: Any, fva: int, va: int, comment: str, policy: MutationPolicy) -> Dict[str, Any]:
    return apply_comment_suggestion(vw, va, comment, policy)
```

---

### Task 4: Export/report generation tool

**Objective:** Generate structured reports from analysis results.

**Files:**
- Create: `src/viv_ai/export.py` — report generation
- Modify: `src/viv_ai/mcp/tools.py` — add `export_analysis_report`
- Test: `tests/test_export.py`

**Report tool output schema:** markdown text with function summaries, severity, confidence, evidence.

---

### Task 5: Hardened bounded-output controls

**Objective:** Make all truncation limits configurable from config, add pagination support to list-like tools.

**Files:**
- Modify: `src/viv_ai/config.py` — add truncation defaults
- Modify: `src/viv_ai/extractors.py` — wire configurable limits
- Modify: `src/viv_ai/mcp/formatters.py` — add pagination helpers
- Modify: `src/viv_ai/mcp/tools.py` — wire pagination where appropriate
