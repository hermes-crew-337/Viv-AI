# Phase V: Workspace Discovery, Auto-Open, and LRU Cache

> **Status:** Proposed
> **Branch target:** new feature branch off current Viv-AI MCP line
> **Focus:** make file access and workspace selection trivial for LLM/MCP clients

**Goal:** Let the MCP server expose a clear file inventory, auto-open or reuse VivWorkspaces on demand, prefer existing `.viv` files by default, and keep recently used workspaces cached under configurable LRU limits.

**Architecture:** Introduce a filesystem-access layer plus a workspace-catalog/cache layer. Every tool that needs a workspace should resolve a serializable selector (`workspace_id`, path, alias, or server workspace name) into a cached/open workspace, loading or creating it on demand. The cache remains server-side and enforces count + size limits with least-recently-used eviction.

**Tech stack:** existing `viv_ai.mcp` server/session/tool stack, Vivisect `VivWorkspace`, Python dataclasses, bounded MCP JSON responses, pytest/unittest.

---

## Requirements captured from atlas

1. On server deployments, file access should be broad and easy.
2. On non-server deployments, file access should be rooted at a CLI-provided base directory.
3. Existing `.viv` files should be reused by default.
4. Re-analysis must be possible on demand.
5. Re-analysis must support preserving the old `.viv` artifact.
6. Multiple VivWorkspaces must be easy for the LLM to discover and address.
7. The LLM should be able to see what files/workspaces are available.
8. Workspaces should be cached across MCP calls.
9. Cache limits should be configurable by count and size.
10. When the cache is full, evict the least recently used workspace.
11. If a tool needs a workspace and none is open yet, auto-load/create it and tell the caller what happened.

---

## Proposed MCP UX

### Workspace selectors

All workspace-requiring tools should accept a **workspace selector** instead of only `workspace_id`:

- `workspace_id` — existing cached/open workspace
- `path` — binary path or `.viv` path under allowed roots
- `workspace_name` — server workspace name when in remote/server mode
- `alias` — stable alias derived from filename or assigned by catalog logic

Resolution priority:
1. explicit `workspace_id`
2. exact cached path match
3. exact cached alias match
4. remote server workspace name
5. local path auto-open

### What the LLM sees

Add tools that make the environment legible:

- `list_files` — bounded recursive file listing under allowed roots
- `get_file_info` — stat-like metadata, type, size, sibling `.viv` presence
- `list_workspace_catalog` — known binaries, `.viv` files, server workspaces, aliases, cached/open status
- `workspace_open` — explicit open/reuse/reanalyze entrypoint
- `list_workspaces` — currently cached/open sessions with LRU metadata
- `workspace_status` — include whether the workspace was cached, loaded from `.viv`, or freshly analyzed

### Auto-open behavior

Any tool that requires a workspace should:
1. resolve selector
2. reuse cached workspace if present
3. otherwise load existing `.viv` if available and allowed
4. otherwise open binary and analyze/create workspace
5. return structured provenance saying which path occurred

Example provenance payload:

```json
{
  "tool": "get_function_summary",
  "workspace_resolution": {
    "mode": "auto_open",
    "selector": {"path": "/samples/a.out"},
    "cache_hit": false,
    "loaded_from_viv": true,
    "created_workspace": false,
    "preserved_existing_viv": false
  }
}
```

---

## CLI / config surface

### New entrypoint flags

Add to `src/viv_ai/mcp/entrypoint.py`:

- `--base-dir PATH` — root directory for local file discovery and path validation
- `--allow-root` — explicit opt-in for full filesystem exposure on the host
- `--server-mode` — enables server-oriented defaults and server workspace discovery behavior
- `--workspace-cache-count N` — max cached workspaces
- `--workspace-cache-bytes N` — soft max estimated bytes across cached workspaces
- `--workspace-max-bytes N` — optional per-workspace refusal threshold/warning threshold
- `--prefer-existing-viv / --no-prefer-existing-viv`
- `--force-reanalyze`
- `--preserve-existing-viv`
- `--preserve-viv-suffix .bak-<timestamp>` or a simpler backup directory/suffix option

### New config fields

Add to `AiConfig` in `src/viv_ai/config.py`:

- `mcp_base_dir: str | None = None`
- `mcp_allow_root: bool = False`
- `mcp_server_mode: bool = False`
- `mcp_workspace_cache_count: int = 8`
- `mcp_workspace_cache_bytes: int = 2 * 1024 * 1024 * 1024`
- `mcp_workspace_max_bytes: int = 0`  # 0 = unlimited
- `mcp_prefer_existing_viv: bool = True`
- `mcp_force_reanalyze: bool = False`
- `mcp_preserve_existing_viv: bool = True`

