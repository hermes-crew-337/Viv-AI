# Viv-AI roadmap: Phase P and beyond

This note proposes the next phases after the current Phase O baseline.

## Phase P proposal: usability and operator experience

Goal: make Viv-AI easier to configure, discover, and operate without already knowing internal details.

Suggested scope:
- add provider/model discovery helpers
  - MCP tool or local helper to list configured providers
  - Ollama model discovery via `/api/tags`
- add clearer configuration surfaces
  - one documented config file example for local-only Ollama
  - one documented config file example for HTTP transport + auth
  - validation errors that point directly to the missing field/value
- improve docs and runbooks
  - stdio vs HTTP decision guide
  - mutation policy quick reference
  - troubleshooting page for timeouts, auth failures, and missing models
- improve operator-facing health/status
  - server info should expose transport/auth posture without secrets
  - optional endpoint or tool for model/provider readiness checks
- add end-to-end smoke coverage
  - real client-shaped tests for stdio and HTTP launch flows

Acceptance ideas:
- new users can select an installed Ollama model without reading source
- a broken config produces actionable errors
- docs cover the common local setup and the common MCP client setup

## Phase Q proposal: richer auth and multi-client transport maturity

Goal: make the HTTP surface more production-ready.

Suggested scope:
- stronger HTTP auth schemes beyond static bearer token env vars
- clearer auth failure/error taxonomy
- tighter request size and transport limits
- compatibility smoke tests for more MCP client shapes
- transport configuration serialization + validation tests

## Phase R proposal: analyst workflow polish

Goal: improve the day-to-day Vivisect UI experience.

Suggested scope:
- richer Qt-native widgets and layout polish
- better history browsing and result comparison
- queue inspection/editing tools for staged proposals
- clearer provenance display for cached vs fresh AI output
- small-task progress UX for background jobs

## Phase S proposal: advanced reasoning and batch workflows

Goal: increase analysis power and throughput.

Suggested scope:
- batch function analysis workflows
- targeted rename/comment campaigns over filtered function sets
- richer graph/symbolik cross-linking in AI outputs
- optional export/report generation for review sessions
- tighter bounded-output controls for larger binaries

## Phase T proposal: ecosystem and packaging maturity

Goal: make Viv-AI easier to adopt and maintain.

Suggested scope:
- packaged examples for Hermes, Claude Desktop, and generic MCP clients
- release checklist and versioned changelog flow
- CI test matrix for unit/integration/live-optional jobs
- contributor docs for adding providers/tools/schemas safely
- long-lived compatibility guidance for Vivisect and Ollama versions

## Phase U proposal: server integration and collaborative AI

Goal: allow an AI agent (Hermes or internal Viv-AI plugin) to drive a Vivisect Server follow-the-leader session, with real-time explanation delivery to connected human analysts.

### Background

Vivisect Server supports shared workspaces where multiple users connect, results live server-side, and updates propagate in near real-time. A user can lead ("Follow Me!") and connected followers attach their memory/function views to the leader. The existing event infrastructure (`VTE_IAMLEADER`, `VTE_FOLLOWME`, `VTE_KILLLEADER`) and Qt GUI handlers already support this flow — the gap is headless leadership by an AI agent.

### Architecture

```
LLM (Hermes) ──MCP──▶ Viv-AI Server (headless)
                           │ vw.iAmLeader() / vw.followTheLeader()
                           ▼
                     Vivisect Server
                           │ VTE_FOLLOWME broadcast
                           ▼
              ┌──────────────────────┐
              │ Human's GUI (follower)│
              │ enviNavGoto(expr)     │
              │ sees explanation      │
              └──────────────────────┘
```

The MCP server connects as a headless Vivisect Server client (no Qt). It holds a `vw` reference and calls `vw.followTheLeader()` directly — no views needed. Followers who've opted in receive `VTE_FOLLOWME` and their Qt views navigate automatically via the existing handler.

