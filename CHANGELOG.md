# Changelog

## [Unreleased]

### Added
- 16 new agent definitions in `agents.json` (total: 38 agents):
  - **Crush** (`~/.config/crush/crush.json`) - uses top-level `"mcp"` key with `type` field
  - **OpenCode** (`~/.config/opencode/opencode.json`) - uses `"mcp"` key, `command` as array, `"environment"` instead of `"env"`
  - **VTCode** (`~/.vtcode/vtcode.toml`) - TOML with `[[mcp.providers]]` array-of-tables format
  - **5ire**, **AI Panel**, **AI Panel IDSN**, **MATE**, **MCP Sync**, **Jan** - standard `mcpServers` JSON
  - **Trae** (Bytedance editor) with Roo Code and Kilo Code extensions
  - **Antigravity** editor with Roo Code and Kilo Code extensions
  - **Windsurf** Roo Code and Kilo Code extensions
  - **VS Code Insiders** base config (uses `"servers"` key like VS Code)
- New fields in `McpServer` model: `name`, `headers`, `transport`, `environment`
- `is_http` property on `McpServer` for detecting HTTP-based transports
- `AgentDef` fields: `command_as_array`, `env_key`, `server_format` for special-format agents
- Reader/writer support for OpenCode format (command arrays, environment key, local→stdio)
- Reader/writer support for VTCode format (TOML array-of-tables providers)

### Changed
- `McpServer` validation now permissive (no hard error when command/url absent) to accommodate agents that store command differently

## 0.1.0 (unreleased)

- Initial release
- Support for 22 AI agents across macOS, Windows, and Linux
- Commands: push, pull_new, pull_all, init, list, show, dump
- JSON and TOML config format support
- Source of Truth (SoT) management with platformdirs
- Rich console output with full path reporting
- Dry-run mode for all write operations
- Custom agent definitions via user override file