Validation rules:
- reject negative sizes/counts
- require `--allow-root` for unrestricted `/`
- normalize `base_dir` to absolute path

---

## Code changes by area

### Task 1: Add file-access policy + catalog primitives

**Objective:** Create a single source of truth for what paths are visible and valid.

**Files:**
- Create: `src/viv_ai/mcp/filesystem.py`
- Modify: `src/viv_ai/mcp/session.py`
- Test: `tests/test_mcp_filesystem.py`

**Implementation notes:**
- Add a `FilesystemPolicy` dataclass:
  - `base_dir`
  - `allow_root`
  - `server_mode`
- Add helpers:
  - `normalize_path(path)`
  - `is_allowed_path(path)`
  - `discover_files(root, limit, offset, suffixes)`
  - `find_candidate_workspace_files(path)`
- Treat `.viv` files and binaries as catalogable entries.
- In server mode, default root should be `/` only when explicitly allowed.

**Tests:**
- allows paths under base dir
- rejects traversal outside base dir
- enumerates `.viv` and non-`.viv` files predictably
- root exposure requires explicit opt-in

---

### Task 2: Extend session objects with cache and provenance metadata

**Objective:** Track enough metadata for LRU, file provenance, and user-facing explanations.

**Files:**
- Modify: `src/viv_ai/mcp/session.py`
- Test: `tests/test_mcp_session.py`

**Implementation notes:**
- Extend `WorkspaceSession` with:
  - `selector_path`
  - `binary_path`
  - `viv_path`
  - `alias`
  - `source_kind` (`local_binary`, `local_viv`, `remote_workspace`)
  - `loaded_from_viv: bool`
  - `created_from_binary: bool`
  - `analysis_started: bool`
  - `analysis_completed: bool`
  - `estimated_size_bytes: int`
  - `last_accessed_ts: float`
  - `open_count: int`
- Add `touch()` method or manager-side access update.
- `to_dict()` should include cache-related metadata safe for MCP output.

**Tests:**
- access updates `last_accessed_ts`
- metadata serializes cleanly
- existing path reuse still works

---

### Task 3: Implement LRU workspace cache manager

**Objective:** Enforce count/size limits and evict least recently used sessions.

**Files:**
- Modify: `src/viv_ai/mcp/session.py`
- Test: `tests/test_mcp_session.py`

**Implementation notes:**
- Keep path and alias indexes.
- Before inserting a new session:
  - estimate its size
  - evict oldest `last_accessed_ts` entries until under limits
- Refuse or warn on over-limit single workspaces depending on config.
- When evicting, return metadata describing what got dropped.
- On every `get_workspace()` / `get_session()`, update LRU state.

**Tests:**
- evicts LRU on count overflow
- evicts enough entries on byte overflow
- does not evict active hit when re-accessed
- reports eviction metadata

---

### Task 4: Teach the loader to prefer existing `.viv` files

**Objective:** Reuse analysis artifacts by default and support explicit re-analysis.

**Files:**
- Modify: `src/viv_ai/mcp/entrypoint.py`
- Modify: `src/viv_ai/mcp/session.py`
- Possibly create: `src/viv_ai/mcp/workspace_loader.py`
- Test: `tests/test_mcp_entrypoint.py`
- Test: `tests/test_mcp_session.py`

**Implementation notes:**
- Replace bare `_viv_load(path)` with a richer loader plan:
  - if input path ends in `.viv`, load it directly
  - if input is a binary and sibling `.viv` exists and preference enabled, load sibling `.viv`
  - if `force_reanalyze`, ignore sibling `.viv`
  - if `preserve_existing_viv`, rename/copy old `.viv` before re-analysis
  - after loading binary directly, start analysis and save/create `.viv` if appropriate
- Return both workspace object and load metadata.

**Tests:**
- sibling `.viv` is preferred by default
- `force_reanalyze=True` bypasses `.viv`
- preserve option creates backup behavior metadata
- direct `.viv` path load is supported

---

### Task 5: Add workspace selector resolution + auto-open path

**Objective:** Let all analysis tools work even when the caller only knows a path or alias.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py`
- Modify: `src/viv_ai/mcp/session.py`
- Test: `tests/test_mcp_tools.py`

**Implementation notes:**
- Introduce a shared resolver, e.g. `resolve_workspace_for_tool(...)`.
- Accept either:
  - `workspace_id`
  - `path`
  - `alias`
  - `workspace_name`
- Update all workspace-using tools to call resolver rather than raw `workspace_id` lookup.
- Response should clearly state whether it was:
  - cache hit
  - cache miss + loaded existing `.viv`
  - cache miss + loaded remote workspace
  - cache miss + created/analyzed new workspace

**Tests:**
- `get_metadata(path=...)` auto-opens
- `get_function_summary(alias=...)` resolves cached workspace
- unknown selectors return useful structured errors

---

### Task 6: Add file and catalog discovery MCP tools

**Objective:** Make available files/workspaces obvious to the LLM.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py`
- Test: `tests/test_mcp_tools.py`

