# this_file: src/mcp_synchro/readers.py
"""Reads config files. JSON, TOML, whatever the agent wrote."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from loguru import logger

from mcp_synchro.agents import AgentDef
from mcp_synchro.models import McpServersConfig


def read_json(path: Path) -> dict[str, Any]:
    """Cracks open a JSON file and hands back the raw dict."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_toml(path: Path) -> dict[str, Any]:
    """Cracks open a TOML file and hands back the raw dict."""
    with path.open("rb") as f:
        return tomllib.load(f)


def _array_to_dict(servers_array: list[dict[str, Any]]) -> dict[str, Any]:
    """Some agents store servers as a list instead of a dict. This fixes that.
    It rips the `name` key out of the dict and uses it as the parent key.
    """
    result = {}
    for server in servers_array:
        name = server.get("name", "")
        if name:
            server_copy = {k: v for k, v in server.items() if k != "name"}
            result[name] = server_copy
    return result


def _normalize_opencode_server(data: dict[str, Any]) -> dict[str, Any]:
    """Translates OpenCode\'s weird dialect into standard MCP.

    OpenCode puts everything in an array (`"command": ["npx", "-y", ...]`) instead
    of splitting `command` and `args`. It also says `environment` instead of `env`
    and `local` instead of `stdio`.
    """
    result = dict(data)
    # Convert command array to command + args
    cmd = result.get("command")
    if isinstance(cmd, list) and cmd:
        result["command"] = cmd[0]
        result["args"] = cmd[1:]
    # Convert "environment" to "env"
    if "environment" in result and "env" not in result:
        result["env"] = result.pop("environment")
    # Normalize type
    if result.get("type") == "local":
        result["type"] = "stdio"
    return result


def extract_mcp_servers(
    data: dict[str, Any],
    agent: AgentDef,
) -> dict[str, Any] | None:
    """Digs into the raw file data and pulls out the MCP servers chunk.

    Agents bury this in different places. Claude puts it at `"mcpServers"`. VS Code wraps
    it in `"mcp": {"servers": ...}`. Codex uses TOML snake_case. This function follows the
    map defined in the `AgentDef` to find the treasure.
    """
    # If there's a wrapper key (e.g., VS Code's "mcp" -> "servers")
    if agent.mcp_wrapper_key:
        wrapper = data.get(agent.mcp_wrapper_key)
        if isinstance(wrapper, dict):
            servers = wrapper.get(agent.mcp_key)
            if isinstance(servers, list):
                servers = _array_to_dict(servers)
            if isinstance(servers, dict):
                return servers
        return None

    # Direct key lookup
    servers = data.get(agent.mcp_key)
    if isinstance(servers, list):
        servers = _array_to_dict(servers)
    if isinstance(servers, dict):
        return servers

    return None


def read_agent_config(
    path: Path,
    agent: AgentDef,
) -> tuple[dict[str, Any], McpServersConfig | None]:
    """Reads an agent\'s config file and spits out both the raw data and the parsed servers.

    Why both? Because when we write back to this file later, we need to preserve all the
    agent\'s other settings (like theme colors or keybinds). We only ever mutate the MCP slice.

    Args:
        path: Where the file lives on disk.
        agent: The rules for how to read it.

    Returns:
        (The entire raw dictionary, The structured MCP config object if found).
    """
    logger.debug(f"Reading {agent.name} config: {path}")

    if agent.is_toml:
        data = read_toml(path)
    else:
        data = read_json(path)

    mcp_data = extract_mcp_servers(data, agent)

    if mcp_data is None:
        logger.debug(f"No MCP servers found in {path}")
        return data, None

    # Normalize OpenCode command array and environment key
    if agent.command_as_array:
        mcp_data = {
            name: _normalize_opencode_server(cfg) if isinstance(cfg, dict) else cfg
            for name, cfg in mcp_data.items()
        }
    if agent.env_key and agent.env_key != "env":
        for cfg in mcp_data.values():
            if isinstance(cfg, dict) and agent.env_key in cfg and "env" not in cfg:
                cfg["env"] = cfg.pop(agent.env_key)

    try:
        if agent.is_toml:
            config = McpServersConfig.from_toml_dict(mcp_data)
        else:
            config = McpServersConfig.from_dict(mcp_data)
        logger.debug(f"Found {len(config.servers)} servers in {agent.name}")
        return data, config
    except Exception as e:
        logger.warning(f"Failed to parse MCP servers from {path}: {e}")
        return data, None
