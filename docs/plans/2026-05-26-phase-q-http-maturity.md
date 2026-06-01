# Phase Q HTTP Transport Maturity Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

Goal: make the HTTP surface more production-ready with stronger auth, clearer errors, and better limits.

Architecture: extend the existing `http_transport.py` module with richer auth options, better error handling, and request limits while maintaining backward compatibility. Add comprehensive tests for the new features.

Tech Stack: Python, HTTP server, pytest/unittest.

---

## Scope summary

Phase Q should focus on making the HTTP transport more robust and production-ready:

1. Enhanced authentication schemes
2. Better error handling and taxonomy
3. Request size and transport limits
4. Comprehensive compatibility testing
5. Configuration validation

---

## Task 1: Add support for API key authentication

Objective: Add support for API key authentication in addition to bearer tokens.

Files:
- Modify: `src/viv_ai/mcp/http_transport.py`
- Test: `tests/test_mcp_http.py`

Step 1: Add new auth configuration options
- Add `--api-key-env` argument
- Add support for API key in `X-API-Key` header

Step 2: Update auth validation logic
- Support both bearer token and API key authentication
- Ensure backward compatibility

Step 3: Add tests for API key auth
- Test successful API key auth
- Test failed API key auth
- Test mixed auth scenarios

Step 4: Update documentation
- Update `docs/mcp-client-usage.md` with API key examples
- Update argument help text

Step 5: Commit
`git commit -am "feat: add API key authentication support to HTTP transport"`

---

## Task 2: Implement request size limits

Objective: Add configurable request size limits to prevent resource exhaustion.

Files:
- Modify: `src/viv_ai/mcp/http_transport.py`
- Test: `tests/test_mcp_http.py`

Step 1: Add request size limit configuration
- Add `--max-request-size` argument (default 1MB)
- Add config file support for request size limits

Step 2: Implement request size checking
- Check Content-Length header
- Return 413 (Payload Too Large) for oversized requests

Step 3: Add tests for request size limits
- Test requests under the limit
- Test requests over the limit
- Test missing Content-Length header

Step 4: Commit
`git commit -am "feat: add request size limits to HTTP transport"`

---

## Task 3: Improve error handling and taxonomy

Objective: Create a clearer error taxonomy and better error responses.

Files:
- Modify: `src/viv_ai/mcp/http_transport.py`
- Test: `tests/test_mcp_http.py`

Step 1: Define error taxonomy
- Auth errors (401, 403)
- Client errors (400, 404, 413)
- Server errors (500, 503)
- Rate limiting errors (429)

Step 2: Implement structured error responses
- Consistent JSON error format
- Error codes and messages
- Request ID for tracing

Step 3: Add tests for error conditions
- Test each error type
- Verify error response format
- Test error logging

Step 4: Commit
`git commit -am "feat: improve HTTP error handling and taxonomy"`

---

## Task 4: Add rate limiting support

Objective: Add basic rate limiting to prevent abuse.

Files:
- Modify: `src/viv_ai/mcp/http_transport.py`
- Test: `tests/test_mcp_http.py`

Step 1: Add rate limiting configuration
- Add `--rate-limit` argument (requests per minute)
- Add `--rate-limit-window` argument (time window in seconds)

Step 2: Implement rate limiting
- Track requests per client IP or API key
- Return 429 (Too Many Requests) when limit exceeded
- Add Retry-After header

Step 3: Add tests for rate limiting
- Test requests under the limit
- Test requests over the limit
- Test rate limit reset

Step 4: Commit
`git commit -am "feat: add rate limiting to HTTP transport"`

---

|## Task 5: ~~Add comprehensive compatibility tests~~ ✅ DONE
|
|Objective: Ensure compatibility with various MCP clients.
|
|Files:
|- Create: `tests/test_mcp_http_compatibility.py` — 22 tests covering no-auth, bearer token, API key, GET /healthz, custom paths, invalid paths, Content-Length validation, end-to-end MCP flow (initialize → tools/list → tools/call → shutdown), server/info, request ID tracing, rate limiter IP isolation, rate limiter hybrid key, concurrent clients, env var resolution, and missing env var errors.
|
|Step 1: Test with different HTTP clients
|- Test no-auth mode
|- Test bearer token auth (standard and invalid)
|- Test API key auth (X-API-Key and Bearer header)
|
|Step 2: Test different auth methods
|- No auth
|- Bearer token
|- API key
|
|Step 3: Test error scenarios
|- Invalid requests, malformed JSON, unsupported methods
|- GET on unknown path, POST on unknown path
|- Invalid Content-Length header
|
|Step 4: Commit
|`git commit -am "test: add comprehensive HTTP compatibility tests"`
|
|---
|
|## Task 6: ~~Add transport configuration validation~~ ✅ DONE
|
|Objective: Add validation for HTTP transport configuration.
|
|Files:
|- Modify: `src/viv_ai/config.py` — extend AiConfig.validate() with host, port, request size, rate limit, rate limit window, auth token env, and API key env validation
|- Test: `tests/test_config.py` — 22 new tests in PhaseQTransportConfigValidationTests class
|
|Step 1: Add HTTP transport config validation
|- Validate host format (non-empty, non-whitespace)
|- Validate port range (0-65535)
|- Validate request size (must be positive)
|- Validate rate limit (non-negative) and rate limit window (positive)
|- Validate auth env var names (non-empty when set)
|
|Step 2: Add validation tests
|- 22 tests covering valid defaults, edge cases, and invalid configs
|
|Step 3: Commit
|`git commit -am "feat: add HTTP transport configuration validation"`

---

## Recommended execution order

1. Task 1 — API key authentication
2. Task 2 — Request size limits
3. Task 3 — Error handling improvements
4. Task 4 — Rate limiting
5. Task 6 — Configuration validation
6. Task 5 — Compatibility tests

This ordering builds the core functionality first, then adds comprehensive testing.

## Acceptance criteria

- The HTTP transport supports both bearer token and API key authentication
- Request size limits prevent resource exhaustion
- Error responses are consistent and informative
- Rate limiting prevents abuse
- Configuration is properly validated
- Compatibility is tested with multiple MCP clients
- Backward compatibility is maintained