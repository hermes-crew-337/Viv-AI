# Viv-AI

AI integration plugin for Vivisect, with two operator surfaces:
- in-Vivisect GUI assistance for reverse-engineering workflows
- MCP server launchers for tools like Hermes, mcp-cli, and Claude Desktop

## Project status

This repository contains a standalone `viv_ai` package with GUI and MCP surfaces implemented through Phase P.

Implemented today:
- standalone Python package namespace: `viv_ai`
- Vivisect plugin entrypoint exposed via `vivExtension(vw, vwgui)`
- provider-agnostic config and mutation-policy models
- provider adapters for Ollama, OpenAI-compatible APIs, Anthropic, and Gemini
- bounded binary/function extraction helpers
- control-flow graph summarization helpers
- symbolik path summarization helpers
- analysis service orchestration with cache + redaction
- safe write-back helpers for rename/comment suggestions with policy enforcement
- plugin/dock/menu/context-menu GUI integration scaffold
- workflow-oriented panel state with scope switching and analysis history
- review queue support for staged rename/comment suggestions
- packaged stdio MCP entrypoint and optional HTTP MCP transport
- provider/model discovery support including live Ollama model enumeration and actionable config validation hints
- leader coordination tools (leader session lifecycle, annotation, status) for collaborative server workflows
- `--mode` CLI flag (`local` / `remote` / `hybrid`) for workspace access scoping

Still intentionally incomplete:
- richer HTTP auth schemes beyond the current bearer-token env-var gate
- richer Qt-native widgets beyond the current workflow scaffold
- remote-provider auth/runtime integrations beyond request-shape scaffolding
- advanced vuln triage / exploit-assistance workflows
- any decompiler implementation

## Quick start

### 1) Install Viv-AI

Preferred setup on hosts that already have `uv`:

```bash
uv venv --clear .venv
. .venv/bin/activate
uv pip install pytest vivisect
uv pip install -e .
```

Classic `venv` + `pip` also works:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install vivisect pytest
pip install -e .
```

### 2) Create a config file

Viv-AI now looks for config in this order:
- explicit `--config /path/to/config.json`
- `VIV_AI_CONFIG=/path/to/config.json`
- default file: `~/.config/viv-ai/config.json`
- otherwise: a default in-memory config is used

Minimal local Ollama example:

```json
{
  "default_provider": "ollama",
  "default_model": "qwen2.5:72b-instruct",
  "local_only": true,
  "remote_providers_enabled": false,
  "mutation_policy": "review_before_apply",
  "providers": {
    "ollama": {
      "provider_type": "ollama",
      "endpoint": "http://127.0.0.1:11434",
      "model": "qwen2.5:72b-instruct"
    }
  }
}
```

Install that at the default path:

```bash
mkdir -p ~/.config/viv-ai
$EDITOR ~/.config/viv-ai/config.json
```

Or point Viv-AI somewhere else:

```bash
export VIV_AI_CONFIG=/path/to/viv-ai-config.json
```

For more examples, including Claude/OpenAI/OpenRouter/Gemini-style setups, see:
- `docs/provider-configuration.md`

### 3) Pick your mode

Mode A: use AI inside the Vivisect GUI
- best when you want function-by-function help while navigating the workspace
- gives you menus, context-menu actions, provider status, and staged review/apply flow

Mode B: use Viv-AI as an MCP server
- best when you want Hermes, mcp-cli, Claude Desktop, or another MCP client to drive Vivisect analysis externally
- exposes bounded inspection and AI-backed analysis tools over stdio or HTTP

## Using Viv-AI inside Vivisect

Point `VIV_EXT_PATH` at the directory containing the installed `viv_ai` package, or at the repo `src/` directory during editable development:

```bash
export VIV_EXT_PATH=/path/to/Viv-AI/src
```

Then launch Vivisect normally.

When the plugin loads with GUI support, Viv-AI currently registers:

### Tools menu entries

- `Tools -> AI Helper -> Show Panel`
- `Tools -> AI Helper -> Explain Current Function`
- `Tools -> AI Helper -> Analyze Current Function Graph`
- `Tools -> AI Helper -> Summarize Current Binary`
- `Tools -> AI Helper -> Summarize Current Function Symboliks`
- `Tools -> AI Helper -> Queue Current Function Analysis`
- `Tools -> AI Helper -> Show Provider Status`
- `Tools -> AI Helper -> Start Leader Session`
- `Tools -> AI Helper -> Stop Leader Session`
- `Tools -> AI Helper -> Leader Session Status`

### Context-menu entries on functions

- `Explain Function with AI`
- `Analyze Function Graph with AI`
- `Summarize Symbolik Paths with AI`
- `Queue Function Analysis`

### Current GUI workflow

1. load a workspace in Vivisect
2. navigate to a function
3. use the Tools menu or right-click context menu
4. inspect the rendered explanation/graph/symbolik result
5. review any staged rename/comment suggestions before applying them
6. use `Show Provider Status` if model/provider readiness looks wrong

## Using Viv-AI as an MCP server

### stdio launcher

Installed console script:

```bash
viv-ai-mcp
```

Explicit config path:

```bash
viv-ai-mcp --config /path/to/config.json
```

Access mode flag:

```bash
viv-ai-mcp --config /path/to/config.json --mode local    # files only
viv-ai-mcp --config /path/to/config.json --mode remote   # server only
viv-ai-mcp --config /path/to/config.json --mode hybrid   # both (default)
```

Module form:

```bash
python -m viv_ai.mcp.entrypoint --config /path/to/config.json
```

### Hermes example

```yaml
mcp_servers:
  viv_ai:
    command: "viv-ai-mcp"
    args: ["--config", "/home/you/.config/viv-ai/config.json"]
    timeout: 60
    connect_timeout: 30
