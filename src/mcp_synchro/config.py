# this_file: src/mcp_synchro/config.py
"""The master record. This module handles the Source of Truth (SoT) and config directories."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from platformdirs import user_config_dir

from mcp_synchro.models import McpServersConfig

APP_NAME = "mcp-synchro"
SOT_FILENAME = "mcp.json"
USER_AGENTS_FILENAME = "mcp-synchro.json"


def get_config_dir() -> Path:
    """Finds or builds the base config directory. Plops it in the right OS-specific folder."""
    config_dir = Path(user_config_dir(APP_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_sot_path() -> Path:
    """Returns the path to our holy grail: `mcp.json`."""
    return get_config_dir() / SOT_FILENAME


def get_user_agents_path() -> Path:
    """Returns the path to the user\'s custom overrides for agent definitions."""
    return get_config_dir() / USER_AGENTS_FILENAME


def load_sot() -> McpServersConfig:
    """Pulls the Source of Truth off the disk.

    If the file doesn\'t exist yet, we don\'t crash; we just hand back a blank slate.
    """
    sot_path = get_sot_path()
    if not sot_path.exists():
        logger.debug(f"SoT not found at {sot_path}, returning empty config")
        return McpServersConfig(servers={})

    logger.debug(f"Loading SoT from {sot_path}")
    with sot_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # SoT is stored as {"mcpServers": {...}}
    mcp_data = data.get("mcpServers", {})
    return McpServersConfig.from_dict(mcp_data)


def save_sot(config: McpServersConfig) -> Path:
    """Writes the current state of the universe back to disk.

    Wraps the raw server list inside an `"mcpServers"` key so it looks like a standard config.

    Args:
        config: The heavy object holding all known MCP servers.

    Returns:
        The path to the freshly minted file.
    """
    sot_path = get_sot_path()
    sot_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"mcpServers": config.to_dict()}

    with sot_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.debug(f"Saved {len(config.servers)} servers to SoT: {sot_path}")
    return sot_path