**New tools:**
- `list_files(base_subpath='', suffixes=[], limit=100, offset=0)`
- `get_file_info(path)`
- `list_workspace_catalog(limit=100, offset=0)`

**Response design:**
- bounded, paginated
- include path, type, size, matching `.viv`, alias suggestion, cached/open flag
- in server mode, include remote workspace names when available

**Tests:**
- list is bounded and paginated
- `.viv` relationships are surfaced
- server/local catalog entries can coexist

---

### Task 7: Expand `workspace_open`, `workspace_status`, and `list_workspaces`

**Objective:** Surface all important cache/provenance details.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py`
- Test: `tests/test_mcp_tools.py`
- Test: `tests/test_mcp_entrypoint.py`

**Implementation notes:**
- `workspace_open` should accept:
  - `path`
  - `alias`
  - `workspace_name`
  - `force_reanalyze`
  - `preserve_existing_viv`
- `workspace_status` should include:
  - cache state
  - source kind
  - analysis status
  - `.viv` reuse vs fresh analysis
  - last accessed
  - estimated size
- `list_workspaces` should sort by most recently used first.

**Tests:**
- summaries mention cache hit vs auto-open
- status reports `.viv` provenance
- list ordering follows LRU recency

---

### Task 8: Documentation + examples

**Objective:** Make the feature discoverable for Hermes and other MCP clients.

**Files:**
- Modify: `docs/mcp-client-usage.md`
- Modify: `README.md`
- Optionally add: `docs/workspace-discovery.md`

**Docs to include:**
- local mode with `--base-dir /path/to/tree`
- server deployment with broad filesystem access
- how `.viv` reuse works by default
- how to force re-analysis safely
- how auto-open works from path-only calls
- example multi-workspace workflow for an LLM

---

## Tool schema changes

Current schema hard-codes `workspace_id` for most tools. Update metadata so clients can discover the easier path-based API.

Preferred pattern:

```python
workspace_selector = {
    'type': 'object',
    'properties': {
        'workspace_id': {'type': 'string'},
        'path': {'type': 'string'},
        'alias': {'type': 'string'},
        'workspace_name': {'type': 'string'},
    },
}
```

In practice, because MCP clients handle flat schemas more predictably, keep flat optional fields on each tool and validate that at least one selector field is present.

---

## Suggested implementation order

1. filesystem policy
2. richer session metadata
3. LRU cache
4. smarter loader (`.viv` preference + reanalysis)
5. selector-based auto-open resolver
6. discovery/catalog tools
7. metadata/docs polish

---

## Acceptance criteria

1. Starting the MCP server in local mode with `--base-dir <dir>` lets the client enumerate all files below that root.
2. Starting the MCP server in server mode with explicit root opt-in exposes the host filesystem clearly and safely.
3. If `foo.bin.viv` or sibling `.viv` exists, opening `foo.bin` reuses it by default.
4. A caller can explicitly force re-analysis and preserve the old `.viv` artifact.
5. A caller can use either `workspace_id`, path, alias, or server workspace name to target a workspace.
6. A workspace-using tool can auto-open a workspace on demand and report that it did so.
7. `list_workspace_catalog` and `list_workspaces` make available/cached workspaces obvious.
8. Cache eviction is LRU and obeys configured count/byte limits.
9. Tests cover local, remote, cache-hit, cache-miss, `.viv` reuse, forced reanalysis, and eviction behavior.

---

## Risks / pitfalls

- Vivisect workspace size is hard to estimate exactly; use a best-effort estimator and document that byte limits are soft.
- Persisting newly analyzed workspaces to `.viv` may need explicit save hooks depending on Vivisect behavior.
- Auto-open must not silently escape the allowed root in local mode.
- Path-only APIs can create ambiguity when filenames repeat; alias/path resolution rules must be deterministic.
- Remote/server workspaces and local file-backed workspaces should share one selector UX, but their metadata will differ.

---

## Recommended first code slice

If we want a low-risk first merge, do this in two PRs:

**PR 1:** filesystem policy + catalog tools + richer `workspace_open/status/list` metadata

**PR 2:** selector auto-open + `.viv` preference/reanalysis + LRU eviction

That keeps the API legibility work separate from the heavier loader/cache semantics.
