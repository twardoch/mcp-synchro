# Work Progress

## 2026-03-25: Issue 102 - Support all 41 config file paths

### Completed
- Researched MCP config syntax for all 41 config file paths from issue
- Checked 38 local config files (30 exist on this system)
- Identified 6 distinct config format variations across agents
- Added 16 missing agent definitions to agents.json (22 → 38 total)
- Updated McpServer model with 4 new fields for superset coverage
- Added reader/writer support for OpenCode and VTCode special formats
- Fixed 2 test failures from permissive validation change
- All 110 tests passing

### Config Format Variations Discovered
| Format | Agents | Key | Notes |
|--------|--------|-----|-------|
| Standard JSON | Claude Desktop, Cursor, BoltAI, Jan, etc. | `mcpServers` | Most common |
| VS Code JSON | VS Code, VS Code Insiders | `servers` | Under `mcp` wrapper or standalone |
| TOML | Codex CLI | `mcp_servers` | snake_case keys |
| Crush/OpenCode JSON | Crush, OpenCode | `mcp` | Direct container, no mcpServers nesting |
| VTCode TOML | VTCode | `[[mcp.providers]]` | Array-of-tables with name field |
| Extension JSON | Cline, Roo, Kilo | `mcpServers` | Same format across VS Code/Cursor/Trae/Windsurf/Antigravity |

### OpenCode Special Fields
- `command`: array instead of string (`["cmd", "arg1"]`)
- `environment`: instead of `env`
- `type`: `"local"` instead of `"stdio"`

### Test Results
- 110 tests passed, 0 failures
- Lint: all checks passed
