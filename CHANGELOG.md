# Changelog

## [Unreleased] — 2026-06-29

### Added
- **GitHub Actions CI** (`.github/workflows/ci.yml`): macOS + Ubuntu matrix, Python 3.12 & 3.13,
  Ruff lint + format check, mypy strict typecheck, pytest, wheel build artifact.
- **MkDocs documentation** (`src_docs/`): MaterialX theme; pages for Home, Supported Agents,
  Config Format Reference, Path Template Expansion, and Style Guide.
- **`STYLE_GUIDE.md`**: project-wide conventions for naming, camelCase↔snake_case rules,
  path template syntax, and how to add a new agent.
- **Pinned Antigravity 2.0 fixture** (`tests/fixtures/antigravity_mcp_config.json`):
  static fixture representing the `mcp_config.json` format used by Antigravity 2.0 (GA 2026-06-18),
  with a `serverUrl` remote server and a local stdio server.
- **Test: `test_antigravity_pinned_fixture_normalizes_serverUrl`** — verifies that reading the
  pinned Antigravity 2.0 fixture canonicalizes `serverUrl` → `url` in the internal model.
- **Test: `test_probe_tools_100_cap_guard_when_over_limit_then_warns`** — verifies that
  `push(probe_tools=True)` emits a `logger.warning` when a server exposes more than 100 tools
  (Antigravity's hardcoded per-server tool cap, added 2026-06-18).
- Extended inline documentation in `models.py`: full docstrings for `_camel_to_snake` and
  `_snake_to_camel` explaining the JSON camelCase vs. Codex TOML snake_case split.
- Extended inline documentation in `agents.py`: full docstring for `AgentDef.resolve_path`
  explaining `~`, `%APPDATA%`/`%USERPROFILE%`/`%LOCALAPPDATA%` expansion on Windows,
  and the distinction from `platformdirs`-managed SoT paths.

### Changed
- Test count: 120 → 122 (all pass).

---

## [Unreleased — May 2026]

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
