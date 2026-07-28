# Phase U: Collaborative Sessions + Documentation

> **Status:** Active
> **Branch:** `feat/phase-q-http-maturity`
> **Tests:** 336 baseline → target ~380+

**Goal:** Complete the collaborative reverse-engineering workflow by adding `leader_annotate`, `leader_status`, explain variants, plugin-side leader integration, and ship the missing README/INSTALL documentation.

**Prerequisite context:** Tasks 1–4 from the [Phase U roadmap](../roadmap-phases-p-plus.md#phase-u-proposal-server-integration-and-collaborative-ai) were front-loaded during Phase Q/S development and are already delivered:
- ✅ `server_connect`, `server_disconnect`, `server_list_workspaces`
- ✅ `leader_start`, `leader_navigate`, `leader_end`, `leader_list`, `leader_get_location`
- ✅ `leader_chat` (Option A delivery path)
- ✅ `leader_explain_and_navigate`

What remains is the unblocked roadmap scope plus new doc files.

---

### Task 1: Add `leader_annotate` MCP tool

**Objective:** Set a workspace comment at a specific VA — Option B delivery path from the roadmap. Followers see AI-generated annotations directly in their disassembly view as comments.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py` — add handler + metadata
- Test: `tests/test_server_connection.py` — add tests
- Verify: `pytest tests/test_server_connection.py::LeaderToolTests -v`

**Step 1: Write tests**

Add to `LeaderToolTests` in `test_server_connection.py`:

```python
def test_leader_annotate_sets_comment(self):
    self.server.call_tool('leader_start', workspace_id=self.wid)
    from viv_ai.mcp.tools import ANNOTATION_PREFIX

    result = self.server.call_tool(
        'leader_annotate', workspace_id=self.wid,
        va='0x401000', text='Suspicious loop bound check',
    )

    self.assertTrue(result['ok'])
    self.assertEqual(result['data']['va'], '0x401000')
    self.assertTrue(result['data']['annotated'])

def test_leader_annotate_without_leader_returns_error(self):
    result = self.server.call_tool(
        'leader_annotate', workspace_id=self.wid,
        va='0x401000', text='test',
    )
    self.assertFalse(result['ok'])
    self.assertIn('no active leader', result['error'])

def test_leader_annotate_on_local_workspace_fails(self):
    open_result = self.server.call_tool(
        'workspace_open', path='/tmp/fake.bin',
    )
    wid = open_result['data']['workspace_id']
    result = self.server.call_tool(
        'leader_annotate', workspace_id=wid,
        va='0x401000', text='test',
    )
    self.assertFalse(result['ok'])
    self.assertIn('not connected', result['error'])
```

**Step 2: Run tests to verify failure**

```bash
pytest tests/test_server_connection.py::LeaderToolTests::test_leader_annotate -v
```
Expected: FAIL — "unknown tool"

**Step 3: Add tool handler to `tools.py`**

Add to `tools.py` after the `leader_chat` function:

```python
ANNOTATION_PREFIX = '[Viv-AI] '

def leader_annotate(manager: WorkspaceSessionManager, workspace_id: str, va: Any, text: str, **kwargs) -> Dict[str, Any]:
    """Set a workspace comment at a VA for followers to see."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(
            workspace_id, 'address',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_annotate'},
        ).to_dict()

    fva_int = parse_va(va)
    full_text = f'{ANNOTATION_PREFIX}{text}'
    vw.setComment(fva_int, full_text)

    return ToolResponse.ok(
        workspace_id, 'address',
        data={'va': f'0x{fva_int:08x}', 'annotated': True, 'comment': full_text},
        provenance={'tool': 'leader_annotate'},
        summary=f'annotated 0x{fva_int:08x} with comment',
    ).to_dict()
```

Add metadata to `build_tool_metadata()`:

```python
'leader_annotate': {
    'description': 'Set a workspace comment at a VA as the AI leader. Followers see annotations directly in their disassembly.',
    'inputSchema': _schema({
        'workspace_id': workspace_id,
        'va': hex_addr,
        'text': {'type': 'string', 'description': 'Annotation text to set as a comment on this address.'},
    }, ['workspace_id', 'va', 'text']),
    'annotations': {'readOnlyHint': False},
},
```

Add to `build_default_registry()`:

```python
'leader_annotate': leader_annotate,
```

Add to `validate_server_mode` test loop in `test_server_connection.py:test_leader_tools_fail_on_local_workspace`.

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_server_connection.py -v
```
Expected: all LeaderToolTests pass (existing + new)

---

### Task 2: Add `leader_status` MCP tool

**Objective:** Return aggregate status of the AI leader session — follower count, current location, session name, chat activity. Makes the session observable for the MCP client.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py` — add handler + metadata
- Test: `tests/test_server_connection.py` — add tests

**Step 1: Write tests**

```python
def test_leader_status_returns_session_state(self):
    self.server.call_tool('leader_start', workspace_id=self.wid,
                          session_name='My Session', initial_location='0x401000')

    result = self.server.call_tool('leader_status', workspace_id=self.wid)

    self.assertTrue(result['ok'])
    data = result['data']
    self.assertIn('leader_uuid', data)
    self.assertEqual(data['session_name'], 'My Session')
    self.assertEqual(data['current_location'], '0x401000')
    self.assertIn('leader_sessions', data)

def test_leader_status_without_leader_returns_error(self):
    result = self.server.call_tool('leader_status', workspace_id=self.wid)
    self.assertFalse(result['ok'])
    self.assertIn('no active leader', result['error'])
```

**Step 2: Run tests to verify failure**

```bash
pytest tests/test_server_connection.py::LeaderToolTests::test_leader_status -v
```

**Step 3: Add handler + metadata + registry entry**

```python
def leader_status(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """Return aggregate status of the leader session."""
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

    loc = vw.getLeaderLoc(leader_uuid) if hasattr(vw, 'getLeaderLoc') else None
    info = vw.getLeaderInfo(leader_uuid) if hasattr(vw, 'getLeaderInfo') else (None, None)
    user, fname = info if info else (None, None)
    all_sessions = vw.getLeaderSessions() if hasattr(vw, 'getLeaderSessions') else {}
    chat_count = len(getattr(vw, '_chats', []))

    return ToolResponse.ok(
        workspace_id, 'server',
        data={
            'leader_uuid': leader_uuid,
            'user': user,
            'session_name': fname,
            'current_location': loc,
            'leader_sessions': [
                {'uuid': u, 'user': s[0], 'session_name': s[1],
                 'current_location': vw.getLeaderLoc(u) if hasattr(vw, 'getLeaderLoc') else None}
                for u, s in all_sessions.items()
            ],
            'chat_count': chat_count,
        },
        provenance={'tool': 'leader_status'},
        summary=f'leader \"{fname}\" at {loc} with {len(all_sessions)} session(s)',
    ).to_dict()
```

Metadata:

```python
'leader_status': {
    'description': 'Return aggregate status of the AI leader session: session name, current location, all leader sessions on the workspace, and chat activity.',
    'inputSchema': _schema({'workspace_id': workspace_id}, ['workspace_id']),
    'annotations': {'readOnlyHint': True},
},
```

**Step 4: Run tests**

```bash
pytest tests/test_server_connection.py -v
```

---

### Task 3: Add `leader_explain_binary` and `leader_explain_graph` variants

**Objective:** Complete the explain-variant family from roadmap Task 4. These composite tools run AI analysis + navigate followers + deliver via chat, analogous to the existing `leader_explain_and_navigate` but for binary-level and graph-level analysis.

**Files:**
- Modify: `src/viv_ai/mcp/tools.py` — add handlers + metadata
- Test: `tests/test_server_connection.py` — add tests

**Step 1: Write tests**

```python
def test_leader_explain_binary_fallback_no_ai(self):
    self.server.call_tool('leader_start', workspace_id=self.wid)
    self.server.session_manager.analysis_service = None

    result = self.server.call_tool(
        'leader_explain_binary', workspace_id=self.wid,
    )

    self.assertTrue(result['ok'])
    self.assertFalse(result['data']['ai_analysis_completed'])

def test_leader_explain_graph_fallback_no_ai(self):
    self.server.call_tool('leader_start', workspace_id=self.wid)
    self.server.session_manager.analysis_service = None

    result = self.server.call_tool(
        'leader_explain_graph', workspace_id=self.wid,
        fva='0x401000',
    )

    self.assertTrue(result['ok'])
    self.assertFalse(result['data']['ai_analysis_completed'])
```

**Step 2: Run to verify failure**

**Step 3: Add handlers**

```python
def leader_explain_binary(manager: WorkspaceSessionManager, workspace_id: str, **kwargs) -> Dict[str, Any]:
    """Composite: AI-summarize the binary, navigate to entry point, deliver summary via chat."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(workspace_id, 'server',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_explain_binary'}).to_dict()

    # Navigate to entry point
    entry_points = vw.getEntryPoints()
    target = f'0x{entry_points[0]:x}' if entry_points else '0x0'
    vw.followTheLeader(leader_uuid, target)

    # AI analysis
    ai_result = None
    err = _check_provider_available(manager)
    if not err:
        try:
            ai_result = _analysis_service(manager).analyze_binary(vw, options=_options_from_kwargs(kwargs))
        except Exception:
            pass

    if ai_result:
        summary_text = ai_result.get('analysis', {}).get('summary', '')
        if summary_text:
            vw.chat(f'[AI binary] {summary_text}')

    return ToolResponse.ok(workspace_id, 'binary', data={
        'navigated_to': target,
        'ai_analysis_completed': ai_result is not None,
        'analysis': ai_result.get('analysis') if ai_result else None,
    }, provenance={'tool': 'leader_explain_binary', 'ai_analysis': ai_result is not None},
    summary=f'navigated to entry {target}' + (', AI binary summary delivered' if ai_result else '')).to_dict()


def leader_explain_graph(manager: WorkspaceSessionManager, workspace_id: str, fva: Any, **kwargs) -> Dict[str, Any]:
    """Composite: AI-analyze a function's graph, navigate followers, deliver via chat."""
    session = manager.get_session(workspace_id)
    vw = session.workspace
    _validate_server_mode(vw)

    leader_uuid = session.metadata.get('leader_uuid')
    if not leader_uuid:
        return ToolResponse.error_response(workspace_id, 'function',
            'no active leader session — call leader_start first',
            provenance={'tool': 'leader_explain_graph'}).to_dict()

    fva_hex = f'0x{parse_va(fva):x}'
    vw.followTheLeader(leader_uuid, fva_hex)

    ai_result = None
    err = _check_provider_available(manager)
    if not err:
        try:
            ai_result = _analysis_service(manager).analyze_graph(
                vw.getFunctionGraph(parse_va(fva)),
                options=_options_from_kwargs(kwargs),
            )
        except Exception:
            pass

    if ai_result:
        summary_text = ai_result.get('analysis', {}).get('summary', '')
        if summary_text:
            vw.chat(f'[AI graph] {summary_text}')

    return ToolResponse.ok(workspace_id, 'function', data={
        'navigated_to': fva_hex,
        'ai_analysis_completed': ai_result is not None,
        'analysis': ai_result.get('analysis') if ai_result else None,
    }, provenance={'tool': 'leader_explain_graph', 'ai_analysis': ai_result is not None},
    summary=f'navigated to {fva_hex}' + (', graph analysis delivered' if ai_result else '')).to_dict()
```

Add metadata entries and registry entries for both.

**Step 4: Run tests**

```bash
pytest tests/test_server_connection.py -v
```

---

### Task 4: `--mode` CLI flag for MCP launcher

**Objective:** Add `--mode {local,remote,hybrid}` to `viv-ai-mcp` entrypoint that controls whether workspace loading defaults to local file paths or Vivisect Server connections.

**Files:**
- Modify: `src/viv_ai/mcp/entrypoint.py` — add flag + mode routing
- Test: `tests/test_mcp_entrypoint.py` — add tests

**Step 1: Write tests**

```python
def test_mode_local_default(self):
    """Default mode is 'local', no behavioral change."""
    ...

def test_mode_remote_requires_server_config(self):
    """--mode remote without server config produces actionable error."""
    ...
```

**Step 2: Add `--mode` to `build_arg_parser()`**

```python
parser.add_argument('--mode', choices=['local', 'remote', 'hybrid'],
                    default='local',
                    help='Workspace loading mode (default: local)')
```

Store mode on the server for tool-level access (add `self.mode` to `VivAIMcpServer` and propagate from entrypoint).

**Step 3: Run tests**

---

### Task 5: Plugin-side AI leader session (Task 5 from roadmap)

**Objective:** Add "Start AI Leader Session" Tools menu entry that declares the AI dock as leader and syncs all `enviNavGoto()` calls to followers automatically.

**Files:**
- Modify: `src/viv_ai/ui/widgets.py` — add `start_leader_session()` and `stop_leader_session()` methods
- Modify: `src/viv_ai/__init__.py` — register new menu entries
- Test: `tests/test_ui_plugin.py` — add tests

**Step 1 (Deferred — Qt-dependent, manual testing):**
- Add `_leading = False` flag to `AIHelperPanel`
- Add `start_leader_session()` that calls `vw.iAmLeader(uuid, 'Viv-AI AI Helper')` and sets nav hook
- Add "Start AI Leader Session" / "Stop AI Leader Session" menu entries to `install_gui()`
- The nav hook intercepts `enviNavGoto` and calls `vw.followTheLeader(uuid, expr)` when `_leading` is True

---

### Task 6: Update README.md

**Objective:** Bump project status through Phase S/U and add documentation for all server/leader/campaign/batch tools. Add testing badges.

**Files:**
- Modify: `README.md`

Changes needed:
- Status line: "through Phase P" → "through Phase U"
- Add to "Implemented today" list: server connection, follow-the-leader, campaign operations, batch analysis, export report, vuln triage, leader annotate/status
- Add "Collaborative Analysis" section with server/leader tool examples
- Add testing badge section (336 pass, 2 skip)
- Add MCP HTTP transport usage notes

---

### Task 7: Create INSTALL.md

**Objective:** Standalone install guide separate from README — covers pip, uv, config, MCP client setup, troubleshooting.

**Files:**
- Create: `INSTALL.md`

Sections:
- Prerequisites (Python 3.10+, Vivisect, Ollama optional)
- Install via pip / uv
- Config file setup with examples
- GUI plugin setup (VIV_EXT_PATH)
- MCP server setup (stdio + Hermes/Claude Desktop config)
- HTTP transport setup
- Testing the installation
- Troubleshooting (timeouts, auth, missing model)
