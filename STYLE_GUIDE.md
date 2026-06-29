# Style Guide

## Language & runtime

- **Python 3.12+**.  `from __future__ import annotations` at the top of every module.
- Target CPython; no PyPy-specific workarounds.

## Formatting & linting

- **Ruff** (`line-length = 88`, `target-version = "py312"`, rules E/W/F/I/B/UP/RUF).
- **mypy strict** must pass on `src/`.
- Run before committing: `uvx ruff check --fix . && uvx ruff format . && uvx mypy src/`

## Type hints

- Annotate every function parameter and return value.
- Prefer the built-in generics: `list[str]`, `dict[str, Any]`, `X | Y` (not `Optional[X]`).
- Use `from __future__ import annotations` so forward references work without quotes.

## Structure

- `src/` layout; package is `mcp_synchro`.
- Functions ≤ 20 lines (guideline).  Split helpers out rather than nesting.
- Files ≤ 200 lines (guideline).
- `pathlib.Path` for all filesystem operations.
- `loguru` for logging; `--verbose` flag enables DEBUG level.

## this_file tracking

Every source file must have a `this_file:` comment near the top (after any shebang), with the
path relative to the project root and no leading `./`:

```python
# this_file: src/mcp_synchro/models.py
```

Update the comment if you move the file.

## Domain conventions

### camelCase ↔ snake_case

The MCP ecosystem splits on naming:

| Context | Convention | Example |
|---------|-----------|---------|
| JSON configs (most agents) | camelCase | `mcpServers`, `alwaysAllow` |
| TOML configs (Codex CLI) | snake_case | `mcp_servers`, `always_allow` |
| Python model fields | camelCase | `McpServer.alwaysAllow` |

`_camel_to_snake` / `_snake_to_camel` in `models.py` are the only converters; use them instead
of ad-hoc string manipulation.

The rule: insert `_` before every uppercase letter in a camelCase string and lower-case everything.
Round-trip is bijective for all field names in practice.

### Canonical URL field

The SoT always stores remote server URLs under the `"url"` key.  Agent-specific URL keys
(`serverUrl` for Antigravity, `httpUrl` for legacy Gemini) are applied at write time via
`AgentDef.remote_url_key` and `_normalize_for_agent()`.

### Transport

- Internal canonical value for Streamable HTTP: `"http"` (after stripping `"streamable-"` prefix).
- `"explicit"` transport indicator: emit a `type` field in the output.
- `"implicit"` transport indicator: omit `type` / `transport`; agent infers from URL presence.

### Path templates

- Use `~` for Unix home directory.
- Use `%APPDATA%`, `%USERPROFILE%`, `%LOCALAPPDATA%` for Windows.
- `AgentDef.resolve_path()` handles expansion; never call `expanduser()` directly outside that method.
- The SoT path and user agent override path use `platformdirs.user_config_dir("mcp-synchro")` —
  not a template.

## Naming

- Test functions: `test_<function>_when_<condition>_then_<result>`.
- Constants: `UPPER_SNAKE_CASE`.
- Private helpers: leading underscore.

## Testing

- All tests in `tests/test_all.py`.
- Static fixtures in `tests/fixtures/` (JSON / TOML).
- `tmp_path` for any disk I/O inside tests.
- Mock everything real: `patch("mcp_synchro.config.get_sot_path", ...)`, etc.
- Target: 0 failures, ≥ 80% coverage.

## Commits

Conventional commits: `type(scope): description` (imperative mood, ≤ 72 chars).

Types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `perf`.

## Adding a new agent

1. Add entry to `src/mcp_synchro/agents.json`.
2. Run `mcp-synchro list` to verify.
3. Add a test asserting the new ID and paths in `load_all_agent_defs()`.
4. Add a row to `src_docs/md/supported-agents.md`.
5. Add an entry to `CHANGELOG.md`.
