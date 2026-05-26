# Viv-AI standard analysis workflows

This catalog describes the current and planned analyst workflows available through the Viv-AI GUI, MCP server, and future VivCLI surfaces.

The plugin is intentionally structured so that all analysis actions follow the same core pattern internally:
1. extract a bounded payload from Vivisect
2. send that to an analysis service with task type + options
3. render results or stage reviewable suggestions

This document catalogs what those tasks currently do and sketches what they might grow into.

## Binary-wide workflows

### Current: Binary summary

**Task:** generate a textual summary of the entire workspace

**Input shape:**
- Architecture
- Platform
- Format
- Entry points
- Imports
- Exports

**LLM prompt style:**
- "Here is a {format} binary compiled for {arch} on {platform}. It has entry points at {entrypoints}, imports {imports}, and exports {exports}. Summarize its likely purpose and threat posture."

**Current result format:**
```json
{
  "summary": "ELF binary likely serving as network service handler",
  "evidence": ["imports connect/listen/accept", "exports include service_main"],
  "confidence": "medium"
}
```

**Review behavior:** none

**Usage surface:** GUI binary menu, MCP `get_binary_summary`

**Future opportunities:**
- deeper file type detection via magic bytes
- import/export pattern analysis for library family identification
- threat posture triage based on known-vulnerable function patterns

### Planned: Vulnerability surface mapping

**Task:** detect and rank potential vulnerability surfaces across the binary

**Input shape:**
- all user-accessible entry points
- all import resolution failures
- all unchecked pointer/array access markers
- all external data deserialization points

**LLM prompt style:**
- "Here are the external entry surfaces. Rank them for vulnerability potential based on common patterns from CVE databases and exploit analysis literature."

**Future result format sketch:**
```json
{
  "surfaces": [
    {
      "fva": "0x401000",
      "type": "network handler",
      "risk": "high",
      "patterns": ["accepts raw buffer", "calls vulnerable memcpy"],
      "cve_suggestions": ["CVE-2021-1234-like overflow"]
    }
  ]
}
```

**Review behavior:** staged in review panel with risk categories

**Usage surface:** GUI binary menu, MCP `find_vuln_surfaces`

**Boundary notes:**
- always explain reasoning before proposing exploit sketches
- mark all automated surface suggestions as preliminary
- defer to analyst judgment on false positives

## Function-level workflows

### Current: Function explanation

**Task:** explain a function’s purpose and behavior from its metadata and disassembly

**Input shape:**
- function VA
- raw disassembly
- cross-references
- string references
- comment context if available

**LLM prompt style:**
- "Here is disassembly for function at {va}. It is called from {xrefs}, references strings {strings}. Explain what the function does and why it might exist."

**Current result format:**
```json
{
  "summary": "decrypts a payload buffer in-place using RC4",
  "evidence": ["mov esi, [esp+4] (payload)", "call rc4_init_key", "loop over buffer xor'ing with keystream"],
  "confidence": "high",
  "proposed_name": "rc4_decrypt_payload",
  "proposed_comment": "RC4 decryptor for stage2 payload"
}
```

**Review behavior:** stages `proposed_name` and `proposed_comment`

**Usage surface:** GUI Tools/context menus, MCP `ai_explain_function`

**Future opportunities:**
- richer cross-function behavioral linking
- pattern matches for known crypto/decode/implant logic
- integration with symbolik path evidence for deeper reasoning

### Current: Function rename/comment proposal

**Task:** generate a structured rename/comment for a function

**Input shape:**
- same as function explanation
- plus any staged suggestions from other analysis tools

**LLM prompt style:**
- "Given this function analysis, propose a consistent name and a useful descriptive comment following reverse-engineering best practices."

**Current result format:**
```json
{
  "proposed_name": "handle_http_request",
  "proposed_comment": "Parses HTTP headers from input buffer, dispatches to handler functions."
}
```

**Review behavior:** staged in review panel with accept/reject/reword controls

