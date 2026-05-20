# Viv-AI MCP client usage

This document shows minimal client-side setup patterns and example tool calls for the current Viv-AI MCP server.

## Server posture

Current operational defaults:
- read-only mutation posture unless `direct_apply_enabled` is explicitly configured
- tool-call concurrency cap
- per-tool timeout cap
- local-only provider policy by default for AI-backed tools

## Hermes Agent client example

Current status: this repo exposes the in-process `VivAIMcpServer` class and tool registry, but it does not yet ship a packaged stdio MCP entrypoint module. For Hermes, Claude Desktop, or another MCP client, wrap the server with your own launcher until a transport entrypoint lands.

Example prompts once connected:
- open `/tmp/a.out` in the Viv-AI MCP server and summarize the binary
- explain function `0x401000`
- show the bounded graph for function `0x401000`
- propose a rename for function `0x401000` to `decrypt_payload`

## Claude Desktop / generic stdio MCP shape

When you add your own stdio transport wrapper, point your MCP client config at that wrapper command. The exact JSON/YAML shape depends on the client, but the workflow below stays the same once the server is reachable.

## OpenAI-compatible client shape

For OpenAI-compatible agent stacks that can call MCP tools, expose the same wrapped server over the transport shape they expect, then use the tool workflows below.

## Example workflow

1. `workspace_open` with a file path
2. `get_metadata` to confirm architecture/platform/format
3. `get_function_summary` or `ai_explain_function` for a target function
4. `get_function_graph` for bounded CFG inspection
5. `propose_function_rename` or `propose_comment` for non-mutating reviewable suggestions
6. `apply_function_rename` or `apply_comment` only when the server is explicitly configured for `direct_apply_enabled`

## Example tool calls

Open a workspace:

```json
{"tool":"workspace_open","arguments":{"path":"/tmp/a.out"}}
```

Explain a function with AI:

```json
{"tool":"ai_explain_function","arguments":{"workspace_id":"<workspace-id>","fva":"0x401000","temperature":0.1}}
```

Inspect a bounded graph:

```json
{"tool":"get_function_graph","arguments":{"workspace_id":"<workspace-id>","fva":"0x401000","max_nodes":32,"max_edges":48}}
```

Propose a rename:

```json
{"tool":"propose_function_rename","arguments":{"workspace_id":"<workspace-id>","fva":"0x401000","new_name":"decrypt_payload"}}
```

Apply a rename when direct apply is enabled server-side:

```json
{"tool":"apply_function_rename","arguments":{"workspace_id":"<workspace-id>","fva":"0x401000","new_name":"decrypt_payload"}}
```

## Notes

- Tool outputs are intentionally bounded for LLM-friendly MCP use.
- AI-backed tools depend on a server-side `AnalysisService`; clients never pass provider objects directly.
- Remote-capable providers are blocked when local-only policy is enabled.
- If a tool exceeds the configured time budget or concurrency cap, the server returns a structured error.
