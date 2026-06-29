---
title: Contributing & Style Guide
---

# Contributing & Style Guide

See also [`STYLE_GUIDE.md`](https://github.com/twardoch/mcp-synchro/blob/main/STYLE_GUIDE.md)
in the repository root for a self-contained reference.

## Code style

- **Python 3.12+**.  Use `from __future__ import annotations` in every module.
- **Ruff** enforces formatting and linting (`line-length = 88`, `target-version = "py312"`).
- **mypy strict** must pass on `src/`.
- **Type hints** on every function signature.  Prefer `list` / `dict` / `X | Y` over `List` / `Dict` / `Optional`.
- Functions ≤ 20 lines, files ≤ 200 lines (guidelines, not hard limits).
- `pathlib.Path` for all file system operations — never `os.path`.

## Naming

- Test functions: `test_<what>_when_<condition>_then_<result>`.
- Constants: `UPPER_SNAKE_CASE`.
- Private helpers: leading underscore (`_camel_to_snake`).
- `this_file:` comment near the top of every source file, path relative to project root.

## Domain conventions

### camelCase vs snake_case

The MCP ecosystem is split:

- **JSON configs** (most agents): field names are `camelCase` — `mcpServers`, `alwaysAllow`, `bearerTokenEnvVar`.
- **TOML configs** (Codex CLI): field names are `snake_case` — `mcp_servers`, `always_allow`, `bearer_token_env_var`.

`mcp-synchro` stores the canonical form as `camelCase` in the SoT and in `McpServer` model fields,
and converts to `snake_case` only when writing Codex TOML.  The conversion helpers live in
`models.py`:

```python
def _camel_to_snake(name: str) -> str: ...   # "alwaysAllow" → "always_allow"
def _snake_to_camel(name: str) -> str: ...   # "always_allow" → "alwaysAllow"
```

The rule is mechanical: insert `_` before every capital letter, lower-case the whole string
(camel→snake), or capitalize the first letter of each underscore-separated part after the first
(snake→camel).  The conversion is bijective for the field names used in practice.

### Remote URL keys

The canonical URL field in the SoT is always `url`.  On write, `mcp-synchro` renames it to
the agent's `remote_url_key`:

- `"url"` — Claude, Cursor, VS Code, Codex, most agents (default)
- `"serverUrl"` — Antigravity, Windsurf
- `"httpUrl"` — Gemini CLI (legacy, for Streamable HTTP)

### Transport indicator

- `explicit` (default): the `type` field is written to the agent config.
- `implicit`: no `type` / `transport` field; the agent infers transport from the URL.

## Testing

- Every new behaviour needs at least one test in `tests/test_all.py`.
- Fixtures (static JSON / TOML files) live under `tests/fixtures/`.
- Use `tmp_path` (pytest built-in) for any file system operations.
- Use `unittest.mock.patch` — never touch the real SoT or agent configs during tests.
- 0 failures required before any commit or PR.

## Commit style

Conventional commits: `type(scope): description`.

Common types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.

Example: `feat(agents): add Antigravity 2.0 support with serverUrl mapping`.

## Adding a new agent

1. Add an entry to `src/mcp_synchro/agents.json` following the existing schema.
2. Run `mcp-synchro list` locally to confirm the agent appears.
3. Add a test asserting the new agent's ID and paths are present in `load_all_agent_defs()`.
4. Update `src_docs/md/supported-agents.md` with a new row in the agent table.
5. Update `CHANGELOG.md`.
