---
title: mcp-synchro
---

# mcp-synchro

**One config file. Every AI agent. Synced.**

`mcp-synchro` maintains a single **Source of Truth** (`mcp.json`) and pushes it to Claude Desktop, Cursor, Codex CLI, Antigravity (agy), VS Code, Windsurf, Cline, Roo Code, OpenCode and 30+ more — all at once.

## Quick start

```bash
pip install mcp-synchro

# See which agents are installed
mcp-synchro list

# Rebuild master file from every installed agent
mcp-synchro pull_all

# Preview push without touching anything
mcp-synchro push --dry-run

# Stamp master config onto every installed agent
mcp-synchro push
```

## Commands

| Command | Description |
|---------|-------------|
| `push` / `sync` | Stamp SoT onto every installed agent config |
| `pull_new` | Import servers not yet in the SoT (non-destructive) |
| `pull_all` / `init` | Rebuild SoT from scratch by merging all agents |
| `list` | Show all known agents and whether they are installed |
| `show` | Pretty-print the current SoT contents |
| `dump` | Print SoT as raw JSON (pipeable to `jq`) |
| `migrate FROM --to TO` | One-shot migration between agents (e.g. Gemini → agy) |
| `agy-sync` | Push to all three Antigravity products at once |
| `doctor` | Run each agent's post-write validation command |

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | false | Preview changes without writing |
| `--verbose` | false | Enable debug log output |
| `--probe-tools` | false | Probe stdio servers for tool count before push (warns if >100) |
| `--no-resolve-commands` | false | Disable macOS GUI absolute-path resolution |
| `--workspace PATH` | — | Target a project-scope config instead of the global one |

## Where the SoT lives

| OS | Path |
|----|------|
| macOS / Linux | `~/.config/mcp-synchro/mcp.json` |
| Windows | `%APPDATA%\mcp-synchro\mcp.json` |

The directory is resolved by [platformdirs](https://platformdirs.readthedocs.io/).
