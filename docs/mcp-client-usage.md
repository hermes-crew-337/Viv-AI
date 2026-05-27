# Viv-AI MCP client usage

This document shows minimal client-side setup patterns and example tool calls for the current Viv-AI MCP server.

Before launching the server, remember the config lookup order:
- explicit CLI flag: `--config /path/to/config.json`
- env override: `VIV_AI_CONFIG=/path/to/config.json`
- default file: `~/.config/viv-ai/config.json`
- otherwise: default in-memory config

Provider config examples for Ollama, OpenAI-compatible APIs, Anthropic, Gemini, and OpenRouter-style use live in `docs/provider-configuration.md`.

## Server posture

Current operational defaults:
- read-only mutation posture unless `direct_apply_enabled` is explicitly configured
- tool-call concurrency cap
- per-tool timeout cap
- local-only provider policy by default for AI-backed tools
- tool discovery includes per-tool input schemas and read-only hints for MCP clients
- optional HTTP transport uses bearer auth via an env-var reference, not an in-config raw secret

## Ollama model selection

For the Ollama-backed analysis provider, the configured model name is passed through exactly as configured. You should still choose from what the Ollama server already has installed, but Viv-AI now exposes a `list_provider_models` MCP tool that reports the configured model, discovered available models, and actionable config issues.

Examples of valid installed names seen during local validation include:
- `qwen2.5:72b-instruct`
- `qwen2.5-coder:32b-instruct`
- `cas/llama-3.2-3b-instruct:latest`
- `gemma4:31b`

To discover what your Ollama server currently exposes:

```bash
curl http://MATRIX:11434/api/tags
# or:
ollama list
```

For the live smoke test in this repo, set the exact model name with `VIV_AI_OLLAMA_MODEL`.

## Hermes Agent client example

Launch the packaged stdio entrypoint:

```yaml
mcp_servers:
  viv_ai:
    command: "viv-ai-mcp"
    args: []
    timeout: 60
    connect_timeout: 30
```

You can also run it directly without the installed console script:

```yaml
mcp_servers:
  viv_ai:
    command: "python"
    args: ["-m", "viv_ai.mcp.entrypoint"]
    timeout: 60
    connect_timeout: 30
```

Example prompts once connected:
- open `/tmp/a.out` in the Viv-AI MCP server and summarize the binary
- explain function `0x401000`
- show the bounded graph for function `0x401000`
- propose a rename for function `0x401000` to `decrypt_payload`

## HTTP transport example

Optional HTTP transport is also available:

```bash
# Using bearer token authentication
export VIV_AI_MCP_TOKEN=replace-me
viv-ai-mcp-http --host 127.0.0.1 --port 8765 --auth-token-env VIV_AI_MCP_TOKEN

# Using API key authentication
export VIV_AI_MCP_API_KEY=replace-me
viv-ai-mcp-http --host 127.0.0.1 --port 8765 --api-key-env VIV_AI_MCP_API_KEY

# With request size limit (default is 1MB)
viv-ai-mcp-http --host 127.0.0.1 --port 8765 --max-request-size 2048
```

Then POST JSON-RPC requests to `http://127.0.0.1:8765/mcp` with either:

Bearer token authentication:
```http
Authorization: Bearer replace-me
Content-Type: application/json
```

API key authentication (two options):
```http
# Option 1: X-API-Key header
X-API-Key: replace-me
Content-Type: application/json

# Option 2: Authorization header with Bearer prefix
Authorization: Bearer replace-me
Content-Type: application/json
```

`GET /healthz` returns a lightweight health/transport summary without exposing the token or API key value.

## Claude Desktop / generic stdio MCP shape

Point the client at the installed launcher or Python module:

```json
{
  "mcpServers": {
    "viv-ai": {
      "command": "viv-ai-mcp",
      "args": []
    }
  }
}
```

Equivalent direct-module form:

```json
{
  "mcpServers": {
    "viv-ai": {
      "command": "python",
      "args": ["-m", "viv_ai.mcp.entrypoint"]
    }
  }
}
```

## OpenAI-compatible client shape

For OpenAI-compatible agent stacks that can call MCP tools, expose the same stdio entrypoint over the transport shape they expect, for example:

```json
{
  "type": "stdio",
  "command": "viv-ai-mcp",
  "args": []
}
```

Then use the tool workflows below.

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

List configured/discovered provider models:

```json
{"tool":"list_provider_models","arguments":{"provider_name":"ollama"}}
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
- `tools/list` now exposes per-tool input schemas and read-only annotations for better client UX.
- Invalid JSON and malformed `tools/call` argument shapes return structured JSON-RPC errors instead of crashing the server.
- AI-backed tools depend on a server-side `AnalysisService`; clients never pass provider objects directly.
- Remote-capable providers are blocked when local-only policy is enabled.
- If a tool exceeds the configured time budget or concurrency cap, the server returns a structured error.
