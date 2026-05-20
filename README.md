# Viv-AI

AI integration plugin for Vivisect, including in-Viv helpers and an MCP-oriented core.

## Phase A status

This repository currently contains the standalone Phase A package skeleton.

Implemented in Phase A:
- standalone Python package namespace: `viv_ai`
- Vivisect plugin entrypoint exposed via `vivExtension(vw, vwgui)`
- provider-agnostic config and mutation-policy models
- provider adapter scaffolding for Ollama, OpenAI-compatible APIs, Anthropic, and Gemini
- optional live Ollama smoke test support

Implemented through Phase O:
- bounded binary/function extraction helpers
- control-flow graph summarization helpers
- symbolik path summarization helpers
- prompt/schema bundles for structured analysis tasks
- analysis service orchestration with cache + redaction
- safe write-back helpers for rename/comment suggestions with policy enforcement
- plugin/dock/context-menu/hotkey GUI integration scaffold
- workflow-oriented panel state with scope switching and analysis history
- review queue support for multi-item staged suggestions
- settings update controller for UI-driven config changes
- background job runner for non-blocking analysis execution
- rendered result views for structured summaries, evidence, cache status, and errors
- async workflow support for graph/function/binary analysis scheduling
- MCP foundation modules for request/response schemas and workspace session management
- minimal MCP server shell with tool registry and workspace lifecycle tools
- initial read-only MCP metadata/binary-summary tool surface on the shared core
- bounded read-only MCP inspection tools for strings, imports, exports, names, and xrefs
- MCP function-summary tool reusing the shared bounded extractor payloads
- MCP function-graph tool reusing the shared bounded graph serializer
- MCP symbolik-summary tool reusing the shared bounded path summarizer
- AI-backed MCP function explanation tool reusing the shared AnalysisService
- AI-backed MCP binary summarization tool reusing the shared AnalysisService
- MCP mutation proposal tools for function renames and comments
- explicit opt-in MCP apply tools with read-only/review policy enforcement and structured audit-friendly results
- MCP tool-call concurrency and timeout caps with structured errors
- local-only provider policy enforcement for AI-backed analysis paths
- packaged stdio MCP entrypoint module and `viv-ai-mcp` launcher script
- per-tool MCP input schemas and read-only/mutating annotations for client discovery
- structured JSON-RPC parse/invalid-params error handling for stdio MCP requests
- optional HTTP MCP transport with bearer-token auth via env-var reference
- packaged `viv-ai-mcp-http` launcher for HTTP deployment smoke tests
- initial MCP client usage/examples documentation
- context-menu entry generation for function explanation
- staged review/apply flow helpers and settings persistence controller

Still not yet implemented:
- richer HTTP auth schemes beyond the current bearer-token env-var gate
- richer Qt-native widgets beyond the current workflow scaffold
- remote-provider auth/runtime integrations beyond request-shape scaffolding

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install vivisect pytest
pip install -e .
```

## Testing

Run unit and packaging tests:

```bash
pytest
```

Run an integration-style loader test with installed Vivisect:

```bash
pytest tests/test_viv_loader_integration.py
```

Optional live Ollama smoke test:

```bash
export VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1
export VIV_AI_OLLAMA_ENDPOINT=http://MATRIX:11434
pytest tests/test_ollama_live.py
```

## Using with Vivisect

Point `VIV_EXT_PATH` at the directory containing the installed `viv_ai` package, or at the repo `src/` directory during editable development:

```bash
export VIV_EXT_PATH=/path/to/Viv-AI/src
```

## MCP docs

- docs/mcp-client-usage.md
