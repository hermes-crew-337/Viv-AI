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

Not yet implemented in Phase A:
- function/binary extraction logic
- graph or symbolic-analysis orchestration
- GUI widgets/docks
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
