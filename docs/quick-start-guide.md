# Viv-AI Quick Start: First 10 Minutes

This guide walks you from zero to your first AI-powered analysis in under ten minutes. No prior Viv-AI knowledge assumed.

---

## Prerequisites

- Python 3.11+
- `vivisect` installed (`pip install vivisect` or via your preferred method)
- [Ollama](https://ollama.ai) installed locally for local model inference (or any OpenAI-compatible provider if you prefer)

---

## Minute 0–2: Install Viv-AI

Preferred setup with `uv`:

```bash
cd ~/BotShare/hermes_workspace/repos/Viv-AI   # or wherever your workspace is
uv venv --clear .venv && . .venv/bin/activate
uv pip install -e .
```

Or standard pip:

```bash
cd ~/BotShare/hermes_workspace/repos/Viv-AI
python3 -m venv .venv && . .venv/bin/activate
pip install -U pip && pip install vivisect -e .
```

---

## Minute 2–4: Install a model

If using local Ollama (recommended for first-time setup):

```bash
ollama pull qwen2.5:72b-instruct   # or any small/fast model to start
curl http://127.0.0.1:11434/api/tags | python -m json.tool
# Verify it appears in the list above
```

If using a remote provider (OpenAI, Anthropic, etc.), skip this step and move to config.

---

## Minute 4–6: Create your first config file

Create `~/.config/viv-ai/config.json` with minimal Ollama config:

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

Key fields explained:
- **`local_only: true`** — Prevents any calls to remote API providers (safe default)
- **`mutation_policy: "review_before_apply"`** — All rename/comment changes must be reviewed and applied explicitly; never direct-write to the workspace
- **`remote_providers_enabled: false`** — Blocks OpenRouter/Anthropic/OpenAI even if configured

---

## Minute 6–8: Start your first analysis session

### Option A: Via Vivisect GUI (interactive)

```bash
export VIV_EXT_PATH=/path/to/Viv-AI/src   # points Vivisect at the plugin entrypoint
vivise  # launch Vivisect normally
```

Once running:

1. Open any binary workspace: `File -> Open` (or drag a `.bin` file onto the window)
2. Right-click any address in the disassembly listing and choose `Explain Function with AI`
3. Or use the Tools menu: `Tools -> AI Helper -> Show Panel`
4. The panel should render an AI-powered explanation of the selected function

### Option B: Via MCP server (headless/agent-driven)

```bash
viv-ai-mcp
```

Or with explicit config path:

```bash
viv-ai-mcp --config ~/.config/viv-ai/config.json
```

From another terminal, you can immediately send JSON-RPC tools. Example for function explanation:

```json
{
  "method": "tools/call",
  "params": {
    "name": "ai_explain_function",
    "arguments": {
      "workspace": "/path/to/binary.vw",
      "function_address": "0x401000"
    }
  }
}
```

---

## Minute 8–9: Review a rename suggestion

To see the mutation workflow in action:

1. In the GUI, use `Explain Function with AI` on any function
2. Ask (via panel or MCP) for a suggested rename: `"propose_rename function at 0x401000"`
3. The function is **not renamed** — it's queued in the review stage
4. Apply from the GUI: `Tools -> AI Helper -> Show Review Queue` and click "Apply"
5. Or via MCP, call `apply_suggested_renames` to confirm

This is how all write-back works — staged, never automatic.

---

## Minute 9–10: Verify mode flags at runtime

Start the server with diagnostics printed on launch:

```bash
viv-ai-mcp --mode local    # files only — no server calls
viv-ai-mcp --mode remote   # server only — no local filesystem access
viv-ai-mcp --mode hybrid   # both (default)
```

On startup, Viv-AI prints diagnostic info. If you'd like more verbose logs at launch, add:

```bash
VIV_AI_DEBUG=1 viv-ai-mcp
```

You should see something like:

```
[Viv-AI MCP] Mode: hybrid
  Local files: allowed
  Server:      allowed
  AI provider: ollama/qwen2.5:72b-instruct
  Mutation policy: review_before_apply
```

---

## You're all set. What's next?

- **Deep dive on MCP clients** → `docs/mcp-client-usage.md` for Hermes/Anthropic/Claude Desktop integration examples
- **Provider config reference** → `docs/provider-configuration.md` for remote providers (OpenAI, Anthropic, OpenRouter, Gemini)
- **Collaborative sessions** → `docs/leader-session-guide.md` for leader/assistant multi-agent workflows
- **Full workflow docs** → `docs/analysis-workflows.md` for batch triage, exploit-assistance pipelines

---

*This file is PR-ready. Insert it between existing "### 2) Create a config file" and "### 3) Pick your mode" sections in README.md.*
