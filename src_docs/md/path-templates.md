---
title: Path Template Expansion
---

# Path Template Expansion

Each agent definition in `agents.json` (and in your custom `mcp-synchro.json`) provides a
`"paths"` map from OS identifier to a path template string.  `mcp-synchro` expands these at
runtime to locate the agent's config file.

## OS identifiers

| Key | Matches |
|-----|---------|
| `"darwin"` | macOS (any version) |
| `"linux"` | Linux (any distribution) |
| `"win32"` | Windows (32-bit and 64-bit, per Python convention) |

The identifier is compared against `sys.platform`.  Only the entry matching the current OS
is used; others are ignored.

## Expansion rules

### Unix (`~`)

On macOS and Linux the `~` prefix is expanded to the current user's home directory via
`pathlib.Path.expanduser()`.  This is equivalent to `os.path.expanduser("~")`.

```
~/.config/mcp-synchro/mcp.json
→ /home/alice/.config/mcp-synchro/mcp.json   (Linux)
→ /Users/alice/.config/mcp-synchro/mcp.json  (macOS)
```

### Windows (`%VAR%`)

On Windows the following environment variable placeholders are expanded before `expanduser()`
is called:

| Placeholder | Environment variable | Typical value |
|-------------|---------------------|---------------|
| `%APPDATA%` | `APPDATA` | `C:\Users\Alice\AppData\Roaming` |
| `%USERPROFILE%` | `USERPROFILE` | `C:\Users\Alice` |
| `%LOCALAPPDATA%` | `LOCALAPPDATA` | `C:\Users\Alice\AppData\Local` |

```
%APPDATA%/mcp-synchro/mcp.json
→ C:\Users\Alice\AppData\Roaming\mcp-synchro\mcp.json
```

Only these three variables are expanded; arbitrary `%VAR%` placeholders are not resolved.

### Source of Truth path (platformdirs)

The SoT file (`mcp.json`) and the user agent override file (`mcp-synchro.json`) are **not**
defined via path templates in `agents.json`.  Their location is computed at runtime by
[platformdirs](https://platformdirs.readthedocs.io/) using the app name `"mcp-synchro"`:

| OS | Result of `user_config_dir("mcp-synchro")` |
|----|---------------------------------------------|
| macOS | `~/Library/Application Support/mcp-synchro` |
| Linux | `~/.config/mcp-synchro` |
| Windows | `%APPDATA%\mcp-synchro` |

The SoT path is always `<config_dir>/mcp.json`.
The user agent override path is always `<config_dir>/mcp-synchro.json`.

`platformdirs` ensures the OS-correct directory is used regardless of the
`$XDG_CONFIG_HOME` or `$HOME` environment.

## Example: adding a custom agent on macOS

```json
{
  "agents": {
    "my-agent": {
      "name": "My Agent",
      "config_format": "json",
      "mcp_key": "mcpServers",
      "paths": {
        "darwin": "~/Library/Application Support/MyAgent/config.json",
        "linux":  "~/.config/myagent/config.json",
        "win32":  "%APPDATA%/MyAgent/config.json"
      }
    }
  }
}
```

Place this file at `~/.config/mcp-synchro/mcp-synchro.json` (macOS/Linux) or
`%APPDATA%\mcp-synchro\mcp-synchro.json` (Windows).

## Workspace-scope paths

Some agents (Claude Code, Cursor, VS Code) also support project-level MCP configs.
Pass `--workspace PATH` to `push` or `pull` to target these:

| Agent | Workspace config path |
|-------|-----------------------|
| Claude Code | `.mcp.json` (project root) |
| Cursor | `.cursor/mcp.json` |
| VS Code | `.vscode/mcp.json` |

Agents that do not support workspace scope (including all Antigravity products as of June 2026)
raise an error if `--workspace` is combined with their ID.
