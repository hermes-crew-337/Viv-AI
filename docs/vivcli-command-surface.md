# Viv-AI VivCLI command surface sketch

This document sketches the in-Vivisect CLI command surface for Viv-AI workflows.

Target VivCLI integration point TBD pending repo confirmation of the right hook.

## Command namespace

Base: `:ai`

Subcommands:
- `status`
- `explain`
- `graph`
- `symbolik`
- `binary`
- `rename-proposal` / `comment-proposal`
- `vuln-surface`
- `vuln-triage`
- `decompile` (future)

## Command shapes

### `:ai status`

**Purpose:** Show configured providers, readiness, and local model state

**Example:**
```
(ai) status
Provider: ollama (ready)
Endpoint: http://127.0.0.1:11434
Model: qwen2.5:72b-instruct
Issues: none
```

**MCP equivalent:** `list_provider_models`

**Panel behavior:** Open/focus the AI Helper dock

### `:ai explain [fva]`

**Purpose:** Explain the current or named function

**Example:**
```
(ai) explain 0x401000
Decrypts payload buffer using RC4. Cross-references indicate network origin.
```

**MCP equivalent:** `ai_explain_function`

**Panel behavior:** Render result in AI Helper dock, stage rename/comment if provided

### `:ai graph [fva]`

**Purpose:** Analyze the current or named function’s control-flow graph

**Example:**
```
(ai) graph
Switch-based dispatcher with 7 cases. Jump table at 0x401020.
```

**MCP equivalent:** `get_function_graph_analysis`

**Panel behavior:** Render result in AI Helper dock

### `:ai symbolik [fva]`

**Purpose:** Interpret symbolic execution paths for the function

**Example:**
```
(ai) symbolik
One satisfiable success path. Sets retval=1 when eax==0.
```

**MCP equivalent:** `get_symbolik_summary`

**Panel behavior:** Render result in AI Helper dock

### `:ai binary`

**Purpose:** Summarize the entire workspace

**Example:**
```
(ai) binary
ELF service binary for amd64. Listens on TCP port, handles HTTP requests.
```

**MCP equivalent:** `get_binary_summary`

**Panel behavior:** Render result in AI Helper dock

### `:ai rename-proposal [fva] [hint]`

**Purpose:** Propose a name for a function with optional analyst hint

**Example:**
```
(ai) rename-proposal 0x401000 decrypt_payload
Proposed name: decrypt_payload_rc4
Staged in review panel.
```

**MCP equivalent:** `propose_function_rename`

**Panel behavior:** Stage in review panel

### `:ai comment-proposal [fva] [hint]`

**Purpose:** Propose a comment for a function with optional analyst hint

**Example:**
```
(ai) comment-proposal 0x401000 decryptor
Proposed comment: RC4 decryptor for stage2 payload
Staged in review panel.
```

**MCP equivalent:** `propose_comment`

**Panel behavior:** Stage in review panel

### `:ai vuln-surface [fva]`

**Purpose:** Scan a function for preliminary vulnerability patterns

**Example:**
```
(ai) vuln-surface
Potential buffer overflow at 0x401030: memcpy with unchecked length
Staged in vuln triage panel.
```

**MCP equivalent:** `analyze_vuln_function`

**Panel behavior:** Stage in vulnerability triage queue

### `:ai vuln-triage`

**Purpose:** Open the vulnerability triage panel and list findings

**Example:**
```
(ai) vuln-triage
1 unreviewed finding.
0x401000: buffer overflow (memcpy with user length)
```

**MCP equivalent:** `list_vuln_findings`

**Panel behavior:** Open/focus vuln triage dock

### Future: `:ai decompile [fva]`

**Purpose:** Assist in generating pseudocode for a function

**Example:**
```
(ai) decompile 0x401000
// Pseudocode sketch:
int decrypt_payload(char* input, int len) {
    rc4_init_key(...);
    for (int i = 0; i < len; i++) {
        input[i] ^= keystream[i];
    }
    return 0;
}
```

**MCP equivalent:** `propose_decompilation`

**Panel behavior:** Render in decompiler assistance dock

## Command behavior policy

All commands should:
- fail gracefully with error messages if Viv-AI is not loaded
- show "not configured" status if provider/model is missing
- log usage to the Vivisect console
- render results in the appropriate dock where available
- stage suggestions in the review panel when mutation is involved
- respect the global `MutationPolicy` config

## Future expansion hooks

Commands may grow flags for:
- `--model <name>` (override default)
- `--temperature <float>` (control randomness)
- `--no-cache` (force fresh analysis)
- `--audit` (log to audit trail if enabled)

But these should be explicitly opt-in per command rather than global flags to avoid complexity.