**Usage surface:** GUI panel apply buttons, MCP `propose_function_rename`, `propose_comment`

**Future opportunities:**
- batch naming campaigns via filtered function sets
- namespace-aware naming suggestions (e.g. `crypto::rc4_init`)
- integration with symbolik constraints for more precise naming

### Planned: Vulnerability analysis within function

**Task:** inspect a function for vulnerability patterns and risk posture

**Input shape:**
- full function disassembly
- string/xref context
- symbolik path constraints if available
- cached analysis from other tasks

**LLM prompt style:**
- "Inspect this function for common vulnerability patterns. Focus on buffer overflows, unchecked pointer derefs, integer overflows, format string bugs. For each finding, explain the evidence and suggest a cautious name suffix like _vuln_check."

**Future result format sketch:**
```json
{
  "findings": [
    {
      "type": "buffer overflow",
      "location": "0x401030",
      "evidence": "memcpy with user-controlled length",
      "comment_suffix": "_vuln_memcpy_overflow"
    }
  ]
}
```

**Review behavior:** staged naming suggestions with evidence previews

**Usage surface:** GUI context menu, MCP `analyze_vuln_function`

**Boundary notes:**
- always cite line-level evidence
- avoid generating exploit code or payload sketches here
- treat all findings as analyst-previewable hypotheses

## Graph-level workflows

### Current: Function graph analysis

**Task:** inspect a function’s control-flow graph for high-level structure

**Input shape:**
- function VA
- structured CFG with basic blocks and edges
- loop/branch metadata if available

**LLM prompt style:**
- "Here is a control-flow graph with {blocks} blocks and {edges} edges. Describe any high-level patterns like dispatchers, loops, conditional chains, or obfuscation attempts."

**Current result format:**
```json
{
  "summary": "dispatcher with nested switch-case handling",
  "evidence": ["central hub block with many outward edges", "consistent edge weights suggest jump table"],
  "confidence": "high"
}
```

**Review behavior:** none

**Usage surface:** GUI Tools/context menus, MCP `get_function_graph_analysis`

**Future opportunities:**
- deeper graph pattern recognition for compiler-generated or obfuscated code
- integration with symbolic execution path summaries
- vulnerability surfacing from graph structure (e.g. unchecked dispatch)

### Planned: Vulnerability tracing through graph structure

**Task:** trace potential vulnerability paths through a function’s CFG

**Input shape:**
- full CFG
- user-controlled input sources if known
- sensitive sink functions like `memcpy`, `strcpy`

**LLM prompt style:**
- "Trace paths from {input_sources} to {dangerous_sinks}. For each path, note whether the length or bounds are checked and whether a vulnerability is plausible."

**Future result format sketch:**
```json
{
  "paths": [
    {
      "from_va": "0x401000",
      "to_va": "0x401050",
      "dangerous_call": "memcpy@0x401040",
      "length_checked": false,
      "risk": "high"
    }
  ]
}
```

**Review behavior:** path evidence staged in review panel

**Usage surface:** GUI graph menu, MCP `trace_vuln_paths`

**Boundary notes:**
- treat all paths as "potentially vulnerable unless proven otherwise"
- defer to symbolic execution tools for exact constraints
- mark speculative findings clearly

## Symbolik path workflows

### Current: Symbolik path summarization

**Task:** interpret high-level behavior from symbolic execution paths

**Input shape:**
- list of symbolik paths with constraints and effects
- function VA context

**LLM prompt style:**
- "Here are symbolic execution paths for the function. Each has constraints and effects. Summarize the high-level behavior implied by the union of these paths."

**Current result format:**
```json
{
  "summary": "function returns 1 when eax == 0, otherwise enters error path",
  "evidence": ["constraint: eax == 0", "effect: retval = 1", "constraint: eax != 0", "effect: retval = 0, calls log_error"],
  "confidence": "medium"
}
```

**Review behavior:** none

