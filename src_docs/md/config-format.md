---
title: Config Format Reference
---

# Config Format Reference

## Source of Truth file (`mcp.json`)

The SoT uses the canonical Claude Desktop JSON shape — `"mcpServers"` at the top level, each
server keyed by name:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/you/projects"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "ghp_..." }
    },
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

## McpServer fields

Every server entry in the SoT is validated against the `McpServer` Pydantic model.
All fields are optional (the model is permissive to handle agent-specific extras).

### Core stdio fields

| Field | Type | Description |
|-------|------|-------------|
| `command` | `str` | Executable to run (e.g. `"npx"`, `"uvx"`, `"/usr/local/bin/python3"`) |
| `args` | `list[str]` | Arguments passed to `command`. A bare string is auto-promoted to a one-element list. |
| `env` | `dict[str, str]` | Environment variables injected into the subprocess. |
| `cwd` | `str` | Working directory for the subprocess. |

### Core HTTP fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Canonical remote URL (SSE or Streamable HTTP endpoint). |
| `type` | `str` | Transport type: `"stdio"`, `"sse"`, `"http"`. |
| `transport` | `str` | Alternative transport field; `"streamable-http"` and `"streamableHttp"` are normalized to `"http"`. |

### Common flags

| Field | Type | Description |
|-------|------|-------------|
| `disabled` | `bool` | Marks the server as off. Takes precedence over `enabled`. |
| `enabled` | `bool` | Inverted flag; `false` disables. Used by some agents instead of `disabled`. |
| `timeout` | `int` | Subprocess / connection timeout in seconds. |

### Agent-specific fields stored in the SoT

The SoT preserves all extra fields that individual agents attach. Common ones:

| Field | Used by | Description |
|-------|---------|-------------|
| `alwaysAllow` | Cline, Roo, Kilo | Tools auto-approved without confirmation |
| `autoApprove` | Cline, Roo | Legacy alias for `alwaysAllow` |
| `trust` | Gemini / Antigravity | Marks the server as trusted |
| `bearerTokenEnvVar` | Codex CLI | Env-var name holding the bearer token |
| `httpHeaders` | Codex CLI | Static HTTP headers as `dict[str, str]` |
| `headers` | many agents | HTTP request headers |
| `envFile` | VS Code | Path to a `.env` file injected at launch |

## Agent-specific output format mapping

When `push` writes to an agent's config, `mcp-synchro` applies agent-specific transformations:

### Remote URL key

Different agents use different JSON keys for the HTTP endpoint URL:

| Key | Used by |
|-----|---------|
| `url` | Claude Desktop, Cursor, VS Code, Codex CLI, most agents |
| `serverUrl` | Antigravity (Desktop, IDE, CLI), Windsurf |
| `httpUrl` | Gemini CLI (legacy, for Streamable HTTP; SSE uses `url`) |

`mcp-synchro` always stores the canonical `url` in the SoT and rewrites it to the correct key on push.

### Transport indicator

| Mode | Meaning | Used by |
|------|---------|---------|
| `explicit` | Requires `"type": "http"` (or `"sse"`) in the output | Cursor, VS Code, most agents |
| `implicit` | Transport inferred from URL presence; no `type` field emitted | Antigravity, Windsurf |

### camelCase ↔ snake_case (Codex CLI)

Codex CLI is the only agent that uses TOML + snake_case keys.
`mcp-synchro` converts field names bidirectionally:

| SoT / JSON (camelCase) | Codex TOML (snake_case) |
|------------------------|------------------------|
| `bearerTokenEnvVar` | `bearer_token_env_var` |
| `alwaysAllow` | `always_allow` |
| `httpHeaders` | `http_headers` |
| `mcpServers` wrapper | `[mcp_servers."name"]` TOML table |

### OpenCode: command array + environment

OpenCode combines `command` and `args` into a single array and renames `env` → `environment`:

| SoT field | OpenCode field |
|-----------|----------------|
| `command` + `args` | `"command": ["npx", "-y", "…"]` |
| `env` | `"environment"` |
| `"stdio"` transport | `"type": "local"` |

### Cursor: streamable-http guard

Cursor does not support the `"streamable-http"` transport string; it expects `"type": "http"`.
`mcp-synchro` automatically rewrites `transport: "streamable-http"` to `type: "http"` when
writing Cursor configs, and drops the `transport` key.

## Preserving non-MCP data

`mcp-synchro` reads the **entire** agent config file but only modifies the MCP servers slice.
Everything else — API keys, UI preferences, keybindings, extension settings — is left intact.

The read/write cycle is:

1. Read whole file into a raw `dict`.
2. Extract the MCP section identified by `mcp_key` (and `mcp_wrapper_key` if present).
3. Replace that slice with the transformed SoT content.
4. Write the whole `dict` back to disk.