### Suggested scope

**Task 1: Headless Vivisect Server client in MCP**
- Add `workspace_connect` MCP tool: connect to Vivisect Server by host:port + workspace name using cobra transport
- Add `workspace_disconnect` tool: clean disconnect, kill leader sessions
- Add `server_list_workspaces` tool: enumerate workspaces on a server
- Modify `WorkspaceSessionManager` to support remote `vw` references alongside local file loads
- Config mode flag in MCP launcher: `--mode local|remote`

**Task 2: Leader session management MCP tools**
- Add `leader_start(session_name, initial_location)` — calls `vw.iAmLeader()` with generated uuid
- Add `leader_navigate(va_expr)` — calls `vw.followTheLeader(uuid, expr)`, all followers navigate there
- Add `leader_end()` — calls `vw.killLeaderSession(uuid)`
- Add `leader_list()` — wraps `vw.getLeaderSessions()` + `vw.getLeaderLoc()`
- Add `leader_status()` — shows follower count, current location, session name

**Task 3: Real-time AI explanation delivery**
- Option A (immediate): `leader_chat(message)` sends `VWE_CHAT` — followers see it in chat window
- Option B (immediate): `leader_annotate(va, text)` sets a workspace comment at the location
- Option C (preferred): new transient event `VTE_AI_EXPLANATION` carrying structured explanation (summary, evidence, confidence). Qt GUI renders as a dock/overlay/toast — requires Vivisect core PR

**Task 4: AI explanation workflow (the tool that ties it together)**
- Add `leader_explain_function(fva)` — full flow:
  1. Run `ai_explain_function` internally
  2. Call `leader_navigate(fva)` to jump followers
  3. Deliver explanation via configured path (chat / comment / VTE_AI_EXPLANATION)
- Equivalent `leader_explain_binary()`, `leader_explain_graph()`

**Task 5: Internal (non-MCP) plugin path**
- When Viv-AI is loaded as a Vivisect GUI plugin, it can drive its own memory view as the leader by setting `_leading = True` on the plugin's dock. Every `enviNavGoto()` call broadcasts automatically.
- Add a "Start AI Leader Session" Tools menu entry that declares leadership and opens the AI panel.
- Plugin-state management: the AI dock becomes the leader view, its navigation syncs to followers.

### Acceptance criteria

- An MCP client (Hermes) can connect a headless Viv-AI to a Vivisect Server
- The headless MCP server can declare a leader session that human users see and can follow
- When the AI navigates via MCP, all connected followers' GUI views jump to that address
- The AI's explanation appears in followers' GUIs in real-time (chat, comment, or dedicated widget)
- The plugin-based internal path also works: "Start AI Leader Session" in the Tools menu, then AI analysis actions broadcast to followers
- Full test coverage for leader session lifecycle and event propagation

### Notes

- The headless client uses the same cobra transport that Vivisect's existing remote client infrastructure uses — no new protocol work needed.
- Event dispatch (VTE_FOLLOWME → Qt GUI navigation) already works end-to-end. The only new server-side code is the MCP tool layer that calls existing `vw` methods.
- Option C (VTE_AI_EXPLANATION) should be designed collaboratively with the Vivisect core repo since it touches the event registry and Qt renderers.
- Leader session uuids should be generated and managed internally by Viv-AI's session manager, not exposed as a complexity to the LLM caller.
- For the Hermes → MCP → Server path, the user asks something like "start an AI analysis session on the foo-bar workspace, explain what's at 0x401000" and the system handles routing.

## Related docs

For the full Phase P implementation plan, see:
- `docs/plans/2026-05-22-phase-p-usability-installation.md`

For standard analysis workflows being targeted, see:
- `docs/analysis-workflows.md`

For VivCLI command surface planning, see:
- `docs/vivcli-command-surface.md`

For provider configuration examples, see:
- `docs/provider-configuration.md`
