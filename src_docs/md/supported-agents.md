---
title: Supported Agents
---

# Supported Agents

`mcp-synchro` ships with built-in definitions for **41 agents** across macOS, Windows, and Linux.
Definitions live in `src/mcp_synchro/agents.json` and can be extended or overridden by placing a
`mcp-synchro.json` file in your config directory.

## Agent table

> **Config key**: the JSON/TOML key that holds the MCP server map.
> **Wrapper**: an outer key that encloses the config key (e.g. VS Code uses `{"mcp": {"servers": …}}`).
> **Remote URL key**: the key used for remote/HTTP server URLs in that agent's native format.

| Agent | ID | Format | Config key | Wrapper | Remote URL key | Platforms |
|-------|----|--------|-----------|---------|---------------|-----------|
| 5ire | `5ire` | JSON | `mcpServers` | — | `url` | all |
| AI Panel | `ai-panel` | JSON | `mcpServers` | — | `url` | all |
| AI Panel IDSN | `ai-panel-idsn` | JSON | `mcpServers` | — | `url` | all |
| Amp | `amp` | JSON | `mcpServers` | `amp` | `url` | all |
| Antigravity CLI (agy) | `antigravity-cli` | JSON | `mcpServers` | — | `serverUrl` | all |
| Antigravity Desktop | `antigravity-desktop` | JSON | `mcpServers` | — | `serverUrl` | all |
| Antigravity IDE | `antigravity-ide` | JSON | `mcpServers` | — | `serverUrl` | all |
| Augment | `augment` | JSON | `mcpServers` | — | `url` | all |
| BoltAI | `boltai` | JSON | `mcpServers` | — | `url` | all |
| Claude Code | `claude-code` | JSON | `mcpServers` | — | `url` | all |
| Claude Desktop | `claude-desktop` | JSON | `mcpServers` | — | `url` | all |
| Cline (VS Code) | `cline-vscode` | JSON | `mcpServers` | — | `url` | all |
| Codex CLI | `codex` | **TOML** | `mcp_servers` | — | `url` | all |
| Continue | `continue` | JSON | `mcpServers` | — | `url` | all |
| Crush | `crush` | JSON | `mcp` | — | `url` | all |
| Cursor | `cursor` | JSON | `mcpServers` | — | `url` | all |
| Gemini CLI *(deprecated 2026-06-18)* | `gemini` | JSON | `mcpServers` | — | `httpUrl` | all |
| GitHub Copilot CLI | `copilot-cli` | JSON | `mcpServers` | — | `url` | all |
| Jan | `jan` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (Antigravity) | `kilo-antigravity` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (Cursor) | `kilo-cursor` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (Trae) | `kilo-trae` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (VS Code) | `kilo-vscode` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (VS Code Insiders) | `kilo-vscode-insiders` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code (Windsurf) | `kilo-windsurf` | JSON | `mcpServers` | — | `url` | all |
| Kilo Code CLI | `kilo-cli` | JSON | `mcpServers` | — | `url` | all |
| MATE | `mate` | JSON | `mcpServers` | — | `url` | all |
| MCP Sync | `mcp-sync` | JSON | `mcpServers` | — | `url` | all |
| OpenCode | `opencode` | JSON | `mcp` | — | *(command array)* | all |
| Qwen Code | `qwen` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (Antigravity) | `roo-antigravity` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (Cursor) | `roo-cursor` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (Trae) | `roo-trae` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (VS Code) | `roo-vscode` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (VS Code Insiders) | `roo-vscode-insiders` | JSON | `mcpServers` | — | `url` | all |
| Roo Code (Windsurf) | `roo-windsurf` | JSON | `mcpServers` | — | `url` | all |
| Trae | `trae` | JSON | `mcpServers` | — | `url` | all |
| VS Code | `vscode` | JSON | `servers` | `mcp` | `url` | all |
| VS Code Insiders | `vscode-insiders` | JSON | `servers` | — | `url` | all |
| VTCode | `vtcode` | **TOML** | `providers` | `mcp` | `url` | all |
| Windsurf | `windsurf` | JSON | `mcpServers` | — | `serverUrl` | all |

## Special-format agents

### Codex CLI (TOML)

Codex writes its config in TOML instead of JSON and uses **snake_case** keys.

```toml
[mcp_servers."filesystem"]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem"]

[mcp_servers."github"]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
bearer_token_env_var = "GITHUB_TOKEN"
```

`mcp-synchro` converts `camelCase` ↔ `snake_case` automatically when reading or writing Codex configs.

### OpenCode (command array)

OpenCode stores the command and its arguments **as a single array** under the `"command"` key,
uses `"environment"` instead of `"env"`, and calls the type `"local"` instead of `"stdio"`.

```json
{
  "mcp": {
    "my-server": {
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
      "environment": { "GITHUB_TOKEN": "ghp_..." },
      "type": "local"
    }
  }
}
```

`mcp-synchro` splits the array back into `command` + `args` on read, and merges them on write.

### VS Code (wrapper key)

VS Code wraps the server map in an outer `"mcp"` object:

```json
{
  "mcp": {
    "servers": {
      "my-server": { "command": "npx", "args": [...] }
    }
  }
}
```

### Antigravity (serverUrl + tool cap)

All three Antigravity products (Desktop, IDE, CLI) use `serverUrl` instead of `url` for remote
servers and rely on an **implicit** transport indicator (no `type` or `transport` field needed).
They also enforce a **100-tool-per-server hard cap**; use `--probe-tools` on push to detect
servers that would be silently rejected.

## Deprecated agents

| Agent | ID | Deprecated since | Successor |
|-------|----|-----------------|-----------|
| Gemini CLI | `gemini` | 2026-06-18 | `antigravity-cli` |

Run `mcp-synchro migrate gemini --to antigravity-cli` to one-shot migrate your legacy config.

## Adding custom agents

Place a `mcp-synchro.json` file in your config directory (`~/.config/mcp-synchro/` on Linux/macOS):

```json
{
  "agents": {
    "my-custom-agent": {
      "name": "My Custom Agent",
      "description": "Internal tooling agent",
      "config_format": "json",
      "mcp_key": "mcpServers",
      "paths": {
        "darwin": "~/.myagent/config.json",
        "linux": "~/.myagent/config.json",
        "win32": "%APPDATA%/myagent/config.json"
      }
    }
  }
}
```

Custom definitions are merged over the built-in list; same `id` wins (your definition takes precedence).
