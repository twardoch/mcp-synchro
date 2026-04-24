# this_file: src/mcp_synchro/sync.py
"""The syncing engine. Where configs get pushed, pulled, and merged."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from mcp_synchro.agents import DiscoveredAgent, discover_agents, load_all_agent_defs
from mcp_synchro.config import get_user_agents_path, load_sot, save_sot
from mcp_synchro.models import McpServersConfig
from mcp_synchro.readers import read_agent_config
from mcp_synchro.writers import write_agent_config


@dataclass
class SyncResult:
    """The receipt for a single sync operation. Did it work? What did it touch?"""

    agent_name: str
    path: Path
    success: bool
    message: str
    servers_count: int = 0


def _get_discovered_agents() -> list[DiscoveredAgent]:
    """Wakes up the hunting dogs and finds every agent currently living on this disk."""
    user_agents = get_user_agents_path()
    agent_defs = load_all_agent_defs(
        user_agents_path=user_agents if user_agents.exists() else None
    )
    return discover_agents(agent_defs)


def push(dry_run: bool = False) -> list[SyncResult]:
    """Stamps the Source of Truth onto every agent config we can find.

    We read `mcp.json` (the SoT), hunt down Claude, Cursor, Codex, etc.,
    and surgically overwrite their MCP sections. The rest of their configs
    (like UI settings or API keys) are safely ignored.

    Args:
        dry_run: Look, don\'t touch. If True, we log what we *would* do without writing files.

    Returns:
        A receipt for every agent we touched (or tried to).
    """
    results: list[SyncResult] = []
    sot = load_sot()

    if not sot.servers:
        logger.warning("SoT is empty, nothing to push")
        return [
            SyncResult(
                agent_name="SoT",
                path=Path(""),
                success=False,
                message="SoT is empty. Run 'pull_all' or 'init' first.",
            )
        ]

    discovered = _get_discovered_agents()
    if not discovered:
        return [
            SyncResult(
                agent_name="System",
                path=Path(""),
                success=False,
                message="No agent configs found on this system.",
            )
        ]

    for da in discovered:
        try:
            data, _ = read_agent_config(da.path, da.agent)

            if dry_run:
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message=f"Would write {len(sot.servers)} servers (dry run)",
                        servers_count=len(sot.servers),
                    )
                )
            else:
                write_agent_config(da.path, data, sot, da.agent)
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message=f"Wrote {len(sot.servers)} servers",
                        servers_count=len(sot.servers),
                    )
                )

        except PermissionError:
            results.append(
                SyncResult(
                    agent_name=da.agent.name,
                    path=da.path,
                    success=False,
                    message="Permission denied",
                )
            )
        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=da.agent.name,
                    path=da.path,
                    success=False,
                    message=str(e),
                )
            )

    return results


def pull_new(dry_run: bool = False) -> list[SyncResult]:
    """Scavenges for new servers the Source of Truth doesn\'t know about yet.

    If you manually added a server to Cursor, this function finds it and
    adds it to `mcp.json`. Existing servers in `mcp.json` are left untouched.

    Args:
        dry_run: Look, don\'t touch. Just tell us what new servers you found.

    Returns:
        A receipt mapping out who provided new servers.
    """
    results: list[SyncResult] = []
    sot = load_sot()
    existing_names = set(sot.servers.keys())
    new_servers: dict[str, Any] = {}

    discovered = _get_discovered_agents()
    for da in discovered:
        try:
            _, agent_config = read_agent_config(da.path, da.agent)
            if agent_config is None:
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message="No MCP servers found",
                    )
                )
                continue

            added = []
            for name, server in agent_config.servers.items():
                if name not in existing_names and name not in new_servers:
                    new_servers[name] = server
                    added.append(name)

            if added:
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message=f"New: {', '.join(added)}",
                        servers_count=len(added),
                    )
                )
            else:
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message="No new servers",
                    )
                )

        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=da.agent.name,
                    path=da.path,
                    success=False,
                    message=str(e),
                )
            )

    if new_servers:
        merged_servers = dict(sot.servers)
        merged_servers.update(new_servers)
        merged = McpServersConfig(servers=merged_servers)

        if dry_run:
            logger.info(f"Would add {len(new_servers)} new servers to SoT (dry run)")
        else:
            save_sot(merged)
            logger.info(f"Added {len(new_servers)} new servers to SoT")

    return results


def pull_all(dry_run: bool = False) -> list[SyncResult]:
    """Nukes the Source of Truth and rebuilds it from scratch by reading everyone.

    We walk through every agent config, grab every server, and throw them
    into a giant pot. If two agents have a server with the same name, the
    last agent we read wins the fight.

    Args:
        dry_run: Calculate the new world order, but don\'t commit it to disk.

    Returns:
        A receipt detailing exactly how many servers we yanked from each agent.
    """
    results: list[SyncResult] = []
    all_servers: dict[str, Any] = {}

    discovered = _get_discovered_agents()
    for da in discovered:
        try:
            _, agent_config = read_agent_config(da.path, da.agent)
            if agent_config is None:
                results.append(
                    SyncResult(
                        agent_name=da.agent.name,
                        path=da.path,
                        success=True,
                        message="No MCP servers found",
                    )
                )
                continue

            count = 0
            for name, server in agent_config.servers.items():
                all_servers[name] = server
                count += 1

            results.append(
                SyncResult(
                    agent_name=da.agent.name,
                    path=da.path,
                    success=True,
                    message=f"Found {count} servers",
                    servers_count=count,
                )
            )

        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=da.agent.name,
                    path=da.path,
                    success=False,
                    message=str(e),
                )
            )

    if all_servers:
        merged = McpServersConfig(servers=all_servers)
        if dry_run:
            logger.info(f"Would save {len(all_servers)} servers to SoT (dry run)")
        else:
            save_sot(merged)
            logger.info(f"Saved {len(all_servers)} servers to SoT")

    return results
