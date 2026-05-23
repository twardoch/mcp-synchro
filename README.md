# mcp-synchro

One config file. Every AI agent. Synced.

Keep your MCP (Model Context Protocol) server list in a single master file and push it to Claude Desktop, Cursor, Codex CLI, Gemini CLI, VS Code, Windsurf, Cline, Roo, and 15+ more — all at once.

## The problem

MCP servers are tools that AI agents can call: a filesystem browser, a web search tool, a database connector, a code executor. Every agent you use has its own config file in its own format, in its own folder, on its own path.

Add a new MCP server manually and you are editing a dozen files. Rename one and you are hunting through JSON and TOML spread across `~/Library/`, `~/.config/`, and `%APPDATA%`. One agent uses `mcpServers`, another uses `mcp_servers`. One wants JSON, one wants TOML with snake_case keys.

## The solution

`mcp-synchro` maintains a single **Source of Truth** file (`mcp.json`). You edit that one file. Then:

```bash
mcp-synchro push        # stamp your MCP servers into every agent config on this machine
mcp-synchro pull_new    # grab any servers an agent has that your master file doesn't
mcp-synchro pull_all    # rebuild the master file from scratch using every agent's current config
```

The tool reads each agent's native config format, updates only the MCP servers section, and leaves everything else (API keys, UI preferences, keybindings) untouched.

## May 2026 Ecosystem & Antigravity Support

`mcp-synchro` fully supports Google's **Antigravity 2.0 Ecosystem** introduced at Google I/O 2026, alongside deprecation and migration utilities for the legacy Gemini CLI.

### The Antigravity Split
Google has transitioned its developer interfaces into three distinct products, each with its own configuration path:
- **Antigravity Desktop 2.0**: Standalone agent desktop (`~/.gemini/antigravity/mcp_config.json`)
- **Antigravity IDE**: Developer workspace editor (`~/.gemini/antigravity-ide/mcp_config.json`)
- **Antigravity CLI (`agy`)**: High-performance terminal coding agent (`~/.gemini/antigravity-cli/mcp_config.json`)

### Legacy Gemini CLI Deprecation
The Gemini CLI is scheduled for retirement on **June 18, 2026**. The `gemini` agent definition is now deprecated. To assist in the migration, you can run:
```bash
mcp-synchro migrate gemini --to antigravity-cli
```
This command automatically imports your legacy servers from `settings.json` into `agy`'s configuration and backs up the original config.

### Field Convention Normalization
Different tools expect different formats and keys. `mcp-synchro` acts as a superset compiler for the following convention mapping:

| Agent / Interface | Remote HTTP Key | SSE / Transport Key | Transport Indicator | Auth Header Key |
|---|---|---|---|---|
| **Antigravity (Desktop, IDE, CLI)** | `serverUrl` | `serverUrl` | Implicit | `headers` |
| **Windsurf** | `serverUrl` | `serverUrl` | Implicit | `headers` |
| **Cursor** | `url` | `url` | Explicit (`type: "http"`) | `headers` |
| **VS Code** | `url` | `url` | Explicit | `headers` |
| **Gemini CLI (Legacy)** | `httpUrl` | `url` | Key Choice | `headers` |
| **Claude Desktop / Code** | `url` | `url` | Explicit | `headers` |
| **Codex CLI (TOML)** | `url` | `url` | Implicit | `headers` (snake_case) |
| **OpenCode** | (command array) | — | Explicit (`type: "local"`) | — |

### Advanced Flags & Features
- **Project Workspaces**: Use `--workspace PATH` on `push` and `pull` to target supported workspace/project configurations (e.g. `.cursor/mcp.json`, `.mcp.json`, `.vscode/mcp.json`). Unsupported agents like Antigravity will print a warning or gracefully skip workspace-level compilation.
- **macOS GUI PATH Bypass**: GUI launches of Antigravity IDE/Desktop do not inherit `.zshrc` shell configurations. Stdio command paths (like `npx`, `uvx`, `node`) are automatically auto-resolved to absolute paths. Disable using `--no-resolve-commands`.
- **Tool Cap Guardrail**: Antigravity has a hard cap of 100 tools per server. Pass `--probe-tools` on push to perform a mock JSON-RPC handshake to count server tools and print a warning if a server exceeds the limit.
- **Self-Health Validation**: Run `mcp-synchro doctor` to execute and verify each agent's configured check command (e.g., `agy mcp list`).
- **Agy-Sync Shortcut**: Run `mcp-synchro agy-sync` to sync master configurations to all 3 Antigravity products in one go.

## What MCP is

Model Context Protocol is an open standard that lets AI agents talk to external tools and data sources. Instead of baking every tool directly into an agent, you run small MCP servers locally (or remotely) and point agents at them. One MCP server for filesystem access, one for GitHub, one for your internal database — and every agent that supports MCP can use all of them.

The configuration is simple:

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
    }
  }
}
```

The problem is that every AI agent invents its own variation of this format — different key names, different file locations, sometimes TOML instead of JSON.

## Install

```bash
pip install mcp-synchro
# or
uv pip install mcp-synchro
```

## Quick start

```bash
# See which agents are detected on this machine
mcp-synchro list

# Pull all agent configs into a fresh master file
mcp-synchro pull_all

# Preview what push would do without writing anything
mcp-synchro push --dry-run

# Push your master config to all agents
mcp-synchro push
```

The master config file lives at the OS-appropriate user config directory (e.g. `~/.config/mcp-synchro/mcp.json` on Linux/macOS, `%APPDATA%\mcp-synchro\mcp.json` on Windows).

## Supported agents

Claude Desktop, Cursor, VS Code (Copilot), Windsurf, Cline, Roo Code, Codex CLI, Gemini CLI, OpenCode, 5ire, Jan, Qwen Chat, Crush, and more. Agent definitions live in a bundled JSON file and can be extended with a local override.

## Config format

The Source of Truth file uses the standard Claude Desktop JSON shape:

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/you"],
    "env": {}
  },
  "brave-search": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": { "BRAVE_API_KEY": "BSA..." }
  }
}
```

When pushing to Codex CLI (which uses TOML), `mcp-synchro` automatically converts camelCase keys to snake_case and writes the correct TOML structure. When pulling from Codex, it converts back.

## What gets preserved

Only the MCP servers section of each agent's config is touched. Claude Desktop's `globalShortcut`, Cursor's UI settings, VS Code's extension preferences — none of that is read or written.

## License

MIT
