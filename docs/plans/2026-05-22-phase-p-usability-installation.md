# Phase P Usability and Easy Installation Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

Goal: make Viv-AI easy to install, configure, discover, and use from both MCP clients and the Vivisect GUI without requiring source diving.

Architecture: keep the shared `viv_ai` core as the single source of truth for provider config, analysis workflows, and runtime policy; expose that core through clearer README/docs, runtime config discovery, richer Vivisect menu/context actions, and lightweight operator-facing status surfaces. Defer decompiler/exploit-specific heavy features to later phases, but shape the current workflows so they can host those future actions cleanly.

Tech Stack: Python, Vivisect plugin entrypoints, Qt/Vivisect GUI hooks, MCP stdio/HTTP transports, JSON config files, pytest/unittest.

---

## Scope summary

Phase P should land in four tracks:

1. Easy installation and no-brainer README flows
2. Provider setup and configuration clarity for local + remote LLMs
3. Vivisect UX controls: menu paths, context menus, hotkeys, and VivCLI follow-ons
4. Analyst workflows: common AI-assisted actions over function, graph, symbolik, binary, and future vuln/exploit assistance

Out of scope for this phase:
- full decompiler implementation
- exploit generation automation that mutates targets or emits weaponized output by default
- production auth redesign beyond current HTTP bearer-token posture
- heavy remote orchestration or multi-user persistence

---

## Task 1: Document the end-user installation story in README

Objective: make the README sufficient for a new user to get Viv-AI running in the two primary modes: Vivisect GUI plugin and MCP server.

Files:
- Modify: `README.md`
- Test: `tests/test_packaging.py` if README-linked assumptions imply packaging expectations

Step 1: Add a short "Quick Start" section near the top.
- Include editable-install setup.
- Include exact `VIV_EXT_PATH` usage for Vivisect plugin loading.
- Include exact `viv-ai-mcp` launch usage.
- Include default config path `~/.config/viv-ai/config.json` and env override `VIV_AI_CONFIG`.

Step 2: Add a "Choose your mode" section.
- Mode A: using AI inside the Vivisect GUI
- Mode B: using Viv-AI as an MCP server from Hermes / mcp-cli / Claude Desktop / generic clients
- Explain when to choose each in 1-2 sentences.

Step 3: Add a "First working config" section.
- Show one minimal Ollama config.
- Show one remote-provider-enabled config example.
- Explicitly note that remote providers remain policy-gated.

Step 4: Add a "What appears in Vivisect" section.
- List current Tools menu entries.
- List context-menu actions.
- Mention provider-status visibility and staged review behavior.

Step 5: Verify readability.
Run: `. .venv/bin/activate && pytest tests/test_packaging.py -q`
Expected: PASS

Step 6: Commit.
`git commit -am "docs: add README quick start and usage guide"`

---

## Task 2: Add dedicated provider configuration documentation

Objective: make model/provider setup obvious for Ollama, OpenAI-compatible APIs, Anthropic, Gemini, and OpenRouter.

Files:
- Create: `docs/provider-configuration.md`
- Modify: `README.md`
- Modify: `docs/mcp-client-usage.md`

Step 1: Create a provider matrix.
For each provider, document:
- `provider_type`
- typical endpoint
- how auth is supplied
- exact model field expectations
- local-only vs remote-provider policy implications

Step 2: Add concrete JSON examples.
Include examples for:
- Ollama local server
- OpenAI / OpenRouter compatible endpoint
- Anthropic
- Gemini

Step 3: Add troubleshooting notes.
Include:
- missing model
- wrong endpoint
- auth not configured
- local-only policy blocking remote usage

Step 4: Link this doc from `README.md` and `docs/mcp-client-usage.md`.

Step 5: Verify config docs match code.
Read against:
- `src/viv_ai/config.py`
- `src/viv_ai/models.py`
- `src/viv_ai/providers/*.py`

Step 6: Commit.
`git commit -am "docs: add provider configuration guide"`

---

## Task 3: Harden runtime config discovery and launcher ergonomics

Objective: make config discovery consistent for plugin and MCP entrypoints so users do not have to manually wire config in code.

Files:
- Modify: `src/viv_ai/config.py`
- Modify: `src/viv_ai/__init__.py`
- Modify: `src/viv_ai/mcp/entrypoint.py`
- Modify: `src/viv_ai/mcp/http_transport.py`
- Test: `tests/test_config.py`
- Test: `tests/test_plugin_loading.py`
- Test: `tests/test_mcp_entrypoint.py`
- Test: `tests/test_mcp_http.py`

Step 1: Add failing tests for config path resolution.
Cover:
- no file present -> default in-memory config
- explicit path wins
- env path wins when no explicit path
- missing explicit path raises `FileNotFoundError`

Step 2: Add/adjust plugin entrypoint tests.
Cover:
- `vivExtension()` result exposes `config_path`
- boot log mentions Phase P and whether config file/default config was used

Step 3: Add/adjust MCP launcher tests.
Cover:
- `--config` is accepted by stdio entrypoint
- HTTP launcher can be driven from config-backed auth/host/port values

Step 4: Implement minimal code to satisfy tests.
Keep one runtime config resolver in `config.py`; do not duplicate path logic in each launcher.

Step 5: Run focused tests.
Run: `. .venv/bin/activate && pytest tests/test_config.py tests/test_plugin_loading.py tests/test_mcp_entrypoint.py tests/test_mcp_http.py -q`
Expected: PASS

Step 6: Commit.
`git commit -am "feat: unify runtime config loading across plugin and MCP launchers"`

---

## Task 4: Finish the current Vivisect GUI control surface

