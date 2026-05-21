# Viv-AI roadmap: Phase P and beyond

This note proposes the next phases after the current Phase O baseline.

## Phase P proposal: usability and operator experience

Goal: make Viv-AI easier to configure, discover, and operate without already knowing internal details.

Suggested scope:
- add provider/model discovery helpers
  - MCP tool or local helper to list configured providers
  - Ollama model discovery via `/api/tags`
- add clearer configuration surfaces
  - one documented config file example for local-only Ollama
  - one documented config file example for HTTP transport + auth
  - validation errors that point directly to the missing field/value
- improve docs and runbooks
  - stdio vs HTTP decision guide
  - mutation policy quick reference
  - troubleshooting page for timeouts, auth failures, and missing models
- improve operator-facing health/status
  - server info should expose transport/auth posture without secrets
  - optional endpoint or tool for model/provider readiness checks
- add end-to-end smoke coverage
  - real client-shaped tests for stdio and HTTP launch flows

Acceptance ideas:
- new users can select an installed Ollama model without reading source
- a broken config produces actionable errors
- docs cover the common local setup and the common MCP client setup

## Phase Q proposal: richer auth and multi-client transport maturity

Goal: make the HTTP surface more production-ready.

Suggested scope:
- stronger HTTP auth schemes beyond static bearer token env vars
- clearer auth failure/error taxonomy
- tighter request size and transport limits
- compatibility smoke tests for more MCP client shapes
- transport configuration serialization + validation tests

## Phase R proposal: analyst workflow polish

Goal: improve the day-to-day Vivisect UI experience.

Suggested scope:
- richer Qt-native widgets and layout polish
- better history browsing and result comparison
- queue inspection/editing tools for staged proposals
- clearer provenance display for cached vs fresh AI output
- small-task progress UX for background jobs

## Phase S proposal: advanced reasoning and batch workflows

Goal: increase analysis power and throughput.

Suggested scope:
- batch function analysis workflows
- targeted rename/comment campaigns over filtered function sets
- richer graph/symbolik cross-linking in AI outputs
- optional export/report generation for review sessions
- tighter bounded-output controls for larger binaries

## Phase T proposal: ecosystem and packaging maturity

Goal: make Viv-AI easier to adopt and maintain.

Suggested scope:
- packaged examples for Hermes, Claude Desktop, and generic MCP clients
- release checklist and versioned changelog flow
- CI test matrix for unit/integration/live-optional jobs
- contributor docs for adding providers/tools/schemas safely
- long-lived compatibility guidance for Vivisect and Ollama versions
