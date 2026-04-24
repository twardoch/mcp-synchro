# this_file: src/mcp_synchro/agents.py
"""The hunting dogs. Defines where each AI agent hides its config file and how to sniff it out."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class AgentDef:
    """A dossier on a specific AI agent.

    Tells us what format it expects (JSON, TOML), what key holds the servers
    (e.g., `mcpServers` or `mcp_servers`), and where it hides its config on
    Mac, Windows, and Linux.
    """

    id: str
    name: str
    description: str
    config_format: str  # "json" or "toml"
    mcp_key: str  # "mcpServers", "mcp_servers", "mcp", "servers", "providers"
    paths: dict[str, str]  # platform -> path template
    mcp_wrapper_key: str | None = (
        None  # e.g., "mcp" for VS Code's {"mcp": {"servers": ...}}
    )
    command_as_array: bool = False  # OpenCode uses ["cmd", "arg1", ...] for command
    env_key: str | None = None  # OpenCode uses "environment" instead of "env"
    server_format: str = "dict"  # "dict" (default) or "array" (VTCode)

    @property
    def is_toml(self) -> bool:
        """Does this agent speak TOML instead of JSON?"""
        return self.config_format == "toml"

    def get_path_template(self) -> str | None:
        """Grabs the raw file path template for the OS we\'re currently running on."""
        return self.paths.get(sys.platform)

    def resolve_path(self) -> Path | None:
        """Turns a path template into a real, absolute path.

        Expands `~` on Unix and `%APPDATA%` or `%USERPROFILE%` on Windows.
        Returns None if we don\'t know where this agent lives on this OS.
        """
        template = self.get_path_template()
        if template is None:
            return None

        # Expand environment variables on Windows
        if sys.platform == "win32":
            for var in ("APPDATA", "USERPROFILE", "LOCALAPPDATA"):
                placeholder = f"%{var}%"
                if placeholder in template:
                    env_val = os.environ.get(var, "")
                    template = template.replace(placeholder, env_val)

        # Expand ~ for home directory
        path = Path(template).expanduser()
        return path

    def config_exists(self) -> bool:
        """Is the file actually sitting on the disk right now?"""
        path = self.resolve_path()
        return path is not None and path.exists()


@dataclass
class DiscoveredAgent:
    """A pairing of an Agent dossier with the actual physical file we found on disk."""

    agent: AgentDef
    path: Path


def load_agents_json(path: Path) -> dict[str, Any]:
    """Reads an `agents.json` map from disk."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_builtin_agents_path() -> Path:
    """Finds our baked-in `agents.json` that ships with the package."""
    return Path(__file__).parent / "agents.json"


def parse_agent_defs(data: dict[str, Any]) -> list[AgentDef]:
    """Translates the raw JSON payload into a list of strongly-typed AgentDefs."""
    agents_data = data.get("agents", {})
    result: list[AgentDef] = []
    for agent_id, agent_info in agents_data.items():
        result.append(
            AgentDef(
                id=agent_id,
                name=agent_info["name"],
                description=agent_info.get("description", ""),
                config_format=agent_info.get("config_format", "json"),
                mcp_key=agent_info.get("mcp_key", "mcpServers"),
                paths=agent_info.get("paths", {}),
                mcp_wrapper_key=agent_info.get("mcp_wrapper_key"),
                command_as_array=agent_info.get("command_as_array", False),
                env_key=agent_info.get("env_key"),
                server_format=agent_info.get("server_format", "dict"),
            )
        )
    return result


def load_all_agent_defs(user_agents_path: Path | None = None) -> list[AgentDef]:
    """Compiles the master list of all known AI agents.

    Loads our built-in list first, then layers any custom user definitions
    on top. User configs always win ties.
    """
    # Load built-in
    builtin_path = get_builtin_agents_path()
    builtin_data = load_agents_json(builtin_path)
    agents_by_id: dict[str, AgentDef] = {}
    for agent in parse_agent_defs(builtin_data):
        agents_by_id[agent.id] = agent

    # Load user override if provided
    if user_agents_path and user_agents_path.exists():
        logger.debug(f"Loading user agent definitions from {user_agents_path}")
        user_data = load_agents_json(user_agents_path)
        for agent in parse_agent_defs(user_data):
            agents_by_id[agent.id] = agent

    return sorted(agents_by_id.values(), key=lambda a: a.name)


def discover_agents(agent_defs: list[AgentDef] | None = None) -> list[DiscoveredAgent]:
    """Scours the hard drive for every known AI agent.

    If we find a config file exactly where the AgentDef said it would be,
    we add it to the discovered list.

    Args:
        agent_defs: A custom list of targets to hunt. If None, we hunt everything.

    Returns:
        A list of confirmed hits.
    """
    if agent_defs is None:
        agent_defs = load_all_agent_defs()

    discovered: list[DiscoveredAgent] = []
    for agent in agent_defs:
        path = agent.resolve_path()
        if path is not None and path.exists():
            discovered.append(DiscoveredAgent(agent=agent, path=path))
            logger.debug(f"Found {agent.name}: {path}")
        else:
            logger.debug(f"Not found: {agent.name} ({path})")

    return discovered