**Usage surface:** GUI context menu (when symbolik backend present), MCP `get_symbolik_summary`

**Future opportunities:**
- deeper constraint interpretation via solver-backed LLM prompting
- integration with known vulnerability patterns via symbolic reasoning
- automated test-case sketch generation from satisfiable paths

### Planned: Exploit assistance from symbolik evidence

**Task:** assist in exploit development using symbolic path constraints

**Input shape:**
- satisfiable symbolik paths with exact constraints
- desired postcondition (e.g. "eax == 0xcafebabe after function return")
- architecture/platform context

**LLM prompt style:**
- "Given these satisfiable paths and desired postcondition, explain what input buffer or register values would achieve that result."

**Future result format sketch:**
```json
{
  "exploit_ideas": [
    {
      "type": "buffer overflow",
      "required_input": "buffer[100] = 0xcafebabe; buffer[104] = <ret_addr>",
      "evidence_path": "path-3",
      "postcondition": "eax = 0xcafebabe"
    }
  ]
}
```

**Review behavior:** exploit ideas staged with evidence/source path links

**Usage surface:** GUI symbolik menu, MCP `propose_exploit_paths`

**Boundary notes:**
- require explicit user activation for exploit-assist modes
- always explain the path logic before suggesting payloads
- mark all exploit assistance as for-defense-only tools
- log all exploit assist requests as structured audit entries

## Review/staged mutation workflows

### Current: Review queue and apply controls

**Task:** stage and review proposed changes before applying them

**Input shape:**
- staged rename/comment suggestions
- mutation policy (review_before_apply or direct_apply_enabled)

**LLM prompt style:**
- not directly involved (this is UI workflow orchestration)

**Current result format:**
- pending `proposed_name` and `proposed_comment` tracked in panel state
- apply buttons or context menu items for user action

**Review behavior:** mandatory multi-item queue inspection

**Usage surface:** GUI panel buttons, GUI context menus if policy allows

**Future opportunities:**
- richer queue inspection/editor UX
- multi-function batch apply with group comments
- integration with external review tools or logging systems

### Planned: Vulnerability triage queue

**Task:** inspect and triage vulnerability surface suggestions in batch

**Input shape:**
- list of vulnerability findings from various analysis tasks
- risk categories and evidence summaries

**LLM prompt style:**
- when user drills down:
  - "Here is the evidence for finding {n}. Explain why this represents a plausible vulnerability surface and what an attacker might attempt."

**Future result format sketch:**
```json
{
  "triage_queue": [
    {
      "fva": "0x401000",
      "type": "buffer overflow",
      "risk": "high",
      "evidence_preview": "memcpy with unchecked user length",
      "status": "unreviewed"
    }
  ]
}
```

**Review behavior:** findings staged in vulnerability triage panel

**Usage surface:** GUI vuln triage dock, MCP `list_vuln_findings`

**Boundary notes:**
- treat all findings as "to be confirmed by analyst"
- preserve all evidence and reasoning for external review
- log all triage decisions for later audit if configured

## Policy and mutation boundaries

All AI-backed actions today use the `MutationPolicy` enum to decide apply behavior:

### CONSERVATIVE_READONLY
- only allow inspection tools
- block all rename/comment/apply actions
- safest default posture

### REVIEW_BEFORE_APPLY
- stage all changes in review panel
- require explicit user accept for each apply
- prevent direct-apply tools in MCP unless configured otherwise

### DIRECT_APPLY_ENABLED
- allow automated apply on trusted internal models only
- log all applies to audit trail
- require `local_only: false` and `remote_providers_enabled: true`

This policy posture is checked:
- in GUI panel methods before staging suggestions
- in MCP tool handlers before applying changes
- in Vivisect context-menu hooks before direct applies

Future exploit-assistance or decompiler workflows will likely:
- require a new policy tier above `REVIEW_BEFORE_APPLY`
- mandate audit logging for all tool-use requests
- include structured provenance for all model inputs/outputs
