# Viv-AI Collaborative Sessions Guide (Leader Sessions)

This guide documents the "follow-the-leader" collaborative analysis workflow in Viv-AI, where one agent or client drives deep analysis and other clients observe, annotate, and query the leader's progress.

---

## What is a Leader Session?

A **leader session** establishes an authoritative AI-analyst connection that runs on top of an active Vivisect workspace. The leader:

- Opens/analyzes workspaces independently
- Traverses functions, proposes renames, summarizes binaries and graphs
- Coordinates the analysis state so multiple followers can observe or interact

Think of it as a **remote control + observer** pattern:
- The **leader** is in control — it navigates, analyzes, and writes changes back in stages
- **Followers** connect to see what the leader sees (function-by-function explanations) and can query status/annotations without disrupting the leader's work

---

## Architecture Overview

```
[Vivisect Core] <— vw.iAmLeader() / vw.killLeaderSession() / vw.getLeaderSessions() 
       ↑ leader lifecycle hooks
[Viv-AI Plugin Panel] — Qt GUI widgets register Tools menu entries
[MCP Tools server]   — leader_start/leader_stop/leader_status/leader_annotate via stdio+MCP
[GUI Panel Methods]  — start_leader_session()/stop_leader_session()/leader_session_status()
```

Key Vivisect API:
- `vw.iAmLeader(uuid, session_name, initial_location=None)`
- `vw.killLeaderSession(session_uuid)`
- `vw.getLeaderSessions()` → `{uuid: (session_name, current_address)}`

Viv-AI wraps these in both the QML panel and MCP server.

---

## Establishing a Leader Session — GUI Mode

### Prerequisites

Before using leader sessions you must have Vivisect running with a workspace loaded:

1. Open your target binary: `File -> Open` (or drag onto the window)
2. Wait for the disassembly listing to appear

### Creating a Leader Session

1. Navigate to any function address in the listing (e.g., click on it so it appears as "current")
2. Click the menu: `Tools -> AI Helper -> Start Leader Session`
3. Viv-AI will:
   - Generate a UUID for this session
   - Call `vw.iAmLeader()` with your chosen session name (`"Viv-AI"` by default)
   - Print startup diagnostics to the terminal

**Startup diagnostics** (printed on launch):

```
[Viv-AI MCP] Mode: hybrid
  Local files: allowed
  Server:      allowed
  AI provider: ollama/qwen2.5:72b-instruct
  Mutation policy: review_before_apply
```

### Managing the Leader Session via GUI

Once running, you can control it from `Tools -> AI Helper`:

| Menu Action | MCP Tool Equivalent | When to Use |
|-------------|--------------------|-------------|
| `Stop Leader Session` | `leader_stop` | End your session and let others take over |
| `Leader Session Status` | `leader_status` | Check which sessions are active right now |
| `Show Panel` | — | Bring up the full analysis panel, including leader mode controls |

### What Followes Sees on Join

When a follower connects to an active session:

- They can see the **current address/program location** the leader is focused on
- They receive live annotations via the MCP `leader_annotate` tool (or manually from GUI)
- The panel shows session metadata: name, current function, start time, status ("active" / "paused")
- Followers are **not** blocked from navigating their own workspace, but they cannot propose renames while someone else is the leader

---

## Establishing a Leader Session — MCP Mode

### Step 1: Start the Viv-AI MCP server

```bash
viv-ai-mcp --config ~/.config/viv-ai/config.json --mode hybrid
```

### Step 2: Discover available tools (if your client supports tool discovery)

Your MCP client should enumerate `leader_start`, `leader_stop`, `leader_status`, and `leader_annotate` as available tools. If not, they are always callable by name regardless of whether the transport returns them in a tool-list response.

### Step 3: Start the session

```json
{
  "method": "tools/call",
  "params": {
    "name": "leader_start",
    "arguments": {
      "workspace": "/path/to/binary.vw",
      "session_name": "Viv-AI-analyst-01",
      "initial_location": null   // starts at the first function; or pass "0x401000"
    }
  }
}
```

Response will include the session UUID:

```json
{
  "result": {
    "session_uuid": "a1b2c3d4-5678-90ef-abcd-ef123456",
    "session_name": "Viv-AI-analyst-01",
    "workspace": "/path/to/binary.vw",
    "status": "active",
    "message": "Leader session established at address 0x00000000 (first function)"
  }
}
```

### Step 4: Coordinate with followers

The leader can now use these tools throughout the analysis:

| MCP Tool | Purpose | Example Use Case |
|----------|---------|------------------|
| `leader_status` | Check who has the session, where they are right now | "What's the leader doing on 0x401050?" |
| `leader_annotate(address, note)` | Push a human-readable annotation to the workspace for followers to see | Leave notes about suspected vulnerability locations |
| `ai_explain_function(workspace, function_address)` | Get an AI explanation of any address (leader only) | Deep-dive analysis on current target |
| `workspace_catalog_status` | Verify which workspaces are still tracked | See if your workspace is cached |

### Step 5: Stop the session when done

```json
{
  "method": "tools/call",
  "params": {
    "name": "leader_stop",
    "arguments": {
      "session_uuid": "a1b2c3d4-5678-90ef-abcd-ef123456"
    }
  }
}
```

---

## Multi-Agent Collaboration Pattern with Followes

### Use Case: Deep-dive analysis on a suspected malware binary

**Leader's workflow:**

1. Leader opens the workspace via `workspace_open`
2. Leader starts session and navigates function-by-function using `ai_explain_function`
3. Leader proposes renames in stages, which appear in the reviewer queue
4. Leader annotates interesting addresses with `leader_annotate(0x4015A6, "Suspected CVE-XXXX-XXXXXXXX — string extraction from XOR-encoded buffer")`

**Followers' workflow:**

1. A follower opens the same workspace independently (or connects via MCP)
2. They can see leader annotations appear in real time
3. They query `leader_status` to know where the leader is focused right now
4. They read explanations for specific functions using `ai_explain_function` on their own, without needing to ask an LLM directly

### When You Shouldn't Use This Pattern

- **Single-machine single-analyst**: No need for the coordination overhead — just use the GUI panel or direct MCP calls
- **Unshared workspace files**: If followers can't access `.vw` files because of permission boundaries, leader sessions won't sync properly
- **Read-only analysis on remote binaries** where `local_only: true` would block the leader's file access

---

## Troubleshooting Leader Sessions

### "Session is already active" error

Another session may be running. Check active sessions:

```bash
# Via MCP
leader_status  → returns {sessions: [...]} or {} if none are running

# In GUI
Tools -> AI Helper -> Leader Session Status
```

If stale (the process died but Vivisect doesn't know):

1. Ask the other user to call `leader_stop` on their end
2. Or restart Vivisect entirely — killed-session UUIDs will clear on next launch and are never reused within a single session

### "I joined, but I don't see annotations"

- Your workspace must be opened **before** the leader starts (or at least before annotation is pushed)
- If both clients use the same `workspace` path but different Vivisect instances, you may need to call `workspace_discover` or `discover_files` to refresh the shared state.

### Mode flags blocking leader session

The leader only works if `--mode local|hybrid` (local access required). If launched in `remote` mode:
- AI tools still run (they call remote providers)
- But file/workspace discovery, renames, and annotations will fail silently or throw `LocalWorkspaceAccessRequired` errors
- **Fix:** Re-launch with `--mode local` or `--mode hybrid`

### Leader session persists across process exits

Not possible — the leader state lives in Vivisect's Python object tree. A killed process clears all sessions automatically. No manual cleanup needed.

---

## Quick Reference Card

| Action | GUI Menu | MCP Tool | Notes |
|--------|----------|----------|-------|
| Start session | `Tools -> AI Helper -> Start Leader Session` | `leader_start(workspace, session_name)` | Requires workspace open in Vivisect |
| Check who is leader | `Tools -> AI Helper -> Leader Session Status` | `leader_status()` | Returns active sessions list |
| Leave a note for followers | *(panel annotation field)* | `leader_annotate(0xaddress, "note text")` | Visible to all connecting clients |
| Stop session | `Tools -> AI Helper -> Stop Leader Session` | `leader_stop(session_uuid)` | Releases the leader control |

---

*This file is PR-ready. It serves as `docs/leader-session-guide.md` and fills gap #B from the UX review ("Clarify leader sessions").*
