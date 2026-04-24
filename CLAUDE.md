# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Scope

**One sentence:** A Python CLI tool that synchronizes MCP (Model Context Protocol) server configurations across 20+ AI agents (Claude Desktop, Cursor, Codex, Gemini CLI, Cline, Roo, etc.) on macOS, Windows, and Linux.

This is the consolidated successor to two prior implementations in `_private/synchromcp/` (Fire CLI, ~1K LOC) and `_private/mcp-xync/` (Typer CLI, ~4K LOC). The requirements spec is in `issues/101.md`.

## Architecture

### Core Concept

A single **Source of Truth (SoT)** file (`mcp.json`) lives in the user's config directory (via `platformdirs`). The SoT holds the superset of all mcpServers configs. A built-in `mcp-synchro.json` (plus optional user override) defines where each agent's config lives and how it's structured.

### Key Design Constraints

- **Config formats vary:** Most agents use JSON with `"mcpServers"` key; Codex uses TOML with `"mcp_servers"` (snake_case). Some nest the key differently (Gemini: `settings.json` with nested path).
- **Preserve non-MCP data:** When writing to an agent's config, only touch the mcpServers section; leave everything else intact.
- **Property variations across agents:** Same MCP server may need slightly different property names, types (string vs list), or structures depending on the target agent.
- **No symlinking/hardlinking:** Each agent gets its own independent config file written in its native format.
- **Platform-aware paths:** Config locations differ per OS. Use `platformdirs` for the SoT location, and agent-specific path templates with `~`, `%APPDATA%`, etc.

### CLI Commands

| Command | Purpose |
|---------|---------|
| `push` / `sync` | Push SoT configs to agent config files |
| `pull_new` | Import servers from agents not yet in SoT |
| `pull_all` / `init` | Replace SoT with deduped merge of all agent configs |

### Prior Art Reference

| Feature | synchromcp (`_private/synchromcp/`) | mcp-xync (`_private/mcp-xync/`) |
|---------|-----------------------------------|---------------------------------|
| CLI framework | `fire` | `typer` |
| Config management | Manual platform detection | `dynaconf` + `platformdirs` |
| Agent definitions | Hardcoded in `config.py` | `client_definitions.json` |
| Key insight | Readers/writers preserve non-MCP data | Global + project config tiers |
| Key insight | camelCase/snake_case auto-conversion | Fuzzy matching, interactive wizard |
| Key insight | Mount support for external volumes | Backup before write |

## Development Commands

```bash
# Setup
uv venv --python 3.12 && uv sync

# Run tests
uvx hatch test

# Lint and format
uvx ruff check --fix . && uvx ruff format .

# Type check
uvx mypy src/

# Run CLI (after install)
python -m mcp_synchro push --dry-run

# Build package
uvx hatch build

# Publish
./publish.sh  # uses uv publish
```

## Package Stack

| Package | Purpose |
|---------|---------|
| `fire` | CLI framework |
| `pydantic` v2 | Data validation, mcpServers models |
| `platformdirs` | Cross-platform config directory |
| `tomli` / `tomli-w` | TOML read/write (Codex configs) |
| `rich` | Console output, full path reporting |
| `loguru` | Logging with `--verbose` mode |
| `hatch-vcs` | Semver from git tags |

## Build System

- **`hatch`** with `hatch-vcs` for git-tag-based versioning
- `pyproject.toml` is the single source of truth for project metadata
- `src/` layout: source lives under `src/mcp_synchro/`
- Tests in `tests/` using `pytest`
- Ruff for linting/formatting (line-length 88, target py312)

## Key Domain Knowledge

### mcpServers Structure

The canonical JSON shape (originated from Claude Desktop):
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@some/mcp-server"],
      "env": { "API_KEY": "..." },
      "url": "http://...",
      "transport": "stdio|sse|streamable-http"
    }
  }
}
```

TOML equivalent (Codex): uses `[mcp_servers."server-name"]` with snake_case keys.

### Agent Config Locations

Reference: `_private/mcp-xync/mcp_sync/client_definitions.json` and `_private/synchromcp/PLAN.md` Section 1 contain comprehensive per-platform paths for all supported agents.

### Conventions

- Conventional commits: `type(scope): description`
- Test naming: `test_function_when_condition_then_result`
- Functions under 20 lines, files under 200 lines
- Type hints on all functions
- `pathlib` for all path operations
