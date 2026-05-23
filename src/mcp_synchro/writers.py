# this_file: src/mcp_synchro/writers.py
"""Writes config files. JSON, TOML, we don't judge."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import tomli_w
from loguru import logger

from mcp_synchro.agents import AgentDef
from mcp_synchro.models import McpServersConfig


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Dumps a dict to a JSON file. Pretty-prints it so humans can still read it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_toml(path: Path, data: dict[str, Any]) -> None:
    """Dumps a dict to a TOML file. Because some agents (Codex) like it that way."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        tomli_w.dump(data, f)


def _to_opencode_server(data: dict[str, Any]) -> dict[str, Any]:
    """Translates standard MCP back into OpenCode's weird dialect.

    We pack `command` and `args` back into a single array, rename `env` to `environment`,
    and call `stdio` `local`.
    """
    result = dict(data)
    # Merge command + args into command array
    cmd = result.pop("command", None)
    args = result.pop("args", [])
    if cmd:
        result["command"] = [cmd] + (args or [])
        result["enabled"] = True
        result["type"] = "local"
    # Convert "env" to "environment"
    if "env" in result:
        result["environment"] = result.pop("env")
    # Convert type
    if result.get("type") == "stdio":
        result["type"] = "local"
    elif "type" not in result:
        result["type"] = "local"
    return result


def _dict_to_array(servers: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Turns our clean dictionary of servers into a flat list. Why? Because VTCode says so.
    We inject the dictionary key as a `name` property inside each item.
    """
    result = []
    for name, config in servers.items():
        entry = {"name": name}
        entry.update(config)
        result.append(entry)
    return result


def _normalize_for_agent(
    server_dict: dict[str, Any],
    agent: AgentDef,
    resolve_commands: bool = True,
) -> dict[str, Any]:
    """Applies all agent-specific mappings and conventions."""
    mutated = dict(server_dict)

    # 1. Resolve path/command on macOS GUI if enabled
    if (
        resolve_commands
        and sys.platform == "darwin"
        and agent.id in ("antigravity-desktop", "antigravity-ide")
    ):
        cmd = mutated.get("command")
        if cmd and not cmd.startswith(("/", ".")):
            # Detect commands likely not in /usr/bin or /usr/local/bin
            targets = {
                "npx",
                "uvx",
                "bunx",
                "python3",
                "python",
                "node",
                "npm",
                "bun",
                "deno",
            }
            if cmd in targets:
                resolved = shutil.which(cmd)
                if resolved:
                    mutated["command"] = resolved
                    logger.warning(
                        f"Auto-resolved command '{cmd}' to absolute path '{resolved}' for agent '{agent.id}' to bypass macOS GUI PATH bug. "
                        "If you experience issues, consider launching the GUI app from the terminal."
                    )

    # 2. OpenCode normalization
    if agent.id == "opencode":
        return _to_opencode_server(mutated)

    # 3. Handle key naming per agent settings
    if agent.remote_url_key == "serverUrl":
        if mutated.get("url"):
            mutated["serverUrl"] = mutated["url"]
        mutated.pop("url", None)
        mutated.pop("httpUrl", None)
        if agent.transport_indicator == "implicit":
            mutated.pop("type", None)
            mutated.pop("transport", None)

    elif agent.remote_url_key == "httpUrl":
        transport_val = mutated.get("transport") or mutated.get("type")
        is_sse = transport_val in ("sse", "websocket")
        if mutated.get("url"):
            if is_sse:
                mutated["url"] = mutated["url"]
                mutated.pop("httpUrl", None)
            else:
                mutated["httpUrl"] = mutated["url"]
                mutated.pop("url", None)
        mutated.pop("serverUrl", None)
        if agent.transport_indicator == "implicit":
            mutated.pop("type", None)
            mutated.pop("transport", None)

    else:  # remote_url_key == "url" (default)
        if mutated.get("url"):
            mutated["url"] = mutated["url"]
        mutated.pop("serverUrl", None)
        mutated.pop("httpUrl", None)
        if agent.transport_indicator == "implicit":
            mutated.pop("type", None)
            mutated.pop("transport", None)

    # 4. Cursor streamable-http guardrail
    if agent.id == "cursor":
        transport_val = mutated.get("transport") or mutated.get("type")
        if transport_val in ("http", "streamable-http", "streamablehttp"):
            mutated["type"] = "http"
            mutated.pop("transport", None)

    return mutated


def update_mcp_servers(
    data: dict[str, Any],
    mcp_config: McpServersConfig,
    agent: AgentDef,
    resolve_commands: bool = True,
) -> dict[str, Any]:
    """Surgically replaces the MCP chunk of a config without breaking the rest of it.

    Args:
        data: The whole enchilada (the raw file contents).
        mcp_config: Our fresh, shiny MCP servers.
        agent: The rules dictating where and how to shove the servers in.
        resolve_commands: Auto-resolve stdio executable commands to absolute paths.

    Returns:
        A frankenstein dictionary ready to be written to disk.
    """
    result = data.copy()

    # Convert to appropriate format
    if agent.is_toml:
        new_servers = mcp_config.to_toml_dict()
    else:
        new_servers = mcp_config.to_dict()

    # Normalize per agent
    new_servers = {
        name: _normalize_for_agent(cfg, agent, resolve_commands)
        if isinstance(cfg, dict)
        else cfg
        for name, cfg in new_servers.items()
    }

    if agent.server_format == "array":
        new_servers_data: dict[str, Any] | list[dict[str, Any]] = _dict_to_array(
            new_servers
        )
    else:
        new_servers_data = new_servers

    # Handle wrapper key (e.g., VS Code's "mcp" -> "servers")
    if agent.mcp_wrapper_key:
        if agent.mcp_wrapper_key not in result:
            result[agent.mcp_wrapper_key] = {}
        result[agent.mcp_wrapper_key][agent.mcp_key] = new_servers_data
    else:
        result[agent.mcp_key] = new_servers_data

    return result


def write_agent_config(
    path: Path,
    data: dict[str, Any],
    mcp_config: McpServersConfig,
    agent: AgentDef,
    resolve_commands: bool = True,
) -> None:
    """Writes the updated config to disk. Safely.

    We take the raw data we read earlier, splice in our updated MCP servers,
    and write it back in the native format (JSON or TOML). The agent's other
    settings remain untouched.

    Args:
        path: Where the file lives.
        data: The raw baseline data.
        mcp_config: The new MCP configuration payload.
        agent: The agent definition mapping the rules.
        resolve_commands: Auto-resolve stdio executable commands to absolute paths.
    """
    updated = update_mcp_servers(data, mcp_config, agent, resolve_commands)

    if agent.is_toml:
        write_toml(path, updated)
    else:
        write_json(path, updated)

    logger.debug(f"Wrote {len(mcp_config.servers)} servers to {path}")