```

### Claude Desktop / generic stdio MCP example

```json
{
  "mcpServers": {
    "viv-ai": {
      "command": "viv-ai-mcp",
      "args": ["--config", "/home/you/.config/viv-ai/config.json"]
    }
  }
}
```

### Optional HTTP launcher

```bash
export VIV_AI_MCP_TOKEN=replace-me
viv-ai-mcp-http --config ~/.config/viv-ai/config.json --path /mcp
```

If you do not want to bake host/port/auth-env into the config file, CLI flags still work:

```bash
viv-ai-mcp-http --host 127.0.0.1 --port 8765 --path /mcp --auth-token-env VIV_AI_MCP_TOKEN
```

`GET /healthz` returns a small transport/health summary without exposing secret values.

More MCP examples live in:
- `docs/mcp-client-usage.md`

## Provider and model configuration

Viv-AI is designed to support both local and remote-backed models.

### Local Ollama

Use this when you want local-only operation.

- provider type: `ollama`
- endpoint example: `http://127.0.0.1:11434`
- model must match the exact installed model name

To list installed Ollama models:

```bash
curl http://127.0.0.1:11434/api/tags
# or
ollama list
```

Examples of valid model names seen during testing:
- `qwen2.5:72b-instruct`
- `qwen2.5-coder:32b-instruct`
- `cas/llama-3.2-3b-instruct:latest`
- `gemma4:31b`

### Remote-capable providers

Viv-AI includes config/model scaffolding for:
- Anthropic
- OpenAI-compatible APIs
- OpenRouter via the OpenAI-compatible surface
- Gemini

These still depend on your selected policy:
- `local_only: true` blocks remote-capable provider use on AI-backed paths
- set `remote_providers_enabled: true` when you explicitly want remote use

See `docs/provider-configuration.md` for copy-pasteable config examples.

## Standard analysis workflows

Current workflows exposed through the GUI and/or MCP surface include:
- binary summary
- function explanation
- function graph analysis
- symbolik path summarization
- rename proposal generation
- comment proposal generation
- review-before-apply mutation flow
- provider/model readiness inspection
- leader session lifecycle (start, stop, status)
- leader annotation and status queries
- leader explain-and-navigate coordination

Planned next-step workflow areas:
- richer batch analysis across selected function sets
- deeper graph/symbolik evidence binding
- vulnerability triage helpers
- exploit-assistance-oriented analyst workflows with strong review boundaries
- longer-term decompiler-oriented research informed by `https://decompilation.wiki/`

## Testing

Run the full unit and packaging suite:

```bash
pytest
```

Focused validation commands:

```bash
pytest tests/test_plugin_loading.py tests/test_ui_plugin.py tests/test_ui_render.py -q
pytest tests/test_config.py tests/test_mcp_entrypoint.py tests/test_mcp_http.py -q
```

Loader integration test with installed Vivisect:

```bash
pytest tests/test_viv_loader_integration.py
```

Optional live Ollama smoke test:

```bash
export VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1
export VIV_AI_OLLAMA_ENDPOINT=http://127.0.0.1:11434
export VIV_AI_OLLAMA_MODEL=qwen2.5:72b-instruct
pytest tests/test_ollama_live.py
```

## Documentation index

- `docs/provider-configuration.md`
- `docs/mcp-client-usage.md`
- `docs/roadmap-phases-p-plus.md`
- `docs/plans/2026-05-22-phase-p-usability-installation.md`
