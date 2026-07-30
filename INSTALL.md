# Viv-AI Installation Guide

## Requirements

- **Python 3.10+** (tested with 3.11)
- **Vivisect** (installable from PyPI or your own fork)
- **(optional)** An Ollama instance or remote AI provider endpoint for AI-backed tools
- **(optional)** A Vivisect Server instance for collaborative/leader workflows

## Install Viv-AI

### Using uv (recommended)

```bash
uv venv --clear .venv
source .venv/bin/activate
uv pip install pytest vivisect
uv pip install -e .
```

### Using venv + pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install vivisect pytest
pip install -e .
```

This installs two console scripts:
- **`viv-ai-mcp`** — stdio MCP server entrypoint
- **`viv-ai-mcp-http`** — optional HTTP MCP transport

## Configure AI Providers

Viv-AI loads configuration from the first available source:

1. `--config /path/to/config.json` (CLI flag)
2. `$VIV_AI_CONFIG` (environment variable)
3. `~/.config/viv-ai/config.json` (default path)
4. In-memory defaults (no file needed, but AI tools won't work)

### Minimal local Ollama config

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

Save at `~/.config/viv-ai/config.json`:

```bash
mkdir -p ~/.config/viv-ai
cp config.json ~/.config/viv-ai/
```

See `docs/provider-configuration.md` for Anthropic, OpenAI, OpenRouter, and Gemini examples.

## Using as a Vivisect GUI Plugin

Point Vivisect at the package:

```bash
export VIV_EXT_PATH=/path/to/Viv-AI/src
vivisect
```

The plugin registers under **Tools → AI Helper** with menu entries for:
- Explain / Graph / Symbolik / Binary analysis of the current function
- Queue, review, and apply rename/comment suggestions
- **Start/Stop/Status** leader session management (requires server connection)

## Using as an MCP Server

### stdio mode

```bash
viv-ai-mcp --config ~/.config/viv-ai/config.json
```

Access mode flag:

```bash
viv-ai-mcp --mode local    # files only; blocks server_connect
viv-ai-mcp --mode remote   # server only; blocks workspace_open
viv-ai-mcp --mode hybrid   # both allowed (default)
```

Other common flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--once` | off | Process one JSON-RPC request and exit |
| `--config` | auto | Path to config file |
| `--mode` | hybrid | Workspace access scope |
| `--read-only` | auto | Block mutations |
| `--read-write` | auto | Allow mutations |
| `--analyze-timeout` | 60s | Background analysis timeout on open |

### HTTP mode

```bash
export VIV_AI_MCP_TOKEN=your-token
viv-ai-mcp-http --host 127.0.0.1 --port 8765 --auth-token-env VIV_AI_MCP_TOKEN
```

### Hermes Agent config

```yaml
mcp_servers:
  viv_ai:
    command: "viv-ai-mcp"
    args: ["--config", "/home/you/.config/viv-ai/config.json"]
    timeout: 60
    connect_timeout: 30
```

## Testing

```bash
pytest
```

Optional live Ollama smoke test:

```bash
export VIV_AI_ENABLE_LIVE_OLLAMA_TEST=1
export VIV_AI_OLLAMA_ENDPOINT=http://127.0.0.1:11434
export VIV_AI_OLLAMA_MODEL=qwen2.5:72b-instruct
pytest tests/test_ollama_live.py
```

## Troubleshooting

### "No AI providers configured"
1. Check that `~/.config/viv-ai/config.json` exists or use `--config`
2. Confirm `provider_type` is one of: `ollama`, `openai`, `anthropic`, `gemini`
3. Run `list_provider_models` MCP tool to see what's discovered

### "workspace is not connected to a Vivisect Server"
Leader tools require a remote workspace opened via `server_connect`. Use `workspace_open` for local files instead.

### "cannot open local workspace: server is in 'remote' mode"
The server was launched with `--mode remote` which blocks local file opens. Use `--mode hybrid` (default) or `--mode local`.

### "cannot connect to remote server: server is in 'local' mode"
The server was launched with `--mode local` which blocks server connections. Use `--mode hybrid` (default) or `--mode remote`.

### Timeouts on AI-calling tools
- Increase `--analyze-timeout` (or `mcp_max_tool_seconds` in config)
- Check provider endpoint health outside Viv-AI
- Reduce model size or switch to a faster model

## Layout

```
Viv-AI/
├── src/
│   └── viv_ai/
│       ├── __init__.py        # vivExtension plugin entrypoint
│       ├── service.py         # analysis service orchestration
│       ├── config.py          # config model + loader
│       ├── mcp/               # MCP server tools + transport
│       ├── ui/                # Qt dock widget + menus
│       └── ...
├── tests/
├── INSTALL.md                 # this file
├── README.md                  # overview
└── docs/
    ├── provider-configuration.md
    ├── mcp-client-usage.md
    └── roadmap-phases-p-plus.md
```

## Upgrading

```bash
cd /path/to/Viv-AI
git pull
pip install -e .
```

If the schema changed, check `docs/provider-configuration.md` for new config fields.