Objective: make the AI helper discoverable from normal Vivisect workflows.

Files:
- Modify: `src/viv_ai/ui/widgets.py`
- Modify: `src/viv_ai/ui/render.py`
- Modify: `src/viv_ai/ui/__init__.py`
- Test: `tests/test_ui_plugin.py`
- Test: `tests/test_ui_render.py`

Step 1: Ensure Tools menu exposes the core actions.
Required actions:
- Show Panel
- Explain Current Function
- Analyze Current Function Graph
- Summarize Current Binary
- Summarize Current Function Symboliks
- Queue Current Function Analysis
- Show Provider Status

Step 2: Ensure context menus expose per-function actions.
Required actions:
- Explain Function with AI
- Analyze Function Graph with AI
- Summarize Symbolik Paths with AI
- Queue Function Analysis

Step 3: Render provider/model health clearly.
Include configured model, discovered models, provider type, endpoint, and validation issues.

Step 4: Preserve shared panel/controller state.
All menu and context actions must reuse the installed panel instance.

Step 5: Run focused GUI tests.
Run: `. .venv/bin/activate && pytest tests/test_ui_plugin.py tests/test_ui_render.py -q`
Expected: PASS

Step 6: Commit.
`git commit -am "feat: expand Vivisect AI helper controls and provider status"`

---

## Task 5: Design and stage VivCLI integration points

Objective: define the command surface for analysts who want text-driven access inside Vivisect before building the full command handler.

Files:
- Create: `docs/vivcli-command-surface.md`
- Modify: `docs/plans/2026-05-22-phase-p-usability-installation.md`
- Future code targets: Vivisect command registration layer once the host-side hook is selected

Step 1: Decide the command shape.
Proposed commands:
- `:ai status`
- `:ai explain 0x401000`
- `:ai graph 0x401000`
- `:ai symbolik 0x401000`
- `:ai binary`
- `:ai rename-proposal 0x401000 decrypt_payload`

Step 2: Define output contracts.
For each command, specify:
- text output
- whether it stages review items
- whether it is read-only
- whether it should open/focus the panel

Step 3: Identify the code hook point in Vivisect.
Do not implement until the repo confirms the right host-side registration API.

Step 4: Commit.
`git commit -am "docs: define VivCLI command surface for Viv-AI"`

---

## Task 6: Build an analysis workflow catalog for common reverse-engineering tasks

Objective: clearly define the standard AI-assisted operations the plugin should support next.

Files:
- Create: `docs/analysis-workflows.md`
- Modify: `README.md`
- Modify: `docs/roadmap-phases-p-plus.md`

Step 1: Group workflows by input shape.
Sections:
- binary-wide summarization
- function explanation
- graph reasoning
- symbolik/path reasoning
- rename/comment proposal workflows
- future vuln triage workflows

Step 2: For each workflow, specify:
- required extraction inputs
- bounded data to send to LLM
- expected model output shape
- review/apply behavior
- failure modes

Step 3: Add future-oriented sections for:
- vulnerability surfacing
- exploit-assistance boundaries
- decompiler-assisted workflows referencing `https://decompilation.wiki/`

Step 4: Commit.
`git commit -am "docs: add analysis workflow catalog"`

---

## Task 7: Add end-to-end smoke coverage for the documented paths

Objective: make sure the new install/docs flows are backed by at least thin automated coverage.

Files:
- Modify: `tests/test_plugin_loading.py`
- Modify: `tests/test_mcp_entrypoint.py`
- Modify: `tests/test_mcp_http.py`
- Optional create: `tests/test_docs_examples.py`

Step 1: Cover plugin bootstrap with default config.

Step 2: Cover stdio MCP bootstrap with `--config`.

Step 3: Cover HTTP bootstrap with config-driven auth env var.

Step 4: If practical, add a docs-example smoke test that validates example JSON config snippets deserialize through `AiConfig.from_dict()`.

Step 5: Run the focused suite.
Run: `. .venv/bin/activate && pytest tests/test_config.py tests/test_plugin_loading.py tests/test_ui_plugin.py tests/test_ui_render.py tests/test_mcp_entrypoint.py tests/test_mcp_http.py -q`
Expected: PASS

Step 6: Commit.
`git commit -am "test: cover documented config and launcher flows"`

---

## Recommended execution order

1. Task 3 — config/runtime ergonomics
2. Task 4 — GUI controls and provider status
3. Task 1 — README quick start
4. Task 2 — provider configuration guide
5. Task 6 — analysis workflow catalog
6. Task 5 — VivCLI command surface design
7. Task 7 — end-to-end smoke coverage

This ordering gets the user-visible product behavior stable before freezing the docs.

## Acceptance criteria

- A new user can install Viv-AI and launch either the plugin or the MCP server from README alone.
- A new user can configure Ollama, Anthropic, OpenAI/OpenRouter-compatible APIs, or Gemini from copy-pasteable docs.
- The Vivisect GUI exposes obvious menu/context actions for the core AI workflows.
- Provider/model readiness is visible in-product and in MCP tooling.
- Runtime config behavior is consistent across GUI plugin, stdio MCP, and HTTP MCP launchers.
- The docs explicitly separate current capability from future work such as vuln triage, exploit assistance, and decompiler ideas.

## Notes for later phases

- Vulnerability pinpointing should begin as explainable triage and hypothesis generation, not silent automation.
- Exploit-assistance features should be explicitly scoped, logged, and review-oriented.
- Decompiler work should be treated as its own architecture phase informed by decompilation.wiki concepts, with IR/lifting boundaries documented before code is written.
