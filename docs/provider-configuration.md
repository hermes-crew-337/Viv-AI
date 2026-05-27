# Viv-AI provider configuration

This document shows how to configure Viv-AI to talk to local or remote-backed LLM providers.

Viv-AI config resolution order is:
- explicit CLI flag: `--config /path/to/config.json`
- env override: `VIV_AI_CONFIG=/path/to/config.json`
- default file: `~/.config/viv-ai/config.json`
- otherwise: default in-memory config

## Common fields

Top-level config fields you will usually care about:

```json
{
  "default_provider": "ollama",
  "default_model": "qwen2.5:72b-instruct",
  "local_only": true,
  "remote_providers_enabled": false,
  "mutation_policy": "review_before_apply",
  "providers": {}
}
```

Notes:
- `default_provider` must match a key inside `providers`
- `default_model` is a convenience/default field; each provider still needs its own `model`
- `local_only: true` keeps AI-backed analysis restricted to local providers
- `remote_providers_enabled: true` must be set before intentionally using remote-capable providers
- `mutation_policy` controls whether rename/comment changes are review-only or direct-apply capable

## Provider matrix

### Ollama

Use when:
- you want local-only model execution
- you already have models installed in Ollama

Key fields:
- `provider_type`: `ollama`
- `endpoint`: usually `http://127.0.0.1:11434`
- `model`: exact installed model name
- auth: none at the Viv-AI layer

Example:

```json
{
  "default_provider": "ollama",
  "default_model": "qwen2.5:72b-instruct",
  "local_only": true,
  "remote_providers_enabled": false,
  "providers": {
    "ollama": {
      "provider_type": "ollama",
      "endpoint": "http://127.0.0.1:11434",
      "model": "qwen2.5:72b-instruct"
    }
  }
}
```

Model discovery:

```bash
curl http://127.0.0.1:11434/api/tags
# or
ollama list
```

The model string is used verbatim. Examples:
- `qwen2.5:72b-instruct`
- `qwen2.5-coder:32b-instruct`
- `cas/llama-3.2-3b-instruct:latest`
- `gemma4:31b`

### OpenAI-compatible APIs

Use when:
- your endpoint speaks an OpenAI-style chat/completions API
- you want OpenAI itself or another compatible backend
- you want OpenRouter through the compatible surface

Key fields:
- `provider_type`: `openai_compat`
- `endpoint`: base API URL
- `model`: remote model ID
- auth: provider config fields and/or environment-driven integration in the provider adapter path

Example:

```json
{
  "default_provider": "openrouter",
  "default_model": "anthropic/claude-3.7-sonnet",
  "local_only": false,
  "remote_providers_enabled": true,
  "providers": {
    "openrouter": {
      "provider_type": "openai_compat",
      "endpoint": "https://openrouter.ai/api/v1",
      "model": "anthropic/claude-3.7-sonnet",
      "api_key_env": "OPENROUTER_API_KEY"
    }
  }
}
```

You can use the same shape for other compatible endpoints by changing `endpoint`, provider name, model ID, and the env var you use for the key.

### Anthropic

Use when:
- you want the Anthropic-native request shape instead of a compatibility layer

Key fields:
- `provider_type`: `anthropic`
- `endpoint`: typically `https://api.anthropic.com`
- `model`: e.g. a Claude model ID
- auth: API key via the provider’s configured auth path

Example:

```json
{
  "default_provider": "anthropic",
  "default_model": "claude-3-7-sonnet-latest",
  "local_only": false,
  "remote_providers_enabled": true,
  "providers": {
    "anthropic": {
      "provider_type": "anthropic",
      "endpoint": "https://api.anthropic.com",
      "model": "claude-3-7-sonnet-latest",
      "api_key_env": "ANTHROPIC_API_KEY"
    }
  }
}
```

### Gemini

Use when:
- you want Google Gemini models through the Gemini-native request shape

Key fields:
- `provider_type`: `gemini`
- `endpoint`: typically `https://generativelanguage.googleapis.com`
- `model`: Gemini model ID
- auth: API key via the provider’s configured auth path

Example:

```json
{
  "default_provider": "gemini",
  "default_model": "gemini-2.5-pro",
  "local_only": false,
  "remote_providers_enabled": true,
  "providers": {
    "gemini": {
      "provider_type": "gemini",
      "endpoint": "https://generativelanguage.googleapis.com",
      "model": "gemini-2.5-pro",
      "api_key_env": "GEMINI_API_KEY"
    }
  }
}
```

## Local-only vs remote policy

Viv-AI intentionally keeps provider selection policy separate from provider wiring.

Common safe local setup:

```json
{
  "local_only": true,
  "remote_providers_enabled": false
}
```

Remote-enabled setup:

```json
{
  "local_only": false,
  "remote_providers_enabled": true
}
```

If a remote-capable provider is configured but the policy still says local-only, AI-backed analysis paths should refuse to use that provider and report a structured issue instead of silently sending data remotely.

## MCP HTTP transport auth config

For the optional HTTP MCP transport, keep raw auth secrets out of the config file itself when possible.

Example using bearer token authentication:

```json
{
  "mcp_http_bind_host": "127.0.0.1",
  "mcp_http_bind_port": 8765,
  "mcp_http_auth_token_env": "VIV_AI_MCP_TOKEN"
}
```

Example using API key authentication:

```json
{
  "mcp_http_bind_host": "127.0.0.1",
  "mcp_http_bind_port": 8765,
  "mcp_http_api_key_env": "VIV_AI_MCP_API_KEY"
}
```

Then export the actual token or API key before launching:

```bash
# For bearer token authentication
export VIV_AI_MCP_TOKEN=replace-me
viv-ai-mcp-http --config ~/.config/viv-ai/config.json

# For API key authentication
export VIV_AI_MCP_API_KEY=replace-me
viv-ai-mcp-http --config ~/.config/viv-ai/config.json
```

## Troubleshooting

### "default provider 'X' is not configured"

Fix:
- make sure `default_provider` matches a key under `providers`
- example: `default_provider: "ollama"` requires `providers.ollama`

### "provider 'X' has no endpoint configured"

Fix:
- set `providers.<name>.endpoint`
- make sure you used the correct base URL for that provider

### "provider 'X' has no model configured"

Fix:
- set `providers.<name>.model`
- for Ollama, use the exact installed name from `ollama list` or `/api/tags`

### remote provider blocked by policy

Fix:
- set `local_only` to `false`
- set `remote_providers_enabled` to `true`
- confirm you actually intend to send analysis content to a remote service

### HTTP MCP auth env var is not set

Fix:
- export the env var named by `mcp_http_auth_token_env` or `mcp_http_api_key_env`
- then restart `viv-ai-mcp-http`

## Related docs

- `README.md`
- `docs/mcp-client-usage.md`
- `docs/roadmap-phases-p-plus.md`
